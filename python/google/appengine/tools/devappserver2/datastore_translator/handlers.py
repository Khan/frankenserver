"""Handlers for the REST APIs.

This includes the toplevel translation logic for each RPC, although common
parts are generally extracted out to separate files.
"""
from __future__ import absolute_import

import json
import logging
import os

import webapp2
import google.protobuf.json_format

from google.appengine.api import datastore
from google.appengine.tools.devappserver2.datastore_translator import grpc
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_key)
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_entity)
from google.appengine.tools.devappserver2.datastore_translator import run_query
# Amusingly, there is no legal way to wrap the following line:
from google.appengine.tools.devappserver2.datastore_translator.genproto import datastore_pb2  # noqa: E501


class Ping(webapp2.RequestHandler):
  """Handler that returns a simple 200, as a health check."""
  def get(self):
    self.response.status_int = 200
    self.response.content_type = 'text/plain'
    self.response.write('Ok')


def _fix_up_for_proto(serializable):
  """Fix up special cases in the JSON-to-protobuf translation.

  The protobuf-over-HTTP API actually used by REST clients and the documented
  JSON-over-HTTP API are mostly a straightforward translation using protobuf's
  json_format.  However, they are not identical (and sadly any differences are
  not documented explicitly, although they can be inferred by comparing the
  documentation to the proto files -- see genproto/README.md).  This function
  fixes up a JSON-serializable response in the style of the documented API
  in-place into something that is ready to convert to protobuf.

  At present, the only known difference is in the handling of the Value struct
  when it represents null.  This is represented in JSON as
    {"nullValue": null}
  and in protobuf as a protobuf NullValue, which in JSON looks like
    {"nullValue": "NULL_VALUE"}
  Additionally, errors are represented differently, but this is handled
  separately.

  TODO(benkraft): Eventually, we may need a reverse to this function
  that does the opposite conversion; right now we just handle it in
  translate_value.py.
  """
  if isinstance(serializable, dict):
    if 'nullValue' in serializable:
      serializable['nullValue'] = 'NULL_VALUE'

    map(_fix_up_for_proto, serializable.values())  # fix descendants
  elif isinstance(serializable, list):
    map(_fix_up_for_proto, serializable)


class _DatastoreApiHandlerBase(webapp2.RequestHandler):
  """Base handler for Datastore REST API requests.

  Handlers should subclass this, and implement json_post, which should accept
  and return JSON (or may raise grpc.Error).

  NOTE(benkraft): The JSON is a lie!  Our code is structured as to match the
  JSON-over-HTTP REST API documented at:
      https://cloud.google.com/datastore/docs/reference/data/rest/
  However, the actual Google Cloud clients, when they say "HTTP", really mean
  they implement a REST-like protobuf-over-HTTP API similar to the
  above-documented one (more information about the protos is in
  genproto/README.md).  The difference is mostly just the standard protobuf
  json_format translation (but see _fix_up_for_proto above for differences in
  the data semantics, and grpc.Error for the differences in the error
  semantics).  This class also handles the translation between those two, such
  that we can accept either JSON as documented or protobufs as implemented.
  """
  def json_post(self, project_id, json_input):
    """Extension point for subclasses to implement their logic.

    This will be called (with project_id as the project ID and json_input as
    the POST data parsed from JSON.  It should return a JSON-serializable
    response, or call self.error() and return nothing.
    """
    raise NotImplementedError("Subclasses must implement!")

  # Subclasses must override these to the correct protobuf message types (from
  # datastore_pb2.py).
  REQUEST_MESSAGE = None
  RESPONSE_MESSAGE = None

  def post(self, project_id):
    content_type = self.request.headers.get('content-type')
    try:
      # Check the content type, deserialize the request, and set the response
      # content type to match.
      if content_type == 'application/x-protobuf':
        self.response.content_type = content_type
        # For reasons that are surely beyond me, the Java Datastore client
        # can't handle errors with a charset set, so we explicitly clear it.
        # (Non-error responses work fine with the charset, as far as I can
        # tell, but it's not necessary so we just omit it.)
        self.response.charset = None
        try:
          message = self.REQUEST_MESSAGE()
          message.MergeFromString(self.request.body)
          json_input = google.protobuf.json_format.MessageToDict(message)
        except Exception as e:
          raise grpc.Error("INVALID_ARGUMENT", "Invalid %s: %s"
                           % (self.REQUEST_MESSAGE.__name__, e))

      elif content_type == 'application/json':
        self.response.content_type = content_type
        try:
          json_input = json.loads(self.request.body)
        except Exception as e:
          raise grpc.Error("INVALID_ARGUMENT", "Invalid JSON: %s" % e)

      elif not content_type:
        self.response.content_type = 'application/json'  # good enough, we hope
        raise grpc.Error("INVALID_ARGUMENT", "Missing content-type.")
      else:
        self.response.content_type = 'application/json'  # good enough, we hope
        raise grpc.Error("INVALID_ARGUMENT", "Invalid content-type %s."
                         % content_type)

      # Check that the project IDs match (up to dev~ which devappserver adds).
      devappserver_project_id = os.environ.get('APPLICATION_ID')
      if 'dev~%s' % project_id != devappserver_project_id:
        raise grpc.Error("INVALID_ARGUMENT",
                         "requested project ID %s does not match "
                         "devappserver's project ID %s" % (
                             project_id, devappserver_project_id))

      # Now, actually handle the request, and serialize the response.
      try:
        self.response.status_int = 200
        json_output = self.json_post(project_id, json_input)
        if content_type == 'application/x-protobuf':
          _fix_up_for_proto(json_output)
          message = self.RESPONSE_MESSAGE()
          google.protobuf.json_format.Parse(json.dumps(json_output), message)
          self.response.write(message.SerializeToString())
        else:
          json.dump(json_output, self.response)
      except grpc.Error:
        raise
      except KeyError as e:   # a common case, we just guess it's a bad request
        raise grpc.Error("INVALID_ARGUMENT",
                         "Invalid request: missing key %s." % e)
      except ValueError as e:  # similarly
        raise grpc.Error("INVALID_ARGUMENT", "Invalid request: %s." % e)
      except Exception as e:
        # In this case, it's useful to log the full stacktrace.
        logging.exception(e)
        raise grpc.Error("UNKNOWN", "Internal server error: %s" % e)

    except grpc.Error as e:
      self.response.status_int = e.http_code

      if e.http_code >= 500:
        logging.error(e)
      else:
        logging.debug(e)

      # The JSON and proto APIs serialize errors somewhat differently; see
      # grpc.Error for the structure of each.
      if content_type == 'application/x-protobuf':
        self.response.write(e.as_proto().SerializeToString())
      else:
        json.dump(e.as_json_serializable(), self.response)


