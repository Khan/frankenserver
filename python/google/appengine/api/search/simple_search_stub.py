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




"""Simple RAM backed Search API stub."""










import bisect
import copy
import cPickle as pickle
import datetime
import logging
import math
import os
import random
import re
import string
import tempfile
import threading
import urllib
import uuid

from google.appengine.datastore import document_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api.namespace_manager import namespace_manager
from google.appengine.api.search import query_parser
from google.appengine.api.search import QueryParser
from google.appengine.api.search import search
from google.appengine.api.search import search_service_pb
from google.appengine.runtime import apiproxy_errors

__all__ = ['IndexConsistencyError',
           'GeoPoint',
           'Number',
           'Posting',
           'PostingList',
           'Quote',
           'RamInvertedIndex',
           'SearchServiceStub',
           'SimpleIndex',
           'SimpleTokenizer',
           'Token',
           'UnsupportedOnDevError',
          ]


_TEXT_DOCUMENT_FIELD_TYPES = [
    document_pb.FieldValue.ATOM,
    document_pb.FieldValue.TEXT,
    document_pb.FieldValue.HTML,
    ]

_TEXT_QUERY_TYPES = [
    QueryParser.NAME,
    QueryParser.PHRASE,
    QueryParser.TEXT,
    ]

_NUMBER_DOCUMENT_FIELD_TYPES = [
    document_pb.FieldValue.NUMBER,
    ]

_NUMBER_QUERY_TYPES = [
    QueryParser.FLOAT,
    QueryParser.INT,
    QueryParser.NUMBER,
    ]

_VISIBLE_PRINTABLE_ASCII = frozenset(
    set(string.printable) - set(string.whitespace))


class IndexConsistencyError(Exception):
  """Indicates attempt to create index with same name different consistency."""


class UnsupportedOnDevError(Exception):
  """Indicates attempt to perform an action unsupported on the dev server."""


def _Repr(class_instance, ordered_dictionary):
  """Generates an unambiguous representation for instance and ordered dict."""
  return 'search.%s(%s)' % (class_instance.__class__.__name__, ', '.join(
      ["%s='%s'" % (key, value)
       for (key, value) in ordered_dictionary if value]))


def _TreeRepr(tree, depth=0):
  """Generate a string representation of an ANTLR parse tree for debugging."""

  def _NodeRepr(node):
    text = str(node.getType())
    if node.getText():
      text = '%s: %s' % (text, node.getText())
    return text

  children = ''
  if tree.children:
    children = '\n' + '\n'.join([_TreeRepr(child, depth=depth+1)
                                 for child in tree.children if child])
  return depth * '  ' + _NodeRepr(tree) + children


class Token(object):
  """Represents a token, usually a word, extracted from some document field."""

  def __init__(self, chars=None, position=None, field_name=None):
    """Initializer.

    Args:
      chars: The string representation of the token.
      position: The position of the token in the sequence from the document
        field.
      field_name: The name of the field the token occured in.

    Raises:
      TypeError: If an unknown argument is passed.
    """
    self._chars = chars
    self._position = position
    self._field_name = field_name

  @property
  def chars(self):
    """Returns a list of fields of the document."""
    value = self._chars
    if not isinstance(value, basestring):
      value = str(self._chars)
    if self._field_name:
      return self._field_name + ':' + value
    return value

  @property
  def position(self):
    """Returns a list of fields of the document."""
    return self._position

  def RestrictField(self, field_name):
    """Creates a copy of this Token and sets field_name."""
    return Token(chars=self.chars, position=self.position,
                 field_name=field_name)

  def __repr__(self):
    return _Repr(self, [('chars', self.chars), ('position', self.position)])

  def __eq__(self, other):
    return self.chars == other.chars

  def __hash__(self):
    return hash(self.chars)


class Quote(Token):
  """Represents a single or double quote in a document field or query."""

  def __init__(self, **kwargs):
    Token.__init__(self, **kwargs)


class Number(Token):
  """Represents a number in a document field or query."""

  def __init__(self, **kwargs):
    Token.__init__(self, **kwargs)


class GeoPoint(Token):
  """Represents a geo point in a document field or query."""

  def __init__(self, **kwargs):
    self._latitude = kwargs.pop('latitude')
    self._longitude = kwargs.pop('longitude')
    Token.__init__(self, **kwargs)

  @property
  def latitude(self):
    """Returns the angle between equatorial plan and line thru the geo point."""
    return self._latitude

  @property
  def longitude(self):
    """Returns the angle from a reference meridian to another meridian."""
    return self._longitude


