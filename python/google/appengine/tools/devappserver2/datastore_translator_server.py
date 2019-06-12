"""Accepts datastore v1 REST API requests, translating them to App Engine RPCs.

This allows other applications -- those not written for App Engine (or written
for Second Gen runtimes) -- to talk to the App Engine datastore stub using the
new (v1) public REST API.  (See below for what "REST" here means.)

It's intended to serve a similar purpose to the Google Cloud Datastore
Emulator, but by building on the old sqlite stub it can handle a lot more data
without trouble.  (Khan folks, see ADR #166 for details.)

Most of the work here was actually done by Google, who implemented the
cloud_datastore_v1_stub that handles the translation.  But they never wired it
up to anything -- I guess they decided to write the emulator instead.  So we
just had to wire it up (and fix a few bugs).

The datastore v1 API exists in three forms:
- gRPC, as documented at
    https://cloud.google.com/datastore/docs/reference/data/rpc/
- JSON-over-HTTP (referred to as "REST" in the documentation), as documented at
    https://cloud.google.com/datastore/docs/reference/data/rest/
- protobuf-over-HTTP, using the same protos as the gRPC form, but over an
  HTTP/1.1 transport.

The official clients always implement protobuf-over-HTTP, and in many cases
also gRPC; we implement JSON-over-HTTP (which is the easiest for humans to
debug) and protobuf-over-HTTP (for the clients).  (We can't implement
JSON-over-HTTP because we can't easily accept HTTP/2 or any other gRPC
transport from within dev_appserver.)  The datastore v1 stub to which we
delegate uses the protobuf form of the APIs, but wired up to an App Engine
style stub.

For the most part, the JSON API is a straightfoward translation of the gRPC
protobufs using the protobuf json_format.  There are a few differences, which
can be determined by comparing the documentation to the proto files at
  https://github.com/googleapis/googleapis/tree/master/google/datastore/v1
The two known differences are in the representation of nulls (see
_fix_up_json_result below) and errors (see GrpcError).
"""
from __future__ import absolute_import

import collections
import json
import logging
import os

from google.protobuf import json_format
from googledatastore.genproto import code_pb2
from googledatastore.genproto import datastore_pb2
from googledatastore.genproto import status_pb2
import webapp2

from google.appengine.api import apiproxy_stub_map
from google.appengine.datastore import cloud_datastore_v1_stub
from google.appengine.datastore import datastore_v3_pb
from google.appengine.runtime import apiproxy_errors
from google.appengine.tools.devappserver2 import wsgi_server

_GRPC_CODE_TO_HTTP_STATUS = {
  # Copied from, and further documented at
  # https://github.com/grpc/grpc/blob/master/doc/statuscodes.md
  'OK': 200,
  'CANCELLED': 499,
  'UNKNOWN': 500,
  'INVALID_ARGUMENT': 400,
  'DEADLINE_EXCEEDED': 504,
  'NOT_FOUND': 404,
  'ALREADY_EXISTS': 409,
  'PERMISSION_DENIED': 403,
  'UNAUTHENTICATED': 401,
  'RESOURCE_EXHAUSTED': 429,
  'FAILED_PRECONDITION': 400,
  'ABORTED': 409,
  'OUT_OF_RANGE': 400,
  'UNIMPLEMENTED': 501,
  'INTERNAL': 500,
  'UNAVAILABLE': 503,
  'DATA_LOSS': 500,
}

_DATASTORE_ERROR_TO_GRPC_STATUS = {
  datastore_v3_pb.Error.BAD_REQUEST: 'INVALID_ARGUMENT',
  datastore_v3_pb.Error.CONCURRENT_TRANSACTION: 'ABORTED',
  datastore_v3_pb.Error.INTERNAL_ERROR: 'INTERNAL',
  datastore_v3_pb.Error.NEED_INDEX: 'FAILED_PRECONDITION',
  datastore_v3_pb.Error.TIMEOUT: 'DEADLINE_EXCEEDED',
  datastore_v3_pb.Error.PERMISSION_DENIED: 'PERMISSION_DENIED',
  datastore_v3_pb.Error.BIGTABLE_ERROR: 'INTERNAL',
  datastore_v3_pb.Error.RESOURCE_EXHAUSTED: 'RESOURCE_EXHAUSTED',
  datastore_v3_pb.Error.NOT_FOUND: 'NOT_FOUND',
  datastore_v3_pb.Error.ALREADY_EXISTS: 'ALREADY_EXISTS',
  datastore_v3_pb.Error.FAILED_PRECONDITION: 'FAILED_PRECONDITION',
  datastore_v3_pb.Error.UNAUTHENTICATED: 'UNAUTHENTICATED',
  datastore_v3_pb.Error.ABORTED: 'ABORTED',
}

_GRPC_CODE_TO_INT = dict(code_pb2.Code.items())
assert _GRPC_CODE_TO_INT.keys() == _GRPC_CODE_TO_HTTP_STATUS.keys()


