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










import random
import string
import urllib

from google.appengine.datastore import document_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api.search import search_api
from google.appengine.api.search import search_service_pb
from google.appengine.runtime import apiproxy_errors

__all__ = ['IndexConsistencyError',
           'SearchServiceStub',
           'SimpleIndex',
           'RamInvertedIndex',
           'SimpleTokenizer'
          ]


class IndexConsistencyError(Exception):
  """Indicates attempt to create index with same name different consistency."""


def _Repr(class_instance, ordered_dictionary):
  """Generates an unambiguous representation for instance and ordered dict."""
  return 'search_api.%s(%s)' % (class_instance.__class__.__name__, ', '.join(
      ["%s='%s'" % (key, value) for (key, value) in ordered_dictionary
       if value is not None and value != []]))


class SimpleTokenizer(object):
  """A simple tokenizer that breaks up string on white space characters."""

  def __init__(self, split_restricts=True):
    self._split_restricts = split_restricts

  def Tokenize(self, content):
    tokens = []
    for token in content.lower().split():
      if ':' in token and self._split_restricts:
        tokens.extend(token.split(':'))
      else:
        tokens.append(token)
    return tokens


class RamInvertedIndex(object):
  """A simple RAM-resident inverted file over documents."""

  def __init__(self, tokenizer):
    self._tokenizer = tokenizer
    self._inverted_index = {}

  def AddDocument(self, document):
    """Adds a document into the index."""
    doc_id = document.doc_id()
    for field in document.field_list():
      self._AddTokens(doc_id, field.name(), field.value().string_value())

  def RemoveDocument(self, document):
    """Removes a document from the index."""
    doc_id = document.doc_id()
    for field in document.field_list():
      self._RemoveTokens(doc_id, field.name(), field.value().string_value())

  def _AddTokens(self, doc_id, field_name, field_value):
    """Adds token occurrences for a given doc's field value."""
    for token in self._tokenizer.Tokenize(field_value):
      self._AddToken(doc_id, token)
      self._AddToken(doc_id, field_name + ':' + token)

  def _RemoveTokens(self, doc_id, field_name, field_value):
    """Removes tokens occurrences for a given doc's field value."""
    for token in self._tokenizer.Tokenize(field_value):
      self._RemoveToken(doc_id, token)
      self._RemoveToken(doc_id, field_name + ':' + token)

  def _AddToken(self, doc_id, token):
    """Adds a token occurrence for a document."""
    doc_ids = self._inverted_index.get(token)
    if doc_ids is None:
      self._inverted_index[token] = doc_ids = set([])
    doc_ids.add(doc_id)

  def _RemoveToken(self, doc_id, token):
    """Removes a token occurrence for a document."""
    if token in self._inverted_index:
      doc_ids = self._inverted_index[token]
      if doc_id in doc_ids:
        doc_ids.remove(doc_id)
        if not doc_ids:
          del self._inverted_index[token]

  def GetDocsForToken(self, token):
    """Returns all documents which contain the token."""
    if token in self._inverted_index:
      return self._inverted_index[token]
    return []

  def __repr__(self):
    return _Repr(self, [('_inverted_index', self._inverted_index)])


