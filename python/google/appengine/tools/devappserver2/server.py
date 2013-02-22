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
import cStringIO
import functools
import httplib
import logging
import math
import os.path
import random
import re
import string
import threading
import time
import urlparse
import wsgiref.headers

import google
from concurrent import futures

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import appinfo
from google.appengine.api import request_info
from google.appengine.api.logservice import log_service_pb
from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import blob_image
from google.appengine.tools.devappserver2 import blob_upload
from google.appengine.tools.devappserver2 import channel
from google.appengine.tools.devappserver2 import constants
from google.appengine.tools.devappserver2 import errors
from google.appengine.tools.devappserver2 import file_watcher
from google.appengine.tools.devappserver2 import http_runtime_constants
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.devappserver2 import login

from google.appengine.tools.devappserver2 import python_runtime
from google.appengine.tools.devappserver2 import request_rewriter
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import start_response_utils
from google.appengine.tools.devappserver2 import static_files_handler
from google.appengine.tools.devappserver2 import url_handler
from google.appengine.tools.devappserver2 import wsgi_handler
from google.appengine.tools.devappserver2 import wsgi_server


_LOWER_HEX_DIGITS = string.hexdigits.lower()
_UPPER_HEX_DIGITS = string.hexdigits.upper()
_REQUEST_ID_HASH_LENGTH = 8

_THREAD_POOL = futures.ThreadPoolExecutor(max_workers=100)
_RESTART_INSTANCES_CONFIG_CHANGES = frozenset(
    [application_configuration.NORMALIZED_LIBRARIES_CHANGED,
     application_configuration.SKIP_FILES_CHANGED,
     # The server must be restarted when the handlers change because files
     # appearing in static content handlers make them unavailable to the
     # runtime.
     application_configuration.HANDLERS_CHANGED,
     application_configuration.ENV_VARIABLES_CHANGED])

_REQUEST_LOGGING_BLACKLIST_RE = re.compile(
    r'^/_ah/(?:channel/(?:dev|jsapi)|img|login|upload)')

# Fake arguments for _handle_script_request for request types that don't use
# user-specified handlers.
_EMPTY_MATCH = re.match('', '')
_DUMMY_URLMAP = appinfo.URLMap(script='/')
_SHUTDOWN_TIMEOUT = 30


def _static_files_regex_from_handlers(handlers):
  patterns = []
  for url_map in handlers:
    handler_type = url_map.GetHandlerType()
    if url_map.application_readable:
      continue
    if handler_type == appinfo.STATIC_FILES:
      patterns.append(r'(%s)' % url_map.upload)
    elif handler_type == appinfo.STATIC_DIR:
      patterns.append('(%s%s%s)' % (url_map.static_dir.rstrip(os.path.sep),
                                    re.escape(os.path.sep), r'.*'))
  return r'^%s$' % '|'.join(patterns)


class InteractiveCommandError(errors.Error):
  pass


class _ScriptHandler(url_handler.UserConfiguredURLHandler):
  """A URL handler that will cause the request to be dispatched to an instance.

  This handler is special in that it does not have a working handle() method
  since the Server's dispatch logic is used to select the appropriate Instance.
  """

  def __init__(self, url_map):
    """Initializer for _ScriptHandler.

    Args:
      url_map: An appinfo.URLMap instance containing the configuration for this
          handler.
    """
    try:
      url_pattern = re.compile('%s$' % url_map.url)
    except re.error, e:
      raise errors.InvalidAppConfigError(
          'invalid url %r in script handler: %s' % (url_map.url, e))

    super(_ScriptHandler, self).__init__(url_map, url_pattern)
    self.url_map = url_map

  def handle(self, match, environ, start_response):
    """This is a dummy method that should never be called."""
    raise NotImplementedError()


