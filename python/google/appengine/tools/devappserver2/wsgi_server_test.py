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
"""Tests for google.appengine.tools.devappserver2.wsgi_server."""


import json
import select
import socket
import time
import unittest
import urllib2

import google

from cherrypy import wsgiserver
import mox

from google.appengine.tools.devappserver2 import wsgi_server


class TestError(Exception):
  pass


class WsgiServerTest(unittest.TestCase):
  def setUp(self):
    super(WsgiServerTest, self).setUp()
    self.server = wsgi_server.WsgiServer(('localhost', 0),
                                         self.wsgi_application)
    self.server.start()

  def tearDown(self):
    super(WsgiServerTest, self).tearDown()
    self.server.quit()

  def test_serve(self):
    result = urllib2.urlopen('http://localhost:%d/foo?bar=baz' %
                             self.server.port)
    body = result.read()
    environ = json.loads(body)
    self.assertEqual(200, result.code)
    self.assertEqual('/foo', environ['PATH_INFO'])
    self.assertEqual('bar=baz', environ['QUERY_STRING'])

  def wsgi_application(self, environ, start_response):
    start_response('200 OK', [('Content-Type', 'application/json')])
    serializable_environ = environ.copy()
    del serializable_environ['wsgi.input']
    del serializable_environ['wsgi.errors']
    return [json.dumps(serializable_environ)]

  def other_wsgi_application(self, environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return ['Hello World']

  def test_set_app(self):
    self.server.set_app(self.other_wsgi_application)
    result = urllib2.urlopen('http://localhost:%d/foo?bar=baz' %
                             self.server.port)
    body = result.read()
    self.assertEqual(200, result.code)
    self.assertEqual('Hello World', body)

  def test_set_error(self):
    self.server.set_error(204)
    result = urllib2.urlopen('http://localhost:%d/foo?bar=baz' %
                             self.server.port)
    self.assertEqual(204, result.code)


class SharedCherryPyThreadPoolTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(wsgi_server._THREAD_POOL, 'submit')
    self.thread_pool = wsgi_server.SharedCherryPyThreadPool()

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_put(self):
    connection = object()
    wsgi_server._THREAD_POOL.submit(self.thread_pool._handle, connection)
    self.mox.ReplayAll()
    self.thread_pool.put(connection)
    self.mox.VerifyAll()
    self.assertEqual(set([connection]), self.thread_pool._connections)

  def test_handle(self):
    connection = self.mox.CreateMock(wsgiserver.HTTPConnection)
    self.mox.StubOutWithMock(self.thread_pool._condition, 'notify')
    self.thread_pool._connections.add(connection)
    connection.communicate()
    connection.close()
    self.thread_pool._condition.notify()
    self.mox.ReplayAll()
    self.thread_pool._handle(connection)
    self.mox.VerifyAll()
    self.assertEqual(set(), self.thread_pool._connections)

  def test_handle_with_exception(self):
    connection = self.mox.CreateMock(wsgiserver.HTTPConnection)
    self.mox.StubOutWithMock(self.thread_pool._condition, 'notify')
    self.thread_pool._connections.add(connection)
    connection.communicate().AndRaise(TestError)
    connection.close()
    self.thread_pool._condition.notify()
    self.mox.ReplayAll()
    self.assertRaises(TestError, self.thread_pool._handle, connection)
    self.mox.VerifyAll()
    self.assertEqual(set(), self.thread_pool._connections)

  def test_stop(self):
    wsgi_server._THREAD_POOL.submit(self.thread_pool._stop, 3)
    self.mox.ReplayAll()
    self.thread_pool.stop(3)
    self.mox.VerifyAll()

  def test__stop_no_connections(self):
    self.mox.ReplayAll()
    self.thread_pool._stop(0.1)
    self.mox.VerifyAll()

  def test__stop_with_connections(self):
    connection = self.mox.CreateMock(wsgiserver.HTTPConnection)
    self.thread_pool._connections.add(connection)
    self.mox.StubOutWithMock(self.thread_pool, '_shutdown_connection')
    self.thread_pool._shutdown_connection(connection)

    self.mox.ReplayAll()
    self.thread_pool._stop(1)
    self.mox.VerifyAll()

  def test_shutdown_connection(self):

    class DummyObect(object):
      pass

    connection = DummyObect()
    connection.rfile = DummyObect()
    connection.rfile.closed = False
    connection.socket = self.mox.CreateMockAnything()
    connection.socket.shutdown(socket.SHUT_RD)

    self.mox.ReplayAll()
    self.thread_pool._shutdown_connection(connection)
    self.mox.VerifyAll()

  def test_shutdown_connection_rfile_already_close(self):

    class DummyObect(object):
      pass

    connection = DummyObect()
    connection.rfile = DummyObect()
    connection.rfile.closed = True
    connection.socket = self.mox.CreateMockAnything()

    self.mox.ReplayAll()
    self.thread_pool._shutdown_connection(connection)
    self.mox.VerifyAll()


class SelectThreadTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.select_thread = wsgi_server.SelectThread()

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_add_socket(self):
    sockets = self.select_thread._sockets
    socket_to_callback = self.select_thread._socket_to_callback
    sockets_copy = frozenset(self.select_thread._sockets)
    socket_to_callback_copy = self.select_thread._socket_to_callback.copy()
    s = object()
    callback = object()
    self.select_thread.add_socket(s, callback)
    self.assertEqual(sockets_copy, sockets)
    self.assertEqual(socket_to_callback_copy, socket_to_callback)
    self.assertEqual(frozenset([s]), self.select_thread._sockets)
    self.assertEqual({s: callback}, self.select_thread._socket_to_callback)

  def test_remove_socket(self):
    s1 = object()
    callback1 = object()
    s2 = object()
    callback2 = object()
    self.select_thread._sockets = frozenset([s1, s2])
    self.select_thread._socket_to_callback = {s1: callback1, s2: callback2}
    sockets = self.select_thread._sockets
    socket_to_callback = self.select_thread._socket_to_callback
    sockets_copy = frozenset(self.select_thread._sockets)
    socket_to_callback_copy = self.select_thread._socket_to_callback.copy()
    self.select_thread.remove_socket(s1)
    self.assertEqual(sockets_copy, sockets)
    self.assertEqual(socket_to_callback_copy, socket_to_callback)
    self.assertEqual(frozenset([s2]), self.select_thread._sockets)
    self.assertEqual({s2: callback2}, self.select_thread._socket_to_callback)

  def test_select_no_sockets(self):
    self.mox.StubOutWithMock(select, 'select')
    self.mox.StubOutWithMock(time, 'sleep')
    time.sleep(1)
    self.mox.ReplayAll()
    self.select_thread._select()
    self.mox.VerifyAll()

  def test_select(self):
    s = object()
    self.mox.StubOutWithMock(select, 'select')
    callback = self.mox.CreateMockAnything()
    select.select(frozenset([s]), [], [], 1).AndReturn(([s], [], []))
    callback()
    self.mox.ReplayAll()
    self.select_thread.add_socket(s, callback)
    self.select_thread._select()
    self.mox.VerifyAll()

  def test_select_not_ready(self):
    s = object()
    self.mox.StubOutWithMock(select, 'select')
    callback = self.mox.CreateMockAnything()
    select.select(frozenset([s]), [], [], 1).AndReturn(([], [], []))
    self.mox.ReplayAll()
    self.select_thread.add_socket(s, callback)
    self.select_thread._select()
    self.mox.VerifyAll()


class WsgiServerStartupTest(unittest.TestCase):

  def setUp(self):
    self.mox = mox.Mox()
    self.server = wsgi_server.WsgiServer(('localhost', 0), None)

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_start_port_in_use(self):
    self.mox.StubOutWithMock(socket, 'getaddrinfo')
    self.mox.StubOutWithMock(self.server, 'bind')
    af = object()
    socktype = object()
    proto = object()
    socket.getaddrinfo('localhost', 0, socket.AF_UNSPEC, socket.SOCK_STREAM, 0,
                       socket.AI_PASSIVE).AndReturn(
                           [(af, socktype, proto, None, None)])
    self.server.bind(af, socktype, proto).AndRaise(socket.error)
    self.mox.ReplayAll()
    self.assertRaises(wsgi_server.BindError, self.server.start)
    self.mox.VerifyAll()

  def test_start(self):
    # Ensure no CherryPy thread pools are started.
    self.mox.StubOutWithMock(wsgiserver.ThreadPool, 'start')
    self.mox.StubOutWithMock(wsgi_server._SELECT_THREAD, 'add_socket')
    wsgi_server._SELECT_THREAD.add_socket(mox.IsA(socket.socket),
                                          self.server.tick)
    self.mox.ReplayAll()
    self.server.start()
    self.mox.VerifyAll()

  def test_quit(self):
    self.mox.StubOutWithMock(wsgi_server._SELECT_THREAD, 'remove_socket')
    self.server.socket = object()
    self.server.requests = self.mox.CreateMock(
        wsgi_server.SharedCherryPyThreadPool)
    wsgi_server._SELECT_THREAD.remove_socket(self.server.socket)
    self.server.requests.stop(timeout=1)
    self.mox.ReplayAll()
    self.server.quit()
    self.mox.VerifyAll()

if __name__ == '__main__':
  unittest.main()
