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

from google.appengine.api import datastore
from google.appengine.datastore import datastore_query
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_key)
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_value)


def gae_to_rest_entity(gae_entity):
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
        translate_value.gae_to_rest(
          gae_value, indexed=(name not in gae_entity.unindexed_properties())))

  return rest_entity


def rest_to_gae_entity(rest_entity, project_id=None, incomplete_key=False):
  """Convert a REST entity to a datastore.Entity.

  This is the inverse of gae_to_rest_entity.  project_id and incomplete_key are
  as for translate_key.rest_to_gae.
  """
  gae_key = translate_key.rest_to_gae(
    rest_entity['key'], project_id, incomplete_key)

  gae_entity = datastore.Entity(
    gae_key.kind(), parent=gae_key.parent(), name=gae_key.name(),
    id=None if gae_key.id() == -1 else gae_key.id(),
    namespace=gae_key.namespace())

  unindexed_properties = []
  for name, rest_value in rest_entity.get('properties', {}).iteritems():
    gae_entity[name], is_indexed = translate_value.rest_to_gae(rest_value)
    if not is_indexed:
      unindexed_properties.append(name)

  gae_entity.set_unindexed_properties(unindexed_properties)
  return gae_entity


_FAKE_ENTITY_VERSION = '1'


def entity_version():
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


def gae_to_rest_cursor(gae_cursor):
  """Convert a datastore_query.Cursor to REST-style base64 string.

  In REST, this is an opaque string; in fact, it appears to be roughly the
  base64ed version of the GAE cursor as bytes.  It doesn't really need to match
  the way prod does things, as long as we're consistent: the string is opaque
  and specific to a query.  But it *does* need to be valid base64, because the
  protobuf version of the API wants to represent it as bytes.
  """
  # You might think we could use gae_cursor.to_urlsafe_string() here, but in
  # fact we can't: that uses base64.urlsafe_b64encode which is a different
  # base64 alphabet than proto expects.  So we do it ourselves.
  return base64.b64encode(gae_cursor.to_bytes())


def rest_to_gae_cursor(rest_cursor):
  """Convert a REST-style base64 string cursor to a datastore_query.Cursor.

  This is the reverse of gae_to_rest_cursor, with one exception: it will pass
  through None for the convenience of callers (since cursors are not required
  in requests).
  """
  if rest_cursor is None:
    return None
  # See gae_to_rest_cursor for why we can't use from_urlsafe_string.
  return datastore_query.Cursor.from_bytes(base64.b64decode(rest_cursor))


def gae_to_rest_entity_result(gae_entity, cursor=None):
  """Convert a datastore.Entity to a REST EntityResult.

  The REST structure we return is documented here:
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/EntityResult
  As described there, cursor should be set for query results.
  """
  retval = {
    'entity': gae_to_rest_entity(gae_entity),
    'version': entity_version(),
  }
  if cursor:
    retval['cursor'] = cursor
  return retval


def gae_key_to_rest_entity_result(gae_key, cursor=None):
  """Convert a datastore.Key to a REST KEYS_ONLY EntityResult.

  This returns a similar structure to gae_to_rest_entity_result, only it
  returns it KEYS_ONLY style.  This is not really documented as far as I can
  find, but it basically means the entity consists of only a key.  It's used in
  keys-only queries, and in missing entities from get requests.
  """
  retval = {
    'entity': {
      'key': translate_key.gae_to_rest(gae_key),
    },
    'version': entity_version(),
  }
  if cursor:
    retval['cursor'] = cursor
  return retval
