from __future__ import absolute_import

import datetime

from google.appengine.api import datastore
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import ndb
from google.appengine.tools.devappserver2.datastore_translator import testbase
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_entity)
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_key)


# In order to make sure we are getting a good test of how the datastore works,
# we use DB models and grab the datastore.Entity out from them for testing,
# instead of constructing our own entities directly.
class EmptyModel(db.Model):
  pass


class SimpleModel(db.Model):
  boolean = db.BooleanProperty(indexed=True)
  integer = db.IntegerProperty(indexed=True)
  unindexed_float = db.FloatProperty(indexed=False)


class StringsModel(db.Model):
  string = db.StringProperty(indexed=True)
  unindexed_string = db.StringProperty(indexed=False)
  text = db.TextProperty(indexed=False)
  byte_string = db.ByteStringProperty(indexed=True)
  unindexed_byte_string = db.ByteStringProperty(indexed=False)
  blob = db.BlobProperty(indexed=False)


class DateTimesModel(db.Model):
  date = db.DateProperty(indexed=True)
  time = db.TimeProperty(indexed=True)
  dt = db.DateTimeProperty(indexed=True)


class FancyModel(db.Model):
  geo_point = db.GeoPtProperty(indexed=True)
  user = db.UserProperty(indexed=True)
  ref = db.ReferenceProperty(SimpleModel, indexed=True)
  self_ref = db.SelfReferenceProperty(indexed=True)


class ListsModel(db.Model):
  integer_list = db.ListProperty(int, indexed=True)
  string_list = db.StringListProperty(indexed=True)
  unindexed_string_list = db.StringListProperty(indexed=False)


class StructuredModel(ndb.Model):
  integers = ndb.IntegerProperty(indexed=False, repeated=True)
  string = ndb.StringProperty(indexed=False)


# We just do a quick smoke test for ndb -- to see that things generally work,
# and to test LocalStructuredProperty which has no db equivalent.
class NdbModel(ndb.Model):
  integer = ndb.IntegerProperty(indexed=True)
  unindexed_float = ndb.FloatProperty(indexed=False)
  repeated_string = ndb.StringProperty(indexed=True, repeated=True)
  unindexed_repeated_string = ndb.StringProperty(indexed=False, repeated=True)
  local_structured = ndb.LocalStructuredProperty(
    StructuredModel, indexed=False)
  structured = ndb.StructuredProperty(StructuredModel, indexed=False)
  key = ndb.KeyProperty(indexed=True)