class Posting(object):
  """Represents a occurrences of some token at positions in a document."""

  def __init__(self, doc_id):
    """Initializer.

    Args:
      doc_id: The identifier of the document with token occurrences.

    Raises:
      TypeError: If an unknown argument is passed.
    """
    self._doc_id = doc_id
    self._positions = []

  @property
  def doc_id(self):
    """Return id of the document that the token occurred in."""
    return self._doc_id

  def AddPosition(self, position):
    """Adds the position in token sequence to occurrences for token."""
    pos = bisect.bisect_left(self._positions, position)
    if pos < len(self._positions) and self._positions[pos] == position:
      return
    self._positions.insert(pos, position)

  def RemovePosition(self, position):
    """Removes the position in token sequence from occurrences for token."""
    pos = bisect.bisect_left(self._positions, position)
    if pos < len(self._positions) and self._positions[pos] == position:
      del self._positions[pos]

  def __cmp__(self, other):
    if not isinstance(other, Posting):
      return -2
    return cmp(self.doc_id, other.doc_id)

  @property
  def positions(self):
    return self._positions

  def __repr__(self):
    return _Repr(self, [('doc_id', self.doc_id), ('positions', self.positions)])


class SimpleTokenizer(object):
  """A tokenizer which converts text to lower case and splits on whitespace."""

  def __init__(self, split_restricts=True):
    self._split_restricts = split_restricts
    self._html_pattern = re.compile(r'<[^>]*>')

  def TokenizeText(self, text, token_position=0):
    """Tokenizes the text into a sequence of Tokens."""
    return self._TokenizeForType(field_type=document_pb.FieldValue.TEXT,
                                 value=text, token_position=token_position)

  def TokenizeValue(self, field_value, token_position=0):
    """Tokenizes a document_pb.FieldValue into a sequence of Tokens."""
    if field_value.type() is document_pb.FieldValue.GEO:
      return self._TokenizeForType(field_type=field_value.type(),
                                   value=field_value.geo(),
                                   token_position=token_position)
    return self._TokenizeForType(field_type=field_value.type(),
                                 value=field_value.string_value(),
                                 token_position=token_position)

  def _TokenizeString(self, value, field_type):
    if field_type is document_pb.FieldValue.HTML:
      return self._StripHtmlTags(value).lower().split()
    if field_type is document_pb.FieldValue.ATOM:
      return [value.lower()]
    return value.lower().split()

  def _StripHtmlTags(self, value):
    """Replace HTML tags with spaces."""
    return self._html_pattern.sub(' ', value)

  def _TokenizeForType(self, field_type, value, token_position=0):
    """Tokenizes value into a sequence of Tokens."""
    if field_type is document_pb.FieldValue.NUMBER:
      return [Token(chars=value, position=token_position)]

    if field_type is document_pb.FieldValue.GEO:
      return [GeoPoint(latitude=value.lat(), longitude=value.lng(),
                       position=token_position)]

    tokens = []
    token_strings = []

    if not self._split_restricts:
      token_strings = value.lower().split()
    else:
      token_strings = self._TokenizeString(value, field_type)
    for token in token_strings:
      if ':' in token and self._split_restricts:
        for subtoken in token.split(':'):
          tokens.append(Token(chars=subtoken, position=token_position))
          token_position += 1
      elif '"' in token:
        for subtoken in token.split('"'):
          if not subtoken:
            tokens.append(Quote(chars='"', position=token_position))
          else:
            tokens.append(Token(chars=subtoken, position=token_position))
          token_position += 1
      else:
        tokens.append(Token(chars=token, position=token_position))
        token_position += 1
    return tokens


class PostingList(object):
  """Represents ordered positions of some token in document.

  A PostingList consists of a document id and a sequence of positions
  that the same token occurs in the document.
  """

  def __init__(self):
    self._postings = []

  def Add(self, doc_id, position):
    """Adds the token position for the given doc_id."""
    posting = Posting(doc_id=doc_id)
    pos = bisect.bisect_left(self._postings, posting)
    if pos < len(self._postings) and self._postings[
        pos].doc_id == posting.doc_id:
      posting = self._postings[pos]
    else:
      self._postings.insert(pos, posting)
    posting.AddPosition(position)

  def Remove(self, doc_id, position):
    """Removes the token position for the given doc_id."""
    posting = Posting(doc_id=doc_id)
    pos = bisect.bisect_left(self._postings, posting)
    if pos < len(self._postings) and self._postings[
        pos].doc_id == posting.doc_id:
      posting = self._postings[pos]
      posting.RemovePosition(position)
      if not posting.positions:
        del self._postings[pos]

  @property
  def postings(self):
    return self._postings

  def __iter__(self):
    return iter(self._postings)

  def __repr__(self):
    return _Repr(self, [('postings', self.postings)])


class _ScoredDocument(object):
  """A scored document_pb.Document."""

  def __init__(self, document, score):
    self._document = document
    self._score = score

  @property
  def document(self):
    return self._document

  @property
  def score(self):
    return self._score

  def __repr__(self):
    return _Repr(self, [('document', self.document), ('score', self.score)])


