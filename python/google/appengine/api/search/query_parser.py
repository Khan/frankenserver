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




"""Wrapper for QueryParser."""


import google
import antlr3

from google.appengine.api.search import QueryLexer
from google.appengine.api.search import QueryParser


_OPERATOR_MAP = {
    QueryParser.CONJUNCTION: 'AND',
    QueryParser.DISJUNCTION: 'OR',
    QueryParser.NEGATION: 'NOT',
    QueryParser.NONE: 'None',
    QueryParser.NUMBER: 'Number',
    QueryParser.RESTRICTION: 'Restrict',
    QueryParser.STRING: 'String',
    QueryParser.WORD: 'Word',
    QueryParser.VALUE: 'Value',
    QueryParser.TEXT: 'Text',
    QueryParser.EOF: 'EOF',
    QueryParser.LT: '<',
    QueryParser.LE: '<=',
    QueryParser.GT: '>',
    QueryParser.GE: '>=',
    QueryParser.SELECTOR: 'Selector',
    QueryParser.PHRASE: 'Phrase',
    QueryParser.INT: 'Int'}


class QueryException(Exception):
  """An error occurred while parsing the query input string."""


class QueryLexerWithErrors(QueryLexer.QueryLexer):
  """An overridden Lexer that raises exceptions."""

  def emitErrorMessage(self, msg):
    """Raise an exception if the input fails to parse correctly.

    Overriding the default, which normally just prints a message to
    stderr.

    Arguments:
      msg: the error message
    Raises:
      QueryException: always.
    """
    raise QueryException(msg)


class QueryParserWithErrors(QueryParser.QueryParser):
  """An overridden Parser that raises exceptions."""

  def emitErrorMessage(self, msg):
    """Raise an exception if the input fails to parse correctly.

    Overriding the default, which normally just prints a message to
    stderr.

    Arguments:
      msg: the error message
    Raises:
      QueryException: always.
    """
    raise QueryException(msg)


def CreateParser(query):
  """Creates a Query Parser."""
  input_string = antlr3.ANTLRStringStream(query)
  lexer = QueryLexerWithErrors(input_string)
  tokens = antlr3.CommonTokenStream(lexer)
  parser = QueryParserWithErrors(tokens)
  return parser


def _Parse(query):
  parser = CreateParser(query)
  try:
    return parser.query()
  except Exception, e:
    raise QueryException(e.message)


def _TypeToString(node_type):
  """Converts a node_type to a string."""
  if node_type in _OPERATOR_MAP.keys():
    return _OPERATOR_MAP[node_type]
  return 'unknown operator: ' + str(node_type)


def Simplify(parser_return):
  """Simplifies the output of the parser."""
  if parser_return.tree:
    return _SimplifyNode(parser_return.tree)
  return parser_return


def _SimplifyNode(node):
  """Simplifies the node removing singleton conjunctions and others."""
  if not node.getType():
    return _SimplifyNode(node.children[0])
  elif node.getType() is QueryParser.CONJUNCTION and node.getChildCount() is 1:
    return _SimplifyNode(node.children[0])
  elif node.getType() is QueryParser.DISJUNCTION and node.getChildCount() is 1:
    return _SimplifyNode(node.children[0])
  elif (node.getType() is QueryParser.RESTRICTION and node.getChildCount() is 2
        and node.children[0].getType() is QueryParser.NONE):
    return _SimplifyNode(node.children[1])
  elif (node.getType() is QueryParser.VALUE and node.getChildCount() is 2 and
        (node.children[0].getType() is QueryParser.WORD or
         node.children[0].getType() is QueryParser.STRING or
         node.children[0].getType() is QueryParser.NUMBER)):
    return _SimplifyNode(node.children[1])
  for i, child in enumerate(node.children):
    node.setChild(i, _SimplifyNode(child))
  return node


def ToString(node):
  """Translates the node in a parse tree into a query string fragment."""
  output = ''
  if node.getChildCount():
    output += '('
  if (node.getType() is QueryParser.TEXT or
      node.getType() is QueryParser.SELECTOR or
      node.getType() is QueryParser.PHRASE or
      node.getType() is QueryParser.INT):
    output += node.getText()
  else:
    output += _TypeToString(node.getType())
  if node.getChildCount():
    output += ' '
  output += ' '.join([ToString(child) for child in node.children])
  if node.getChildCount():
    output += ')'
  return output


def Parse(query):
  """Parses a query and simplifies the parse tree."""
  return Simplify(_Parse(query))
