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

"""
In-memory persistent stub for the Python datastore API. Gets, queries,
and searches are implemented as in-memory scans over all entities.

Stores entities across sessions as pickled proto bufs in a single file. On
startup, all entities are read from the file and loaded into memory. On
every Put(), the file is wiped and all entities are written from scratch.
Clients can also manually Read() and Write() the file themselves.

Transactions are serialized through __tx_lock. Each transaction acquires it
when it begins and releases it when it commits or rolls back. This is
important, since there are other member variables like __tx_snapshot that are
per-transaction, so they should only be used by one tx at a time.
"""






import datetime
import logging
import os
import struct
import sys
import tempfile
import threading
import warnings

import cPickle as pickle

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api import datastore
from google.appengine.api import datastore_admin
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api import users
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.runtime import apiproxy_errors
from google.net.proto import ProtocolBuffer
from google.appengine.datastore import entity_pb

warnings.filterwarnings('ignore', 'tempnam is a potential security risk')


entity_pb.Reference.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Query.__hash__ = lambda self: hash(self.Encode())


_MAXIMUM_RESULTS = 1000


_MAX_QUERY_OFFSET = 1000


_MAX_QUERY_COMPONENTS = 100


class _StoredEntity(object):
  """Simple wrapper around an entity stored by the stub.

  Public properties:
    protobuf: Native protobuf Python object, entity_pb.EntityProto.
    encoded_protobuf: Encoded binary representation of above protobuf.
    native: datastore.Entity instance.
  """

  def __init__(self, entity):
    """Create a _StoredEntity object and store an entity.

    Args:
      entity: entity_pb.EntityProto to store.
    """
    self.protobuf = entity

    self.encoded_protobuf = entity.Encode()

    self.native = datastore.Entity._FromPb(entity)


