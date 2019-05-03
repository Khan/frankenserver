"""Translation of keys between REST and App Engine APIs."""
from __future__ import absolute_import

from google.appengine.api import datastore
from google.appengine.tools.devappserver2.datastore_translator import grpc


def rest_to_gae(rest_key, project_id=None, incomplete=False):
  """Translate a REST API style key into a datastore.Key.

  Arguments:
    rest_key: The REST API's key object, parsed from JSON.  Documented at:
        https://cloud.google.com/datastore/docs/reference/data/rest/v1/Key
    project_id: The project ID for this request, or None.  (If set, we validate
        this against the key's project ID; if not we infer it from environ.)
    incomplete: True if this is an incomplete key, i.e. one to which the
        datastore will assign the ID of the final path item, such as in an
        AllocateIds call.  Note that in REST-land, incomplete keys simply omit
        the 'id' or 'name' value, but in App Engine it is set to a bogus value.
        TODO(benkraft): Alternately, we could do like ndb does and construct
        the reference (_Key__reference) by hand, which avoids the bogus value.
        It's not clear it matters.

  Returns: the corresponding datastore.Key object.

  Raises: grpc.Error, if the key is invalid.
  """
  maybe_project_id = rest_key.get('partitionId', {}).get('projectId')
  if maybe_project_id and project_id and project_id != maybe_project_id:
    raise grpc.Error("INVALID_ARGUMENT",
                     "mismatched databases within request: %s vs. %s" %
                     (project_id, maybe_project_id))

  path_components = []
  for i, item in enumerate(rest_key['path']):
    path_components.append(item['kind'])
    # An incomplete key semantically doesn't have an ID on the last
    # element in the path; REST implements it this way but App Engine
    # expects it to be set (because you can't make a key with neither ID
    # nor name) and simply ignores the value.  Additionally, REST uses
    # string IDs (presumably due to JSON limitations) whereas App Engine
    # uses longs.
    if incomplete and i == len(rest_key['path']) - 1:   # last item in path
      if 'name' in item or 'id' in item:
        raise grpc.Error("INVALID_ARGUMENT",
                         "Final key path element must not be complete.")
      path_components.append(1)
    else:
      # TODO(benkraft): Build utils to do this kind of schema checking in a
      # more consistent way.
      if 'name' in item and 'id' in item:
        raise grpc.Error("INVALID_ARGUMENT",
                         "Key path element cannot have both id and name.")
      elif 'name' in item:
        path_components.append(item['name'])
      elif 'id' in item:
        path_components.append(long(item['id']))
      else:
        raise grpc.Error("INVALID_ARGUMENT",
                         "Key path element must have either id or name.")

  namespace = rest_key.get('partitionId', {}).get('namespaceId')
  return datastore.Key.from_path(*path_components, namespace=namespace)


def gae_to_rest(gae_key):
  """Translate a datastore.Key into a REST API style key.

  Note that this includes fairly little validation, as the datastore.Key
  constructor does most of it for us (and datastore.Keys usually come from
  appengine anyway).  In particular, it does not validate whether the key is
  complete.

  Arguments:
    rest_key: A datastore.Key object.
    project_id: The project ID for this request.  (We validate this against the
        key's project ID.)

  Returns: The corresponding REST API key object, JSON-serializably, per:
      https://cloud.google.com/datastore/docs/reference/data/rest/v1/Key
  """
  # REST doesn't use the "dev~" prefix on app-name.
  partition_id = {'projectId': gae_key.app().split('~', 1)[-1]}
  if gae_key.namespace():
    partition_id['namespaceId'] = gae_key.namespace()

  reversed_path_items = []
  while gae_key:
    item = {'kind': gae_key.kind()}
    if gae_key.id():
      item['id'] = str(gae_key.id())
    if gae_key.name():
      item['name'] = gae_key.name()
    reversed_path_items.append(item)
    gae_key = gae_key.parent()

  return {
    'partitionId': partition_id,
    'path': list(reversed(reversed_path_items)),
  }
