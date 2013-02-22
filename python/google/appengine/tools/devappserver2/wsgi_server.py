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
"""A WSGI server implementation using a shared thread pool."""


import httplib
import select
import socket
import threading
import time

import google

from cherrypy import wsgiserver
from concurrent import futures

from google.appengine.tools.devappserver2 import errors
from google.appengine.tools.devappserver2 import http_runtime_constants


class BindError(errors.Error):
  """The server failed to bind its address."""

# TODO: Consolidate the various thread pools.
_THREAD_POOL = futures.ThreadPoolExecutor(max_workers=100)


class SharedCherryPyThreadPool(object):
  """A mimic of wsgiserver.ThreadPool that delegates to a shared thread pool."""

  def __init__(self):
    self._condition = threading.Condition()
    self._connections = set()  # Protected by self._condition.

  def stop(self, timeout=5):
    _THREAD_POOL.submit(self._stop, timeout)

  def _stop(self, timeout):
    timeout_time = time.time() + timeout
    with self._condition:
      while self._connections and time.time() < timeout_time:
        self._condition.wait(timeout_time - time.time())
      for connection in self._connections:
        self._shutdown_connection(connection)

  @staticmethod
  def _shutdown_connection(connection):
    if not connection.rfile.closed:
      connection.socket.shutdown(socket.SHUT_RD)

  def put(self, obj):
    with self._condition:
      self._connections.add(obj)
    _THREAD_POOL.submit(self._handle, obj)

  def _handle(self, obj):
    try:
      obj.communicate()
    finally:
      obj.close()
      with self._condition:
        self._connections.remove(obj)
        self._condition.notify()


class SelectThread(object):
  """A thread that selects on sockets and calls corresponding callbacks."""

  def __init__(self):
    self._lock = threading.Lock()
    # self._sockets is a frozenset and self._socket_to_callback is never mutated
    # so they can be snapshotted by the select thread without needing to copy.
    self._sockets = frozenset()
    self._socket_to_callback = {}
    self._select_thread = threading.Thread(target=self._loop_forever)
    self._select_thread.daemon = True

  def start(self):
    self._select_thread.start()

  def add_socket(self, s, callback):
    """Add a new socket to watch.

    Args:
      s: A socket to select on.
      callback: A callable with no args to be called when s is ready for a read.
    """
    with self._lock:
      self._sockets = self._sockets.union([s])
      new_socket_to_callback = self._socket_to_callback.copy()
      new_socket_to_callback[s] = callback
      self._socket_to_callback = new_socket_to_callback

  def remove_socket(self, s):
    """Remove a watched socket."""
    with self._lock:
      self._sockets = self._sockets.difference([s])
      new_socket_to_callback = self._socket_to_callback.copy()
      del new_socket_to_callback[s]
      self._socket_to_callback = new_socket_to_callback

  def _loop_forever(self):
    while True:
      self._select()

  def _select(self):
    with self._lock:
      sockets = self._sockets
      socket_to_callback = self._socket_to_callback
    if sockets:
      ready_sockets, _, _ = select.select(sockets, [], [], 1)
      for s in ready_sockets:
        socket_to_callback[s]()
    else:
      # select([], [], [], 1) is not supported on Windows.
      time.sleep(1)

_SELECT_THREAD = SelectThread()
_SELECT_THREAD.start()


class WsgiServer(wsgiserver.CherryPyWSGIServer):
  """A WSGI server that uses a shared SelectThread and thread pool."""

  def __init__(self, host, app):
    """Constructs a WsgiServer.

    Args:
      host: A (hostname, port) tuple containing the hostname and port to bind.
          The port can be 0 to allow any port.
      app: A WSGI app to handle requests.
    """
    super(WsgiServer, self).__init__(host, self)
    self._lock = threading.Lock()
    self._app = app  # Protected by _lock.
    self._error = None  # Protected by _lock.
    self.requests = SharedCherryPyThreadPool()
    self.software = http_runtime_constants.SERVER_SOFTWARE

  def start(self):
    """Starts the WsgiServer.

    This is a modified version of the base class implementation. Changes:
      - Removed unused functionality (Unix domain socket and SSL support).
      - Raises BindError instead of socket.error.
      - Uses SharedCherryPyThreadPool instead of wsgiserver.ThreadPool.
      - Calls _SELECT_THREAD.add_socket instead of looping forever.

    Raises:
      BindError: The address could not be bound.
    """
    # AF_INET or AF_INET6 socket
    # Get the correct address family for our host (allows IPv6 addresses)
    host, port = self.bind_addr
    try:
      info = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
    except socket.gaierror:
      if ':' in self.bind_addr[0]:
        info = [(socket.AF_INET6, socket.SOCK_STREAM, 0, '', self.bind_addr +
                 (0, 0))]
      else:
        info = [(socket.AF_INET, socket.SOCK_STREAM, 0, '', self.bind_addr)]

    self.socket = None
    for res in info:
      af, socktype, proto, _, _ = res
      try:
        self.bind(af, socktype, proto)
      except socket.error:
        if self.socket:
          self.socket.close()
        self.socket = None
        continue
      break
    if not self.socket:
      raise BindError('Unable to bind %s:%s' % self.bind_addr)

    # Timeout so KeyboardInterrupt can be caught on Win32
    self.socket.settimeout(1)
    self.socket.listen(self.request_queue_size)

    self.ready = True
    self._start_time = time.time()
    _SELECT_THREAD.add_socket(self.socket, self.tick)

  def quit(self):
    """Quits the WsgiServer."""
    _SELECT_THREAD.remove_socket(self.socket)
    self.requests.stop(timeout=1)

  @property
  def port(self):
    """Returns the port that the server is bound to."""
    return self.socket.getsockname()[1]

  def set_app(self, app):
    """Sets the PEP-333 app to use to serve requests."""
    with self._lock:
      self._app = app

  def set_error(self, error):
    """Sets the HTTP status code to serve for all requests."""
    with self._lock:
      self._error = error
      self._app = None

  def __call__(self, environ, start_response):
    with self._lock:
      app = self._app
      error = self._error
    if app:
      return app(environ, start_response)
    else:
      start_response('%d %s' % (error, httplib.responses[error]), [])
      return []