class _DocumentStatistics(object):
  """Statistics about terms occuring in a document."""

  def __init__(self):
    self._term_stats = {}

  def __iter__(self):
    for item in self._term_stats.items():
      yield item

  def IncrementTermCount(self, term):
    """Adds an occurrence of the term to the stats for the document."""
    count = 0
    if term in self._term_stats:
      count = self._term_stats[term]
    count += 1
    self._term_stats[term] = count

  def TermFrequency(self, term):
    """Returns the term frequency in the document."""
    if term not in self._term_stats:
      return 0
    return self._term_stats[term]

  @property
  def term_stats(self):
    """Returns the collection of term frequencies in the document."""
    return self._term_stats

  def __eq__(self, other):
    return self.term_stats == other.term_stats

  def __hash__(self):
    return hash(self.term_stats)

  def __repr__(self):
    return _Repr(self, [('term_stats', self.term_stats)])


class RamInvertedIndex(object):
  """A simple RAM-resident inverted file over documents."""

  def __init__(self, tokenizer):
    self._tokenizer = tokenizer
    self._inverted_index = {}
    self._schema = {}
    self._document_ids = set([])

  def _AddDocumentId(self, doc_id):
    """Adds the doc_id to set in index."""
    self._document_ids.add(doc_id)

  def _RemoveDocumentId(self, doc_id):
    """Removes the doc_id from the set in index."""
    if doc_id in self._document_ids:
      self._document_ids.remove(doc_id)

  @property
  def document_count(self):
    return len(self._document_ids)

  def _AddFieldType(self, name, field_type):
    """Adds the type to the list supported for a named field."""
    if name not in self._schema:
      field_types = document_pb.FieldTypes()
      field_types.set_name(name)
      self._schema[name] = field_types
    field_types = self._schema[name]
    if field_type not in field_types.type_list():
      field_types.add_type(field_type)

  def GetDocumentStats(self, document):
    """Gets statistics about occurrences of terms in document."""
    document_stats = _DocumentStatistics()
    for field in document.field_list():
      for token in self._tokenizer.TokenizeValue(field_value=field.value()):
        document_stats.IncrementTermCount(token.chars)
    return document_stats

  def AddDocument(self, doc_id, document):
    """Adds a document into the index."""
    token_position = 0
    for field in document.field_list():
      self._AddFieldType(field.name(), field.value().type())
      self._AddTokens(doc_id, field.name(), field.value(), token_position)
    self._AddDocumentId(doc_id)

  def RemoveDocument(self, document):
    """Removes a document from the index."""
    doc_id = document.id()
    for field in document.field_list():
      self._RemoveTokens(doc_id, field.name(), field.value())
    self._RemoveDocumentId(doc_id)

  def _AddTokens(self, doc_id, field_name, field_value, token_position):
    """Adds token occurrences for a given doc's field value."""
    for token in self._tokenizer.TokenizeValue(field_value, token_position):
      self._AddToken(doc_id, token)
      self._AddToken(doc_id, token.RestrictField(field_name))

  def _RemoveTokens(self, doc_id, field_name, field_value):
    """Removes tokens occurrences for a given doc's field value."""
    for token in self._tokenizer.TokenizeValue(field_value=field_value):
      self._RemoveToken(doc_id, token)
      self._RemoveToken(doc_id, token.RestrictField(field_name))

  def _AddToken(self, doc_id, token):
    """Adds a token occurrence for a document."""
    postings = self._inverted_index.get(token)
    if postings is None:
      self._inverted_index[token] = postings = PostingList()
    postings.Add(doc_id, token.position)

  def _RemoveToken(self, doc_id, token):
    """Removes a token occurrence for a document."""
    if token in self._inverted_index:
      postings = self._inverted_index[token]
      postings.Remove(doc_id, token.position)
      if not postings.postings:
        del self._inverted_index[token]

  def GetPostingsForToken(self, token):
    """Returns all document postings which for the token."""
    if token in self._inverted_index:
      return self._inverted_index[token].postings
    return []

  def GetSchema(self):
    """Returns the schema for the index."""
    return self._schema

  def __repr__(self):
    return _Repr(self, [('_inverted_index', self._inverted_index),
                        ('_schema', self._schema),
                        ('document_count', self.document_count)])


def _ScoreRequested(params):
  """Returns True if match scoring requested, False otherwise."""
  return params.has_scorer_spec() and params.scorer_spec().has_scorer()


def _GetFieldInDocument(document, field_name):
  """Find and return the field with the provided name in the document."""
  for f in document.field_list():
    if f.name() == field_name:
      return f
  return None


def _GetQueryNodeText(node):
  """Returns the text from the node, handling that it could be unicode."""
  return node.getText().encode('utf-8')


def _DateValueForField(string_value):
  """Returns the date object associated with a date field."""
  date_parts = [int(part) for part in string_value.split('-')]
  return datetime.date(*date_parts)


