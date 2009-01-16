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

"""An apiproxy stub that calls a remote handler via HTTP.

This allows easy remote access to the App Engine datastore, and potentially any
of the other App Engine APIs, using the same interface you use when accessing
the service locally.

An example Python script:
---
from google.appengine.ext import db
from google.appengine.ext import remote_api
from myapp import models
import getpass

def auth_func():
  return (raw_input('Username:'), getpass.getpass('Password:'))

remote_api.ConfigureRemoteDatastore('my-app', '/remote_api', auth_func)

# Now you can access the remote datastore just as if your code was running on
# App Engine!

houses = models.House.all().fetch(100)
for a_house in q:
  a_house.doors += 1
db.put(houses)
---

A few caveats:
- Where possible, avoid iterating over queries directly. Fetching as many
  results as you will need is faster and more efficient.
- If you need to iterate, consider instead fetching items in batches with a sort
  order and constructing a new query starting from where the previous one left
  off. The __key__ pseudo-property can be used as a sort key for this purpose,
  and does not even require a custom index if you are iterating over all
  entities of a given type.
- Likewise, it's a good idea to put entities in batches. Instead of calling put
  for each individual entity, accumulate them and put them in batches using
  db.put(), if you can.
- Requests and responses are still limited to 1MB each, so if you have large
  entities or try and fetch or put many of them at once, your requests may fail.
"""





import os
import pickle
import sha
import sys
import thread
import threading
from google.appengine.api import apiproxy_stub_map
from google.appengine.datastore import datastore_pb
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.runtime import apiproxy_errors
from google.appengine.tools import appengine_rpc


def GetUserAgent():
  """Determines the value of the 'User-agent' header to use for HTTP requests.

  Returns:
    String containing the 'user-agent' header value, which includes the SDK
    version, the platform information, and the version of Python;
    e.g., "remote_api/1.0.1 Darwin/9.2.0 Python/2.5.2".
  """
  product_tokens = []

  product_tokens.append("Google-remote_api/1.0")

  product_tokens.append(appengine_rpc.GetPlatformToken())

  python_version = ".".join(str(i) for i in sys.version_info)
  product_tokens.append("Python/%s" % python_version)

  return " ".join(product_tokens)


def GetSourceName():
  return "Google-remote_api-1.0"


class TransactionData(object):
  """Encapsulates data about an individual transaction."""

  def __init__(self, thread_id):
    self.thread_id = thread_id
    self.preconditions = {}
    self.entities = {}


class RemoteStub(object):
  """A stub for calling services on a remote server over HTTP.

  You can use this to stub out any service that the remote server supports.
  """

  def __init__(self, server, path):
    """Constructs a new RemoteStub that communicates with the specified server.

    Args:
      server: An instance of a subclass of
        google.appengine.tools.appengine_rpc.AbstractRpcServer.
      path: The path to the handler this stub should send requests to.
    """
    self._server = server
    self._path = path

  def MakeSyncCall(self, service, call, request, response):
    request_pb = remote_api_pb.Request()
    request_pb.set_service_name(service)
    request_pb.set_method(call)
    request_pb.mutable_request().set_contents(request.Encode())

    response_pb = remote_api_pb.Response()
    response_pb.ParseFromString(self._server.Send(self._path,
                                                  request_pb.Encode()))

    if response_pb.has_exception():
      raise pickle.loads(response_pb.exception().contents())
    else:
      response.ParseFromString(response_pb.response().contents())


