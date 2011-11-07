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




"""A Python Search API used by app developers.

Contains methods used to interface with Search API.
Contains API classes that forward to apiproxy.
"""







import datetime
import re
import string
import sys

from google.appengine.datastore import document_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_types
from google.appengine.api import namespace_manager
from google.appengine.api.search import expression_parser
from google.appengine.api.search import query_parser
from google.appengine.api.search import search_service_pb
from google.appengine.runtime import apiproxy_errors


__all__ = [
    'AtomField',
    'DateField',
    'DeleteDocumentResponse',
    'Document',
    'Error',
    'Field',
    'FieldExpression',
    'HtmlField',
    'Index',
    'IndexDocumentResponse',
    'ListIndexesResponse',
    'ListDocumentsResponse',
    'NumberField',
    'OperationResult',
    'SearchRequest',
    'SearchResult',
    'SearchResponse',
    'SortSpec',
    'TextField',
    'list_indexes',
    ]

_MAXIMUM_INDEX_NAME_LENGTH = 100
_MAXIMUM_FIELD_VALUE_LENGTH = 1024 * 1024
_MAXIMUM_FIELD_ATOM_LENGTH = 500
_LANGUAGE_LENGTH = 2
_MAXIMUM_FIELD_NAME_LENGTH = 500
_MAXIMUM_CURSOR_LENGTH = 1000
_MAXIMUM_DOCUMENT_ID_LENGTH = 100
_MAXIMUM_STRING_LENGTH = 500
_MAXIMUM_EXPRESSION_LENGTH = 5000

_ASCII_PRINTABLE = frozenset(set(string.printable) - set(string.whitespace) |
                             set(' '))
_FIELD_NAME_PATTERN = '^[A-Za-z][A-Za-z0-9_]*$'


_PROTO_FIELDS_STRING_VALUE = frozenset([document_pb.FieldValue.TEXT,
                                        document_pb.FieldValue.HTML,
                                        document_pb.FieldValue.ATOM])



_INDEX_MAP = {}


class Error(Exception):
  """Indicates a call on the search API has failed."""

  def __init__(self, operation_result=None, response=None):
    """Initializer.

    Args:
      operation_result: The result of some API operation.
      response: The response to some request on the search API.
    """
    Exception.__init__(self)
    self._operation_result = operation_result
    self._response = response

  @property
  def operation_result(self):
    """The result of some API operation."""
    return self._operation_result

  @property
  def response(self):
    """The response to some request on the search API."""
    return self._response

  def __str__(self):
    if self._operation_result:
      if self._operation_result.message is not None:
        return self._operation_result.message
    return ''


_KNOWN_SEARCH_ERROR_SET = set([
    search_service_pb.SearchServiceError.INVALID_REQUEST,
    search_service_pb.SearchServiceError.TRANSIENT_ERROR,
    search_service_pb.SearchServiceError.INTERNAL_ERROR
    ])


def _ToSearchError(error, response):
  """Translate an application error to a search Error, if possible.

  Args:
    error: An ApplicationError to translate.
    response: The response to the API request.

  Returns:
    An Error if the error is known, otherwise the given
    apiproxy_errors.ApplicationError.
  """
  if error.application_error in _KNOWN_SEARCH_ERROR_SET:
    return Error(
        _NewOperationResult(error.application_error, error.error_detail),
        response)
  return error


def _RaiseInternalError(message, response):
  """Raises an Error with INTERNAL_ERROR, given message and response."""
  raise Error(OperationResult(OperationResult.INTERNAL_ERROR, message),
              response)


def _CheckInteger(value, name, zero_ok=True, upper_bound=None):
  """Checks whether value is an integer between the lower and upper bounds.

  Args:
    value: The value to check.
    name: The name of the value, to use in error messages.
    zero_ok: True if zero is allowed.
    upper_bound: The upper (inclusive) bound of the value. Optional.

  Returns:
    The checked value.

  Raises:
    ValueError: If the value is not a int or long, or is out of range.
  """
  datastore_types.ValidateInteger(value, name, ValueError, empty_ok=True,
                                  zero_ok=zero_ok)
  if upper_bound is not None and value > upper_bound:
    raise ValueError('%s, %d must be <= %d' % (name, value, upper_bound))
  return value


def _CheckEnum(value, name, values=None):
  """Checks whether value is a member of the set of values given.

  Args:
    value: The value to check.
    name: The name of the value, to use in error messages.
    values: The iterable of possible values.

  Returns:
    The checked value.

  Raises:
    ValueError: If the value is not one of the allowable values.
  """
  if value not in values:
    raise ValueError('%s, %r must be in %s' % (name, value, values))
  return value


def _CheckNumber(value, name):
  """Checks whether value is a number.

  Args:
    value: The value to check.
    name: The name of the value, to use in error messages.

  Returns:
    The checked value.

  Raises:
    TypeError: If the value is not a number.
  """
  if not isinstance(value, (int, long, float)):
    raise TypeError('%s must be a number' % name)
  return value


def _CheckStatus(status, response=None):
  """Checks whether a RequestStatus has a value of OK.

  Args:
    status: The RequestStatus to check.
    response: The response to the request.

  Returns:
    The response.

  Raises:
    Error: If the value of status is not OK.
  """
  if status.code() != search_service_pb.SearchServiceError.OK:
    raise Error(_NewOperationResultFromPb(status), response)
  return response


def _ValidateString(value,
                    name='unused',
                    max_len=_MAXIMUM_STRING_LENGTH,
                    empty_ok=False,
                    type_exception=TypeError,
                    value_exception=ValueError):
  """Raises an exception if value is not a valid string or a subclass thereof.

  A string is valid if it's not empty, no more than _MAXIMUM_STRING_LENGTH
  bytes. The exception type can be specified with the exception
  arguments for type and value issues.

  Args:
    value: The value to validate.
    name: The name of this value; used in the exception message.
    max_len: The maximum allowed length, in bytes.
    empty_ok: Allow empty value.
    type_exception: The type of exception to raise if not a basestring.
    value_exception: The type of exception to raise if invalid value.

  Returns:
    The checked string.

  Raises:
    TypeError: If value is not a basestring or subclass.
    ValueError: If the value is None or longer than max_len.
  """
  if value is None and empty_ok:
    return
  if value is not None and not isinstance(value, basestring):
    raise type_exception('%s should be a string; received %s (a %s):' %
                         (name, value, datastore_types.typename(value)))
  if not value and not empty_ok:
    raise value_exception('%s must not be empty.' % name)

  encoded_value = value
  if isinstance(value, unicode):
    encoded_value = value.encode('utf-8')

  if len(encoded_value) > max_len:
    raise value_exception('%s must be under %d bytes.' % (name, max_len))
  return value


def _ValidatePrintableAsciiNotReserved(value, name):
  """Raises an exception if value is not printable ASCII string nor reserved.

  Non-space whitespace characters are also excluded. Printable ASCII
  strings starting with '!' are reserved for internal use.

  Args:
    value: The value to validate.
    name: The name of this value; use in the exception message.

  Returns:
    The checked value.

  Raises:
    ValueError: If the value is not ASCII printable or starts with '!'
  """
  for char in value:
    if char not in _ASCII_PRINTABLE:
      raise ValueError(
          '%s must be printable ASCII and not non-space whitespace: %s'
          % (name, value))
  if value.startswith('!'):
    raise ValueError('%s must not start with "!": %s' % (name, value))
  return value


def _CheckIndexName(index_name):
  """Checks index_name is a string which is not too long, and returns it.

  Index names must be ASCII printable, not reserved (start with '!') nor
  include non-space whitespace characters.
  """
  _ValidateString(index_name, 'index name', _MAXIMUM_INDEX_NAME_LENGTH)
  return _ValidatePrintableAsciiNotReserved(index_name, 'index_name')


def _CheckFieldName(name):
  """Checks field name is not too long and matches field name pattern.

  Field name pattern: "[A-Za-z][A-Za-z0-9_]*".
  """
  _ValidateString(name, 'name', _MAXIMUM_FIELD_NAME_LENGTH)
  if not re.match(_FIELD_NAME_PATTERN, name):
    raise ValueError('field name "%s" should match pattern: %s' %
                     (name, _FIELD_NAME_PATTERN))
  return name


