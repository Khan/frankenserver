"""Utilities related to gRPC.

We implement the REST API, not gRPC, but the error codes are still structured
as for gRPC.  This implements some simple wrappers.
"""
from __future__ import absolute_import

# Amusingly, there is no legal way to wrap the following lines:
from google.appengine.tools.devappserver2.datastore_translator.genproto import status_pb2  # noqa: E501
from google.appengine.tools.devappserver2.datastore_translator.genproto import code_pb2  # noqa: E501

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

_GRPC_CODE_TO_INT = dict(code_pb2.Code.items())
assert _GRPC_CODE_TO_INT.keys() == _GRPC_CODE_TO_HTTP_STATUS.keys()


class Error(Exception):
  """Return an error to the user.

  This is formatted roughly like the ones from the real Google API.  Note
  that to simplify the translator, in general we make no attempt to match its
  actual error text.  (In fact, even the official Google emulator doesn't
  match the prod API precisely!)  We just try to give something vaguely
  useful where we can.

  Init Arguments:
    grpc_code (str): a GRPC status code (one of the keys from
        _GRPC_CODE_TO_HTTP_STATUS, above)
    message (str): a human readable error message

  TODO(benkraft): Include the "details" field as the real API does (e.g. for
  invalid keys in the JSON).
  """
  def __init__(self, grpc_code, message):
    super(Error, self).__init__(message)
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
