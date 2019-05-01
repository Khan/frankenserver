"""Translation of entities between REST and App Engine APIs.

The App Engine concept here is not really App Engine, it's just ordinary python
types, although some of those are the wrapper classes in datastore_types.  The
REST version is Value, which is documented here:
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery#Value
and used in both entities and queries.
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
  # TODO(benkraft): Is there any way around this circular dep?  It's necessary
  # to translate EmbeddedEntity values (a.k.a. entityValue in REST-land and
  # LocalStructuredProperty in ndb-land).
  from google.appengine.tools.devappserver2.datastore_translator import (
    translate_entity)

  # NOTE(benkraft): FromPb will fill in a fake key (with id=0) here; luckily
  # _gae_to_rest_entity will filter that back out (by checking
  # has_id_or_name()).
  return translate_entity.gae_to_rest_entity(
    datastore.Entity.FromPb(entity_proto))


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


def gae_to_rest(gae_value, indexed=True):
  """Convert a GAE (property) value to the REST equivalent.

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
        'values': [gae_to_rest(item, indexed) for item in gae_value]
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