def _CheckExpression(expression):
  """Checks whether the expression is a string."""
  expression = _ValidateString(expression, max_len=_MAXIMUM_EXPRESSION_LENGTH)
  expression_parser.Parse(expression)
  return expression


def _CheckFieldNames(names):
  """Checks each name in names is a valid field name."""
  for name in names:
    _CheckFieldName(name)
  return names


def _GetList(a_list):
  """Utility function that conversts None to the empty list."""
  if a_list is None:
    return []
  else:
    return list(a_list)


def _ConvertToList(arg):
  """Converts arg to a list, empty if None, single element if not a list."""
  if isinstance(arg, basestring):
    return [arg]
  if arg is not None:
    try:
      return list(iter(arg))
    except TypeError:
      return [arg]
  return []


def _CheckDocumentId(doc_id):
  """Checks doc_id is a valid document identifier, and returns it.

  Document ids must be ASCII printable, not include non-space whitespace
  characters, and not start with '!'.
  """
  _ValidateString(doc_id, 'doc_id', _MAXIMUM_DOCUMENT_ID_LENGTH)
  _ValidatePrintableAsciiNotReserved(doc_id, 'doc_id')
  return doc_id


def _CheckText(value, name='value', empty_ok=True):
  """Checks the field text is a valid string."""
  return _ValidateString(value, name, _MAXIMUM_FIELD_VALUE_LENGTH, empty_ok)


def _CheckHtml(html):
  """Checks the field html is a valid HTML string."""
  return _ValidateString(html, 'html', _MAXIMUM_FIELD_VALUE_LENGTH,
                         empty_ok=True)


def _CheckAtom(atom):
  """Checks the field atom is a valid string."""
  return _ValidateString(atom, 'atom', _MAXIMUM_FIELD_ATOM_LENGTH,
                         empty_ok=True)


def _CheckDate(date):
  """Checks the date is a datetime.date, but not a datetime.datetime."""
  if not isinstance(date, datetime.date) or isinstance(date, datetime.datetime):
    raise TypeError('date %s must be a date but not a datetime' % date)
  return date


def _CheckLanguage(language):
  """Checks language is None or a string of _LANGUAGE_LENGTH."""
  if language is None:
    return None
  if not isinstance(language, basestring):
    raise TypeError('language code must be a string')
  if len(language) != _LANGUAGE_LENGTH:
    raise ValueError('language should have a length of %d'
                     % _LANGUAGE_LENGTH)
  return language


def _Repr(class_instance, ordered_dictionary):
  """Generates an unambiguous representation for instance and ordered dict."""
  return 'search.%s(%s)' % (class_instance.__class__.__name__, ', '.join(
      ["%s='%s'" % (key, value) for (key, value) in ordered_dictionary
       if value is not None and value != []]))


def _ListIndexesResponseToList(response):
  """Returns a ListIndexesResponse constructed from list_indexes response pb."""
  return ListIndexesResponse(
      indexes=[_NewIndexFromPb(index_spec.index_spec())
               for index_spec in response.index_metadata_list()])




def list_indexes(namespace='', offset=None, limit=None,
                 start_index_name=None, include_start_index=True,
                 index_name_prefix=None, **kwargs):
  """Returns a list of available indexes.

  Args:
    namespace: The namespace of indexes to be returned.
    offset: The offset of the first returned index.
    limit: The number of indexes to return.
    start_index_name: The name of the first index to be returned.
    include_start_index: Whether or not to return the start index.
    index_name_prefix: The prefix used to select returned indexes.

  Returns:
    The ListIndexesResponse containing a list of available indexes.

  Raises:
    InternalError: If the request fails on internal servers.
  """
  args_diff = set(kwargs.iterkeys()) - frozenset(['app_id'])
  if args_diff:
    raise TypeError('Invalid arguments: %s' % ', '.join(args_diff))


  request = search_service_pb.ListIndexesRequest()
  params = request.mutable_params()

  if namespace is None:
    namespace = namespace_manager.get_namespace()
  if namespace is None:
    namespace = ''
  namespace_manager.validate_namespace(namespace, exception=ValueError)
  params.set_namespace(namespace)
  if offset is not None:
    params.set_offset(_CheckInteger(offset, 'offset', zero_ok=True))
  if limit is not None:
    params.set_limit(_CheckInteger(limit, 'limit', zero_ok=False))
  if start_index_name is not None:
    params.set_start_index_name(
        _ValidateString(start_index_name, "start_index_name",
                        _MAXIMUM_INDEX_NAME_LENGTH,
                        empty_ok=False))
  if include_start_index is not None:
    params.set_include_start_index(bool(include_start_index))
  if index_name_prefix is not None:
    params.set_index_name_prefix(
        _ValidateString(index_name_prefix, "index_name_prefix",
                        _MAXIMUM_INDEX_NAME_LENGTH,
                        empty_ok=False))

  response = search_service_pb.ListIndexesResponse()
  if 'app_id' in kwargs:
    request.set_app_id(kwargs.get('app_id'))

  try:
    apiproxy_stub_map.MakeSyncCall('search', 'ListIndexes', request, response)
  except apiproxy_errors.ApplicationError, e:
    raise _ToSearchError(e, _ListIndexesResponseToList(response))

  return _CheckStatus(response.status(), _ListIndexesResponseToList(response))


class Field(object):
  """An abstract base class which represents a field of a document.

  This class should not be directly instantiated.
  """

  def __init__(self, name, value, language=None):
    """Initializer.

    Args:
      name: The name of the field. Field names must have maximum length
        _MAXIMUM_FIELD_NAME_LENGTH and match pattern "[A-Za-z][A-Za-z0-9_]*".
      value: The value of the field which can be a str, unicode or date.
      language: The ISO 693-1 two letter code of the language used in the value.
        See http://www.sil.org/iso639-3/codes.asp?order=639_1&letter=%25 for a
        list of valid codes. Correct specification of language code will assist
        in correct tokenization of the field. If None is given, then the
        language code of the document will be used.

    Raises:
      TypeError: If any of the parameters have invalid types, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have invalid values.
    """
    self._name = _CheckFieldName(name)
    self._value = self._CheckValue(value)
    self._language = _CheckLanguage(language)

  @property
  def name(self):
    """Returns the name of the field."""
    return self._name

  @property
  def language(self):
    """Returns the code of the language the content in value is written in."""
    return self._language

  @property
  def value(self):
    """Returns the value of the field."""
    return self._value

  def _CheckValue(self, value):
    """Checks the value is valid for the given type.

    Args:
      value: The value to check.

    Returns:
      The checked value.
    """
    raise NotImplementedError('_CheckValue is an abstract method')

  def __repr__(self):
    return _Repr(self, [('name', self.name), ('language', self.language),
                        ('value', self.value)])

  def __eq__(self, other):
    return isinstance(other, type(self)) and self.__key() == other.__key()

  def __ne__(self, other):
    return not self == other

  def __key(self):
    return (self.name, self.value, self.language)

  def __hash__(self):
    return hash(self.__key())

  def __str__(self):
    return repr(self)


def _CopyFieldToProtocolBuffer(field, pb):
  """Copies field's contents to a document_pb.Field protocol buffer."""
  pb.set_name(field.name)
  field_value_pb = pb.mutable_value()
  if field.language:
    field_value_pb.set_language(field.language)
  if field.value:
    field._CopyValueToProtocolBuffer(field_value_pb)
  return pb


class TextField(Field):
  """A Field that has text content.

  The following example shows a text field named signature with Polish content:
    TextField(name='signature', value='brzydka pogoda', language='pl')
  """

  def __init__(self, name, value=None, language=None):
    """Initializer.

    Args:
      name: The name of the field.
      value: A str or unicode object containing text.
      language: The code of the language the value is encoded in.

    Raises:
      TypeError: If value is not a string.
      ValueError: If value is longer than allowed.
    """
    Field.__init__(self, name, value, language)

  def _CheckValue(self, value):
    return _CheckText(value)

  def _CopyValueToProtocolBuffer(self, field_value_pb):
    field_value_pb.set_type(document_pb.FieldValue.TEXT)
    if isinstance(self.value, unicode):
      field_value_pb.set_string_value(self.value.encode('utf-8'))
    else:
      field_value_pb.set_string_value(self.value)


