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

"""Task Queue API.

Enables an application to queue background work for itself. Work is done through
webhooks that process tasks pushed from a queue. Tasks will execute in
best-effort order of ETA. Webhooks that fail will cause tasks to be retried at a
later time. Multiple queues may exist with independent throttling controls.

Webhook URLs may be specified directly for Tasks, or the default URL scheme
may be used, which will translate Task names into URLs relative to a Queue's
base path. A default queue is also provided for simple usage.
"""



import datetime
import re
import time
import urllib
import urlparse

import taskqueue_service_pb

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import urlfetch
from google.appengine.runtime import apiproxy_errors


class Error(Exception):
  """Base-class for exceptions in this module."""


class UnknownQueueError(Error):
  """The queue specified is unknown."""


class TransientError(Error):
  """There was a transient error while accessing the queue.

  Please Try again later.
  """


class InternalError(Error):
  """There was an internal error while accessing this queue.

  If this problem continues, please contact the App Engine team through
  our support forum with a description of your problem.
  """


class InvalidTaskError(Error):
  """The task's parameters, headers, or method is invalid."""


class InvalidTaskNameError(InvalidTaskError):
  """The task's name is invalid."""


class TaskTooLargeError(InvalidTaskError):
  """The task is too large with its headers and payload."""


class TaskAlreadyExistsError(InvalidTaskError):
  """Task already exists. It has not yet run."""


class TombstonedTaskError(InvalidTaskError):
  """Task has been tombstoned."""


class InvalidUrlError(InvalidTaskError):
  """The task's relative URL is invalid."""


class BadTaskStateError(Error):
  """The task is in the wrong state for the requested operation."""


class InvalidQueueError(Error):
  """The Queue's configuration is invalid."""


class InvalidQueueNameError(InvalidQueueError):
  """The Queue's name is invalid."""


class _RelativeUrlError(Error):
  """The relative URL supplied is invalid."""


class PermissionDeniedError(Error):
  """The requested operation is not allowed for this app."""


MAX_QUEUE_NAME_LENGTH = 100

MAX_TASK_NAME_LENGTH = 500

MAX_TASK_SIZE_BYTES = 10 * (2 ** 10)

MAX_URL_LENGTH = 2083

_DEFAULT_QUEUE = 'default'

_DEFAULT_QUEUE_PATH = '/_ah/queue'

_METHOD_MAP = {
    'GET': taskqueue_service_pb.TaskQueueAddRequest.GET,
    'POST': taskqueue_service_pb.TaskQueueAddRequest.POST,
    'HEAD': taskqueue_service_pb.TaskQueueAddRequest.HEAD,
    'PUT': taskqueue_service_pb.TaskQueueAddRequest.PUT,
    'DELETE': taskqueue_service_pb.TaskQueueAddRequest.DELETE,
}

_NON_POST_METHODS = frozenset(['GET', 'HEAD', 'PUT', 'DELETE'])

_BODY_METHODS = frozenset(['POST', 'PUT'])

_TASK_NAME_PATTERN = r'^[a-zA-Z0-9-]{1,%s}$' % MAX_TASK_NAME_LENGTH

_TASK_NAME_RE = re.compile(_TASK_NAME_PATTERN)

_QUEUE_NAME_PATTERN = r'^[a-zA-Z0-9-]{1,%s}$' % MAX_QUEUE_NAME_LENGTH

_QUEUE_NAME_RE = re.compile(_QUEUE_NAME_PATTERN)


class _UTCTimeZone(datetime.tzinfo):
  """UTC timezone."""

  ZERO = datetime.timedelta(0)

  def utcoffset(self, dt):
    return self.ZERO

  def dst(self, dt):
    return self.ZERO

  def tzname(self, dt):
    return 'UTC'


_UTC = _UTCTimeZone()


def _parse_relative_url(relative_url):
  """Parses a relative URL and splits it into its path and query string.

  Args:
    relative_url: The relative URL, starting with a '/'.

  Returns:
    Tuple (path, query) where:
      path: The path in the relative URL.
      query: The query string in the URL without the '?' character.

  Raises:
    _RelativeUrlError if the relative_url is invalid for whatever reason
  """
  if not relative_url:
    raise _RelativeUrlError('Relative URL is empty')
  (scheme, netloc, path, query, fragment) = urlparse.urlsplit(relative_url)
  if scheme or netloc:
    raise _RelativeUrlError('Relative URL may not have a scheme or location')
  if fragment:
    raise _RelativeUrlError('Relative URL may not specify a fragment')
  if not path or path[0] != '/':
    raise _RelativeUrlError('Relative URL path must start with "/"')
  return path, query


