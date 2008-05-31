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

"""GQL -- the SQL-like interface to the datastore.

Defines the GQL-based query class, which is a query mechanism
for the datastore which provides an alternative model for interacting with
data stored.
"""





import heapq
import logging
import re

from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types


LOG_LEVEL = logging.DEBUG - 1


def Execute(query_string, *args, **keyword_args):
  """Execute command to parse and run the query.

  Calls the query parser code to build a proto-query which is an
  unbound query. The proto-query is then bound into a real query and
  executed.

  Args:
    query_string: properly formatted GQL query string.
    args: rest of the positional arguments used to bind numeric references in
          the query.
    keyword_args: dictionary-based arguments (for named parameters).

  Returns:
    the result of running the query with *args.
  """
  app = keyword_args.pop('_app', None)
  proto_query = GQL(query_string, _app=app)
  return proto_query.Bind(args, keyword_args).Run()


class GQL(object):
  """A GQL interface to the datastore.

  GQL is a SQL-like language which supports more object-like semantics
  in a langauge that is familiar to SQL users. The language supported by
  GQL will change over time, but will start off with fairly simple
  semantics.

  - reserved words are case insensitive
  - names are case sensitive

  The syntax for SELECT is fairly straightforward:

  SELECT * FROM <entity>
    [WHERE <condition> [AND <condition> ...]]
    [ORDER BY <property> [ASC | DESC] [, <property> [ASC | DESC] ...]]
    [LIMIT [<offset>,]<count>]
    [OFFSET <offset>]
    [HINT (ORDER_FIRST | HINT FILTER_FIRST | HINT ANCESTOR_FIRST)]

  <condition> := <property> {< | <= | > | >= | =} <value>
  <condition> := ANCESTOR IS <entity or key>

  Currently the parser is LL(1) because of the simplicity of the grammer
  (as it is largely predictive with one token lookahead).

  The class is implemented using some basic regular expression tokenization
  to pull out reserved tokens and then the recursive descent parser will act
  as a builder for the pre-compiled query. This pre-compiled query is then
  bound to arguments before executing the query.

  Initially, three parameter passing mechanisms are supported when calling
  Execute():

  - Positional parameters
  Execute('SELECT * FROM Story WHERE Author = :1 AND Date > :2')
  - Named parameters
  Execute('SELECT * FROM Story WHERE Author = :author AND Date > :date')
  - Literals (numbers, and strings)
  Execute('SELECT * FROM Story WHERE Author = \'James\'')

  We will properly serialize and quote all values.

  It should also be noted that there are some caveats to the queries that can
  be expressed in the syntax. The parser will attempt to make these clear as
  much as possible, but some of the caveats include:
    - There is no OR operation. In most cases, you should prefer to use IN to
      express the idea of wanting data matching one of a set of properties.
    - You cannot express inequality operators on multiple different properties
    - You can only have one != operator per query (related to the previous
      rule).
    - The IN and != operators must be used carefully because they can
      dramatically raise the amount of work done by the datastore. As such,
      there is a limit on the number of elements you can use in IN statements.
      This limit is set fairly low. Currently, a max of 30 queries is allowed,
      which means 30 elements in a single IN clause. != translates into 2x the
      number of queries, and IN multiplies by the number of elements in the
      clause (so having two IN clauses, one with 5 elements, the other with 6
      will cause 30 queries to occur).
    - Literals can currently only take the form of simple types (strings,
      integers, floats).


  SELECT * will return an iterable set of entries, but other operations (schema
  queries, updates, inserts or field selections) will return alternative
  result types.
  """

  TOKENIZE_REGEX = re.compile(r"""
    (?:'[^'\n\r]*')+|
    <=|>=|!=|=|<|>|
    :\w+|
    ,|
    \*|
    -?\d+(?:\.\d+)?|
    \w+|
    \(|\)|
    \S+
    """, re.VERBOSE | re.IGNORECASE)

  MAX_ALLOWABLE_QUERIES = 30

  __ANCESTOR = -1

  def __init__(self, query_string, _app=None):
    """Ctor.

    Parses the input query into the class as a pre-compiled query, allowing
    for a later call to Bind() to bind arguments as defined in the
    documentation.

    Args:
      query_string: properly formatted GQL query string.

    Raises:
      datastore_errors.BadQueryError: if the query is not parsable.
    """
    self._entity = ''
    self.__filters = {}
    self.__bound_filters = {}
    self.__has_ancestor = False
    self.__orderings = []
    self.__offset = -1
    self.__limit = -1
    self.__hint = ''
    self.__app = _app

    self.__symbols = self.TOKENIZE_REGEX.findall(query_string)
    self.__next_symbol = 0
    if not self.__Select():
      raise datastore_errors.BadQueryError(
          'Unable to parse query')
    else:
      pass

  def Bind(self, args, keyword_args):
    """Bind the existing query to the argument list.

    Assumes that the input args are first positional, then a dictionary.
    So, if the query contains references to :1, :2 and :name, it is assumed
    that arguments are passed as (:1, :2, dict) where dict contains a mapping
    [name] -> value.

    Args:
      args: the arguments to bind to the object's unbound references.
      keyword_args: dictionary-based arguments (for named parameters).

    Raises:
      datastore_errors.BadArgumentError: when arguments are left unbound
        (missing from the inputs arguments) or when arguments do not match the
        expected type.

    Returns:
      The bound datastore.Query object. This may take the form of a MultiQuery
      object if the GQL query will require multiple backend queries to statisfy.
    """
    num_args = len(args)
    input_args = frozenset(xrange(num_args))
    used_args = set()

    queries = []
    enumerated_queries = self.EnumerateQueries(used_args, args, keyword_args)
    if enumerated_queries:
      query_count = len(enumerated_queries)
    else:
      query_count = 1

    for i in xrange(query_count):
      queries.append(datastore.Query(self._entity, _app=self.__app))

    logging.log(LOG_LEVEL, 'Copying %i pre-bound filters',
                len(self.__bound_filters))
    for ((identifier, condition), value) in self.__bound_filters.iteritems():
      logging.log(LOG_LEVEL, 'Pre-bound filter: %s %s %s',
                  identifier, condition, value)
      if not self.__IsMultiQuery(condition):
        for query in queries:
          self.__AddFilterToQuery(identifier, condition, value, query)

    logging.log(LOG_LEVEL,
                'Binding with %i positional args %s and %i keywords %s'
                , len(args), args, len(keyword_args), keyword_args)
    for (param, filters) in self.__filters.iteritems():
      for (identifier, condition) in filters:
        value = self.__GetParam(param, args, keyword_args)
        if isinstance(param, int):
          used_args.add(param - 1)
        if not self.__IsMultiQuery(condition):
          for query in queries:
            self.__AddFilterToQuery(identifier, condition, value, query)
          logging.log(LOG_LEVEL, 'binding: %s %s', param, value)

    unused_args = input_args - used_args
    if unused_args:
      unused_values = [unused_arg + 1 for unused_arg in unused_args]
      raise datastore_errors.BadArgumentError('Unused positional arguments %s' %
                                              unused_values)

    if enumerated_queries:
      logging.debug('Multiple Queries Bound: %s' % enumerated_queries)

      for (query, enumerated_query) in zip(queries, enumerated_queries):
        query.update(enumerated_query)

    if self.__orderings:
      for query in queries:
        query.Order(*tuple(self.__orderings))

    if query_count > 1:
      return MultiQuery(queries, self.__orderings)
    else:
      return queries[0]

  def EnumerateQueries(self, used_args, args, keyword_args):
    """Create a list of all multi-query filter combinations required.

    To satisfy multi-query requests ("IN" and "!=" filters), multiple queries
    may be required. This code will enumerate the power-set of all multi-query
    filters.

    Args:
      used_args: used positional parameters (output only variable used in
        reporting for unused positional args)
      args: positional arguments referenced by the proto-query in self. This
        assumes the input is a tuple (and can also be called with a varargs
        param).
      keyword_args: dict of keyword arguments referenced by the proto-query in
        self.

    Returns:
      A list of maps [(identifier, condition) -> value] of all queries needed
      to satisfy the GQL query with the given input arguments.
    """
    enumerated_queries = []

    for ((identifier, condition), value) in self.__bound_filters.iteritems():
      self.__AddMultiQuery(identifier, condition, value, enumerated_queries)

    for (param, filters) in self.__filters.iteritems():
      for (identifier, condition) in filters:
        value = self.__GetParam(param, args, keyword_args)
        if isinstance(param, int):
          used_args.add(param - 1)
        self.__AddMultiQuery(identifier, condition, value, enumerated_queries)

    return enumerated_queries

  def __IsMultiQuery(self, condition):
    """Return whether or not this condition could require multiple queries."""
    return condition.lower() in ('in', '!=')

  def __GetParam(self, reference, args, keyword_args):
    """Get the specified parameter from the input arguments.

    Args:
      reference: id for a filter reference in the filter list (string or
          number)
      args: positional args passed in by the user (tuple of arguments, indexed
          numerically by "reference")
      keyword_args: dict of keyword based arguments (strings in "reference")

    Returns:
      The specified param from the input list.

    Raises:
      BadArgumentError if the referenced argument doesn't exist.
    """
    num_args = len(args)
    if isinstance(reference, int):
      if reference <= num_args:
        return args[reference - 1]
      else:
        raise datastore_errors.BadArgumentError(
            'Missing argument for bind, requires argument #%i, '
            'but only has %i args.' % (reference, num_args))
    elif isinstance(reference, str):
      if reference in keyword_args:
        return keyword_args[reference]
      else:
        raise datastore_errors.BadArgumentError(
            'Missing named arguments for bind, requires argument %s' %
            reference)
    else:
      assert False, 'Unknown reference %s' % reference

  def __AddMultiQuery(self, identifier, condition, value, enumerated_queries):
    """Helper function to add a muti-query to previously enumerated queries.

    Args:
      identifier: property being filtered by this condition
      condition: filter condition (e.g. !=,in)
      value: value being bound
      enumerated_queries: in/out list of already bound queries -> expanded list
        with the full enumeration required to satisfy the condition query
    Raises:
      BadArgumentError if the filter is invalid (namely non-list with IN)
    """

    def CloneQueries(queries, n):
      """Do a full copy of the queries and append to the end of the queries.

      Does an in-place replication of the input list and sorts the result to
      put copies next to one-another.

      Args:
        queries: list of all filters to clone
        n: number of copies to make

      Returns:
        Number of iterations needed to fill the structure
      """
      if not enumerated_queries:
        for i in xrange(n):
          queries.append({})
        return 1
      else:
        old_size = len(queries)
        tmp_queries = []
        for i in xrange(n - 1):
          [tmp_queries.append(filter_map.copy()) for filter_map in queries]
        queries.extend(tmp_queries)
        queries.sort()
        return old_size

    if condition == '!=':
      if len(enumerated_queries) * 2 > self.MAX_ALLOWABLE_QUERIES:
        raise datastore_errors.BadArgumentError(
          'Cannot satisfy query -- too many IN/!= values.')

      num_iterations = CloneQueries(enumerated_queries, 2)
      for i in xrange(num_iterations):
        enumerated_queries[2 * i]['%s <' % identifier] = value
        enumerated_queries[2 * i + 1]['%s >' % identifier] = value
    elif condition.lower() == 'in':
      if not isinstance(value, list):
        raise datastore_errors.BadArgumentError('List expected for "IN" filter')

      in_list_size = len(value)
      if len(enumerated_queries) * in_list_size > self.MAX_ALLOWABLE_QUERIES:
        raise datastore_errors.BadArgumentError(
          'Cannot satisfy query -- too many IN/!= values.')

      num_iterations = CloneQueries(enumerated_queries, in_list_size)
      for clone_num in xrange(num_iterations):
        for value_num in xrange(len(value)):
          list_val = value[value_num]
          query_num = in_list_size * clone_num + value_num
          filt = '%s =' % identifier
          enumerated_queries[query_num][filt] = list_val

  def __AddFilterToQuery(self, identifier, condition, value, query):
    """Add a filter condition to a query based on the inputs.

    Args:
      identifier: name of the property (or self.__ANCESTOR for ancestors)
      condition: test condition
      value: test value passed from the caller
      query: query to add the filter to
    """
    if identifier != self.__ANCESTOR:
      filter_condition = '%s %s' % (identifier, condition)
      logging.log(LOG_LEVEL, 'Setting filter on "%s" with value "%s"',
                  filter_condition, value.__class__)
      datastore._AddOrAppend(query, filter_condition, value)

    else:
      logging.log(LOG_LEVEL, 'Setting ancestor query for ancestor %s', value)
      query.Ancestor(value)

  def Run(self, *args, **keyword_args):
    """Runs this query.

    Similar to datastore.Query.Run.
    Assumes that limit == -1 or > 0

    Args:
      args: arguments used to bind to references in the compiled query object.
      keyword_args: dictionary-based arguments (for named parameters).

    Returns:
      A list of results if a query count limit was passed.
      A result iterator if no limit was given.
    """
    bind_results = self.Bind(args, keyword_args)

    offset = 0
    if self.__offset != -1:
      offset = self.__offset

    if self.__limit == -1:
      it = bind_results.Run()
      try:
        for i in xrange(offset):
          it.next()
      except StopIteration:
        pass

      return it
    else:
      res = bind_results.Get(self.__limit, offset)
      return res

  def filters(self):
    """Return the compiled list of filters."""
    return self.__filters

  def hint(self):
    """Return the datastore hint."""
    return self.__hint

  def limit(self):
    """Return numerical result count limit."""
    return self.__limit

  def orderings(self):
    """Return the result ordering list."""
    return self.__orderings

  __iter__ = Run

  __quoted_string_regex = re.compile(r'((?:\'[^\'\n\r]*\')+)')
  __ordinal_regex = re.compile(r':(\d+)$')
  __named_regex = re.compile(r':(\w+)$')
  __identifier_regex = re.compile(r'(\w+)$')
  __conditions_regex = re.compile(r'(<=|>=|!=|=|<|>|is|in)$', re.IGNORECASE)
  __number_regex = re.compile(r'(\d+)$')

  def __Error(self, error_message):
    """Generic query error.

    Args:
      error_message: string to emit as part of the 'Parse Error' string.

    Raises:
      BadQueryError and passes on an error message from the caller. Will raise
      BadQueryError on all calls to __Error()
    """
    if self.__next_symbol >= len(self.__symbols):
      raise datastore_errors.BadQueryError(
          'Parse Error: %s at end of string' % error_message)
    else:
      raise datastore_errors.BadQueryError(
          'Parse Error: %s at symbol %s' %
          (error_message, self.__symbols[self.__next_symbol]))

  def __Accept(self, symbol_string):
    """Advance the symbol and return true iff the next symbol matches input."""
    if self.__next_symbol < len(self.__symbols):
      logging.log(LOG_LEVEL, '\t%s', self.__symbols)
      logging.log(LOG_LEVEL, '\tExpect: %s Got: %s',
                  symbol_string, self.__symbols[self.__next_symbol].upper())
      if self.__symbols[self.__next_symbol].upper() == symbol_string:
        logging.log(LOG_LEVEL, '\tAccepted')
        self.__next_symbol += 1
        return True
    return False

  def __Expect(self, symbol_string):
    """Require that the next symbol matches symbol_string, or emit an error.

    Args:
      symbol_string: next symbol expected by the caller

    Raises:
      BadQueryError if the next symbol doesn't match the parameter passed in.
    """
    if not self.__Accept(symbol_string):
      self.__Error('Unexpected Symbol: %s' % symbol_string)

  def __AcceptRegex(self, regex):
    """Advance and return the symbol if the next symbol matches the regex.

    Args:
      regex: the compiled regular expression to attempt acceptance on.

    Returns:
      The first group in the expression to allow for convenient access
      to simple matches. Requires () around some objects in the regex.
      None if no match is found.
    """
    if self.__next_symbol < len(self.__symbols):
      match_symbol = self.__symbols[self.__next_symbol]
      logging.log(LOG_LEVEL, '\taccept %s on symbol %s', regex, match_symbol)
      match = regex.match(match_symbol)
      if match:
        self.__next_symbol += 1
        if match.groups():
          matched_string = match.group(1)

        logging.log(LOG_LEVEL, '\taccepted %s', matched_string)
        return matched_string

    return None

  def __AcceptTerminal(self):
    """Only accept an empty string.

    Returns:
      True

    Raises:
      BadQueryError if there are unconsumed symbols in the query.
    """
    if self.__next_symbol < len(self.__symbols):
      self.__Error('Expected no additional symbols')
    return True

  def __Select(self):
    """Consume the SELECT clause and everything that follows it.

    Assumes SELECT * to start.
    Transitions to a FROM clause.

    Returns:
      True if parsing completed okay.
    """
    self.__Expect('SELECT')
    self.__Expect('*')
    return self.__From()

  def __From(self):
    """Consume the FROM clause.

    Assumes a single well formed entity in the clause.
    Assumes FROM <Entity Name>
    Transitions to a WHERE clause.

    Returns:
      True if parsing completed okay.
    """
    self.__Expect('FROM')
    entity = self.__AcceptRegex(self.__identifier_regex)
    if entity:
      self._entity = entity
      return self.__Where()
    else:
      self.__Error('Identifier Expected')
      return False

  def __Where(self):
    """Consume the WHERE cluase.

    These can have some recursion because of the AND symbol.

    Returns:
      True if parsing the WHERE clause completed correctly, as well as all
      subsequent clauses
    """
    if self.__Accept('WHERE'):
      return self.__FilterList()
    return self.__OrderBy()

  def __FilterList(self):
    """Consume the filter list (remainder of the WHERE clause)."""
    identifier = self.__AcceptRegex(self.__identifier_regex)
    if not identifier:
      self.__Error('Invalid WHERE Identifier')
      return False

    condition = self.__AcceptRegex(self.__conditions_regex)
    reference = None
    if not condition:
      self.__Error('Invalid WHERE Condition')
      return False
    else:
      reference = self.__Reference()

    self.__CheckFilterSyntax(identifier, condition)
    if reference:
      self.__AddReferenceFilter(identifier, condition, reference)
    else:
      if condition.lower() == 'in':
        self.__Error('Invalid WHERE condition: IN unsupported with literals')
      if not self.__AddLiteralFilter(identifier, condition, self.__Literal()):
        self.__Error('Invalid WHERE condition')

    if self.__Accept('AND'):
      return self.__FilterList()

    return self.__OrderBy()

  def __CheckFilterSyntax(self, identifier, condition):
    """Check that filter conditions are valid and throw errors if not.

    Args:
      identifier: identifier being used in comparison
      condition: string form of the comparison operator used in the filter
    """
    if identifier.lower() == 'ancestor':
      if condition.lower() == 'is':
        if self.__has_ancestor:
          self.__Error('Only one ANCESTOR IS" clause allowed')
      else:
        self.__Error('"IS" expected to follow "ANCESTOR"')
    elif condition.lower() == 'is':
      self.__Error('"IS" can only be used when comparing against "ANCESTOR"')

  def __AddReferenceFilter(self, identifier, condition, reference):
    """Add an unbound referential filter to the query being built.

    Args:
      identifier: identifier being used in comparison
      condition: string form of the comparison operator used in the filter
      reference: ID of the reference being made (either int or string depending
          on the type of reference being made)
    """
    filter_rule = (identifier, condition)
    if identifier.lower() == 'ancestor':
      self.__has_ancestor = True
      filter_rule = (self.__ANCESTOR, 'is')
      assert condition.lower() == 'is'

    self.__filters.setdefault(reference, []).append(filter_rule)

  def __AddLiteralFilter(self, identifier, condition, literal):
    """Add a literal filter to the query being built.

    Args:
      identifier: identifier being used in comparison
      condition: string form of the comparison operator used in the filter
      literal: direct value being used in the filter

    Returns:
      True if the literal was valid, false otherwise.
    """
    if literal is not None:
      datastore._AddOrAppend(self.__bound_filters,
                             (identifier, condition), literal)
      return True
    else:
      return False

  def __Reference(self):
    """Consume a parameter reference and return it.

    Consumes a reference to a positional parameter (:1) or a named parameter
    (:email). Only consumes a single reference (not lists).

    Returns:
      The name of the reference (integer for positional parameters or string
      for named parameters) to a bind-time parameter.
    """
    reference = self.__AcceptRegex(self.__ordinal_regex)
    if reference:
      return int(reference)
    else:
      reference = self.__AcceptRegex(self.__named_regex)
      if reference:
        return reference

    return None

  def __Literal(self):
    """Parse literals from our token list.

    Returns:
      The parsed literal from the input string (currently either a string,
      integer, or floating point value).
    """
    literal = None
    try:
      literal = int(self.__symbols[self.__next_symbol])
    except ValueError:
      pass
    else:
      self.__next_symbol += 1

    if literal is None:
      try:
        literal = float(self.__symbols[self.__next_symbol])
      except ValueError:
        pass
      else:
        self.__next_symbol += 1

    if literal is None:
      literal = self.__AcceptRegex(self.__quoted_string_regex)
      if literal:
        literal = literal[1:-1].replace("''", "'")

    if literal is None:
      if self.__Accept('TRUE'):
        literal = True
      elif self.__Accept('FALSE'):
        literal = False

    return literal

  def __OrderBy(self):
    """Consume the ORDER BY clause."""
    if self.__Accept('ORDER'):
      self.__Expect('BY')
      return self.__OrderList()
    return self.__Limit()

  def __OrderList(self):
    """Consume variables and sort order for ORDER BY clause."""
    identifier = self.__AcceptRegex(self.__identifier_regex)
    if identifier:
      if self.__Accept('DESC'):
        self.__orderings.append((identifier, datastore.Query.DESCENDING))
      elif self.__Accept('ASC'):
        self.__orderings.append((identifier, datastore.Query.ASCENDING))
      else:
        self.__orderings.append((identifier, datastore.Query.ASCENDING))
    else:
      self.__Error('Invalid ORDER BY Property')

    logging.log(LOG_LEVEL, self.__orderings)
    if self.__Accept(','):
      return self.__OrderList()
    return self.__Limit()

  def __Limit(self):
    """Consume the LIMIT clause."""
    if self.__Accept('LIMIT'):
      maybe_limit = self.__AcceptRegex(self.__number_regex)

      if maybe_limit:
        if self.__Accept(','):
          self.__offset = int(maybe_limit)
          if self.__offset < 0:
            self.__Error('Bad offset in LIMIT Value')
          else:
            logging.log(LOG_LEVEL, 'Set offset to %i', self.__offset)
            maybe_limit = self.__AcceptRegex(self.__number_regex)

        self.__limit = int(maybe_limit)
        if self.__limit < 1:
          self.__Error('Bad Limit in LIMIT Value')
        else:
          logging.log(LOG_LEVEL, 'Set limit to %i', self.__limit)
      else:
        self.__Error('Non-number limit in LIMIT clause')

    return self.__Offset()

  def __Offset(self):
    """Consume the OFFSET clause."""
    if self.__Accept('OFFSET'):
      if self.__offset != -1:
        self.__Error('Offset already defined in LIMIT clause')

      offset = self.__AcceptRegex(self.__number_regex)

      if offset:
        self.__offset = int(offset)
        if self.__offset < 0:
          self.__Error('Bad offset in OFFSET clause')
        else:
          logging.log(LOG_LEVEL, 'Set offset to %i', self.__offset)
      else:
        self.__Error('Non-number offset in OFFSET clause')

    return self.__Hint()

  def __Hint(self):
    """Consume the HINT clause.

    Requires one of three options (mirroring the rest of the datastore):
      HINT ORDER_FIRST
      HINT ANCESTOR_FIRST
      HINT FILTER_FIRST

    Returns:
      True if the hint clause and later clauses all parsed okay
    """
    if self.__Accept('HINT'):
      if self.__Accept('ORDER_FIRST'):
        self.__hint = 'ORDER_FIRST'
      elif self.__Accept('FILTER_FIRST'):
        self.__hint = 'FILTER_FIRST'
      elif self.__Accept('ANCESTOR_FIRST'):
        self.__hint = 'ANCESTOR_FIRST'
      else:
        self.__Error('Unknown HINT')
        return False
    return self.__AcceptTerminal()


