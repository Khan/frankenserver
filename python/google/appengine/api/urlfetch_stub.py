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

"""Stub version of the urlfetch API, based on httplib."""



import httplib
import logging
import socket
import urllib
import urlparse

from google.appengine.api import apiproxy_stub
from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors
from google.appengine.api import urlfetch_service_pb
from google.appengine.runtime import apiproxy_errors


MAX_RESPONSE_SIZE = 2 ** 24

MAX_REDIRECTS = urlfetch.MAX_REDIRECTS

REDIRECT_STATUSES = frozenset([
  httplib.MOVED_PERMANENTLY,
  httplib.FOUND,
  httplib.SEE_OTHER,
  httplib.TEMPORARY_REDIRECT,
])

PORTS_ALLOWED_IN_PRODUCTION = (
    None, '80', '443', '4443', '8080', '8081', '8082', '8083', '8084', '8085',
    '8086', '8087', '8088', '8089', '8188', '8444', '8990')

_API_CALL_DEADLINE = 5.0


_UNTRUSTED_REQUEST_HEADERS = frozenset([
  'accept-encoding',
  'content-length',
  'host',
  'referer',
  'vary',
  'via',
  'x-forwarded-for',
])

class URLFetchServiceStub(apiproxy_stub.APIProxyStub):
  """Stub version of the urlfetch API to be used with apiproxy_stub_map."""

  def __init__(self, service_name='urlfetch'):
    """Initializer.

    Args:
      service_name: Service name expected for all calls.
    """
    super(URLFetchServiceStub, self).__init__(service_name)

  def _Dynamic_Fetch(self, request, response):
    """Trivial implementation of URLFetchService::Fetch().

    Args:
      request: the fetch to perform, a URLFetchRequest
      response: the fetch response, a URLFetchResponse
    """
    (protocol, host, path, parameters, query, fragment) = urlparse.urlparse(request.url())

    payload = None
    if request.method() == urlfetch_service_pb.URLFetchRequest.GET:
      method = 'GET'
    elif request.method() == urlfetch_service_pb.URLFetchRequest.POST:
      method = 'POST'
      payload = request.payload()
    elif request.method() == urlfetch_service_pb.URLFetchRequest.HEAD:
      method = 'HEAD'
    elif request.method() == urlfetch_service_pb.URLFetchRequest.PUT:
      method = 'PUT'
      payload = request.payload()
    elif request.method() == urlfetch_service_pb.URLFetchRequest.DELETE:
      method = 'DELETE'
    else:
      logging.error('Invalid method: %s', request.method())
      raise apiproxy_errors.ApplicationError(
        urlfetch_service_pb.URLFetchServiceError.UNSPECIFIED_ERROR)

    if not (protocol == 'http' or protocol == 'https'):
      logging.error('Invalid protocol: %s', protocol)
      raise apiproxy_errors.ApplicationError(
        urlfetch_service_pb.URLFetchServiceError.INVALID_URL)

    if not host:
      logging.error('Missing host.')
      raise apiproxy_errors.ApplicationError(
          urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR)

    sanitized_headers = self._SanitizeHttpHeaders(_UNTRUSTED_REQUEST_HEADERS,
                                                  request.header_list())
    request.clear_header()
    request.header_list().extend(sanitized_headers)

    self._RetrieveURL(request.url(), payload, method,
                      request.header_list(), response,
                      follow_redirects=request.followredirects())

  def _RetrieveURL(self, url, payload, method, headers, response,
                   follow_redirects=True):
    """Retrieves a URL.

    Args:
      url: String containing the URL to access.
      payload: Request payload to send, if any; None if no payload.
      method: HTTP method to use (e.g., 'GET')
      headers: List of additional header objects to use for the request.
      response: Response object
      follow_redirects: optional setting (defaulting to True) for whether or not
        we should transparently follow redirects (up to MAX_REDIRECTS)

    Raises:
      Raises an apiproxy_errors.ApplicationError exception with FETCH_ERROR
      in cases where:
        - MAX_REDIRECTS is exceeded
        - The protocol of the redirected URL is bad or missing.
    """
    last_protocol = ''
    last_host = ''

    for redirect_number in xrange(MAX_REDIRECTS + 1):
      parsed = urlparse.urlparse(url)
      protocol, host, path, parameters, query, fragment = parsed

      port = urllib.splitport(urllib.splituser(host)[1])[1]

      if port not in PORTS_ALLOWED_IN_PRODUCTION:
        logging.warning(
          'urlfetch received %s ; port %s is not allowed in production!' %
          (url, port))

      if protocol and not host:
        logging.error('Missing host on redirect; target url is %s' % url)
        raise apiproxy_errors.ApplicationError(
          urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR)

      if not host and not protocol:
        host = last_host
        protocol = last_protocol

      adjusted_headers = {
        'Host': host,
        'Accept': '*/*',
      }
      if payload is not None:
        adjusted_headers['Content-Length'] = len(payload)
      if method == 'POST' and payload:
        adjusted_headers['Content-Type'] = 'application/x-www-form-urlencoded'

      for header in headers:
        adjusted_headers[header.key().title()] = header.value()

      logging.debug('Making HTTP request: host = %s, '
                    'url = %s, payload = %s, headers = %s',
                    host, url, payload, adjusted_headers)
      try:
        if protocol == 'http':
          connection = httplib.HTTPConnection(host)
        elif protocol == 'https':
          connection = httplib.HTTPSConnection(host)
        else:
          error_msg = 'Redirect specified invalid protocol: "%s"' % protocol
          logging.error(error_msg)
          raise apiproxy_errors.ApplicationError(
              urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR, error_msg)

        last_protocol = protocol
        last_host = host

        if query != '':
          full_path = path + '?' + query
        else:
          full_path = path

        orig_timeout = socket.getdefaulttimeout()
        try:
          socket.setdefaulttimeout(_API_CALL_DEADLINE)
          connection.request(method, full_path, payload, adjusted_headers)
          http_response = connection.getresponse()
          http_response_data = http_response.read()
        finally:
          socket.setdefaulttimeout(orig_timeout)
          connection.close()
      except (httplib.error, socket.error, IOError), e:
        raise apiproxy_errors.ApplicationError(
          urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR, str(e))

      if http_response.status in REDIRECT_STATUSES and follow_redirects:
        url = http_response.getheader('Location', None)
        if url is None:
          error_msg = 'Redirecting response was missing "Location" header'
          logging.error(error_msg)
          raise apiproxy_errors.ApplicationError(
              urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR, error_msg)
      else:
        response.set_statuscode(http_response.status)
        response.set_content(http_response_data[:MAX_RESPONSE_SIZE])
        for header_key, header_value in http_response.getheaders():
          header_proto = response.add_header()
          header_proto.set_key(header_key)
          header_proto.set_value(header_value)

        if len(http_response_data) > MAX_RESPONSE_SIZE:
          response.set_contentwastruncated(True)

        break
    else:
      error_msg = 'Too many repeated redirects'
      logging.error(error_msg)
      raise apiproxy_errors.ApplicationError(
          urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR, error_msg)

  def _SanitizeHttpHeaders(self, untrusted_headers, headers):
    """Cleans "unsafe" headers from the HTTP request/response.

    Args:
      untrusted_headers: set of untrusted headers names
      headers: list of string pairs, first is header name and the second is header's value
    """
    return (h for h in headers if h.key().lower() not in untrusted_headers)
