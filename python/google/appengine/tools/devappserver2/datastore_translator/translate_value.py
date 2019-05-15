"""Translation of entities between REST and App Engine APIs.

The App Engine concept here is not really App Engine, it's just ordinary python
types, although some of those are the wrapper classes in datastore_types.  The
REST version is Value, which is documented here:
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery#Value
and used in both entities and queries.

NOTE(benkraft) on string types: datastore understands five different kinds of
strings: the python (2) builtins str and unicode, as well as the wrapper
classes datastore_types.Blob(str), datastore_types.ByteString(str), and
datastore_types.Text(unicode).  As far as I can tell, the underlying
implementation itself handles four types, which correspond to short (indexable)
and long (unindexable) byte-strings and unicode-strings.  Sadly, without
understanding the full datastore REST implementation (and how it decides which
internal type to use for a given stringValue or blobValue) it's hard to get
everything perfect.

In particular, when translating GAE values to REST values, we translate str or
any of its subtypes to blobValue, and unicode or any of its subtypes to
stringValue.  In the other direction, we use unicode for short stringValues,
Text for long stringValues, and similarly ByteString and Blob for short and
long blobValues.  (We avoid str entirely here: it seems that datastore
sometimes tries to cast it to unicode, which is no good.)  When we have
information about meaning, we prefer that, but we don't depend on it, since
REST clients generally don't pass it.  This seems to be enough to make
everything work well enough for our use cases.
"""
from __future__ import absolute_import

import base64
import collections
import datetime
import logging

from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.api import users
from google.appengine.tools.devappserver2.datastore_translator import grpc
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_key)


def _identity(val):
  """Trivial converter for values that require no special logic."""
  return val


def _decode_unicode(val):
  """Convert REST stringValue to GAE, per NOTE on strings in file docstring."""
  if len(val) > 1500:
    return datastore_types.Text(val)
  else:
    return val


def _decode_bytes(val):
  """Convert REST blobValue to GAE, per NOTE on strings in file docstring."""
  raw = base64.b64decode(val)
  if len(raw) > 1500:
    return datastore_types.Blob(raw)
  else:
    return datastore_types.ByteString(raw)


def _datetime_to_iso(dt):
  """Convert python datetime to the ISO-8601 formatted string used by REST."""
  # Datastore times use UTC, but do not explicitly set the tzinfo.
  return dt.isoformat() + 'Z'