class SimpleIndex(object):
  """A simple search service which uses a RAM-resident inverted file."""

  def __init__(self, index_spec):
    self._index_spec = index_spec
    self._documents = {}
    self._parser = SimpleTokenizer(split_restricts=False)
    self._inverted_index = RamInvertedIndex(SimpleTokenizer())

  @property
  def IndexSpec(self):
    """Returns the index specification for the index."""
    return self._index_spec

  def IndexDocuments(self, documents, response):
    """Indexes an iterable DocumentPb.Document."""
    for document in documents:
      doc_id = document.doc_id()
      if doc_id in self._documents:
        old_document = self._documents[doc_id]
        self._inverted_index.RemoveDocument(old_document)
      self._documents[doc_id] = document
      new_status = response.add_status()
      new_status.set_status(search_service_pb.SearchServiceError.OK)
      self._inverted_index.AddDocument(document)

  def DeleteDocuments(self, document_ids, response):
    """Deletes documents for the given document_ids."""
    for document_id in document_ids:
      if document_id in self._documents:
        document = self._documents[document_id]
        self._inverted_index.RemoveDocument(document)
        del self._documents[document_id]
      delete_status = response.add_status()
      delete_status.set_status(search_service_pb.SearchServiceError.OK)

  def _DocumentsForDocIds(self, doc_ids):
    """Returns the documents for the given doc_ids."""
    docs = []
    for doc_id in doc_ids:
      if doc_id in self._documents:
        docs.append(self._documents[doc_id])
    return docs

  def Search(self, search_request):
    """Searches the simple index for ."""
    query = urllib.unquote(search_request.query())
    tokens = self._parser.Tokenize(query)
    if not tokens:
      return self._documents.values()
    else:
      token = tokens[0]
      doc_ids = self._inverted_index.GetDocsForToken(token)
      if len(tokens) > 1:
        for token in tokens[1]:
          next_doc_ids = self._inverted_index.GetDocsForToken(token)
          doc_ids = [doc_id for doc_id in doc_ids if doc_id in next_doc_ids]
          if not doc_ids:
            break
      return self._DocumentsForDocIds(doc_ids)

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

  def __init__(self, service_name='search'):
    """Constructor.

    Args:
      service_name: Service name expected for all calls.
    """
    self.__indexes = {}
    super(SearchServiceStub, self).__init__(service_name)

  def _InvalidRequest(self, status, exception):
    status.set_status(search_service_pb.SearchServiceError.INVALID_REQUEST)
    status.set_error_detail(exception.message)

  def _UnknownIndex(self, status, index_spec):
    status.set_status(search_service_pb.SearchServiceError.INVALID_REQUEST)
    status.set_error_detail('no index for %r' % index_spec)

  def _GetOrCreateIndex(self, index_spec, create=True):
    index = self.__indexes.get(index_spec.index_name())
    if index is None:
      if create:
        index = SimpleIndex(index_spec)
        self.__indexes[index_spec.index_name()] = index
      else:
        return None
    elif index.IndexSpec.consistency() != index_spec.consistency():
      raise IndexConsistencyError('Cannot creat index of same name with'
                                  ' different consistency mode')
    return index

  def _GetIndex(self, index_spec):
    return self._GetOrCreateIndex(index_spec=index_spec, create=False)

  def _Dynamic_CreateIndex(self, request, response):
    """A local implementation of SearchService.CreateIndex RPC.

    Create an index based on a supplied IndexSpec.

    Args:
      request: A search_service_pb.CreateIndexRequest.
      response: An search_service_pb.CreateIndexResponse.
    """
    index_spec = request.index_spec()
    index = None
    try:
      index = self._GetOrCreateIndex(index_spec)
    except IndexConsistencyError, exception:
      self._InvalidRequest(response.mutable_status(), exception)
      return
    spec_pb = response.mutable_index_spec()
    spec_pb.MergeFrom(index.IndexSpec)
    response.mutable_status().set_status(
        search_service_pb.SearchServiceError.OK)

  def _Dynamic_IndexDocument(self, request, response):
    """A local implementation of SearchService.IndexDocument RPC.

    Index a new document or update an existing document.

    Args:
      request: A search_service_pb.IndexDocumentRequest.
      response: An search_service_pb.IndexDocumentResponse.
    """
    params = request.params()
    try:
      index = self._GetOrCreateIndex(params.index_spec())
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
      index.DeleteDocuments(params.document_id_list(), response)
    except IndexConsistencyError, exception:
      self._InvalidRequest(response.add_status(), exception)

  def _Dynamic_ListIndexes(self, request, response):
    """A local implementation of SearchService.ListIndexes RPC.

    Args:
      request: A search_service_pb.ListIndexesRequest.
      response: An search_service_pb.ListIndexesResponse.
    """



    if request.has_app_id():
      if random.choice([True] + [False] * 9):
        raise apiproxy_errors.ResponseTooLargeError()

      for _ in xrange(random.randint(0, 2) * random.randint(5, 15)):
        new_index_spec = response.add_index_metadata().mutable_index_spec()
        new_index_spec.set_index_name(
            ''.join(random.choice(string.printable)
                    for _ in xrange(random.randint(
                        1, search_api._MAXIMUM_INDEX_NAME_LENGTH))))
        new_index_spec.set_consistency(random.choice([
            search_service_pb.IndexSpec.GLOBAL,
            search_service_pb.IndexSpec.PER_DOCUMENT]))
      response.mutable_status().set_status(
          random.choice([search_service_pb.SearchServiceError.OK] * 10 +
                        [search_service_pb.SearchServiceError.TRANSIENT_ERROR] +
                        [search_service_pb.SearchServiceError.INTERNAL_ERROR]))
      return

    for index in self.__indexes.values():
      index_spec = index.IndexSpec
      new_index_spec = response.add_index_metadata().mutable_index_spec()
      new_index_spec.set_index_name(index_spec.index_name())
      new_index_spec.set_consistency(index_spec.consistency())
    response.mutable_status().set_status(
        search_service_pb.SearchServiceError.OK)

  def _RandomSearchResponse(self, request, response):

    if random.random() < 0.1:
      raise apiproxy_errors.ResponseTooLargeError()

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
      doc.set_doc_id(doc_id)
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

    response.mutable_status().set_status(
        random.choice([search_service_pb.SearchServiceError.OK] * 10 +
                      [search_service_pb.SearchServiceError.TRANSIENT_ERROR] +
                      [search_service_pb.SearchServiceError.INTERNAL_ERROR]))
    response.set_matched_count(matched_count)

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




    params = request.params()
    docs_to_return = 20
    if params.has_limit():
      docs_to_return = params.limit()

    results = index.Search(params)

    response.set_matched_count(len(results))

    count = 0
    for i in xrange(len(results)):
      result = results[i]
      search_result = response.add_result()
      search_result.mutable_document().CopyFrom(result)
      count += 1
      if count >= docs_to_return:
        break
    response.status().set_status(search_service_pb.SearchServiceError.OK)

  def __repr__(self):
    return _Repr(self, [('__indexes', self.__indexes)])
