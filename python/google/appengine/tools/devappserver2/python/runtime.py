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
"""A Python devappserver2 runtime."""


import base64
import cStringIO
import httplib
import logging
import os
import sys
import time
import traceback
import urllib
import urlparse

import google

import google.appengine.api
from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import rdbms_mysqldb
from google.appengine.api.logservice import log_service_pb
from google.appengine.api.logservice import logservice
from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.runtime import background
from google.appengine.runtime import request_environment
from google.appengine.runtime import runtime
from google.appengine.runtime import shutdown
from google.appengine.tools.devappserver2 import http_runtime_constants
from google.appengine.tools.devappserver2 import request_rewriter
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import wsgi_server
from google.appengine.tools.devappserver2.python import request_state
from google.appengine.tools.devappserver2.python import sandbox


class PythonRuntime(object):
  """A WSGI application that forwards requests to a user-provided app."""

  _PYTHON_LIB_DIR = os.path.dirname(os.path.dirname(google.__file__))

  def __init__(self, config):
    logging.debug('Initializing runtime with %s', config)
    self.config = config
    self.environ_template = {
        'APPLICATION_ID': config.app_id,
        'CURRENT_VERSION_ID': config.version_id,
        'APPENGINE_RUNTIME': 'python27',
        'AUTH_DOMAIN': 'gmail.com',
        'HTTPS': 'off',
        'SCRIPT_NAME': '',
        'SERVER_SOFTWARE': http_runtime_constants.SERVER_SOFTWARE,
        'TZ': 'UTC',
        'wsgi.multithread': config.threadsafe,
        }
    self._command_globals = {}  # Use to evaluate interactive requests.
    self.environ_template.update((env.key, env.value) for env in config.environ)

  def __call__(self, environ, start_response):
    remote_api_stub.RemoteStub._SetRequestId(
        environ[http_runtime_constants.REQUEST_ID_ENVIRON])
    request_type = environ.pop(http_runtime_constants.REQUEST_TYPE_HEADER, None)
    request_state.start_request(
        environ[http_runtime_constants.REQUEST_ID_ENVIRON])
    try:
      if request_type == 'background':
        response = self.handle_background_request(environ)
      elif request_type == 'shutdown':
        response = self.handle_shutdown_request(environ)
      elif request_type == 'interactive':
        response = self.handle_interactive_request(environ)
      else:
        response = self.handle_normal_request(environ)
    finally:
      request_state.end_request(
          environ[http_runtime_constants.REQUEST_ID_ENVIRON])
    error = response.get('error', 0)
    self._flush_logs(response.get('logs', []))
    if error == 0:
      response_code = response['response_code']
      status = '%d %s' % (response_code, httplib.responses.get(
          response_code, 'Unknown Status Code'))
      start_response(status, response['headers'])
      return [response.get('body', '')]
    elif error == 2:
      start_response('404 Not Found', [])
      return []
    else:
      start_response('500 Internal Server Error',
                     [(http_runtime_constants.ERROR_CODE_HEADER, str(error))])
      return []

  def handle_normal_request(self, environ):
    user_environ = self.get_user_environ(environ)
    script = environ.pop(http_runtime_constants.SCRIPT_HEADER)
    body = environ['wsgi.input'].read(int(environ.get('CONTENT_LENGTH', 0)))
    url = 'http://%s:%s%s?%s' % (user_environ['SERVER_NAME'],
                                 user_environ['SERVER_PORT'],
                                 urllib.quote(environ['PATH_INFO']),
                                 environ['QUERY_STRING'])
    return runtime.HandleRequest(user_environ, script, url, body,
                                 self.config.application_root,
                                 self._PYTHON_LIB_DIR)

  def handle_background_request(self, environ):
    return background.Handle(self.get_user_environ(environ))

  def handle_shutdown_request(self, environ):
    response, exc = shutdown.Handle(self.get_user_environ(environ))
    if exc:
      for request in request_state.get_request_states():
        if (request.request_id !=
            environ[http_runtime_constants.REQUEST_ID_ENVIRON]):
          request.inject_exception(exc[1])
    return response

  def handle_interactive_request(self, environ):
    code = environ['wsgi.input'].read().replace('\r\n', '\n')

    user_environ = self.get_user_environ(environ)
    if 'HTTP_CONTENT_LENGTH' in user_environ:
      del user_environ['HTTP_CONTENT_LENGTH']
    user_environ['REQUEST_METHOD'] = 'GET'
    url = 'http://%s:%s%s?%s' % (user_environ['SERVER_NAME'],
                                 user_environ['SERVER_PORT'],
                                 urllib.quote(environ['PATH_INFO']),
                                 environ['QUERY_STRING'])

    results_io = cStringIO.StringIO()
    old_sys_stdout = sys.stdout

    try:
      error = logservice.LogsBuffer()
      request_environment.current_request.Init(error, user_environ)
      url = urlparse.urlsplit(url)
      environ.update(runtime.CgiDictFromParsedUrl(url))
      sys.stdout = results_io
      try:
        compiled_code = compile(code, '<string>', 'exec')
        exec(compiled_code, self._command_globals)
      except:
        traceback.print_exc(file=results_io)

      return {'error': 0,
              'response_code': 200,
              'headers': [('Content-Type', 'text/plain')],
              'body': results_io.getvalue(),
              'logs': error.parse_logs()}
    finally:
      request_environment.current_request.Clear()
      sys.stdout = old_sys_stdout

  def get_user_environ(self, environ):
    """Returns a dict containing the environ to pass to the user's application.

    Args:
      environ: A dict containing the request WSGI environ.

    Returns:
      A dict containing the environ representing an HTTP request.
    """
    user_environ = self.environ_template.copy()
    self.copy_headers(environ, user_environ)
    user_environ['REQUEST_METHOD'] = environ.get('REQUEST_METHOD', 'GET')
    content_type = environ.get('CONTENT_TYPE')
    if content_type:
      user_environ['HTTP_CONTENT_TYPE'] = content_type
    content_length = environ.get('CONTENT_LENGTH')
    if content_length:
      user_environ['HTTP_CONTENT_LENGTH'] = content_length
    return user_environ

  def copy_headers(self, source_environ, dest_environ):
    """Copy headers from source_environ to dest_environ.

    This extracts headers that represent environ values and propagates all
    other headers which are not used for internal implementation details or
    headers that are stripped.

    Args:
      source_environ: The source environ dict.
      dest_environ: The environ dict to populate.
    """
    for env in http_runtime_constants.ENVIRONS_TO_PROPAGATE:
      value = source_environ.get(
          http_runtime_constants.INTERNAL_ENVIRON_PREFIX + env, None)
      if value is not None:
        dest_environ[env] = value
    for name, value in source_environ.items():
      if (name.startswith('HTTP_') and
          not name.startswith(http_runtime_constants.INTERNAL_ENVIRON_PREFIX)):
        dest_environ[name] = value

  def _flush_logs(self, logs):
    """Flushes logs using the LogService API.

    Args:
      logs: A list of tuples (timestamp_usec, level, message).
    """
    logs_group = log_service_pb.UserAppLogGroup()
    for timestamp_usec, level, message in logs:
      log_line = logs_group.add_log_line()
      log_line.set_timestamp_usec(timestamp_usec)
      log_line.set_level(level)
      log_line.set_message(message)
    request = log_service_pb.FlushRequest()
    request.set_logs(logs_group.Encode())
    response = api_base_pb.VoidProto()
    apiproxy_stub_map.MakeSyncCall('logservice', 'Flush', request, response)