class HtmlField(Field):
  """A Field that has HTML content.

  The following example shows an html field named content:
    HtmlField(name='content', value='<html>herbata, kawa</html>', language='pl')
  """

  def __init__(self, name, value=None, language=None):
    """Initializer.

    Args:
      name: The name of the field.
      value: A str or unicode object containing the searchable content of the
        Field.
      language: The code of the language the value is encoded in.

    Raises:
      TypeError: If value is not a string.
      ValueError: If value is longer than allowed.
    """
    Field.__init__(self, name, value, language)

  def _CheckValue(self, value):
    return _CheckHtml(value)

  def _CopyValueToProtocolBuffer(self, field_value_pb):
    field_value_pb.set_type(document_pb.FieldValue.HTML)
    field_value_pb.set_string_value(self.value)


class AtomField(Field):
  """A Field that has content to be treated as a single token for indexing.

  The following example shows an atom field named contributor:
    AtomField(name='contributor', value='foo@bar.com')
  """

  def __init__(self, name, value=None, language=None):
    """Initializer.

    Args:
      name: The name of the field.
      value: A str or unicode object to be treated as an indivisible text value.
      language: The code of the language the value is encoded in.

    Raises:
      TypeError: If value is not a string.
      ValueError: If value is longer than allowed.
    """
    Field.__init__(self, name, value, language)

  def _CheckValue(self, value):
    return _CheckAtom(value)

  def _CopyValueToProtocolBuffer(self, field_value_pb):
    field_value_pb.set_type(document_pb.FieldValue.ATOM)
    field_value_pb.set_string_value(self.value)


class DateField(Field):
  """A Field that has a date value.

  The following example shows an date field named creation_date:
    DateField(name='creation_date', value=datetime.date(2011, 03, 11))
  """

  def __init__(self, name, value=None):
    """Initializer.

    Args:
      name: The name of the field.
      value: A datetime.date but not a datetime.datetime.

    Raises:
      TypeError: If value is not a datetime.date or is a datetime.datetime.
    """
    Field.__init__(self, name, value)

  def _CheckValue(self, value):
    return _CheckDate(value)

  def _CopyValueToProtocolBuffer(self, field_value_pb):
    field_value_pb.set_type(document_pb.FieldValue.DATE)
    field_value_pb.set_string_value(self.value.isoformat())


class NumberField(Field):
  """A Field that has a numeric value.

  The following example shows a number field named size:
    NumberField(name='size', value=10)
  """

  def __init__(self, name, value=None):
    """Initializer.

    Args:
      name: The name of the field.
      value: A numeric value.

    Raises:
      TypeError: If value is not numeric.
    """
    Field.__init__(self, name, value)

  def _CheckValue(self, value):
    return _CheckNumber(value, 'field value')

  def _CopyValueToProtocolBuffer(self, field_value_pb):
    field_value_pb.set_type(document_pb.FieldValue.NUMBER)
    field_value_pb.set_string_value(str(self.value))


def _GetValue(value_pb):
  """Gets the value from the value_pb."""
  if value_pb.type() in _PROTO_FIELDS_STRING_VALUE:
    if value_pb.has_string_value():
      return value_pb.string_value()
    return None
  if value_pb.type() == document_pb.FieldValue.DATE:
    if value_pb.has_string_value():
      return datetime.datetime.strptime(value_pb.string_value(),
                                        '%Y-%m-%d').date()
    return None
  if value_pb.type() == document_pb.FieldValue.NUMBER:
    if value_pb.has_string_value():
      return float(value_pb.string_value())
    return None
  raise TypeError('unknown FieldValue type %d' % value_pb.type())


def _NewFieldFromPb(pb):
  """Constructs a Field from a document_pb.Field protocol buffer."""
  name = pb.name()
  value = _GetValue(pb.value())
  lang = None
  if pb.value().has_language():
    lang = pb.value().language()
  val_type = pb.value().type()
  if val_type == document_pb.FieldValue.TEXT:
    return TextField(name, value, lang)
  elif val_type == document_pb.FieldValue.HTML:
    return HtmlField(name, value, lang)
  elif val_type == document_pb.FieldValue.ATOM:
    return AtomField(name, value, lang)
  elif val_type == document_pb.FieldValue.DATE:
    return DateField(name, value)
  elif val_type == document_pb.FieldValue.NUMBER:
    return NumberField(name, value)
  return Error(
      OperationResult(OperationResult.INVALID_REQUEST,
                      'Unknown field value type %d' % val_type))


class Document(object):
  """Represents a user generated document.

  The following example shows how to create a document consisting of a set
  of fields, some plain text and some in HTML.

  Document(doc_id='document id',
           fields=[TextField(name='subject', value='going for dinner'),
                   HtmlField(name='body',
                             value='<html>I found a place.</html>',
                   TextField(name='signature', value='brzydka pogoda',
                             language='pl')],
           language='en')
  """
  _FIRST_JAN_2011 = datetime.datetime(2011, 1, 1)

  def __init__(self, doc_id=None, fields=None, language='en', order_id=None):
    """Initializer.

    Args:
      doc_id: The printable ASCII string identifying the document which does
        not start with '!' which is reserved. Non-space whitespace characters
        are also excluded from ids. If no id is provided, the search service
        will provide one.
      fields: An iterable of Field instances representing the content of the
        document.
      language: The code of the language used in the field values. Defaults
      to 'en' (English).
      order_id: The id used to specify the order this document will be returned
        in search results, where 0 <= order_id <= sys.maxint. Defaults to the
        number of seconds since 1st Jan 2011. Documents are returned in
        descending order of the order ID.

    Raises:
      TypeError: If any of the parameters have invalid types, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have invalid values.
    """
    if doc_id is not None:
      _CheckDocumentId(doc_id)
    self._doc_id = doc_id
    self._fields = _GetList(fields)
    self._language = _CheckLanguage(language)

    if order_id is None:
      order_id = self._GetDefaultOrderId()
    self._order_id = self._CheckOrderId(order_id)

  @property
  def doc_id(self):
    """Returns the document identifier."""
    return self._doc_id

  @property
  def fields(self):
    """Returns a list of fields of the document."""
    return self._fields

  @property
  def language(self):
    """Returns the code of the language the document fields are written in."""
    return self._language

  @property
  def order_id(self):
    """Returns the id used to return documents in a defined order."""
    return self._order_id

  def _CheckOrderId(self, order_id):
    """Checks the order id is valid, then returns it."""
    return _CheckInteger(order_id, 'order_id', upper_bound=sys.maxint)

  def _GetDefaultOrderId(self):
    """Returns a default order id as total seconds since 1st Jan 2011."""
    td = datetime.datetime.now() - Document._FIRST_JAN_2011
    return td.seconds + (td.days * 24 * 3600)

  def __repr__(self):
    return _Repr(
        self, [('doc_id', self.doc_id), ('fields', self.fields),
               ('language', self.language), ('order_id', self.order_id)])

  def __eq__(self, other):
    return (isinstance(other, type(self)) and self.doc_id == other.doc_id and
            self.order_id == other.order_id and self.language == other.language
            and len(self.fields) == len(other.fields) and
            sorted(self.fields) == sorted(other.fields))

  def __ne__(self, other):
    return not self == other

  def __key(self):
    return self.doc_id

  def __hash__(self):
    return hash(self.__key())

  def __str__(self):
    return repr(self)


def _CopyDocumentToProtocolBuffer(document, pb):
  """Copies Document to a document_pb.Document protocol buffer."""
  pb.set_storage(document_pb.Document.DISK)
  if document.doc_id:
    pb.set_id(document.doc_id)
  if document.language:
    pb.set_language(document.language)
  for field in document.fields:
    field_pb = pb.add_field()
    _CopyFieldToProtocolBuffer(field, field_pb)
  pb.set_order_id(document.order_id)
  return pb


def _NewDocumentFromPb(doc_pb):
  """Constructs a Document from a document_pb.Document protocol buffer."""
  fields = [_NewFieldFromPb(f) for f in doc_pb.field_list()]
  lang = None
  if doc_pb.has_language():
    lang = doc_pb.language()
  return Document(doc_id=doc_pb.id(), fields=fields,
                  language=lang,
                  order_id=doc_pb.order_id())