class RemoteDatastoreStub(RemoteStub):
  """A specialised stub for accessing the App Engine datastore remotely.

  A specialised stub is required because there are some datastore operations
  that preserve state between calls. This stub makes queries possible.
  Transactions on the remote datastore are unfortunately still impossible.
  """

  def __init__(self, server, path):
    super(RemoteDatastoreStub, self).__init__(server, path)
    self.__queries = {}
    self.__transactions = {}

    self.__next_local_cursor = 1
    self.__local_cursor_lock = threading.Lock()
    self.__next_local_tx = 1
    self.__local_tx_lock = threading.Lock()

  def MakeSyncCall(self, service, call, request, response):
    assert service == 'datastore_v3'

    explanation = []
    assert request.IsInitialized(explanation), explanation

    handler = getattr(self, '_Dynamic_' + call, None)
    if handler:
      handler(request, response)
    else:
      super(RemoteDatastoreStub, self).MakeSyncCall(service, call, request,
                                                    response)

    assert response.IsInitialized(explanation), explanation

  def _Dynamic_RunQuery(self, query, query_result):
    self.__local_cursor_lock.acquire()
    try:
      cursor_id = self.__next_local_cursor
      self.__next_local_cursor += 1
    finally:
      self.__local_cursor_lock.release()
    self.__queries[cursor_id] = query

    query_result.mutable_cursor().set_cursor(cursor_id)
    query_result.set_more_results(True)

  def _Dynamic_Next(self, next_request, query_result):
    cursor = next_request.cursor().cursor()
    if cursor not in self.__queries:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'Cursor %d not found' % cursor)
    query = self.__queries[cursor]

    if query is None:
      query_result.set_more_results(False)
      return

    request = datastore_pb.Query()
    request.CopyFrom(query)
    if request.has_limit():
      request.set_limit(min(request.limit(), next_request.count()))
    else:
      request.set_limit(next_request.count())

    super(RemoteDatastoreStub, self).MakeSyncCall(
        'remote_datastore', 'RunQuery', request, query_result)

    query.set_offset(query.offset() + query_result.result_size())
    if query.has_limit():
      query.set_limit(query.limit() - query_result.result_size())
    if not query_result.more_results():
      self.__queries[cursor] = None

  def _Dynamic_Get(self, get_request, get_response):
    txid = None
    if get_request.has_transaction():
      txid = get_request.transaction().handle()
      txdata = self.__transactions[txid]
      assert (txdata.thread_id == thread.get_ident(),
              "Transactions are single-threaded.")

      keys = [(k, k.Encode()) for k in get_request.key_list()]

      new_request = datastore_pb.GetRequest()
      for key, enckey in keys:
        if enckey not in txdata.entities:
          new_request.add_key().CopyFrom(key)
    else:
      new_request = get_request

    if new_request.key_size() > 0:
      super(RemoteDatastoreStub, self).MakeSyncCall(
          'datastore_v3', 'Get', new_request, get_response)

    if txid is not None:
      newkeys = new_request.key_list()
      entities = get_response.entity_list()
      for key, entity in zip(newkeys, entities):
        entity_hash = None
        if entity.has_entity():
          entity_hash = sha.new(entity.entity().Encode()).digest()
        txdata.preconditions[key.Encode()] = (key, entity_hash)

      new_response = datastore_pb.GetResponse()
      it = iter(get_response.entity_list())
      for key, enckey in keys:
        if enckey in txdata.entities:
          cached_entity = txdata.entities[enckey][1]
          if cached_entity:
            new_response.add_entity().mutable_entity().CopyFrom(cached_entity)
          else:
            new_response.add_entity()
        else:
          new_entity = it.next()
          if new_entity.has_entity():
            assert new_entity.entity().key() == key
            new_response.add_entity().CopyFrom(new_entity)
          else:
            new_response.add_entity()
      get_response.CopyFrom(new_response)

  def _Dynamic_Put(self, put_request, put_response):
    if put_request.has_transaction():
      entities = put_request.entity_list()

      requires_id = lambda x: x.id() == 0 and not x.has_name()
      new_ents = [e for e in entities
                  if requires_id(e.key().path().element_list()[-1])]
      id_request = remote_api_pb.PutRequest()
      if new_ents:
        for ent in new_ents:
          e = id_request.add_entity()
          e.mutable_key().CopyFrom(ent.key())
          e.mutable_entity_group()
        id_response = datastore_pb.PutResponse()
        super(RemoteDatastoreStub, self).MakeSyncCall(
            'remote_datastore', 'GetIDs', id_request, id_response)
        assert id_request.entity_size() == id_response.key_size()
        for key, ent in zip(id_response.key_list(), new_ents):
          ent.mutable_key().CopyFrom(key)
          ent.mutable_entity_group().add_element().CopyFrom(
              key.path().element(0))

      txid = put_request.transaction().handle()
      txdata = self.__transactions[txid]
      assert (txdata.thread_id == thread.get_ident(),
              "Transactions are single-threaded.")
      for entity in entities:
        txdata.entities[entity.key().Encode()] = (entity.key(), entity)
        put_response.add_key().CopyFrom(entity.key())
    else:
      super(RemoteDatastoreStub, self).MakeSyncCall(
          'datastore_v3', 'Put', put_request, put_response)

  def _Dynamic_Delete(self, delete_request, response):
    if delete_request.has_transaction():
      txid = delete_request.transaction().handle()
      txdata = self.__transactions[txid]
      assert (txdata.thread_id == thread.get_ident(),
              "Transactions are single-threaded.")
      for key in delete_request.key_list():
        txdata.entities[key.Encode()] = (key, None)
    else:
      super(RemoteDatastoreStub, self).MakeSyncCall(
          'datastore_v3', 'Delete', delete_request, response)

  def _Dynamic_BeginTransaction(self, request, transaction):
    self.__local_tx_lock.acquire()
    try:
      txid = self.__next_local_tx
      self.__transactions[txid] = TransactionData(thread.get_ident())
      self.__next_local_tx += 1
    finally:
      self.__local_tx_lock.release()
    transaction.set_handle(txid)

  def _Dynamic_Commit(self, transaction, transaction_response):
    txid = transaction.handle()
    if txid not in self.__transactions:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Transaction %d not found.' % (txid,))

    txdata = self.__transactions[txid]
    assert (txdata.thread_id == thread.get_ident(),
            "Transactions are single-threaded.")
    del self.__transactions[txid]

    tx = remote_api_pb.TransactionRequest()
    for key, hash in txdata.preconditions.values():
      precond = tx.add_precondition()
      precond.mutable_key().CopyFrom(key)
      if hash:
        precond.set_hash(hash)

    puts = tx.mutable_puts()
    deletes = tx.mutable_deletes()
    for key, entity in txdata.entities.values():
      if entity:
        puts.add_entity().CopyFrom(entity)
      else:
        deletes.add_key().CopyFrom(key)

    super(RemoteDatastoreStub, self).MakeSyncCall(
        'remote_datastore', 'Transaction',
        tx, datastore_pb.PutResponse())

  def _Dynamic_Rollback(self, transaction, transaction_response):
    txid = transaction.handle()
    self.__local_tx_lock.acquire()
    try:
      if txid not in self.__transactions:
        raise apiproxy_errors.ApplicationError(
            datastore_pb.Error.BAD_REQUEST,
            'Transaction %d not found.' % (txid,))

      assert (txdata[txid].thread_id == thread.get_ident(),
              "Transactions are single-threaded.")
      del self.__transactions[txid]
    finally:
      self.__local_tx_lock.release()

  def _Dynamic_CreateIndex(self, index, id_response):
    raise apiproxy_errors.CapabilityDisabledError(
        'The remote datastore does not support index manipulation.')

  def _Dynamic_UpdateIndex(self, index, void):
    raise apiproxy_errors.CapabilityDisabledError(
        'The remote datastore does not support index manipulation.')

  def _Dynamic_DeleteIndex(self, index, void):
    raise apiproxy_errors.CapabilityDisabledError(
        'The remote datastore does not support index manipulation.')


def ConfigureRemoteDatastore(app_id, path, auth_func, servername=None):
  """Does necessary setup to allow easy remote access to an AppEngine datastore.

  Args:
    app_id: The app_id of your app, as declared in app.yaml.
    path: The path to the remote_api handler for your app
      (for example, '/remote_api').
    auth_func: A function that takes no arguments and returns a
      (username, password) tuple. This will be called if your application
      requires authentication to access the remote_api handler (it should!)
      and you do not already have a valid auth cookie.
    servername: The hostname your app is deployed on. Defaults to
      <app_id>.appspot.com.
  """
  if not servername:
    servername = '%s.appspot.com' % (app_id,)
  os.environ['APPLICATION_ID'] = app_id
  apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
  server = appengine_rpc.HttpRpcServer(servername, auth_func, GetUserAgent(),
                                       GetSourceName())
  stub = RemoteDatastoreStub(server, path)
  apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', stub)
