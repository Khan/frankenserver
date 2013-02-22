#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Manage the lifecycle of runtime processes and dispatch requests to them."""


import collections
import logging
import threading
import time

import google
from concurrent import futures

from google.appengine.tools.devappserver2 import errors


# TODO: Consolidate the various thread pools.
_THREAD_POOL = futures.ThreadPoolExecutor(max_workers=100)

NORMAL_REQUEST = 0
READY_REQUEST = 1  # A warmup request i.e. /_ah/warmup.
BACKGROUND_REQUEST = 2  # A request to create a background thread.
SHUTDOWN_REQUEST = 3  # A request to stop the server i.e. /_ah/stop.
# A request to send a command to the server for evaluation e.g. for use by
# interactive shells.
INTERACTIVE_REQUEST = 4


class CannotAcceptRequests(errors.Error):
  """An Instance cannot accept a request e.g. because it is quitting."""


class CannotQuitServingInstance(errors.Error):
  """An Instance cannot be quit e.g. because it is handling a request."""


class InvalidInstanceId(errors.Error):
  """The requested instance id is not serving."""


class RuntimeProxy(object):
  """Abstract base class for a subclass that manages a runtime process."""

  def handle(self, environ, start_response, url_map, match, request_id,
             request_type):
    """Forwards an HTTP request to a runtime process and yields the result.

    Subclasses should not override this; override handle_hook instead.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler matching this request.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      request_type: The type of the request. See *_REQUEST module constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    raise NotImplementedError()

  def start(self):
    """Starts the runtime process."""
    raise NotImplementedError()

  def wait_until_serving(self, timeout=30.0):
    """Waits until the runtime is ready to handle requests.

    Args:
      timeout: The maximum number of seconds to wait for the server to be ready.

    Raises:
      Error: if the server process exits or is not ready in "timeout" seconds.
    """
    raise NotImplementedError()

  def quit(self):
    """Terminates the runtime process."""
    raise NotImplementedError()


class Instance(object):
  """Handle requests through a RuntimeProxy."""

  def __init__(self,
               request_data,
               instance_id,
               runtime_proxy,
               max_concurrent_requests,
               max_background_threads=0,
               expect_ready_request=False):
    """Initializer for Instance.

    Args:
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
      instance_id: A string or integer representing the unique (per server) id
          of the instance.
      runtime_proxy: A RuntimeProxy instance that will be used to handle
          requests.
      max_concurrent_requests: The maximum number of concurrent requests that
          the instance can handle. If the instance does not support concurrent
          requests then the value should be 1.
      max_background_threads: The maximum number of background threads that
          the instance can handle. If the instance does not support background
          threads then the value should be 0.
      expect_ready_request: If True then the instance will be sent a special
          request (i.e. /_ah/warmup or /_ah/start) before it can handle external
          requests.
    """
    self._request_data = request_data
    self._instance_id = instance_id
    self._max_concurrent_requests = max_concurrent_requests
    self._max_background_threads = max_background_threads
    self._runtime_proxy = runtime_proxy

    self._condition = threading.Condition()

    self._num_outstanding_requests = 0  # Protected by self._condition.
    self._num_running_background_threads = 0  # Protected by self._condition.
    self._total_requests = 0  # Protected by self._condition.
    self._started = False  # Protected by self._condition.
    self._quitting = False  # Protected by self._condition.
    self._quit = False  # Protected by self._condition.
    self._last_request_end_time = time.time()  # Protected by self._condition.
    self._expecting_ready_request = expect_ready_request
    self._expecting_shutdown_request = False

    # A deque containg (start_time, end_time) 2-tuples representing completed
    # requests. This is used to compute latency and qps statistics.
    self._request_history = collections.deque()  # Protected by self._condition.

  def __repr__(self):
    statuses = []
    if not self._started:
      statuses.append('not started')
    if self._quitting:
      statuses.append('quitting')
    if self._quit:
      statuses.append('quit')
    if self._expecting_ready_request:
      statuses.append('handling ready request')

    if statuses:
      status = ' [%s]' % ' '.join(statuses)
    else:
      status = ''

    return '<Instance %s: %d/%d, total: %d%s>' % (
        self._instance_id,
        self._num_outstanding_requests,
        self._max_concurrent_requests,
        self._total_requests,
        status)

  @property
  def instance_id(self):
    """The unique string or integer id for the Instance."""
    return self._instance_id

  @property
  def total_requests(self):
    """The total number requests that the Instance has handled."""
    with self._condition:
      return self._total_requests

  @property
  def remaining_request_capacity(self):
    """The number of extra requests that the Instance can currently handle."""
    with self._condition:
      return self._max_concurrent_requests - self._num_outstanding_requests

  @property
  def remaining_background_thread_capacity(self):
    """The number of extra background threads the Instance can handle."""
    with self._condition:
      return self._max_background_threads - self._num_running_background_threads

  @property
  def num_outstanding_requests(self):
    """The number of requests that the Instance is currently handling."""
    with self._condition:
      return self._num_outstanding_requests

  @property
  def idle_seconds(self):
    """The number of seconds that the Instance has been idle.

    Will be None if no requests have ever been received.
    """
    with self._condition:
      if self._num_outstanding_requests:
        return 0.0
      else:
        return time.time() - self._last_request_end_time

  @property
  def handling_ready_request(self):
    """True if the Instance is handling or will be sent a ready request."""
    return self._expecting_ready_request

  def get_latency_60s(self):
    """Returns the average request latency over the last 60s in seconds."""
    with self._condition:
      self._trim_request_history_to_60s()
      if not self._request_history:
        return 0.0
      else:
        total_latency = sum(
            end - start for (start, end) in self._request_history)
        return total_latency / len(self._request_history)

  def get_qps_60s(self):
    """Returns the average queries-per-second over the last 60 seconds."""
    with self._condition:
      self._trim_request_history_to_60s()
      if not self._request_history:
        return 0.0
      else:
        return len(self._request_history) / 60.0

  @property
  def has_quit(self):
    with self._condition:
      return self._quit or self._quitting or self._expecting_shutdown_request

  @property
  def can_accept_requests(self):
    """True if .handle() will accept requests.

    Does not consider outstanding request volume.
    """
    with self._condition:
      return (not self._quit and
              not self._quitting and
              not self._expecting_ready_request and
              not self._expecting_shutdown_request and
              self._started)

  def _trim_request_history_to_60s(self):
    """Removes obsolete entries from _outstanding_request_history."""
    window_start = time.time() - 60
    with self._condition:
      while self._request_history:
        t, _ = self._request_history[0]
        if t < window_start:
          self._request_history.popleft()
        else:
          break

  def start(self):
    """Start the instance and the RuntimeProxy.

    Returns:
      True if the Instance was started or False, if the Instance has already
      been quit.
    """
    # TODO: This is held for a long time, which blocks other threads from
    # viewing instance state.
    with self._condition:
      if self._quit:
        return False
      self._runtime_proxy.start()
      self._runtime_proxy.wait_until_serving()
      self._last_request_end_time = time.time()
      self._started = True
    logging.debug('Started instance: %s', self)
    return True

  def quit(self, allow_async=False, force=False, expect_shutdown=False):
    """Quits the instance and the RuntimeProxy.

    Args:
      allow_async: Whether to enqueue the quit after all requests have completed
          if the instance cannot be quit immediately.
      force: Whether to force the instance to quit even if the instance is
          currently handling a request. This overrides allow_async if True.
      expect_shutdown: Whether the instance will be sent a shutdown request.

    Raises:
      CannotQuitServingInstance: if the Instance is currently handling a
          request and allow_async is False.
    """
    with self._condition:
      if self._quit:
        return
      if not self._started:
        self._quit = True
        return
      if expect_shutdown:
        self._expecting_shutdown_request = True
        return
      if (self._num_outstanding_requests or
          self._num_running_background_threads or
          self._expecting_shutdown_request):
        if not force:
          if allow_async or expect_shutdown:
            self._quitting = True
            return
          raise CannotQuitServingInstance()
      self._quit = True
      self._runtime_proxy.quit()
      self._condition.notify_all()
    logging.debug('Quit instance: %s', self)

  def reserve_background_thread(self):
    """Reserves a background thread slot.

    Raises:
      CannotAcceptRequests: if the Instance is already handling the maximum
          permissible number of background threads or is not in a state where it
          can handle background threads.
    """
    with self._condition:
      if self._quit:
        raise CannotAcceptRequests('Instance has been quit')
      if not self._started:
        raise CannotAcceptRequests('Instance has not started')
      if self._expecting_ready_request:
        raise CannotAcceptRequests('Instance is waiting for ready request')
      if not self.remaining_background_thread_capacity:
        raise CannotAcceptRequests(
            'Instance has no additional background thread capacity')
      self._num_running_background_threads += 1

  def handle(self, environ, start_response, url_map, match, request_id,
             request_type):
    """Handles an HTTP request by forwarding it to the RuntimeProxy.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler matching this request.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      request_type: The type of the request. See *_REQUEST module constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.

    Raises:
      CannotAcceptRequests: if the Instance has quit or is already handling the
          maximum permissible number of concurrent requests.
    """
    start_time = time.time()
    with self._condition:
      if self._quit:
        raise CannotAcceptRequests('Instance has been quit')
      if not self._started:
        raise CannotAcceptRequests('Instance has not started')

      if request_type not in (BACKGROUND_REQUEST, SHUTDOWN_REQUEST):
        if self._quitting:
          raise CannotAcceptRequests('Instance is shutting down')
        if self._expecting_ready_request and request_type != READY_REQUEST:
          raise CannotAcceptRequests('Instance is waiting for ready request')
        if not self.remaining_request_capacity:
          raise CannotAcceptRequests('Instance has no additional capacity')
        self._num_outstanding_requests += 1

      self._request_data.set_request_instance(request_id, self)
      self._total_requests += 1

    environ['INSTANCE_ID'] = str(self._instance_id)
    try:
      # Force the generator to complete so the code in the finally block runs
      # at the right time.
      return list(self._runtime_proxy.handle(environ,
                                             start_response,
                                             url_map,
                                             match,
                                             request_id,
                                             request_type))
    finally:
      logging.debug('Request handled by %s in %0.4fs',
                    self, time.time() - start_time)
      with self._condition:
        if request_type == READY_REQUEST:
          self._expecting_ready_request = False
        if request_type == BACKGROUND_REQUEST:
          self._num_running_background_threads -= 1
        elif request_type != SHUTDOWN_REQUEST:
          self._num_outstanding_requests -= 1
        self._last_request_end_time = time.time()
        self._trim_request_history_to_60s()
        self._request_history.append((start_time, self._last_request_end_time))
        if request_type == READY_REQUEST:
          self._condition.notify(self._max_concurrent_requests)
        elif request_type == SHUTDOWN_REQUEST:
          self._expecting_shutdown_request = False
          self.quit(allow_async=True)
        elif request_type == NORMAL_REQUEST:
          self._condition.notify()
        if (not self._num_outstanding_requests and
            not self._num_running_background_threads):
          if self._quitting:
            self.quit()

  def wait(self, timeout_time):
    """Wait for this instance to have capacity to serve a request.

    Args:
      timeout_time: A float containing a time in seconds since the epoch to wait
          until before timing out.

    Returns:
      True if the instance has request capacity or False if the timeout time was
      reached or the instance has been quit.
    """
    with self._condition:
      while (time.time() < timeout_time and not self.remaining_request_capacity
             and not self.has_quit):
        self._condition.wait(timeout_time - time.time())
      return bool(self.remaining_request_capacity)


class InstanceFactory(object):
  """An abstract factory that creates instances for an InstancePool.

  Attributes:
    max_concurrent_requests: The maximum number of concurrent requests that
        Instances created by this factory can handle. If the Instances do not
        support concurrent requests then the value should be 1.
    START_URL_MAP: An apinfo.URLMap that should be used as the default
        /_ah/start handler if no user-specified script handler matches.
    WARMUP_URL_MAP: An apinfo.URLMap that should be used as the default
        /_ah/warmup handler if no user-specified script handler matches.
  """

  START_URL_MAP = None
  WARMUP_URL_MAP = None
  # If True then the runtime supports interactive command evaluation e.g. for
  # use in interactive shells.
  SUPPORTS_INTERACTIVE_REQUESTS = False

  def __init__(self, request_data, max_concurrent_requests,
               max_background_threads=0):
    """Initializer for InstanceFactory.

    Args:
      request_data: A wsgi_request_info.WSGIRequestInfo instance that will be
          populated with Instance data for use by the API stubs.
      max_concurrent_requests: The maximum number of concurrent requests that
          Instances created by this factory can handle. If the Instances do not
          support concurrent requests then the value should be 1.
      max_background_threads: The maximum number of background threads that
          the instance can handle. If the instance does not support background
          threads then the value should be 0.
    """
    self.request_data = request_data
    self.max_concurrent_requests = max_concurrent_requests
    self.max_background_threads = max_background_threads

  def new_instance(self, instance_id, expect_ready_request=False):
    """Create and return a new Instance.

    Args:
      instance_id: A string or integer representing the unique (per server) id
          of the instance.
      expect_ready_request: If True then the instance will be sent a special
          request (i.e. /_ah/warmup or /_ah/start) before it can handle external
          requests.

    Returns:
      The newly created instance.Instance.
    """
    raise NotImplementedError()
