from __future__ import absolute_import

import datetime

from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.api import users
from google.appengine.tools.devappserver2.datastore_translator import testbase
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_key)
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_value)


class ValueConversionTest(testbase.DatastoreTranslatorTestBase):
  """Tests value conversion (both directions).

  NOTE(benkraft): This test has some overlap with translate_entity_test, but
  it's helpful to have both because that tests things in the context of real db
  models -- which is what we actually want -- whereas this is necessarily a
  more synthetic test.
  """
  def _test_both_conversions(self, gae_value, rest_value, indexed=True):
    actual_rest_value = translate_value.gae_to_rest(gae_value, indexed)
    # We don't worry about whether we are consistent about setting meaning,
    # although if we do set it we make sure it matches.
    if 'meaning' not in rest_value:
      actual_rest_value.pop('meaning', None)
    self.assertEqual(actual_rest_value, rest_value)

    self.assertEqual(translate_value.rest_to_gae(rest_value),
                     (gae_value, indexed))

  def test_indexing(self):
    self._test_both_conversions(
      12345, {'integerValue': '12345', 'excludeFromIndexes': True},
      indexed=False)

  def test_invalid_rest_values(self):
    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      # Multiple values
      translate_value.rest_to_gae({
        'integerValue': '12345',
        'stringValue': '12345',
      })

    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      # No value
      translate_value.rest_to_gae({})

    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      # Value key we've never heard of
      translate_value.rest_to_gae({'myValue': '12345'})

    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      # Option key we've never heard of
      translate_value.rest_to_gae({'fast': True, 'stringValue': 'zoom'})

    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      # Some of everything
      translate_value.rest_to_gae({
        'fast': True,
        'stringValue': 'zoom',
        'myValue': '1234',
      })

  def test_null(self):
    self._test_both_conversions(None, {'nullValue': None})

  def test_boolean(self):
    self._test_both_conversions(True, {'booleanValue': True})

  def test_int(self):
    self._test_both_conversions(12345, {'integerValue': '12345'})

  def test_long(self):
    self._test_both_conversions(9223372036854775807,
                                {'integerValue': '9223372036854775807'})

  def test_float(self):
    self._test_both_conversions(0.57721566, {'doubleValue': 0.57721566})

  def test_datetime(self):
    self._test_both_conversions(
      datetime.datetime(2019, 5, 1, 12, 34, 56),
      {'timestampValue': '2019-05-01T12:34:56Z'})
    self._test_both_conversions(
      datetime.datetime(2019, 5, 1, 12, 34, 56, 1),
      {'timestampValue': '2019-05-01T12:34:56.000001Z'})

  def test_unicode(self):
    # Since the string types compare equal, we play a bit fast and loose with
    # which type is actually returned, and just hope datastore can figure it
    # out.  It's not totally clear what the right behavior is anyway.
    # TODO(benkraft): Test this better when we test actual puts.
    self._test_both_conversions(
      u'asdf', {'stringValue': u'asdf'})
    self._test_both_conversions(
      u'eight\u277d', {'stringValue': u'eight\u277d'})
    self._test_both_conversions(
      datastore_types.Text(u'eight\u277d'),
      {'stringValue': u'eight\u277d', 'meaning': 15})
    self._test_both_conversions(
      datastore_types.Text(u'eight\u277d'),
      {'stringValue': u'eight\u277d'})

  def test_string(self):
    # As with test_unicode we play a bit fast and loose.
    # TODO(benkraft): Test this better when we test actual puts.
    self._test_both_conversions(
      'asdf', {'blobValue': 'YXNkZg=='})
    self._test_both_conversions(
      '\x00\x01\x02', {'blobValue': 'AAEC'})
    self._test_both_conversions(
      datastore_types.Blob('\x00\x01\x02'),
      {'blobValue': 'AAEC', 'meaning': 14})
    self._test_both_conversions(
      datastore_types.Blob('\x00\x01\x02'), {'blobValue': 'AAEC'})
    self._test_both_conversions(
      datastore_types.ByteString('\x00\x01\x02'),
      {'blobValue': 'AAEC', 'meaning': 16})
    self._test_both_conversions(
      datastore_types.ByteString('\x00\x01\x02'), {'blobValue': 'AAEC'})
    self._test_both_conversions(
      '\x80\x81\x82', {'blobValue': 'gIGC'})
    self._test_both_conversions(
      datastore_types.ByteString('\x80\x81\x82'), {'blobValue': 'gIGC'})

  def test_key(self):
    self._test_both_conversions(
      datastore.Key.from_path('Foo', 123),
      {'keyValue': translate_key.gae_to_rest(
        datastore.Key.from_path('Foo', 123))})
    self._test_both_conversions(
      datastore.Key.from_path('Foo', 'asdf', 'Bar', '123'),
      {'keyValue': translate_key.gae_to_rest(
        datastore.Key.from_path('Foo', 'asdf', 'Bar', '123'))})

  def test_geopt(self):
    self._test_both_conversions(
      datastore_types.GeoPt(36.5785, -118.2923),
      {'geoPointValue': {'latitude': 36.5785, 'longitude': -118.2923}})
    self._test_both_conversions(
      datastore_types.GeoPt(0, 0),
      {'geoPointValue': {'latitude': 0, 'longitude': 0}})

  def test_user(self):
    self._test_both_conversions(
      users.User('foo@example.com', 'gmail.com'),
      {'entityValue': {'properties': {
        'email': {
          'stringValue': 'foo@example.com',
          'excludeFromIndexes': True
        },
        'auth_domain': {
          'stringValue': 'gmail.com',
          'excludeFromIndexes': True
        },
      }}})
    self._test_both_conversions(
      users.User('foo@example.com', 'gmail.com', '11111111111111111111111111'),
      {'entityValue': {'properties': {
        'user_id': {
          'stringValue': '11111111111111111111111111',
          'excludeFromIndexes': True
        },
        'email': {
          'stringValue': 'foo@example.com',
          'excludeFromIndexes': True
        },
        'auth_domain': {
          'stringValue': 'gmail.com',
          'excludeFromIndexes': True
        },
      }}})

  def test_list(self):
    self._test_both_conversions(
      [1, 2, 3],
      {'arrayValue': {'values': [
        {'integerValue': '1'},
        {'integerValue': '2'},
        {'integerValue': '3'},
      ]}})

    self._test_both_conversions(
      [1, 2, 3],
      {'arrayValue': {'values': [
        {'integerValue': '1', 'excludeFromIndexes': True},
        {'integerValue': '2', 'excludeFromIndexes': True},
        {'integerValue': '3', 'excludeFromIndexes': True},
      ]}},
      indexed=False)

    self._test_both_conversions([], {'arrayValue': {'values': []}})
    # We should also accept omitted 'values'.
    self.assertEqual(translate_value.rest_to_gae({'arrayValue': {}}),
                     ([], True))

    with self.assertRaisesGrpcCode("INVALID_ARGUMENT"):
      # Toplevel index setting (not allowed)
      translate_value.rest_to_gae({
        'arrayValue': {'values': [
          {'integerValue': '1'},
          {'integerValue': '2'},
          {'integerValue': '3', 'excludeFromIndexes': True},
        ]},
        'excludeFromIndexes': True})

    with self.assertRaisesGrpcCode("UNIMPLEMENTED"):
      # Inconsistent index settings (allowed but we can't handle)
      translate_value.rest_to_gae({'arrayValue': {'values': [
        {'integerValue': '1', 'excludeFromIndexes': True},
        {'integerValue': '2'},
        {'integerValue': '3', 'excludeFromIndexes': True},
      ]}})