def _iso_to_datetime(iso_string):
  """Convert the ISO-8601 formatted string used by REST to python datetime."""
  # Datastore times use UTC, but do not explicitly set the tzinfo.
  try:
    return datetime.datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%S.%fZ")
  except ValueError:
    try:
      return datetime.datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
      raise grpc.Error("INVALID_ARGUMENT",
                       "'%s' is not a valid ISO-8601 date." % iso_string)


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
  properties = {
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
    properties['user_id'] = {
      'stringValue': user.user_id(),
      'excludeFromIndexes': True,
    }
  return {'properties': properties}


_REQUIRED_USER_FIELDS = frozenset(['email', 'auth_domain'])
_POTENTIAL_USER_FIELDS = _REQUIRED_USER_FIELDS | frozenset(
  # TODO(benkraft): federated_* are not used but I'm not sure if they can still
  # exist in the datastore.
  ['user_id', 'federated_identity', 'federated_provider'])


def _looks_like_user_value(rest_entity):
  # Users never have a key -- they're not real entities.
  if 'key' in rest_entity:
    return False

  # They always have _REQUIRED_USER_FIELDS, and sometimes
  # _POTENTIAL_USER_FIELDS, never others.
  props = set(rest_entity.get('properties', {}))
  return _REQUIRED_USER_FIELDS <= props <= _POTENTIAL_USER_FIELDS


def _rest_entity_or_user_to_gae_value(rest_entity):
  """Convert a REST-style entityValue to a user or entity.

  Sadly, the REST API doesn't give us any way to tell between a UserProperty
  and an EmbeddedEntity (i.e. LocalStructuredProperty).  We just have to guess.
  This method can therefore return either a users.User or a
  datastore_types.EmbeddedEntity.
  """
  if _looks_like_user_value(rest_entity):
    properties = rest_entity['properties']
    return users.User(properties['email']['stringValue'],
                      properties['auth_domain']['stringValue'],
                      properties.get('user_id', {}).get('stringValue'))
  else:
    # TODO(benkraft): Implement this along with put() -- I don't think we use
    # it for queries.  Once we implement entity-translation from REST to GAE,
    # the code will simply be:
    # return datastore_types.EmbeddedEntity(
    #   datastore.Entity.ToPb(translate_entity.rest_to_gae(rest_entity)))
    raise grpc.Error("UNIMPLEMENTED",
                     "TODO(benkraft): Implement this when implementing puts.")


def _gae_geopt_to_rest(geopt):
  """Convert a datastore_types.GeoPt to a REST-style geoPointValue."""
  return {
    'latitude': geopt.lat,
    'longitude': geopt.lon,
  }


def _rest_geo_point_value_to_gae(geo_point_value):
  """Convert a REST-style geoPointValue to a datastore_types.GeoPt."""
  return datastore_types.GeoPt(geo_point_value['latitude'],
                               geo_point_value['longitude'])


# GAE/REST conversion metadata for a given type.
#
# This represents the information we need to convert between REST and GAE value
# types.  It has the following fields:
#   gae_types (Tuple[type]): the Python types for the values datastore gives
#     us.  These are the value types, not the db properties, and roughly match
#     those described here:
#         https://cloud.google.com/appengine/docs/standard/python/datastore/typesandpropertyclasses#Datastore_Value_Types
#     If several types use the same conversion logic, they should all be
#     included -- the rest_to_gae converter should return the best one for a
#     given value, although the 'meaning' field (see comments below in
#     the definition of gae_to_rest()) can override it.
#   rest_field (string): the field-name, in the Value struct, where we should
#     put this value in REST-land.  (See the module docstring for more
#     information.)
#   gae_to_rest (function): a function to convert a value of gae_type to
#     something which JSONifies to whatever the REST API expects.
#   rest_to_gae (function): a function to convert whatever the REST API expects
#     back to a value of gae_type.  (This is normally the inverse of
#     rest_to_gae.)
_Converter = collections.namedtuple(
  '_Converter', ['gae_types', 'rest_field', 'gae_to_rest', 'rest_to_gae'])

_CONVERTERS = [
  # Simple python types.
  # We ignore the value of nullValue -- it should be something which represents
  # null no matter what -- so that we don't have to fix up the differences
  # between the JSON-over-HTTP and protobuf-over-HTTP APIs (see
  # handlers._fix_up_for_proto).
  _Converter((type(None),), 'nullValue', _identity, lambda val: None),
  _Converter((bool,), 'booleanValue', _identity, _identity),
  _Converter((long, int), 'integerValue', str, long),
  _Converter((float,), 'doubleValue', _identity, _identity),
  _Converter((datetime.datetime,), 'timestampValue',
             _datetime_to_iso, _iso_to_datetime),

  # String/bytes types -- see NOTE on string types in file docstring.
  _Converter((unicode, datastore_types.Text),
             'stringValue', _identity, _decode_unicode),
  _Converter((str, datastore_types.Blob, datastore_types.ByteString),
             'blobValue', base64.b64encode, _decode_bytes),

  # Fancier datastore types, mostly with bespoke converters.
  _Converter((datastore.Key,), 'keyValue',
             translate_key.gae_to_rest, translate_key.rest_to_gae),
  _Converter((datastore_types.GeoPt,), 'geoPointValue',
             _gae_geopt_to_rest, _rest_geo_point_value_to_gae),
  # HACK(benkraft): As described in _rest_entity_or_user_to_gae_value, users
  # and embedded entities look the same to the REST API.  We just have to guess
  # when we translate; and that means here we end up with two overlapping
  # converter entries.
  # EmbeddedEntity is things like LocalStructuredProperty.
  _Converter((datastore_types.EmbeddedEntity,), 'entityValue',
             _entity_proto_to_rest_entity, _rest_entity_or_user_to_gae_value),
  _Converter((users.User,), 'entityValue',
             _user_property_to_rest_entity, _rest_entity_or_user_to_gae_value),
]

_CONVERTERS_BY_GAE_TYPE = {t: c for c in _CONVERTERS for t in c.gae_types}
_CONVERTERS_BY_REST_FIELD = {c.rest_field: c for c in _CONVERTERS}

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
  set(_CONVERTERS_BY_GAE_TYPE) | _UNIMPLEMENTED_CONVERTERS)
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
    # NOTE(benkraft): We can't write an ordinary converter for this because it
    # handles meaning and indexing specially.
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
  if t not in _CONVERTERS_BY_GAE_TYPE:
    raise grpc.Error(
      "UNKNOWN", "Don't know how to convert property type %s" % t)

  converter = _CONVERTERS_BY_GAE_TYPE[t]
  retval = {converter.rest_field: converter.gae_to_rest(gae_value)}

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


