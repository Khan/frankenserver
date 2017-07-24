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
"""Provides A WSGI Proxy Server that translates remote api call into grpc.

Without this proxy, remote_api_stub would need to import grpc into the python
runtime it lives, which is also the same process running user applications.
Hence the grpc module imported by devappserver would pollute python runtime.
"""

import logging
import os
from grpc.beta import implementations

from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.tools.devappserver2 import grpc_service_pb2
from google.appengine.tools.devappserver2 import wsgi_server


def create_stub(grpc_apiserver_host):
  """Creates a grpc_service.CallHandler stub.

  Args:
    grpc_apiserver_host: String, the host that CallHandler service listens on.
      Should be in the format of hostname:port.

  Returns:
    A CallHandler stub.
  """
  # See http://www.grpc.io/grpc/python/_modules/grpc/beta/implementations.html:
  # the method insecure_channel requires explicitly two parameters (host, port)
  # here our host already contain port number, so the second parameter is None.
  prefix = 'http://'
  if grpc_apiserver_host.startswith(prefix):
    grpc_apiserver_host = grpc_apiserver_host[len(prefix):]
  channel = implementations.insecure_channel(grpc_apiserver_host, None)
  return grpc_service_pb2.beta_create_CallHandler_stub(channel)


def make_grpc_call_from_remote_api(stub, request):
  """Translate remote_api_pb.Request to gRPC call.

  Args:
    stub: A grpc_service_pb2.beta_create_CallHandler_stub object.
    request: A remote_api_pb.Request message.

  Returns:
    A remote_api_pb.Response message.
  """
  # Translate remote_api_pb.Request into grpc_service_pb2.Request
  request_pb = grpc_service_pb2.Request(
      service_name=request.service_name(),
      method=request.method(),
      request=request.request())
  if request.has_request_id():
    request_pb.request_id = request.request_id()

  response_pb = stub.HandleCall(request_pb, remote_api_stub.TIMEOUT_SECONDS)

  # Translate grpc_service_pb2.Response back to remote_api_pb.Response
  response = remote_api_pb.Response()
  # TODO: b/36590656#comment3 continuously complete exception handling.
  response.set_response(response_pb.response)
  if response_pb.HasField('rpc_error'):
    response.mutable_rpc_error().ParseFromString(
        response_pb.rpc_error.SerializeToString())
  if response_pb.HasField('application_error'):
    response.mutable_application_error().ParseFromString(
        response_pb.application_error.SerializeToString())
  return response


class GrpcProxyServer(wsgi_server.WsgiServer):
  """A WSGI Server that translates remote api call into grpc."""

  GRPC_API_SERVER_HOST = 'localhost'

  def __init__(self, port):
    """Initialize the grpc proxy server.

    Args:
      port: An integer indicating the port number this server listens on.
    """
    self._port = port
    self._stub = create_stub(
        '%s:%s' % (self.GRPC_API_SERVER_HOST, os.environ['GRPC_PORT']))
    super(GrpcProxyServer, self).__init__(
        (self.GRPC_API_SERVER_HOST, self._port), self)

  def __call__(self, environ, start_response):
    """Handles WSGI requests.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      An encoded proto message: remote_api.Response.
    """
    start_response('200 OK', [('Content-Type', 'application/octet-stream')])

    # NOTE: Exceptions encountered when parsing the PB or handling the request
    # will be propagated back to the caller the same way as exceptions raised
    # by the actual API call.
    if environ.get('HTTP_TRANSFER_ENCODING') == 'chunked':
      # CherryPy concatenates all chunks  when 'wsgi.input' is read but v3.2.2
      # will not return even when all of the data in all chunks has been
      # read. See: https://bitbucket.org/cherrypy/cherrypy/issue/1131.
      wsgi_input = environ['wsgi.input'].read(2**32)
    else:
      wsgi_input = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))

    request = remote_api_pb.Request()
    request.ParseFromString(wsgi_input)
    response = make_grpc_call_from_remote_api(self._stub, request)
    return response.Encode()

  def start(self):
    super(GrpcProxyServer, self).start()
    logging.info('Starting GRPC Proxy server at: http://%s:%s',
                 self.GRPC_API_SERVER_HOST, self._port)
