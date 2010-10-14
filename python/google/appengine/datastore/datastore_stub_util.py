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

"""Utility functions shared between the file and sqlite datastore stubs."""


import md5

from google.appengine.api import datastore_types
from google.appengine.api.datastore_errors import BadRequestError
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_pb
from google.appengine.runtime import apiproxy_errors


def ValidateQuery(query, filters, orders, max_query_components):
  """Validate a datastore query with normalized filters, orders.

  Raises an ApplicationError when any of the following conditions are violated:
  - transactional queries have an ancestor
  - queries that are not too large
    (sum of filters, orders, ancestor <= max_query_components)
  - ancestor (if any) app and namespace match query app and namespace
  - kindless queries only filter on __key__ and only sort on __key__ ascending
  - multiple inequality (<, <=, >, >=) filters all applied to the same property
  - filters on __key__ compare to a reference in the same app and namespace as
    the query
  - if an inequality filter on prop X is used, the first order (if any) must
    be on X

  Args:
    query: query to validate
    filters: normalized (by datastore_index.Normalize) filters from query
    orders: normalized (by datastore_index.Normalize) orders from query
    max_query_components: limit on query complexity
  """

  def BadRequest(message):
    raise apiproxy_errors.ApplicationError(
        datastore_pb.Error.BAD_REQUEST, message)

  key_prop_name = datastore_types._KEY_SPECIAL_PROPERTY
  unapplied_log_timestamp_us_name = (
      datastore_types._UNAPPLIED_LOG_TIMESTAMP_SPECIAL_PROPERTY)

  if query.has_transaction():
    if not query.has_ancestor():
      BadRequest('Only ancestor queries are allowed inside transactions.')

  num_components = len(filters) + len(orders)
  if query.has_ancestor():
    num_components += 1
  if num_components > max_query_components:
    BadRequest('query is too large. may not have more than %s filters'
               ' + sort orders ancestor total' % max_query_components)

  if query.has_ancestor():
    ancestor = query.ancestor()
    if query.app() != ancestor.app():
      BadRequest('query app is %s but ancestor app is %s' %
                 (query.app(), ancestor.app()))
    if query.name_space() != ancestor.name_space():
      BadRequest('query namespace is %s but ancestor namespace is %s' %
                 (query.name_space(), ancestor.name_space()))

  ineq_prop_name = None
  for filter in filters:
    if filter.property_size() != 1:
      BadRequest('Filter has %d properties, expected 1' %
                 filter.property_size())

    prop = filter.property(0)
    prop_name = prop.name().decode('utf-8')

    if prop_name == key_prop_name:
      if not prop.value().has_referencevalue():
        BadRequest('%s filter value must be a Key' % key_prop_name)
      ref_val = prop.value().referencevalue()
      if ref_val.app() != query.app():
        BadRequest('%s filter app is %s but query app is %s' %
                   (key_prop_name, ref_val.app(), query.app()))
      if ref_val.name_space() != query.name_space():
        BadRequest('%s filter namespace is %s but query namespace is %s' %
                   (key_prop_name, ref_val.name_space(), query.name_space()))

    if (filter.op() in datastore_index.INEQUALITY_OPERATORS and
        prop_name != unapplied_log_timestamp_us_name):
      if ineq_prop_name is None:
        ineq_prop_name = prop_name
      elif ineq_prop_name != prop_name:
        BadRequest(('Only one inequality filter per query is supported.  '
                    'Encountered both %s and %s') % (ineq_prop_name, prop_name))

  if ineq_prop_name is not None and orders:
    first_order_prop = orders[0].property().decode('utf-8')
    if first_order_prop != ineq_prop_name:
      BadRequest('The first sort property must be the same as the property '
                 'to which the inequality filter is applied.  In your query '
                 'the first sort property is %s but the inequality filter '
                 'is on %s' % (first_order_prop, ineq_prop_name))

  if not query.has_kind():
    for filter in filters:
      prop_name = filter.property(0).name().decode('utf-8')
      if (prop_name != key_prop_name and
          prop_name != unapplied_log_timestamp_us_name):
        BadRequest('kind is required for non-__key__ filters')
    for order in orders:
      prop_name = order.property().decode('utf-8')
      if not (prop_name == key_prop_name and
              order.direction() is datastore_pb.Query_Order.ASCENDING):
        BadRequest('kind is required for all orders except __key__ ascending')


