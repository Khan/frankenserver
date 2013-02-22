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
"""Allows API stubs to access request and system state when handling calls.

Certain API stubs require access to information about the request that triggered
the API call (e.g. user_service_stub needs to know the host name of the request
to generate continuation URLs) or system state (e.g. servers_stub).

Other stubs (e.g. taskqueue_stub, channel_stub) need to be able to dispatch
requests within the system.

An instance of a RequestInfo subclass is passed to stubs that require these
capabilities.
"""

import logging
import os
import urllib


class Error(Exception):
  pass


class ServerDoesNotExistError(Error):
  """The provided server does not exist."""


class VersionDoesNotExistError(Error):
  """The provided version does not exist."""


class InvalidInstanceIdError(Error):
  """The provided instance ID is invalid."""


class NotSupportedWithAutoScalingError(Error):
  """The requested operation is not supported for auto-scaling servers."""


class ServerAlreadyStartedError(Error):
  """The server is already started."""


class ServerAlreadyStoppedError(Error):
  """The server is already stopped."""


class BackgroundThreadLimitReachedError(Error):
  """The instance is at its background thread capacity."""


class Dispatcher(object):
  """Provides information about and dispatches requests to servers."""

  def get_server_names(self):
    """Returns a list of server names."""
    raise NotImplementedError()

  def get_versions(self, server):
    """Returns a list of versions for a server.

    Args:
      server: A str containing the name of the server.

    Returns:
      A list of str containing the versions for the specified server.

    Raises:
      ServerDoesNotExistError: The server does not exist.
    """
    raise NotImplementedError()

  def get_default_version(self, server):
    """Returns the default version for a server.

    Args:
      server: A str containing the name of the server.

    Returns:
      A str containing the default version for the specified server.

    Raises:
      ServerDoesNotExistError: The server does not exist.
    """
    raise NotImplementedError()

  def get_hostname(self, server, version, instance=None):
    """Returns the hostname for a (server, version, instance) tuple.

    If instance is set, this will return a hostname for that particular
    instances. Otherwise, it will return the hostname for load-balancing.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.
      instance: An optional str containing the instance ID.

    Returns:
      A str containing the hostname.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      InvalidInstanceIdError: The instance ID is not valid for the
          server/version or the server/version uses automatic scaling.
    """
    raise NotImplementedError()

  def set_num_instances(self, server, version, instances):
    """Sets the number of instances to run for a version of a server.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.
      instances: An int containing the number of instances to run.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    raise NotImplementedError()

  def get_num_instances(self, server, version):
    """Gets the number of instances running for a version of a server.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    raise NotImplementedError()

  def start_server(self, server, version):
    """Starts a server.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    raise NotImplementedError()

  def stop_server(self, server, version):
    """Stops a server.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    raise NotImplementedError()

  def add_event(self, runnable, eta, service=None, event_id=None):
    """Add a callable to be run at the specified time.

    Args:
      runnable: A callable object to call at the specified time.
      eta: An int containing the time to run the event, in seconds since the
          epoch.
      service: A str containing the name of the service that owns this event.
          This should be set if event_id is set.
      event_id: A str containing the id of the event. If set, this can be passed
          to update_event to change the time at which the event should run.
    """
    raise NotImplementedError()

  def update_event(self, eta, service, event_id):
    """Update the eta of a scheduled event.

    Args:
      eta: An int containing the time to run the event, in seconds since the
          epoch.
      service: A str containing the name of the service that owns this event.
      event_id: A str containing the id of the event to update.
    """
    raise NotImplementedError()

  def add_async_request(self, method, relative_url, headers, body, source_ip,
                        server_name=None, version=None, instance_id=None):
    """Dispatch an HTTP request asynchronously.

    Args:
      method: A str containing the HTTP method of the request.
      relative_url: A str containing path and query string of the request.
      headers: A list of (key, value) tuples where key and value are both str.
      body: A str containing the request body.
      source_ip: The source ip address for the request.
      server_name: An optional str containing the server name to service this
          request. If unset, the request will be dispatched to the default
          server.
      version: An optional str containing the version to service this request.
          If unset, the request will be dispatched to the default version.
      instance_id: An optional str containing the instance_id of the instance to
          service this request. If unset, the request will be dispatched to
          according to the load-balancing for the server and version.
    """
    raise NotImplementedError()

  def send_background_request(self, server_name, version, instance,
                              background_request_id):
    """Dispatch a background thread request.

    Args:
      server_name: A str containing the server name to service this
          request.
      version: A str containing the version to service this request.
      instance: The instance to service this request.
      background_request_id: A str containing the unique background thread
          request identifier.

    Raises:
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
      BackgroundThreadLimitReachedError: The instance is at its background
          thread capacity.
    """
    raise NotImplementedError()




