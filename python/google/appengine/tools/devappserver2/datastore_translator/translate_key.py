"""Translation of keys between REST and App Engine APIs.

NOTE(benkraft): One of the most confusing parts of key-translation is the
handling of incomplete keys, which are keys where the name/ID is omitted, and
left to be auto-assigned by datastore.  In REST, these are handled
consistently: the field is omitted when applicable.  But in GAE, they're an
inconsistent mess.  In particular:
- datastore.Key.from_path() requires an ID be passed, although any integer is
  valid, including negative or zero values (which are invalid keys).  (It is
  possible to construct an invalid Key by constructing the reference
  (_Key__reference) by hand, like ndb does, but that's more work.)
- AllocateIds(), which requires an incomplete key (when size is set),
  explicitly forbids a zero ID but allows any nonzero value.
- the datastore.Entity constructor checks at construction time that the passed
  ID is positive, and leaves it unset (None) for incomplete keys.
Furthermore, Keys are immutable so it's not convenient to fix up a value just
before passing it to the API.  To allow flexible handling of this mess, we
represent an incomplete key in GAE as one with a negative ID.  This allows us
to pass around invalid keys just fine, and to use them for AllocateIds without
modification, but we can check for the sentinel value when constructing an
Entity (which requires destructuring the key anyway).
"""
from __future__ import absolute_import

from google.appengine.api import datastore
from google.appengine.tools.devappserver2.datastore_translator import grpc
from google.appengine.tools.devappserver2.datastore_translator import util


def rest_partition_to_gae_namespace(partition_id, project_id=None):
  """Validate a REST PartitionId and extract the namespace.

  REST uses a "PartitionId" structure:
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/PartitionId
  which includes both a project ID and an appengine-style namespace ID.  This
  function extracts the latter (and validates the former, if possible).

  Arguments:
    partition_id: REST structure as documented above.  May be None, for
        convenience of callers.
    project_id: The current project ID, if known; this will be validated
        against the input.
  """

  partition_id = partition_id or {}
  maybe_project_id = partition_id.get('projectId')
  if maybe_project_id and project_id and project_id != maybe_project_id:
    raise grpc.Error("INVALID_ARGUMENT",
                     "mismatched databases within request: %s vs. %s" %
                     (project_id, maybe_project_id))

  return partition_id.get('namespaceId')


def rest_to_gae(rest_key, project_id=None, incomplete=False):
  """Translate a REST API style key into a datastore.Key.

  Arguments:
    rest_key: The REST API's key object, parsed from JSON.  Documented at:
        https://cloud.google.com/datastore/docs/reference/data/rest/v1/Key
    project_id: The project ID for this request, or None.  (If set, we validate
        this against the key's project ID; if not we infer it from environ.)
    incomplete: True if this must be an incomplete key, i.e. one to which the
        datastore will assign the ID of the final path item, such as in an
        AllocateIds call; False (default) if it must not be; None if either is
        allowable.  See top-of-file NOTE for more on how we represent these.

  Returns: the corresponding datastore.Key object.

  Raises: grpc.Error, if the key is invalid.
  """
  namespace = rest_partition_to_gae_namespace(
    rest_key.get('partitionId'), project_id=project_id)

  path_components = []
  for i, item in enumerate(rest_key['path']):
    path_components.append(item['kind'])
    # An incomplete key semantically doesn't have an ID on the last
    # element in the path; REST implements it this way but App Engine
    # expects it to be set (because you can't make a key with neither ID
    # nor name) and simply ignores the value.  Additionally, REST uses
    # string IDs (presumably due to JSON limitations) whereas App Engine
    # uses longs.
    is_last_element = (i == len(rest_key['path']) - 1)
    field, id_or_name = util.get_matching_key(
      item, {'id', 'name'}, 'Key path element',
      required=(incomplete is False or not is_last_element))
    if field is None:
      # -1 is a sentinel, which some of our code checks, where the appengine
      # APIs are inconsistent in how they want things.
      path_components.append(-1)
    elif incomplete and is_last_element:
      raise grpc.Error("INVALID_ARGUMENT",
                       "Final key path element must not be complete.")
    else:
      if field == 'id':
        id_or_name = long(id_or_name)
      path_components.append(id_or_name)

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
