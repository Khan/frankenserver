"""Accepts datastore v1 REST API requests, translating them to App Engine RPCs.

This allows other applications -- those not written for App Engine (or written
for Second Gen runtimes) -- to talk to the App Engine datastore stub using the
new (v1) public REST API.

It's intended to serve a similar purpose to the Google Cloud Datastore
Emulator, but by building on the old sqlite stub it can handle a lot more data
without trouble.  (Khan folks, see ADR #166 for details.)
"""
from __future__ import absolute_import

import logging

import webapp2

from google.appengine.tools.devappserver2 import wsgi_server

from . import handlers


_ROUTES = [
    ('/', handlers.Ping),
    ('/v1/projects/([^/:]*):allocateIds', handlers.AllocateIds),
    ('/v1/projects/([^/:]*):lookup', handlers.Lookup),
    ('/v1/projects/([^/:]*):runQuery', handlers.RunQuery),
]


def get_app(host=None, enable_host_checking=True):
  """Get the WSGI app.

  Only tests likely need this directly.  host is required if
  enable_host_checking is set (the default) and ignored otherwise.
  """
  translator_app = webapp2.WSGIApplication(_ROUTES, debug=False)
  if enable_host_checking:
    translator_app = wsgi_server.WsgiHostCheck([host], translator_app)
  return translator_app


class DatastoreTranslatorServer(wsgi_server.WsgiServer):
  """The class that devappserver2.py loads to run the datastore translator.

  Init args:
    host: A string containing the name of the host that the server should
        bind to e.g. "localhost".
    port: An int containing the port that the server should bind to e.g. 80.
    enable_host_checking: A bool indicating that HTTP Host checking should
        be enforced for incoming requests.
  """
  def __init__(self, host, port, enable_host_checking=True):
    self._host = host
    app = get_app(host, enable_host_checking)
    super(DatastoreTranslatorServer, self).__init__((host, port), app)

  def start(self):
    super(DatastoreTranslatorServer, self).start()
    logging.info('Starting datastore translator server at: http://%s:%d',
                 *self.bind_addr)
