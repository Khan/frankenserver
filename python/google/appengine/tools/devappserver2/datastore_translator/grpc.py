"""Utilities related to gRPC.

We implement the REST API, not gRPC, but the error codes are still structured
as for gRPC.  This implements some simple wrappers.
"""

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

  def as_serializable(self):
    return {
      'error': {
        'code': self.http_code,
        'status': self.grpc_code,
        'message': self.message,
      }
    }
