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
"""Tests for google.appengine.tools.devappserver2.python.runtime."""


import cStringIO
import json
import logging
import sys
import unittest

import google
import mox

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api.logservice import log_service_pb
from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.tools.devappserver2 import http_runtime_constants
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2.python import runtime
from google.appengine.tools.devappserver2.python import sandbox


class PythonRuntimeTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(apiproxy_stub_map, 'MakeSyncCall')
    self.sys_stderr = sys.stderr
    sandbox._init_logging()
    self.config = runtime_config_pb2.Config()
    self.config.application_root = (
        'apphosting/tools/devappserver2/python/testdata/wsgi_env')
    if sys.path[0] != self.config.application_root:
      sys.path.insert(0, self.config.application_root)
    self.config.app_id = 'app'
    self.config.version_id = '1'
    self.config.threadsafe = False
    self.config.environ.add(key='key', value='value')
    self.body = ''

  def tearDown(self):
    sys.stderr = self.sys_stderr
    logging.getLogger().handlers = []
    self.mox.UnsetStubs()

  def start_response(self, status, headers):
    self.status = status
    self.headers = headers
    return self.write

  def write(self, data):
    self.body += data

  def test_environ(self):
    self.runtime = runtime.PythonRuntime(self.config)
    environ = {
        'wsgi.input': cStringIO.StringIO(''),
        'CONTENT_LENGTH': '0',
        http_runtime_constants.SCRIPT_HEADER: 'echo.app',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_NAME'):
        'localhost',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_PORT'):
        '8080',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_PROTOCOL'):
        'HTTP/1.0',
        'SCRIPT_NAME': '',
        'SERVER_NAME': 'server',
        'SERVER_PORT': '12345',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'PATH_INFO': '/env',
        'QUERY_STRING': 'foo=bar',
        http_runtime_constants.REQUEST_ID_ENVIRON: 'abc123',
        'HTTP_A_HEADER': 'value',
        '%s%s' % (http_runtime_constants.INTERNAL_ENVIRON_PREFIX,
                  'HIDDEN_HEADER'):
        'hidden_value',
        }
    expected_logs = log_service_pb.FlushRequest()
    expected_logs.set_logs('')
    apiproxy_stub_map.MakeSyncCall('logservice', 'Flush',
                                   expected_logs,
                                   api_base_pb.VoidProto())
    self.mox.ReplayAll()
    self.body += ''.join(self.runtime(environ, self.start_response))
    self.mox.VerifyAll()
    self.assertEqual('200 OK', self.status)
    env = json.loads(self.body)
    self.assertEqual('python27', env['APPENGINE_RUNTIME'])
    self.assertEqual('app', env['APPLICATION_ID'])
    self.assertEqual('1', env['CURRENT_VERSION_ID'])
    self.assertEqual('value', env['HTTP_A_HEADER'])
    self.assertEqual('localhost', env['SERVER_NAME'])
    self.assertEqual('8080', env['SERVER_PORT'])
    self.assertEqual('HTTP/1.0', env['SERVER_PROTOCOL'])
    self.assertFalse('%s%s' % (http_runtime_constants.INTERNAL_ENVIRON_PREFIX,
                               'HIDDEN_HEADER') in env)
    self.assertEqual('value', env['key'])

  def test_404(self):
    self.runtime = runtime.PythonRuntime(self.config)
    environ = {
        'wsgi.input': cStringIO.StringIO(''),
        'CONTENT_LENGTH': '0',
        http_runtime_constants.SCRIPT_HEADER: '404.py',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_NAME'):
        'localhost',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_PORT'):
        '8080',
        'PATH_INFO': '/env',
        'QUERY_STRING': 'foo=bar',
        http_runtime_constants.REQUEST_ID_ENVIRON: 'abc123',
        }
    expected_logs = log_service_pb.FlushRequest()
    expected_logs.set_logs('')
    apiproxy_stub_map.MakeSyncCall('logservice', 'Flush',
                                   expected_logs,
                                   api_base_pb.VoidProto())
    self.mox.ReplayAll()
    self.body += ''.join(self.runtime(environ, self.start_response))
    self.mox.VerifyAll()
    self.assertEqual('404 Not Found', self.status)
    self.assertFalse(self.body)

  def test_interactive_request(self):
    self.runtime = runtime.PythonRuntime(self.config)
    command = 'print 5+5'
    environ = {
        'wsgi.input': cStringIO.StringIO(command),
        'CONTENT_LENGTH': str(len(command)),
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_NAME'):
        'localhost',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_PORT'):
        '8080',
        'PATH_INFO': '/env',
        'QUERY_STRING': 'foo=bar',
        http_runtime_constants.REQUEST_ID_ENVIRON: 'abc123',
        http_runtime_constants.REQUEST_TYPE_HEADER: 'interactive',
        }
    expected_logs = log_service_pb.FlushRequest()
    expected_logs.set_logs('')
    apiproxy_stub_map.MakeSyncCall('logservice', 'Flush',
                                   expected_logs,
                                   api_base_pb.VoidProto())
    self.mox.ReplayAll()
    self.body += ''.join(self.runtime(environ, self.start_response))
    self.mox.VerifyAll()
    self.assertEqual('200 OK', self.status)
    self.assertEqual('10\n', self.body)

  def test_logging(self):
    self.config.application_root = (
        'apphosting/tools/devappserver2/python/testdata/logs')
    if sys.path[0] != self.config.application_root:
      sys.path.insert(0, self.config.application_root)
    self.runtime = runtime.PythonRuntime(self.config)
    environ = {
        'wsgi.input': cStringIO.StringIO(''),
        'CONTENT_LENGTH': '0',
        http_runtime_constants.SCRIPT_HEADER: 'writer.app',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_NAME'):
        'localhost',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_PORT'):
        '8080',
        http_runtime_constants.REQUEST_ID_ENVIRON: 'abc123',
        'PATH_INFO': '/write',
        'QUERY_STRING': '',
        }

    def check_logs(logs):
      logs_group = log_service_pb.UserAppLogGroup(logs.logs())
      self.assertEqual(0, logs_group.log_line(0).level())
      self.assertEqual('debug', logs_group.log_line(0).message())
      self.assertEqual(1, logs_group.log_line(1).level())
      self.assertEqual('info', logs_group.log_line(1).message())
      self.assertEqual(2, logs_group.log_line(2).level())
      self.assertEqual('warning', logs_group.log_line(2).message())
      self.assertEqual(3, logs_group.log_line(3).level())
      self.assertEqual('error', logs_group.log_line(3).message())
      self.assertEqual(3, logs_group.log_line(4).level())
      self.assertEqual('stderr', logs_group.log_line(4).message())
      return True
    apiproxy_stub_map.MakeSyncCall('logservice', 'Flush',
                                   mox.Func(check_logs),
                                   api_base_pb.VoidProto())
    self.mox.ReplayAll()
    self.runtime(environ, self.start_response)
    self.mox.VerifyAll()
    self.assertEqual('200 OK', self.status)

  def test_uncaught_exception(self):
    self.runtime = runtime.PythonRuntime(self.config)
    environ = {
        'wsgi.input': cStringIO.StringIO(''),
        'CONTENT_LENGTH': '0',
        http_runtime_constants.SCRIPT_HEADER: 'fake.module',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_NAME'):
        'localhost',
        '%s%s' % (
            http_runtime_constants.INTERNAL_ENVIRON_PREFIX, 'SERVER_PORT'):
        '8080',
        'PATH_INFO': '/env',
        'QUERY_STRING': 'foo=bar',
        http_runtime_constants.REQUEST_ID_ENVIRON: 'abc123',
        }
    apiproxy_stub_map.MakeSyncCall('logservice', 'Flush',
                                   mox.IgnoreArg(),
                                   api_base_pb.VoidProto())
    self.mox.ReplayAll()
    self.body += ''.join(self.runtime(environ, self.start_response))
    self.mox.VerifyAll()
    self.assertEqual('500 Internal Server Error', self.status)
    self.assertSequenceEqual(
        [(http_runtime_constants.ERROR_CODE_HEADER, '1')],
        self.headers)
    self.assertFalse(self.body)


class SetupStubsTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_setup_stubs(self):
    self.mox.StubOutWithMock(remote_api_stub, 'ConfigureRemoteApi')
    remote_api_stub.ConfigureRemoteApi('app', '/', mox.IgnoreArg(),
                                       'localhost:12345',
                                       use_remote_datastore=False)
    config = runtime_config_pb2.Config()
    config.app_id = 'app'
    config.api_port = 12345
    self.mox.ReplayAll()
    runtime.setup_stubs(config)
    self.mox.VerifyAll()

if __name__ == '__main__':
  unittest.main()