def _QuoteString(argument):
  return '"' + argument.replace('"', '\"') + '"'


class FieldExpression(object):
  """Represents an expression that will be computed for each result returned.

  For example,
    FieldExpression(name='content-snippet',
                    expression='snippet("very important", content)')
  means a computed field 'content-snippet' will be returned with each search
  result, which contains HTML snippets of the 'content' field which match
  the query 'very important'.
  """

  _MAXIMUM_EXPRESSION_LENGTH = 1000
  _MAXIMUM_OPERATOR_LENGTH = 100

  def __init__(self, name, expression):
    """Initializer.

    Args:
      name: The name of the computed field for the expression.
      expression: The expression to evaluate and return in a field with
        given name in results.

    Raises:
      TypeError: If any of the parameters has an invalid type, or an unknown
        attribute is passed.
      ValueError: If any of the parameters has an invalid value.
    """
    self._name = _CheckFieldName(name)
    if expression is None:
      raise ValueError('expression in FieldExpression cannot be null')
    if not isinstance(expression, basestring):
      raise TypeError('expression expected in FieldExpression, but got %s' %
                      type(expression))
    self._expression = _CheckExpression(expression)

  @property
  def name(self):
    """Returns name of the expression to return in search results."""
    return self._name

  @property
  def expression(self):
    """Returns a string containing an expression returned in search results."""
    return self._expression

  def __repr__(self):
    return _Repr(
        self, [('name', self.name), ('expression', self.expression)])


def _CopyFieldExpressionToProtocolBuffer(field_expression, pb):
  """Copies FieldExpression to a search_service_pb.FieldSpec_Expression."""
  pb.set_name(field_expression.name)
  pb.set_expression(field_expression.expression)


class SortSpec(object):
  """Sorting specification for a single dimension.

  Multi-dimensional sorting is supported by a list of SortSpecs. For example,

    [SortSpec(expression='author', default_value=SortSpec.MAX_FIELD_VALUE),
     SortSpec(expression='subject', sort_descending=False,
              default_value=SortSpec.MIN_FIELD_VALUE)]

  will sort the result set by author in descending order and then subject in
  ascending order. Documents with no author will appear at the top of results.
  Documents with no subject will appear at the top of the author group.
  """


  CUSTOM, MATCH_SCORER, RESCORING_MATCH_SCORER = (
      'CUSTOM', 'MATCH_SCORER', 'RESCORING_MATCH_SCORER')

  _MAXIMUM_LIMIT = 10000

  _TYPES = frozenset([CUSTOM, MATCH_SCORER, RESCORING_MATCH_SCORER])


  try:
    MAX_FIELD_VALUE = unichr(0x10ffff) * 80
  except ValueError:

    MAX_FIELD_VALUE = unichr(0xffff) * 80

  MIN_FIELD_VALUE = ''

  def __init__(self, sort_type=CUSTOM, expression=None, sort_descending=True,
               default_value=None, limit=1000):
    """Initializer.

    Args:
      sort_type: The type of sorting to use on search results. Defaults to
        CUSTOM. The possible types include:
          CUSTOM: User must specify the scoring function in the expression
            field.
          MATCH_SCORER: Sort documents using a scorer that returns a score
            based on term frequency divided by document frequency.
          RESCORING_MATCH_SCORER: Sort documents using match scoring and
            rescoring.
      expression: An expression to be evaluated on each matching document
        to be used to sort by. The expression can simply be a field name,
        or some compound expression such as "score + count(likes) * 0.1"
        which will add the score from a scorer to a count of the values
        of a likes field times 0.1.
      sort_descending: Whether to sort in descending or ascending order.
      default_value: The default value of the expression, if no field
        present nor can be calculated for a document. A text value must
        be specified for text sorts. A numeric value must be specified for
        numeric sorts.
      limit: The limit on the number of documents to score. Defaults to 1000.
        Used if using a scorer, ignored otherwise.

    Raises:
      TypeError: If any of the parameters has an invalid type, or an unknown
        attribute is passed.
      ValueError: If any of the parameters has an invalid value.
    """
    self._sort_type = self._CheckType(sort_type)
    self._expression = expression
    self._sort_descending = sort_descending
    self._default_value = default_value
    if sort_type == SortSpec.CUSTOM:
      if expression is None:
        raise TypeError('expression required for CUSTOM sort_type')
      _CheckExpression(expression)
      if isinstance(self.default_value, basestring):
        _CheckText(self._default_value, 'default_value')
      elif self._default_value is not None:
        _CheckNumber(self._default_value, 'default_value')
    else:
      if expression is not None:
        raise TypeError('expression only allowed in CUSTOM sort_type')
      if default_value is not None:
        raise TypeError('default_value only allowed in CUSTOM sort_type')
    self._limit = self._CheckLimit(limit)

  @property
  def sort_type(self):
    """Returns the type of the scorer to use."""
    return self._sort_type

  @property
  def expression(self):
    """Returns the expression to sort by."""
    return self._expression

  @property
  def sort_descending(self):
    """Returns whether to sort the field in descending or ascending order."""
    return self._sort_descending

  @property
  def default_value(self):
    """Returns a default value used for sorting fields which have no value."""
    return self._default_value

  @property
  def limit(self):
    """Returns the limit on the number of documents to score."""
    return self._limit

  def _CheckType(self, sort_type):
    """Checks sort_type is a valid SortSpec type and returns it."""
    return _CheckEnum(sort_type, 'sort_type', values=self._TYPES)

  def _CheckLimit(self, limit):
    """Checks the limit on number of docs to score is not too large."""
    return _CheckInteger(limit, 'limit', upper_bound=self._MAXIMUM_LIMIT)

  def __repr__(self):
    return _Repr(
        self, [('sort_type', self.sort_type),
               ('expression', self.expression),
               ('sort_descending', self.sort_descending),
               ('default_value', self.default_value),
               ('limit', self.limit)])


def _CopySortSpecToProtocolBuffer(sort_spec, pb):
  """Copies this SortSpec to a search_service_pb.SortSpec protocol buffer."""
  pb.set_sort_expression(sort_spec.expression)
  pb.set_sort_descending(bool(sort_spec.sort_descending))
  if sort_spec.default_value is not None:
    if isinstance(sort_spec.default_value, basestring):
      pb.set_default_value_text(sort_spec.default_value)
    else:
      pb.set_default_value_numeric(sort_spec.default_value)
  return pb


_SORT_TYPE_PB_MAP = {
    SortSpec.RESCORING_MATCH_SCORER:
    search_service_pb.ScorerSpec.RESCORING_MATCH_SCORER,
    SortSpec.MATCH_SCORER: search_service_pb.ScorerSpec.MATCH_SCORER}


def _CopySortSpecToScorerSpecProtocolBuffer(sort_spec, pb):
  """Copies a SortSpec to a search_service_pb.ScorerSpec."""
  pb.set_scorer(_SORT_TYPE_PB_MAP.get(sort_spec.sort_type))
  pb.set_limit(sort_spec.limit)
  return pb