class GrpcError(Exception):
  """Return an error to the user.

  These errors are in the style of gRPC, but we serialize them in two ways:
  into JSON (see as_json_serializable()) and into the Status proto (see
  as_proto()).  Unlike the rest of the API, these are not a simple json_format
  translation away.

  Note that while we format errors like prod, neither we nor the underlying
  stub attempt to match the error text exactly.  (In fact, even the official
  Google emulator doesn't match the prod API precisely!)  We just try to give
  something vaguely useful where we can.

  We also handle translation from the error semantics of the cloud_datastore_v1
  stub, which raises App Engine style apiproxy_errors.ApplicationErrors, using
  the status codes from datastore_v3_pb.Error; see from_application_error().

  Init Arguments:
    grpc_code (str): a GRPC status code (one of the keys from
        _GRPC_CODE_TO_HTTP_STATUS, above)
    message (str): a human readable error message
  """
  def __init__(self, grpc_code, message):
    super(GrpcError, self).__init__(message)
    if grpc_code in _GRPC_CODE_TO_HTTP_STATUS:
      self.grpc_code = grpc_code
    else:
      self.grpc_code = 'UNKNOWN'

  @property
  def http_code(self):
    return _GRPC_CODE_TO_HTTP_STATUS[self.grpc_code]

  @property
  def grpc_code_int(self):
    return _GRPC_CODE_TO_INT[self.grpc_code]

  def as_json_serializable(self):
    """Convert this error to its JSON-serializable form.

    Note that this does not really match the proto form -- use .as_proto()
    instead of converting this to a proto.

    TODO(benkraft): Include the "details" field as the real API does (e.g. for
    invalid keys in the JSON).
    """
    return {
      'error': {
        'code': self.http_code,
        'status': self.grpc_code,
        'message': self.message,
      }
    }

  def as_proto(self):
    """Convert this error to a status_pb2.Status proto."""
    message = status_pb2.Status()
    message.code = self.grpc_code_int
    message.message = self.message
    return message

  @classmethod
  def from_application_error(cls, e):
    """Convert an apiproxy_errors.ApplicationError to a GrpcError.

    The error should have an error code from datastore_v3_pb.Error.
    """
    grpc_status = _DATASTORE_ERROR_TO_GRPC_STATUS.get(
      e.application_error, 'UNKNOWN')
    return cls(grpc_status, e.error_detail)


class Ping(webapp2.RequestHandler):
  """Handler that returns a simple 200, as a health check."""
  def get(self):
    self.response.status_int = 200
    self.response.content_type = 'text/plain'
    self.response.write('Ok')


RestRpc = collections.namedtuple(
  'DatastoreV1Rpc',
  ['rest_name', 'rpc_name', 'request_class', 'response_class'])


_RPCS = [
  RestRpc('allocateIds', 'AllocateIds',
          datastore_pb2.AllocateIdsRequest,
          datastore_pb2.AllocateIdsResponse),
  RestRpc('beginTransaction', 'BeginTransaction',
          datastore_pb2.BeginTransactionRequest,
          datastore_pb2.BeginTransactionResponse),
  RestRpc('commit', 'Commit',
          datastore_pb2.CommitRequest,
          datastore_pb2.CommitResponse),
  RestRpc('lookup', 'Lookup',
          datastore_pb2.LookupRequest,
          datastore_pb2.LookupResponse),
  RestRpc('reserveIds', 'ReserveIds',
          datastore_pb2.ReserveIdsRequest,
          datastore_pb2.ReserveIdsResponse),
  RestRpc('rollback', 'Rollback',
          datastore_pb2.RollbackRequest,
          datastore_pb2.RollbackResponse),
  RestRpc('runQuery', 'RunQuery',
          datastore_pb2.RunQueryRequest,
          datastore_pb2.RunQueryResponse),
]

_RPCS_BY_REST_NAME = {rpc.rest_name: rpc for rpc in _RPCS}


def _fix_up_json_result(serializable):
  """Fix up special cases in the JSON-to-protobuf translation.

  As discussed in the file docstring, the protobuf-over-HTTP API actually used
  by REST clients and the documented JSON-over-HTTP API are mostly a
  straightforward translation using protobuf's json_format, but there are a few
  differences.  This fixes up a json_formatted protobuf response into the
  actual JSON returned by the API.

  At present, the only known difference (outside of errors) is in the handling
  of the Value struct when it represents null.  This is represented in JSON as
    {"nullValue": null}
  and in protobuf as a protobuf NullValue, which in json_format looks like
    {"nullValue": "NULL_VALUE"}

  TODO(benkraft): In principle we might need the inverse direction, but the
  datastore stub happens to handle the JSON-style null just fine, because it
  uses nullValue as the default case.
  """
  if isinstance(serializable, dict):
    if 'nullValue' in serializable:
      serializable['nullValue'] = None

    map(_fix_up_json_result, serializable.values())  # fix descendants
  elif isinstance(serializable, list):
    map(_fix_up_json_result, serializable)

  return serializable


