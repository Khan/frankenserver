from __future__ import absolute_import

import webapp2

class PingHandler(webapp2.RequestHandler):
  def get(self):
    self.response.status_int = 200
    self.response.content_type = 'text/plain'
    self.response.write('pong')
