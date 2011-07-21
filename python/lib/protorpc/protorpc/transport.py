#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
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

"""Transport library for ProtoRPC.

Contains underlying infrastructure used for communicating RPCs over low level
transports such as HTTP.

Includes HTTP transport built over urllib2.
"""

import logging
import sys
import urllib2

from protorpc import messages
from protorpc import protobuf
from protorpc import remote
from protorpc import util

try:
  from google.appengine.api import urlfetch
except ImportError:
  urlfetch = None

__all__ = [
  'RpcStateError',

  'HttpTransport',
  'Rpc',
  'Transport',
]


class RpcStateError(messages.Error):
  """Raised when trying to put RPC in to an invalid state."""


class Rpc(object):
  """Represents a client side RPC.

  An RPC is created by the transport class and is used with a single RPC.  While
  an RPC is still in process, the response is set to None.  When it is complete
  the response will contain the response message.
  """

  def __init__(self, request):
    """Constructor.

    Args:
      request: Request associated with this RPC.
    """
    self.__request = request
    self.__response = None
    self.__state = remote.RpcState.RUNNING
    self.__error_message = None
    self.__error_name = None

  @property
  def request(self):
    """Request associated with RPC."""
    return self.__request

  @property
  def response(self):
    """Response associated with RPC."""
    self.wait()
    self.__check_status()
    return self.__response

  @property
  def state(self):
    """State associated with RPC."""
    return self.__state

  @property
  def error_message(self):
    """Error, if any, associated with RPC."""
    self.wait()
    return self.__error_message

  @property
  def error_name(self):
    """Error name, if any, associated with RPC."""
    self.wait()
    return self.__error_name

  def wait(self):
    """Wait for an RPC to finish."""
    if self.__state == remote.RpcState.RUNNING:
      self._wait_impl()

  def _wait_impl(self):
    """Implementation for wait()."""
    raise NotImplementedError()

  def __check_status(self):
    error_class = remote.RpcError.from_state(self.__state)
    if error_class is not None:
      if error_class is remote.ApplicationError:
        raise error_class(self.__error_message, self.__error_name)
      else:
        raise error_class(self.__error_message)

  def __set_state(self, state, error_message=None, error_name=None):
    if self.__state != remote.RpcState.RUNNING:
      raise RpcStateError(
        'RPC must be in RUNNING state to change to %s' % state)
    if state == remote.RpcState.RUNNING:
      raise RpcStateError('RPC is already in RUNNING state')
    self.__state = state
    self.__error_message = error_message
    self.__error_name = error_name

  def set_response(self, response):
    # TODO: Even more specific type checking.
    if not isinstance(response, messages.Message):
      raise TypeError('Expected Message type, received %r' % (response))

    self.__response = response
    self.__set_state(remote.RpcState.OK)

  def set_status(self, status):
    status.check_initialized()
    self.__set_state(status.state, status.error_message, status.error_name)


class Transport(object):
  """Transport base class.

  Provides basic support for implementing a ProtoRPC transport such as one
  that can send and receive messages over HTTP.

  Implementations override _start_rpc.  This method receives a RemoteInfo
  instance and a request Message. The transport is expected to set the rpc
  response or raise an exception before termination.
  """

  @util.positional(1)
  def __init__(self, protocol=protobuf):
    """Constructor.

    Args:
      protocol: The protocol implementation.  Must implement encode_message and
        decode_message.
    """
    self.__protocol = protocol

  @property
  def protocol(self):
    """Protocol associated with this transport."""
    return self.__protocol

  def send_rpc(self, remote_info, request):
    """Initiate sending an RPC over the transport.

    Args:
      remote_info: RemoteInfo instance describing remote method.
      request: Request message to send to service.

    Returns:
      An Rpc instance intialized with the request..
    """
    request.check_initialized()

    rpc = self._start_rpc(remote_info, request)

    return rpc

  def _start_rpc(self, remote_info, request):
    """Start a remote procedure call.

    Args:
      remote_info: RemoteInfo instance describing remote method.
      request: Request message to send to service.

    Returns:
      An Rpc instance initialized with the request.
    """
    raise NotImplementedError()