def ParseKeyFilteredQuery(filters, orders):
  """Parse queries which only allow filters and ascending-orders on __key__.

  Raises exceptions for illegal queries.
  Args:
    filters: the normalized filters of a query.
    orders: the normalized orders of a query.
  Returns:
     The key range (start, start_inclusive, end, end_inclusive) requested
     in the query.
  """
  remaining_filters = []
  start_key = None
  start_inclusive = False
  end_key = None
  end_inclusive = False
  key_prop = datastore_types._KEY_SPECIAL_PROPERTY
  for f in filters:
    op = f.op()
    if not (f.property_size() == 1 and
            f.property(0).name() == key_prop and
            not (op == datastore_pb.Query_Filter.IN or
                 op == datastore_pb.Query_Filter.EXISTS)):
      remaining_filters.append(f)
      continue

    val = f.property(0).value()
    if not val.has_referencevalue():
      raise BadRequestError('__key__ kind must be compared to a key')
    limit = datastore_types.FromReferenceProperty(val)

    if op == datastore_pb.Query_Filter.LESS_THAN:
      if end_key is None or limit <= end_key:
        end_key = limit
        end_inclusive = False
    elif (op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL or
          op == datastore_pb.Query_Filter.EQUAL):
      if end_key is None or limit < end_key:
        end_key = limit
        end_inclusive = True

    if op == datastore_pb.Query_Filter.GREATER_THAN:
      if start_key is None or limit >= start_key:
        start_key = limit
        start_inclusive = False
    elif (op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL or
          op == datastore_pb.Query_Filter.EQUAL):
      if start_key is None or limit > start_key:
        start_key = limit
        start_inclusive = True

  remaining_orders = []
  for o in orders:
    if not (o.direction() == datastore_pb.Query_Order.ASCENDING and
            o.property() == datastore_types._KEY_SPECIAL_PROPERTY):
      remaining_orders.append(o)
    else:
      break

  if remaining_filters:
    raise BadRequestError(
        'Only comparison filters on ' + key_prop + ' supported')
  if remaining_orders:
    raise BadRequestError('Only ascending order on ' + key_prop + ' supported')

  return (start_key, start_inclusive, end_key, end_inclusive)


def ParseKindQuery(query, filters, orders):
  """Parse __kind__ (schema) queries.

  Raises exceptions for illegal queries.
  Args:
    query: A Query PB.
    filters: the normalized filters from query.
    orders: the normalized orders from query.
  Returns:
     The kind range (start, start_inclusive, end, end_inclusive) requested
     in the query.
  """
  if query.has_ancestor():
    raise BadRequestError('ancestor queries not allowed')

  start_kind, start_inclusive, end_kind, end_inclusive = ParseKeyFilteredQuery(
      filters, orders)

  return (_KindKeyToString(start_kind), start_inclusive,
          _KindKeyToString(end_kind), end_inclusive)


def _KindKeyToString(key):
  """Extract kind name from __kind__ key.

  Raises an ApplicationError if the key is not of the form '__kind__'/name.

  Args:
    key: a key for a __kind__ instance, or a false value.
  Returns:
    kind specified by key, or key if key is a false value.
  """
  if not key:
    return key
  key_path = key.to_path()
  if (len(key_path) == 2 and key_path[0] == '__kind__' and
      isinstance(key_path[1], basestring)):
    return key_path[1]
  raise BadRequestError('invalid Key for __kind__ table')


def ParseNamespaceQuery(query, filters, orders):
  """Parse __namespace__  queries.

  Raises exceptions for illegal queries.
  Args:
    query: A Query PB.
    filters: the normalized filters from query.
    orders: the normalized orders from query.
  Returns:
     The kind range (start, start_inclusive, end, end_inclusive) requested
     in the query.
  """
  if query.has_ancestor():
    raise BadRequestError('ancestor queries not allowed')

  start_kind, start_inclusive, end_kind, end_inclusive = ParseKeyFilteredQuery(
      filters, orders)

  return (_NamespaceKeyToString(start_kind), start_inclusive,
          _NamespaceKeyToString(end_kind), end_inclusive)

def _NamespaceKeyToString(key):
  """Extract namespace name from __namespace__ key.

  Raises an ApplicationError if the key is not of the form '__namespace__'/name
  or '__namespace__'/_EMPTY_NAMESPACE_ID.

  Args:
    key: a key for a __namespace__ instance, or a false value.
  Returns:
    namespace specified by key, or key if key is a false value.
  """
  if not key:
    return key
  key_path = key.to_path()
  if len(key_path) == 2 and key_path[0] == '__namespace__':
    if key_path[1] == datastore_types._EMPTY_NAMESPACE_ID:
      return ''
    if isinstance(key_path[1], basestring):
      return key_path[1]
  raise BadRequestError('invalid Key for __namespace__ table')


def SynthesizeUserId(email):
  """Return a synthetic user ID from an email address.

  Note that this is not the same user ID found in the production system.

  Args:
    email: An email address.

  Returns:
    A string userid derived from the email address.
  """
  user_id_digest = md5.new(email.lower()).digest()
  user_id = '1' + ''.join(['%02d' % ord(x) for x in user_id_digest])[:20]
  return user_id


def FillUsersInQuery(filters):
  """Fill in a synthetic user ID for all user properties in a set of filters.

  Args:
    filters: The normalized filters from query.
  """
  for filter in filters:
    for property in filter.property_list():
      FillUser(property)


def FillUser(property):
  """Fill in a synthetic user ID for a user properties.

  Args:
    property: A Property which may have a user value.
  """
  if property.value().has_uservalue():
    uid = SynthesizeUserId(property.value().uservalue().email())
    if uid:
      property.mutable_value().mutable_uservalue().set_obfuscated_gaiaid(uid)