class AllocateIds(_DatastoreApiHandlerBase):
  """Translate the REST allocateIds call (to App Engine's AllocateIds)."""
  REQUEST_MESSAGE = datastore_pb2.AllocateIdsRequest
  RESPONSE_MESSAGE = datastore_pb2.AllocateIdsResponse

  def json_post(self, project_id, json_input):
    keys = json_input.get('keys')
    if not keys:
      # Strangely, the API returns an empty OK if .keys is missing or empty.
      return {}

    returned_keys = []
    for key in keys:
      gae_key = translate_key.rest_to_gae(key, project_id, incomplete=True)

      # The REST API is structured such that you pass a bunch of incomplete
      # keys; in App Engine instead you pass a single incomplete key and a
      # count of how big a range you'd like.  (Note the returned range is
      # inclusive.)
      # TODO(benkraft): Do these requests async (if there are multiple).
      # (This may require making the tests depend on ordering less.)
      start, end = datastore.AllocateIds(gae_key, size=1)
      if end < start:
        # Check that we got back an allocation!  This should "never" happen.
        raise grpc.Error("INTERNAL", "Unable to allocate IDs.")

      # Sadly, there's no documented way to modify a datastore key in place.
      # We do it anyway -- copying would be a bunch more work.  (This is just
      # setting the id of the last element of the key-path.)
      gae_key._Key__reference.path().element(-1).set_id(start)

      returned_keys.append(translate_key.gae_to_rest(gae_key))
    return {'keys': returned_keys}


_CONSISTENCIES = {
  None: None,
  "EVENTUAL": datastore.EVENTUAL_CONSISTENCY,
  "STRONG": datastore.STRONG_CONSISTENCY,
}


def _parse_read_options(rest_options):
  """Parse REST-style read options.

  Returns: a datastore read policy (e.g. datastore.STRONG_CONSISTENCY, or None)
  """
  if not rest_options:
    return None

  if rest_options.pop('transaction', None):
    raise grpc.Error('UNIMPLEMENTED',
                     'TODO(benkraft): Implement transactions.')

  rest_consistency = rest_options.pop('readConsistency', None)
  if rest_consistency not in _CONSISTENCIES:
    raise grpc.Error('INVALID_ARGUMENT',
                     'Invalid consistency %s' % rest_consistency)
  gae_consistency = _CONSISTENCIES[rest_consistency]

  # We should have handled all options by now.
  if rest_options:
    raise grpc.Error('INVALID_ARGUMENT',
                     'Invalid options: %s' % ', '.join(rest_options))

  return gae_consistency


class Lookup(_DatastoreApiHandlerBase):
  """Translate the REST lookup call (to App Engine's Get)."""
  REQUEST_MESSAGE = datastore_pb2.LookupRequest
  RESPONSE_MESSAGE = datastore_pb2.LookupResponse

  def json_post(self, project_id, json_input):
    keys = json_input.get('keys')
    if not keys:
      # Strangely, the API returns an empty OK if .keys is missing or empty.
      return {}

    # I'm not sure if consistency does anything for gets (especially in dev),
    # but it's legal in both REST and GAE so we may as well pass it through.
    consistency = _parse_read_options(json_input.get('readOptions'))

    datastore_keys = [translate_key.rest_to_gae(key, project_id)
                      for key in keys]
    datastore_entities = datastore.Get(datastore_keys,
                                       read_policy=consistency)

    retval = {}

    found = [
      translate_entity.gae_to_rest_entity_result(entity)
      for entity in datastore_entities
      if entity is not None]
    if found:
      retval['found'] = found

    missing = [translate_entity.gae_key_to_rest_entity_result(key)
               for key, entity in zip(datastore_keys, datastore_entities)
               if entity is None]
    if missing:
      retval['missing'] = missing

    return retval


class RunQuery(_DatastoreApiHandlerBase):
  """Translate the REST runQuery call (to App Engine's Query)."""
  REQUEST_MESSAGE = datastore_pb2.RunQueryRequest
  RESPONSE_MESSAGE = datastore_pb2.RunQueryResponse

  def json_post(self, project_id, json_input):
    namespace = translate_key.rest_partition_to_gae_namespace(
      json_input.get('partitionId'), project_id=project_id)
    consistency = _parse_read_options(json_input.get('readOptions'))

    if 'gqlQuery' in json_input:
      # Note that implementing GQL may not be too hard -- most of what we need
      # is already in google.appengine.ext.gql.  But there's no need right now.
      raise grpc.Error('UNIMPLEMENTED', 'TODO(benkraft): Implement GQL.')

    batch = run_query.translate_and_execute(
      json_input['query'], namespace, consistency)

    return {'batch': batch}