class HttpTransport(Transport):
  """Transport for communicating with HTTP servers."""

  class __HttpRequest(object):
    """Base class for library-specific requests."""

    def __init__(self, method_url, transport, encoded_request):
      """Constructor.

      Args:
        method_url: The URL where the method is located.
        transport: The Transport instance making the request.
      """
      self._method_url = method_url
      self._transport = transport

      self._start_request(encoded_request)

    def _get_rpc_status(self, content_type, content):
      """Get an RpcStats from content.

      Args:
        content_type: Content-type of the provided content.
        content: Content of the http response.

      Returns:
        RpcStatus if found in content. If not, returns None.
      """
      protocol = self._transport.protocol
      if content_type == protocol.CONTENT_TYPE:
        try:
          rpc_status = protocol.decode_message(remote.RpcStatus, content)
        except Exception, decode_err:
          logging.warning(
            'An error occurred trying to parse status: %s\n%s',
            str(decode_err), content)
          return None
        else:
          return rpc_status

    def _start_request(self):
      raise NotImplementedError()

    def get_response(self):
      """Get the encoded response for the request.

      If an error occurs on the server and the server sends an RpcStatus
      as the response body, an RpcStatus will be returned as the second
      element in the response tuple.

      In cases where there is an error, but no RpcStatus is transmitted,
      we raise a ServerError with the response content.

      Returns:
        Tuple (encoded_response, rpc_status):
          encoded_response: Encoded message in protocols wire format.
          rpc_status: RpcStatus if returned by server.

      Raises:
        NetworkError if transport has issues communicating with the network.
        RequestError if transport receives an error constructing the
          HttpRequest.
        ServerError if the server responds with an http error code and does
          not send an encoded RpcStatus as the response content.
      """
      raise NotImplementedError()


  class __UrlfetchRequest(__HttpRequest):
    """Request cycle for a remote call using urlfetch."""

    __urlfetch_rpc = None

    def _start_request(self, encoded_request):
      """Initiate async call."""

      self.__urlfetch_rpc = urlfetch.create_rpc()

      headers = {
        'Content-type': self._transport.protocol.CONTENT_TYPE
      }

      urlfetch.make_fetch_call(self.__urlfetch_rpc,
                               self._method_url,
                               payload=encoded_request,
                               method='POST',
                               headers=headers)

    def get_response(self):
      try:
        http_response = self.__urlfetch_rpc.get_result()

        if http_response.status_code >= 400:
          status = self._get_rpc_status(
            http_response.headers.get('content-type'),
            http_response.content)

          if status:
            return http_response.content, status

          return None, remote.RpcStatus(state=remote.RpcState.SERVER_ERROR,
                                        error_message=http_response.content)

      except urlfetch.DownloadError, err:
        raise remote.NetworkError, (str(err), err)

      except urlfetch.InvalidURLError, err:
        raise remote.RequestError, 'Invalid URL, received: %s' % (
          self.__urlfetch.request.url())

      except urlfetch.ResponseTooLargeError:
        raise remote.NetworkError(
          'The response data exceeded the maximum allowed size.')

      return http_response.content, None


  class __UrllibRequest(__HttpRequest):
    """Request cycle for a remote call using Urllib."""

    def _start_request(self, encoded_request):
      """Create the urllib2 request. """
      http_request = urllib2.Request(self._method_url, encoded_request)
      http_request.add_header('Content-type',
                              self._transport.protocol.CONTENT_TYPE)

      self.__http_request = http_request

    def get_response(self):
      try:
        http_response = urllib2.urlopen(self.__http_request)
      except urllib2.HTTPError, err:
        if err.code >= 400:
          status = self._get_rpc_status(err.hdrs.get('content-type'),
                                        err.read())

          if status:
            return err.msg, status

        # TODO: Map other types of errors to appropriate exceptions.
        _, _, trace_back = sys.exc_info()
        return None, remote.RpcStatus(state=remote.RpcState.SERVER_ERROR,
                                      error_message='HTTP Error %s: %s' % (
                                        err.code, err.msg))

      except urllib2.URLError, err:
        _, _, trace_back = sys.exc_info()
        if isinstance(err, basestring):
          error_message = err
        else:
          error_message = err.args[0]

        return None, remote.RpcStatus(state=remote.RpcState.NETWORK_ERROR,
                                      error_message='Network Error: %s' %
                                      error_message)

      return http_response.read(), None

  @util.positional(2)
  def __init__(self, service_url, protocol=protobuf):
    """Constructor.

    Args:
      service_url: URL where the service is located.  All communication via
        the transport will go to this URL.
      protocol: The protocol implementation.  Must implement encode_message and
        decode_message.
    """
    super(HttpTransport, self).__init__(protocol=protocol)
    self.__service_url = service_url

    if urlfetch:
      self.__request_type = self.__UrlfetchRequest
    else:
      self.__request_type = self.__UrllibRequest

  def _start_rpc(self, remote_info, request):
    """Start a remote procedure call.

    Args:
      remote_info: A RemoteInfo instance for this RPC.
      request: The request message for this RPC.

    Returns:
      An Rpc instance initialized with a Request.
    """
    method_url = '%s.%s' % (self.__service_url, remote_info.method.func_name)
    encoded_request = self.protocol.encode_message(request)

    http_request = self.__request_type(method_url=method_url,
                                       transport=self,
                                       encoded_request=encoded_request)

    rpc = Rpc(request)

    def wait_impl():
      """Implementation of _wait for an Rpc."""

      encoded_response, status = http_request.get_response()

      if status:
        rpc.set_status(status)
      else:
        response = self.protocol.decode_message(remote_info.response_type,
                                                encoded_response)
        rpc.set_response(response)

    rpc._wait_impl = wait_impl

    return rpc