class SearchRequest(object):
  """A request to search an index for documents which match a query.

  For example, the following code fragment requests a search for
  documents where 'first' occurs in subject and 'good' occurs anywhere,
  returning at most 20 documents, starting the search from 'cursor token',
  returning another single cursor for the response, sorting by subject in
  descending order, returning the author, subject, and summary fields as well
  as a snippeted field content.

    SearchRequest(query='subject:first good',
                  limit=20,
                  cursor=cursor_from_previous_response,
                  cursor_type=SearchRequest.RESPONSE_CURSOR,
                  sort_specs=[SortSpec(expression='subject', default_value='')],
                  returned_fields=['author', 'subject', 'summary'],
                  snippeted_fields=['content'])

  The following code fragment shows how to use a response cursor

    response = index.search(
        SearchRequest(cursor=previous_cursor,
                      cursor_type=SearchRequest.RESPONSE_CURSOR))

    previous_cursor = response.cursor
    for result in response:
       # process result

  The following code fragment shows how to use a result cursor

    response = index.search(
        SearchRequest(cursor=previous_cursor,
                      cursor_type=SearchRequest.RESULT_CURSOR))

    for result in response:
       previous_cursor = result.cursor
  """


  RESPONSE_CURSOR, RESULT_CURSOR = ('RESPONSE_CURSOR', 'RESULT_CURSOR')

  _CURSOR_TYPES = frozenset([RESPONSE_CURSOR, RESULT_CURSOR])
  _MAXIMUM_QUERY_LENGTH = 1000
  _MAXIMUM_LIMIT = 800
  _MAXIMUM_MATCHED_COUNT_ACCURACY = 10000
  _MAXIMUM_FIELDS_TO_RETURN = 100

  def __init__(self, query, offset=0, limit=20, matched_count_accuracy=100,
               cursor=None, cursor_type=None, sort_specs=None,
               returned_fields=None, snippeted_fields=None,
               returned_expressions=None, **kwargs):
    """Initializer.

    Args:
      query: The query to match against documents in the index. A query is a
        boolean expression containing terms.  For example, the query
          'job tag:"very important" sent:[TO 2011-02-28]'
        finds documents with the term job in any field, that contain the
        phrase "very important" in a tag field, and a sent date up to and
        including 28th February, 2011.  You can use combinations of
          '(cat OR feline) food NOT dog'
        to find documents which contain the term cat or feline as well as food,
        but do not mention the term dog. A further example,
          'category:televisions brand:sony price:[300 TO 400}'
        will return documents which have televisions in a category field, a
        sony brand and a price field which is 300 (inclusive) to 400
        (exclusive).
      offset: The offset is number of documents to skip in results.
      limit: The limit on number of documents to return in results.
      matched_count_accuracy: The minimum accuracy requirement for
        SearchResponse.matched_count. If set, the matched_count will be
        accurate up to at least that number. For example, when set to 100,
        any SearchResponse with matched_count <= 100 is accurate. This option
        may add considerable latency/expense, especially when used with
        returned_fields.
      cursor: A cursor returned in a previous set of search results to use
        as a starting point to retrieve the next set of results. This can get
        you better performance, and also improves the consistency of pagination
        through index updates.
      cursor_type: The type of cursor returned results will have, if any.
        Possible types are:
          RESPONSE_CURSOR: A single cursor will be returned in the response
          to continue from the end of the results.
          RESULT_CURSOR: One cursor will be returned with each search
          result, so you can continue after any result.
      sort_specs: An iterable of SortSpecs specifying a multi-dimensional sort
        over the search results.
      returned_fields: An iterable of names of fields to return in search
        results.
      snippeted_fields: An iterable of names of fields to snippet and return
        in search result expressions.
      returned_expressions: An iterable of FieldExpression to evaluate and
        return in search results.

    Raises:
      TypeError: If any of the parameters have invalid types, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have invalid values.
    """



    if 'app_id' in kwargs:
      self._app_id = kwargs.pop('app_id')
    else:
      self._app_id = None

    if kwargs:
      raise TypeError('Invalid arguments: %s' % ', '.join(kwargs))

    self._query = self._CheckQuery(query)
    self._offset = self._CheckOffset(offset)
    self._limit = self._CheckLimit(limit)
    self._matched_count_accuracy = self._CheckMatchedCountAccuracy(
        matched_count_accuracy)

    self._cursor = self._CheckCursor(cursor)
    self._cursor_type = self._CheckCursorType(cursor_type)

    self._sort_specs = _GetList(sort_specs)

    self._returned_fields = _CheckFieldNames(_ConvertToList(returned_fields))
    self._snippeted_fields = _CheckFieldNames(_ConvertToList(snippeted_fields))
    self._returned_expressions = _ConvertToList(returned_expressions)

    if (len(self._returned_expressions) + len(self._snippeted_fields) +
        len(self._returned_fields)) > self._MAXIMUM_FIELDS_TO_RETURN:
      raise ValueError(
          'too many fields, snippets or expressions to return  %d > maximum %d'
          % (len(self._returned_expressions), self._MAXIMUM_FIELDS_TO_RETURN))

  @property
  def query(self):
    """Returns the query to match against documents in an index."""
    return self._query

  @property
  def offset(self):
    """Returns the offset in the document list to return in search results."""
    return self._offset

  @property
  def limit(self):
    """Returns the limit on number of documents to return in search results."""
    return self._limit

  @property
  def matched_count_accuracy(self):
    """Returns the accuracy for SearchResponse.matched_count."""
    return self._matched_count_accuracy

  @property
  def cursor(self):
    """Returns a cursor from a previous set of search results.

    The search will be continued from this cursor.
    """
    return self._cursor

  @property
  def cursor_type(self):
    """Returns the type of cursor to return.

    This can be NONE, a single RESPONSE_CURSOR, or a RESULT_CURSOR with each
    result.
    """
    return self._cursor_type

  @property
  def sort_specs(self):
    """Returns a list of SortSpecs specifying a multi-dimensional sort."""
    return self._sort_specs

  @property
  def returned_fields(self):
    """Returns a list of names of fields to return in search results."""
    return self._returned_fields

  @property
  def snippeted_fields(self):
    """Returns a list of names of fields to snippet in search results."""
    return self._snippeted_fields

  @property
  def returned_expressions(self):
    """Returns a list of FieldExpression to evaluate and return in results."""
    return self._returned_expressions

  def _CheckQuery(self, query):
    """Checks a query is a valid query string."""
    _ValidateString(query, 'query', SearchRequest._MAXIMUM_QUERY_LENGTH,
                    empty_ok=True)
    if query is None:
      raise ValueError('query must not be null')
    if query.strip():
      if isinstance(query, unicode):
        query_parser.Parse(query)
      else:
        query_parser.Parse(unicode(query, 'utf-8'))
    return query

  def _CheckLimit(self, limit):
    """Checks the limt of documents to return is an integer within range."""
    return _CheckInteger(
        limit, 'limit', zero_ok=False, upper_bound=self._MAXIMUM_LIMIT)

  def _CheckOffset(self, offset):
    """Checks the offset in document list is an integer within range."""
    return _CheckInteger(
        offset, 'offset', zero_ok=True, upper_bound=self._MAXIMUM_LIMIT)

  def _CheckMatchedCountAccuracy(self, matched_count_accuracy):
    """Checks the accuracy is an integer within range."""
    return _CheckInteger(
        matched_count_accuracy, 'matched_count_accuracy',
        zero_ok=False, upper_bound=self._MAXIMUM_MATCHED_COUNT_ACCURACY)

  def _CheckCursor(self, cursor):
    """Checks the cursor if specified is a string which is not too long."""
    return _ValidateString(cursor, 'cursor', _MAXIMUM_CURSOR_LENGTH,
                           empty_ok=True)

  def _CheckCursorType(self, cursor_type):
    """Checks the cursor_type is one specified in _CURSOR_TYPES or None."""
    if cursor_type is None:
      return None
    return _CheckEnum(cursor_type, 'cursor_type',
                      values=SearchRequest._CURSOR_TYPES)

  def __repr__(self):
    return _Repr(self, [('query', self.query),
                        ('offset', self.offset),
                        ('limit', self.limit),
                        ('matched_count_accuracy', self.matched_count_accuracy),
                        ('cursor', self.cursor),
                        ('cursor_type', self.cursor_type),
                        ('sort_specs', self.sort_specs),
                        ('returned_fields', self.returned_fields),
                        ('snippeted_fields', self.snippeted_fields),
                        ('returned_expressions', self.returned_expressions)])


_CURSOR_TYPE_PB_MAP = {
  None: search_service_pb.SearchParams.NONE,
  SearchRequest.RESPONSE_CURSOR: search_service_pb.SearchParams.SINGLE,
  SearchRequest.RESULT_CURSOR: search_service_pb.SearchParams.PER_RESULT
  }


