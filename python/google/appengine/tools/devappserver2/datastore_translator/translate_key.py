"""Translation of keys between REST and App Engine APIs."""
from __future__ import absolute_import

from google.appengine.api import datastore
from google.appengine.tools.devappserver2.datastore_translator import grpc


def rest_to_gae(rest_key, project_id, incomplete=False):
  """Translate a REST API style key into a datastore.Key.

  Arguments:
    rest_key: The REST API's key object, parsed from JSON.  Documented at:
        https://cloud.google.com/datastore/docs/reference/data/rest/v1/Key
    project_id: The project ID for this request.  (We validate this against the
        key's project ID.)
    incomplete: True if this is an incomplete key, i.e. one to which the
        datastore will assign the ID of the final path item, such as in an
        AllocateIds call.  Note that in REST-land, incomplete keys simply omit
        the 'id' or 'name' value, but in App Engine it is set to a bogus value.

  Returns: the corresponding datastore.Key object.

  Raises: grpc.Error, if the key is invalid.
  """
  maybe_project_id = rest_key.get('partitionId', {}).get('projectId')
  if maybe_project_id and project_id != maybe_project_id:
    raise grpc.Error("INVALID_ARGUMENT",
                     "mismatched databases within request: %s vs. %s" %
                     (project_id, maybe_project_id))

  path_components = []
  for i, item in enumerate(rest_key['path']):
    path_components.append(item['kind'])
    # An AllocateIds request semantically doesn't have an ID on the last
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
        path_components.append(item['id'])
      else:
        raise grpc.Error("INVALID_ARGUMENT",
                         "Key path element must have either id or name.")

  # The REST API is structured such that you pass a bunch of incomplete
  # keys; in App Engine instead you pass a single incomplete key and a
  # count of how big a range you'd like.
  # TODO(benkraft): Do these requests async (if there are multiple).
  namespace = rest_key.get('partitionId', {}).get('namespaceId')
  return datastore.Key.from_path(*path_components, namespace=namespace)
