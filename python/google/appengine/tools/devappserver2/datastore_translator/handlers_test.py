from __future__ import absolute_import

import cStringIO
import json
import wsgiref.util

from google.appengine.ext import db
from google.appengine.tools.devappserver2 import wsgi_test_utils
from google.appengine.tools.devappserver2.datastore_translator import (
  datastore_translator_server)
from google.appengine.tools.devappserver2.datastore_translator import testbase


class DatastoreTranslatorHandlerTestBase(testbase.DatastoreTranslatorTestBase,
                                         wsgi_test_utils.WSGITestCase):
  def setUp(self):
    super(DatastoreTranslatorHandlerTestBase, self).setUp()
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

  def test_success_several_keys(self):
    self.assertOK(
      '/v1/projects/myapp:allocateIds',
      {'keys': [
        {'path': [{'kind': 'Foo'}]},
        {'path': [{'kind': 'Foo'}]},
        {'path': [{'kind': 'Foo'}]},
        {'path': [{'kind': 'Foo'}]},
        {'path': [{'kind': 'Bar'}]},
      ]},
      {'keys': [
        {
          'partitionId': {'projectId': 'myapp'},
          'path': [{'kind': 'Foo', 'id': '1'}]
        },
        {
          'partitionId': {'projectId': 'myapp'},
          'path': [{'kind': 'Foo', 'id': '2'}]
        },
        {
          'partitionId': {'projectId': 'myapp'},
          'path': [{'kind': 'Foo', 'id': '3'}]
        },
        {
          'partitionId': {'projectId': 'myapp'},
          'path': [{'kind': 'Foo', 'id': '4'}]
        },
        {
          'partitionId': {'projectId': 'myapp'},
          # Again, this is arbitrary but deterministic.
          'path': [{'kind': 'Bar', 'id': '5'}]
        },
      ]})

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

  def test_no_kind(self):
    self.assertError(
      '/v1/projects/myapp:allocateIds',
      {'keys': [{'path': [{}]}]},
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


class SimpleModel(db.Model):
  boolean = db.BooleanProperty(indexed=True)
  integer = db.IntegerProperty(indexed=True)
  unindexed_string = db.StringProperty(indexed=False)
  blob = db.BlobProperty(indexed=False)


class TestLookup(DatastoreTranslatorHandlerTestBase):
  def setUp(self):
    super(TestLookup, self).setUp()

    SimpleModel(
      key_name='exists',
      boolean=True,
      integer=12,
      unindexed_string=u'\u1111',
      blob='\x80',
    ).put()

    SimpleModel(
      parent=db.Key.from_path('ParentModel', 1),
      key_name='child',
      boolean=False,
      integer=16,
      unindexed_string=u'\u2222',
      blob='\x80',
    ).put()

  def test_success_simple_key(self):
    self.assertOK(
      '/v1/projects/myapp:lookup',
      {'keys': [{'path': [{'kind': 'SimpleModel', 'name': 'exists'}]}]},

      {
        'found': [{
          'entity': {
            'key': {
              'partitionId': {'projectId': 'myapp'},
              'path': [{'kind': 'SimpleModel', 'name': 'exists'}],
            },
            'properties': {
              'blob': {
                'blobValue': 'gA==',
                'excludeFromIndexes': True,
                'meaning': 14,
              },
              'boolean': {'booleanValue': True},
              'integer': {'integerValue': '12'},
              'unindexed_string': {
                'excludeFromIndexes': True,
                'stringValue': u'\u1111',
              },
            },
          },
          'version': '1',
        }],
      })

  def test_missing(self):
    self.assertOK(
      '/v1/projects/myapp:lookup',
      {'keys': [{'path': [{'kind': 'SimpleModel', 'name': 'nope'}]}]},

      {
        'missing': [{
          'entity': {
            'key': {
              'partitionId': {'projectId': 'myapp'},
              'path': [{'kind': 'SimpleModel', 'name': 'nope'}],
            },
          },
          'version': '1',
        }],
      })

  def test_several_keys(self):
    self.assertOK(
      '/v1/projects/myapp:lookup',
      {'keys': [
        {'path': [{'kind': 'SimpleModel', 'name': 'exists'}]},
        {'path': [{'kind': 'SimpleModel', 'name': 'nope'}]},
        {'path': [
          {'kind': 'ParentModel', 'id': '1'},
          {'kind': 'SimpleModel', 'name': 'child'},
        ]},
      ]},

      {
        'found': [{
          'entity': {
            'key': {
              'partitionId': {'projectId': 'myapp'},
              'path': [{'kind': 'SimpleModel', 'name': 'exists'}],
            },
            'properties': {
              'blob': {
                'blobValue': 'gA==',
                'excludeFromIndexes': True,
                'meaning': 14,
              },
              'boolean': {'booleanValue': True},
              'integer': {'integerValue': '12'},
              'unindexed_string': {
                'excludeFromIndexes': True,
                'stringValue': u'\u1111',
              },
            },
          },
          'version': '1',
        }, {
          'entity': {
            'key': {
              'partitionId': {'projectId': 'myapp'},
              'path': [
                {'kind': 'ParentModel', 'id': '1'},
                {'kind': 'SimpleModel', 'name': 'child'},
              ],
            },
            'properties': {
              'blob': {
                'blobValue': 'gA==',
                'excludeFromIndexes': True,
                'meaning': 14,
              },
              'boolean': {'booleanValue': False},
              'integer': {'integerValue': '16'},
              'unindexed_string': {
                'excludeFromIndexes': True,
                'stringValue': u'\u2222',
              },
            },
          },
          'version': '1',
        }],
        'missing': [{
          'entity': {
            'key': {
              'partitionId': {'projectId': 'myapp'},
              'path': [{'kind': 'SimpleModel', 'name': 'nope'}],
            },
          },
          'version': '1',
        }],
      })

  def test_empty_success(self):
    self.assertOK(
      '/v1/projects/myapp:lookup',
      {},
      {})
    self.assertOK(
      '/v1/projects/myapp:lookup',
      {'keys': []},
      {})




