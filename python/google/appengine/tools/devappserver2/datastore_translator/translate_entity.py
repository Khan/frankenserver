"""Translation of entities between REST and App Engine APIs.

The App Engine concept here is datastore.Entity, which is much lower-level than
db/ndb models.  It stores property-values as a dict (the class actually
inherits from dict) as well as a list of those property values that are not
indexed (`entity.unindexed_properties()`) and the entity's key
(`entity.key()`).  Given a db.Model, one can grab the datastore.Entity as
`model_instance._entity`.  (There is no easy way to do so for an ndb.Model.)

The corresponding datastore concept is Entity, described at
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/Entity
"""
from __future__ import absolute_import

import base64
import datetime

from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.api import users
from google.appengine.tools.devappserver2.datastore_translator import grpc
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_key)


def _identity(val):
  """Trivial converter for values that require no special logic."""
  return val


def _datetime_to_iso(dt):
  """Convert python datetime to the ISO-8601 formatted string used by REST."""
  # Datastore times use UTC, but do not explicitly set the tzinfo.
  return dt.isoformat() + 'Z'


def _entity_proto_to_rest_entity(entity_proto):
  """Convert a serialized entity_pb.EntityProto to a REST-style entity.

  This is cribbed from db.model_for_protobuf, as described by
  datastore_types.EmbeddedEntity.
  """
  # NOTE(benkraft): FromPb will fill in a fake key (with id=0) here; luckily
  # _gae_to_rest_entity will filter that back out (by checking
  # has_id_or_name()).
  return _gae_to_rest_entity(datastore.Entity.FromPb(entity_proto))


def _user_property_to_rest_entity(user):
  """Convert a users.User to a REST-style entity.

  The REST API represents UserProperty as an entityValue with the following
  properties:
  - user_id (stringValue),
  - email (stringValue),
  - auth_domain (stringValue)

  This is cribbed from datastore_types.PackUser.  We do not implement
  federated_identity, because it's long gone from the datastore.  (Even
  auth_domain may be unused now.)
  """
  retval = {
    'email': {
      'stringValue': user.email(),
      'excludeFromIndexes': True,
    },
    'auth_domain': {
      'stringValue': user.auth_domain(),
      'excludeFromIndexes': True,
    },
  }
  if user.user_id() is not None:
    retval['user_id'] = {
      'stringValue': user.user_id(),
      'excludeFromIndexes': True,
    }
  return retval


def _geopt_to_rest_value(geopt):
  """Convert a datastore_types.GeoPt to a REST-style geoPointValue."""
  return {
    'latitude': geopt.lat,
    'longitude': geopt.lon,
  }


# Converters, by type, for the values that datastore gives us.  These are the
# value types, not the db properties, and roughly match those described here:
#     https://cloud.google.com/appengine/docs/standard/python/datastore/typesandpropertyclasses#Datastore_Value_Types
# Many of these methods are cribbed from the implementations of
# datastore_types.Pack*.
#
# The dict should have as keys a type, and as values a pair
#   (REST field name, converter)
# The REST field name is something like 'stringValue' -- see
#    https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery#Value
# for details.  The converter should accept an instance of the given type, and
# convert it to whatever the REST API wants for that property type.
_GAE_TO_REST_PROPERTY_CONVERTERS = {
  # Simple python types.
  type(None): ('nullValue', _identity),
  bool: ('booleanValue', _identity),
  int: ('integerValue', str),
  long: ('integerValue', str),
  float: ('doubleValue', _identity),
  datetime.datetime: ('timestampValue', _datetime_to_iso),

  # String/bytes types.
  # TODO(benkraft): It's unclear to me which of these are actually used in
  # modern datastore, but we implement them all because it's easy to do so.
  unicode: ('stringValue', _identity),
  datastore_types.Text: ('stringValue', _identity),
  str: ('blobValue', base64.b64encode),
  datastore_types.Blob: ('blobValue', base64.b64encode),
  datastore_types.ByteString: ('blobValue', base64.b64encode),

  # Fancier datastore types, mostly with bespoke converters.
  datastore.Key: ('keyValue', translate_key.gae_to_rest),
  datastore_types.EmbeddedEntity: (    # e.g. LocalStructuredProperty
    'entityValue', _entity_proto_to_rest_entity),
  users.User: ('entityValue', _user_property_to_rest_entity),
  datastore_types.GeoPt: ('geoPointValue', _geopt_to_rest_value),
}


# This is just to make explicit which of the types in
# datastore_types._PROPERTY_TYPES we do not currently handle,
# because we don't use them in webapp and don't intend to.
_UNIMPLEMENTED_CONVERTERS = {
  datastore_types.BlobKey,
  datastore_types._OverflowDateTime,     # datetime too big for Python/ISO-8601
  datastore_types.Category,
  datastore_types.Email,
  datastore_types.IM,
  datastore_types.Link,
  datastore_types.PhoneNumber,
  datastore_types.PostalAddress,
  datastore_types.Rating,
}


# Check that we've handled, or decided not to handle, all the types datastore
# thinks it will give us.
_PROPERTY_TYPES_HANDLED = (
  set(_GAE_TO_REST_PROPERTY_CONVERTERS) | _UNIMPLEMENTED_CONVERTERS)