class Server(object):
  """The abstract base for all instance pool implementations."""

  def _create_instance_factory(self,
                               server_configuration):
    """Create an instance.InstanceFactory.

    Args:
      server_configuration: An application_configuration.ServerConfiguration
          instance storing the configuration data for a server.

    Returns:
      A instance.InstanceFactory subclass that can be used to create instances
      with the provided configuration.
    """
    if server_configuration.runtime in ('python', 'python27'):
      return python_runtime.PythonRuntimeInstanceFactory(
          request_data=self._request_data,
          runtime_config_getter=self._get_runtime_config,
          server_configuration=server_configuration)

    else:
      assert 0, 'unknown runtime %r' % server_configuration.runtime

  def _create_url_handlers(self):
    """Constructs URLHandlers based on the server configuration.

    Returns:
      A list of url_handler.URLHandlers corresponding that can react as
      described in the given configuration.
    """
    handlers = []
    # Add special URL handlers (taking precedence over user-defined handlers)
    url_pattern = '/%s$' % login.LOGIN_URL_RELATIVE
    handlers.append(wsgi_handler.WSGIHandler(login.application,
                                             url_pattern))
    url_pattern = '/%s' % blob_upload.UPLOAD_URL_PATH
    # The blobstore upload handler forwards successful requests back to self
    handlers.append(
        wsgi_handler.WSGIHandler(blob_upload.Application(self), url_pattern))

    url_pattern = '/%s' % blob_image.BLOBIMAGE_URL_PATTERN
    handlers.append(
        wsgi_handler.WSGIHandler(blob_image.Application(), url_pattern))

    url_pattern = '/%s' % channel.CHANNEL_URL_PATTERN
    handlers.append(
        wsgi_handler.WSGIHandler(channel.application, url_pattern))

    found_start_handler = False
    found_warmup_handler = False
    # Add user-defined URL handlers
    for url_map in self._server_configuration.handlers:
      handler_type = url_map.GetHandlerType()
      if handler_type == appinfo.HANDLER_SCRIPT:
        handlers.append(_ScriptHandler(url_map))
        if not found_start_handler and re.match('%s$' % url_map.url,
                                                '/_ah/start'):
          found_start_handler = True
        if not found_warmup_handler and re.match('%s$' % url_map.url,
                                                 '/_ah/warmup'):
          found_warmup_handler = True
      elif handler_type == appinfo.STATIC_FILES:
        handlers.append(
            static_files_handler.StaticFilesHandler(
                self._server_configuration.application_root,
                url_map))
      elif handler_type == appinfo.STATIC_DIR:
        handlers.append(
            static_files_handler.StaticDirHandler(
                self._server_configuration.application_root,
                url_map))
      else:
        assert 0, 'unexpected handler %r for %r' % (handler_type, url_map)
    # Add a handler for /_ah/start if no script handler matches.
    if not found_start_handler:
      handlers.insert(0, _ScriptHandler(self._instance_factory.START_URL_MAP))
    # Add a handler for /_ah/warmup if no script handler matches and warmup is
    # enabled.
    if (not found_warmup_handler and
        'warmup' in (self._server_configuration.inbound_services or [])):
      handlers.insert(0, _ScriptHandler(self._instance_factory.WARMUP_URL_MAP))
    return handlers

  def _get_runtime_config(self):
    runtime_config = runtime_config_pb2.Config()
    runtime_config.app_id = self._server_configuration.application
    runtime_config.version_id = self._server_configuration.version_id
    runtime_config.threadsafe = self._server_configuration.threadsafe or False
    runtime_config.application_root = (
        self._server_configuration.application_root)
    runtime_config.skip_files = str(self._server_configuration.skip_files)
    runtime_config.static_files = _static_files_regex_from_handlers(
        self._server_configuration.handlers)
    runtime_config.api_port = self._api_port

    for library in self._server_configuration.normalized_libraries:
      runtime_config.libraries.add(name=library.name, version=library.version)

    for key, value in (self._server_configuration.env_variables or {}).items():
      runtime_config.environ.add(key=str(key), value=str(value))

    if self._cloud_sql_config:
      runtime_config.cloud_sql_config.CopyFrom(self._cloud_sql_config)


    return runtime_config

  def _restart_instances(self, restart_clean):
    """Restart every instance or every instance that has serviced a request.

    Args:
      restart_clean: If False then only instances that have handled at least
          one request will be restarted.
    """
    # TODO: The instance restart strategy should be customizable
    # per runtime. Compiled languages, for example, might need to
    # recompile.
    logging.debug('Restarting instances.')
    with self._condition:
      instances_to_quit = set(inst for inst in self._instances
                              if restart_clean or inst.total_requests)
      self._instances -= instances_to_quit

    for inst in instances_to_quit:
      inst.quit(allow_async=True)

  def _handle_changes(self):
    """Handle file or configuration changes."""
    # Always check for config and file changes because checking also clears
    # pending changes.
    config_changes = self._server_configuration.check_for_updates()
    has_file_changes = self._watcher.has_changes()

    if application_configuration.HANDLERS_CHANGED in config_changes:
      handlers = self._create_url_handlers()
      with self._handler_lock:
        self._handlers = handlers

    if config_changes & _RESTART_INSTANCES_CONFIG_CHANGES:
      self._restart_instances(restart_clean=True)
    elif has_file_changes:
      self._restart_instances(restart_clean=False)

  def __init__(self,
               server_configuration,
               host,
               balanced_port,
               api_port,

               cloud_sql_config,
               request_data):
    """Initializer for Server.

    Args:
      server_configuration: An application_configuration.ServerConfiguration
          instance storing the configuration data for a server.
      host: A string containing the host that any HTTP servers should bind to
          e.g. "localhost".
      balanced_port: An int specifying the port where the balanced server for
          the pool should listen.
      api_port: The port that APIServer listens for RPC requests on.

      cloud_sql_config: A runtime_config_pb2.CloudSQL instance containing the
          required configuration for local Google Cloud SQL development. If None
          then Cloud SQL will not be available.
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
    """
    self._server_configuration = server_configuration
    self._name = server_configuration.server_name
    self._host = host
    self._api_port = api_port
    self._balanced_port = balanced_port

    self._cloud_sql_config = cloud_sql_config
    self._request_data = request_data
    self._watcher = file_watcher.get_file_watcher(
        self._server_configuration.application_root)

    self._instance_factory = self._create_instance_factory(
        self._server_configuration)
    self._handler_lock = threading.Lock()
    self._handlers = self._create_url_handlers()

    self._balanced_server = wsgi_server.WsgiServer(
        (self._host, self._balanced_port), self)
    self._quit_event = threading.Event()  # Set when quit() has been called.

  @property
  def name(self):
    """The name of the server, as defined in app.yaml.

    This value will be constant for the lifetime of the server even in the
    server configuration changes.
    """
    return self._name

  @property
  def ready(self):
    """The server is ready to handle HTTP requests."""
    return self._balanced_server.ready

  @property
  def balanced_port(self):
    """The port that the balanced HTTP server for the Server is listening on."""
    assert self._balanced_server.ready, 'balanced server not running'
    return self._balanced_server.port

  @property
  def host(self):
    """The host that the HTTP server(s) for this Server is listening on."""
    return self._host

  @property
  def balanced_address(self):
    """The address of the balanced HTTP server e.g. "localhost:8080"."""
    if self.balanced_port != 80:
      return '%s:%s' % (self.host, self.balanced_port)
    else:
      return self.host

  @property
  def max_instance_concurrent_requests(self):
    """The number of concurrent requests that each Instance can handle."""
    return self._instance_factory.max_concurrent_requests

  @property
  def server_configuration(self):
    """The application_configuration.ServerConfiguration for this server."""
    return self._server_configuration

  @property
  def supports_interactive_commands(self):
    """True if the server can evaluate arbitrary code and return the result."""
    return self._instance_factory.SUPPORTS_INTERACTIVE_REQUESTS

  def _handle_script_request(self,
                             environ,
                             start_response,
                             url_map,
                             match,
                             inst=None):
    """Handles a HTTP request that has matched a script handler.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler that matched.
      match: A re.MatchObject containing the result of the matched URL pattern.
      inst: The Instance to send the request to. If None then an appropriate
          Instance will be chosen.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    raise NotImplementedError()

  def _no_handler_for_request(self, environ, start_response, request_id):
    """Handle a HTTP request that does not match any user-defined handlers."""
    self._insert_log_message('No handlers matched this URL.', 2, request_id)
    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return ['The url "%s" does not match any handlers.' % environ['PATH_INFO']]

  def _error_response(self, environ, start_response, status):
    start_response('%d %s' % (status, httplib.responses[status]), [])
    return []

  def _handle_request(self, environ, start_response, inst=None,
                      request_type=instance.NORMAL_REQUEST):
    """Handles a HTTP request.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      inst: The Instance to send the request to. If None then an appropriate
          Instance will be chosen. Setting inst is not meaningful if the
          request does not match a "script" handler.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    if inst:
      try:
        environ['SERVER_PORT'] = str(self.get_instance_port(inst.instance_id))
      except request_info.NotSupportedWithAutoScalingError:
        environ['SERVER_PORT'] = str(self.balanced_port)
    else:
      environ['SERVER_PORT'] = str(self.balanced_port)
    with self._request_data.request(
        environ,
        self._server_configuration) as request_id:
      should_log_request = not _REQUEST_LOGGING_BLACKLIST_RE.match(
          environ['PATH_INFO'])
      environ['REQUEST_ID_HASH'] = self.generate_request_id_hash()
      if should_log_request:
        environ['REQUEST_LOG_ID'] = self.generate_request_log_id()
        if 'HTTP_HOST' in environ:
          hostname = environ['HTTP_HOST']
        elif environ['SERVER_PORT'] == '80':
          hostname = environ['SERVER_NAME']
        else:
          hostname = '%s:%s' % (environ['SERVER_NAME'], environ['SERVER_PORT'])

        if environ.get('QUERY_STRING'):
          resource = '%s?%s' % (environ['PATH_INFO'], environ['QUERY_STRING'])
        else:
          resource = environ['PATH_INFO']
        email, _, _ = login.get_user_info(environ.get('HTTP_COOKIE', ''))
        method = environ.get('REQUEST_METHOD', 'GET')
        http_version = environ.get('SERVER_PROTOCOL', 'HTTP/1.0')

        logservice = apiproxy_stub_map.apiproxy.GetStub('logservice')
        logservice.start_request(
            request_id=request_id,
            user_request_id=environ['REQUEST_LOG_ID'],
            ip=environ.get('REMOTE_ADDR', ''),
            app_id=self._server_configuration.application,
            version_id=self._server_configuration.version_id,
            nickname=email.split('@', 1)[0],
            user_agent=environ.get('HTTP_USER_AGENT', ''),
            host=hostname,
            method=method,
            resource=resource,
            http_version=http_version)

      def wrapped_start_response(status, response_headers, exc_info=None):
        response_headers.append(('Server',
                                 http_runtime_constants.SERVER_SOFTWARE))
        if should_log_request:
          headers = wsgiref.headers.Headers(response_headers)
          status_code = int(status.split(' ', 1)[0])
          content_length = int(headers.get('Content-Length', 0))
          logservice.end_request(request_id, status_code, content_length)
          logging.info('"%(method)s %(resource)s %(http_version)s" '
                       '%(status)d %(content_length)s',
                       {'method': method,
                        'resource': resource,
                        'http_version': http_version,
                        'status': status_code,
                        'content_length': content_length or '-'})
        return start_response(status, response_headers, exc_info)

      if (environ['REQUEST_METHOD'] in ('GET', 'HEAD', 'TRACE') and
          int(environ.get('CONTENT_LENGTH') or '0') != 0):
        # CONTENT_LENGTH may be empty or absent.
        wrapped_start_response('400 Bad Request', [])
        return ['"%s" requests may not contain bodies.' %
                environ['REQUEST_METHOD']]

      with self._handler_lock:
        handlers = self._handlers

      try:
        request_url = environ['PATH_INFO']
        if request_type in (instance.BACKGROUND_REQUEST,
                            instance.INTERACTIVE_REQUEST,
                            instance.SHUTDOWN_REQUEST):
          app = functools.partial(self._handle_script_request,
                                  url_map=_DUMMY_URLMAP,
                                  match=_EMPTY_MATCH,
                                  request_id=request_id,
                                  inst=inst,
                                  request_type=request_type)
          return request_rewriter.frontend_rewriter_middleware(app)(
              environ, wrapped_start_response)
        for handler in handlers:
          match = handler.match(request_url)
          if match:
            auth_failure = handler.handle_authorization(environ,
                                                        wrapped_start_response)
            if auth_failure is not None:
              return auth_failure

            if isinstance(handler, _ScriptHandler):
              app = functools.partial(self._handle_script_request,
                                      url_map=handler.url_map,
                                      match=match,
                                      request_id=request_id,
                                      inst=inst,
                                      request_type=request_type)
              return request_rewriter.frontend_rewriter_middleware(app)(
                  environ, wrapped_start_response)
            else:
              return handler.handle(match, environ, wrapped_start_response)
        return self._no_handler_for_request(environ, wrapped_start_response,
                                            request_id)
      except StandardError, e:
        logging.exception('Request to %r failed', request_url)
        wrapped_start_response('500 Internal Server Error', [], e)
        return []

  def _async_shutdown_instance(self, inst, port):
    _THREAD_POOL.submit(self._shutdown_instance, inst, port)

  def _shutdown_instance(self, inst, port):
    force_shutdown_time = time.time() + _SHUTDOWN_TIMEOUT
    try:
      environ = self.build_request_environ(
          'GET', '/_ah/stop', [], '', '0.1.0.3', port, fake_login=True)
      self._handle_request(environ,
                           start_response_utils.null_start_response,
                           inst=inst,
                           request_type=instance.SHUTDOWN_REQUEST)
      logging.debug('Sent shutdown request: %s', inst)
    except:
      logging.exception('Internal error while handling shutdown request.')
    finally:
      time_to_wait = force_shutdown_time - time.time()
      self._quit_event.wait(time_to_wait)
      inst.quit(force=True)

  def _insert_log_message(self, message, level, request_id):
    logs_group = log_service_pb.UserAppLogGroup()
    log_line = logs_group.add_log_line()
    log_line.set_timestamp_usec(int(time.time() * 1e6))
    log_line.set_level(level)
    log_line.set_message(message)
    request = log_service_pb.FlushRequest()
    request.set_logs(logs_group.Encode())
    response = api_base_pb.VoidProto()
    logservice = apiproxy_stub_map.apiproxy.GetStub('logservice')
    logservice._Dynamic_Flush(request, response, request_id)

  @staticmethod
  def generate_request_log_id():
    """Generate a random REQUEST_LOG_ID.

    Returns:
      A string suitable for use as a REQUEST_LOG_ID. The returned string is
      variable length to emulate the the production values, which encapsulate
      the application id, version and some log state.
    """
    return ''.join(random.choice(_LOWER_HEX_DIGITS)
                   for _ in range(random.randrange(30, 100)))

  @staticmethod
  def generate_request_id_hash():
    """Generate a random REQUEST_ID_HASH."""
    return ''.join(random.choice(_UPPER_HEX_DIGITS)
                   for _ in range(_REQUEST_ID_HASH_LENGTH))

  def set_num_instances(self, instances):
    """Sets the number of instances for this server to run.

    Args:
      instances: An int containing the number of instances to run.
    """
    raise request_info.NotSupportedWithAutoScalingError()

  def get_num_instances(self):
    """Returns the number of instances for this server to run."""
    raise request_info.NotSupportedWithAutoScalingError()

  def suspend(self):
    """Stops the server from serving requests."""
    raise request_info.NotSupportedWithAutoScalingError()

  def resume(self):
    """Restarts the server."""
    raise request_info.NotSupportedWithAutoScalingError()

  def get_instance_address(self, instance_id):
    """Returns the address of the HTTP server for an instance."""
    return '%s:%s' % (self.host, self.get_instance_port(instance_id))

  def get_instance_port(self, instance_id):
    """Returns the port of the HTTP server for an instance."""
    raise request_info.NotSupportedWithAutoScalingError()

  def get_instance(self, instance_id):
    """Returns the instance with the provided instance ID."""
    raise request_info.NotSupportedWithAutoScalingError()

  @property
  def supports_individually_addressable_instances(self):
    return False

  def create_interactive_command_server(self):
    """Returns a InteractiveCommandServer that can be sent user commands."""
    if self._instance_factory.SUPPORTS_INTERACTIVE_REQUESTS:
      return InteractiveCommandServer(self._server_configuration,
                                      self._host,
                                      self._balanced_port,
                                      self._api_port,

                                      self._cloud_sql_config,
                                      self._request_data)
    else:
      raise NotImplementedError('runtime does not support interactive commands')

  def build_request_environ(self, method, relative_url, headers, body,
                            source_ip, port, fake_login=False):
    if isinstance(body, unicode):
      body = body.encode('ascii')

    url = urlparse.urlsplit(relative_url)
    if port != 80:
      host = '%s:%s' % (self.host, port)
    else:
      host = self.host
    environ = {constants.FAKE_IS_ADMIN_HEADER: '1',
               'HTTP_HOST': host,
               'CONTENT_LENGTH': str(len(body)),
               'PATH_INFO': url.path,
               'QUERY_STRING': url.query,
               'REQUEST_METHOD': method,
               'REMOTE_ADDR': source_ip,
               'SERVER_NAME': self.host,
               'SERVER_PORT': str(port),
               'SERVER_PROTOCOL': 'HTTP/1.1',
               'wsgi.version': (1, 0),
               'wsgi.url_scheme': 'http',
               'wsgi.errors': cStringIO.StringIO(),
               'wsgi.multithread': True,
               'wsgi.multiprocess': True,
               'wsgi.input': cStringIO.StringIO(body)}
    if fake_login:
      environ[constants.FAKE_LOGGED_IN_HEADER] = '1'
    for key, value in headers:
      environ['HTTP_%s' % key.upper().replace('-', '_')] = value
    return environ