class _LocalFakeDispatcher(Dispatcher):
  """A fake Dispatcher implementation usable by tests."""

  def __init__(self,
               server_names=None,
               server_name_to_versions=None,
               server_name_to_default_versions=None,
               server_name_to_version_to_hostname=None):
    super(_LocalFakeDispatcher, self).__init__()
    if server_names is None:
      server_names = ['default']
    if server_name_to_versions is None:
      server_name_to_versions = {'default': ['1']}
    if server_name_to_default_versions is None:
      server_name_to_default_versions = {'default': '1'}
    if server_name_to_version_to_hostname is None:
      server_name_to_version_to_hostname = {'default': {'1': 'localhost:8080'}}
    self._server_names = server_names
    self._server_name_to_versions = server_name_to_versions
    self._server_name_to_default_versions = server_name_to_default_versions
    self._server_name_to_version_to_hostname = (
        server_name_to_version_to_hostname)

  def get_server_names(self):
    """Returns a list of server names."""
    return self._server_names

  def get_versions(self, server):
    """Returns a list of versions for a server.

    Args:
      server: A str containing the name of the server.

    Returns:
      A list of str containing the versions for the specified server.

    Raises:
      ServerDoesNotExistError: The server does not exist.
    """
    if server not in self._server_name_to_versions:
      raise ServerDoesNotExistError()
    return self._server_name_to_versions[server]

  def get_default_version(self, server):
    """Returns the default version for a server.

    Args:
      server: A str containing the name of the server.

    Returns:
      A str containing the default version for the specified server.

    Raises:
      ServerDoesNotExistError: The server does not exist.
    """
    if server not in self._server_name_to_default_versions:
      raise ServerDoesNotExistError()
    return self._server_name_to_default_versions[server]

  def get_hostname(self, server, version, instance=None):
    """Returns the hostname for a (server, version, instance) tuple.

    If instance is set, this will return a hostname for that particular
    instances. Otherwise, it will return the hostname for load-balancing.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.
      instance: An optional str containing the instance ID.

    Returns:
      A str containing the hostname.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      InvalidInstanceIdError: The instance ID is not valid for the
          server/version or the server/version uses automatic scaling.
    """
    if server not in self._server_name_to_version_to_hostname:
      raise ServerDoesNotExistError()
    if version not in self._server_name_to_version_to_hostname[server]:
      raise VersionDoesNotExistError()
    if instance:

      raise InvalidInstanceIdError()
    return self._server_name_to_version_to_hostname[server][version]

  def set_num_instances(self, server, version, instances):
    """Sets the number of instances to run for a version of a server.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.
      instances: An int containing the number of instances to run.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    if server not in self._server_name_to_versions:
      raise ServerDoesNotExistError()
    if version not in self._server_name_to_versions[server]:
      raise VersionDoesNotExistError()

    raise NotSupportedWithAutoScalingError()

  def get_num_instances(self, server, version):
    """Gets the number of instances running for a version of a server.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    if server not in self._server_name_to_versions:
      raise ServerDoesNotExistError()
    if version not in self._server_name_to_versions[server]:
      raise VersionDoesNotExistError()

    raise NotSupportedWithAutoScalingError()

  def start_server(self, server, version):
    """Starts a server.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    if server not in self._server_name_to_versions:
      raise ServerDoesNotExistError()
    if version not in self._server_name_to_versions[server]:
      raise VersionDoesNotExistError()

    raise NotSupportedWithAutoScalingError()

  def stop_server(self, server, version):
    """Stops a server.

    Args:
      server: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    if server not in self._server_name_to_versions:
      raise ServerDoesNotExistError()
    if version not in self._server_name_to_versions[server]:
      raise VersionDoesNotExistError()

    raise NotSupportedWithAutoScalingError()

  def add_event(self, runnable, eta, service=None, event_id=None):
    """Add a callable to be run at the specified time.

    Args:
      runnable: A callable object to call at the specified time.
      eta: An int containing the time to run the event, in seconds since the
          epoch.
      service: A str containing the name of the service that owns this event.
          This should be set if event_id is set.
      event_id: A str containing the id of the event. If set, this can be passed
          to update_event to change the time at which the event should run.
    """
    logging.warning('Scheduled events are not supported with '
                    '_LocalFakeDispatcher')

  def update_event(self, eta, service, event_id):
    """Update the eta of a scheduled event.

    Args:
      eta: An int containing the time to run the event, in seconds since the
          epoch.
      service: A str containing the name of the service that owns this event.
      event_id: A str containing the id of the event to update.
    """
    logging.warning('Scheduled events are not supported with '
                    '_LocalFakeDispatcher')

  def add_async_request(self, method, relative_url, headers, body, source_ip,
                        server_name=None, version=None, instance_id=None):
    """Dispatch an HTTP request asynchronously.

    Args:
      method: A str containing the HTTP method of the request.
      relative_url: A str containing path and query string of the request.
      headers: A list of (key, value) tuples where key and value are both str.
      body: A str containing the request body.
      source_ip: The source ip address for the request.
      server_name: An optional str containing the server name to service this
          request. If unset, the request will be dispatched to the default
          server.
      version: An optional str containing the version to service this request.
          If unset, the request will be dispatched to the default version.
      instance_id: An optional str containing the instance_id of the instance to
          service this request. If unset, the request will be dispatched to
          according to the load-balancing for the server and version.
    """
    logging.warning('Request dispatching is not supported with '
                    '_LocalFakeDispatcher')

  def send_background_request(self, server_name, version, instance,
                              background_request_id):
    """Dispatch a background thread request.

    Args:
      server_name: A str containing the server name to service this
          request.
      version: A str containing the version to service this request.
      instance: The instance to service this request.
      background_request_id: A str containing the unique background thread
          request identifier.

    Raises:
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
      BackgroundThreadLimitReachedError: The instance is at its background
          thread capacity.
    """
    logging.warning('Request dispatching is not supported with '
                    '_LocalFakeDispatcher')
    raise BackgroundThreadLimitReachedError()