class DatastoreFileStub(apiproxy_stub.APIProxyStub):
  """ Persistent stub for the Python datastore API.

  Stores all entities in memory, and persists them to a file as pickled
  protocol buffers. A DatastoreFileStub instance handles a single app's data
  and is backed by files on disk.
  """

  _PROPERTY_TYPE_TAGS = {
    datastore_types.Blob: entity_pb.PropertyValue.kstringValue,
    bool: entity_pb.PropertyValue.kbooleanValue,
    datastore_types.Category: entity_pb.PropertyValue.kstringValue,
    datetime.datetime: entity_pb.PropertyValue.kint64Value,
    datastore_types.Email: entity_pb.PropertyValue.kstringValue,
    float: entity_pb.PropertyValue.kdoubleValue,
    datastore_types.GeoPt: entity_pb.PropertyValue.kPointValueGroup,
    datastore_types.IM: entity_pb.PropertyValue.kstringValue,
    int: entity_pb.PropertyValue.kint64Value,
    datastore_types.Key: entity_pb.PropertyValue.kReferenceValueGroup,
    datastore_types.Link: entity_pb.PropertyValue.kstringValue,
    long: entity_pb.PropertyValue.kint64Value,
    datastore_types.PhoneNumber: entity_pb.PropertyValue.kstringValue,
    datastore_types.PostalAddress: entity_pb.PropertyValue.kstringValue,
    datastore_types.Rating: entity_pb.PropertyValue.kint64Value,
    str: entity_pb.PropertyValue.kstringValue,
    datastore_types.Text: entity_pb.PropertyValue.kstringValue,
    type(None): 0,
    unicode: entity_pb.PropertyValue.kstringValue,
    users.User: entity_pb.PropertyValue.kUserValueGroup,
    }

  WRITE_ONLY = entity_pb.CompositeIndex.WRITE_ONLY
  READ_WRITE = entity_pb.CompositeIndex.READ_WRITE
  DELETED = entity_pb.CompositeIndex.DELETED
  ERROR = entity_pb.CompositeIndex.ERROR

  _INDEX_STATE_TRANSITIONS = {
    WRITE_ONLY: frozenset((READ_WRITE, DELETED, ERROR)),
    READ_WRITE: frozenset((DELETED,)),
    ERROR: frozenset((DELETED,)),
    DELETED: frozenset((ERROR,)),
  }

  def __init__(self,
               app_id,
               datastore_file,
               history_file,
               require_indexes=False,
               service_name='datastore_v3'):
    """Constructor.

    Initializes and loads the datastore from the backing files, if they exist.

    Args:
      app_id: string
      datastore_file: string, stores all entities across sessions.  Use None
          not to use a file.
      history_file: string, stores query history.  Use None as with
          datastore_file.
      require_indexes: bool, default False.  If True, composite indexes must
          exist in index.yaml for queries that need them.
      service_name: Service name expected for all calls.
    """
    super(DatastoreFileStub, self).__init__(service_name)


    assert isinstance(app_id, basestring) and app_id != ''
    self.__app_id = app_id
    self.__datastore_file = datastore_file
    self.__history_file = history_file

    self.__entities = {}

    self.__schema_cache = {}

    self.__tx_snapshot = {}

    self.__queries = {}

    self.__transactions = {}

    self.__indexes = {}
    self.__require_indexes = require_indexes

    self.__query_history = {}

    self.__next_id = 1
    self.__next_cursor = 1
    self.__next_tx_handle = 1
    self.__next_index_id = 1
    self.__id_lock = threading.Lock()
    self.__cursor_lock = threading.Lock()
    self.__tx_handle_lock = threading.Lock()
    self.__index_id_lock = threading.Lock()
    self.__tx_lock = threading.Lock()
    self.__entities_lock = threading.Lock()
    self.__file_lock = threading.Lock()
    self.__indexes_lock = threading.Lock()

    self.Read()

  def Clear(self):
    """ Clears the datastore by deleting all currently stored entities and
    queries. """
    self.__entities = {}
    self.__queries = {}
    self.__transactions = {}
    self.__query_history = {}
    self.__schema_cache = {}

  def _AppKindForKey(self, key):
    """ Get (app, kind) tuple from given key.

    The (app, kind) tuple is used as an index into several internal
    dictionaries, e.g. __entities.

    Args:
      key: entity_pb.Reference

    Returns:
      Tuple (app, kind), both are unicode strings.
    """
    last_path = key.path().element_list()[-1]
    return key.app(), last_path.type()

  def _StoreEntity(self, entity):
    """ Store the given entity.

    Args:
      entity: entity_pb.EntityProto
    """
    key = entity.key()
    app_kind = self._AppKindForKey(key)
    if app_kind not in self.__entities:
      self.__entities[app_kind] = {}
    self.__entities[app_kind][key] = _StoredEntity(entity)

    if app_kind in self.__schema_cache:
      del self.__schema_cache[app_kind]

  READ_PB_EXCEPTIONS = (ProtocolBuffer.ProtocolBufferDecodeError, LookupError,
                        TypeError, ValueError)
  READ_ERROR_MSG = ('Data in %s is corrupt or a different version. '
                    'Try running with the --clear_datastore flag.\n%r')
  READ_PY250_MSG = ('Are you using FloatProperty and/or GeoPtProperty? '
                    'Unfortunately loading float values from the datastore '
                    'file does not work with Python 2.5.0. '
                    'Please upgrade to a newer Python 2.5 release or use '
                    'the --clear_datastore flag.\n')

  def Read(self):
    """ Reads the datastore and history files into memory.

    The in-memory query history is cleared, but the datastore is *not*
    cleared; the entities in the files are merged into the entities in memory.
    If you want them to overwrite the in-memory datastore, call Clear() before
    calling Read().

    If the datastore file contains an entity with the same app name, kind, and
    key as an entity already in the datastore, the entity from the file
    overwrites the entity in the datastore.

    Also sets __next_id to one greater than the highest id allocated so far.
    """
    if self.__datastore_file and self.__datastore_file != '/dev/null':
      for encoded_entity in self.__ReadPickled(self.__datastore_file):
        try:
          entity = entity_pb.EntityProto(encoded_entity)
        except self.READ_PB_EXCEPTIONS, e:
          raise datastore_errors.InternalError(self.READ_ERROR_MSG %
                                               (self.__datastore_file, e))
        except struct.error, e:
          if (sys.version_info[0:3] == (2, 5, 0)
              and e.message.startswith('unpack requires a string argument')):
            raise datastore_errors.InternalError(self.READ_PY250_MSG +
                                                 self.READ_ERROR_MSG %
                                                 (self.__datastore_file, e))
          else:
            raise

        self._StoreEntity(entity)

        last_path = entity.key().path().element_list()[-1]
        if last_path.has_id() and last_path.id() >= self.__next_id:
          self.__next_id = last_path.id() + 1

      self.__query_history = {}
      for encoded_query, count in self.__ReadPickled(self.__history_file):
        try:
          query_pb = datastore_pb.Query(encoded_query)
        except self.READ_PB_EXCEPTIONS, e:
          raise datastore_errors.InternalError(self.READ_ERROR_MSG %
                                               (self.__history_file, e))

        if query_pb in self.__query_history:
          self.__query_history[query_pb] += count
        else:
          self.__query_history[query_pb] = count

  def Write(self):
    """ Writes out the datastore and history files. Be careful! If the files
    already exist, this method overwrites them!
    """
    self.__WriteDatastore()
    self.__WriteHistory()

  def __WriteDatastore(self):
    """ Writes out the datastore file. Be careful! If the file already exist,
    this method overwrites it!
    """
    if self.__datastore_file and self.__datastore_file != '/dev/null':
      encoded = []
      for kind_dict in self.__entities.values():
        for entity in kind_dict.values():
          encoded.append(entity.encoded_protobuf)

      self.__WritePickled(encoded, self.__datastore_file)

  def __WriteHistory(self):
    """ Writes out the history file. Be careful! If the file already exist,
    this method overwrites it!
    """
    if self.__history_file and self.__history_file != '/dev/null':
      encoded = [(query.Encode(), count)
                 for query, count in self.__query_history.items()]

      self.__WritePickled(encoded, self.__history_file)

  def __ReadPickled(self, filename):
    """Reads a pickled object from the given file and returns it.
    """
    self.__file_lock.acquire()

    try:
      try:
        if filename and filename != '/dev/null' and os.path.isfile(filename):
          return pickle.load(open(filename, 'rb'))
        else:
          logging.warning('Could not read datastore data from %s', filename)
      except (AttributeError, LookupError, NameError, TypeError,
              ValueError, struct.error, pickle.PickleError), e:
        raise datastore_errors.InternalError(
          'Could not read data from %s. Try running with the '
          '--clear_datastore flag. Cause:\n%r' % (filename, e))
    finally:
      self.__file_lock.release()

    return []

  def __WritePickled(self, obj, filename, openfile=file):
    """Pickles the object and writes it to the given file.
    """
    if not filename or filename == '/dev/null' or not obj:
      return

    tmpfile = openfile(os.tempnam(os.path.dirname(filename)), 'wb')

    pickler = pickle.Pickler(tmpfile, protocol=1)
    pickler.fast = True
    pickler.dump(obj)

    tmpfile.close()

    self.__file_lock.acquire()
    try:
      try:
        os.rename(tmpfile.name, filename)
      except OSError:
        try:
          os.remove(filename)
        except:
          pass
        os.rename(tmpfile.name, filename)
    finally:
      self.__file_lock.release()

  def MakeSyncCall(self, service, call, request, response):
    """ The main RPC entry point. service must be 'datastore_v3'. So far, the
    supported calls are 'Get', 'Put', 'RunQuery', 'Next', and 'Count'.
    """
    super(DatastoreFileStub, self).MakeSyncCall(service,
                                                call,
                                                request,
                                                response)

    explanation = []
    assert response.IsInitialized(explanation), explanation

  def QueryHistory(self):
    """Returns a dict that maps Query PBs to times they've been run.
    """
    return dict((pb, times) for pb, times in self.__query_history.items()
                if pb.app() == self.__app_id)

  def _Dynamic_Put(self, put_request, put_response):
    clones = []
    for entity in put_request.entity_list():
      clone = entity_pb.EntityProto()
      clone.CopyFrom(entity)
      clones.append(clone)

      assert clone.has_key()
      assert clone.key().path().element_size() > 0

      last_path = clone.key().path().element_list()[-1]
      if last_path.id() == 0 and not last_path.has_name():
        self.__id_lock.acquire()
        last_path.set_id(self.__next_id)
        self.__next_id += 1
        self.__id_lock.release()

        assert clone.entity_group().element_size() == 0
        group = clone.mutable_entity_group()
        root = clone.key().path().element(0)
        group.add_element().CopyFrom(root)

      else:
        assert (clone.has_entity_group() and
                clone.entity_group().element_size() > 0)

    self.__entities_lock.acquire()

    try:
      for clone in clones:
        self._StoreEntity(clone)
    finally:
      self.__entities_lock.release()

    if not put_request.has_transaction():
      self.__WriteDatastore()

    put_response.key_list().extend([c.key() for c in clones])


  def _Dynamic_Get(self, get_request, get_response):
    for key in get_request.key_list():
        app_kind = self._AppKindForKey(key)

        group = get_response.add_entity()
        try:
          entity = self.__entities[app_kind][key].protobuf
        except KeyError:
          entity = None

        if entity:
          group.mutable_entity().CopyFrom(entity)


  def _Dynamic_Delete(self, delete_request, delete_response):
    self.__entities_lock.acquire()
    try:
      for key in delete_request.key_list():
        app_kind = self._AppKindForKey(key)
        try:
          del self.__entities[app_kind][key]
          if not self.__entities[app_kind]:
            del self.__entities[app_kind]

          del self.__schema_cache[app_kind]
        except KeyError:
          pass

        if not delete_request.has_transaction():
          self.__WriteDatastore()
    finally:
      self.__entities_lock.release()


  def _Dynamic_RunQuery(self, query, query_result):
    if not self.__tx_lock.acquire(False):
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST, 'Can\'t query inside a transaction.')
    else:
      self.__tx_lock.release()

    if query.has_offset() and query.offset() > _MAX_QUERY_OFFSET:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST, 'Too big query offset.')

    num_components = len(query.filter_list()) + len(query.order_list())
    if query.has_ancestor():
      num_components += 1
    if num_components > _MAX_QUERY_COMPONENTS:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          ('query is too large. may not have more than %s filters'
           ' + sort orders ancestor total' % _MAX_QUERY_COMPONENTS))

    app = query.app()

    if self.__require_indexes:
      required, kind, ancestor, props, num_eq_filters = datastore_index.CompositeIndexForQuery(query)
      if required:
        required_key = kind, ancestor, props
        indexes = self.__indexes.get(app)
        if not indexes:
          raise apiproxy_errors.ApplicationError(
              datastore_pb.Error.NEED_INDEX,
              "This query requires a composite index, but none are defined. "
              "You must create an index.yaml file in your application root.")
        eq_filters_set = set(props[:num_eq_filters])
        remaining_filters = props[num_eq_filters:]
        for index in indexes:
          definition = datastore_admin.ProtoToIndexDefinition(index)
          index_key = datastore_index.IndexToKey(definition)
          if required_key == index_key:
            break
          if num_eq_filters > 1 and (kind, ancestor) == index_key[:2]:
            this_props = index_key[2]
            this_eq_filters_set = set(this_props[:num_eq_filters])
            this_remaining_filters = this_props[num_eq_filters:]
            if (eq_filters_set == this_eq_filters_set and
                remaining_filters == this_remaining_filters):
              break
        else:
          raise apiproxy_errors.ApplicationError(
              datastore_pb.Error.NEED_INDEX,
              "This query requires a composite index that is not defined. "
              "You must update the index.yaml file in your application root.")

    try:
      query.set_app(app)
      results = self.__entities[app, query.kind()].values()
      results = [entity.native for entity in results]
    except KeyError:
      results = []

    if query.has_ancestor():
      ancestor_path = query.ancestor().path().element_list()
      def is_descendant(entity):
        path = entity.key()._Key__reference.path().element_list()
        return path[:len(ancestor_path)] == ancestor_path
      results = filter(is_descendant, results)

    operators = {datastore_pb.Query_Filter.LESS_THAN:             '<',
                 datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:    '<=',
                 datastore_pb.Query_Filter.GREATER_THAN:          '>',
                 datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL: '>=',
                 datastore_pb.Query_Filter.EQUAL:                 '==',
                 }

    for filt in query.filter_list():
      assert filt.op() != datastore_pb.Query_Filter.IN

      prop = filt.property(0).name().decode('utf-8')
      op = operators[filt.op()]

      filter_val_list = [datastore_types.FromPropertyPb(filter_prop)
                         for filter_prop in filt.property_list()]

      def passes(entity):
        """ Returns True if the entity passes the filter, False otherwise. """
        if prop in datastore_types._SPECIAL_PROPERTIES:
          entity_vals = self.__GetSpecialPropertyValue(entity, prop)
        else:
          entity_vals = entity.get(prop, [])

        if not isinstance(entity_vals, list):
          entity_vals = [entity_vals]

        for fixed_entity_val in entity_vals:
          if type(fixed_entity_val) in datastore_types._RAW_PROPERTY_TYPES:
            continue

          for filter_val in filter_val_list:
            fixed_entity_type = self._PROPERTY_TYPE_TAGS.get(
              fixed_entity_val.__class__)
            filter_type = self._PROPERTY_TYPE_TAGS.get(filter_val.__class__)
            if fixed_entity_type == filter_type:
              comp = u'%r %s %r' % (fixed_entity_val, op, filter_val)
            elif op != '==':
              comp = '%r %s %r' % (fixed_entity_type, op, filter_type)
            else:
              continue

            logging.log(logging.DEBUG - 1,
                        'Evaling filter expression "%s"', comp)

            try:
              ret = eval(comp)
              if ret and ret != NotImplementedError:
                return True
            except TypeError:
              pass

        return False

      results = filter(passes, results)

    def has_prop_indexed(entity, prop):
      """Returns True if prop is in the entity and is not a raw property, or
      is a special property."""
      if prop in datastore_types._SPECIAL_PROPERTIES:
        return True

      values = entity.get(prop, [])
      if not isinstance(values, (tuple, list)):
        values = [values]

      for value in values:
        if type(value) not in datastore_types._RAW_PROPERTY_TYPES:
          return True
      return False

    for order in query.order_list():
      prop = order.property().decode('utf-8')
      results = [entity for entity in results if has_prop_indexed(entity, prop)]

    def order_compare_entities(a, b):
      """ Return a negative, zero or positive number depending on whether
      entity a is considered smaller than, equal to, or larger than b,
      according to the query's orderings. """
      cmped = 0
      for o in query.order_list():
        prop = o.property().decode('utf-8')

        reverse = (o.direction() is datastore_pb.Query_Order.DESCENDING)

        if prop in datastore_types._SPECIAL_PROPERTIES:
          a_val = self.__GetSpecialPropertyValue(a, prop)
          b_val = self.__GetSpecialPropertyValue(b, prop)
        else:
          a_val = a[prop]
          if isinstance(a_val, list):
            a_val = sorted(a_val, order_compare_properties, reverse=reverse)[0]

          b_val = b[prop]
          if isinstance(b_val, list):
            b_val = sorted(b_val, order_compare_properties, reverse=reverse)[0]

        cmped = order_compare_properties(a_val, b_val)

        if o.direction() is datastore_pb.Query_Order.DESCENDING:
          cmped = -cmped

        if cmped != 0:
          return cmped

      if cmped == 0:
        return cmp(a.key(), b.key())

    def order_compare_properties(x, y):
      """Return a negative, zero or positive number depending on whether
      property value x is considered smaller than, equal to, or larger than
      property value y. If x and y are different types, they're compared based
      on the type ordering used in the real datastore, which is based on the
      tag numbers in the PropertyValue PB.
      """
      if isinstance(x, datetime.datetime):
        x = datastore_types.DatetimeToTimestamp(x)
      if isinstance(y, datetime.datetime):
        y = datastore_types.DatetimeToTimestamp(y)

      x_type = self._PROPERTY_TYPE_TAGS.get(x.__class__)
      y_type = self._PROPERTY_TYPE_TAGS.get(y.__class__)

      if x_type == y_type:
        try:
          return cmp(x, y)
        except TypeError:
          return 0
      else:
        return cmp(x_type, y_type)

    results.sort(order_compare_entities)

    offset = 0
    limit = len(results)
    if query.has_offset():
      offset = query.offset()
    if query.has_limit():
      limit = query.limit()
    if limit > _MAXIMUM_RESULTS:
      limit = _MAXIMUM_RESULTS
    results = results[offset:limit + offset]

    clone = datastore_pb.Query()
    clone.CopyFrom(query)
    clone.clear_hint()
    if clone in self.__query_history:
      self.__query_history[clone] += 1
    else:
      self.__query_history[clone] = 1
    self.__WriteHistory()

    self.__cursor_lock.acquire()
    cursor = self.__next_cursor
    self.__next_cursor += 1
    self.__cursor_lock.release()
    self.__queries[cursor] = (results, len(results))

    query_result.mutable_cursor().set_cursor(cursor)
    query_result.set_more_results(len(results) > 0)

  def _Dynamic_Next(self, next_request, query_result):
    cursor = next_request.cursor().cursor()

    try:
      results, orig_count = self.__queries[cursor]
    except KeyError:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'Cursor %d not found' % cursor)

    count = next_request.count()
    results_pb = [r._ToPb() for r in results[:count]]
    query_result.result_list().extend(results_pb)
    del results[:count]

    query_result.set_more_results(len(results) > 0)

  def _Dynamic_Count(self, query, integer64proto):
    query_result = datastore_pb.QueryResult()
    self._Dynamic_RunQuery(query, query_result)
    cursor = query_result.cursor().cursor()
    results, count = self.__queries[cursor]
    integer64proto.set_value(count)
    del self.__queries[cursor]

  def _Dynamic_BeginTransaction(self, request, transaction):
    self.__tx_handle_lock.acquire()
    handle = self.__next_tx_handle
    self.__next_tx_handle += 1
    self.__tx_handle_lock.release()

    self.__transactions[handle] = None
    transaction.set_handle(handle)

    self.__tx_lock.acquire()
    snapshot = [(app_kind, dict(entities))
                for app_kind, entities in self.__entities.items()]
    self.__tx_snapshot = dict(snapshot)

  def _Dynamic_Commit(self, transaction, transaction_response):
    if not self.__transactions.has_key(transaction.handle()):
      raise apiproxy_errors.ApplicationError(
        datastore_pb.Error.BAD_REQUEST,
        'Transaction handle %d not found' % transaction.handle())

    self.__tx_snapshot = {}
    try:
      self.__WriteDatastore()
    finally:
      self.__tx_lock.release()

  def _Dynamic_Rollback(self, transaction, transaction_response):
    if not self.__transactions.has_key(transaction.handle()):
      raise apiproxy_errors.ApplicationError(
        datastore_pb.Error.BAD_REQUEST,
        'Transaction handle %d not found' % transaction.handle())

    self.__entities = self.__tx_snapshot
    self.__tx_snapshot = {}
    self.__tx_lock.release()

  def _Dynamic_GetSchema(self, app_str, schema):
    minint = -sys.maxint - 1
    try:
      minfloat = float('-inf')
    except ValueError:
      minfloat = -1e300000

    app_str = app_str.value()

    kinds = []

    for app, kind in self.__entities:
      if app == app_str:
        app_kind = (app, kind)
        if app_kind in self.__schema_cache:
          kinds.append(self.__schema_cache[app_kind])
          continue

        kind_pb = entity_pb.EntityProto()
        kind_pb.mutable_key().set_app('')
        kind_pb.mutable_key().mutable_path().add_element().set_type(kind)
        kind_pb.mutable_entity_group()

        props = {}

        for entity in self.__entities[app_kind].values():
          for prop in entity.protobuf.property_list():
            if prop.name() not in props:
              props[prop.name()] = entity_pb.PropertyValue()
            props[prop.name()].MergeFrom(prop.value())

        for value_pb in props.values():
          if value_pb.has_int64value():
            value_pb.set_int64value(minint)
          if value_pb.has_booleanvalue():
            value_pb.set_booleanvalue(False)
          if value_pb.has_stringvalue():
            value_pb.set_stringvalue('')
          if value_pb.has_doublevalue():
            value_pb.set_doublevalue(minfloat)
          if value_pb.has_pointvalue():
            value_pb.mutable_pointvalue().set_x(minfloat)
            value_pb.mutable_pointvalue().set_y(minfloat)
          if value_pb.has_uservalue():
            value_pb.mutable_uservalue().set_gaiaid(minint)
            value_pb.mutable_uservalue().set_email('')
            value_pb.mutable_uservalue().set_auth_domain('')
            value_pb.mutable_uservalue().clear_nickname()
          elif value_pb.has_referencevalue():
            value_pb.clear_referencevalue()
            value_pb.mutable_referencevalue().set_app('')

        for name, value_pb in props.items():
          prop_pb = kind_pb.add_property()
          prop_pb.set_name(name)
          prop_pb.set_multiple(False)
          prop_pb.mutable_value().CopyFrom(value_pb)

        kinds.append(kind_pb)
        self.__schema_cache[app_kind] = kind_pb

    for kind_pb in kinds:
      schema.add_kind().CopyFrom(kind_pb)

  def _Dynamic_CreateIndex(self, index, id_response):
    if index.id() != 0:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'New index id must be 0.')
    elif self.__FindIndex(index):
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'Index already exists.')

    self.__index_id_lock.acquire()
    index.set_id(self.__next_index_id)
    id_response.set_value(self.__next_index_id)
    self.__next_index_id += 1
    self.__index_id_lock.release()

    clone = entity_pb.CompositeIndex()
    clone.CopyFrom(index)
    app = index.app_id()
    clone.set_app_id(app)

    self.__indexes_lock.acquire()
    try:
      if app not in self.__indexes:
        self.__indexes[app] = []
      self.__indexes[app].append(clone)
    finally:
      self.__indexes_lock.release()

  def _Dynamic_GetIndices(self, app_str, composite_indices):
    composite_indices.index_list().extend(
      self.__indexes.get(app_str.value(), []))

  def _Dynamic_UpdateIndex(self, index, void):
    stored_index = self.__FindIndex(index)
    if not stored_index:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             "Index doesn't exist.")
    elif (index.state() != stored_index.state() and
          index.state() not in self._INDEX_STATE_TRANSITIONS[stored_index.state()]):
      raise apiproxy_errors.ApplicationError(
        datastore_pb.Error.BAD_REQUEST,
        "cannot move index state from %s to %s" %
          (entity_pb.CompositeIndex.State_Name(stored_index.state()),
          (entity_pb.CompositeIndex.State_Name(index.state()))))

    self.__indexes_lock.acquire()
    try:
      stored_index.set_state(index.state())
    finally:
      self.__indexes_lock.release()

  def _Dynamic_DeleteIndex(self, index, void):
    stored_index = self.__FindIndex(index)
    if not stored_index:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             "Index doesn't exist.")

    app = index.app_id()
    self.__indexes_lock.acquire()
    try:
      self.__indexes[app].remove(stored_index)
    finally:
      self.__indexes_lock.release()

  def __FindIndex(self, index):
    """Finds an existing index by definition.

    Args:
      definition: entity_pb.CompositeIndex

    Returns:
      entity_pb.CompositeIndex, if it exists; otherwise None
    """
    app = index.app_id()
    if app in self.__indexes:
      for stored_index in self.__indexes[app]:
        if index.definition() == stored_index.definition():
          return stored_index

    return None

  @classmethod
  def __GetSpecialPropertyValue(cls, entity, property):
    """Returns an entity's value for a special property.

    Right now, the only special property is __key__, whose value is the
    entity's key.

    Args:
      entity: datastore.Entity

    Returns:
      property value. For __key__, a datastore_types.Key.

    Raises:
      AssertionError, if the given property is not special.
    """
    assert property in datastore_types._SPECIAL_PROPERTIES
    if property == datastore_types._KEY_SPECIAL_PROPERTY:
      return entity.key()
