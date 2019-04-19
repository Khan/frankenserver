from __future__ import absolute_import

import cStringIO
import json
import os
import wsgiref.util

from google.appengine.tools.devappserver2.datastore_translator import (
  datastore_translator_server)
from google.appengine.tools.devappserver2 import wsgi_test_utils
from google.appengine.tools.devappserver2 import stub_util


class DatastoreTranslatorHandlerTestBase(wsgi_test_utils.WSGITestCase):
  maxDiff = None

  def setUp(self):
    self.app_id = 'dev~myapp'
    # TODO(benkraft): Clean this environ setting up at end-of-test.
    # (Many of the devappserver tests don't do this, so it can't be that
    # important.)
    os.environ['APPLICATION_ID'] = self.app_id
    stub_util.setup_test_stubs(app_id=self.app_id)
    self.server = datastore_translator_server.get_app('localhost')

  def getJsonResponse(self, relative_url, json_request, expected_status):
    # Build the fake request (partially cribbed from api_server_test.py).
    request_body = json.dumps(json_request)
    request_environ = {
      'HTTP_HOST': 'localhost:8001',
      'PATH_INFO': relative_url,
      'REQUEST_METHOD': 'POST',
      'CONTENT_TYPE': 'application/json',
      'CONTENT_LENGTH': str(len(request_body)),
      'wsgi.input': cStringIO.StringIO(request_body),
    }
    wsgiref.util.setup_testing_defaults(request_environ)

    # Set up the WSGI response callable.
    # cribbed from wsgi_test_utils.py, but modified to allow us to assert about
    # the *parsed* json:
    write_buffer = cStringIO.StringIO()
    actual_start_response_args = []

    def start_response(status, headers, exc_info=None):
      actual_start_response_args.extend((status, headers, exc_info))
      return write_buffer.write

    # Run the request.
    response = self.server(request_environ, start_response)

    # Assert that we got a response and it looks as expected.
    self.assertTrue(actual_start_response_args,
                    "start_response never called!")
    self.assertEqual(len(actual_start_response_args), 3,
                     "start_response called multiple times!")

    actual_status, actual_headers, actual_exc_info = actual_start_response_args
    actual_status_int = int(actual_status.split()[0])
    response_body = ''.join(response)

    self.assertEqual(expected_status, actual_status_int,
                     "Expected status %s, got status %s for response %s"
                     % (expected_status, actual_status_int, response_body))
    self.assertIsNone(actual_exc_info)

    try:
      return json.loads(response_body)
    except Exception:
      print response_body
      raise

  def assertOK(self, relative_url, json_request, expected_json_response):
    actual_response = self.getJsonResponse(relative_url, json_request, 200)
    self.assertEqual(actual_response, expected_json_response)

  def assertError(self, relative_url, json_request,
                  expected_http_status, expected_grpc_status):
    actual_response = self.getJsonResponse(relative_url, json_request,
                                           expected_http_status)
    # We deliberately don't assert about the message, since that seems likely
    # to be fragile.
    self.assertIn('error', actual_response)
    self.assertEqual(actual_response['error']['code'], expected_http_status)
    self.assertEqual(actual_response['error']['status'], expected_grpc_status)


class TestAllocateIds(DatastoreTranslatorHandlerTestBase):
  def test_success_simple_key(self):
    self.assertOK(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{
        'path': [{'kind': 'Foo'}]
      }]},
      {'keys': [{
        'partitionId': {'projectId': 'myapp'},
        # Conveniently (here and below), the sqlite stub seems to be totally
        # deterministic as to which ID it allocates us (namely 1).
        'path': [{'kind': 'Foo', 'id': '1'}]
      }]})

  def test_success_with_ancestors(self):
    self.assertOK(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{
        'path': [
          {'kind': 'Foo', 'id': '5629499534213120'},
          {'kind': 'Bar', 'name': 'asdfgh1234'},
          {'kind': 'Baz'},
        ],
      }]},
      {'keys': [{
        'partitionId': {'projectId': 'myapp'},
        'path': [
          {'kind': 'Foo', 'id': '5629499534213120'},
          {'kind': 'Bar', 'name': 'asdfgh1234'},
          {'kind': 'Baz', 'id': '1'},
        ],
      }]})

  def test_success_with_namespace(self):
    self.assertOK(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{
        'partitionId': {
          'projectId': 'myapp',
          'namespaceId': 'the-namespace',
        },
        'path': [{'kind': 'Foo'}],
      }]},
      {'keys': [{
        'partitionId': {
          'projectId': 'myapp',
          'namespaceId': 'the-namespace',
        },
        'path': [{'kind': 'Foo', 'id': '1'}]
      }]})

  def test_empty_success(self):
    self.assertOK(
      '/v1/projects/myapp:allocateIds',
      {},
      {})
    self.assertOK(
      '/v1/projects/myapp:allocateIds',
      {'keys': []},
      {})

  # TODO(benkraft): Split some of these tests out to a translate_key_test.py.
  def test_no_kind(self):
    self.assertError(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{'path': [{}]}]},
      400, 'INVALID_ARGUMENT')

  def test_path_with_incomplete_key(self):
    self.assertError(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{
        'path': [
          {'kind': 'Foo'},
          {'kind': 'Bar', 'name': 'asdfgh1234'},
          {'kind': 'Baz'},
        ],
      }]},
      400, 'INVALID_ARGUMENT')

  def test_path_with_both_name_and_id(self):
    self.assertError(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{
        'path': [
          {'kind': 'Foo', 'name': 'asdf', 'id': '123'},
          {'kind': 'Baz'},
        ],
      }]},
      400, 'INVALID_ARGUMENT')

  def test_path_ending_with_complete_key(self):
    self.assertError(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{
        'path': [{'kind': 'Foo', 'id': '123'}],
      }]},
      400, 'INVALID_ARGUMENT')
    self.assertError(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{
        'path': [{'kind': 'Foo', 'name': 'asdf'}],
      }]},
      400, 'INVALID_ARGUMENT')

  def test_mismatched_project(self):
    self.assertError(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{
        'partitionId': {'projectId': 'yourapp'},
        'path': [{'kind': 'Foo'}],
      }]},
      400, 'INVALID_ARGUMENT')

  def test_matched_but_wrong_project(self):
    self.assertError(
      '/v1/projects/yourapp:allocateIds',
      {'keys': [{
        'partitionId': {'projectId': 'yourapp'},
        'path': [{'kind': 'Foo'}],
      }]},
      400, 'INVALID_ARGUMENT')
