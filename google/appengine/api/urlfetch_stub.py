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
import urlparse

from google.appengine.api import urlfetch_errors
from google.appengine.api import urlfetch_service_pb
from google.appengine.runtime import apiproxy_errors


MAX_RESPONSE_SIZE = 2 ** 24

MAX_REDIRECTS = 5

REDIRECT_STATUSES = frozenset([
  httplib.MOVED_PERMANENTLY,
  httplib.FOUND,
  httplib.SEE_OTHER,
  httplib.TEMPORARY_REDIRECT,
])


class URLFetchServiceStub(object):
  """Stub version of the urlfetch API to be used with apiproxy_stub_map."""

  def MakeSyncCall(self, service, call, request, response):
    """The main RPC entry point.

    Arg:
      service: Must be 'urlfetch'.
      call: A string representing the rpc to make.  Must be part of
        URLFetchService.
      request: A protocol buffer of the type corresponding to 'call'.
      response: A protocol buffer of the type corresponding to 'call'.
    """
    assert service == 'urlfetch'
    assert request.IsInitialized()

    attr = getattr(self, '_Dynamic_' + call)
    attr(request, response)

  def _Dynamic_Fetch(self, request, response):
    """Trivial implementation of URLFetchService::Fetch().

    Args:
      request: the fetch to perform, a URLFetchRequest
      response: the fetch response, a URLFetchResponse
    """
    (protocol, host, path, parameters, query, fragment) = urlparse.urlparse(request.url())

    payload = ''
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
    elif request.method() == urlfetch_service_pb.URLFetchRequest.HEAD:
      method = 'DELETE'
    else:
      logging.error('Invalid method: %s', request.method())
      raise apiproxy_errors.ApplicationError(
        urlfetch_service_pb.URLFetchServiceError.UNSPECIFIED_ERROR)

    if not (protocol == 'http' or protocol == 'https'):
      logging.error('Invalid protocol: %s', protocol)
      raise apiproxy_errors.ApplicationError(
        urlfetch_service_pb.URLFetchServiceError.INVALID_URL)

    self._RetrieveURL(request.url(), payload, method,
                      request.header_list(), response)

  def _RetrieveURL(self, url, payload, method, headers, response):
    """Retrieves a URL.

    Args:
      url: String containing the URL to access.
      payload: Request payload to send, if any.
      method: HTTP method to use (e.g., 'GET')
      headers: List of additional header objects to use for the request.
      response: Response object

    Raises:
      Raises an apiproxy_errors.ApplicationError exception with FETCH_ERROR
      in cases where:
        - MAX_REDIRECTS is exceeded
        - The protocol of the redirected URL is bad or missing.
    """
    last_protocol = ''
    last_host = ''

    for redirect_number in xrange(MAX_REDIRECTS + 1):
      (protocol, host, path, parameters, query, fragment) = urlparse.urlparse(url)

      if host == '' and protocol == '':
        host = last_host
        protocol = last_protocol

      adjusted_headers = {
        'Content-Length': len(payload),
        'Host': host,
        'Accept': '*/*',
      }
      for header in headers:
        adjusted_headers[header.key()] = header.value()

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

        try:
          connection.request(method, full_path, payload, adjusted_headers)
          http_response = connection.getresponse()
          http_response_data = http_response.read()
        finally:
          connection.close()
      except (httplib.error, socket.error, IOError), e:
        raise apiproxy_errors.ApplicationError(
          urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR, str(e))

      if http_response.status in REDIRECT_STATUSES:
        url = http_response.getheader('Location', None)
        if url is None:
          error_msg = 'Redirecting response was missing "Location" header'
          logging.error(error_msg)
          raise apiproxy_errors.ApplicationError(
              urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR, error_msg)
        else:
          method = 'GET'
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