def _CopySearchRequestToProtocolBuffer(request, pb):
  """Copies SearchRequest to search_service_pb.SearchParams proto buffer."""
  if isinstance(request.query, unicode):
    pb.set_query(request.query.encode('utf-8'))
  else:
    pb.set_query(request.query)
  if request.cursor:
    pb.set_cursor(request.cursor)
  pb.set_cursor_type(_CURSOR_TYPE_PB_MAP.get(request.cursor_type))
  if request.offset:
    pb.set_offset(request.offset)
  pb.set_limit(request.limit)
  pb.set_matched_count_accuracy(request.matched_count_accuracy)
  if (request.returned_fields or request.snippeted_fields
      or request.returned_expressions):
    field_spec_pb = pb.mutable_field_spec()
    for field in request.returned_fields:
      field_spec_pb.add_name(field)
    for snippeted_field in request.snippeted_fields:
      _CopyFieldExpressionToProtocolBuffer(
          FieldExpression(
              name=snippeted_field,
              expression='snippet(' + _QuoteString(request.query)
              + ', ' + snippeted_field + ')'),
          field_spec_pb.add_expression())
    for expression in request.returned_expressions:
      _CopyFieldExpressionToProtocolBuffer(
          expression, field_spec_pb.add_expression())
  if request.sort_specs:
    for sort_spec in request.sort_specs:
      if sort_spec.sort_type == SortSpec.CUSTOM:
        sort_spec_pb = pb.add_sort_spec()
        _CopySortSpecToProtocolBuffer(sort_spec, sort_spec_pb)
      else:
        _CopySortSpecToScorerSpecProtocolBuffer(
            sort_spec, pb.mutable_scorer_spec())
  return pb


class SearchResult(object):
  """Represents a result of executing a search request."""


  def __init__(self, document, sort_scores=None, expressions=None, cursor=None):
    """Initializer.

    Args:
      document: The document returned as a query result. Only fields
        specified in a SearchRequest will be returned in the document.
      sort_scores: The list of scores assigned during sort evaluation. Each
        sort dimension is included. Positive scores are used for ascending
        sorts; negative scores for descending.
      expressions: The list of computed fields which are the result of
        expressions requested.
      cursor: A cursor associated with the document.

    Raises:
      TypeError: If any of the parameters have invalid types, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have invalid values.
    """
    self._document = document
    self._sort_scores = self._CheckSortScores(_GetList(sort_scores))
    self._expressions = _GetList(expressions)
    self._cursor = self._CheckCursor(cursor)

  @property
  def document(self):
    """A document which matches the query."""
    return self._document

  @property
  def sort_scores(self):
    """The list of scores assigned during sort evaluation.

    Each sort dimension is included. Positive scores are used for ascending
    sorts; negative scores for descending.

    Returns:
      The list of numeric sort scores.
    """
    return self._sort_scores

  @property
  def expressions(self):
    """The list of computed fields the result of expression evaluation.

    For example, if a request has
      FieldExpression(name='snippet', 'snippet("good story", content)')
    meaning to compute a snippet field containing HTML snippets extracted
    from the matching of the query 'good story' on the field 'content'.
    This means a field such as the following will be returned in expressions
    for the search result:
      HtmlField(name='snippet', value='that was a <b>good story</b> to finish')

    Returns:
      The computed fields.
    """
    return self._expressions

  @property
  def cursor(self):
    """A cursor associated with a result, a continued search starting point.

    To get this cursor to appear, set the SearchRequest.cursor_type to
    SearchRequest.RESULT_CURSOR, otherwise this will be None.

    Returns:
      The result cursor.
    """
    return self._cursor

  def _CheckSortScores(self, sort_scores):
    """Checks sort_scores is a list of floats, and returns it."""
    for sort_score in sort_scores:
      _CheckNumber(sort_score, 'sort_scores')
    return sort_scores

  def _CheckCursor(self, cursor):
    """Checks cursor is a string which is not too long, and returns it."""
    return _ValidateString(cursor, 'cursor', _MAXIMUM_CURSOR_LENGTH,
                           empty_ok=True)

  def __repr__(self):
    return _Repr(self, [('document', self.document),
                        ('sort_scores', self.sort_scores),
                        ('expressions', self.expressions),
                        ('cursor', self.cursor)])


class IndexDocumentResponse(object):
  """Represents the result of executing a index document request.

  For example, the following code shows how a response could be used
  to determine which documents were successfully indexed or not. The
  ids and statuses are in the order documents were supplied.

  response = index.index_documents(documents)
  for (result, doc_id) in zip(response.results, response.document_ids):
    if result.code == OK:
      print "doc with ID", doc_id, "indexed successfully"
    else:
     print "Failed to index doc with ID", doc_id
  """

  def __init__(self, results=None, document_ids=None):
    """Initializer.

    Args:
      results: The list of OperationResult returned from executing
        a index document request.
      document_ids: The document ids of the documents indexed in the order
        of the request. These ids could have been assigned by the service
        if no document id was provided for a document in the request.

    Raises:
      TypeError: If any of the parameters have an invalid type, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have an invalid value.
    """
    self._results = _GetList(results)
    self._document_ids = _GetList(document_ids)

  def __iter__(self):
    for result in self.results:
      yield result

  @property
  def results(self):
    """Returns list of OperationResult for indexing each document."""
    return self._results

  @property
  def document_ids(self):
    """Returns a list of document IDs of documents indexed."""
    return self._document_ids

  def __repr__(self):
    return _Repr(self, [('results', self.results),
                        ('document_ids', self.document_ids)])


class DeleteDocumentResponse(object):
  """Represents the result of executing a delete document request.

  For example, the following code shows how a response could be used
  to determine which documents were successfully deleted or not.

  response = index.delete_documents(document_ids)
  for (result, doc_id) in zip(response.results, document_ids):
    if result.code == OK:
      print "doc with ID", doc_id, "successfully deleted"
    else:
     print "Failed to delete doc with ID", doc_id
  """

  def __init__(self, results=None):
    """Initializer.

    Args:
      results: The list of OperationResult returned from executing
        a delete document request.

    Raises:
      TypeError: If any of the parameters have an invalid type, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have an invalid value.
    """
    self._results = _GetList(results)

  def __iter__(self):
    for result in self.results:
      yield result

  @property
  def results(self):
    """Returns list of OperationResult for deleting each document."""
    return list(self._results)

  def __repr__(self):
    return _Repr(self, [('results', self.results)])


class SearchResponse(object):
  """Represents the result of executing a search request."""

  def __init__(self, matched_count, results=None, operation_result=None,
               cursor=None):
    """Initializer.

    Args:
      operation_result: The OperationResult of the search including error code
      and message if any.
      results: The list of SearchResult returned from executing a search
        request.
      matched_count: The number of documents matched by the query.
      cursor: A cursor to continue the search from the end of the
        search results.

    Raises:
      TypeError: If any of the parameters have an invalid type, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have an invalid value.
    """
    self._operation_result = operation_result
    self._matched_count = _CheckInteger(matched_count, 'matched_count')
    self._results = _GetList(results)
    self._cursor = cursor

  def __iter__(self):

    for result in self.results:
      yield result

  @property
  def operation_result(self):
    """Returns the OperationResult of the search."""
    return self._operation_result

  @property
  def results(self):
    """Returns the list of SearchResult that matched the query."""
    return self._results

  @property
  def matched_count(self):
    """Returns the count of documents which matched the query.

    Note that this is an approximation and not an exact count.
    If SearchRequest.matched_count_accuracy is set to 100 for example,
    then matched_count <= 100 is accurate.

    Returns:
      The number of documents matched.
    """
    return self._matched_count


  @property
  def returned_count(self):
    """Returns the count of documents returned in results."""
    return len(self._results)

  @property
  def cursor(self):
    """Returns a cursor that can be used to continue search from last result.

    This corresponds to setting SearchRequest.cursor_type to
    SearchRequest.RESPONSE_CURSOR, otherwise this will be None.

    Returns:
      The response cursor.
    """
    return self._cursor

  def __repr__(self):
    return _Repr(self, [('operation_result', self.operation_result),
                        ('results', self.results),
                        ('matched_count', self.matched_count),
                        ('cursor', self.cursor)])


class ListDocumentsResponse(object):
  """Represents the result of executing a list documents request.

  For example, the following code shows how a response could be used
  to determine which documents were successfully deleted or not.

  response = index.list_documents()
  for document in response:
    print "document ", document
  """

  def __init__(self, documents=None):
    """Initializer.

    Args:
      documents: The documents returned from an index ordered by Id.

    Raises:
      TypeError: If any of the parameters have an invalid type, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have an invalid value.
    """
    self._documents = _GetList(documents)

  def __iter__(self):
    for document in self.documents:
      yield document

  @property
  def documents(self):
    """Returns a list of documents ordered by Id from the index."""
    return self._documents

  def __repr__(self):
    return _Repr(self, [('documents', self.documents)])