def setup_stubs(config):
  """Sets up API stubs using remote API."""
  remote_api_stub.ConfigureRemoteApi(config.app_id, '/', lambda: ('', ''),
                                     'localhost:%d' % config.api_port,
                                     use_remote_datastore=False)

  if config.HasField('cloud_sql_config'):
    # Connect the RDBMS API to MySQL.
    sys.modules['google.appengine.api.rdbms'] = rdbms_mysqldb
    google.appengine.api.rdbms = rdbms_mysqldb

    if config.cloud_sql_config.mysql_socket:
      unix_socket = config.cloud_sql_config.mysql_socket
    elif (os.name == 'posix' and
          config.cloud_sql_config.mysql_host == 'localhost'):
      # From http://dev.mysql.com/doc/refman/5.0/en/connecting.html:
      # "On Unix, MySQL programs treat the host name localhost specially,
      # in a way that is likely different from what you expect compared to
      # other network-based programs. For connections to localhost, MySQL
      # programs attempt to connect to the local server by using a Unix socket
      # file. This occurs even if a --port or -P option is given to specify a
      # port number."
      #
      # This logic is duplicated in rdbms_mysqldb.connect but FindUnixSocket
      # will not worked in devappserver2 when rdbms_mysqldb.connect is called
      # because os.access is replaced in the sandboxed environment.
      #
      # A warning is not logged if FindUnixSocket returns None because it would
      # appear for all users, not just those who call connect.
      unix_socket = rdbms_mysqldb.FindUnixSocket()
    else:
      unix_socket = None

    rdbms_mysqldb.SetConnectKwargs(
        host=config.cloud_sql_config.mysql_host,
        port=config.cloud_sql_config.mysql_port,
        user=config.cloud_sql_config.mysql_user,
        passwd=config.cloud_sql_config.mysql_password,
        unix_socket=unix_socket)


def main():
  config = runtime_config_pb2.Config()
  config.ParseFromString(base64.b64decode(sys.stdin.read()))
  setup_stubs(config)
  server = wsgi_server.WsgiServer(
      ('localhost', 0),
      request_rewriter.runtime_rewriter_middleware(PythonRuntime(config)))
  server.start()
  sandbox.enable_sandbox(config)
  print server.port
  sys.stdout.close()
  sys.stdout = sys.stderr
  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    pass
  finally:
    server.quit()


if __name__ == '__main__':
  main()
