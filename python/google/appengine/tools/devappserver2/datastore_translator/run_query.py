"""Translates a REST-style query into a datastore query, and executes it.

This is the bulk of the implementation of the REST runQuery call:
  https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery
This call has a lot of different options and such to handle; and for better or
worse the translation and execution are fairly tightly coupled so this file
handles both.
"""
from __future__ import absolute_import

from google.appengine.api import datastore
from google.appengine.tools.devappserver2.datastore_translator import grpc
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_entity)
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_value)


# Mapping from REST operator name to GAE symbol.
_OPERATORS = {
  'LESS_THAN': '<',
  'LESS_THAN_OR_EQUAL': '<=',
  'GREATER_THAN': '>',
  'GREATER_THAN_OR_EQUAL': '>=',
  'EQUAL': '=',
}


def _translate_filter(rest_filter):
  """Translate a REST-style filter into a GAE filter-dict.

  REST represents filters with the following object:
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery#Filter
  while GAE wants a dict of db-style filter keys (e.g. 'property_name =') to
  values.  This function does the translation.

  HACK(benkraft): To handle ancestor queries (which REST represents as a
  filter, but GAE does totally differently) in a convenient and consistent way
  we simply make a bogus filter key, 'ancestor', which the caller should pop
  off before passing the remaining filters to datastore.Query.
  """
  if not rest_filter:
    return {}

  property_filter = rest_filter.get('propertyFilter')
  composite_filter = rest_filter.get('compositeFilter')
  if not (bool(property_filter) ^ bool(composite_filter)):
    raise grpc.Error('INVALID_ARGUMENT',
                     'Must pass exactly one of propertyFilter'
                     'and compositeFilter')

  if property_filter:
    op = property_filter['op']
    prop = property_filter['property']['name']
    val, is_indexed = translate_value.rest_to_gae(property_filter['value'])
    if not is_indexed:
      # This is kind of a bogus error -- we know nothing about whether the
      # actual values in the datastore are indexed, we just know that the
      # caller has said "query for this unindexed value" which makes no sense.
      # But clearly they are doing something wrong, and prod errors, so we do.
      raise grpc.Error('INVALID_ARGUMENT',
                       'query filter value must be indexed')

    if op == 'HAS_ANCESTOR':
      if prop != '__key__':
        raise grpc.Error('INVALID_ARGUMENT',
                         'ancestor queries must use __key__, not %s' % prop)
      elif not isinstance(val, datastore.Key):
        raise grpc.Error('INVALID_ARGUMENT',
                         'ancestor queries must pass a key, not a %s'
                         % type(val))
      return {'ancestor': val}

    else:
      if op not in _OPERATORS:
        raise grpc.Error('INVALID_ARGUMENT', 'unknown op %s' % op)
      return {'%s %s' % (prop, _OPERATORS[op]): val}

  else:  # composite filter
    op = composite_filter['op']
    if op != 'AND':   # AND is the only valid op at this time.
      raise grpc.Error('INVALID_ARGUMENT', 'unknown op %s' % op)

    retval = {}
    for subfilter in composite_filter['filters']:
      translated_subfilter = _translate_filter(subfilter)
      common_keys = set(retval) & set(translated_subfilter)
      if common_keys:
        raise grpc.Error('INVALID_ARGUMENT',
                         'multiple filters for %s' % ', '.join(common_keys))

      retval.update(translated_subfilter)
    return retval


def _translate_ordering(ordering):
  """Translate a REST-style ordering to a GAE ordering tuple.

  REST uses the PropertyOrder structure:
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery#PropertyOrder
  whereas GAE uses a tuple (field_name, direction).
  """
  raw_direction = ordering.get('direction', 'ASCENDING')
  if raw_direction == 'DESCENDING':
    direction = datastore.Query.DESCENDING
  elif raw_direction == 'ASCENDING':
    direction = datastore.Query.ASCENDING
  else:
    raise grpc.Error('INVALID_ARGUMENT',
                     'invalid ordering-direction %s' % raw_direction)
  return (ordering['property']['name'], direction)