class ListIndexesResponse(object):
  """Represents the result of executing a list indexes request.

  For example, the following code shows how the response can be
  used to get IndexSpec objects listed.

  response = search.list_indexes()
  for index in response:
    print "index ", index.name
  """

  def __init__(self, indexes=None):
    """Initializer.

    Args:
      indexes: A list of IndexSpec of available indexes.

    Raises:
      TypeError: If any of the parameters have an invalid type, or an unknown
        attribute is passed.
      ValueError: If any of the parameters have an invalid value.
    """
    self._indexes = _GetList(indexes)

  def __iter__(self):
    for index in self.indexes:
      yield index

  @property
  def indexes(self):
    """Returns a list of IndexSpec of available indexes."""
    return self._indexes

  def __repr__(self):
    return _Repr(self, [('indexes', self.indexes)])


class OperationResult(object):
  """Represents the result of an index/search operation."""

  OK, INVALID_REQUEST, TRANSIENT_ERROR, INTERNAL_ERROR = (
      'OK', 'INVALID_REQUEST', 'TRANSIENT_ERROR', 'INTERNAL_ERROR')

  _CODES = frozenset([OK, INVALID_REQUEST, TRANSIENT_ERROR, INTERNAL_ERROR])

  def __init__(self, code, message=None):
    """Initializer.

    Args:
      code: The error or success code of the operation.
      message: An error message associated with any error.

    Raises:
      TypeError: If an unknown attribute is passed.
      ValueError: If an unknown code is passed.
    """
    self._code = code
    if self._code not in self._CODES:
      raise ValueError('Unknown operation result code %r, must be one of %s'
                       % (self._code, self._CODES))
    self._message = message
    if self._message is not None and not isinstance(self._message, basestring):
      raise TypeError('message must be a string: %r' % self._message)

  @property
  def code(self):
    """Returns the code of the operation result."""
    return self._code

  @property
  def message(self):
    """Returns any associated error message if the operation was in error."""
    return self._message

  def __repr__(self):
    return _Repr(self, [('code', self.code), ('message', self.message)])


_ERROR_OPERATION_CODE_MAP = {
    search_service_pb.SearchServiceError.OK: OperationResult.OK,
    search_service_pb.SearchServiceError.INVALID_REQUEST:
    OperationResult.INVALID_REQUEST,
    search_service_pb.SearchServiceError.TRANSIENT_ERROR:
    OperationResult.TRANSIENT_ERROR,
    search_service_pb.SearchServiceError.INTERNAL_ERROR:
    OperationResult.INTERNAL_ERROR
    }


def _NewOperationResultFromPb(status_pb):
  """Constructs an OperationResult from a search_service.RequestStatus pb."""
  message = None
  if status_pb.has_error_detail():
    message = status_pb.error_detail()
  return _NewOperationResult(status_pb.code(), message)


def _NewOperationResult(code, message):
  """Constructs an OperationResult from a search_service.SearchServiceError."""
  return OperationResult(code=_ERROR_OPERATION_CODE_MAP[code],
                         message=message)


def _NewOperationResultListFromPb(status_pb_list):
  """Returns a list of OperationResult from a list of RequestStatus pb."""
  return [_NewOperationResultFromPb(status) for status in status_pb_list]


def _CheckResponseList(response_list):
  """Raises an Error if some operation result is not OK."""
  for operation_result in response_list:
    if operation_result.code != OperationResult.OK:
      raise Error(operation_result, response_list)
  return response_list


