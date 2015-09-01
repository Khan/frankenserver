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



"""Implementation of the Cloud Datastore V1 API.

This implementation forwards directly to the v3 service."""













from google.appengine.datastore import entity_pb

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_rpc
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_pbs
from google.appengine.datastore import datastore_query
from google.appengine.datastore import datastore_stub_util
from google.appengine.datastore import cloud_datastore_validator
from google.appengine.runtime import apiproxy_errors

_CLOUD_DATASTORE_ENABLED = datastore_pbs._CLOUD_DATASTORE_ENABLED
if _CLOUD_DATASTORE_ENABLED:
  from datastore_pbs import googledatastore

SERVICE_NAME = 'cloud_datastore_v1'
V3_SERVICE_NAME = 'datastore_v3'


class _StubIdResolver(datastore_pbs.IdResolver):
  """A IdResolver that converts all project_ids to dev~project_id.

  Users can provide a list of app_ids to override the conversions.
  """

  def __init__(self, app_ids=None):
    """Create a _StubIdResolver.

    Optionally, can provide a list of application ids.
    """
    super(_StubIdResolver, self).__init__(app_ids)

  def resolve_app_id(self, project_id):
    """Resolve the project id. Defaults to dev~project_id."""
    try:
      return super(_StubIdResolver, self).resolve_app_id(project_id)
    except datastore_pbs.InvalidConversionError:
      return 'dev~%s' % project_id


