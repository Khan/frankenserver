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




"""Primitives for dealing with datastore indexes.

Example index.yaml file:
------------------------

indexes:

- kind: Cat
  ancestor: no
  properties:
  - name: name
  - name: age
    direction: desc

- kind: Cat
  properties:
  - name: name
    direction: ascending
  - name: whiskers
    direction: descending

- kind: Store
  ancestor: yes
  properties:
  - name: business
    direction: asc
  - name: owner
    direction: asc
"""









from google.appengine.api import datastore_types
from google.appengine.api import validation
from google.appengine.api import yaml_errors
from google.appengine.api import yaml_object
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import entity_pb


class Property(validation.Validated):
  """Representation for an individual property of an index.

  Attributes:
    name: Name of attribute to sort by.
    direction: Direction of sort.
  """

  ATTRIBUTES = {
      'name': validation.Type(str, convert=False),
      'direction': validation.Options(('asc', ('ascending',)),
                                      ('desc', ('descending',)),
                                      default='asc'),
      }


class Index(validation.Validated):
  """Individual index definition.

  Order of the properties determines a given indexes sort priority.

  Attributes:
    kind: Datastore kind that index belongs to.
    ancestors: Include ancestors in index.
    properties: Properties to sort on.
  """

  ATTRIBUTES = {
      'kind': validation.Type(str, convert=False),
      'ancestor': validation.Type(bool, convert=False, default=False),
      'properties': validation.Optional(validation.Repeated(Property)),
      }


class IndexDefinitions(validation.Validated):
  """Top level for index definition file.

  Attributes:
    indexes: List of Index definitions.
  """

  ATTRIBUTES = {
      'indexes': validation.Optional(validation.Repeated(Index)),
      }


def ParseIndexDefinitions(document, open_fn=None):
  """Parse an individual index definitions document from string or stream.

  Args:
    document: Yaml document as a string or file-like stream.
    open_fn: Function for opening files. Unused.

  Raises:
    EmptyConfigurationFile when the configuration file is empty.
    MultipleConfigurationFile when the configuration file contains more than
    one document.

  Returns:
    Single parsed yaml file if one is defined, else None.
  """
  try:
    return yaml_object.BuildSingleObject(IndexDefinitions, document)
  except yaml_errors.EmptyConfigurationFile:
    return None


def ParseMultipleIndexDefinitions(document):
  """Parse multiple index definitions documents from a string or stream.

  Args:
    document: Yaml document as a string or file-like stream.

  Returns:
    A list of datstore_index.IndexDefinitions objects, one for each document.
  """
  return yaml_object.BuildObjects(IndexDefinitions, document)


def IndexDefinitionsToKeys(indexes):
  """Convert IndexDefinitions to set of keys.

  Args:
    indexes: A datastore_index.IndexDefinitions instance, or None.

  Returns:
    A set of keys constructed from the argument, each key being a
    tuple of the form (kind, ancestor, properties) where properties is
    a tuple of (name, direction) pairs, direction being ASCENDING or
    DESCENDING (the enums).
  """
  keyset = set()
  if indexes is not None:
    if indexes.indexes:
      for index in indexes.indexes:
        keyset.add(IndexToKey(index))
  return keyset


def IndexToKey(index):
  """Convert Index to key.

  Args:
    index: A datastore_index.Index instance (not None!).

  Returns:
    A tuple of the form (kind, ancestor, properties) where properties
    is a tuple of (name, direction) pairs, direction being ASCENDING
    or DESCENDING (the enums).
  """
  props = []
  if index.properties is not None:
    for prop in index.properties:
      if prop.direction == 'asc':
        direction = ASCENDING
      else:
        direction = DESCENDING
      props.append((prop.name, direction))
  return index.kind, index.ancestor, tuple(props)






ASCENDING = datastore_pb.Query_Order.ASCENDING
DESCENDING = datastore_pb.Query_Order.DESCENDING


EQUALITY_OPERATORS = set((datastore_pb.Query_Filter.EQUAL,
                          ))
INEQUALITY_OPERATORS = set((datastore_pb.Query_Filter.LESS_THAN,
                            datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL,
                            datastore_pb.Query_Filter.GREATER_THAN,
                            datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL,
                            ))
EXISTS_OPERATORS = set((datastore_pb.Query_Filter.EXISTS,
                        ))


_DIRECTION_MAP = {
    'asc':        entity_pb.Index_Property.ASCENDING,
    'ascending':  entity_pb.Index_Property.ASCENDING,
    'desc':       entity_pb.Index_Property.DESCENDING,
    'descending': entity_pb.Index_Property.DESCENDING,
    }