class DatastoreTranslatorHandler(webapp2.RequestHandler):
  """A request handler that wires up the cloud_datastore_v1 stub to HTTP.

  This handler mostly just delegates to the stub (which must already be set
  up), and handles request and response serialization.  Most of the interesting
  bits relate to the translation between the different styles of API, as
  described in the file docstring.
  """

  def post(self, project_id, rest_name):
    content_type = self.request.headers.get('content-type')
    try:
      # Figure out which RPC this is.
      if rest_name not in _RPCS_BY_REST_NAME:
        raise GrpcError("NOT_FOUND", "RPC %s not found." % rest_name)
      _, rpc_name, request_class, response_class = (
        _RPCS_BY_REST_NAME[rest_name])

      # Check that the project IDs match (up to dev~ which devappserver adds).
      devappserver_project_id = os.environ.get('APPLICATION_ID')
      if 'dev~%s' % project_id != devappserver_project_id:
        raise GrpcError("INVALID_ARGUMENT",
                        "requested project ID %s does not match "
                        "devappserver's project ID %s" % (
                          project_id, devappserver_project_id))

      # Check the content type, and figure out how to (de)serialize it.
      if content_type == 'application/x-protobuf':
        def deserialize(body, into_proto):
          return into_proto.MergeFromString(body)

        def serialize(proto, write_func):
          write_func(proto.SerializeToString())

      elif content_type == 'application/json':
        def deserialize(body, into_proto):
          json_format.Parse(body, into_proto)

        def serialize(proto, write_func):
          write_func(
            json.dumps(_fix_up_json_result(json_format.MessageToDict(proto)),
                       indent=2))

      elif not content_type:
        raise GrpcError("INVALID_ARGUMENT", "Missing content-type.")
      else:
        raise GrpcError("INVALID_ARGUMENT", "Invalid content-type %s."
                        % content_type)

      # Now actually deserialize the request.
      try:
        request_proto = request_class()
        deserialize(self.request.body, request_proto)
      except Exception as e:
        raise GrpcError("INVALID_ARGUMENT", "Invalid %s: %s"
                        % (request_class.__name__, e))

      try:
        # Pass the request through to the stub.
        response_proto = response_class()
        apiproxy_stub_map.MakeSyncCall('cloud_datastore_v1', rpc_name,
                                       request_proto, response_proto)

        # Serialize the response.
        self.response.status_int = 200
        self.response.content_type = content_type
        serialize(response_proto, self.response.write)

      # If there was an error, convert it to a GrpcError.
      except apiproxy_errors.ApplicationError as e:
        raise GrpcError.from_application_error(e)
      except Exception as e:
        # In this case, it's useful to log the full stacktrace.
        logging.exception(e)
        raise GrpcError("UNKNOWN", "Internal server error: %s" % e)

    # Serialize an error anywhere in the process.
    except GrpcError as e:
      self.response.status_int = e.http_code

      if e.http_code >= 500:
        logging.error(e)
      else:
        logging.debug(e)

      # The JSON and proto APIs serialize errors somewhat differently; see
      # GrpcError for the structure of each.
      if content_type == 'application/x-protobuf':
        self.response.content_type = content_type
        # For reasons that are surely beyond me, the Java Datastore client
        # can't handle errors with a charset set, so we explicitly clear it.
        # (Non-error responses seem to work fine with the charset.)
        self.response.charset = None
        self.response.write(e.as_proto().SerializeToString())
      else:
        self.response.content_type = 'application/json'  # good enough, we hope
        json.dump(e.as_json_serializable(), self.response)


_ROUTES = [
    ('/', Ping),
    ('/v1/projects/([^/:]*):([^/:]*)', DatastoreTranslatorHandler),
]


def get_app(host=None, enable_host_checking=True):
  """Get the WSGI app.

  Only tests likely need this directly.  host is required if
  enable_host_checking is set (the default) and ignored otherwise.
  """
  # Set up the stub, which the app needs to run.
  cloud_stub = cloud_datastore_v1_stub.CloudDatastoreV1Stub(
    os.environ.get('APPLICATION_ID'))
  apiproxy_stub_map.apiproxy.RegisterStub(
    cloud_datastore_v1_stub.SERVICE_NAME, cloud_stub)

  # Set up the shim app.
  translator_app = webapp2.WSGIApplication(_ROUTES, debug=False)
  if enable_host_checking:
    translator_app = wsgi_server.WsgiHostCheck([host], translator_app)
  return translator_app


class DatastoreTranslatorServer(wsgi_server.WsgiServer):
  """The class that devappserver2.py loads to run the datastore translator.

  Init args:
    host: A string containing the name of the host that the server should
        bind to e.g. "localhost".
    port: An int containing the port that the server should bind to e.g. 80.
    enable_host_checking: A bool indicating that HTTP Host checking should
        be enforced for incoming requests.
  """
  def __init__(self, host, port, enable_host_checking=True):
    self._host = host
    app = get_app(host, enable_host_checking)
    super(DatastoreTranslatorServer, self).__init__((host, port), app)

  def start(self):
    super(DatastoreTranslatorServer, self).start()
    logging.info('Starting datastore translator server at: http://%s:%d',
                 *self.bind_addr)
