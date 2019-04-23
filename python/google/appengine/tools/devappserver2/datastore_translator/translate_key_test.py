from __future__ import absolute_import

from google.appengine.api import datastore
from google.appengine.tools.devappserver2.datastore_translator import testbase
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_key)


class RestToGaeTest(testbase.DatastoreTranslatorTestBase):
  def test_simple_key(self):
    self.assertEqual(
      translate_key.rest_to_gae(
        {'path': [{'kind': 'Foo', 'id': '17'}]},
        self.app_id),
      datastore.Key.from_path('Foo', 17))

  def test_large_id(self):
    self.assertEqual(
      translate_key.rest_to_gae(
        {'path': [{'kind': 'Foo', 'id': '5629499534213120'}]},
        self.app_id),
      datastore.Key.from_path('Foo', 5629499534213120))

  def test_simple_key_with_name(self):
    self.assertEqual(
      translate_key.rest_to_gae(
        {'path': [{'kind': 'Foo', 'name': 'x17'}]},
        self.app_id),
      datastore.Key.from_path('Foo', 'x17'))

  def test_simple_key_with_integer_like_name(self):
    self.assertEqual(
      translate_key.rest_to_gae(
        {'path': [{'kind': 'Foo', 'name': '17'}]},
        self.app_id),
      datastore.Key.from_path('Foo', '17'))

  def test_simple_incomplete_key(self):
    self.assertEqual(
      translate_key.rest_to_gae(
        {'path': [{'kind': 'Foo'}]},
        self.app_id,
        incomplete=True),
      datastore.Key.from_path('Foo', 1))

  def test_key_with_ancestors(self):
    self.assertEqual(
      translate_key.rest_to_gae(
        {'path': [
          {'kind': 'Foo', 'id': '5629499534213120'},
          {'kind': 'Bar', 'name': 'asdfgh1234'},
          {'kind': 'Baz', 'id': '1'},
        ]},
        self.app_id),
      datastore.Key.from_path(
        'Foo', 5629499534213120,
        'Bar', 'asdfgh1234',
        'Baz', 1))

  def test_incomplete_key_with_ancestors(self):
    self.assertEqual(
      translate_key.rest_to_gae(
        {'path': [
          {'kind': 'Foo', 'id': '5629499534213120'},
          {'kind': 'Bar', 'name': 'asdfgh1234'},
          {'kind': 'Baz'},
        ]},
        self.app_id,
        incomplete=True),
      datastore.Key.from_path(
        'Foo', 5629499534213120,
        'Bar', 'asdfgh1234',
        'Baz', 1))

  def test_key_with_project(self):
    # Note: we allow either dev~myapp or myapp, but you have to be consistent!
    self.assertEqual(
      translate_key.rest_to_gae({
        'partitionId': {'projectId': 'myapp'},
        'path': [{'kind': 'Foo', 'id': '1'}]
      }, 'myapp'),
      datastore.Key.from_path('Foo', 1))

  def test_key_with_dev_project(self):
    self.assertEqual(
      translate_key.rest_to_gae({
        'partitionId': {'projectId': 'dev~myapp'},
        'path': [{'kind': 'Foo', 'id': '1'}]
      }, 'dev~myapp'),
      datastore.Key.from_path('Foo', 1))

  def test_key_with_namespace(self):
    self.assertEqual(
      translate_key.rest_to_gae({
        'partitionId': {
          'projectId': self.app_id,
          'namespaceId': 'the-namespace',
        },
        'path': [{'kind': 'Foo', 'id': '1'}]
      }, self.app_id),
      datastore.Key.from_path('Foo', 1, namespace='the-namespace'))

  def test_invalid_key_no_kind(self):
    with self.assertRaises(KeyError):    # handlers.py translates this
      translate_key.rest_to_gae({'path': [{}]}, self.app_id)

  def test_invalid_key_non_integer_id(self):
    with self.assertRaises(ValueError):  # handlers.py translates this
      translate_key.rest_to_gae(
        {'path': [{'kind': 'Foo', 'id': 'asdf'}]},
        self.app_id)

  def test_invalid_key_path_item_incomplete(self):
    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      translate_key.rest_to_gae(
        {'path': [
          {'kind': 'Foo'},
          {'kind': 'Bar', 'name': 'asdfgh1234'},
          {'kind': 'Baz'},
        ]},
        self.app_id,
        incomplete=True),

  def test_invalid_key_both_name_and_id(self):
    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      translate_key.rest_to_gae(
        {'path': [{'kind': 'Foo', 'id': '1234', 'name': 'asdfgh1234'}]},
        self.app_id)

  def test_invalid_key_both_name_and_id_in_path(self):
    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      translate_key.rest_to_gae(
        {'path': [
          {'kind': 'Foo', 'id': '1234', 'name': 'asdfgh1234'},
          {'kind': 'Baz'},
        ]},
        self.app_id,
        incomplete=True)

  def test_invalid_key_incomplete(self):
    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      translate_key.rest_to_gae(
        {'path': [
          {'kind': 'Foo', 'id': '1234'},
          {'kind': 'Baz'},
        ]},
        self.app_id)

  def test_invalid_incomplete_key_with_id(self):
    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      translate_key.rest_to_gae(
        {'path': [
          {'kind': 'Foo', 'id': '1234'},
          {'kind': 'Baz', 'id': '1234'},
        ]},
        self.app_id,
        incomplete=True)

  def test_invalid_incomplete_key_with_name(self):
    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      translate_key.rest_to_gae(
        {'path': [
          {'kind': 'Foo', 'id': '1234'},
          {'kind': 'Baz', 'name': 'asdf'},
        ]},
        self.app_id,
        incomplete=True)

  def test_invalid_key_with_mismatched_project(self):
    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      translate_key.rest_to_gae({
        'partitionId': {'projectId': 'yourapp'},
        'path': [{'kind': 'Foo', 'id': '1'}]
      }, 'myapp'),
      datastore.Key.from_path('Foo', 1)