class AutoScalingServer(Server):
  """A pool of instances that is autoscaled based on traffic."""

  # The minimum number of seconds to wait, after quitting an idle instance,
  # before quitting another idle instance.
  _MIN_SECONDS_BETWEEN_QUITS = 60
  # The time horizon to use when calculating the number of instances required
  # to serve the current level of traffic.
  _REQUIRED_INSTANCE_WINDOW_SECONDS = 60

  _DEFAULT_AUTOMATIC_SCALING = appinfo.AutomaticScaling(
      min_pending_latency='0.1s',
      max_pending_latency='0.5s',
      min_idle_instances=1,
      max_idle_instances=1000)

  @staticmethod
  def _parse_pending_latency(timing):
    """Parse a pending latency string into a float of the value in seconds.

    Args:
      timing: A str of the form 1.0s or 1000ms.

    Returns:
      A float representation of the value in seconds.
    """
    if timing.endswith('ms'):
      return float(timing[:-2]) / 1000
    else:
      return float(timing[:-1])

  @classmethod
  def _populate_default_automatic_scaling(cls, automatic_scaling):
    for attribute in automatic_scaling.ATTRIBUTES:
      if getattr(automatic_scaling, attribute) in ('automatic', None):
        setattr(automatic_scaling, attribute,
                getattr(cls._DEFAULT_AUTOMATIC_SCALING, attribute))

  def _process_automatic_scaling(self, automatic_scaling):
    if automatic_scaling:
      self._populate_default_automatic_scaling(automatic_scaling)
    else:
      automatic_scaling = self._DEFAULT_AUTOMATIC_SCALING
    self._min_pending_latency = self._parse_pending_latency(
        automatic_scaling.min_pending_latency)
    self._max_pending_latency = self._parse_pending_latency(
        automatic_scaling.max_pending_latency)
    self._min_idle_instances = int(automatic_scaling.min_idle_instances)
    self._max_idle_instances = int(automatic_scaling.max_idle_instances)

  def __init__(self,
               server_configuration,
               host,
               balanced_port,
               api_port,

               cloud_sql_config,
               request_data):
    """Initializer for AutoScalingServer.

    Args:
      server_configuration: An application_configuration.ServerConfiguration
          instance storing the configuration data for a server.
      host: A string containing the host that any HTTP servers should bind to
          e.g. "localhost".
      balanced_port: An int specifying the port where the balanced server for
          the pool should listen.
      api_port: The port that APIServer listens for RPC requests on.

      cloud_sql_config: A runtime_config_pb2.CloudSQL instance containing the
          required configuration for local Google Cloud SQL development. If None
          then Cloud SQL will not be available.
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
    """
    super(AutoScalingServer, self).__init__(server_configuration,
                                            host,
                                            balanced_port,
                                            api_port,

                                            cloud_sql_config,
                                            request_data)

    self._process_automatic_scaling(
        self._server_configuration.automatic_scaling)

    self._instances = set()  # Protected by self._condition.
    # A deque containg (time, num_outstanding_instance_requests) 2-tuples.
    # This is used to track the maximum number of outstanding requests in a time
    # period. Protected by self._condition.
    self._outstanding_request_history = collections.deque()
    self._num_outstanding_instance_requests = 0  # Protected by self._condition.
    # The time when the last instance was quit in seconds since the epoch.
    self._last_instance_quit_time = 0  # Protected by self._condition.

    self._condition = threading.Condition()  # Protects instance state.
    self._instance_adjustment_thread = threading.Thread(
        target=self._loop_adjusting_instances)

  def start(self):
    """Start background management of the Server."""
    self._balanced_server.start()
    self._watcher.start()
    self._instance_adjustment_thread.start()

  def quit(self):
    """Stops the Server."""
    self._quit_event.set()
    self._instance_adjustment_thread.join()
    # The instance adjustment thread depends on the balanced server and the
    # watcher so wait for it exit before quitting them.
    self._watcher.quit()
    self._balanced_server.quit()
    for inst in self.instances:
      inst.quit(force=True)
    with self._condition:
      self._condition.notify_all()

  @property
  def instances(self):
    """A set of all the instances currently in the Server."""
    with self._condition:
      return set(self._instances)

  @property
  def num_outstanding_instance_requests(self):
    """The number of requests that instances are currently handling."""
    with self._condition:
      return self._num_outstanding_instance_requests

  def _handle_instance_request(self,
                               environ,
                               start_response,
                               url_map,
                               match,
                               request_id,
                               inst,
                               request_type):
    """Handles a request routed a particular Instance.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler that matched.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      inst: The instance.Instance to send the request to.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    if request_type != instance.READY_REQUEST:
      with self._condition:
        self._num_outstanding_instance_requests += 1
        self._outstanding_request_history.append(
            (time.time(), self.num_outstanding_instance_requests))
    try:
      logging.debug('Dispatching request to %s', inst)
      return inst.handle(environ, start_response, url_map, match, request_id,
                         request_type)
    finally:
      with self._condition:
        if request_type != instance.READY_REQUEST:
          self._num_outstanding_instance_requests -= 1
        self._condition.notify()

  def _handle_script_request(self,
                             environ,
                             start_response,
                             url_map,
                             match,
                             request_id,
                             inst=None,
                             request_type=instance.NORMAL_REQUEST):
    """Handles a HTTP request that has matched a script handler.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler that matched.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      inst: The instance.Instance to send the request to. If None then an
          appropriate instance.Instance will be chosen.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    if inst is not None:
      return self._handle_instance_request(
          environ, start_response, url_map, match, request_id, inst,
          request_type)

    with self._condition:
      self._num_outstanding_instance_requests += 1
      self._outstanding_request_history.append(
          (time.time(), self.num_outstanding_instance_requests))

    try:
      start_time = time.time()
      timeout_time = start_time + self._min_pending_latency
      # Loop until an instance is available to handle the request.
      while True:
        inst = self._choose_instance(timeout_time)
        if not inst:
          inst = self._add_instance(permit_warmup=False)

        try:
          logging.debug('Dispatching request to %s after %0.4fs pending',
                        inst, time.time() - start_time)
          return inst.handle(environ,
                             start_response,
                             url_map,
                             match,
                             request_id,
                             request_type)
        except instance.CannotAcceptRequests:
          continue
    finally:
      with self._condition:
        self._num_outstanding_instance_requests -= 1
        self._condition.notify()

  def _add_instance(self, permit_warmup):
    """Creates and adds a new instance.Instance to the Server.

    Args:
      permit_warmup: If True then the new instance.Instance will be sent a new
          warmup request if it is configured to receive them.

    Returns:
      The newly created instance.Instance.
    """
    perform_warmup = permit_warmup and (
        'warmup' in (self._server_configuration.inbound_services or []))

    inst = self._instance_factory.new_instance(
        self.generate_instance_id(),
        expect_ready_request=perform_warmup)

    with self._condition:
      self._instances.add(inst)

    inst.start()
    if perform_warmup:
      self._async_warmup(inst)
    else:
      with self._condition:
        self._condition.notify(self.max_instance_concurrent_requests)
    logging.debug('Created instance: %s', inst)
    return inst

  @staticmethod
  def generate_instance_id():
    return ''.join(random.choice(_LOWER_HEX_DIGITS) for _ in range(36))

  def _warmup(self, inst):
    """Send a warmup request to the given instance."""

    try:
      environ = self.build_request_environ(
          'GET', '/_ah/warmup', [], '', '0.1.0.3', self.balanced_port,
          fake_login=True)
      self._handle_request(environ,
                           start_response_utils.null_start_response,
                           inst=inst,
                           request_type=instance.READY_REQUEST)
      with self._condition:
        self._condition.notify(self.max_instance_concurrent_requests)
    except:
      logging.exception('Internal error while handling warmup request.')

  def _async_warmup(self, inst):
    """Asynchronously send a markup request to the given Instance."""
    _THREAD_POOL.submit(self._warmup, inst)

  def _trim_outstanding_request_history(self):
    """Removes obsolete entries from _outstanding_request_history."""
    window_start = time.time() - self._REQUIRED_INSTANCE_WINDOW_SECONDS
    with self._condition:
      while self._outstanding_request_history:
        t, _ = self._outstanding_request_history[0]
        if t < window_start:
          self._outstanding_request_history.popleft()
        else:
          break

  def _get_num_required_instances(self):
    """Returns the number of Instances required to handle the request load."""
    with self._condition:
      self._trim_outstanding_request_history()
      if not self._outstanding_request_history:
        return 0
      else:
        peak_concurrent_requests = max(
            current_requests
            for (t, current_requests)
            in self._outstanding_request_history)
        return int(math.ceil(peak_concurrent_requests /
                             self.max_instance_concurrent_requests))

  def _split_instances(self):
    """Returns a 2-tuple representing the required and extra Instances.

    Returns:
      A 2-tuple of (required_instances, not_required_instances):
        required_instances: The set of the instance.Instances, in a state that
                            can handle requests, required to handle the current
                            request load.
        not_required_instances: The set of the Instances contained in this
                                Server that not are not required.
    """
    with self._condition:
      num_required_instances = self._get_num_required_instances()

      available = [inst for inst in self._instances
                   if inst.can_accept_requests]
      available.sort(key=lambda inst: -inst.num_outstanding_requests)

      required = set(available[:num_required_instances])
      return required, self._instances - required

  def _choose_instance(self, timeout_time):
    """Returns the best Instance to handle a request or None if all are busy."""
    with self._condition:
      while time.time() < timeout_time:
        required_instances, not_required_instances = self._split_instances()
        if required_instances:
          # Pick the instance with the most remaining capacity to handle
          # requests.
          required_instances = sorted(
              required_instances,
              key=lambda inst: inst.remaining_request_capacity)
          if required_instances[-1].remaining_request_capacity:
            return required_instances[-1]

        available_instances = [inst for inst in not_required_instances
                               if inst.remaining_request_capacity > 0 and
                               inst.can_accept_requests]
        if available_instances:
          # Pick the instance with the *least* capacity to handle requests
          # to avoid using unnecessary idle instances.
          available_instances.sort(
              key=lambda instance: instance.num_outstanding_requests)
          return available_instances[-1]
        else:
          self._condition.wait(timeout_time - time.time())
    return None

  def _adjust_instances(self):
    """Creates new Instances or deletes idle Instances based on current load."""
    now = time.time()
    with self._condition:
      _, not_required_instances = self._split_instances()

    if len(not_required_instances) < self._min_idle_instances:
      self._add_instance(permit_warmup=True)
    elif (len(not_required_instances) > self._max_idle_instances and
          now >
          (self._last_instance_quit_time + self._MIN_SECONDS_BETWEEN_QUITS)):
      for inst in not_required_instances:
        if not  inst.num_outstanding_requests:
          try:
            inst.quit()
          except instance.CannotQuitServingInstance:
            pass
          else:
            self._last_instance_quit_time = now
            logging.debug('Quit instance: %s', inst)
            with self._condition:
              self._instances.remove(inst)
              break

  def _loop_adjusting_instances(self):
    """Loops until the Server exits, reloading, adding or removing Instances."""
    while not self._quit_event.is_set():
      if self.ready:
        self._handle_changes()
        self._adjust_instances()
      self._quit_event.wait(timeout=1)

  def __call__(self, environ, start_response):
    return self._handle_request(environ, start_response)


