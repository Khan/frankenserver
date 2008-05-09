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

  SELECT * will return an iterable set of entries, but other operations (schema
  queries, updates, inserts or field selections) will return alternative
  result types.
  """

  TOKENIZE_REGEX = re.compile(r"""
    (?:'[^'\n\r]*')+|
    <=|>=|=|<|>|
    :\w+|
    ,|
    \*|
    -?\d+(?:\.\d+)?|
    \w+|
    \(|\)|
    \S+
    """, re.VERBOSE | re.IGNORECASE)

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
        (missing from the inputs arguments).

    Returns:
      The bound datastore.Query object.
    """
    num_args = len(args)
    input_args = frozenset(xrange(num_args))
    used_args = set()

    query = datastore.Query(self._entity, _app=self.__app)

    logging.log(LOG_LEVEL, 'Copying %i pre-bound filters',
                len(self.__bound_filters))
    for (condition, value) in self.__bound_filters.iteritems():
      logging.log(LOG_LEVEL, 'Pre-bound filter: %s %s', condition, value)
      query[condition] = value

    logging.log(LOG_LEVEL, 'Binding with %i args %s', len(args), args)
    for (param, filters) in self.__filters.iteritems():
      for (identifier, condition) in filters:
        if isinstance(param, int):
          if param <= num_args:
            self.__AddFilter(identifier, condition, args[param-1], query)
            used_args.add(param - 1)
            logging.log(LOG_LEVEL, 'binding: %i %s', param, args[param-1])
          else:
            raise datastore_errors.BadArgumentError(
                'Missing argument for bind, requires argument #%i, '
                'but only has %i args.' % (param, num_args))
        elif isinstance(param, str):
          if param in keyword_args:
            self.__AddFilter(identifier, condition, keyword_args[param], query)
            logging.log(LOG_LEVEL, 'binding: %s %s', param, keyword_args)
          else:
            raise datastore_errors.BadArgumentError(
                'Missing named arguments for bind, requires argument %s' %
                param)
        else:
          assert False, 'Unknown parameter %s' % param

    if self.__orderings:
      query.Order(*tuple(self.__orderings))

    unused_args = input_args - used_args
    if unused_args:
      unused_values = [unused_arg + 1 for unused_arg in unused_args]
      raise datastore_errors.BadArgumentError('Unused positional arguments %s' %
                                              unused_values)

    return query

  def __AddFilter(self, identifier, condition, value, query):
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
      query[filter_condition] = value
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
    bound_query = self.Bind(args, keyword_args)
    offset = 0
    if self.__offset != -1:
      offset = self.__offset

    if self.__limit == -1:
      it = bound_query.Run()
      try:
        for i in xrange(offset):
          it.next()
      except StopIteration:
        pass

      return it
    else:

      res = bound_query.Get(self.__limit + offset)
      return res[offset:]

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
  __conditions_regex = re.compile(r'(<=|>=|=|<|>|is)$', re.IGNORECASE)
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
      self.__bound_filters['%s %s' % (identifier, condition)] = literal
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
            logging.log(LOG_LEVEL, 'Set offset to %i' % self.__offset)
            maybe_limit = self.__AcceptRegex(self.__number_regex)

        self.__limit = int(maybe_limit)
        if self.__limit < 1:
          self.__Error('Bad Limit in LIMIT Value')
        else:
          logging.log(LOG_LEVEL, 'Set limit to %i' % self.__limit)
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
          logging.log(LOG_LEVEL, 'Set offset to %i' % self.__offset)
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
