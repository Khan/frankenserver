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
"""Helper for Cloud Endpoints API server in the development app server.

This is a fake apiserver proxy that does simple transforms on requests that
come in to /_ah/api and then re-dispatches them to /_ah/spi.  It does not do
any authentication, quota checking, DoS checking, etc.

In addition, the proxy loads api configs from
/_ah/spi/BackendService.getApiConfigs prior to each call, in case the
configuration has changed.
"""



import json
import logging
import re
import wsgiref

from google.appengine.tools.devappserver2.endpoints import api_config_manager
from google.appengine.tools.devappserver2.endpoints import api_request
from google.appengine.tools.devappserver2.endpoints import discovery_api_proxy
from google.appengine.tools.devappserver2.endpoints import discovery_service
from google.appengine.tools.devappserver2.endpoints import util


__all__ = ['API_SERVING_PATTERN',
           'EndpointsDispatcher']


# Pattern for paths handled by this module.
API_SERVING_PATTERN = '_ah/api/.*'

_SPI_ROOT_FORMAT = '/_ah/spi/%s'
_SERVER_SOURCE_IP = '0.2.0.3'

# Internal constants
_CORS_HEADER_ORIGIN = 'Origin'
_CORS_HEADER_REQUEST_METHOD = 'Access-Control-Request-Method'
_CORS_HEADER_REQUEST_HEADERS = 'Access-Control-Request-Headers'
_CORS_HEADER_ALLOW_ORIGIN = 'Access-Control-Allow-Origin'
_CORS_HEADER_ALLOW_METHODS = 'Access-Control-Allow-Methods'
_CORS_HEADER_ALLOW_HEADERS = 'Access-Control-Allow-Headers'
_CORS_ALLOWED_METHODS = frozenset(('DELETE', 'GET', 'PATCH', 'POST', 'PUT'))


