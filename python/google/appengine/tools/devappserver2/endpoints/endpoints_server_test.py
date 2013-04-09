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
"""Unit tests for the endpoints_server module."""



import httplib
import json
import unittest

import google

import mox

from google.appengine.tools.devappserver2 import dispatcher
from google.appengine.tools.devappserver2.endpoints import api_config_manager
from google.appengine.tools.devappserver2.endpoints import api_request
from google.appengine.tools.devappserver2.endpoints import discovery_api_proxy
from google.appengine.tools.devappserver2.endpoints import endpoints_server
from google.appengine.tools.devappserver2.endpoints import test_utils


class JsonMatches(mox.Comparator):
  """A Mox comparator to compare a string of a JSON object to a JSON object."""

  def __init__(self, json_object):
    """Constructor.

    Args:
      json_object: The JSON object to compare against.
    """
    self._json_object = json_object

  def equals(self, json_string):
    """Check if the given object matches our json object.

    This converts json_string from a string to a JSON object, then compares it
    against our json object.

    Args:
      json_string: A string containing a JSON object to be compared against.

    Returns:
      True if the object matches, False if not.
    """
    other_json = json.loads(json_string)
    return self._json_object == other_json

  def __repr__(self):
    return '<JsonMatches %r>' % self._json_object


class DevAppserverEndpointsServerTest(test_utils.TestsWithStartResponse):

  def setUp(self):
    """Set up a dev Endpoints server."""
    super(DevAppserverEndpointsServerTest, self).setUp()
    self.mox = mox.Mox()
    self.config_manager = api_config_manager.ApiConfigManager()
    self.mock_dispatcher = self.mox.CreateMock(dispatcher.Dispatcher)
    self.server = endpoints_server.EndpointsDispatcher(self.mock_dispatcher,
                                                       self.config_manager)

  def tearDown(self):
    self.mox.UnsetStubs()

  def prepare_dispatch(self, config):
    # The Dispatch call will make a call to GetApiConfigs, making a
    # dispatcher request.  Set up that request.
    request_method = 'POST'
    request_path = '/_ah/spi/BackendService.getApiConfigs'
    request_headers = [('Content-Type', 'application/json')]
    request_body = '{}'
    response_body = json.dumps({'items': [config]})
    self.mock_dispatcher.add_request(
        request_method, request_path, request_headers, request_body,
        endpoints_server._SERVER_SOURCE_IP).AndReturn(
            dispatcher.ResponseTuple('200 OK',
                                     [('Content-Type', 'application/json'),
                                      ('Content-Length',
                                       str(len(response_body)))],
                                     response_body))

  def assert_dispatch_to_spi(self, request, config, spi_path,
                             expected_spi_body_json=None):
    """Assert that dispatching a request to the SPI works.

    Mock out the dispatcher.add_request and handle_spi_response, and use these
    to ensure that the correct request is being sent to the back end when
    Dispatch is called.

    Args:
      request: An ApiRequest, the request to dispatch.
      config: A dict containing the API configuration.
      spi_path: A string containing the relative path to the SPI.
      expected_spi_body_json: If not None, this is a JSON object containing
        the mock response sent by the back end.  If None, this will create an
        empty response.
    """
    self.prepare_dispatch(config)

    spi_headers = [('Content-Type', 'application/json')]
    spi_body_json = expected_spi_body_json or {}
    spi_response = dispatcher.ResponseTuple('200 OK', [], 'Test')
    self.mock_dispatcher.add_request(
        'POST', spi_path, spi_headers, JsonMatches(spi_body_json),
        request.source_ip).AndReturn(spi_response)

    self.mox.StubOutWithMock(self.server, 'handle_spi_response')
    self.server.handle_spi_response(
        mox.IsA(api_request.ApiRequest), mox.IsA(api_request.ApiRequest),
        spi_response, self.start_response).AndReturn('Test')

    # Run the test.
    self.mox.ReplayAll()
    response = self.server.dispatch(request, self.start_response)
    self.mox.VerifyAll()

    self.assertEqual('Test', response)

  def test_dispatch_invalid_path(self):
    config = json.dumps({
        'name': 'guestbook_api',
        'version': 'v1',
        'methods': {
            'guestbook.get': {
                'httpMethod': 'GET',
                'path': 'greetings/{gid}',
                'rosyMethod': 'MyApi.greetings_get'
            }
        }
    })
    request = test_utils.build_request('/_ah/api/foo')
    self.prepare_dispatch(config)
    self.mox.ReplayAll()
    response = self.server.dispatch(request, self.start_response)
    self.mox.VerifyAll()

    self.assert_http_match(response, 404,
                           [('Content-Type', 'text/plain'),
                            ('Content-Length', '9')],
                           'Not Found')

  def test_dispatch_json_rpc(self):
    config = json.dumps({
        'name': 'guestbook_api',
        'version': 'X',
        'methods': {
            'foo.bar': {
                'httpMethod': 'GET',
                'path': 'greetings/{gid}',
                'rosyMethod': 'baz.bim'
            }
        }
    })
    request = test_utils.build_request(
        '/_ah/api/rpc',
        '{"method": "foo.bar", "apiVersion": "X"}')
    self.assert_dispatch_to_spi(request, config,
                                '/_ah/spi/baz.bim')

  def test_dispatch_rest(self):
    config = json.dumps({
        'name': 'myapi',
        'version': 'v1',
        'methods': {
            'bar': {
                'httpMethod': 'GET',
                'path': 'foo/{id}',
                'rosyMethod': 'baz.bim'
            }
        }
    })
    request = test_utils.build_request('/_ah/api/myapi/v1/foo/testId')
    self.assert_dispatch_to_spi(request, config,
                                '/_ah/spi/baz.bim',
                                {'id': 'testId'})

  def test_explorer_redirect(self):
    request = test_utils.build_request('/_ah/api/explorer')
    response = self.server.dispatch(request, self.start_response)
    self.assert_http_match(response, 302,
                           [('Content-Length', '0'),
                            ('Location', ('https://developers.google.com/'
                                          'apis-explorer/?base='
                                          'http://localhost:42/_ah/api'))],
                           '')

  def test_static_existing_file(self):
    relative_url = '/_ah/api/static/proxy.html'

    # Set up mocks for the call to DiscoveryApiProxy.get_static_file.
    discovery_api = self.mox.CreateMock(
        discovery_api_proxy.DiscoveryApiProxy)
    self.mox.StubOutWithMock(discovery_api_proxy, 'DiscoveryApiProxy')
    discovery_api_proxy.DiscoveryApiProxy().AndReturn(discovery_api)
    static_response = self.mox.CreateMock(httplib.HTTPResponse)
    static_response.status = 200
    static_response.reason = 'OK'
    static_response.getheader('Content-Type').AndReturn('test/type')
    test_body = 'test body'
    discovery_api.get_static_file(relative_url).AndReturn(
        (static_response, test_body))

    # Make sure the dispatch works as expected.
    request = test_utils.build_request(relative_url)
    self.mox.ReplayAll()
    response = self.server.dispatch(request, self.start_response)
    self.mox.VerifyAll()

    response = ''.join(response)
    self.assert_http_match(response, '200 OK',
                           [('Content-Length', '%d' % len(test_body)),
                            ('Content-Type', 'test/type')],
                           test_body)

  def test_static_non_existing_file(self):
    relative_url = '/_ah/api/static/blah.html'

    # Set up mocks for the call to DiscoveryApiProxy.get_static_file.
    discovery_api = self.mox.CreateMock(
        discovery_api_proxy.DiscoveryApiProxy)
    self.mox.StubOutWithMock(discovery_api_proxy, 'DiscoveryApiProxy')
    discovery_api_proxy.DiscoveryApiProxy().AndReturn(discovery_api)
    static_response = self.mox.CreateMock(httplib.HTTPResponse)
    static_response.status = 404
    static_response.reason = 'Not Found'
    static_response.getheaders().AndReturn([('Content-Type', 'test/type')])
    test_body = 'No Body'
    discovery_api.get_static_file(relative_url).AndReturn(
        (static_response, test_body))

    # Make sure the dispatch works as expected.
    request = test_utils.build_request(relative_url)
    self.mox.ReplayAll()
    response = self.server.dispatch(request, self.start_response)
    self.mox.VerifyAll()

    response = ''.join(response)
    self.assert_http_match(response, '404 Not Found',
                           [('Content-Length', '%d' % len(test_body)),
                            ('Content-Type', 'test/type')],
                           test_body)

  def test_handle_non_json_spi_response(self):
    orig_request = test_utils.build_request('/_ah/api/fake/path')
    spi_request = orig_request.copy()
    spi_response = dispatcher.ResponseTuple(
        200, [('Content-type', 'text/plain')],
        'This is an invalid response.')
    response = self.server.handle_spi_response(orig_request, spi_request,
                                               spi_response,
                                               self.start_response)
    error_json = {'error': {'message':
                            'Non-JSON reply: This is an invalid response.'}}
    body = json.dumps(error_json)
    self.assert_http_match(response, '500',
                           [('Content-Type', 'application/json'),
                            ('Content-Length', '%d' % len(body))],
                           body)

  def test_handle_non_json_spi_response_cors(self):
    """Test that an error response still handles CORS headers."""
    server_response = dispatcher.ResponseTuple(
        '200 OK', [('Content-type', 'text/plain')],
        'This is an invalid response.')
    response = self.check_cors([('origin', 'test.com')], True, 'test.com',
                               server_response=server_response)
    self.assertEqual(
        {'error': {'message': 'Non-JSON reply: This is an invalid response.'}},
        json.loads(response))

  def check_cors(self, request_headers, expect_response, expected_origin=None,
                 expected_allow_headers=None, server_response=None):
    """Check that CORS headers are handled correctly.

    Args:
      request_headers: A list of (header, value), to be used as headers in the
        request.
      expect_response: A boolean, whether or not CORS headers are expected in
        the response.
      expected_origin: A string or None.  If this is a string, this is the value
        that's expected in the response's allow origin header.  This can be
        None if expect_response is False.
      expected_allow_headers: A string or None.  If this is a string, this is
        the value that's expected in the response's allow headers header.  If
        this is None, then the response shouldn't have any allow headers
        headers.
      server_response: A dispatcher.ResponseTuple or None.  The backend's
        response, to be wrapped and returned as the server's response.  If
        this is None, a generic response will be generated.

    Returns:
      A string containing the body of the response that would be sent.
    """
    orig_request = test_utils.build_request('/_ah/api/fake/path',
                                            http_headers=request_headers)
    spi_request = orig_request.copy()

    if server_response is None:
      server_response = dispatcher.ResponseTuple(
          '200 OK', [('Content-type', 'application/json')], '{}')

    response = self.server.handle_spi_response(orig_request, spi_request,
                                               server_response,
                                               self.start_response)

    headers = dict(self.response_headers)
    if expect_response:
      self.assertIn(endpoints_server._CORS_HEADER_ALLOW_ORIGIN, headers)
      self.assertEqual(
          headers[endpoints_server._CORS_HEADER_ALLOW_ORIGIN],
          expected_origin)

      self.assertIn(endpoints_server._CORS_HEADER_ALLOW_METHODS, headers)
      self.assertEqual(set(headers[
          endpoints_server._CORS_HEADER_ALLOW_METHODS].split(',')),
                       endpoints_server._CORS_ALLOWED_METHODS)

      if expected_allow_headers is not None:
        self.assertIn(endpoints_server._CORS_HEADER_ALLOW_HEADERS,
                      headers)
        self.assertEqual(
            headers[endpoints_server._CORS_HEADER_ALLOW_HEADERS],
            expected_allow_headers)
      else:
        self.assertNotIn(endpoints_server._CORS_HEADER_ALLOW_HEADERS,
                         headers)
    else:
      self.assertNotIn(endpoints_server._CORS_HEADER_ALLOW_ORIGIN,
                       headers)
      self.assertNotIn(endpoints_server._CORS_HEADER_ALLOW_METHODS,
                       headers)
      self.assertNotIn(endpoints_server._CORS_HEADER_ALLOW_HEADERS,
                       headers)
    return ''.join(response)

  def test_handle_cors(self):
    """Test CORS support on a regular request."""
    self.check_cors([('origin', 'test.com')], True, 'test.com')

  def test_handle_cors_preflight(self):
    """Test a CORS preflight request."""
    self.check_cors([('origin', 'http://example.com'),
                     ('Access-control-request-method', 'GET')], True,
                    'http://example.com')

  def test_handle_cors_preflight_invalid(self):
    """Test a CORS preflight request for an unaccepted OPTIONS request."""
    self.check_cors([('origin', 'http://example.com'),
                     ('Access-control-request-method', 'OPTIONS')], False)

  def test_handle_cors_preflight_request_headers(self):
    """Test a CORS preflight request."""
    self.check_cors([('origin', 'http://example.com'),
                     ('Access-control-request-method', 'GET'),
                     ('Access-Control-Request-Headers', 'Date,Expires')], True,
                    'http://example.com', 'Date,Expires')

  def test_lily_uses_python_method_name(self):
    """Verify Lily protocol correctly uses python method name.

    This test verifies the fix to http://b/7189819
    """
    config = json.dumps({
        'name': 'guestbook_api',
        'version': 'X',
        'methods': {
            'author.greeting.info.get': {
                'httpMethod': 'GET',
                'path': 'authors/{aid}/greetings/{gid}/infos/{iid}',
                'rosyMethod': 'InfoService.get'
            }
        }
    })
    request = test_utils.build_request(
        '/_ah/api/rpc',
        '{"method": "author.greeting.info.get", "apiVersion": "X"}')
    self.assert_dispatch_to_spi(request, config,
                                '/_ah/spi/InfoService.get',
                                {})

  def test_handle_spi_response_json_rpc(self):
    """Verify headers transformed, JsonRpc response transformed, written."""
    orig_request = test_utils.build_request(
        '/_ah/api/rpc', '{"method": "foo.bar", "apiVersion": "X"}')
    self.assertTrue(orig_request.is_rpc())
    orig_request.request_id = 'Z'
    spi_request = orig_request.copy()
    spi_response = dispatcher.ResponseTuple('200 OK', [('a', 'b')],
                                            '{"some": "response"}')

    response = self.server.handle_spi_response(orig_request, spi_request,
                                               spi_response,
                                               self.start_response)
    response = ''.join(response)  # Merge response iterator into single body.

    self.assertEqual(self.response_status, '200 OK')
    self.assertIn(('a', 'b'), self.response_headers)
    self.assertEqual({'id': 'Z', 'result': {'some': 'response'}},
                     json.loads(response))

  def test_handle_spi_response_batch_json_rpc(self):
    """Verify that batch requests have an appropriate batch response."""
    orig_request = test_utils.build_request(
        '/_ah/api/rpc', '[{"method": "foo.bar", "apiVersion": "X"}]')
    self.assertTrue(orig_request.is_batch())
    self.assertTrue(orig_request.is_rpc())
    orig_request.request_id = 'Z'
    spi_request = orig_request.copy()
    spi_response = dispatcher.ResponseTuple('200 OK', [('a', 'b')],
                                            '{"some": "response"}')

    response = self.server.handle_spi_response(orig_request, spi_request,
                                               spi_response,
                                               self.start_response)
    response = ''.join(response)  # Merge response iterator into single body.

    self.assertEqual(self.response_status, '200 OK')
    self.assertIn(('a', 'b'), self.response_headers)
    self.assertEqual([{'id': 'Z', 'result': {'some': 'response'}}],
                     json.loads(response))

  def test_handle_spi_response_rest(self):
    orig_request = test_utils.build_request('/_ah/api/test', '{}')
    spi_request = orig_request.copy()
    body = json.dumps({'some': 'response'}, indent=1)
    spi_response = dispatcher.ResponseTuple('200 OK', [('a', 'b')], body)
    response = self.server.handle_spi_response(orig_request, spi_request,
                                               spi_response,
                                               self.start_response)
    self.assert_http_match(response, '200 OK',
                           [('a', 'b'),
                            ('Content-Length', '%d' % len(body))],
                           body)

  def test_transform_rest_request(self):
    """Verify body is updated with path params."""
    orig_request = test_utils.build_request('/_ah/api/test',
                                            '{"sample": "body"}')
    new_request = self.server.transform_rest_request(orig_request, {'gid': 'X'})
    self.assertEqual({'sample': 'body', 'gid': 'X'},
                     json.loads(new_request.body))

  def test_transform_rest_request_with_query_params(self):
    """Verify body is updated with query parameters."""
    orig_request = test_utils.build_request('/_ah/api/test?foo=bar',
                                            '{"sample": "body"}')
    new_request = self.server.transform_rest_request(orig_request, {})
    self.assertEqual({'sample': 'body', 'foo': ['bar']},
                     json.loads(new_request.body))

  def test_transform_request(self):
    """Verify path is method name and Content length is updated."""
    request = test_utils.build_request('/_ah/api/test/{gid}',
                                       '{"sample": "body"}')
    method_config = {'rosyMethod': 'GuestbookApi.greetings_get'}

    new_request = self.server.transform_request(request, {'gid': 'X'},
                                                method_config)
    self.assertEqual({'sample': 'body', 'gid': 'X'},
                     json.loads(new_request.body))
    self.assertEqual('GuestbookApi.greetings_get', new_request.path)

  def test_transform_json_rpc_request(self):
    """Verify request_id is extracted and body is scoped to body.params."""
    orig_request = test_utils.build_request(
        '/_ah/api/rpc', '{"params": {"sample": "body"}, "id": "42"}')

    new_request = self.server.transform_jsonrpc_request(orig_request)
    self.assertEqual({'sample': 'body'},
                     json.loads(new_request.body))
    self.assertEqual('42', new_request.request_id)

  def test_transform_rest_response(self):
    """Verify the response is reformatted correctly."""
    orig_response = '{"sample": "test", "value1": {"value2": 2}}'
    expected_response = ('{\n'
                         ' "sample": "test", \n'
                         ' "value1": {\n'
                         '  "value2": 2\n'
                         ' }\n'
                         '}')
    self.assertEqual(expected_response,
                     self.server.transform_rest_response(orig_response))

  def test_transform_json_rpc_response(self):
    """Verify request_id inserted into the body, and body into body.result."""
    orig_request = test_utils.build_request(
        '/_ah/api/rpc', '{"params": {"sample": "body"}, "id": "42"}')
    request = orig_request.copy()
    request.request_id = '42'
    response = self.server.transform_jsonrpc_response(request,
                                                      '{"sample": "body"}')
    self.assertEqual({'result': {'sample': 'body'}, 'id': '42'},
                     json.loads(response))

  def test_transform_json_rpc_response_batch(self):
    """Verify request_id inserted into the body, and body into body.result."""
    orig_request = test_utils.build_request(
        '/_ah/api/rpc', '[{"params": {"sample": "body"}, "id": "42"}]')
    request = orig_request.copy()
    request.request_id = '42'
    response = self.server.transform_jsonrpc_response(request,
                                                      '{"sample": "body"}')
    self.assertEqual([{'result': {'sample': 'body'}, 'id': '42'}],
                     json.loads(response))

  def test_lookup_rpc_method_no_body(self):
    orig_request = test_utils.build_request('/_ah/api/rpc', '')
    self.assertEqual(None, self.server.lookup_rpc_method(orig_request))

  def test_lookup_rpc_method(self):
    self.mox.StubOutWithMock(self.server.config_manager, 'lookup_rpc_method')
    self.server.config_manager.lookup_rpc_method('foo', 'v1').AndReturn('bar')

    self.mox.ReplayAll()
    orig_request = test_utils.build_request(
        '/_ah/api/rpc', '{"method": "foo", "apiVersion": "v1"}')
    self.assertEqual('bar', self.server.lookup_rpc_method(orig_request))
    self.mox.VerifyAll()

  def test_verify_response(self):
    response = dispatcher.ResponseTuple('200', [('Content-Type', 'a')], '')
    # Expected response
    self.assertEqual(True, self.server.verify_response(response, 200, 'a'))
    # Any content type accepted
    self.assertEqual(True, self.server.verify_response(response, 200, None))
    # Status code mismatch
    self.assertEqual(False, self.server.verify_response(response, 400, 'a'))
    # Content type mismatch
    self.assertEqual(False, self.server.verify_response(response, 200, 'b'))

    response = dispatcher.ResponseTuple('200', [('Content-Length', '10')], '')
    # Any content type accepted
    self.assertEqual(True, self.server.verify_response(response, 200, None))
    # Specified content type not matched
    self.assertEqual(False, self.server.verify_response(response, 200, 'a'))

if __name__ == '__main__':
  unittest.main()
