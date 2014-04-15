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
"""Document matcher for Search API stub.

DocumentMatcher provides an approximation of the Search API's query matching.
"""


from google.appengine.datastore import document_pb

from google.appengine._internal.antlr3 import tree
from google.appengine.api.search import query_parser
from google.appengine.api.search import QueryParser
from google.appengine.api.search import search_util
from google.appengine.api.search.stub import geo_util
from google.appengine.api.search.stub import simple_tokenizer
from google.appengine.api.search.stub import tokens


MSEC_PER_DAY = 86400000

class ExpressionTreeException(Exception):
  """An error occurred while analyzing/translating the expression parse tree."""

  def __init__(self, msg):
    Exception.__init__(self, msg)


class DistanceMatcher(object):
  """A class to match on geo distance."""
  def __init__(self, geopoint, distance):
    self._geopoint = geopoint
    self._distance = distance

  def _CheckOp(self, op):
    if op == QueryParser.EQ or op == QueryParser.HAS:
      raise ExpressionTreeException('Equality comparison not available for Geo type')
    if op == QueryParser.NE:
      raise ExpressionTreeException('!= comparison operator is not available')
    if op not in (QueryParser.GT, QueryParser.GE, QueryParser.LESSTHAN, QueryParser.LE):
      raise search_util.UnsupportedOnDevError(
          'Operator %s not supported for distance matches on development server.'
          % str(op))

  def _IsDistanceMatch(self, geopoint, op):
    distance = geopoint - self._geopoint
    if op == QueryParser.GT or op == QueryParser.GE:
      return distance >= self._distance
    if op == QueryParser.LESSTHAN or op == QueryParser.LE:
      return distance <= self._distance
    else:
      raise AssertionError, 'unexpected op %s' % str(op)

  def IsMatch(self, field_values, op):
    self._CheckOp(op)



    for field_value in field_values:
      geo_pb = field_value.geo()
      geopoint = geo_util.LatLng(geo_pb.lat(), geo_pb.lng())
      if self._IsDistanceMatch(geopoint, op):
        return True



    if field_values:
      return False




    return op == QueryParser.GT or op == QueryParser.GE