class EndpointsDispatcher(object):
  """Dispatcher that handles requests to the built-in apiserver handlers."""

  _API_EXPLORER_URL = 'https://developers.google.com/apis-explorer/?base='

  def __init__(self, dispatcher, config_manager=None):
    """Constructor for EndpointsDispatcher.

    Args:
      dispatcher: A Dispatcher instance that can be used to make HTTP requests.
      config_manager: An ApiConfigManager instance that allows a caller to
        set up an existing configuration for testing.
    """
    self._dispatcher = dispatcher
    if config_manager is None:
      config_manager = api_config_manager.ApiConfigManager()
    self.config_manager = config_manager
    self._dispatchers = []
    self._add_dispatcher('/_ah/api/explorer/?$',
                         self.handle_api_explorer_request)
    self._add_dispatcher('/_ah/api/static/.*$',
                         self.handle_api_static_request)

  def _add_dispatcher(self, path_regex, dispatch_function):
    """Add a request path and dispatch handler.

    Args:
      path_regex: A string regex, the path to match against incoming requests.
      dispatch_function: The function to call for these requests.  The function
        should take (request, start_response) as arguments and
        return the contents of the response body.
    """
    self._dispatchers.append((re.compile(path_regex), dispatch_function))

  def __call__(self, environ, start_response):
    """Handle an incoming request.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function used to begin the response to the caller.
        This follows the semantics defined in PEP-333.  In particular, it's
        called with (status, response_headers, exc_info=None), and it returns
        an object with a write(body_data) function that can be used to write
        the body of the response.

    Yields:
      An iterable over strings containing the body of the HTTP response.
    """
    request = api_request.ApiRequest(environ)

    # PEP-333 requires that we return an iterator that iterates over the
    # response body.  Yielding the returned body accomplishes this.
    yield self.dispatch(request, start_response)

  def dispatch(self, request, start_response):
    """Handles dispatch to apiserver handlers.

    This typically ends up calling start_response and returning the entire
      body of the response.

    Args:
      request: An ApiRequest, the request from the user.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      A string, the body of the response.
    """
    # Check if this matches any of our special handlers.
    dispatched_response = self.dispatch_non_api_requests(request,
                                                         start_response)
    if dispatched_response is not None:
      return dispatched_response

    # Get API configuration first.  We need this so we know how to
    # call the back end.
    api_config_response = self.get_api_configs()
    if not self.handle_get_api_configs_response(api_config_response):
      return self.fail_request(request, 'BackendService.getApiConfigs Error',
                               start_response)

    # Call the service.
    return self.call_spi(request, start_response)

  def dispatch_non_api_requests(self, request, start_response):
    """Dispatch this request if this is a request to a reserved URL.

    If the request matches one of our reserved URLs, this calls
    start_response and returns the response body.

    Args:
      request: An ApiRequest, the request from the user.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      None if the request doesn't match one of the reserved URLs this
      handles.  Otherwise, returns the response body.
    """
    for path_regex, dispatch_function in self._dispatchers:
      if path_regex.match(request.relative_url):
        return dispatch_function(request, start_response)
    return None

  def handle_api_explorer_request(self, request, start_response):
    """Handler for requests to _ah/api/explorer.

    This calls start_response and returns the response body.

    Args:
      request: An ApiRequest, the request from the user.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      A string containing the response body (which is empty, in this case).
    """
    base_url = 'http://%s:%s/_ah/api' % (request.server, request.port)
    redirect_url = self._API_EXPLORER_URL + base_url
    return util.send_wsgi_redirect_response(redirect_url, start_response)

  def handle_api_static_request(self, request, start_response):
    """Handler for requests to _ah/api/static/.*.

    This calls start_response and returns the response body.

    Args:
      request: An ApiRequest, the request from the user.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      A string containing the response body.
    """
    discovery_api = discovery_api_proxy.DiscoveryApiProxy()
    response, body = discovery_api.get_static_file(request.relative_url)
    status_string = '%d %s' % (response.status, response.reason)
    if response.status == 200:
      # Some of the headers that come back from the server can't be passed
      # along in our response.  Specifically, the response from the server has
      # transfer-encoding: chunked, which doesn't apply to the response that
      # we're forwarding.  There may be other problematic headers, so we strip
      # off everything but Content-Type.
      return util.send_wsgi_response(status_string,
                                     [('Content-Type',
                                       response.getheader('Content-Type'))],
                                     body, start_response)
    else:
      logging.error('Discovery API proxy failed on %s with %d. Details: %s',
                    request.relative_url, response.status, body)
      return util.send_wsgi_response(status_string, response.getheaders(), body,
                                     start_response)

  def get_api_configs(self):
    """Makes a call to the BackendService.getApiConfigs endpoint.

    Returns:
      A ResponseTuple containing the response information from the HTTP
      request.
    """
    headers = [('Content-Type', 'application/json')]
    request_body = '{}'
    response = self._dispatcher.add_request(
        'POST', '/_ah/spi/BackendService.getApiConfigs',
        headers, request_body, _SERVER_SOURCE_IP)
    return response

  @staticmethod
  def verify_response(response, status_code, content_type=None):
    """Verifies that a response has the expected status and content type.

    Args:
      response: The ResponseTuple to be checked.
      status_code: An int, the HTTP status code to be compared with response
        status.
      content_type: A string with the acceptable Content-Type header value.
        None allows any content type.

    Returns:
      True if both status_code and content_type match, else False.
    """
    status = int(response.status.split(' ', 1)[0])
    if status != status_code:
      return False
    if content_type is None:
      return True
    for header, value in response.headers:
      if header.lower() == 'content-type':
        return value == content_type
    else:
      return False

  def handle_get_api_configs_response(self, api_config_response):
    """Parses the result of GetApiConfigs and stores its information.

    Args:
      api_config_response: The ResponseTuple from the GetApiConfigs call.

    Returns:
      True on success, False on failure
    """
    if self.verify_response(api_config_response, 200, 'application/json'):
      self.config_manager.parse_api_config_response(
          api_config_response.content)
      return True
    else:
      return False

  def call_spi(self, orig_request, start_response):
    """Generate SPI call (from earlier-saved request).

    This calls start_response and returns the response body.

    Args:
      orig_request: An ApiRequest, the original request from the user.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      A string containing the response body.
    """
    if orig_request.is_rpc():
      method_config = self.lookup_rpc_method(orig_request)
      params = None
    else:
      method_config, params = self.lookup_rest_method(orig_request)
    if not method_config:
      cors_handler = EndpointsDispatcher.__CheckCorsHeaders(orig_request)
      return util.send_wsgi_not_found_response(start_response,
                                               cors_handler=cors_handler)

    # Prepare the request for the back end.
    spi_request = self.transform_request(orig_request, params, method_config)

    # Check if this SPI call is for the Discovery service.  If so, route
    # it to our Discovery handler.
    discovery = discovery_service.DiscoveryService(self.config_manager)
    discovery_response = discovery.handle_discovery_request(
        spi_request.path, spi_request, start_response)
    if discovery_response:
      return discovery_response

    # Send the request to the user's SPI handlers.
    url = _SPI_ROOT_FORMAT % spi_request.path
    spi_request.headers['Content-Type'] = 'application/json'
    response = self._dispatcher.add_request('POST', url,
                                            spi_request.headers.items(),
                                            spi_request.body,
                                            spi_request.source_ip)
    return self.handle_spi_response(orig_request, spi_request, response,
                                    start_response)

  class __CheckCorsHeaders(object):
    """Track information about CORS headers and our response to them."""

    def __init__(self, request):
      self.allow_cors_request = False
      self.origin = None
      self.cors_request_method = None
      self.cors_request_headers = None

      self.__check_cors_request(request)

    def __check_cors_request(self, request):
      """Check for a CORS request, and see if it gets a CORS response."""
      # Check for incoming CORS headers.
      self.origin = request.headers[_CORS_HEADER_ORIGIN]
      self.cors_request_method = request.headers[_CORS_HEADER_REQUEST_METHOD]
      self.cors_request_headers = request.headers[
          _CORS_HEADER_REQUEST_HEADERS]

      # Check if the request should get a CORS response.
      if (self.origin and
          ((self.cors_request_method is None) or
           (self.cors_request_method.upper() in _CORS_ALLOWED_METHODS))):
        self.allow_cors_request = True

    def update_headers(self, headers_in):
      """Add CORS headers to the response, if needed."""
      if not self.allow_cors_request:
        return

      # Add CORS headers.
      headers = wsgiref.headers.Headers(headers_in)
      headers[_CORS_HEADER_ALLOW_ORIGIN] = self.origin
      headers[_CORS_HEADER_ALLOW_METHODS] = ','.join(tuple(
          _CORS_ALLOWED_METHODS))
      if self.cors_request_headers is not None:
        headers[_CORS_HEADER_ALLOW_HEADERS] = self.cors_request_headers

  def handle_spi_response(self, orig_request, spi_request, response,
                          start_response):
    """Handle SPI response, transforming output as needed.

    This calls start_response and returns the response body.

    Args:
      orig_request: An ApiRequest, the original request from the user.
      spi_request: An ApiRequest, the transformed request that was sent to the
        SPI handler.
      response: A ResponseTuple, the response from the SPI handler.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      A string containing the response body.
    """
    # Verify that the response is json.  If it isn't treat, the body as an
    # error message and wrap it in a json error response.
    for header, value in response.headers:
      if (header.lower() == 'content-type' and
          not value.lower().startswith('application/json')):
        return self.fail_request(orig_request,
                                 'Non-JSON reply: %s' % response.content,
                                 start_response)

    body = response.content
    # Need to check is_rpc() against the original request, because the
    # incoming request here has had its path modified.
    if orig_request.is_rpc():
      body = self.transform_jsonrpc_response(spi_request, body)

    cors_handler = EndpointsDispatcher.__CheckCorsHeaders(orig_request)
    return util.send_wsgi_response(response.status, response.headers, body,
                                   start_response, cors_handler=cors_handler)

  def fail_request(self, orig_request, message, start_response):
    """Write an immediate failure response to outfile, no redirect.

    This calls start_response and returns the error body.

    Args:
      orig_request: An ApiRequest, the original request from the user.
      message: A string containing the error message to be displayed to user.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      A string containing the body of the error response.
    """
    cors_handler = EndpointsDispatcher.__CheckCorsHeaders(orig_request)
    return util.send_wsgi_error_response(message, start_response,
                                         cors_handler=cors_handler)

  def lookup_rest_method(self, orig_request):
    """Looks up and returns rest method for the currently-pending request.

    Args:
      orig_request: An ApiRequest, the original request from the user.

    Returns:
      A tuple of (method descriptor, parameters), or (None, None) if no method
      was found for the current request.
    """
    method_name, method, params = self.config_manager.lookup_rest_method(
        orig_request.path, orig_request.http_method)
    orig_request.method_name = method_name
    return method, params

  def lookup_rpc_method(self, orig_request):
    """Looks up and returns RPC method for the currently-pending request.

    Args:
      orig_request: An ApiRequest, the original request from the user.

    Returns:
      The RPC method descriptor that was found for the current request, or None
      if none was found.
    """
    if not orig_request.body_json:
      return None
    method_name = orig_request.body_json.get('method', '')
    version = orig_request.body_json.get('apiVersion', '')
    orig_request.method_name = method_name
    return self.config_manager.lookup_rpc_method(method_name, version)

  def transform_request(self, orig_request, params, method_config):
    """Transforms orig_request to apiserving request.

    This method uses orig_request to determine the currently-pending request
    and returns a new transformed request ready to send to the SPI.  This
    method accepts a rest-style or RPC-style request.

    Args:
      orig_request: An ApiRequest, the original request from the user.
      params: A dictionary containing path parameters for rest requests, or
        None for an RPC request.
      method_config: A dict, the API config of the method to be called.

    Returns:
      An ApiRequest that's a copy of the current request, modified so it can
      be sent to the SPI.  The path is updated and parts of the body or other
      properties may also be changed.
    """
    if orig_request.is_rpc():
      request = self.transform_jsonrpc_request(orig_request)
    else:
      request = self.transform_rest_request(orig_request, params)
    request.path = method_config.get('rosyMethod', '')
    return request

  def transform_rest_request(self, orig_request, params):
    """Translates a Rest request into an apiserving request.

    This makes a copy of orig_request and transforms it to apiserving
    format (moving request parameters to the body).

    Args:
      orig_request: An ApiRequest, the original request from the user.
      params: A dict with URL path parameters extracted by the config_manager
        lookup.

    Returns:
      A copy of the current request that's been modified so it can be sent
      to the SPI.  The body is updated to include parameters from the
      URL.
    """
    request = orig_request.copy()
    if params:
      request.body_json.update(params)
    if request.parameters:
      request.body_json.update(request.parameters)
    request.body = json.dumps(request.body_json)
    return request

  def transform_jsonrpc_request(self, orig_request):
    """Translates a JsonRpc request/response into apiserving request/response.

    Args:
      orig_request: An ApiRequest, the original request from the user.

    Returns:
      A new request with the request_id updated and params moved to the body.
    """
    request = orig_request.copy()
    request.request_id = request.body_json.get('id')
    request.body_json = request.body_json.get('params', {})
    request.body = json.dumps(request.body_json)
    return request

  def transform_jsonrpc_response(self, spi_request, response_body):
    """Translates a apiserving response to a JsonRpc response.

    Args:
      spi_request: An ApiRequest, the transformed request that was sent to the
        SPI handler.
      response_body: A string containing the backend response to transform
        back to JsonRPC.

    Returns:
      A string with the updated, JsonRPC-formatted request body
    """
    body_json = {'result': json.loads(response_body)}
    if spi_request.request_id is not None:
      body_json['id'] = spi_request.request_id
    if spi_request.is_batch():
      body_json = [body_json]
    return json.dumps(body_json)