assert _PROPERTY_TYPES_HANDLED == datastore_types._PROPERTY_TYPES, (
  _PROPERTY_TYPES_HANDLED.symmetric_difference(
    datastore_types._PROPERTY_TYPES))


def _gae_property_value_to_rest_property_value(gae_value, indexed=True):
  """Convert a GAE property value to the REST equivalent.

  GAE values are just python types -- the keys in
  _GAE_TO_REST_PROPERTY_CONVERTERS above.  REST wants a Value struct documented
  here:
      https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery#Value

  This code does the conversion, which is the meat of converting entities from
  GAE-style to REST.
  """

  if isinstance(gae_value, list):
    return {
      'arrayValue': {
        'values': [
          _gae_property_value_to_rest_property_value(item, indexed)
          for item in gae_value]
        # Strangely, rather than marking the whole arrayValue as unindexed, the
        # REST API wants each item marked unindexed.  So we omit it here.
        #
        # Meanwhile, we do not handle meaning specially, leaving them as values
        # on the individual items.  The intended semantics are unclear;
        # datastore_types's handling suggests maybe we should return an array
        # of meanings but that's definitely not valid in REST, and this is.
      }
    }

  t = type(gae_value)
  if t not in _GAE_TO_REST_PROPERTY_CONVERTERS:
    raise grpc.Error(
      "UNKNOWN", "Don't know how to convert property type %s" % t)

  rest_name, converter = _GAE_TO_REST_PROPERTY_CONVERTERS[t]
  retval = {rest_name: converter(gae_value)}

  # Datastore has a "meaning" field which is used internally to distinguish
  # between the various ways you might interpret a given type -- for example
  # a pile of bytes could be a utf-8 string, some binary data, or the
  # serialized protobuf of an entity (as for LocalStructuredProperty).  This
  # field is not really documented, although one can see the valid meanings
  # in entity_pb.Property.
  #
  # The REST API has a field for meaning, but it's only passed sometimes --
  # seemingly when it's "unclear".  (That is, a serialized entity will be
  # returned as an entityValue, so the meaning is no longer needed, but a
  # datetime too large for ISO-8601 (which can be written from Java) may be
  # returned as an integerValue with meaning GD_WHEN.)
  #
  # Meanwhile, datastore has already made use of the meaning to decide which
  # type to pass us -- for example a BYTESTRING will be passed as a
  # datastore.ByteString.  Sadly, we don't really have a good enough list of
  # cases when the REST API wants the meaning, nor a real description of most
  # of the meanings beyond their names, so we just include them always, and
  # hope that's good enough.
  meaning = datastore_types._PROPERTY_MEANINGS.get(type(gae_value))
  if meaning is not None:
    retval['meaning'] = meaning

  if not indexed:
    retval['excludeFromIndexes'] = True

  return retval


def _gae_to_rest_entity(gae_entity):
  """Convert a datastore.Entity to a REST entity.

  The REST structure we return is documented here:
      https://cloud.google.com/datastore/docs/reference/data/rest/v1/Entity
  """
  rest_entity = {}
  if gae_entity.key().has_id_or_name():
    # Note that in the case where the key is incomplete (e.g. an entityValue
    # property value) the REST API omits the kind entirely, while datastore
    # tracks it (with has_id_or_name() false).
    rest_entity['key'] = translate_key.gae_to_rest(gae_entity.key())

  if len(gae_entity):
    rest_entity['properties'] = {}
    for name, gae_value in gae_entity.iteritems():
      rest_entity['properties'][name] = (
        _gae_property_value_to_rest_property_value(
          gae_value, indexed=(name not in gae_entity.unindexed_properties())))

  return rest_entity


_FAKE_ENTITY_VERSION = '1'


def _entity_version():
  """Return a fake "version" for a REST-style entity.

  In the REST datastore API, entities have a version number which is returned
  in various places (e.g. as a part of an EntityResult).  (This is likely the
  entity group's bigtable timestamp.)  The App Engine API does not expose this
  data, so we have to fake it.

  Luckily, as of April 2019 none of the Google Cloud datastore clients make use
  of the version number, so we don't make any attempt to have a good fake.
  Instead, we just return 1 always -- hopefully any client that cares will
  notice that this makes no sense and complain loudly enough that we will know
  it's time to implement this properly.
  """
  return _FAKE_ENTITY_VERSION


def gae_to_rest_entity_result(gae_entity):
  """Convert a datastore.Entity to a REST EntityResult.

  The REST structure we return is documented here:
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/EntityResult
  """
  return {
    'entity': _gae_to_rest_entity(gae_entity),
    'version': _entity_version(),
    # TODO(benkraft): Implement cursor, once we implement APIs that use it.
  }


def gae_key_to_rest_entity_result(gae_key):
  """Convert a datastore.Key to a REST KEYS_ONLY EntityResult.

  This returns a similar structure to gae_to_rest_entity_result, only it
  returns it KEYS_ONLY style.  This is not really documented as far as I can
  find, but it basically means the entity consists of only a key.  It's used in
  keys-only queries, and in missing entities from get requests.
  """
  return {
    'entity': {
      'key': translate_key.gae_to_rest(gae_key),
    },
    'version': _entity_version(),
  }