class _DocumentMatcher(object):
  """A class to match documents with a query."""

  def __init__(self, query, parser, inverted_index):
    self._query = query
    self._inverted_index = inverted_index
    self._parser = parser

  def _PostingsForToken(self, token):
    """Returns the postings for the token."""
    return self._inverted_index.GetPostingsForToken(token)

  def _MakeToken(self, value):
    """Makes a token from the given value."""
    return self._parser.TokenizeText(value)[0]

  def _PostingsForFieldToken(self, field, value):
    """Returns postings for the value occurring in the given field."""
    token = field + ':' + value
    token = self._MakeToken(token)
    return self._PostingsForToken(token)

  def _SplitPhrase(self, phrase):
    """Returns the list of tokens for the phrase."""
    phrase = phrase[1:len(phrase) - 1]
    return self._parser.TokenizeText(phrase)

  def _MatchPhrase(self, field, match, document):
    """Match a textual field with a phrase query node."""
    phrase = self._SplitPhrase(_GetQueryNodeText(match))
    if not phrase:
      return True
    field_text = self._parser.TokenizeText(field.value().string_value())

    posting = None
    for post in self._PostingsForFieldToken(field.name(), phrase[0].chars):
      if post.doc_id == document.id():
        posting = post
        break
    if not posting:
      return False

    def ExtractWords(tokens):
      return (token.chars for token in tokens)

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

    if (match.getType() in (QueryParser.TEXT, QueryParser.NAME) or
        match.getType() in _NUMBER_QUERY_TYPES):
      matching_docids = [
          post.doc_id for post in self._PostingsForFieldToken(
              field.name(), _GetQueryNodeText(match))]
      return document.id() in matching_docids

    if match.getType() is QueryParser.PHRASE:
      return self._MatchPhrase(field, match, document)

    if match.getType() is QueryParser.CONJUNCTION:
      return all(self._MatchTextField(field, child, document)
                 for child in match.children)

    if match.getType() is QueryParser.DISJUNCTION:
      return any(self._MatchTextField(field, child, document)
                 for child in match.children)

    if match.getType() is QueryParser.NEGATION:
      return not self._MatchTextField(field, match.children[0], document)


    return False

  def _MatchDateField(self, field, match, document):
    """Check if a date field matches a query tree node."""


    return self._MatchComparableField(
        field, match, _DateValueForField, _TEXT_QUERY_TYPES, document)


  def _MatchNumericField(self, field, match, document):
    """Check if a numeric field matches a query tree node."""
    return self._MatchComparableField(
        field, match, float, _NUMBER_QUERY_TYPES, document)


  def _MatchComparableField(
      self, field, match, cast_to_type, query_node_types,
      document):
    """A generic method to test matching for comparable types.

    Comparable types are defined to be anything that supports <, >, <=, >=, ==
    and !=. For our purposes, this is numbers and dates.

    Args:
      field: The document_pb.Field to test
      match: The query node to match against
      cast_to_type: The type to cast the node string values to
      query_node_types: The query node types that would be valid matches
      document: The document that the field is in

    Returns:
      True iff the field matches the query.

    Raises:
      UnsupportedOnDevError: Raised when an unsupported operator is used, or
      when the query node is of the wrong type.
    """

    field_val = cast_to_type(field.value().string_value())

    op = QueryParser.EQ

    if match.getType() in query_node_types:
      try:
        match_val = cast_to_type(_GetQueryNodeText(match))
      except ValueError:
        return False
    elif match.children:
      op = match.getType()
      try:
        match_val = cast_to_type(_GetQueryNodeText(match.children[0]))
      except ValueError:
        return False
    else:
      return False

    if op is QueryParser.EQ:
      return field_val == match_val
    if op is QueryParser.NE:
      return field_val != match_val
    if op is QueryParser.GT:
      return field_val > match_val
    if op is QueryParser.GE:
      return field_val >= match_val
    if op is QueryParser.LT:
      return field_val < match_val
    if op is QueryParser.LE:
      return field_val <= match_val
    raise UnsupportedOnDevError(
        'Operator %s not supported for numerical fields on development server.'
        % match.getText())

  def _MatchField(self, field_query_node, match, document):
    """Check if a field matches a query tree."""

    if isinstance(field_query_node, str):
      field = _GetFieldInDocument(document, field_query_node)
    else:
      field = _GetFieldInDocument(document, field_query_node.getText())
    if not field:
      return False

    if field.value().type() in _TEXT_DOCUMENT_FIELD_TYPES:
      return self._MatchTextField(field, match, document)

    if field.value().type() in _NUMBER_DOCUMENT_FIELD_TYPES:
      return self._MatchNumericField(field, match, document)

    if field.value().type() == document_pb.FieldValue.DATE:
      return self._MatchDateField(field, match, document)

    raise UnsupportedOnDevError(
        'Matching to field type of field "%s" (type=%d) is unsupported on '
        'dev server' % (field.name(), field.value().type()))

  def _MatchGlobal(self, match, document):
    for field in document.field_list():
      if self._MatchField(field.name(), match, document):
        return True
    return False

  def _CheckMatch(self, node, document):
    """Check if a document matches a query tree."""

    if node.getType() is QueryParser.CONJUNCTION:
      return all(self._CheckMatch(child, document) for child in node.children)

    if node.getType() is QueryParser.DISJUNCTION:
      return any(self._CheckMatch(child, document) for child in node.children)

    if node.getType() is QueryParser.NEGATION:
      return not self._CheckMatch(node.children[0], document)

    if node.getType() is QueryParser.RESTRICTION:
      field, match = node.children
      return self._MatchField(field, match, document)

    return self._MatchGlobal(node, document)

  def Matches(self, document):
    return self._CheckMatch(self._query, document)

  def FilterDocuments(self, documents):
    return (doc for doc in documents if self.Matches(doc))