class GaeToRestTest(testbase.DatastoreTranslatorTestBase):
  def test_simple_key(self):
    self.assertEqual(
      translate_key.gae_to_rest(datastore.Key.from_path('Foo', 17)),
      {
        'partitionId': {'projectId': 'myapp'},
        'path': [{'kind': 'Foo', 'id': '17'}],
      })

  def test_large_id(self):
    self.assertEqual(
      translate_key.gae_to_rest(
        datastore.Key.from_path('Foo', 5629499534213120)),
      {
        'partitionId': {'projectId': 'myapp'},
        'path': [{'kind': 'Foo', 'id': '5629499534213120'}],
      })

  def test_simple_key_with_name(self):
    self.assertEqual(
      translate_key.gae_to_rest(datastore.Key.from_path('Foo', 'x17')),
      {
        'partitionId': {'projectId': 'myapp'},
        'path': [{'kind': 'Foo', 'name': 'x17'}],
      })

  def test_simple_key_with_integer_like_name(self):
    self.assertEqual(
      translate_key.gae_to_rest(datastore.Key.from_path('Foo', '17')),
      {
        'partitionId': {'projectId': 'myapp'},
        'path': [{'kind': 'Foo', 'name': '17'}],
      })

  def test_key_with_ancestors(self):
    self.assertEqual(
      translate_key.gae_to_rest(datastore.Key.from_path(
        'Foo', 5629499534213120,
        'Bar', 'asdfgh1234',
        'Baz', 1)),
      {
        'partitionId': {'projectId': 'myapp'},
        'path': [
          {'kind': 'Foo', 'id': '5629499534213120'},
          {'kind': 'Bar', 'name': 'asdfgh1234'},
          {'kind': 'Baz', 'id': '1'},
        ],
      })

  def test_key_with_namespace(self):
    self.assertEqual(
      translate_key.gae_to_rest(
        datastore.Key.from_path('Foo', 1, namespace='the-namespace')),
      {
        'partitionId': {
          'projectId': 'myapp',
          'namespaceId': 'the-namespace',
        },
        'path': [{'kind': 'Foo', 'id': '1'}],
      })