def _flatten_params(params):
  """Converts a dictionary of parameters to a list of parameters.

  Any unicode strings in keys or values will be encoded as UTF-8.

  Args:
    params: Dictionary mapping parameter keys to values. Values will be
      converted to a string and added to the list as tuple (key, value). If
      a values is iterable and not a string, each contained value will be
      added as a separate (key, value) tuple.

  Returns:
    List of (key, value) tuples.
  """
  def get_string(value):
    if isinstance(value, unicode):
      return unicode(value).encode('utf-8')
    else:
      return str(value)

  param_list = []
  for key, value in params.iteritems():
    key = get_string(key)
    if isinstance(value, basestring):
      param_list.append((key, get_string(value)))
    else:
      try:
        iterator = iter(value)
      except TypeError:
        param_list.append((key, str(value)))
      else:
        param_list.extend((key, get_string(v)) for v in iterator)

  return param_list


class Task(object):
  """Represents a single Task on a queue."""

  __CONSTRUCTOR_KWARGS = frozenset([
      'countdown', 'eta', 'headers', 'method', 'name', 'params', 'url'])

  def __init__(self, payload=None, **kwargs):
    """Initializer.

    All parameters are optional.

    Args:
      payload: The payload data for this Task that will be delivered to the
        webhook as the HTTP request body. This is only allowed for POST and PUT
        methods.
      countdown: Time in seconds into the future that this Task should execute.
        Defaults to zero.
      eta: Absolute time when the Task should execute. May not be specified
        if 'countdown' is also supplied.
      headers: Dictionary of headers to pass to the webhook. Values in the
        dictionary may be iterable to indicate repeated header fields.
      method: Method to use when accessing the webhook. Defaults to 'POST'.
      name: Name to give the Task; if not specified, a name will be
        auto-generated when added to a queue and assigned to this object. Must
        match the _TASK_NAME_PATTERN regular expression.
      params: Dictionary of parameters to use for this Task. For POST requests
        these params will be encoded as 'application/x-www-form-urlencoded' and
        set to the payload. For all other methods, the parameters will be
        converted to a query string. May not be specified if the URL already
        contains a query string.
      url: Relative URL where the webhook that should handle this task is
        located for this application. May have a query string unless this is
        a POST method.

    Raises:
      InvalidTaskError if any of the parameters are invalid;
      InvalidTaskNameError if the task name is invalid; InvalidUrlError if
      the task URL is invalid or too long; TaskTooLargeError if the task with
      its payload is too large.
    """
    args_diff = set(kwargs.iterkeys()) - self.__CONSTRUCTOR_KWARGS
    if args_diff:
      raise TypeError('Invalid arguments: %s' % ', '.join(args_diff))

    self.__name = kwargs.get('name')
    if self.__name and not _TASK_NAME_RE.match(self.__name):
      raise InvalidTaskNameError(
          'Task name does not match expression "%s"; found %s' %
          (_TASK_NAME_PATTERN, self.__name))

    self.__default_url, self.__relative_url, query = Task.__determine_url(
        kwargs.get('url', ''))
    self.__headers = urlfetch._CaselessDict()
    self.__headers.update(kwargs.get('headers', {}))
    self.__method = kwargs.get('method', 'POST').upper()
    self.__payload = None
    params = kwargs.get('params', {})

    if query and params:
      raise InvalidTaskError('Query string and parameters both present; '
                             'only one of these may be supplied')

    if self.__method == 'POST':
      if payload and params:
        raise InvalidTaskError('Message body and parameters both present for '
                               'POST method; only one of these may be supplied')
      elif query:
        raise InvalidTaskError('POST method may not have a query string; '
                               'use the "params" keyword argument instead')
      elif params:
        self.__payload = Task.__encode_params(params)
        self.__headers.setdefault(
            'content-type', 'application/x-www-form-urlencoded')
      elif payload is not None:
        self.__payload = Task.__convert_payload(payload, self.__headers)
    elif self.__method in _NON_POST_METHODS:
      if payload and self.__method not in _BODY_METHODS:
        raise InvalidTaskError('Payload may only be specified for methods %s' %
                               ', '.join(_BODY_METHODS))
      if payload:
        self.__payload = Task.__convert_payload(payload, self.__headers)
      if params:
        query = Task.__encode_params(params)
      if query:
        self.__relative_url = '%s?%s' % (self.__relative_url, query)
    else:
      raise InvalidTaskError('Invalid method: %s' % self.__method)

    self.__headers_list = _flatten_params(self.__headers)
    self.__eta = Task.__determine_eta(
        kwargs.get('eta'), kwargs.get('countdown'))
    self.__enqueued = False

    if self.size > MAX_TASK_SIZE_BYTES:
      raise TaskTooLargeError('Task size must be less than %d; found %d' %
                              (MAX_TASK_SIZE_BYTES, self.size))

  @staticmethod
  def __determine_url(relative_url):
    """Determines the URL of a task given a relative URL and a name.

    Args:
      relative_url: The relative URL for the Task.

    Returns:
      Tuple (default_url, relative_url, query) where:
        default_url: True if this Task is using the default URL scheme;
          False otherwise.
        relative_url: String containing the relative URL for this Task.
        query: The query string for this task.

    Raises:
      InvalidUrlError if the relative_url is invalid.
    """
    if not relative_url:
      default_url, query = True, ''
    else:
      default_url = False
      try:
        relative_url, query = _parse_relative_url(relative_url)
      except _RelativeUrlError, e:
        raise InvalidUrlError(e)

    if len(relative_url) > MAX_URL_LENGTH:
      raise InvalidUrlError(
          'Task URL must be less than %d characters; found %d' %
          (MAX_URL_LENGTH, len(relative_url)))

    return (default_url, relative_url, query)

  @staticmethod
  def __determine_eta(eta=None, countdown=None, now=datetime.datetime.now):
    """Determines the ETA for a task.

    If 'eta' and 'countdown' are both None, the current time will be used.
    Otherwise, only one of them may be specified.

    Args:
      eta: A datetime.datetime specifying the absolute ETA or None
      countdown: Count in seconds into the future from the present time that
        the ETA should be assigned to.

    Returns:
      A datetime in the UTC timezone containing the ETA.

    Raises:
      InvalidTaskError if the parameters are invalid.
    """
    if eta is not None and countdown is not None:
      raise InvalidTaskError('May not use a countdown and ETA together')
    elif eta is not None:
      if not isinstance(eta, datetime.datetime):
        raise InvalidTaskError('ETA must be a datetime.datetime instance')
    elif countdown is not None:
      try:
        countdown = float(countdown)
      except ValueError:
        raise InvalidTaskError('Countdown must be a number')
      else:
        eta = now() + datetime.timedelta(seconds=countdown)
    else:
      eta = now()

    if eta.tzinfo is None:
      eta = eta.replace(tzinfo=_UTC)
    return eta.astimezone(_UTC)

  @staticmethod
  def __encode_params(params):
    """URL-encodes a list of parameters.

    Args:
      params: Dictionary of parameters, possibly with iterable values.

    Returns:
      URL-encoded version of the params, ready to be added to a query string or
      POST body.
    """
    return urllib.urlencode(_flatten_params(params))

  @staticmethod
  def __convert_payload(payload, headers):
    """Converts a Task payload into UTF-8 and sets headers if necessary.

    Args:
      payload: The payload data to convert.
      headers: Dictionary of headers.

    Returns:
      The payload as a non-unicode string.

    Raises:
      InvalidTaskError if the payload is not a string or unicode instance.
    """
    if isinstance(payload, unicode):
      headers.setdefault('content-type', 'text/plain; charset=utf-8')
      payload = payload.encode('utf-8')
    elif not isinstance(payload, str):
      raise InvalidTaskError(
          'Task payloads must be strings; invalid payload: %r' % payload)
    return payload

  @property
  def on_queue_url(self):
    """Returns True if this Task will run on the queue's URL."""
    return self.__default_url

  @property
  def eta(self):
    """Returns an datetime corresponding to when this Task will execute."""
    return self.__eta

  @property
  def headers(self):
    """Returns a copy of the headers for this Task."""
    return self.__headers.copy()

  @property
  def method(self):
    """Returns the method to use for this Task."""
    return self.__method

  @property
  def name(self):
    """Returns the name of this Task.

    Will be None if using auto-assigned Task names and this Task has not yet
    been added to a Queue.
    """
    return self.__name

  @property
  def payload(self):
    """Returns the payload for this task, which may be None."""
    return self.__payload

  @property
  def size(self):
    """Returns the size of this task in bytes."""
    HEADER_SEPERATOR = len(': \r\n')
    header_size = sum((len(key) + len(value) + HEADER_SEPERATOR)
                      for key, value in self.__headers_list)
    return (len(self.__method) + len(self.__payload or '') +
            len(self.__relative_url) + header_size)

  @property
  def url(self):
    """Returns the relative URL for this Task."""
    return self.__relative_url

  @property
  def was_enqueued(self):
    """Returns True if this Task has been enqueued.

    Note: This will not check if this task already exists in the queue.
    """
    return self.__enqueued

  def add(self, queue_name=_DEFAULT_QUEUE):
    """Adds this Task to a queue.

    Args:
      queue_name: Name of the queue to add this Task to. (optional)

    Returns:
      This Task itself.

    Raises:
      BadTaskStateError if this task has already been enqueued.
    """
    return Queue(queue_name).add(self)