def Normalize(filters, orders, properties):
  """ Normalizes filter and order query components.

  The resulting components have the same effect as the given components if used
  in a query.

  Returns:
    (filter, orders) the reduced set of filters and orders
  """


  eq_properties = set()
  inequality_properties = set()


  for f in filters:
    if f.op() == datastore_pb.Query_Filter.IN and f.property_size() == 1:
      f.set_op(datastore_pb.Query_Filter.EQUAL)
    if f.op() in EQUALITY_OPERATORS:
      eq_properties.add(f.property(0).name())
    elif f.op() in INEQUALITY_OPERATORS:
      inequality_properties.add(f.property(0).name())

  eq_properties -= inequality_properties


  remove_set = eq_properties.copy()
  new_orders = []
  for o in orders:
    if o.property() not in remove_set:
      remove_set.add(o.property())
      new_orders.append(o)
  orders = new_orders

  remove_set.update(inequality_properties)


  new_filters = []
  for f in filters:
    if f.op() not in EXISTS_OPERATORS:
      new_filters.append(f)
      continue
    name = f.property(0).name()
    if name not in remove_set:
      remove_set.add(name)
      new_filters.append(f)


  for prop in properties:
    if prop not in remove_set:
      remove_set.add(prop)
      new_filter = datastore_pb.Query_Filter()
      new_filter.set_op(datastore_pb.Query_Filter.EXISTS)
      new_prop = new_filter.add_property()
      new_prop.set_name(prop)
      new_prop.set_multiple(False)
      new_prop.mutable_value()
      new_filters.append(new_filter)

  filters = new_filters




  if datastore_types.KEY_SPECIAL_PROPERTY in eq_properties:
    orders = []



  new_orders = []
  for o in orders:
    if o.property() == datastore_types.KEY_SPECIAL_PROPERTY:
      new_orders.append(o)
      break
    new_orders.append(o)
  orders = new_orders

  return (filters, orders)


def RemoveNativelySupportedComponents(filters, orders, properties):
  """ Removes query components that are natively supported by the datastore.

  The resulting filters and orders should not be used in an actual query.

  Returns
    (filters, orders) the reduced set of filters and orders
  """
  (filters, orders) = Normalize(filters, orders, properties)

  for f in filters:
    if f.op() in EXISTS_OPERATORS:



      return (filters, orders)



  has_key_desc_order = False
  if orders and orders[-1].property() == datastore_types.KEY_SPECIAL_PROPERTY:
    if orders[-1].direction() == ASCENDING:
      orders = orders[:-1]
    else:
      has_key_desc_order = True






  if not has_key_desc_order:
    for f in filters:
      if (f.op() in INEQUALITY_OPERATORS and
          f.property(0).name() != datastore_types.KEY_SPECIAL_PROPERTY):
        break
    else:
      filters = [f for f in filters
          if f.property(0).name() != datastore_types.KEY_SPECIAL_PROPERTY]

  return (filters, orders)