def _get_current_rest_cursor(gae_query):
  """Given a datastore.Query, get the cursor for its current iterator position.

  This is a bit weird: you have to have called gae_query.Run(), which returns
  an iterable, and then once you have you can call this function and we'll get
  you the cursor after the last item over which you iterated.
  """
  return translate_entity.gae_to_rest_cursor(gae_query.GetCursor())


def translate_and_execute(query, namespace, consistency):
  """Translate the given query, execute it, and return the result batch.

  This accepts the REST Query structure, as documented at
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery#Query
  and returns the QueryResultBatch type, per
    https://cloud.google.com/datastore/docs/reference/data/rest/v1/projects/runQuery#QueryResultBatch
  """

  # STEP 1: Grab all the options and get them into the form that GAE wants.
  projection = [prop['property']['name']
                for prop in query.get('projection', [])] or None
  keys_only = False
  if projection == ['__key__']:
    # REST implements keys-only queries as a projection on __key__.
    keys_only = True
    projection = None

  if query.get('distinctOn'):
    # TODO(benkraft): Implement distinctOn (we'd have to do it ourselves,
    # except where it exactly matches projection).
    raise grpc.Error('UNIMPLEMENTED', 'TODO(benkraft): Implement distinctOn')

  kinds = [kind['name'] for kind in query.get('kind', [])]
  if len(kinds) > 1:
    raise grpc.Error('INVALID_ARGUMENT',
                     'multi-kind queries are not supported')
  kind = kinds[0] if kinds else None

  filters = _translate_filter(query.get('filter'))
  ancestor = filters.pop('ancestor', None)

  orderings = map(_translate_ordering, query.get('order', []))

  offset = int(query.get('offset', 0))
  limit = int(query['limit']) if 'limit' in query else None

  start_cursor = translate_entity.rest_to_gae_cursor(query.get('startCursor'))
  end_cursor = translate_entity.rest_to_gae_cursor(query.get('endCursor'))

  # STEP 2: Build the query, and then get the iterator.
  gae_query = datastore.Query(
    namespace=namespace,
    kind=kind,
    filters=filters,
    cursor=start_cursor,
    end_cursor=end_cursor,
    keys_only=keys_only,
    projection=projection)
  if ancestor:
    gae_query = gae_query.Ancestor(ancestor)
  if orderings:
    gae_query = gae_query.Order(*orderings)

  iterator = gae_query.Run(offset=offset, limit=limit, read_policy=consistency)

  # STEP 3: Build the results.
  # We have to interleave the iteration over the query results into the
  # translation so we can grab the cursor at various points in the query.
  batch = {'entityResults': []}

  if offset:
    batch['skippedResults'] = offset
    batch['skippedCursor'] = _get_current_rest_cursor(gae_query)

  if keys_only:
    translator = translate_entity.gae_key_to_rest_entity_result
    batch['entityResultType'] = 'KEY_ONLY'
  else:
    translator = translate_entity.gae_to_rest_entity_result
    if projection:
      batch['entityResultType'] = 'PROJECTION'
    else:
      batch['entityResultType'] = 'FULL'

  # This is where we actually fetch the results.
  for result in iterator:
    batch['entityResults'].append(
      translator(result, _get_current_rest_cursor(gae_query)))

  batch['endCursor'] = _get_current_rest_cursor(gae_query)

  # In general, we handle everything as one batch, unless a limit was set, so
  # we never return NOT_FINISHED.  Also, sometimes we just conservatively
  # guess there may be more results; clients should handle this.
  # TODO(benkraft): Batch if the response would get huge.
  # TODO(benkraft): In the MORE_RESULTS_AFTER cases, do another query (or
  # extend the original one) to check if there actually are more results.
  if limit is not None and len(batch['entityResults']) >= limit:
    batch['moreResults'] = 'MORE_RESULTS_AFTER_LIMIT'
  elif end_cursor is not None:
    batch['moreResults'] = 'MORE_RESULTS_AFTER_CURSOR'
  else:
    batch['moreResults'] = 'NO_MORE_RESULTS'

  return batch