class Queue(object):
  """Represents a Queue."""

  def __init__(self, name=_DEFAULT_QUEUE):
    """Initializer.

    Args:
      name: Name of this queue. If not supplied, defaults to the default queue.

    Raises:
      InvalidQueueNameError if the queue name is invalid.
    """
    if not _QUEUE_NAME_RE.match(name):
      raise InvalidQueueNameError(
          'Queue name does not match pattern "%s"; found %s' %
          (_QUEUE_NAME_PATTERN, name))
    self.__name = name
    self.__url = '%s/%s' % (_DEFAULT_QUEUE_PATH, self.__name)

  def add(self, task):
    """Adds a Task to this Queue.

    Args:
      task: The Task to add.

    Returns:
      The Task that was supplied to this method.

    Raises:
      BadTaskStateError if the Task has already been added to a queue.
      Error-subclass on application errors.
    """
    if task.was_enqueued:
      raise BadTaskStateError('Task has already been enqueued')

    request = taskqueue_service_pb.TaskQueueAddRequest()
    response = taskqueue_service_pb.TaskQueueAddResponse()

    adjusted_url = task.url
    if task.on_queue_url:
      adjusted_url = self.__url + task.url


    request.set_queue_name(self.__name)
    request.set_eta_usec(int(time.mktime(task.eta.utctimetuple())) * 10**6)
    request.set_method(_METHOD_MAP.get(task.method))
    request.set_url(adjusted_url)

    if task.name:
      request.set_task_name(task.name)
    else:
      request.set_task_name('')

    if task.payload:
      request.set_body(task.payload)
    for key, value in _flatten_params(task.headers):
      header = request.add_header()
      header.set_key(key)
      header.set_value(value)

    call_tuple = ('taskqueue', 'Add', request, response)
    apiproxy_stub_map.apiproxy.GetPreCallHooks().Call(*call_tuple)
    try:
      apiproxy_stub_map.MakeSyncCall(*call_tuple)
    except apiproxy_errors.ApplicationError, e:
      self.__TranslateError(e)
    else:
      apiproxy_stub_map.apiproxy.GetPostCallHooks().Call(*call_tuple)

    if response.has_chosen_task_name():
      task._Task__name = response.chosen_task_name()
    task._Task__enqueued = True
    return task

  @property
  def name(self):
    """Returns the name of this queue."""
    return self.__name

  @staticmethod
  def __TranslateError(error):
    """Translates a TaskQueueServiceError into an exception.

    Args:
      error: Value from TaskQueueServiceError enum.

    Raises:
      The corresponding Exception sub-class for that error code.
    """
    if (error.application_error ==
        taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE):
      raise UnknownQueueError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.TRANSIENT_ERROR):
      raise TransientError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR):
      raise InternalError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.TASK_TOO_LARGE):
      raise TaskTooLargeError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.INVALID_TASK_NAME):
      raise InvalidTaskNameError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_NAME):
      raise InvalidQueueNameError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.INVALID_URL):
      raise InvalidUrlError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_RATE):
      raise InvalidQueueError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED):
      raise PermissionDeniedError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.TASK_ALREADY_EXISTS):
      raise TaskAlreadyExistsError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.TOMBSTONED_TASK):
      raise TombstonedTaskError(error.error_detail)
    elif (error.application_error ==
          taskqueue_service_pb.TaskQueueServiceError.INVALID_ETA):
      raise InvalidTaskError(error.error_detail)
    else:
      raise Error('Application error %s: %s' %
                  (error.application_error, error.error_detail))


def add(*args, **kwargs):
  """Convenience method will create a Task and add it to the default queue.

  Args:
    *args, **kwargs: Passed to the Task constructor.

  Returns:
    The Task that was added to the queue.
  """
  return Task(*args, **kwargs).add()