class SimpleIndex(object):
  """A simple search service which uses a RAM-resident inverted file."""

  def __init__(self, index_spec):
    self._index_spec = index_spec
    self._documents = {}
    self._parser = SimpleTokenizer(split_restricts=False)
    self._inverted_index = RamInvertedIndex(SimpleTokenizer())

  @property
  def index_spec(self):
    """Returns the index specification for the index."""
    return self._index_spec

  def IndexDocuments(self, documents, response):
    """Indexes an iterable DocumentPb.Document."""
    for document in documents:
      doc_id = document.id()
      if not doc_id:
        doc_id = str(uuid.uuid4())
        document.set_id(doc_id)
      response.add_doc_id(doc_id)
      if doc_id in self._documents:
        old_document = self._documents[doc_id]
        self._inverted_index.RemoveDocument(old_document)
      self._documents[doc_id] = document
      new_status = response.add_status()
      new_status.set_code(search_service_pb.SearchServiceError.OK)
      self._inverted_index.AddDocument(doc_id, document)

  def DeleteDocuments(self, document_ids, response):
    """Deletes documents for the given document_ids."""
    for document_id in document_ids:
      if document_id in self._documents:
        document = self._documents[document_id]
        self._inverted_index.RemoveDocument(document)
        del self._documents[document_id]
      delete_status = response.add_status()
      delete_status.set_code(search_service_pb.SearchServiceError.OK)

  def Documents(self):
    """Returns the documents in the index."""
    return self._documents.values()

  def _TermFrequency(self, term, document):
    """Return the term frequency in the document."""
    return self._inverted_index.GetDocumentStats(document).TermFrequency(term)

  @property
  def document_count(self):
    """Returns the count of documents in the index."""
    return self._inverted_index.document_count

  def _DocumentCountForTerm(self, term):
    """Returns the document count for documents containing the term."""
    return len(self._PostingsForToken(Token(chars=term)))

  def _InverseDocumentFrequency(self, term):
    """Returns inverse document frequency of term."""
    doc_count = self._DocumentCountForTerm(term)
    if doc_count:
      return math.log10(self.document_count / float(doc_count))
    else:
      return 0

  def _TermFrequencyInverseDocumentFrequency(self, term, document):
    """Returns the term frequency times inverse document frequency of term."""
    return (self._TermFrequency(term, document) *
            self._InverseDocumentFrequency(term))

  def _ScoreDocument(self, document, score, terms):
    """Scores a document for the given query."""
    if not score:
      return 0
    tf_idf = 0
    for term in terms:
      tf_idf += self._TermFrequencyInverseDocumentFrequency(term, document)
    return tf_idf

  def _PostingsForToken(self, token):
    """Returns the postings for the token."""
    return self._inverted_index.GetPostingsForToken(token)

  def _CollectTerms(self, node):
    """Get all search terms for scoring."""
    if node.getType() in _TEXT_QUERY_TYPES:
      return set([_GetQueryNodeText(node)])
    elif node.children:
      result = set()
      for term_set in (self._CollectTerms(child) for child in node.children):
        result.update(term_set)
      return result
    return set()

  def _Evaluate(self, node, score=True):
    """Retrieve scored results for a search query."""
    doc_match = _DocumentMatcher(
        node, self._parser, self._inverted_index)

    matched_documents = doc_match.FilterDocuments(self._documents.itervalues())
    terms = self._CollectTerms(node)
    scored_documents = [
        _ScoredDocument(doc, self._ScoreDocument(doc, score, terms))
        for doc in matched_documents]
    return scored_documents

  def _Sort(self, docs, search_params, score):
    if score:
      return sorted(docs, key=lambda doc: doc.score, reverse=True)

    if not search_params.sort_spec_size():
      return sorted(docs, key=lambda doc: doc.document.order_id(), reverse=True)


    sort_spec = search_params.sort_spec(0)

    if not (sort_spec.has_default_value_text() or
            sort_spec.has_default_value_numeric()):
      raise Exception('A default value must be specified for sorting.')
    elif sort_spec.has_default_value_text():
      default_value = sort_spec.default_value_text()
    else:
      default_value = sort_spec.default_value_numeric()

    def SortKey(scored_doc):
      """Return the sort key for a document based on the request parameters."""
      field = _GetFieldInDocument(
          scored_doc.document, sort_spec.sort_expression())
      if not field:
        return default_value

      string_val = field.value().string_value()
      if field.value().type() in _NUMBER_DOCUMENT_FIELD_TYPES:
        return float(string_val)
      if field.value().type() is document_pb.FieldValue.DATE:
        return _DateValueForField(string_val)
      return string_val

    return sorted(docs, key=SortKey, reverse=sort_spec.sort_descending())

  def Search(self, search_request):
    """Searches the simple index for ."""
    query = urllib.unquote(search_request.query())
    query = query.strip()
    if not query:
      return [_ScoredDocument(document, 0) for document in
              copy.copy(self._documents.values())]
    if not isinstance(query, unicode):
      query = unicode(query, 'utf-8')
    query_tree = query_parser.Simplify(query_parser.Parse(query))

    score = _ScoreRequested(search_request)
    docs = self._Evaluate(query_tree, score=score)
    docs = self._Sort(docs, search_request, score)
    return docs

  def GetSchema(self):
    """Returns the schema for the index."""
    return self._inverted_index.GetSchema()

  def __repr__(self):
    return _Repr(self, [('_index_spec', self._index_spec),
                        ('_documents', self._documents),
                        ('_inverted_index', self._inverted_index)])


