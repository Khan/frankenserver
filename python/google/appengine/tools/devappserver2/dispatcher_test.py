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
"""Tests for google.appengine.tools.devappserver2.dispatcher."""

import logging
import unittest

import google

import mox

from google.appengine.api import appinfo
from google.appengine.api import request_info
from google.appengine.tools.devappserver2 import api_server
from google.appengine.tools.devappserver2 import constants
from google.appengine.tools.devappserver2 import dispatcher
from google.appengine.tools.devappserver2 import scheduled_executor
from google.appengine.tools.devappserver2 import server


class ApplicationConfigurationStub(object):
  def __init__(self, servers):
    self.servers = servers


class ServerConfigurationStub(object):
  def __init__(self, application, server_name, version, manual_scaling):
    self.application_root = '/'
    self.application = application
    self.server_name = server_name
    self.major_version = version
    self.version_id = '%s:%s.%s' % (server_name, version, '12345')
    self.runtime = 'python27'
    self.threadsafe = False
    self.handlers = []
    self.skip_files = []
    self.normalized_libraries = []
    self.env_variables = []
    if manual_scaling:
      self.automatic_scaling = appinfo.AutomaticScaling()
      self.manual_scaling = None
    else:
      self.automatic_scaling = None
      self.manual_scaling = appinfo.ManualScaling(instances=1)
    self.inbound_services = None

  def add_change_callback(self, fn):
    pass


SERVER_CONFIGURATIONS = [
    ServerConfigurationStub(application='app',
                            server_name='default',
                            version='version',
                            manual_scaling=False),
    ServerConfigurationStub(application='app',
                            server_name='other',
                            version='version2',
                            manual_scaling=True),
    ]


class AutoScalingServerFacade(server.AutoScalingServer):
  def __init__(self,
               server_configuration,
               host='fakehost',
               balanced_port=0,
               api_port=8080,

               request_data=None,
               instance_factory=None):
    super(AutoScalingServerFacade, self).__init__(server_configuration,
                                                  host,
                                                  balanced_port,
                                                  api_port,

                                                  cloud_sql_config=None,
                                                  request_data=request_data)

  def start(self):
    pass

  def quit(self):
    pass

  @property
  def balanced_address(self):
    return '%s:%s' % (self._host, self._balanced_port)

  @property
  def balanced_port(self):
    return self._balanced_port


class ManualScalingServerFacade(server.ManualScalingServer):
  def __init__(self,
               server_configuration,
               host='fakehost',
               balanced_port=0,
               api_port=8080,

               request_data=None,
               instance_factory=None):
    super(ManualScalingServerFacade, self).__init__(server_configuration,
                                                    host,
                                                    balanced_port,
                                                    api_port,

                                                    cloud_sql_config=None,
                                                    request_data=request_data)

  def start(self):
    pass

  def quit(self):
    pass

  @property
  def balanced_address(self):
    return '%s:%s' % (self._host, self._balanced_port)

  @property
  def balanced_port(self):
    return self._balanced_port

  def get_instance_address(self, instance):
    if instance == 'invalid':
      raise request_info.InvalidInstanceIdError()
    return '%s:%s' % (self._host, int(instance) + 1000)


class DispatcherTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    api_server.test_setup_stubs()
    app_config = ApplicationConfigurationStub(SERVER_CONFIGURATIONS)
    self.dispatcher = dispatcher.Dispatcher(app_config,
                                            'localhost',
                                            1,

                                            cloud_sql_config=None)
    self.server1 = AutoScalingServerFacade(app_config.servers[0],
                                           balanced_port=1,
                                           host='localhost')
    self.server2 = ManualScalingServerFacade(app_config.servers[0],
                                             balanced_port=2,
                                             host='localhost')

    self.mox.StubOutWithMock(self.dispatcher, '_create_server')
    self.dispatcher._create_server(app_config.servers[0], 1).AndReturn(
        (self.server1, 2))
    self.dispatcher._create_server(app_config.servers[1], 2).AndReturn(
        (self.server2, 3))
    self.mox.ReplayAll()
    self.dispatcher.start(12345, object())
    self.mox.VerifyAll()
    self.mox.StubOutWithMock(server.Server, 'build_request_environ')

  def tearDown(self):
    self.dispatcher.quit()
    self.mox.UnsetStubs()

  def test_get_server_names(self):
    self.assertItemsEqual(['default', 'other'],
                          self.dispatcher.get_server_names())

  def test_get_hostname(self):
    self.assertEqual('localhost:1',
                     self.dispatcher.get_hostname('default', 'version'))
    self.assertEqual('localhost:2',
                     self.dispatcher.get_hostname('other', 'version2'))
    self.assertRaises(request_info.ServerDoesNotExistError,
                      self.dispatcher.get_hostname, 'fake', 'version')
    self.assertRaises(request_info.VersionDoesNotExistError,
                      self.dispatcher.get_hostname, 'default', 'fake')
    self.assertRaises(request_info.NotSupportedWithAutoScalingError,
                      self.dispatcher.get_hostname, 'default', 'version', '0')
    self.assertEqual('localhost:1000',
                     self.dispatcher.get_hostname('other', 'version2', '0'))
    self.assertRaises(request_info.InvalidInstanceIdError,
                      self.dispatcher.get_hostname, 'other', 'version2',
                      'invalid')

  def test_get_server_by_name(self):
    self.assertEqual(self.server1,
                     self.dispatcher.get_server_by_name('default'))
    self.assertEqual(self.server2,
                     self.dispatcher.get_server_by_name('other'))
    self.assertRaises(request_info.ServerDoesNotExistError,
                      self.dispatcher.get_server_by_name, 'fake')

  def test_get_versions(self):
    self.assertEqual(['version'], self.dispatcher.get_versions('default'))
    self.assertEqual(['version2'], self.dispatcher.get_versions('other'))
    self.assertRaises(request_info.ServerDoesNotExistError,
                      self.dispatcher.get_versions, 'fake')

  def test_get_default_version(self):
    self.assertEqual('version', self.dispatcher.get_default_version('default'))
    self.assertEqual('version2', self.dispatcher.get_default_version('other'))
    self.assertRaises(request_info.ServerDoesNotExistError,
                      self.dispatcher.get_default_version, 'fake')

  def test_add_event(self):
    self.mox.StubOutWithMock(scheduled_executor.ScheduledExecutor, 'add_event')
    runnable = object()
    scheduled_executor.ScheduledExecutor.add_event(runnable, 123, ('foo',
                                                                   'bar'))
    scheduled_executor.ScheduledExecutor.add_event(runnable, 124, None)
    self.mox.ReplayAll()
    self.dispatcher.add_event(runnable, 123, 'foo', 'bar')
    self.dispatcher.add_event(runnable, 124)
    self.mox.VerifyAll()

  def test_update_event(self):
    self.mox.StubOutWithMock(scheduled_executor.ScheduledExecutor,
                             'update_event')
    scheduled_executor.ScheduledExecutor.update_event(123, ('foo', 'bar'))
    self.mox.ReplayAll()
    self.dispatcher.update_event(123, 'foo', 'bar')
    self.mox.VerifyAll()

  def test_add_async_request(self):
    dummy_environ = object()
    self.mox.StubOutWithMock(dispatcher._THREAD_POOL, 'submit')
    self.dispatcher._server_name_to_server['default'].build_request_environ(
        'PUT', '/foo?bar=baz', [('Header', 'Value'), ('Other', 'Values')],
        'body', '1.2.3.4', 1).AndReturn(
            dummy_environ)
    dispatcher._THREAD_POOL.submit(
        self.dispatcher._handle_request, dummy_environ, mox.IgnoreArg(),
        self.dispatcher._server_name_to_server['default'],
        None, catch_and_log_exceptions=True)
    self.mox.ReplayAll()
    self.dispatcher.add_async_request(
        'PUT', '/foo?bar=baz', [('Header', 'Value'), ('Other', 'Values')],
        'body', '1.2.3.4')
    self.mox.VerifyAll()

  def test_add_async_request_specific_server(self):
    dummy_environ = object()
    self.mox.StubOutWithMock(dispatcher._THREAD_POOL, 'submit')
    self.dispatcher._server_name_to_server['other'].build_request_environ(
        'PUT', '/foo?bar=baz', [('Header', 'Value'), ('Other', 'Values')],
        'body', '1.2.3.4', 2).AndReturn(
            dummy_environ)
    dispatcher._THREAD_POOL.submit(
        self.dispatcher._handle_request, dummy_environ, mox.IgnoreArg(),
        self.dispatcher._server_name_to_server['other'],
        None, catch_and_log_exceptions=True)
    self.mox.ReplayAll()
    self.dispatcher.add_async_request(
        'PUT', '/foo?bar=baz', [('Header', 'Value'), ('Other', 'Values')],
        'body', '1.2.3.4', server_name='other')
    self.mox.VerifyAll()

  def test_add_request(self):
    dummy_environ = object()
    self.mox.StubOutWithMock(self.dispatcher, '_handle_request')
    self.dispatcher._server_name_to_server['default'].build_request_environ(
        'PUT', '/foo?bar=baz', [('Header', 'Value'), ('Other', 'Values')],
        'body', '1.2.3.4', 1).AndReturn(
            dummy_environ)
    self.dispatcher._handle_request(
        dummy_environ, mox.IgnoreArg(),
        self.dispatcher._server_name_to_server['default'],
        None).AndReturn(['Hello World'])
    self.mox.ReplayAll()
    response = self.dispatcher.add_request(
        'PUT', '/foo?bar=baz', [('Header', 'Value'), ('Other', 'Values')],
        'body', '1.2.3.4')
    self.mox.VerifyAll()
    self.assertEqual('Hello World', response.content)

  def test_handle_request(self):
    start_response = object()
    servr = self.dispatcher._server_name_to_server['other']
    self.mox.StubOutWithMock(servr, '_handle_request')
    servr._handle_request({'foo': 'bar'}, start_response, inst=None,
                          request_type=3).AndReturn(['body'])
    self.mox.ReplayAll()
    self.dispatcher._handle_request({'foo': 'bar'}, start_response, servr, None,
                                    request_type=3)
    self.mox.VerifyAll()

  def test_handle_request_reraise_exception(self):
    start_response = object()
    servr = self.dispatcher._server_name_to_server['other']
    self.mox.StubOutWithMock(servr, '_handle_request')
    servr._handle_request({'foo': 'bar'}, start_response).AndRaise(Exception)
    self.mox.ReplayAll()
    self.assertRaises(Exception, self.dispatcher._handle_request,
                      {'foo': 'bar'}, start_response, servr, None)
    self.mox.VerifyAll()

  def test_handle_request_log_exception(self):
    start_response = object()
    servr = self.dispatcher._server_name_to_server['other']
    self.mox.StubOutWithMock(servr, '_handle_request')
    self.mox.StubOutWithMock(logging, 'exception')
    servr._handle_request({'foo': 'bar'}, start_response).AndRaise(Exception)
    logging.exception('Internal error while handling request.')
    self.mox.ReplayAll()
    self.dispatcher._handle_request({'foo': 'bar'}, start_response, servr, None,
                                    catch_and_log_exceptions=True)
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