class ManualScalingServer(Server):
  """A pool of instances that is manually-scaled."""

  _DEFAULT_MANUAL_SCALING = appinfo.ManualScaling(instances='1')
  _MAX_REQUEST_WAIT_TIME = 10

  @classmethod
  def _populate_default_manual_scaling(cls, manual_scaling):
    for attribute in manual_scaling.ATTRIBUTES:
      if getattr(manual_scaling, attribute) in ('manual', None):
        setattr(manual_scaling, attribute,
                getattr(cls._DEFAULT_MANUAL_SCALING, attribute))

  def _process_manual_scaling(self, manual_scaling):
    if manual_scaling:
      self._populate_default_manual_scaling(manual_scaling)
    else:
      manual_scaling = self._DEFAULT_MANUAL_SCALING
    self._initial_num_instances = int(manual_scaling.instances)

  def __init__(self,
               server_configuration,
               host,
               balanced_port,
               api_port,

               cloud_sql_config,
               request_data):
    """Initializer for ManualScalingServer.

    Args:
      server_configuration: An application_configuration.ServerConfiguration
          instance storing the configuration data for a server.
      host: A string containing the host that any HTTP servers should bind to
          e.g. "localhost".
      balanced_port: An int specifying the port where the balanced server for
          the pool should listen.
      api_port: The port that APIServer listens for RPC requests on.

      cloud_sql_config: A runtime_config_pb2.CloudSQL instance containing the
          required configuration for local Google Cloud SQL development. If None
          then Cloud SQL will not be available.
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
    """
    super(ManualScalingServer, self).__init__(server_configuration,
                                              host,
                                              balanced_port,
                                              api_port,

                                              cloud_sql_config,
                                              request_data)

    self._process_manual_scaling(server_configuration.manual_scaling)

    self._instances = []  # Protected by self._condition.
    self._wsgi_servers = []  # Protected by self._condition.
    # Whether the server has been stopped. Protected by self._condition.
    self._suspended = False

    self._condition = threading.Condition()  # Protects instance state.

    # Serializes operations that modify the serving state of or number of
    # instances.
    self._instances_change_lock = threading.RLock()

    self._change_watcher_thread = threading.Thread(
        target=self._loop_watching_for_changes)

  def start(self):
    """Start background management of the Server."""
    self._balanced_server.start()
    self._watcher.start()
    self._change_watcher_thread.start()
    with self._instances_change_lock:
      for _ in xrange(self._initial_num_instances):
        self._add_instance()

  def quit(self):
    """Stops the Server."""
    self._quit_event.set()
    self._change_watcher_thread.join()
    # The instance adjustment thread depends on the balanced server and the
    # watcher so wait for it exit before quitting them.
    self._watcher.quit()
    self._balanced_server.quit()
    for wsgi_servr in self._wsgi_servers:
      wsgi_servr.quit()
    for inst in self._instances:
      inst.quit(force=True)
    with self._condition:
      self._condition.notify_all()

  def get_instance_port(self, instance_id):
    """Returns the port of the HTTP server for an instance."""
    try:
      instance_id = int(instance_id)
    except ValueError:
      raise request_info.InvalidInstanceIdError()
    with self._condition:
      if len(self._instances) > instance_id:
        wsgi_servr = self._wsgi_servers[instance_id]
      else:
        raise request_info.InvalidInstanceIdError()
    return wsgi_servr.port

  @property
  def instances(self):
    """A set of all the instances currently in the Server."""
    with self._condition:
      return set(self._instances)

  def _handle_instance_request(self,
                               environ,
                               start_response,
                               url_map,
                               match,
                               request_id,
                               inst,
                               request_type):
    """Handles a request routed a particular Instance.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler that matched.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      inst: The instance.Instance to send the request to.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    start_time = time.time()
    timeout_time = start_time + self._MAX_REQUEST_WAIT_TIME
    try:
      while time.time() < timeout_time:
        logging.debug('Dispatching request to %s after %0.4fs pending',
                      inst, time.time() - start_time)
        try:
          return inst.handle(environ, start_response, url_map, match,
                             request_id, request_type)
        except instance.CannotAcceptRequests:
          pass
        inst.wait(timeout_time)
        if inst.has_quit:
          return self._error_response(environ, start_response, 503)
      else:
        return self._error_response(environ, start_response, 503)
    finally:
      with self._condition:
        self._condition.notify()

  def _handle_script_request(self,
                             environ,
                             start_response,
                             url_map,
                             match,
                             request_id,
                             inst=None,
                             request_type=instance.NORMAL_REQUEST):
    """Handles a HTTP request that has matched a script handler.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler that matched.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      inst: The instance.Instance to send the request to. If None then an
          appropriate instance.Instance will be chosen.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    if ((request_type in (instance.NORMAL_REQUEST, instance.READY_REQUEST) and
         self._suspended) or self._quit_event.is_set()):
      return self._error_response(environ, start_response, 404)
    if self._server_configuration.is_backend:
      environ['BACKEND_ID'] = self._server_configuration.server_name
    else:
      environ['BACKEND_ID'] = (
          self._server_configuration.version_id.split('.', 1)[0])
    if inst is not None:
      return self._handle_instance_request(
          environ, start_response, url_map, match, request_id, inst,
          request_type)

    start_time = time.time()
    timeout_time = start_time + self._MAX_REQUEST_WAIT_TIME
    while time.time() < timeout_time:
      if ((request_type in (instance.NORMAL_REQUEST, instance.READY_REQUEST) and
           self._suspended) or self._quit_event.is_set()):
        return self._error_response(environ, start_response, 404)
      inst = self._choose_instance(timeout_time)
      if inst:
        try:
          logging.debug('Dispatching request to %s after %0.4fs pending',
                        inst, time.time() - start_time)
          return inst.handle(environ, start_response, url_map, match,
                             request_id, request_type)
        except instance.CannotAcceptRequests:
          continue
        finally:
          with self._condition:
            self._condition.notify()
    else:
      return self._error_response(environ, start_response, 503)

  def _add_instance(self):
    """Creates and adds a new instance.Instance to the Server.

    This must be called with _instances_change_lock held.

    Returns:
      The newly created instance.Instance.
    """
    instance_id = self.get_num_instances()
    inst = self._instance_factory.new_instance(instance_id,
                                               expect_ready_request=True)
    wsgi_servr = wsgi_server.WsgiServer(
        (self._host, 0), functools.partial(self._handle_request, inst=inst))
    wsgi_servr.start()
    with self._condition:
      self._wsgi_servers.append(wsgi_servr)
      self._instances.append(inst)
      suspended = self._suspended
    if not suspended:
      self._async_start_instance(wsgi_servr, inst)

  def _async_start_instance(self, wsgi_servr, inst):
    _THREAD_POOL.submit(self._start_instance, wsgi_servr, inst)

  def _start_instance(self, wsgi_servr, inst):
    if inst.start():
      logging.debug('Started instance: %s at http://%s:%s', inst, self.host,
                    wsgi_servr.port)
      try:
        environ = self.build_request_environ(
            'GET', '/_ah/start', [], '', '0.1.0.3', wsgi_servr.port,
            fake_login=True)
        self._handle_request(environ,
                             start_response_utils.null_start_response,
                             inst=inst,
                             request_type=instance.READY_REQUEST)
        logging.debug('Sent start request: %s', inst)
        with self._condition:
          self._condition.notify(self.max_instance_concurrent_requests)
      except:
        logging.exception('Internal error while handling start request.')

  def _choose_instance(self, timeout_time):
    """Returns an Instance to handle a request or None if all are busy."""
    with self._condition:
      while time.time() < timeout_time:
        for inst in self._instances:
          if inst.can_accept_requests:
            return inst
        self._condition.wait(timeout_time - time.time())
      return None

  def _handle_changes(self):
    """Handle file or configuration changes."""
    # Always check for config and file changes because checking also clears
    # pending changes.
    config_changes = self._server_configuration.check_for_updates()
    has_file_changes = self._watcher.has_changes()

    if application_configuration.HANDLERS_CHANGED in config_changes:
      handlers = self._create_url_handlers()
      with self._handler_lock:
        self._handlers = handlers
    if config_changes & _RESTART_INSTANCES_CONFIG_CHANGES or has_file_changes:
      with self._instances_change_lock:
        if not self._suspended:
          self.restart()

  def _loop_watching_for_changes(self):
    """Loops until the InstancePool is done watching for file changes."""
    while not self._quit_event.is_set():
      if self.ready:
        self._handle_changes()
      self._quit_event.wait(timeout=1)

  def get_num_instances(self):
    with self._instances_change_lock:
      with self._condition:
        return len(self._instances)

  def set_num_instances(self, instances):
    with self._instances_change_lock:
      with self._condition:
        running_instances = self.get_num_instances()
        if running_instances > instances:
          wsgi_servers_to_quit = self._wsgi_servers[instances:]
          del self._wsgi_servers[instances:]
          instances_to_quit = self._instances[instances:]
          del self._instances[instances:]
      if running_instances < instances:
        for _ in xrange(instances - running_instances):
          self._add_instance()
    if running_instances > instances:
      for inst, wsgi_servr in zip(instances_to_quit, wsgi_servers_to_quit):
        self._async_quit_instance(inst, wsgi_servr)

  def _async_quit_instance(self, inst, wsgi_servr):
    _THREAD_POOL.submit(self._quit_instance, inst, wsgi_servr)

  def _quit_instance(self, inst, wsgi_servr):
    port = wsgi_servr.port
    wsgi_servr.quit()
    inst.quit(expect_shutdown=True)
    self._shutdown_instance(inst, port)

  def suspend(self):
    """Suspends serving for this server, quitting all running instances."""
    with self._instances_change_lock:
      if self._suspended:
        raise request_info.ServerAlreadyStoppedError()
      self._suspended = True
      with self._condition:
        instances_to_stop = zip(self._instances, self._wsgi_servers)
        for wsgi_servr in self._wsgi_servers:
          wsgi_servr.set_error(404)
    for inst, wsgi_servr in instances_to_stop:
      self._async_suspend_instance(inst, wsgi_servr.port)

  def _async_suspend_instance(self, inst, port):
    _THREAD_POOL.submit(self._suspend_instance, inst, port)

  def _suspend_instance(self, inst, port):
    inst.quit(expect_shutdown=True)
    self._shutdown_instance(inst, port)

  def resume(self):
    """Resumes serving for this server."""
    with self._instances_change_lock:
      if not self._suspended:
        raise request_info.ServerAlreadyStartedError()
      self._suspended = False
      with self._condition:
        wsgi_servers = self._wsgi_servers
      instances_to_start = []
      for instance_id, wsgi_servr in enumerate(wsgi_servers):
        inst = self._instance_factory.new_instance(instance_id,
                                                   expect_ready_request=True)
        wsgi_servr.set_app(functools.partial(self._handle_request, inst=inst))
        with self._condition:
          self._instances[instance_id] = inst

        instances_to_start.append((wsgi_servr, inst))
    for wsgi_servr, inst in instances_to_start:
      self._async_start_instance(wsgi_servr, inst)

  def restart(self):
    """Restarts the the server, replacing all running instances."""
    with self._instances_change_lock:
      with self._condition:
        instances_to_stop = self._instances[:]
        wsgi_servers = self._wsgi_servers[:]
      instances_to_start = []
      for instance_id, wsgi_servr in enumerate(wsgi_servers):
        inst = self._instance_factory.new_instance(instance_id,
                                                   expect_ready_request=True)
        wsgi_servr.set_app(functools.partial(self._handle_request, inst=inst))
        instances_to_start.append(inst)
      with self._condition:
        self._instances[:] = instances_to_start
    for inst, wsgi_servr in zip(instances_to_stop, wsgi_servers):
      self._async_suspend_instance(inst, wsgi_servr.port)
    for wsgi_servr, inst in zip(wsgi_servers, instances_to_start):
      self._async_start_instance(wsgi_servr, inst)

  def get_instance(self, instance_id):
    """Returns the instance with the provided instance ID."""
    try:
      with self._condition:
        return self._instances[int(instance_id)]
    except (ValueError, IndexError):
      raise request_info.InvalidInstanceIdError()

  def __call__(self, environ, start_response, inst=None):
    return self._handle_request(environ, start_response, inst)

  @property
  def supports_individually_addressable_instances(self):
    return True