def CompositeIndexForQuery(query):
  """Return the composite index needed for a query.

  A query is translated into a tuple, as follows:

  - The first item is the kind string, or None if we're not filtering
    on kind (see below).

  - The second item is a bool giving whether the query specifies an
    ancestor.

  - After that come (property, ASCENDING) pairs for those Filter
    entries whose operator is EQUAL or IN.  Since the order of these
    doesn't matter, they are sorted by property name to normalize them
    in order to avoid duplicates.

  - After that comes at most one (property, ASCENDING) pair for a
    Filter entry whose operator is on of the four inequalities.  There
    can be at most one of these.

  - After that come all the (property, direction) pairs for the Order
    entries, in the order given in the query.  Exceptions:
      (a) if there is a Filter entry with an inequality operator that matches
          the first Order entry, the first order pair is omitted (or,
          equivalently, in this case the inequality pair is omitted).
      (b) if an Order entry corresponds to an equality filter, it is ignored
          (since there will only ever be one value returned).
      (c) if there is an equality filter on __key__ all orders are dropped
          (since there will be at most one result returned).
      (d) if there is an order on __key__ all further orders are dropped (since
          keys are unique).
      (e) orders on __key__ ASCENDING are dropped (since this is supported
          natively by the datastore).

  - Finally, if there are Filter entries whose operator is EXISTS, and
    whose property names are not already listed, they are added, with
    the direction set to ASCENDING.

  This algorithm should consume all Filter and Order entries.

  Additional notes:

  - The low-level implementation allows queries that don't specify a
    kind; but the Python API doesn't support this yet.

  - If there's an inequality filter and one or more sort orders, the
    first sort order *must* match the inequality filter.

  - The following indexes are always built in and should be suppressed:
    - query on kind only;
    - query on kind and one filter *or* one order;
    - query on ancestor only, without kind (not exposed in Python yet);
    - query on kind and equality filters only, no order (with or without
      ancestor).

  - While the protocol buffer allows a Filter to contain multiple
    properties, we don't use this.  It is only needed for the IN operator
    but this is (currently) handled on the client side, so in practice
    each Filter is expected to have exactly one property.

  Args:
    query: A datastore_pb.Query instance.

  Returns:
    A tuple of the form (required, kind, ancestor, properties).
      required: boolean, whether the index is required;
      kind: the kind or None;
      ancestor: True if this is an ancestor query;
      properties: A tuple consisting of any number of:
      - Sets of property names: Indicates these properties can appear in any
        order with any direction.
      - Tuples of (property name, direction) tuples. Indicating the properties
        must appear in the exact order with the given direction. direction can
        be None if direction does not matter.
  """
  required = True


  kind = query.kind()
  ancestor = query.has_ancestor()
  filters = query.filter_list()
  orders = query.order_list()



  for filter in filters:
    assert filter.op() != datastore_pb.Query_Filter.IN, 'Filter.op()==IN'
    nprops = len(filter.property_list())
    assert nprops == 1, 'Filter has %s properties, expected 1' % nprops

  if not kind:


    required = False

  filters, orders = RemoveNativelySupportedComponents(
      filters, orders, query.property_name_list())


  eq_filters = [f for f in filters if f.op() in EQUALITY_OPERATORS]
  ineq_filters = [f for f in filters if f.op() in INEQUALITY_OPERATORS]
  exists_filters = [f for f in filters if f.op() in EXISTS_OPERATORS]
  assert (len(eq_filters) + len(ineq_filters) +
          len(exists_filters)) == len(filters), 'Not all filters used'

  if (kind and not ineq_filters and not exists_filters and
      not orders):



    names = set(f.property(0).name() for f in eq_filters)
    if not names.intersection(datastore_types._SPECIAL_PROPERTIES):
      required = False



  ineq_property = None
  if ineq_filters:
    for filter in ineq_filters:
      if (filter.property(0).name() ==
          datastore_types._UNAPPLIED_LOG_TIMESTAMP_SPECIAL_PROPERTY):
        continue
      if not ineq_property:
        ineq_property = filter.property(0).name()
      else:
        assert filter.property(0).name() == ineq_property




  prefix = frozenset(f.property(0).name() for f in eq_filters)

  postfix_ordered = [(order.property(), order.direction()) for order in orders]

  postfix_unordered = frozenset(f.property(0).name() for f in exists_filters)


  if ineq_property:
    if orders:


      assert ineq_property == orders[0].property()
    else:
      postfix_ordered.append((ineq_property, None))

  property_count = len(prefix) + len(postfix_ordered) + len(postfix_unordered)
  if kind and not ancestor and property_count <= 1:


    required = False


    if postfix_ordered:
      prop, dir = postfix_ordered[0]
      if prop == datastore_types.KEY_SPECIAL_PROPERTY and dir is DESCENDING:
        required = True


  return (required, kind, ancestor,
          (prefix, tuple(postfix_ordered), postfix_unordered))


def GetRecommendedIndexProperties(properties):
  """Converts the properties returned by datastore_index.CompositeIndexForQuery
  into a recommended list of index properties and directions.

  All unordered components are sorted and assigned an ASCENDING direction. All
  ordered components with out a direction are assigned an ASCEDNING direction.

  Args:
    properties: See datastore_index.CompositeIndexForQuery

  Returns:
    A tuple of (name, direction) tuples where:
        name: a property name
        direction: datastore_pb.Query_Order.ASCENDING or ...DESCENDING
  """
  result = []
  for sub_list in properties:
    if isinstance(sub_list, (frozenset, set)):

      for prop in sorted(sub_list):
        result.append((prop, ASCENDING))
    else:


      for prop, dir in sub_list:
        result.append((prop, dir if dir is not None else ASCENDING))

  return tuple(result)