class CloudDatastoreV1Stub(apiproxy_stub.APIProxyStub):
  """Implementation of the Cloud Datastore V1 API.

  This proxies requests to the v3 service."""


  THREADSAFE = False

  def __init__(self, app_id):
    assert _CLOUD_DATASTORE_ENABLED, (
        'Cannot initialize the Cloud Datastore'
        ' stub without installing the Cloud'
        ' Datastore client libraries.')
    apiproxy_stub.APIProxyStub.__init__(self, SERVICE_NAME)
    self.__app_id = app_id
    id_resolver = _StubIdResolver([app_id])
    self.__entity_converter = datastore_pbs.get_entity_converter(
        id_resolver)
    self.__service_converter = datastore_stub_util.get_service_converter(
        id_resolver)
    self.__service_validator = cloud_datastore_validator.get_service_validator()

  def _Dynamic_BeginTransaction(self, req, resp):


    try:
      self.__service_validator.validate_begin_transaction_req(req)
      v3_req = self.__service_converter.v1_to_v3_begin_transaction_req(
          self.__app_id, req)
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))
    except cloud_datastore_validator.ValidationError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))
    v3_resp = datastore_pb.Transaction()
    self.__make_v3_call('BeginTransaction', v3_req, v3_resp)

    try:
      v1_resp = self.__service_converter.v3_to_v1_begin_transaction_resp(
          v3_resp)
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.INTERNAL_ERROR,
                                             str(e))
    resp.CopyFrom(v1_resp)

  def _Dynamic_Rollback(self, req, unused_resp):


    try:
      self.__service_validator.validate_rollback_req(req)
      v3_req = self.__service_converter.v1_rollback_req_to_v3_txn(req)
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))
    except cloud_datastore_validator.ValidationError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))

    self.__make_v3_call('Rollback', v3_req, api_base_pb.VoidProto())


  def _Dynamic_Commit(self, req, resp):


    try:
      self.__service_validator.validate_commit_req(req)
    except cloud_datastore_validator.ValidationError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))
    try:
      txn = None
      if req.transaction:
        txn = req.transaction
      total_index_writes = 0
      for mutation in req.mutations:
        mutation_result, index_writes = (
            self.__apply_v1_mutation(mutation, req.transaction))
        resp.mutation_results.add().CopyFrom(mutation_result)
        total_index_writes += index_writes
      if txn:
        v3_req = self.__service_converter.v1_commit_req_to_v3_txn(req)
        v3_resp = datastore_pb.CommitResponse()
        self.__make_v3_call('Commit', v3_req, v3_resp)
        total_index_writes += v3_resp.cost().index_writes()
      resp.index_updates = total_index_writes
    except datastore_pbs.InvalidConversionError, e:


      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))


  def _Dynamic_RunQuery(self, req, resp):


    self.__normalize_v1_run_query_request(req)
    try:
      self.__service_validator.validate_run_query_req(req)
      v3_req = self.__service_converter.v1_run_query_req_to_v3_query(req)
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))
    except cloud_datastore_validator.ValidationError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))

    v3_resp = datastore_pb.QueryResult()
    self.__make_v3_call('RunQuery', v3_req, v3_resp)

    try:
      v1_resp = self.__service_converter.v3_to_v1_run_query_resp(v3_resp)
      if req.query.projection:
        if (len(req.query.projection) == 1 and
            req.query.projection[0].property.name == '__key__'):
          result_type = googledatastore.EntityResult.KEY_ONLY
        else:
          result_type = googledatastore.EntityResult.PROJECTION
        v1_resp.batch.entity_result_type = result_type
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.INTERNAL_ERROR, str(e))
    resp.CopyFrom(v1_resp)

  def _Dynamic_Lookup(self, req, resp):


    try:
      self.__service_validator.validate_lookup_req(req)
      v3_req = self.__service_converter.v1_to_v3_get_req(req)
    except cloud_datastore_validator.ValidationError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))

    v3_resp = datastore_pb.GetResponse()
    self.__make_v3_call('Get', v3_req, v3_resp)

    try:
      v1_resp = self.__service_converter.v3_to_v1_lookup_resp(v3_resp)
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.INTERNAL_ERROR,
                                             str(e))
    resp.CopyFrom(v1_resp)

  def _Dynamic_AllocateIds(self, req, resp):






    v3_stub = apiproxy_stub_map.apiproxy.GetStub(V3_SERVICE_NAME)
    v3_refs = None
    try:
      self.__service_validator.validate_allocate_ids_req(req)
      if req.keys:
        v3_refs = self.__entity_converter.v1_to_v3_references(req.keys)
    except cloud_datastore_validator.ValidationError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             str(e))
    if v3_refs:
      v3_full_refs = v3_stub._AllocateIds(v3_refs)
      try:
        resp.keys.extend(
            self.__entity_converter.v3_to_v1_keys(v3_full_refs))
      except datastore_pbs.InvalidConversionError, e:
        raise apiproxy_errors.ApplicationError(
            datastore_pb.Error.INTERNAL_ERROR, str(e))


  def __insert_v3_entity(self, v3_entity, v3_txn):
    """Inserts a v3 entity.

    Args:
      v3_entity: an entity_pb.EntityProto
      v3_txn: a datastore_pb.Transaction or None

    Returns:
      a tuple (the number of index writes that occurred,
               the entity key)

    Raises:
      ApplicationError: if the entity already exists
    """
    if not v3_txn:

      v3_txn = datastore_pb.Transaction()
      v3_begin_txn_req = datastore_pb.BeginTransactionRequest()
      v3_begin_txn_req.set_app(v3_entity.key().app())
      self.__make_v3_call('BeginTransaction', v3_begin_txn_req, v3_txn)
      _, key = self.__insert_v3_entity(v3_entity, v3_txn)
      v3_resp = datastore_pb.CommitResponse()
      self.__make_v3_call('Commit', v3_txn, v3_resp)
      return (v3_resp.cost().index_writes(), key)

    if datastore_pbs.is_complete_v3_key(v3_entity.key()):
      v3_get_req = datastore_pb.GetRequest()
      v3_get_req.mutable_transaction().CopyFrom(v3_txn)
      v3_get_req.key_list().append(v3_entity.key())
      v3_get_resp = datastore_pb.GetResponse()
      self.__make_v3_call('Get', v3_get_req, v3_get_resp)
      if v3_get_resp.entity(0).has_entity():
        raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                               'Entity already exists.')
    v3_put_req = datastore_pb.PutRequest()
    v3_put_req.mutable_transaction().CopyFrom(v3_txn)
    v3_put_req.entity_list().append(v3_entity)
    v3_put_resp = datastore_pb.PutResponse()
    self.__make_v3_call('Put', v3_put_req, v3_put_resp)
    return (v3_put_resp.cost().index_writes(),
            v3_put_resp.key(0))

  def __update_v3_entity(self, v3_entity, v3_txn):
    """Updates a v3 entity.

    Args:
      v3_entity: an entity_pb.EntityProto
      v3_txn: a datastore_pb.Transaction or None

    Returns:
      the number of index writes that occurred

    Raises:
      ApplicationError: if the entity does not exist
    """
    if not v3_txn:

      v3_txn = datastore_pb.Transaction()
      v3_begin_txn_req = datastore_pb.BeginTransactionRequest()
      v3_begin_txn_req.set_app(v3_entity.key().app())
      self.__make_v3_call('BeginTransaction', v3_begin_txn_req, v3_txn)
      self.__update_v3_entity(v3_entity, v3_txn)
      v3_resp = datastore_pb.CommitResponse()
      self.__make_v3_call('Commit', v3_txn, v3_resp)
      return v3_resp.cost().index_writes()

    v3_get_req = datastore_pb.GetRequest()
    v3_get_req.mutable_transaction().CopyFrom(v3_txn)
    v3_get_req.key_list().append(v3_entity.key())
    v3_get_resp = datastore_pb.GetResponse()
    self.__make_v3_call('Get', v3_get_req, v3_get_resp)
    if not v3_get_resp.entity(0).has_entity():
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'Entity does not exist.')
    v3_put_req = datastore_pb.PutRequest()
    v3_put_req.mutable_transaction().CopyFrom(v3_txn)
    v3_put_req.entity_list().append(v3_entity)
    v3_put_resp = datastore_pb.PutResponse()
    self.__make_v3_call('Put', v3_put_req, v3_put_resp)
    return v3_put_resp.cost().index_writes()

  def __upsert_v3_entity(self, v3_entity, v3_txn):
    """Upsert a v3 entity.

    Args:
      v3_entity: an entity_pb.EntityProto
      v3_txn: a datastore_pb.Transaction or None

    Returns:
      a tuple (the number of index writes that occurred,
               the key of the entity)
    """
    v3_put_req = datastore_pb.PutRequest()
    if v3_txn:
      v3_put_req.mutable_transaction().CopyFrom(v3_txn)
    v3_put_req.entity_list().append(v3_entity)
    v3_put_resp = datastore_pb.PutResponse()
    self.__make_v3_call('Put', v3_put_req, v3_put_resp)
    return (v3_put_resp.cost().index_writes(),
            v3_put_resp.key(0))

  def __delete_v3_reference(self, v3_key, v3_txn):
    """Deletes a v3 entity.

    Args:
      v3_key: an entity_pb.Reference
      v3_txn: a datastore_pb.Transaction or None

    Returns:
      the number of index writes that occurred
    """
    v3_delete_req = datastore_pb.DeleteRequest()
    if v3_txn:
      v3_delete_req.mutable_transaction().CopyFrom(v3_txn)
    v3_delete_req.add_key().CopyFrom(v3_key)
    v3_delete_resp = datastore_pb.DeleteResponse()
    self.__make_v3_call('Delete', v3_delete_req, v3_delete_resp)
    return v3_delete_resp.cost().index_writes()

  def __apply_v1_mutation(self, v1_mutation, v1_txn):
    """Applies a v1 Mutation.

    Args:
      v1_mutation: a googledatastore.Mutation
      v1_txn: an optional v1 transaction handle or None

    Returns:
     a tuple (googledatastore.MutationResult, number of index writes)
    """
    v3_txn = None
    v3_key = None
    if v1_txn:
      v3_txn = datastore_pb.Transaction()
      self.__service_converter.v1_to_v3_txn(v1_txn, v3_txn)


    if v1_mutation.HasField('insert'):
      v3_entity = entity_pb.EntityProto()
      v1_entity = v1_mutation.insert
      self.__entity_converter.v1_to_v3_entity(v1_entity, v3_entity)
      index_writes, v3_key = self.__insert_v3_entity(v3_entity, v3_txn)


    elif v1_mutation.HasField('update'):
      v3_entity = entity_pb.EntityProto()
      self.__entity_converter.v1_to_v3_entity(v1_mutation.update,
                                              v3_entity)
      index_writes = self.__update_v3_entity(v3_entity, v3_txn)


    elif v1_mutation.HasField('upsert'):
      v3_entity = entity_pb.EntityProto()
      v1_entity = v1_mutation.upsert
      self.__entity_converter.v1_to_v3_entity(v1_entity, v3_entity)
      index_writes, v3_key = self.__upsert_v3_entity(v3_entity, v3_txn)


    elif v1_mutation.HasField('delete'):
      v3_ref = entity_pb.Reference()
      self.__entity_converter.v1_to_v3_reference(v1_mutation.delete,
                                                 v3_ref)
      index_writes = self.__delete_v3_reference(v3_ref, v3_txn)

    v1_mutation_result = googledatastore.MutationResult()
    if v3_key and not datastore_pbs.is_complete_v1_key(v1_entity.key):
      self.__entity_converter.v3_to_v1_key(v3_key, v1_mutation_result.key)
    return v1_mutation_result, index_writes

  def __normalize_v1_run_query_request(self, v1_req):

    pass

  def __make_v3_call(self, method, v3_req, v3_resp):
    apiproxy_stub_map.MakeSyncCall(V3_SERVICE_NAME, method, v3_req, v3_resp)