class SearchServiceStub(apiproxy_stub.APIProxyStub):
  """Simple RAM backed Search service stub.

  This stub provides the search_service_pb.SearchService.  But this is
  NOT a subclass of SearchService itself.  Services are provided by
  the methods prefixed by "_Dynamic_".
  """

  def __init__(self, service_name='search', index_file=None):
    """Constructor.

    Args:
      service_name: Service name expected for all calls.
      index_file: The file to which search indexes will be persisted.
    """
    self.__indexes = {}
    self.__index_file = index_file
    self.__index_file_lock = threading.Lock()
    super(SearchServiceStub, self).__init__(service_name)

    self.Read()

  def _InvalidRequest(self, status, exception):
    status.set_code(search_service_pb.SearchServiceError.INVALID_REQUEST)
    status.set_error_detail(exception.message)

  def _UnknownIndex(self, status, index_spec):
    status.set_code(search_service_pb.SearchServiceError.OK)
    status.set_error_detail('no index for %r' % index_spec)

  def _GetNamespace(self, namespace):
    """Get namespace name.

    Args:
      namespace: Namespace provided in request arguments.

    Returns:
      If namespace is None, returns the name of the current global namespace. If
      namespace is not None, returns namespace.
    """
    if namespace is not None:
      return namespace
    return namespace_manager.get_namespace()

  def _GetIndex(self, index_spec, create=False):
    namespace = self._GetNamespace(index_spec.namespace())

    index = self.__indexes.setdefault(namespace, {}).get(index_spec.name())
    if index is None:
      if create:
        index = SimpleIndex(index_spec)
        self.__indexes[namespace][index_spec.name()] = index
      else:
        return None
    elif index.index_spec.consistency() != index_spec.consistency():
      raise IndexConsistencyError(
          'Cannot create index of same name with different consistency mode '
          '(found %s, requested %s)' % (
              index.index_spec.consistency(), index_spec.consistency()))
    return index

  def _Dynamic_IndexDocument(self, request, response):
    """A local implementation of SearchService.IndexDocument RPC.

    Index a new document or update an existing document.

    Args:
      request: A search_service_pb.IndexDocumentRequest.
      response: An search_service_pb.IndexDocumentResponse.
    """
    params = request.params()
    try:
      index = self._GetIndex(params.index_spec(), create=True)
      index.IndexDocuments(params.document_list(), response)
    except IndexConsistencyError, exception:
      self._InvalidRequest(response.add_status(), exception)

  def _Dynamic_DeleteDocument(self, request, response):
    """A local implementation of SearchService.DeleteDocument RPC.

    Args:
      request: A search_service_pb.DeleteDocumentRequest.
      response: An search_service_pb.DeleteDocumentResponse.
    """
    params = request.params()
    index_spec = params.index_spec()
    try:
      index = self._GetIndex(index_spec)
      if index is None:
        self._UnknownIndex(response.add_status(), index_spec)
        return
      index.DeleteDocuments(params.doc_id_list(), response)
    except IndexConsistencyError, exception:
      self._InvalidRequest(response.add_status(), exception)

  def _Dynamic_ListIndexes(self, request, response):
    """A local implementation of SearchService.ListIndexes RPC.

    Args:
      request: A search_service_pb.ListIndexesRequest.
      response: An search_service_pb.ListIndexesResponse.

    Raises:
      ResponseTooLargeError: raised for testing admin console.
    """



    if request.has_app_id():
      if random.choice([True] + [False] * 9):
        raise apiproxy_errors.ResponseTooLargeError()

      for _ in xrange(random.randint(0, 2) * random.randint(5, 15)):
        new_index_spec = response.add_index_metadata().mutable_index_spec()
        new_index_spec.set_name(
            random.choice(list(_VISIBLE_PRINTABLE_ASCII - set('!'))) +
            ''.join(random.choice(list(_VISIBLE_PRINTABLE_ASCII))
                    for _ in xrange(random.randint(
                        0, search.MAXIMUM_INDEX_NAME_LENGTH))))
        new_index_spec.set_consistency(random.choice([
            search_service_pb.IndexSpec.GLOBAL,
            search_service_pb.IndexSpec.PER_DOCUMENT]))
      response.mutable_status().set_code(
          random.choice([search_service_pb.SearchServiceError.OK] * 10 +
                        [search_service_pb.SearchServiceError.TRANSIENT_ERROR] +
                        [search_service_pb.SearchServiceError.INTERNAL_ERROR]))
      return

    response.mutable_status().set_code(
        search_service_pb.SearchServiceError.OK)

    namespace = self._GetNamespace(request.params().namespace())
    if namespace not in self.__indexes or not self.__indexes[namespace]:
      return

    keys, indexes = zip(*sorted(
        self.__indexes[namespace].iteritems(), key=lambda v: v[0]))
    position = 0
    params = request.params()
    if params.has_start_index_name():
      position = bisect.bisect_left(keys, params.start_index_name())
      if (not params.include_start_index() and position < len(keys)
          and keys[position] == params.start_index_name()):
        position += 1
    elif params.has_index_name_prefix():
      position = bisect.bisect_left(keys, params.index_name_prefix())
    if params.has_offset():
      position += params.offset()
    end_position = position + params.limit()
    prefix = params.index_name_prefix()
    for index in indexes[min(position, len(keys)):min(end_position, len(keys))]:
      index_spec = index.index_spec
      if prefix and not index_spec.name().startswith(prefix):
        break
      metadata = response.add_index_metadata()
      new_index_spec = metadata.mutable_index_spec()
      new_index_spec.set_name(index_spec.name())
      new_index_spec.set_consistency(index_spec.consistency())
      if params.fetch_schema():
        self._AddSchemaInformation(index, metadata)

  def _AddSchemaInformation(self, index, metadata_pb):
    schema = index.GetSchema()
    for name in schema:
      field_types = schema[name]
      new_field_types = metadata_pb.add_field()
      new_field_types.MergeFrom(field_types)

  def _AddDocument(self, response, document, ids_only):
    doc = response.add_document()
    if ids_only:
      doc.set_id(document.id())
    else:
      doc.MergeFrom(document)

  def _Dynamic_ListDocuments(self, request, response):
    """A local implementation of SearchService.ListDocuments RPC.

    Args:
      request: A search_service_pb.ListDocumentsRequest.
      response: An search_service_pb.ListDocumentsResponse.
    """
    params = request.params()
    index = self._GetIndex(params.index_spec(), create=True)
    if index is None:
      self._UnknownIndex(response.mutable_status(), params.index_spec())
      return

    num_docs = 0
    start = not params.has_start_doc_id()
    for document in sorted(index.Documents(), key=lambda doc: doc.id()):
      if start:
        if num_docs < params.limit():
          self._AddDocument(response, document, params.keys_only())
          num_docs += 1
      else:
        if document.id() >= params.start_doc_id():
          start = True
          if (document.id() != params.start_doc_id() or
              params.include_start_doc()):
            self._AddDocument(response, document, params.keys_only())
            num_docs += 1

    response.mutable_status().set_code(
        search_service_pb.SearchServiceError.OK)

  def _RandomSearchResponse(self, request, response):

    random.seed()
    if random.random() < 0.03:
      raise apiproxy_errors.ResponseTooLargeError()
    response.mutable_status().set_code(
        random.choice([search_service_pb.SearchServiceError.OK] * 30 +
                      [search_service_pb.SearchServiceError.TRANSIENT_ERROR] +
                      [search_service_pb.SearchServiceError.INTERNAL_ERROR]))

    params = request.params()
    random.seed(params.query())
    total = random.randint(0, 100)


    if random.random() < 0.3:
      total = 0

    offset = 0
    if params.has_offset():
      offset = params.offset()

    remaining = max(0, total - offset)
    nresults = min(remaining, params.limit())
    matched_count = offset + nresults
    if remaining > nresults:
      matched_count += random.randint(1, 100)

    def RandomText(charset, min_len, max_len):
      return ''.join(random.choice(charset)
                     for _ in xrange(random.randint(min_len, max_len)))

    for i in xrange(nresults):
      seed = '%s:%s' % (params.query(), i + offset)
      random.seed(seed)
      result = response.add_result()
      doc = result.mutable_document()
      doc_id = RandomText(string.letters + string.digits, 8, 10)
      doc.set_id(doc_id)
      random.seed(doc_id)
      for _ in params.sort_spec_list():
        result.add_score(random.random())

      for name, probability in [('creator', 0.90), ('last_change', 0.40)]:
        if random.random() < probability:
          field = doc.add_field()
          field.set_name(name)
          value = field.mutable_value()
          value.set_type(document_pb.FieldValue.TEXT)
          value.set_string_value(
              RandomText(string.letters + string.digits, 2, 10)
              + '@google.com')

      field = doc.add_field()
      field.set_name('content')
      value = field.mutable_value()
      value.set_type(document_pb.FieldValue.TEXT)
      value.set_string_value(
          RandomText(string.printable, 0, 15) + params.query() +
          RandomText(string.printable + 10 * string.whitespace, 5, 5000))

      for i in xrange(random.randint(0, 2)):
        field = doc.add_field()
        field.set_name(RandomText(string.letters, 3, 7))
        value = field.mutable_value()
        value.set_type(document_pb.FieldValue.TEXT)
        value.set_string_value(RandomText(string.printable, 0, 100))

    response.set_matched_count(matched_count)

  def _DefaultFillSearchResponse(self, params, results, response):
    """Fills the SearchResponse with the first set of results."""
    position_range = range(0, min(params.limit(), len(results)))
    self._FillSearchResponse(results, position_range, params.cursor_type(),
                             _ScoreRequested(params), response)

  def _CopyBaseDocument(self, doc, doc_copy):
    doc_copy.set_id(doc.id())
    if doc.has_order_id():
      doc_copy.set_order_id(doc.order_id())
    if doc.has_language():
      doc_copy.set_language(doc.language())

  def _CopyDocument(self, doc, doc_copy, field_spec=None, ids_only=None):
    """Copies Document, doc, to doc_copy restricting fields to field_spec."""
    if ids_only:
      self._CopyBaseDocument(doc, doc_copy)
    elif field_spec and field_spec.name_list():
      self._CopyBaseDocument(doc, doc_copy)
      for field in doc.field_list():
        if field.name() in field_spec.name_list():
          doc_copy.add_field().CopyFrom(field)
    else:
      doc_copy.CopyFrom(doc)

  def _FillSearchResponse(self, results, position_range, cursor_type, score,
                          response, field_spec=None, ids_only=None):
    """Fills the SearchResponse with a selection of results."""
    for i in position_range:
      result = results[i]
      search_result = response.add_result()
      self._CopyDocument(result.document, search_result.mutable_document(),
                         field_spec, ids_only)
      if cursor_type is search_service_pb.SearchParams.PER_RESULT:
        search_result.set_cursor(result.document.id())
      if score:
        search_result.add_score(result.score)

  def _Dynamic_Search(self, request, response):
    """A local implementation of SearchService.Search RPC.

    Args:
      request: A search_service_pb.SearchRequest.
      response: An search_service_pb.SearchResponse.
    """
    if request.has_app_id():
      self._RandomSearchResponse(request, response)
      return

    index = None
    try:
      index = self._GetIndex(request.params().index_spec())
      if index is None:
        self._UnknownIndex(response.mutable_status(),
                           request.params().index_spec())
        return
    except IndexConsistencyError, exception:
      self._InvalidRequest(response.mutable_status(), exception)
      return

    params = request.params()
    results = index.Search(params)
    response.set_matched_count(len(results))

    offset = 0
    if params.has_cursor():
      positions = [i for i in range(len(results)) if results[i].document.id() is
                   params.cursor()]
      if positions:
        offset = positions[0] + 1
    elif params.has_offset():
      offset = params.offset()



    if offset < len(results):
      position_range = range(
          offset,
          min(offset + params.limit(), len(results)))
    else:
      position_range = range(0)
    field_spec = None
    if params.has_field_spec():
      field_spec = params.field_spec()
    self._FillSearchResponse(results, position_range, params.cursor_type(),
                             _ScoreRequested(params), response, field_spec,
                             params.keys_only())
    if (params.cursor_type() is search_service_pb.SearchParams.SINGLE and
        len(position_range)):
      response.set_cursor(
          results[position_range[len(position_range) - 1]].document.id())

    response.mutable_status().set_code(search_service_pb.SearchServiceError.OK)

  def __repr__(self):
    return _Repr(self, [('__indexes', self.__indexes)])

  def Write(self):
    """Write search indexes to the index file.

    This method is a no-op if index_file is set to None.
    """
    if not self.__index_file:
      return





    descriptor, tmp_filename = tempfile.mkstemp(
        dir=os.path.dirname(self.__index_file))
    tmpfile = os.fdopen(descriptor, 'wb')

    pickler = pickle.Pickler(tmpfile, protocol=1)
    pickler.fast = True
    pickler.dump(self.__indexes)

    tmpfile.close()

    self.__index_file_lock.acquire()
    try:
      try:

        os.rename(tmp_filename, self.__index_file)
      except OSError:


        os.remove(self.__index_file)
        os.rename(tmp_filename, self.__index_file)
    finally:
      self.__index_file_lock.release()

  def _ReadFromFile(self):
    self.__index_file_lock.acquire()
    try:
      if os.path.isfile(self.__index_file):
        return pickle.load(open(self.__index_file, 'rb'))
      else:
        logging.warning(
            'Could not read search indexes from %s', self.__index_file)
    except (AttributeError, LookupError, ImportError, NameError, TypeError,
            ValueError, pickle.PickleError), e:
      raise apiproxy_errors.ApplicationError(
          search_service_pb.SearchServiceError.INTERNAL_ERROR,
          'Could not read indexes from %s. Try running with the '
          '--clear_search_index flag. Cause:\n%r' % (self.__index_file, e))
    finally:
      self.__index_file_lock.release()

    return {}

  def Read(self):
    """Read search indexes from the index file.

    This method is a no-op if index_file is set to None.
    """
    if not self.__index_file:
      return
    self.__indexes = self._ReadFromFile()
