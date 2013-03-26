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
import os
import sys
import time

import google

from google.appengine.api import rdbms_mysqldb
from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.tools.devappserver2 import request_rewriter
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import wsgi_server
from google.appengine.tools.devappserver2.python import sandbox


def setup_stubs(config):
  """Sets up API stubs using remote API."""
  remote_api_stub.ConfigureRemoteApi(config.app_id, '/', lambda: ('', ''),
                                     'localhost:%d' % config.api_port,
                                     use_remote_datastore=False)

  if config.HasField('cloud_sql_config'):
    # Connect the RDBMS API to MySQL.
    sys.modules['google.appengine.api.rdbms'] = rdbms_mysqldb
    google.appengine.api.rdbms = rdbms_mysqldb

    connect_kwargs = dict(host=config.cloud_sql_config.mysql_host,
                          port=config.cloud_sql_config.mysql_port,
                          user=config.cloud_sql_config.mysql_user,
                          passwd=config.cloud_sql_config.mysql_password)

    if config.cloud_sql_config.mysql_socket:
      connect_kwargs['unix_socket'] = config.cloud_sql_config.mysql_socket
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
      connect_kwargs['unix_socket'] = rdbms_mysqldb.FindUnixSocket()

    rdbms_mysqldb.SetConnectKwargs(**connect_kwargs)


def main():
  config = runtime_config_pb2.Config()
  config.ParseFromString(base64.b64decode(sys.stdin.read()))
  setup_stubs(config)
  sandbox.enable_sandbox(config)
  # This import needs to be after enabling the sandbox so the runtime
  # implementation imports the sandboxed version of the logging module.
  from google.appengine.tools.devappserver2.python import request_handler

  server = wsgi_server.WsgiServer(
      ('localhost', 0),
      request_rewriter.runtime_rewriter_middleware(
          request_handler.RequestHandler(config)))
  server.start()
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