class MultiQuery(datastore.Query):
  """Class representing a GQL query requiring multiple datastore queries.

  This class is actually a subclass of datastore.Query as it is intended to act
  like a normal Query object (supporting the same interface).
  """

  def __init__(self, bound_queries, orderings):
    self.__bound_queries = bound_queries
    self.__orderings = orderings

  def Get(self, limit, offset=0):
    """Get results of the query with a limit on the number of results.

    Args:
      limit: maximum number of values to return.
      offset: offset requested -- if nonzero, this will override the offset in
              the original query

    Returns:
      An array of entities with at most "limit" entries (less if the query
      completes before reading limit values).
    """
    count = 1
    result = []

    iterator = self.Run()

    try:
      for i in xrange(offset):
        val = iterator.next()
    except StopIteration:
      pass

    try:
      while count <= limit:
        val = iterator.next()
        result.append(val)
        count += 1
    except StopIteration:
      pass
    return result

  class SortOrderEntity(object):
    def __init__(self, entity_iterator, orderings):
      self.__entity_iterator = entity_iterator
      self.__entity = None
      self.__min_max_value_cache = {}
      try:
        self.__entity = entity_iterator.next()
      except StopIteration:
        pass
      else:
        self.__orderings = orderings

    def __str__(self):
      return str(self.__entity)

    def GetEntity(self):
      return self.__entity

    def GetNext(self):
      return MultiQuery.SortOrderEntity(self.__entity_iterator,
                                        self.__orderings)

    def CmpProperties(self, that):
      """Compare two entities and return their relative order.

      Compares self to that based on the current sort orderings and the
      key orders between them. Returns negative, 0, or positive depending on
      whether self is less, equal to, or greater than that. This
      comparison returns as if all values were to be placed in ascending order
      (highest value last).  Only uses the sort orderings to compare (ignores
       keys).

      Args:
        self: SortOrderEntity
        that: SortOrderEntity

      Returns:
        Negative if self < that
        Zero if self == that
        Positive if self > that
      """
      if not self.__entity:
        return cmp(self.__entity, that.__entity)

      for (identifier, order) in self.__orderings:
        value1 = self.__GetValueForId(self, identifier, order)
        value2 = self.__GetValueForId(that, identifier, order)

        result = cmp(value1, value2)
        if order == datastore.Query.DESCENDING:
          result = -result
        if result:
          return result
      return 0

    def __GetValueForId(self, sort_order_entity, identifier, sort_order):
      value = sort_order_entity.__entity[identifier]
      entity_key = sort_order_entity.__entity.key()
      if self.__min_max_value_cache.has_key((entity_key, identifier)):
        value = self.__min_max_value_cache[(entity_key, identifier)]
      elif isinstance(value, list):
        if sort_order == datastore.Query.DESCENDING:
          value = min(value)
        else:
          value = max(value)
        self.__min_max_value_cache[(entity_key, identifier)] = value

      return value

    def __cmp__(self, that):
      """Compare self to that w.r.t. values defined in the sort order.

      Compare an entity with another, using sort-order first, then the key
      order to break ties. This can be used in a heap to have faster min-value
      lookup.

      Args:
        that: other entity to compare to
      Returns:
        negative: if self is less than that in sort order
        zero: if self is equal to that in sort order
        positive: if self is greater than that in sort order
      """
      property_compare = self.CmpProperties(that)
      if property_compare:
        return property_compare
      else:
        return cmp(self.__entity.key(), that.__entity.key())

  def Run(self):
    """Return an iterable output with all results in order."""
    results = []
    count = 1
    for bound_query in self.__bound_queries:
      logging.log(LOG_LEVEL, 'Running query #%i' % count)
      results.append(bound_query.Run())
      count += 1

    def IterateResults(results):
      """Iterator function to return all results in sorted order.

      Iterate over the array of results, yielding the next element, in
      sorted order. This function is destructive (results will be empty
      when the operation is complete).

      Args:
        results: list of result iterators to merge and iterate through

      Yields:
        The next result in sorted order.
      """
      result_heap = []
      for result in results:
        heap_value = MultiQuery.SortOrderEntity(result, self.__orderings)
        if heap_value.GetEntity():
          heapq.heappush(result_heap, heap_value)

      used_keys = set()

      while result_heap:
        top_result = heapq.heappop(result_heap)

        results_to_push = []
        if top_result.GetEntity().key() not in used_keys:
          yield top_result.GetEntity()
        else:
          pass

        used_keys.add(top_result.GetEntity().key())

        results_to_push = []
        while result_heap:
          next = heapq.heappop(result_heap)
          if cmp(top_result, next):
            results_to_push.append(next)
            break
          else:
            results_to_push.append(next.GetNext())
        results_to_push.append(top_result.GetNext())

        for popped_result in results_to_push:
          if popped_result.GetEntity():
            heapq.heappush(result_heap, popped_result)

    return IterateResults(results)