class Index(object):
  """Represents an index allowing indexing, deleting and searching documents.

  The following code fragment shows how to index documents, then search the
  index for documents matching a query.

    # Get the index.
    index = Index(name='index-name',
                  consistency=Index.PER_DOCUMENT_CONSISTENT)

    # Create a document.
    doc = Document(doc_id='document-id',
                   fields=[TextField(name='subject', value='my first email'),
                           HtmlField(name='body',
                                     value='<html>some content here</html>')])

    # Index the document.
    try:
      index.index_documents(doc)
    except search.Error, e:
      if e.operation_result.code == OperationResult.TRANSIENT_ERROR:
        # possibly retry

    # Query the index.
    try:
      response = index.search('subject:first body:here')

      # Iterate through the search results.
      for result in response:
         doc = result.document

    except search.Error, e:
      if e.operation_result.code == OperationResult.TRANSIENT_ERROR:
        # possibly retry
        for result in e.response:
           doc = result.document

  Once an index is created with a given specification, that specification is
  immutable. That is, the consistency mode cannot be changed, once the index is
  created.

  Consistency modes supported by indexes. When creating an index you
  may request whether the index is GLOBALLY_CONSISTENT or
  PER_DOCUMENT_CONSISTENT. An index with GLOBALLY_CONSISTENT mode set, when
  searched, returns results with all cahnges prior to the search request,
  committted. For an index with PER_DOCUMENT_CONSISTENT mode set, a search
  result may contain some out of date documents. However, any two changes
  to any document stored in such an index are applied in the correct order.
  The benefit of PER_DOCUMENT_CONSISTENT is that it provides much higher
  index document throughput than a globally consistent one.

  Typically, you would use GLOBALLY_CONSISTENT if organizing personal user
  information, to reflect all changes known to the user in any search results.
  PER_DOCUMENT_CONSISTENT should be used in indexes that amalgamate
  information from multiple sources, where no single user is aware of all
  collected data.
  """

  GLOBALLY_CONSISTENT, PER_DOCUMENT_CONSISTENT = ('GLOBALLY_CONSISTENT',
                                                  'PER_DOCUMENT_CONSISTENT')

  _CONSISTENCY_MODES = [GLOBALLY_CONSISTENT, PER_DOCUMENT_CONSISTENT]

  def __init__(self, name, namespace=None,
               consistency=PER_DOCUMENT_CONSISTENT):
    """Initializer.

    Args:
      name: The name of the index. An index name must be a printable ASCII
        string not starting with '!', but not containing any non-space
        whitespace characters.
      namespace: The namespace of the index name.
      consistency: The consistency mode of the index, either GLOBALLY_CONSISTENT
        or PER_DOCUMENT_CONSISTENT. Defaults to PER_DOCUMENT_CONSISTENT.

    Raises:
      TypeError: If an unknown attribute is passed.
      ValueError: If an unknown consistency mode, or invalid namespace is given.
    """
    self._name = _CheckIndexName(name)
    self._namespace = namespace
    if self._namespace is None:
      self._namespace = namespace_manager.get_namespace()
    if self._namespace is None:
      self._namespace = ''
    namespace_manager.validate_namespace(self._namespace, exception=ValueError)
    self._consistency = consistency
    if self._consistency not in self._CONSISTENCY_MODES:
      raise ValueError('consistency must be one of %s' %
                       self._CONSISTENCY_MODES)

  @property
  def name(self):
    """Returns the name of the index."""
    return self._name

  @property
  def namespace(self):
    """Returns the namespace of the name of the index."""
    return self._namespace

  @property
  def consistency(self):
    """Returns the consistency mode of the index."""
    return self._consistency

  def __eq__(self, other):
    return (isinstance(other, self.__class__)
            and self.__dict__ == other.__dict__)

  def __ne__(self, other):
    return not self.__eq__(other)

  def __hash__(self):
    return hash(self._name) ^ hash(self._consistency)

  def __repr__(self):
    return _Repr(self, [('name', self.name), ('namespace', self.namespace),
                        ('consistency', self.consistency)])

  def _NewIndexDocumentResponse(self, response):
    return IndexDocumentResponse(
        results=_NewOperationResultListFromPb(response.status_list()),
        document_ids=response.doc_id_list())

  def _CheckIndexResponse(self, response):
    _CheckResponseList(response.results)
    return response

  def index_documents(self, documents):
    """Index the collection of documents.

    If any of the documents are already in the index, then reindex them with
    their corresponding fresh document. If any of the documents fail to be
    indexed, then none of the documents will be indexed.

    Args:
      documents: A Document or iterable of Documents to index.

    Raises:
      TypeError: If an unknown attribute is passed.
      ValueError: If documents is not an iterable of Document.
      InternalError: If the number of document index operations acknowledge
        was not the same as requested.

    Returns:
      IndexDocumentResponse
    """

    if isinstance(documents, basestring):
      raise TypeError('documents must be a Document or sequence of '
                      'Documents, %s found'
                      % datastore_types.typename(documents))
    try:
      docs = list(iter(documents))
    except TypeError:
      docs = [documents]

    if not docs:
      return []

    request = search_service_pb.IndexDocumentRequest()
    response = search_service_pb.IndexDocumentResponse()

    params = request.mutable_params()
    _CopyMetadataToProtocolBuffer(self, params.mutable_index_spec())
    for document in docs:
      doc_pb = params.add_document()
      _CopyDocumentToProtocolBuffer(document, doc_pb)

    try:
      apiproxy_stub_map.MakeSyncCall('search', 'IndexDocument', request,
                                     response)
    except apiproxy_errors.ApplicationError, e:
      raise _ToSearchError(e, self._NewIndexDocumentResponse(response))

    index_response = self._NewIndexDocumentResponse(response)

    if response.status_size() != len(docs):
      _RaiseInternalError('did not index requested number of documents',
                          index_response)

    return self._CheckIndexResponse(index_response)

  def _NewDeleteDocumentResponse(self, response):
    return DeleteDocumentResponse(
        results=_NewOperationResultListFromPb(response.status_list()))

  def _CheckDeleteResponse(self, response):
    _CheckResponseList(response.results)
    return response

  def delete_documents(self, document_ids):
    """Delete the documents with the corresponding document ids from the index.

    If no document exists for the identifier in the list, then that document
    identifier is ignored. If any document delete fails, then no documents
    will be deleted.

    Args:
      document_ids: A single identifier or list of identifiers of documents
        to delete.

    Raises:
      ValueError: If document_ids is not a string or iterable of valid document
        identifiers.
      InternalError: If the number of document delete operations acknowledge
        was not the same as requested.

    Returns:
      DeleteDocumentResponse.
    """
    if isinstance(document_ids, basestring):
      doc_ids = [document_ids]
    else:
      try:
        doc_ids = list(iter(document_ids))
      except TypeError:
        doc_ids = [document_ids]

    if not doc_ids:
      return []
    request = search_service_pb.DeleteDocumentRequest()
    response = search_service_pb.DeleteDocumentResponse()
    params = request.mutable_params()
    _CopyMetadataToProtocolBuffer(self, params.mutable_index_spec())
    for document_id in doc_ids:
      _CheckDocumentId(document_id)
      params.add_doc_id(document_id)

    try:
      apiproxy_stub_map.MakeSyncCall('search', 'DeleteDocument', request,
                                     response)
    except apiproxy_errors.ApplicationError, e:
      raise _ToSearchError(e, self._NewDeleteDocumentResponse(response))

    delete_response = self._NewDeleteDocumentResponse(response)

    if response.status_size() != len(doc_ids):
      _RaiseInternalError('did not delete requested number of documents',
                          delete_response)

    return _CheckResponseList(delete_response)

  def _NewSearchResponse(self, response):
    """Returns a SearchResponse populated from a search_service response pb."""
    results = []
    for result_pb in response.result_list():
      cursor = None
      if result_pb.has_cursor():
        cursor = result_pb.cursor()
      results.append(
          SearchResult(
              document=_NewDocumentFromPb(result_pb.document()),
              sort_scores=result_pb.score_list(),
              expressions=[_NewFieldFromPb(f) for f in
                           result_pb.expression_list()],
              cursor=cursor))
    response_cursor = None
    if response.has_cursor():
      response_cursor = response.cursor()
    return SearchResponse(
        operation_result=_NewOperationResultFromPb(response.status()),
        results=results, matched_count=response.matched_count(),
        cursor=response_cursor)

  def search(self, search_request):
    """Search the index for documents matching the query in the search_request.

    Args:
      search_request: A query string or a SearchRequest containing a query and
        other parameters to score and sort the documents.

    Returns:
      A SearchResponse containing a list of documents matched, number returned
      and number matched by the query in the search_request.

    Raises:
      ValueError: If search_request is not a valid SearchRequest.

    Returns:
      A SearchResponse containing results, counts and OperationResult.
    """
    if isinstance(search_request, basestring):
      search_request = SearchRequest(query=search_request)
    request = search_service_pb.SearchRequest()
    if search_request._app_id:
      request.set_app_id(search_request._app_id)
    params = request.mutable_params()
    _CopyMetadataToProtocolBuffer(self, params.mutable_index_spec())
    _CopySearchRequestToProtocolBuffer(search_request, params)
    response = search_service_pb.SearchResponse()

    try:
      apiproxy_stub_map.MakeSyncCall('search', 'Search', request, response)
    except apiproxy_errors.ApplicationError, e:
      raise _ToSearchError(e, self._NewSearchResponse(response))

    return _CheckStatus(response.status(), self._NewSearchResponse(response))

  def _NewListDocumentsResponse(self, response):
    """Returns a ListDocumentsResponse from the list_documents response pb."""
    documents = []
    for doc_proto in response.document_list():
      documents.append(_NewDocumentFromPb(doc_proto))

    return ListDocumentsResponse(documents=documents)

  def list_documents(self, start_doc_id=None, include_start_doc=True,
                     limit=100, keys_only=False, **kwargs):
    """List documents in the index, in doc_id order.

    Args:
      start_doc_id: String containing the document Id from which to list
        documents from. By default, starts at the first document Id.
      include_start_doc: If true, include the document with the Id specified by
        the start_doc_id parameter.
      limit: The maximum number of documents to return. Defaults to 100.
      keys_only: If true, the documents returned only contain their keys.

    Returns:
      A ListDocumentsResponse containing a list of Documents, ordered by Id.

    Raises:
      Error: Some error occurred processing the request.
      TypeError: An unknown attribute is passed in.
    """
    request = search_service_pb.ListDocumentsRequest()
    if 'app_id' in kwargs:
      request.set_app_id(kwargs.pop('app_id'))

    if kwargs:
      raise TypeError('Invalid arguments: %s' % ', '.join(kwargs))

    params = request.mutable_params()
    _CopyMetadataToProtocolBuffer(self, params.mutable_index_spec())

    if start_doc_id:
      params.set_start_doc_id(start_doc_id)
    params.set_include_start_doc(include_start_doc)

    params.set_limit(limit)
    params.set_keys_only(keys_only)

    response = search_service_pb.ListDocumentsResponse()
    try:
      apiproxy_stub_map.MakeSyncCall('search', 'ListDocuments', request,
                                     response)
    except apiproxy_errors.ApplicationError, e:
      raise _ToSearchError(e, self._NewListDocumentsResponse(response))

    return _CheckStatus(response.status(),
                        self._NewListDocumentsResponse(response))




_CONSISTENCY_MODES_TO_PB_MAP = {
    Index.GLOBALLY_CONSISTENT: search_service_pb.IndexSpec.GLOBAL,
    Index.PER_DOCUMENT_CONSISTENT: search_service_pb.IndexSpec.PER_DOCUMENT}



_CONSISTENCY_PB_TO_MODES_MAP = {
    search_service_pb.IndexSpec.GLOBAL: Index.GLOBALLY_CONSISTENT,
    search_service_pb.IndexSpec.PER_DOCUMENT: Index.PER_DOCUMENT_CONSISTENT}


def _CopyMetadataToProtocolBuffer(index, spec_pb):
  """Copies Index specification to a search_service_pb.IndexSpec."""
  spec_pb.set_name(index.name)
  spec_pb.set_namespace(index.namespace)
  spec_pb.set_consistency(_CONSISTENCY_MODES_TO_PB_MAP.get(index.consistency))


def _NewIndexFromPb(spec_pb):
  """Creates an Index from a search_service_pb.IndexSpec."""
  consistency = _CONSISTENCY_PB_TO_MODES_MAP.get(spec_pb.consistency())
  if spec_pb.has_namespace():
    return Index(name=spec_pb.index_name(), namespace=spec_pb.namespace(),
                 consistency=consistency)
  else:
    return Index(name=spec_pb.name(), consistency=consistency)