class GaeToRestTest(testbase.DatastoreTranslatorTestBase):
  def _put_and_assert(self, db_instance, expected_properties):
    # Un-put datastore entities can be a little wonky, so we test on what we
    # get back from the stub rather than the model as created.  (That's what we
    # would ever be serializing to REST-style anyway.)
    db_instance = db.get(db_instance.put())
    expected_rest_entity = {
      'key': translate_key.gae_to_rest(db_instance.key())}
    if expected_properties:
      expected_rest_entity['properties'] = expected_properties

    self.assertEqual(
      translate_entity._gae_to_rest_entity(db_instance._entity),
      expected_rest_entity)

  def test_empty_model(self):
    self._put_and_assert(EmptyModel(), {})

  def test_simple_model(self):
    self._put_and_assert(
      SimpleModel(boolean=True, integer=555555555555555, unindexed_float=3.14),
      {
        'boolean': {'booleanValue': True},
        'integer': {'integerValue': '555555555555555'},
        'unindexed_float': {'doubleValue': 3.14, 'excludeFromIndexes': True},
      })

  def test_unset_properties(self):
    self._put_and_assert(
      SimpleModel(boolean=False, integer=None),
      {
        'boolean': {'booleanValue': False},
        'integer': {'nullValue': None},
        # db makes implicit nulls explicit.
        'unindexed_float': {'nullValue': None, 'excludeFromIndexes': True},
      })

  def test_string_like_properties(self):
    self._put_and_assert(
      StringsModel(
        string=u'\U0001f44d',
        unindexed_string=':D',   # auto-converted to unicode (since it's ascii)
        text=u'\u2048' * 2048,
        byte_string='\x80\x02N.',
        unindexed_byte_string='!!\x00',
        blob='\xe2\x98\x83' * 3333,
      ), {
        'string': {'stringValue': u'\U0001f44d'},
        'unindexed_string': {'stringValue': ':D',
                             'excludeFromIndexes': True},
        'text': {'stringValue': u'\u2048' * 2048,
                 'meaning': 15,
                 'excludeFromIndexes': True},
        'byte_string': {'blobValue': 'gAJOLg==', 'meaning': 16},
        'unindexed_byte_string': {'blobValue': 'ISEA',
                                  'meaning': 16,
                                  'excludeFromIndexes': True},
        'blob': {'blobValue': '4piD' * 3333,
                 'meaning': 14,
                 'excludeFromIndexes': True},
      })

  def test_datetime_properties(self):
    self._put_and_assert(
      DateTimesModel(
        date=datetime.date(2017, 3, 14),
        time=datetime.time(1, 59),
        dt=datetime.datetime(2017, 3, 14, 1, 59, 26, 535897),
      ), {
        'date': {'meaning': 7, 'timestampValue': '2017-03-14T00:00:00Z'},
        'time': {'meaning': 7, 'timestampValue': '1970-01-01T01:59:00Z'},
        'dt': {'meaning': 7, 'timestampValue': '2017-03-14T01:59:26.535897Z'},
      })

  def test_fancy_properties(self):
    self._put_and_assert(
      FancyModel(
        geo_point=db.GeoPt(37.396632, -122.084141),
        user=users.User('sal@khanacademy.org',
                        'gmail.com',
                        '163021881010976161781'),
        ref=db.Key.from_path('SimpleModel', 1),
        self_ref=db.Key.from_path('FancyModel', '1'),
      ), {
        'geo_point': {
          'geoPointValue': {'latitude': 37.396632, 'longitude': -122.084141},
          'meaning': 9
        },
        'user': {
          'entityValue': {
            'auth_domain': {
              'stringValue': 'gmail.com',
              'excludeFromIndexes': True,
            },
            'email': {
              'stringValue': 'sal@khanacademy.org',
              'excludeFromIndexes': True,
            },
            'user_id': {
              'stringValue': '163021881010976161781',
              'excludeFromIndexes': True,
            },
          },
        },
        'ref': {
          'keyValue': {
            'partitionId': {'projectId': 'myapp'},
            'path': [{'id': '1', 'kind': 'SimpleModel'}],
          },
        },
        'self_ref': {
          'keyValue': {
            'partitionId': {'projectId': 'myapp'},
            'path': [{'name': '1', 'kind': 'FancyModel'}],
          },
        }
      })

  def test_list_properties(self):
    self._put_and_assert(
      ListsModel(
        integer_list=[1, 2, 3],
        string_list=[u'\u200b'],
        unindexed_string_list=[u'\u200e'],
      ), {
        'integer_list': {
          'arrayValue': {
            'values': [
              {'integerValue': '1'},
              {'integerValue': '2'},
              {'integerValue': '3'},
            ],
          },
        },
        'string_list': {
          'arrayValue': {'values': [{'stringValue': u'\u200b'}]},
        },
        'unindexed_string_list': {
          'arrayValue': {
            'values': [
              {'stringValue': u'\u200e', 'excludeFromIndexes': True},
            ]
          },
        },
      })

  def test_unset_list_properties(self):
    # List/repeated properties are omitted if unset or empty.
    # TODO(benkraft): I've seen some in the datastore that instead have
    # 'arrayValue': {}.  How did those get there?  Were they manually created?
    self._put_and_assert(ListsModel(integer_list=[]), {})

  def test_ndb(self):
    ndb_model = NdbModel(
      integer=17,
      unindexed_float=2.71828,
      repeated_string=[u'\U0001f44d', u'\U0001f44e'],
      unindexed_repeated_string=[u'\U0001f44a', u'\U0001f44b'],
      local_structured=StructuredModel(integers=[1, 1, 2, 3], string='581321'),
      structured=StructuredModel(integers=[1, 1, 2, 3], string='581321'),
      key=ndb.Key('FooBar', 'asdf'),
    )
    ndb_key = ndb_model.put()
    db_key = ndb_key.to_old_key()
    entity = datastore.Get(db_key)
    self.assertEqual(
      translate_entity._gae_to_rest_entity(entity),
      {
        'key': translate_key.gae_to_rest(db_key),
        'properties': {
          'integer': {'integerValue': '17'},
          'unindexed_float': {
            'doubleValue': 2.71828,
            'excludeFromIndexes': True,
          },
          'repeated_string': {
            'arrayValue': {
              'values': [
                {'stringValue': u'\U0001f44d'},
                {'stringValue': u'\U0001f44e'},
              ],
            },
          },
          'unindexed_repeated_string': {
            'arrayValue': {
              'values': [
                # ndb automatically stores unindexed strings as Text.
                {
                  'stringValue': u'\U0001f44a',
                  'meaning': 15,
                  'excludeFromIndexes': True,
                },
                {
                  'stringValue': u'\U0001f44b',
                  'meaning': 15,
                  'excludeFromIndexes': True,
                },
              ],
            },
          },
          'local_structured': {
            'entityValue': {
              'properties': {
                'integers': {
                  'arrayValue': {
                    'values': [
                      {'integerValue': '1', 'excludeFromIndexes': True},
                      {'integerValue': '1', 'excludeFromIndexes': True},
                      {'integerValue': '2', 'excludeFromIndexes': True},
                      {'integerValue': '3', 'excludeFromIndexes': True},
                    ]
                  },
                },
                'string': {
                  'stringValue': '581321',
                  'meaning': 15,
                  'excludeFromIndexes': True,
                },
              },
            },
            'excludeFromIndexes': True,
            'meaning': 19,
          },
          'structured.integers': {
            'arrayValue': {
              'values': [
                {'integerValue': '1', 'excludeFromIndexes': True},
                {'integerValue': '1', 'excludeFromIndexes': True},
                {'integerValue': '2', 'excludeFromIndexes': True},
                {'integerValue': '3', 'excludeFromIndexes': True},
              ]
            },
          },
          'structured.string': {
            'stringValue': '581321',
            'meaning': 15,
            'excludeFromIndexes': True,
          },

          'key': {
            'keyValue': {
              'partitionId': {'projectId': u'myapp'},
              'path': [{'kind': u'FooBar', 'name': u'asdf'}],
            },
          },
        },
      })

  def test_entity_result(self):
    db_instance = SimpleModel(
      boolean=True,
      integer=555555555555555,
      unindexed_float=3.14,
    )
    db_instance = db.get(db_instance.put())
    self.assertEqual(
      translate_entity.gae_to_rest_entity_result(db_instance._entity),
      {
        'entity': {
          'key': translate_key.gae_to_rest(db_instance.key()),
          'properties': {
            'boolean': {'booleanValue': True},
            'integer': {'integerValue': '555555555555555'},
            'unindexed_float': {
              'doubleValue': 3.14,
              'excludeFromIndexes': True,
            },
          },
        },
        'version': '1',
      })
