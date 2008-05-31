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
import pickle
import struct
import sys
import tempfile
import threading
import types
import warnings

from google.appengine.api import api_base_pb
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


class DatastoreFileStub(object):
  """ Persistent stub for the Python datastore API.

  Stores all entities in memory, and persists them to a file as pickled
  protocol buffers. A DatastoreFileStub instance handles a single app's data
  and is backed by files on disk.
  """

  def __init__(self, app_id, datastore_file, history_file,
               require_indexes=False):
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
    """

    assert isinstance(app_id, types.StringTypes) and app_id != ''
    self.__app_id = app_id
    self.__datastore_file = datastore_file
    self.__history_file = history_file

    self.__entities = {}

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
    pb_exceptions = (ProtocolBuffer.ProtocolBufferDecodeError, LookupError,
                     TypeError, ValueError)
    error_msg = ('Data in %s is corrupt or a different version. '
                 'Try running with the --clear_datastore flag.\n%r')

    if self.__datastore_file and self.__datastore_file != '/dev/null':
      for encoded_entity in self.__ReadPickled(self.__datastore_file):
        try:
          entity = entity_pb.EntityProto(encoded_entity)
        except pb_exceptions, e:
          raise datastore_errors.InternalError(error_msg %
                                               (self.__datastore_file, e))

        last_path = entity.key().path().element_list()[-1]
        app_kind = (entity.key().app(), last_path.type())
        kind_dict = self.__entities.setdefault(app_kind, {})
        kind_dict[entity.key()] = entity

        if last_path.has_id() and last_path.id() >= self.__next_id:
          self.__next_id = last_path.id() + 1

      self.__query_history = {}
      for encoded_query, count in self.__ReadPickled(self.__history_file):
        try:
          query_pb = datastore_pb.Query(encoded_query)
        except pb_exceptions, e:
          raise datastore_errors.InternalError(error_msg %
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
          encoded.append(entity.Encode())

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
    pickle.dump(obj, tmpfile, 1)
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

    assert service == 'datastore_v3'

    explanation = []
    assert request.IsInitialized(explanation), explanation

    (getattr(self, "_Dynamic_" + call))(request, response)

    assert response.IsInitialized(explanation), explanation

  def ResolveAppId(self, app):
    """ If the given app name is the placeholder for the local app, returns
    our app_id. Otherwise returns the app name unchanged.
    """
    assert app != ''
    if app == datastore._LOCAL_APP_ID:
      return self.__app_id
    else:
      return app

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

      app = self.ResolveAppId(clone.key().app())
      clone.mutable_key().set_app(app)

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
        last_path = clone.key().path().element_list()[-1]
        kind_dict = self.__entities.setdefault((app, last_path.type()), {})
        kind_dict[clone.key()] = clone
    finally:
      self.__entities_lock.release()

    if not put_request.has_transaction():
      self.__WriteDatastore()

    put_response.key_list().extend([c.key() for c in clones])


  def _Dynamic_Get(self, get_request, get_response):
    for key in get_request.key_list():
        app = self.ResolveAppId(key.app())
        key.set_app(app)
        last_path = key.path().element_list()[-1]

        group = get_response.add_entity()
        try:
          entity = self.__entities[app, last_path.type()][key]
        except KeyError:
          entity = None

        if entity:
          group.mutable_entity().CopyFrom(entity)


  def _Dynamic_Delete(self, delete_request, delete_response):
    self.__entities_lock.acquire()
    try:
      for key in delete_request.key_list():
        try:
          app = self.ResolveAppId(key.app())
          key.set_app(app)
          kind = key.path().element_list()[-1].type()
          del self.__entities[app, kind][key]
          if not self.__entities[app, kind]:
            del self.__entities[app, kind]
        except KeyError:
          pass

        if not delete_request.has_transaction():
          self.__WriteDatastore()
    finally:
      self.__entities_lock.release()


  def _Dynamic_RunQuery(self, query, query_result):
    if not self.__tx_lock.acquire(False):
      raise apiproxy_errors.ApplicationError(
        datastore_pb.Error.BAD_REQUEST, "Can't query inside a transaction.")
    else:
      self.__tx_lock.release()

    app = self.ResolveAppId(query.app())

    if self.__require_indexes:
      required_index = datastore_index.CompositeIndexForQuery(query)
      if required_index is not None:
        kind, ancestor, props, num_eq_filters = required_index
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
      results = [datastore.Entity._FromPb(pb) for pb in results]
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

      def passes(entity):
        """ Returns True if the entity passes the filter, False otherwise. """
        entity_vals = entity.get(prop, [])
        if type(entity_vals) is not types.ListType:
          entity_vals = [entity_vals]

        entity_property_list = [datastore_types.ToPropertyPb(prop, value)
                                for value in entity_vals]

        for entity_prop in entity_property_list:
          fixed_entity_val = datastore_types.FromPropertyPb(entity_prop)

          if isinstance(fixed_entity_val, datastore_types._RAW_PROPERTY_TYPES):
            continue

          for filter_prop in filt.property_list():
            filter_val = datastore_types.FromPropertyPb(filter_prop)

            comp = u'%r %s %r' % (fixed_entity_val, op, filter_val)

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
      """Returns True if prop is in the entity and is not a raw property."""
      values = entity.get(prop, [])
      if not isinstance(values, (tuple, list)):
        values = [values]

      for value in values:
        if not isinstance(value, datastore_types._RAW_PROPERTY_TYPES):
          return True
      return False

    for order in query.order_list():
      prop = order.property().decode('utf-8')
      results = [entity for entity in results if has_prop_indexed(entity, prop)]

    def order_compare(a, b):
      """ Return a negative, zero or positive number depending on whether
      entity a is considered smaller than, equal to, or larger than b,
      according to the query's orderings. """
      cmped = 0
      for o in query.order_list():
        prop = o.property().decode('utf-8')

        if o.direction() is datastore_pb.Query_Order.ASCENDING:
          selector = min
        else:
          selector = max

        a_val = a[prop]
        if isinstance(a_val, list):
          a_val = selector(a_val)

        b_val = b[prop]
        if isinstance(b_val, list):
          b_val = selector(b_val)

        try:
          cmped = cmp(a_val, b_val)
        except TypeError:
          cmped = NotImplementedError

        if cmped == NotImplementedError:
          cmped = cmp(type(a_val), type(b_val))

        if o.direction() is datastore_pb.Query_Order.DESCENDING:
          cmped = -cmped

        if cmped != 0:
          return cmped
      if cmped == 0:
        return cmp(a.key(), b.key())

    results.sort(order_compare)

    offset = 0
    limit = len(results)
    if query.has_offset():
      offset = query.offset()
    if query.has_limit():
      limit = query.limit()
    results = results[offset:limit + offset]

    clone = datastore_pb.Query()
    clone.CopyFrom(query)
    clone.clear_hint()
    if clone in self.__query_history:
      self.__query_history[clone] += 1
    else:
      self.__query_history[clone] = 1
    self.__WriteHistory()

    results = [e._ToPb() for e in results]
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
    for r in results[:count]:
      query_result.add_result().CopyFrom(r)
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

    app_str = self.ResolveAppId(app_str.value())

    kinds = []

    for app, kind in self.__entities:
      if app == app_str:
        kind_pb = entity_pb.EntityProto()
        kind_pb.mutable_key().set_app('')
        kind_pb.mutable_key().mutable_path().add_element().set_type(kind)
        kind_pb.mutable_entity_group()
        kinds.append(kind_pb)

        props = {}

        for entity in self.__entities[(app, kind)].values():
          for prop in entity.property_list():
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
            value_pb.set_doublevalue(float('-inf'))
          if value_pb.has_pointvalue():
            value_pb.mutable_pointvalue().set_x(float('-inf'))
            value_pb.mutable_pointvalue().set_y(float('-inf'))
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
          prop_pb.mutable_value().CopyFrom(value_pb)

    schema.kind_list().extend(kinds)

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
    app = self.ResolveAppId(index.app_id())
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
      self.__indexes.get(self.ResolveAppId(app_str.value()), []))

  def _Dynamic_UpdateIndex(self, index, void):
    stored_index = self.__FindIndex(index)
    if not stored_index:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             "Index doesn't exist.")
    elif index.state() != stored_index.state() + 1:
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

    app = self.ResolveAppId(index.app_id())
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
    app = self.ResolveAppId(index.app_id())

    if app in self.__indexes:
      for stored_index in self.__indexes[app]:
        if index.definition() == stored_index.definition():
          return stored_index

    return None
