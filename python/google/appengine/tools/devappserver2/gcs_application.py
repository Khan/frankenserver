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
"""Handles requests GCS API requests.

Includes a WSGI application that forwards Google Cloud Stroage API requests
to the local emulation layer.
"""


import httplib
import webob

from google.appengine.ext.cloudstorage import stub_dispatcher

# Regex for all requests routed through this module.
GCS_URL_PATTERN = '_ah/gcs/(.+)'

HTTP_308_STATUS_MESSAGE = 'Resume Incomplete'


class Application(object):
  """A WSGI application that forwards GCS requests to stub."""

  def __call__(self, environ, start_response):
    request = webob.Request(environ)

    try:
      result = stub_dispatcher.dispatch(request.method, request.headers,
                                        request.url, request.body)
    except ValueError as e:
      status_message = httplib.responses.get(e.args[1], '')
      start_response('%d %s' % (e.args[1], status_message), [])
      return [e.args[0]]

    # The metadata headers must be convereted from unicode to string.
    headers = []
    for k, v in result.headers.iteritems():
      headers.append((str(k), str(v)))

    # GCS uses non-standard HTTP 308 status code.
    status_code = result.status_code
    if status_code == 308:
      status_message = HTTP_308_STATUS_MESSAGE
    else:
      status_message = httplib.responses.get(status_code, '')

    start_response('%d %s' % (status_code, status_message), headers)

    return [result.content]