class BasicScalingServer(Server):
  """A pool of instances that is basic-scaled."""

  _DEFAULT_BASIC_SCALING = appinfo.BasicScaling(max_instances='1',
                                                idle_timeout='15m')
  _MAX_REQUEST_WAIT_TIME = 10

  @staticmethod
  def _parse_idle_timeout(timing):
    """Parse a idle timeout string into an int of the value in seconds.

    Args:
      timing: A str of the form 1m or 10s.

    Returns:
      An int representation of the value in seconds.
    """
    if timing.endswith('m'):
      return int(timing[:-1]) * 60
    else:
      return int(timing[:-1])

  @classmethod
  def _populate_default_basic_scaling(cls, basic_scaling):
    for attribute in basic_scaling.ATTRIBUTES:
      if getattr(basic_scaling, attribute) in ('basic', None):
        setattr(basic_scaling, attribute,
                getattr(cls._DEFAULT_BASIC_SCALING, attribute))

  def _process_basic_scaling(self, basic_scaling):
    if basic_scaling:
      self._populate_default_basic_scaling(basic_scaling)
    else:
      basic_scaling = self._DEFAULT_BASIC_SCALING
    self._max_instances = int(basic_scaling.max_instances)
    self._instance_idle_timeout = self._parse_idle_timeout(
        basic_scaling.idle_timeout)

  def __init__(self,
               server_configuration,
               host,
               balanced_port,
               api_port,

               cloud_sql_config,
               request_data):
    """Initializer for BasicScalingServer.

    Args:
      server_configuration: An application_configuration.ServerConfiguration
          instance storing the configuration data for a server.
      host: A string containing the host that any HTTP servers should bind to
          e.g. "localhost".
      balanced_port: An int specifying the port where the balanced server for
          the pool should listen.
      api_port: The port that APIServer listens for RPC requests on.

      cloud_sql_config: A runtime_config_pb2.CloudSQL instance containing the
          required configuration for local Google Cloud SQL development. If None
          then Cloud SQL will not be available.
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
    """
    super(BasicScalingServer, self).__init__(server_configuration,
                                             host,
                                             balanced_port,
                                             api_port,

                                             cloud_sql_config,
                                             request_data)

    self._process_basic_scaling(server_configuration.basic_scaling)

    self._instances = []  # Protected by self._condition.
    self._wsgi_servers = []  # Protected by self._condition.
    # A list of booleans signifying whether the corresponding instance in
    # self._instances has been or is being started.
    self._instance_running = []  # Protected by self._condition.

    for instance_id in xrange(self._max_instances):
      inst = self._instance_factory.new_instance(instance_id,
                                                 expect_ready_request=True)
      self._instances.append(inst)
      self._wsgi_servers.append(wsgi_server.WsgiServer(
          (self._host, 0), functools.partial(self._handle_request, inst=inst)))
      self._instance_running.append(False)

    self._condition = threading.Condition()  # Protects instance state.

    self._change_watcher_thread = threading.Thread(
        target=self._loop_watching_for_changes_and_idle_instances)

  def start(self):
    """Start background management of the Server."""
    self._balanced_server.start()
    self._watcher.start()
    self._change_watcher_thread.start()
    for wsgi_servr in self._wsgi_servers:
      wsgi_servr.start()

  def quit(self):
    """Stops the Server."""
    self._quit_event.set()
    self._change_watcher_thread.join()
    # The instance adjustment thread depends on the balanced server and the
    # watcher so wait for it exit before quitting them.
    self._watcher.quit()
    self._balanced_server.quit()
    for wsgi_servr in self._wsgi_servers:
      wsgi_servr.quit()
    for inst in self._instances:
      inst.quit(force=True)
    with self._condition:
      self._condition.notify_all()

  def get_instance_port(self, instance_id):
    """Returns the port of the HTTP server for an instance."""
    try:
      instance_id = int(instance_id)
    except ValueError:
      raise request_info.InvalidInstanceIdError()
    with self._condition:
      if len(self._wsgi_servers) > instance_id:
        wsgi_servr = self._wsgi_servers[instance_id]
      else:
        raise request_info.InvalidInstanceIdError()
    return wsgi_servr.port

  @property
  def instances(self):
    """A set of all the instances currently in the Server."""
    with self._condition:
      return set(self._instances)

  def _handle_instance_request(self,
                               environ,
                               start_response,
                               url_map,
                               match,
                               request_id,
                               inst,
                               request_type):
    """Handles a request routed a particular Instance.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler that matched.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      inst: The instance.Instance to send the request to.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    instance_id = inst.instance_id
    start_time = time.time()
    timeout_time = start_time + self._MAX_REQUEST_WAIT_TIME
    try:
      while time.time() < timeout_time:
        logging.debug('Dispatching request to %s after %0.4fs pending',
                      inst, time.time() - start_time)
        try:
          return inst.handle(environ, start_response, url_map, match,
                             request_id, request_type)
        except instance.CannotAcceptRequests:
          pass
        if inst.has_quit:
          return self._error_response(environ, start_response, 503)
        with self._condition:
          if self._instance_running[instance_id]:
            should_start = False
          else:
            self._instance_running[instance_id] = True
            should_start = True
        if should_start:
          self._start_instance(instance_id)
        else:
          inst.wait(timeout_time)
      else:
        return self._error_response(environ, start_response, 503)
    finally:
      with self._condition:
        self._condition.notify()

  def _handle_script_request(self,
                             environ,
                             start_response,
                             url_map,
                             match,
                             request_id,
                             inst=None,
                             request_type=instance.NORMAL_REQUEST):
    """Handles a HTTP request that has matched a script handler.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler that matched.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      inst: The instance.Instance to send the request to. If None then an
          appropriate instance.Instance will be chosen.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    if self._quit_event.is_set():
      return self._error_response(environ, start_response, 404)
    if self._server_configuration.is_backend:
      environ['BACKEND_ID'] = self._server_configuration.server_name
    else:
      environ['BACKEND_ID'] = (
          self._server_configuration.version_id.split('.', 1)[0])
    if inst is not None:
      return self._handle_instance_request(
          environ, start_response, url_map, match, request_id, inst,
          request_type)

    start_time = time.time()
    timeout_time = start_time + self._MAX_REQUEST_WAIT_TIME
    while time.time() < timeout_time:
      if self._quit_event.is_set():
        return self._error_response(environ, start_response, 404)
      inst = self._choose_instance(timeout_time)
      if inst:
        try:
          logging.debug('Dispatching request to %s after %0.4fs pending',
                        inst, time.time() - start_time)
          return inst.handle(environ, start_response, url_map, match,
                             request_id, request_type)
        except instance.CannotAcceptRequests:
          continue
        finally:
          with self._condition:
            self._condition.notify()
    else:
      return self._error_response(environ, start_response, 503)

  def _start_any_instance(self):
    """Choose an inactive instance and start it asynchronously.

    Returns:
      An instance.Instance that will be started asynchronously or None if all
      instances are already running.
    """
    with self._condition:
      for instance_id, running in enumerate(self._instance_running):
        if not running:
          self._instance_running[instance_id] = True
          inst = self._instances[instance_id]
          break
      else:
        return None
    self._async_start_instance(instance_id)
    return inst

  def _async_start_instance(self, instance_id):
    _THREAD_POOL.submit(self._start_instance, instance_id)

  def _start_instance(self, instance_id):
    with self._condition:
      wsgi_servr = self._wsgi_servers[instance_id]
      inst = self._instances[instance_id]
    if inst.start():
      logging.debug('Started instance: %s at http://%s:%s', inst, self.host,
                    wsgi_servr.port)
      try:
        environ = self.build_request_environ(
            'GET', '/_ah/start', [], '', '0.1.0.3', wsgi_servr.port,
            fake_login=True)
        self._handle_request(environ,
                             start_response_utils.null_start_response,
                             inst=inst,
                             request_type=instance.READY_REQUEST)
        logging.debug('Sent start request: %s', inst)
        with self._condition:
          self._condition.notify(self.max_instance_concurrent_requests)
      except:
        logging.exception('Internal error while handling start request.')

  def _choose_instance(self, timeout_time):
    """Returns an Instance to handle a request or None if all are busy."""
    with self._condition:
      while time.time() < timeout_time:
        for inst in self._instances:
          if inst.can_accept_requests:
            return inst
        else:
          inst = self._start_any_instance()
          if inst:
            break
          self._condition.wait(timeout_time - time.time())
    if inst:
      inst.wait(timeout_time)
    return inst

  def _handle_changes(self):
    """Handle file or configuration changes."""
    # Always check for config and file changes because checking also clears
    # pending changes.
    config_changes = self._server_configuration.check_for_updates()
    has_file_changes = self._watcher.has_changes()

    if application_configuration.HANDLERS_CHANGED in config_changes:
      handlers = self._create_url_handlers()
      with self._handler_lock:
        self._handlers = handlers
    if config_changes & _RESTART_INSTANCES_CONFIG_CHANGES or has_file_changes:
      self.restart()

  def _loop_watching_for_changes_and_idle_instances(self):
    """Loops until the InstancePool is done watching for file changes."""
    while not self._quit_event.is_set():
      if self.ready:
        self._shutdown_idle_instances()
        self._handle_changes()
      self._quit_event.wait(timeout=1)

  def _shutdown_idle_instances(self):
    instances_to_stop = []
    with self._condition:
      for instance_id, inst in enumerate(self._instances):
        if (self._instance_running[instance_id] and
            inst.idle_seconds > self._instance_idle_timeout):
          instances_to_stop.append((self._instances[instance_id],
                                    self._wsgi_servers[instance_id]))
          self._instance_running[instance_id] = False
          new_instance = self._instance_factory.new_instance(
              instance_id, expect_ready_request=True)
          self._instances[instance_id] = new_instance
          self._wsgi_servers[instance_id].set_app(
              functools.partial(self._handle_request, inst=new_instance))
    for inst, wsgi_servr in instances_to_stop:
      logging.debug('Shutting down %r', inst)
      self._stop_instance(inst, wsgi_servr)

  def _stop_instance(self, inst, wsgi_servr):
    inst.quit(expect_shutdown=True)
    self._async_shutdown_instance(inst, wsgi_servr.port)

  def restart(self):
    """Restarts the the server, replacing all running instances."""
    instances_to_stop = []
    instances_to_start = []
    with self._condition:
      for instance_id, inst in enumerate(self._instances):
        if self._instance_running[instance_id]:
          instances_to_stop.append((inst, self._wsgi_servers[instance_id]))
          new_instance = self._instance_factory.new_instance(
              instance_id, expect_ready_request=True)
          self._instances[instance_id] = new_instance
          instances_to_start.append(instance_id)
          self._wsgi_servers[instance_id].set_app(
              functools.partial(self._handle_request, inst=new_instance))
    for instance_id in instances_to_start:
      self._async_start_instance(instance_id)
    for inst, wsgi_servr in instances_to_stop:
      self._stop_instance(inst, wsgi_servr)

  def get_instance(self, instance_id):
    """Returns the instance with the provided instance ID."""
    try:
      with self._condition:
        return self._instances[int(instance_id)]
    except (ValueError, IndexError):
      raise request_info.InvalidInstanceIdError()

  def __call__(self, environ, start_response, inst=None):
    return self._handle_request(environ, start_response, inst)

  @property
  def supports_individually_addressable_instances(self):
    return True


