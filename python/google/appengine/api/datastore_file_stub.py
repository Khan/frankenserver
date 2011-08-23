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
"""












import collections
import logging
import os
import struct
import sys
import tempfile
import threading
import weakref



import cPickle as pickle

from google.appengine.api import apiproxy_stub
from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_stub_util
from google.appengine.runtime import apiproxy_errors
from google.net.proto import ProtocolBuffer
from google.appengine.datastore import entity_pb



datastore_pb.Query.__hash__ = lambda self: hash(self.Encode())


class _StoredEntity(object):
  """Simple wrapper around an entity stored by the stub.

  Public properties:
    protobuf: Native protobuf Python object, entity_pb.EntityProto.
    encoded_protobuf: Encoded binary representation of above protobuf.
  """

  def __init__(self, entity):
    """Create a _StoredEntity object and store an entity.

    Args:
      entity: entity_pb.EntityProto to store.
    """
    self.protobuf = entity






    self.encoded_protobuf = entity.Encode()


class KindPseudoKind(object):
  """Pseudo-kind for schema queries.

  Provides a Query method to perform the actual query.

  Public properties:
    name: the pseudo-kind name
  """
  name = '__kind__'

  def Query(self, entities, query, filters, orders):
    """Perform a query on this pseudo-kind.

    Args:
      entities: all the app's entities.
      query: the original datastore_pb.Query.
      filters: the filters from query.
      orders: the orders from query.

    Returns:
      (results, remaining_filters, remaining_orders)
      results is a list of entity_pb.EntityProto
      remaining_filters and remaining_orders are the filters and orders that
      should be applied in memory
    """
    kind_range = datastore_stub_util.ParseKindQuery(query, filters, orders)
    app_namespace_str = datastore_types.EncodeAppIdNamespace(
        query.app(), query.name_space())
    kinds = []


    for app_namespace, kind in entities:
      if app_namespace != app_namespace_str: continue
      kind = kind.decode('utf-8')
      if not kind_range.Contains(kind): continue
      kinds.append(datastore.Entity(self.name, name=kind, _app=query.app(),
                                    namespace=query.name_space())._ToPb())

    return (kinds, [], [])


class PropertyPseudoKind(object):
  """Pseudo-kind for schema queries.

  Provides a Query method to perform the actual query.

  Public properties:
    name: the pseudo-kind name
  """
  name = '__property__'

  def __init__(self, filestub):
    """Constructor.

    Initializes a __property__ pseudo-kind definition.

    Args:
      filestub: the DatastoreFileStub instance being served by this
          pseudo-kind.
    """
    self.filestub = filestub

  def Query(self, entities, query, filters, orders):
    """Perform a query on this pseudo-kind.

    Args:
      entities: all the app's entities.
      query: the original datastore_pb.Query.
      filters: the filters from query.
      orders: the orders from query.

    Returns:
      (results, remaining_filters, remaining_orders)
      results is a list of entity_pb.EntityProto
      remaining_filters and remaining_orders are the filters and orders that
      should be applied in memory
    """
    property_range = datastore_stub_util.ParsePropertyQuery(query, filters,
                                                            orders)
    keys_only = query.keys_only()
    app_namespace_str = datastore_types.EncodeAppIdNamespace(
        query.app(), query.name_space())

    properties = []
    if keys_only:
      usekey = '__property__keys'
    else:
      usekey = '__property__'

    for app_namespace, kind in entities:
      if app_namespace != app_namespace_str: continue

      app_kind = (app_namespace_str, kind)
      kind = kind.decode('utf-8')



      (start_cmp, end_cmp) = property_range.MapExtremes(
          lambda extreme, inclusive, is_end: cmp(kind, extreme[0]))
      if not((start_cmp is None or start_cmp >= 0) and
             (end_cmp is None or end_cmp <= 0)):
        continue


      kind_properties = self.filestub._GetSchemaCache(app_kind, usekey)
      if not kind_properties:
        kind_properties = []
        kind_key = datastore_types.Key.from_path(KindPseudoKind.name, kind,
                                                 _app=query.app(),
                                                 namespace=query.name_space())

        props = collections.defaultdict(set)



        for entity in entities[app_kind].values():
          for prop in entity.protobuf.property_list():
            prop_name = prop.name()

            if (prop_name in
                datastore_stub_util.GetInvisibleSpecialPropertyNames()):
              continue
            value_pb = prop.value()
            props[prop_name].add(datastore_types.GetPropertyValueTag(value_pb))


        for prop in sorted(props):
          property_e = datastore.Entity(self.name, name=prop, parent=kind_key,
                                        _app=query.app(),
                                        namespace=query.name_space())

          if not keys_only and props[prop]:
            property_e['property_representation'] = [
                datastore_stub_util._PROPERTY_TYPE_NAMES[tag]
                for tag in sorted(props[prop])]

          kind_properties.append(property_e._ToPb())

        self.filestub._SetSchemaCache(app_kind, usekey, kind_properties)


      def InQuery(property_e):
        return property_range.Contains(
            (kind, property_e.key().path().element_list()[-1].name()))
      properties += filter(InQuery, kind_properties)

    return (properties, [], [])


class NamespacePseudoKind(object):
  """Pseudo-kind for namespace queries.

  Provides a Query method to perform the actual query.

  Public properties:
    name: the pseudo-kind name
  """
  name = '__namespace__'

  def Query(self, entities, query, filters, orders):
    """Perform a query on this pseudo-kind.

    Args:
      entities: all the app's entities.
      query: the original datastore_pb.Query.
      filters: the filters from query.
      orders: the orders from query.

    Returns:
      (results, remaining_filters, remaining_orders)
      results is a list of entity_pb.EntityProto
      remaining_filters and remaining_orders are the filters and orders that
      should be applied in memory
    """
    namespace_range = datastore_stub_util.ParseNamespaceQuery(query, filters,
                                                              orders)
    app_str = query.app()

    namespaces = set()

    for app_namespace, _ in entities:
      (app_id, namespace) = datastore_types.DecodeAppIdNamespace(app_namespace)
      if app_id == app_str and namespace_range.Contains(namespace):
        namespaces.add(namespace)


    namespace_entities = []
    for namespace in namespaces:
      if namespace:
        namespace_e = datastore.Entity(self.name, name=namespace,
                                       _app=query.app())
      else:
        namespace_e = datastore.Entity(self.name,
                                       id=datastore_types._EMPTY_NAMESPACE_ID,
                                       _app=query.app())
      namespace_entities.append(namespace_e._ToPb())

    return (namespace_entities, [], [])


class DatastoreFileStub(datastore_stub_util.BaseDatastore,
                        apiproxy_stub.APIProxyStub,
                        datastore_stub_util.DatastoreStub):
  """ Persistent stub for the Python datastore API.

  Stores all entities in memory, and persists them to a file as pickled
  protocol buffers. A DatastoreFileStub instance handles a single app's data
  and is backed by files on disk.
  """

  def __init__(self,
               app_id,
               datastore_file,
               history_file=None,
               require_indexes=False,
               service_name='datastore_v3',
               trusted=False,
               consistency_policy=None,
               save_changes=True):
    """Constructor.

    Initializes and loads the datastore from the backing files, if they exist.

    Args:
      app_id: string
      datastore_file: string, stores all entities across sessions.  Use None
          not to use a file.
      history_file: DEPRECATED. No-op.
      require_indexes: bool, default False.  If True, composite indexes must
          exist in index.yaml for queries that need them.
      service_name: Service name expected for all calls.
      trusted: bool, default False.  If True, this stub allows an app to
        access the data of another app.
      consistency_policy: The consistency policy to use or None to use the
        default. Consistency policies can be found in
        datastore_stub_util.*ConsistencyPolicy
      save_changes: bool, default True. If this stub should modify
        datastore_file when entities are changed.
    """
    datastore_stub_util.BaseDatastore.__init__(self, require_indexes,
                                               consistency_policy)
    apiproxy_stub.APIProxyStub.__init__(self, service_name)
    datastore_stub_util.DatastoreStub.__init__(self, weakref.proxy(self),
                                               app_id, trusted)





    self.__datastore_file = datastore_file
    self.__save_changes = save_changes








    self.__entities_by_kind = collections.defaultdict(dict)
    self.__entities_by_group = collections.defaultdict(dict)
    self.__entities_lock = threading.Lock()




    self.__schema_cache = {}


    self.__query_history = {}

    self.__next_id = 1L
    self.__id_lock = threading.Lock()

    self.__file_lock = threading.Lock()


    self._RegisterPseudoKind(KindPseudoKind())
    self._RegisterPseudoKind(PropertyPseudoKind(weakref.proxy(self)))
    self._RegisterPseudoKind(NamespacePseudoKind())

    self.Read()

  def Clear(self):
    """ Clears the datastore by deleting all currently stored entities and
    queries. """
    self.__entities_lock.acquire()
    try:
      datastore_stub_util.BaseDatastore.Clear(self)
      datastore_stub_util.DatastoreStub.Clear(self)

      self.__entities_by_kind = collections.defaultdict(dict)
      self.__entities_by_group = collections.defaultdict(dict)
      self.__query_history = {}
      self.__schema_cache = {}
    finally:
      self.__entities_lock.release()

  def _GetEntityLocation(self, key):
    """Get keys to self.__entities_by_* from the given key.

    Example usage:
      app_kind, eg_k, k = self._GetEntityLocation(key)
      self.__entities_by_kind[app_kind][k]
      self.__entities_by_entity_group[eg_k][k]

    Args:
      key: entity_pb.Reference

    Returns:
      Tuple (by_kind key, by_entity_group key, entity key)
    """
    app_ns = datastore_types.EncodeAppIdNamespace(key.app(), key.name_space())
    kind = key.path().element_list()[-1].type()
    entity_group = datastore_stub_util._GetEntityGroup(key)
    eg_k = datastore_types.ReferenceToKeyValue(entity_group)
    k = datastore_types.ReferenceToKeyValue(key)

    return ((app_ns, kind), eg_k, k)

  def _StoreEntity(self, entity, insert=False):
    """ Store the given entity.

    Any needed locking should be managed by the caller.

    Args:
      entity: The entity_pb.EntityProto to store.
      insert: If we should check for existance.
    """
    app_kind, eg_k, k = self._GetEntityLocation(entity.key())

    assert not insert or k not in self.__entities_by_kind[app_kind]

    self.__entities_by_kind[app_kind][k] = _StoredEntity(entity)
    self.__entities_by_group[eg_k][k] = entity


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
          raise apiproxy_errors.ApplicationError(
              datastore_pb.Error.INTERNAL_ERROR,
              self.READ_ERROR_MSG % (self.__datastore_file, e))
        except struct.error, e:
          if (sys.version_info[0:3] == (2, 5, 0)
              and e.message.startswith('unpack requires a string argument')):


            raise apiproxy_errors.ApplicationError(
                datastore_pb.Error.INTERNAL_ERROR,
                self.READ_PY250_MSG + self.READ_ERROR_MSG %
                (self.__datastore_file, e))
          else:
            raise

        self._StoreEntity(entity)

        last_path = entity.key().path().element_list()[-1]
        if last_path.has_id() and last_path.id() >= self.__next_id:
          self.__next_id = last_path.id() + 1

  def Write(self):
    """ Writes out the datastore and history files. Be careful! If the files
    already exist, this method overwrites them!
    """
    self.__WriteDatastore()

  def __WriteDatastore(self):
    """ Writes out the datastore file. Be careful! If the file already exist,
    this method overwrites it!
    """
    if (self.__datastore_file and self.__datastore_file != '/dev/null' and
        self.__save_changes):
      encoded = []
      for kind_dict in self.__entities_by_kind.values():
        encoded.extend(entity.encoded_protobuf for entity in kind_dict.values())

      self.__WritePickled(encoded, self.__datastore_file)

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
      except (AttributeError, LookupError, ImportError, NameError, TypeError,
              ValueError, struct.error, pickle.PickleError), e:


        raise apiproxy_errors.ApplicationError(
            datastore_pb.Error.INTERNAL_ERROR,
            'Could not read data from %s. Try running with the '
            '--clear_datastore flag. Cause:\n%r' % (filename, e))
    finally:
      self.__file_lock.release()

    return []

  def __WritePickled(self, obj, filename):
    """Pickles the object and writes it to the given file.
    """
    if not filename or filename == '/dev/null' or not obj:
      return


    descriptor, tmp_filename = tempfile.mkstemp(dir=os.path.dirname(filename))
    tmpfile = os.fdopen(descriptor, 'wb')





    pickler = pickle.Pickler(tmpfile, protocol=1)
    pickler.fast = True
    pickler.dump(obj)

    tmpfile.close()

    self.__file_lock.acquire()
    try:
      try:

        os.rename(tmp_filename, filename)
      except OSError:

        try:
          os.remove(filename)
        except:
          pass
        os.rename(tmp_filename, filename)
    finally:
      self.__file_lock.release()

  def MakeSyncCall(self, service, call, request, response):
    """ The main RPC entry point. service must be 'datastore_v3'.
    """
    self.assertPbIsInitialized(request)
    super(DatastoreFileStub, self).MakeSyncCall(service,
                                                call,
                                                request,
                                                response)
    self.assertPbIsInitialized(response)

  def assertPbIsInitialized(self, pb):
    """Raises an exception if the given PB is not initialized and valid."""
    explanation = []
    assert pb.IsInitialized(explanation), explanation

    pb.Encode()

  def QueryHistory(self):
    """Returns a dict that maps Query PBs to times they've been run.
    """

    return dict((pb, times) for pb, times in self.__query_history.items()
                if pb.app() == self._app_id)

  def _GetSchemaCache(self, kind, usekey):
    if kind in self.__schema_cache and usekey in self.__schema_cache[kind]:
      return self.__schema_cache[kind][usekey]
    else:
      return None

  def _SetSchemaCache(self, kind, usekey, value):
    if kind not in self.__schema_cache:
      self.__schema_cache[kind] = {}
    self.__schema_cache[kind][usekey] = value



  def _Put(self, entity, insert):
    entity = datastore_stub_util.StoreEntity(entity)

    self.__entities_lock.acquire()
    try:
      self._StoreEntity(entity, insert)
    finally:
      self.__entities_lock.release()

  def _Get(self, key):
    app_kind, _, k = self._GetEntityLocation(key)


    try:
      return datastore_stub_util.LoadEntity(
          self.__entities_by_kind[app_kind][k].protobuf)
    except KeyError:
      pass

  def _Delete(self, key):
    app_kind, eg_k, k = self._GetEntityLocation(key)

    self.__entities_lock.acquire()
    try:
      del self.__entities_by_kind[app_kind][k]
      del self.__entities_by_group[eg_k][k]
      if not self.__entities_by_kind[app_kind]:

        del self.__entities_by_kind[app_kind]
      if not self.__entities_by_group[eg_k]:
        del self.__entities_by_group[eg_k]

      del self.__schema_cache[app_kind]
    except KeyError:

      pass
    finally:
      self.__entities_lock.release()

  def _GetEntitiesInEntityGroup(self, entity_group):
    eg_k = datastore_types.ReferenceToKeyValue(entity_group)
    return self.__entities_by_group[eg_k].copy()

  def _GetQueryCursor(self, query, filters, orders):
    app_id = query.app()
    namespace = query.name_space()

    pseudo_kind = None
    if query.has_kind() and query.kind() in self._pseudo_kinds:
      pseudo_kind = self._pseudo_kinds[query.kind()]




    self.__entities_lock.acquire()
    try:
      app_ns = datastore_types.EncodeAppIdNamespace(app_id, namespace)
      if pseudo_kind:

        (results, filters, orders) = pseudo_kind.Query(self.__entities_by_kind,
                                                       query, filters, orders)
      elif query.has_kind():
        results = [entity.protobuf for entity in
                   self.__entities_by_kind[app_ns, query.kind()].values()]
      else:
        results = []
        for (cur_app_ns, _), entities in self.__entities_by_kind.iteritems():
          if cur_app_ns == app_ns:
            results.extend(entity.protobuf for entity in entities.itervalues())
    except KeyError:
      results = []
    finally:
      self.__entities_lock.release()

    return datastore_stub_util._GetQueryCursor(results, query, filters, orders)

  def _AllocateIds(self, reference, size=1, max_id=None):
    datastore_stub_util.Check(not (size and max_id),
                              'Both size and max cannot be set.')

    self.__id_lock.acquire()
    try:
      start = self.__next_id
      if size:
        datastore_stub_util.Check(size > 0, 'Size must be greater than 0.')
        self.__next_id += size
      elif max_id:
        datastore_stub_util.Check(max_id >=0,
                                  'Max must be greater than or equal to 0.')
        self.__next_id = max(self.__next_id, max_id + 1)
      end = self.__next_id - 1
    finally:
      self.__id_lock.release()

    return (start, end)



  def _OnApply(self):
    self.__WriteDatastore()

  def _Dynamic_RunQuery(self, query, query_result):
    super(DatastoreFileStub, self)._Dynamic_RunQuery(query, query_result)


    clone = datastore_pb.Query()
    clone.CopyFrom(query)
    clone.clear_hint()
    clone.clear_limit()
    clone.clear_offset()
    if clone in self.__query_history:
      self.__query_history[clone] += 1
    else:
      self.__query_history[clone] = 1
