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


class Property(validation.Validated):
  """Representation for an individual property of an index.

  Attributes:
    name: Name of attribute to sort by.
    direction: Direction of sort.
  """

  ATTRIBUTES = {
      'name': validation.TYPE_STR,
      'direction': validation.Options(('asc', ('ascending',)),
                                      ('desc', ('descending',)),
                                      default='asc'),
      }


class Index(validation.Validated):
  """Individual index definition.

  Order of the properties properties determins a given indixes sort priority.

  Attributes:
    kind: Datastore kind that index belongs to.
    ancestors: Include ancestors in index.
    properties: Properties to sort on.
  """

  ATTRIBUTES = {
      'kind': validation.TYPE_STR,
      'ancestor': validation.Type(bool, default=False),
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


def ParseIndexDefinitions(document):
  """Parse an individual index definitions document from string or stream.

  Args:
    document: Yaml document as a string or file-like stream.

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
    entries, in the order given in the query.  Exceptions: (a) if
    there is a Filter entry with an inequality operator that matches
    the first Order entry, the first order pair is omitted (or,
    equivalently, in this case the inequality pair is omitted); (b) if
    an Order entry corresponds to an equality filter, it is ignored
    (since there will only ever be one value returned).

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
    A tuple of the form (required, kind, ancestor, (prop1, prop2, ...), neq):
      required: boolean, whether the index is required
      kind: the kind or None;
      ancestor: True if this is an ancestor query;
      prop1, prop2, ...: tuples of the form (name, direction) where:
        name: a property name;
        direction: datastore_pb.Query_Order.ASCENDING or ...DESCENDING;
      neq: the number of prop tuples corresponding to equality filters.
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

  if ancestor and not kind and not filters and not orders:
    required = False

  eq_filters = [f for f in filters if f.op() in EQUALITY_OPERATORS]
  ineq_filters = [f for f in filters if f.op() in INEQUALITY_OPERATORS]
  exists_filters = [f for f in filters if f.op() in EXISTS_OPERATORS]
  assert (len(eq_filters) + len(ineq_filters) +
          len(exists_filters)) == len(filters), 'Not all filters used'

  if (kind and eq_filters and not ineq_filters and not exists_filters and
      not orders):
    names = set(f.property(0).name() for f in eq_filters)
    if not names.intersection(datastore_types._SPECIAL_PROPERTIES):
      required = False

  ineq_property = None
  if ineq_filters:
    ineq_property = ineq_filters[0].property(0).name()
    for filter in ineq_filters:
      assert filter.property(0).name() == ineq_property

  new_orders = []
  for order in orders:
    name = order.property()
    for filter in eq_filters:
      if filter.property(0).name() == name:
        break
    else:
      new_orders.append(order)
  orders = new_orders

  props = []

  for f in eq_filters:
    prop = f.property(0)
    props.append((prop.name(), ASCENDING))

  props.sort()

  if ineq_property:
    if orders:
      assert ineq_property == orders[0].property()
    else:
      props.append((ineq_property, ASCENDING))

  for order in orders:
    props.append((order.property(), order.direction()))

  for filter in exists_filters:
    prop = filter.property(0)
    prop_name = prop.name()
    for name, direction in props:
      if name == prop_name:
        break
    else:
      props.append((prop_name, ASCENDING))

  if kind and not ancestor and len(props) <= 1:
    required = False

    if props:
      prop, dir = props[0]
      if prop in datastore_types._SPECIAL_PROPERTIES and dir is DESCENDING:
        required = True

  unique_names = set(name for name, dir in props)
  if len(props) > 1 and len(unique_names) == 1:
    required = False

  return (required, kind, ancestor, tuple(props), len(eq_filters))


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
