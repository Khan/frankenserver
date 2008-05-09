#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""The Python datastore admin API for managing indices and schemas.
"""



from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_pb
from google.appengine.runtime import apiproxy_errors
from google.appengine.datastore import entity_pb

_LOCAL_APP_ID = datastore_types._LOCAL_APP_ID


_DIRECTION_MAP = {
    'asc':        entity_pb.Index_Property.ASCENDING,
    'ascending':  entity_pb.Index_Property.ASCENDING,
    'desc':       entity_pb.Index_Property.DESCENDING,
    'descending': entity_pb.Index_Property.DESCENDING,
    }


def GetSchema(_app=_LOCAL_APP_ID):
  """Infers an app's schema from the entities in the datastore.

  Note that the PropertyValue PBs in the returned EntityProtos are empty
  placeholders, so they may cause problems if you try to convert them to
  python values with e.g. datastore_types. In particular, user values will
  throw UserNotFoundError because their email and auth domain fields will be
  empty.

  Returns:
    list of entity_pb.EntityProto, with kind and property names and types
  """
  req = api_base_pb.StringProto()
  req.set_value(_app)
  resp = datastore_pb.Schema()

  _Call('GetSchema', req, resp)
  return resp.kind_list()


def GetIndices(_app=_LOCAL_APP_ID):
  """Fetches all composite indices in the datastore for this app.

  Returns:
    list of entity_pb.CompositeIndex
  """
  req = api_base_pb.StringProto()
  req.set_value(_app)
  resp = datastore_pb.CompositeIndices()
  try:
    apiproxy_stub_map.MakeSyncCall('datastore_v3', 'GetIndices', req, resp)
  except apiproxy_errors.ApplicationError, err:
    raise datastore._ToDatastoreError(err)

  return resp.index_list()


def CreateIndex(index):
  """Creates a new composite index in the datastore for this app.

  Args:
    index: entity_pb.CompositeIndex

  Returns:
    int, the id allocated to the index
  """
  resp = api_base_pb.Integer64Proto()
  _Call('CreateIndex', index, resp)
  return resp.value()


def UpdateIndex(index):
  """Updates an index's status. The entire index definition must be present.

  Args:
    index: entity_pb.CompositeIndex
  """
  _Call('UpdateIndex', index, api_base_pb.VoidProto())


def DeleteIndex(index):
  """Deletes an index. The entire index definition must be present.

  Args:
    index: entity_pb.CompositeIndex
  """
  _Call('DeleteIndex', index, api_base_pb.VoidProto())


def _Call(call, req, resp):
  """Generic method for making a datastore API call.

  Args:
    call: string, the name of the RPC call
    req: the request PB. if the app_id field is not set, it defaults to the
      local app.
    resp: the response PB
  """
  if hasattr(req, 'app_id') and not req.app_id():
    req.set_app_id(_LOCAL_APP_ID)

  try:
    apiproxy_stub_map.MakeSyncCall('datastore_v3', call, req, resp)
  except apiproxy_errors.ApplicationError, err:
    raise datastore._ToDatastoreError(err)


def IndexDefinitionToProto(app_id, index_definition):
  """Transform individual Index definition to protocol buffer.

  Args:
    app_id: Application id for new protocol buffer CompositeIndex.
    index_definition: datastore_index.Index object to transform.

  Returns:
    New entity_pb.CompositeIndex with default values set and index
    information filled in.
  """
  proto = entity_pb.CompositeIndex()

  proto.set_app_id(app_id)
  proto.set_id(0)
  proto.set_state(entity_pb.CompositeIndex.WRITE_ONLY)

  definition_proto = proto.mutable_definition()
  definition_proto.set_entity_type(index_definition.kind)
  definition_proto.set_ancestor(index_definition.ancestor)

  if index_definition.properties is not None:
    for prop in index_definition.properties:
      prop_proto = definition_proto.add_property()
      prop_proto.set_name(prop.name)
      prop_proto.set_direction(_DIRECTION_MAP[prop.direction])

  return proto


def IndexDefinitionsToProtos(app_id, index_definitions):
  """Transform multiple index definitions to composite index records

  Args:
    app_id: Application id for new protocol buffer CompositeIndex.
    index_definition: A list of datastore_index.Index objects to transform.

  Returns:
    A list of tranformed entity_pb.Compositeindex entities with default values
    set and index information filled in.
  """
  return [IndexDefinitionToProto(app_id, index)
          for index in index_definitions]


def ProtoToIndexDefinition(proto):
  """Transform individual index protocol buffer to index definition.

  Args:
    proto: An instance of entity_pb.CompositeIndex to transform.

  Returns:
    A new instance of datastore_index.Index.
  """
  properties = []
  proto_index = proto.definition()
  for prop_proto in proto_index.property_list():
    prop_definition = datastore_index.Property(name=prop_proto.name())
    if prop_proto.direction() == entity_pb.Index_Property.DESCENDING:
      prop_definition.direction = 'descending'
    properties.append(prop_definition)

  index = datastore_index.Index(kind=proto_index.entity_type(),
                                properties=properties)
  if proto_index.ancestor():
    index.ancestor = True
  return index

def ProtosToIndexDefinitions(protos):
  """Transform multiple index protocol buffers to index definitions.

  Args:
    A list of entity_pb.Index records.
  """
  return [ProtoToIndexDefinition(definition) for definition in protos]
