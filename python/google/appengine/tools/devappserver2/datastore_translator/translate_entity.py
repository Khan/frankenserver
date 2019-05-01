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
    'entity': gae_to_rest_entity(gae_entity),
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