def MinimalCompositeIndexForQuery(query, index_defs):
  """Computes the minimal composite index for this query.

  Unlike datastore_index.CompositeIndexForQuery, this function takes into
  account indexes that already exist in the system.

  Args:
    query: the datastore_pb.Query to compute suggestions for
    index_defs: a list of datastore_index.Index objects that already exist.

  Returns:
    None if no index is needed, otherwise the minimal index in the form
  (is_most_efficient, kind, ancestor, properties). Where is_most_efficient is a
  boolean denoting if the suggested index is the most efficient (i.e. the one
  returned by datastore_index.CompositeIndexForQuery). kind, ancestor,
  and properties are the same variables returned by
  datastore_index.CompositeIndexForQuery.
  """

  required, kind, ancestor, props = CompositeIndexForQuery(query)

  if not required:
    return None



  prefix, postfix_ordered, postfix_unordered = props


  remaining_dict = {}

  for definition in index_defs:
    if (kind != definition.kind or

        (not ancestor and definition.ancestor)):
      continue

    _, _, index_props = IndexToKey(definition)





    postfix_split = len(index_props) - 1
    while (postfix_split >= 0 and
           index_props[postfix_split][0] in postfix_unordered):
      postfix_split -= 1
    postfix_split += 1

    index_postfix_unordered = index_props[postfix_split:]


    if set(prop for prop, dir in index_postfix_unordered) != postfix_unordered:
      continue


    postfix_start = postfix_split - len(postfix_ordered)
    if postfix_start < 0:
      continue

    index_postfix_ordered = index_props[postfix_start:postfix_split]
    match = True
    for (index_prop, index_dir), (prop, dir) in zip(index_postfix_ordered,
                                                    postfix_ordered):
      if index_prop != prop or (dir is not None and index_dir != dir):
        match = False
        break

    if not match:
      continue


    index_prefix = set(prop for prop, dir in index_props[:postfix_start])


    if index_prefix - prefix:
      continue




    index_postfix = tuple(index_postfix_ordered + index_postfix_unordered)
    remaining  = remaining_dict.get(index_postfix)
    if remaining is None:
      remaining = prefix.copy(), ancestor


    props_remaining, ancestor_remaining = remaining
    props_remaining = props_remaining - index_prefix
    if definition.ancestor:
      ancestor_remaining = False

    if not (props_remaining or ancestor_remaining):
      return None

    if (props_remaining, ancestor_remaining) == remaining:
      continue


    remaining_dict[index_postfix] = (props_remaining, ancestor_remaining)

  if not remaining_dict:
    return (True, kind, ancestor, props)

  def calc_cost(minimal_props, minimal_ancestor):
    result = len(minimal_props)
    if minimal_ancestor:
      result += 2


  minimal_postfix, remaining = remaining_dict.popitem()
  minimal_props, minimal_ancestor = remaining
  minimal_cost = calc_cost(minimal_props, minimal_ancestor)
  for index_postfix, (props_remaining, ancestor_remaining) in remaining_dict:
    cost = calc_cost(props_remaining, ancestor_remaining)
    if cost < minimal_cost:
      minimal_cost = cost
      minimal_postfix = index_postfix
      minimal_props = props_remaining
      minimal_ancestor = ancestor_remaining


  return False, kind, minimal_ancestor, (frozenset(minimal_props),
                                         minimal_postfix, frozenset())


def IndexYamlForQuery(kind, ancestor, props):
  """Return the composite index definition YAML needed for a query.

  The arguments are the same as the tuples returned by CompositeIndexForQuery,
  without the last neq element.

  Args:
    kind: the kind or None
    ancestor: True if this is an ancestor query, False otherwise
    prop1, prop2, ...: tuples of the form (name, direction) where:
        name: a property name;
        direction: datastore_pb.Query_Order.ASCENDING or ...DESCENDING;

  Returns:
    A string with the YAML for the composite index needed by the query.
  """
  yaml = []
  yaml.append('- kind: %s' % kind)
  if ancestor:
    yaml.append('  ancestor: yes')
  if props:
    yaml.append('  properties:')
    for name, direction in props:
      yaml.append('  - name: %s' % name)
      if direction == DESCENDING:
        yaml.append('    direction: desc')
  return '\n'.join(yaml)


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
    prop_definition = Property(name=prop_proto.name())
    if prop_proto.direction() == entity_pb.Index_Property.DESCENDING:
      prop_definition.direction = 'descending'
    properties.append(prop_definition)

  index = Index(kind=proto_index.entity_type(), properties=properties)
  if proto_index.ancestor():
    index.ancestor = True
  return index


def ProtosToIndexDefinitions(protos):
  """Transform multiple index protocol buffers to index definitions.

  Args:
    A list of entity_pb.Index records.
  """
  return [ProtoToIndexDefinition(definition) for definition in protos]
