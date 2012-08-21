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




"""Search API module."""

from search import AddDocumentError
from search import AddError
from search import AddResult
from search import AtomField
from search import Cursor
from search import DateField
from search import Document
from search import Error
from search import ExpressionError
from search import Field
from search import FieldExpression
from search import GeoField
from search import GeoPoint
from search import HtmlField
from search import Index
from search import InternalError
from search import InvalidRequest
from search import list_indexes
from search import ListIndexesResponse
from search import ListResponse
from search import MatchScorer
from search import MAXIMUM_DOCUMENT_ID_LENGTH
from search import MAXIMUM_DOCUMENTS_PER_ADD_REQUEST
from search import MAXIMUM_DOCUMENTS_RETURNED_PER_SEARCH
from search import MAXIMUM_EXPRESSION_LENGTH
from search import MAXIMUM_FIELD_ATOM_LENGTH
from search import MAXIMUM_FIELD_NAME_LENGTH
from search import MAXIMUM_FIELD_VALUE_LENGTH
from search import MAXIMUM_FIELDS_RETURNED_PER_SEARCH
from search import MAXIMUM_INDEX_NAME_LENGTH
from search import MAXIMUM_INDEXES_RETURNED_PER_LIST_REQUEST
from search import MAXIMUM_LIST_INDEXES_OFFSET
from search import MAXIMUM_NUMBER_FOUND_ACCURACY
from search import MAXIMUM_QUERY_LENGTH
from search import MAXIMUM_SEARCH_OFFSET
from search import MAXIMUM_SORTED_DOCUMENTS
from search import NumberField
from search import OperationResult
from search import Query
from search import QueryError
from search import QueryOptions
from search import RemoveDocumentError
from search import RemoveError
from search import RemoveResult
from search import RescoringMatchScorer
from search import ScoredDocument
from search import SearchResults
from search import SortExpression
from search import SortOptions
from search import TextField
from search import TransientError
