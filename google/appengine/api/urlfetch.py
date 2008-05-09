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

"""URL downloading API.

Methods defined in this module:
   Fetch(): fetchs a given URL using an HTTP GET or POST
"""





from google.appengine.api import apiproxy_stub_map
from google.appengine.api import urlfetch_service_pb
from google.appengine.api.urlfetch_errors import *
from google.appengine.runtime import apiproxy_errors

GET = 1
POST = 2
HEAD = 3
PUT = 4
DELETE = 5


def fetch(url, payload=None, method=GET, headers={}, allow_truncated=False):
  """Fetches the given HTTP URL, blocking until the result is returned.

  Other optional parameters are:
     method: GET, POST, HEAD, PUT, or DELETE
     payload: POST or PUT payload (implies method is not GET, HEAD, or DELETE)
     headers: dictionary of HTTP headers to send with the request
     allow_truncated: if true, truncate large responses and return them without
     error. otherwise, ResponseTooLargeError will be thrown when a response is
     truncated.

  We use a HTTP/1.1 compliant proxy to fetch the result.

  The returned data structure has the following fields:
     content: string containing the response from the server
     status_code: HTTP status code returned by the server
     headers: dictionary of headers returned by the server

  If the URL is an empty string or obviously invalid, we throw an
  urlfetch.InvalidURLError. If the server cannot be contacted, we throw a
  urlfetch.DownloadError.  Note that HTTP errors are returned as a part
  of the returned structure, so HTTP errors like 404 do not result in an
  exception.
  """
  request = urlfetch_service_pb.URLFetchRequest()
  response = urlfetch_service_pb.URLFetchResponse()
  request.set_url(url)

  if method == GET:
    request.set_method(urlfetch_service_pb.URLFetchRequest.GET)
  elif method == POST:
    request.set_method(urlfetch_service_pb.URLFetchRequest.POST)
  elif method == HEAD:
    request.set_method(urlfetch_service_pb.URLFetchRequest.HEAD)
  elif method == PUT:
    request.set_method(urlfetch_service_pb.URLFetchRequest.PUT)
  elif method == DELETE:
    request.set_method(urlfetch_service_pb.URLFetchRequest.DELETE)

  if payload and (method == POST or method == PUT):
    request.set_payload(payload)

  for key, value in headers.iteritems():
    header_proto = request.add_header()
    header_proto.set_key(key)
    header_proto.set_value(value)

  try:
    apiproxy_stub_map.MakeSyncCall('urlfetch', 'Fetch', request, response)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        urlfetch_service_pb.URLFetchServiceError.INVALID_URL):
      raise InvalidURLError()
    if (e.application_error ==
        urlfetch_service_pb.URLFetchServiceError.UNSPECIFIED_ERROR):
      raise DownloadError()
    if (e.application_error ==
        urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR):
      raise DownloadError()
    if (e.application_error ==
        urlfetch_service_pb.URLFetchServiceError.RESPONSE_TOO_LARGE):
      raise ResponseTooLargeError(None)
    raise e
  result = _URLFetchResult(response)

  if not allow_truncated and response.contentwastruncated():
    raise ResponseTooLargeError(result)

  return result

Fetch = fetch


class _URLFetchResult(object):
  """A Pythonic representation of our fetch response protocol buffer."""
  def __init__(self, response_proto):
    self.__pb = response_proto
    self.content = response_proto.content()
    self.status_code = response_proto.statuscode()
    self.content_was_truncated = response_proto.contentwastruncated()
    self.headers = {}
    for header_proto in response_proto.header_list():
      self.headers[header_proto.key()] = header_proto.value()