class DocumentMatcher(object):
  """A class to match documents with a query."""

  def __init__(self, query, inverted_index):
    self._query = query
    self._inverted_index = inverted_index
    self._parser = simple_tokenizer.SimpleTokenizer()

  def _PostingsForToken(self, token):
    """Returns the postings for the token."""
    return self._inverted_index.GetPostingsForToken(token)

  def _PostingsForFieldToken(self, field, value):
    """Returns postings for the value occurring in the given field."""
    value = simple_tokenizer.NormalizeString(value)
    return self._PostingsForToken(
        tokens.Token(chars=value, field_name=field))

  def _MatchPhrase(self, field, match, document):
    """Match a textual field with a phrase query node."""
    field_text = field.value().string_value()
    phrase_text = query_parser.GetPhraseQueryNodeText(match)


    if field.value().type() == document_pb.FieldValue.ATOM:
      return (field_text == phrase_text)

    phrase = self._parser.TokenizeText(phrase_text)
    field_text = self._parser.TokenizeText(field_text)
    if not phrase:
      return True
    posting = None
    for post in self._PostingsForFieldToken(field.name(), phrase[0].chars):
      if post.doc_id == document.id():
        posting = post
        break
    if not posting:
      return False

    def ExtractWords(token_list):
      return (token.chars for token in token_list)

    for position in posting.positions:




      match_words = zip(ExtractWords(field_text[position:]),
                        ExtractWords(phrase))
      if len(match_words) != len(phrase):
        continue


      match = True
      for doc_word, match_word in match_words:
        if doc_word != match_word:
          match = False

      if match:
        return True
    return False

  def _MatchTextField(self, field, match, document):
    """Check if a textual field matches a query tree node."""

    if match.getType() == QueryParser.FUZZY:
      return self._MatchTextField(field, match.getChild(0), document)

    if match.getType() == QueryParser.VALUE:
      if query_parser.IsPhrase(match):
        return self._MatchPhrase(field, match, document)


      if field.value().type() == document_pb.FieldValue.ATOM:
        return (field.value().string_value() ==
                query_parser.GetQueryNodeText(match))

      query_tokens = self._parser.TokenizeText(
          query_parser.GetQueryNodeText(match))


      if not query_tokens:
        return True




      if len(query_tokens) > 1:
        def QueryNode(token):
          return query_parser.CreateQueryNode(token.chars, QueryParser.TEXT)
        return all(self._MatchTextField(field, QueryNode(token), document)
                   for token in query_tokens)

      token_text = query_tokens[0].chars
      matching_docids = [
          post.doc_id for post in self._PostingsForFieldToken(
              field.name(), token_text)]
      return document.id() in matching_docids

    def ExtractGlobalEq(node):
      op = node.getType()
      if ((op == QueryParser.EQ or op == QueryParser.HAS) and
          len(node.children) >= 2):
        if node.children[0].getType() == QueryParser.GLOBAL:
          return node.children[1]
      return node

    if match.getType() == QueryParser.CONJUNCTION:
      return all(self._MatchTextField(field, ExtractGlobalEq(child), document)
                 for child in match.children)

    if match.getType() == QueryParser.DISJUNCTION:
      return any(self._MatchTextField(field, ExtractGlobalEq(child), document)
                 for child in match.children)

    if match.getType() == QueryParser.NEGATION:
      return not self._MatchTextField(
          field, ExtractGlobalEq(match.children[0]), document)


    return False

  def _MatchDateField(self, field, match, operator, document):
    """Check if a date field matches a query tree node."""


    return self._MatchComparableField(
        field, match, _DateStrToDays, operator, document)



  def _MatchNumericField(self, field, match, operator, document):
    """Check if a numeric field matches a query tree node."""
    return self._MatchComparableField(field, match, float, operator, document)

  def _MatchGeoField(self, field, matcher, operator, document):
    """Check if a geo field matches a query tree node."""

    if not isinstance(matcher, DistanceMatcher):
      return False

    if isinstance(field, tree.CommonTree):
      field = query_parser.GetQueryNodeText(field)
    values = [ field.value() for field in
               search_util.GetAllFieldInDocument(document, field) if
               field.value().type() == document_pb.FieldValue.GEO ]
    return matcher.IsMatch(values, operator)


  def _MatchComparableField(
      self, field, match, cast_to_type, op, document):
    """A generic method to test matching for comparable types.

    Comparable types are defined to be anything that supports <, >, <=, >=, ==.
    For our purposes, this is numbers and dates.

    Args:
      field: The document_pb.Field to test
      match: The query node to match against
      cast_to_type: The type to cast the node string values to
      op: The query node type representing the type of comparison to perform
      document: The document that the field is in

    Returns:
      True iff the field matches the query.

    Raises:
      UnsupportedOnDevError: Raised when an unsupported operator is used, or
      when the query node is of the wrong type.
      ExpressionTreeException: Raised when a != inequality operator is used.
    """

    field_val = cast_to_type(field.value().string_value())

    if match.getType() == QueryParser.VALUE:
      try:
        match_val = cast_to_type(query_parser.GetPhraseQueryNodeText(match))
      except ValueError:
        return False
    else:
      return False

    if op == QueryParser.EQ or op == QueryParser.HAS:
      return field_val == match_val
    if op == QueryParser.NE:
      raise ExpressionTreeException('!= comparison operator is not available')
    if op == QueryParser.GT:
      return field_val > match_val
    if op == QueryParser.GE:
      return field_val >= match_val
    if op == QueryParser.LESSTHAN:
      return field_val < match_val
    if op == QueryParser.LE:
      return field_val <= match_val
    raise search_util.UnsupportedOnDevError(
        'Operator %s not supported for numerical fields on development server.'
        % match.getText())

  def _MatchAnyField(self, field, match, operator, document):
    """Check if a field matches a query tree.

    Args:
      field: the name of the field, or a query node containing the field.
      match: A query node to match the field with.
      operator: The query node type corresponding to the type of match to
        perform (eg QueryParser.EQ, QueryParser.GT, etc).
      document: The document to match.
    """

    if isinstance(field, tree.CommonTree):
      field = query_parser.GetQueryNodeText(field)
    fields = search_util.GetAllFieldInDocument(document, field)
    return any(self._MatchField(f, match, operator, document) for f in fields)

  def _MatchField(self, field, match, operator, document):
    """Check if a field matches a query tree.

    Args:
      field: a document_pb.Field instance to match.
      match: A query node to match the field with.
      operator: The a query node type corresponding to the type of match to
        perform (eg QueryParser.EQ, QueryParser.GT, etc).
      document: The document to match.
    """

    if field.value().type() in search_util.TEXT_DOCUMENT_FIELD_TYPES:
      if operator != QueryParser.EQ and operator != QueryParser.HAS:
        return False
      return self._MatchTextField(field, match, document)

    if field.value().type() in search_util.NUMBER_DOCUMENT_FIELD_TYPES:
      return self._MatchNumericField(field, match, operator, document)

    if field.value().type() == document_pb.FieldValue.DATE:
      return self._MatchDateField(field, match, operator, document)





    if field.value().type() == document_pb.FieldValue.GEO:
      return False

    type_name = document_pb.FieldValue.ContentType_Name(
        field.value().type()).lower()
    raise search_util.UnsupportedOnDevError(
        'Matching fields of type %s is unsupported on dev server (searched for '
        'field %s)' % (type_name, field.name()))

  def _MatchGlobal(self, match, document):
    for field in document.field_list():
      try:
        if self._MatchAnyField(field.name(), match, QueryParser.EQ, document):
          return True
      except search_util.UnsupportedOnDevError:



        pass
    return False

  def _ResolveDistanceArg(self, node):
    if node.getType() == QueryParser.VALUE:
      return query_parser.GetQueryNodeText(node)
    if node.getType() == QueryParser.FUNCTION:
      name, args = node.children
      if name.getText() == 'geopoint':
        lat, lng = (float(query_parser.GetQueryNodeText(v)) for v in args.children)
        return geo_util.LatLng(lat, lng)
    return None

  def _MatchFunction(self, node, match, operator, document):
    name, args = node.children
    if name.getText() == 'distance':
      x, y = args.children
      x, y = self._ResolveDistanceArg(x), self._ResolveDistanceArg(y)
      if isinstance(x, geo_util.LatLng) and isinstance(y, basestring):
        x, y = y, x
      if isinstance(x, basestring) and isinstance(y, geo_util.LatLng):
        distance = float(query_parser.GetQueryNodeText(match))
        matcher = DistanceMatcher(y, distance)
        return self._MatchGeoField(x, matcher, operator, document)
    return False

  def _CheckMatch(self, node, document):
    """Check if a document matches a query tree."""

    if node.getType() == QueryParser.CONJUNCTION:
      return all(self._CheckMatch(child, document) for child in node.children)

    if node.getType() == QueryParser.DISJUNCTION:
      return any(self._CheckMatch(child, document) for child in node.children)

    if node.getType() == QueryParser.NEGATION:
      return not self._CheckMatch(node.children[0], document)

    if node.getType() in query_parser.COMPARISON_TYPES:
      lhs, match = node.children
      if lhs.getType() == QueryParser.GLOBAL:
        return self._MatchGlobal(match, document)
      elif lhs.getType() == QueryParser.FUNCTION:
        return self._MatchFunction(lhs, match, node.getType(), document)
      return self._MatchAnyField(lhs, match, node.getType(), document)

    return False

  def Matches(self, document):
    return self._CheckMatch(self._query, document)

  def FilterDocuments(self, documents):
    return (doc for doc in documents if self.Matches(doc))


def _DateStrToDays(date_str):

  date = search_util.DeserializeDate(date_str)
  return search_util.EpochTime(date) / MSEC_PER_DAY