_local_dispatcher = _LocalFakeDispatcher()


class RequestInfo(object):
  """Allows stubs to lookup state linked to the request making the API call."""

  def get_request_url(self, request_id):
    """Returns the URL the request e.g. 'http://localhost:8080/foo?bar=baz'.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      The URL of the request as a string.
    """
    raise NotImplementedError()

  def get_server(self, request_id):
    """Returns the name of the server serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      A str containing the server name.
    """
    raise NotImplementedError()

  def get_version(self, request_id):
    """Returns the version of the server serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      A str containing the version.
    """
    raise NotImplementedError()

  def get_instance(self, request_id):
    """Returns the instance serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      An opaque representation of the instance serving this request. It should
      only be passed to dispatcher methods expecting an instance.
    """
    raise NotImplementedError()

  def get_dispatcher(self):
    """Returns the Dispatcher.

    Returns:
      The Dispatcher instance.
    """
    raise NotImplementedError()


class _LocalRequestInfo(RequestInfo):
  """Lookup information about a request using environment variables."""

  def get_request_url(self, request_id):
    """Returns the URL the request e.g. 'http://localhost:8080/foo?bar=baz'.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      The URL of the request as a string.
    """
    try:
      host = os.environ['HTTP_HOST']
    except KeyError:
      host = os.environ['SERVER_NAME']
      port = os.environ['SERVER_PORT']
      if port != '80':
        host += ':' + port
    url = 'http://' + host
    url += urllib.quote(os.environ.get('PATH_INFO', '/'))
    if os.environ.get('QUERY_STRING'):
      url += '?' + os.environ['QUERY_STRING']
    return url

  def get_server(self, request_id):
    """Returns the name of the server serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      A str containing the server name.
    """
    return 'default'

  def get_version(self, request_id):
    """Returns the version of the server serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      A str containing the version.
    """
    return '1'

  def get_instance(self, request_id):
    """Returns the instance serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      An opaque representation of the instance serving this request. It should
      only be passed to dispatcher methods expecting an instance.
    """
    return object()

  def get_dispatcher(self):
    """Returns the Dispatcher.

    Returns:
      The Dispatcher instance.
    """
    return _local_dispatcher


_local_request_info = _LocalRequestInfo()