def rest_to_gae(rest_value):
  """Convert a REST Value to the GAE type equivalent.

  This is theoretically the inverse of gae_to_rest (although in practice there
  may be slight differences.

  Returns: a pair (GAE value, true if this property is indexed).  Note that the
    latter is ignored if this is a query.
  """
  # A valid input should have exactly one of the "fooValue" fields, and
  # optionally meaning and/or excludeFromIndexes.  We need to find that unique
  # "fooValue" field (and error if there isn't one).
  non_option_fields = set(rest_value) - {'meaning', 'excludeFromIndexes'}
  if not non_option_fields:
    raise grpc.Error("INVALID_ARGUMENT", "No value passed!")
  if len(non_option_fields) > 1:
    raise grpc.Error("INVALID_ARGUMENT",
                     # It could either be multiple values (you passed both
                     # stringValue and integerValue) or an option we don't know
                     # about (you passed both stringValue and frob).
                     "Multiple value fields or unknown option: %s"
                     % ', '.join(non_option_fields))

  field = non_option_fields.pop()
  unpacked_value = rest_value[field]
  if field == 'arrayValue':
    # NOTE(benkraft): We can't write an ordinary converter for this because it
    # handles meaning and indexing specially.
    #
    # As in gae_to_rest, we expect indexing to be marked on the individual
    # values, but to match for all of them.  (GAE can't represent the case
    # where they differ; it seems like datastore can represent it but the UI
    # doesn't really understand that.)  It's banned at the toplevel in
    # prod (empirically).
    if 'excludeFromIndexes' in rest_value:
      raise grpc.Error("INVALID_ARGUMENT",
                       "Array values must not set excludeFromIndexes.")

    items = unpacked_value.get('values')
    if not items:
      # It's unclear if saying this value is "indexed" is really fair -- in
      # practice it's unset -- but that's the default, and what the datastore
      # viewer UI does.  Prod also accepts unset 'values' as an empty array.
      return [], True

    # It's unclear if meaning is supposed to be set at the toplevel or on each
    # item; we'll accept either (and handle it in the items themselves).
    meaning = rest_value.get('meaning')
    if meaning is not None:
      for item in items:
        item.setdefault('meaning', meaning)

    items, is_indexed_values = zip(*map(rest_to_gae, items))
    is_indexed_values = set(is_indexed_values)
    is_indexed = is_indexed_values.pop()
    if is_indexed_values:
      raise grpc.Error("UNIMPLEMENTED",
                       "Array values have inconsistent index settings.")

    return list(items), is_indexed

  if field not in _CONVERTERS_BY_REST_FIELD:
    raise grpc.Error(
      "INVALID_ARGUMENT", "Don't know how to convert %s" % field)

  converter = _CONVERTERS_BY_REST_FIELD[field]
  gae_value = converter.rest_to_gae(unpacked_value)

  # See gae_to_rest for an explanation of meaning.  Again, here, we do our
  # best, using it to choose between the types we have.
  #
  # HACK(benkraft): Theoretically, the values in _PROPERTY_CONVERSIONS are
  # conversions (to the expected type).  But all the ones we care about are
  # type constructors so we can play a bit fast and loose with the difference.
  type_from_meaning = datastore_types._PROPERTY_CONVERSIONS.get(
    rest_value.get('meaning'))
  if type_from_meaning in converter.gae_types:
    gae_value = type_from_meaning(gae_value)
  elif type_from_meaning is not None:
    logging.warning("Unexpected meaning %s for %s",
                    rest_value.get('meaning'), field)

  return gae_value, not rest_value.get('excludeFromIndexes', False)