class InteractiveCommandServer(Server):
  """A Server that can evaluate user commands.

  This server manages a single Instance which is started lazily.
  """

  _MAX_REQUEST_WAIT_TIME = 15

  def __init__(self,
               server_configuration,
               host,
               balanced_port,
               api_port,

               cloud_sql_config,
               request_data):
    """Initializer for InteractiveCommandServer.

    Args:
      server_configuration: An application_configuration.ServerConfiguration
          instance storing the configuration data for this server.
      host: A string containing the host that will be used when constructing
          HTTP headers sent to the Instance executing the interactive command
          e.g. "localhost".
      balanced_port: An int specifying the port that will be used when
          constructing HTTP headers sent to the Instance executing the
          interactive command e.g. "localhost".
      api_port: The port that APIServer listens for RPC requests on.

      cloud_sql_config: A runtime_config_pb2.CloudSQL instance containing the
          required configuration for local Google Cloud SQL development. If None
          then Cloud SQL will not be available.
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
    """
    super(InteractiveCommandServer, self).__init__(server_configuration,
                                                   host,
                                                   balanced_port,
                                                   api_port,

                                                   cloud_sql_config,
                                                   request_data)
    # Use a single instance so that state is consistent across requests.
    self._inst_lock = threading.Lock()
    self._inst = None

  @property
  def balanced_port(self):
    """The port that the balanced HTTP server for the Server is listening on.

    The InteractiveCommandServer does not actually listen on this port but it is
    used when constructing the "SERVER_PORT" in the WSGI-environment.
    """
    return self._balanced_port

  def quit(self):
    """Stops the InteractiveCommandServer."""
    if self._inst:
      self._inst.quit(force=True)
      self._inst = None

  def _handle_script_request(self,
                             environ,
                             start_response,
                             url_map,
                             match,
                             request_id,
                             inst=None,
                             request_type=instance.INTERACTIVE_REQUEST):
    """Handles a interactive request by forwarding it to the managed Instance.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler that matched.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      inst: The instance.Instance to send the request to.
      request_type: The type of the request. See instance.*_REQUEST module
          constants. This must be instance.INTERACTIVE_REQUEST.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    assert inst is None
    assert request_type == instance.INTERACTIVE_REQUEST

    start_time = time.time()
    timeout_time = start_time + self._MAX_REQUEST_WAIT_TIME

    while time.time() < timeout_time:
      new_instance = False
      with self._inst_lock:
        if not self._inst:
          self._inst = self._instance_factory.new_instance(
              AutoScalingServer.generate_instance_id(),
              expect_ready_request=False)
          new_instance = True
        inst = self._inst

      if new_instance:
        self._inst.start()

      try:
        return inst.handle(environ, start_response, url_map, match,
                           request_id, request_type)
      except instance.CannotAcceptRequests:
        inst.wait(timeout_time)
      except Exception:
        # If the instance is restarted while handling a request then the
        # exception raises is unpredictable.
        if inst != self._inst:
          start_response('503 Service Unavailable', [])
          return ['Instance was restarted while executing command']
        logging.exception('Unexpected exception handling command: %r', environ)
        raise
    else:
      start_response('503 Service Unavailable', [])
      return ['The command timed-out while waiting for another one to complete']

  def restart(self):
    """Restarts the the server."""
    with self._inst_lock:
      if self._inst:
        self._inst.quit(force=True)
        self._inst = None

  def send_interactive_command(self, command):
    """Sends an interactive command to the server.

    Args:
      command: The command to send e.g. "print 5+5".

    Returns:
      A string representing the result of the command e.g. "10\n".

    Raises:
      InteractiveCommandError: if the command failed for any reason.
    """
    start_response = start_response_utils.CapturingStartResponse()

    # 192.0.2.0 is an example address defined in RFC 5737.
    environ = self.build_request_environ(
        'POST', '/', [], command, '192.0.2.0', self.balanced_port)

    try:
      response = self._handle_request(
          environ,
          start_response,
          request_type=instance.INTERACTIVE_REQUEST)
    except Exception as e:
      raise InteractiveCommandError('Unexpected command failure: ', str(e))

    if start_response.status != '200 OK':
      raise InteractiveCommandError(start_response.merged_response(response))

    return start_response.merged_response(response)
