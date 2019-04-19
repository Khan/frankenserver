from __future__ import absolute_import

import json
import logging

import webapp2

from google.appengine.api import datastore


class Ping(webapp2.RequestHandler):
  """Handler that returns a simple 200, as a health check."""
  def get(self):
    self.response.status_int = 200
    self.response.content_type = 'text/plain'
    self.response.write('Ok')


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


class _DatastoreApiHandlerBase(webapp2.RequestHandler):
  """Base handler for Datastore REST API requests.

  Handlers should subclass this, and implement json_post, which should accept
  and return JSON (or may call self.error() and return nothing to return an
  error).
  """
  def error(self, grpc_code, message):
    """Return an error response.

    This is formatted roughly like the ones from the real Google API.  Note
    that to simplify the translator, in general we make no attempt to match its
    actual error text.  (In fact, even the official Google emulator doesn't
    match the prod API precisely!)  We just try to give something vaguely
    useful where we can.

    Arguments:
      grpc_code (str): a GRPC status code (one of the keys from
          _GRPC_CODE_TO_HTTP_STATUS, above)
      message (str): a human readable error message

    TODO(benkraft): Include the "details" field as the real API does (e.g. for
    invalid keys in the JSON).
    """
    if grpc_code not in _GRPC_CODE_TO_HTTP_STATUS:
      grpc_code = 'UNKNOWN'

    http_code = _GRPC_CODE_TO_HTTP_STATUS[grpc_code]
    self.response.status_int = http_code

    error_data = {
      'code': http_code,
      'status': grpc_code,
      'message': message,
    }
    json.dump({'error': error_data}, self.response)

  def json_post(self, project_id, json_input):
    """Extension point for subclasses to implement their logic.

    This will be called (with project_id as the project ID and json_input as
    the POST data parsed from JSON.  It should return a JSON-serializable
    response, or call self.error() and return nothing.
    """
    raise NotImplementedError("Subclasses must implement!")

  def post(self, project_id):
    # TODO(benkraft): Assert that project_id matches the project ID this server
    # was started with (which is the actual one that the App Engine API will
    # use when talking to the sqlite db).
    self.response.content_type = 'application/json'
    if self.request.headers.get('content-type') != 'application/json':
      self.error("INVALID_ARGUMENT", "Missing content-type header.")
      return

    try:
      json_input = json.loads(self.request.body)
    except Exception as e:
      logging.debug(e)
      self.error("INVALID_ARGUMENT", "Invalid JSON: %s" % e)
      return

    try:
      self.response.status_int = 200
      json_output = self.json_post(project_id, json_input)
      json.dump(json_output, self.response)
    except KeyError as e:   # a common case, we just guess it's a bad request
      logging.debug(e)
      self.error("INVALID_ARGUMENT", "Invalid request: missing key %s." % e)
    except Exception as e:
      logging.error(e)
      self.error("UNKNOWN", "Internal server error: %s" % e)


class AllocateIds(_DatastoreApiHandlerBase):
  """Translate the REST allocateIds call (to App Engine's AllocateIds)."""
  def json_post(self, project_id, json_input):
    keys = json_input.get('keys')
    if not keys:
      # Strangely, the API returns an empty OK for any missing or empty keys.
      return {}

    for key in keys:
      # TODO(benkraft): Assert that if set, key['partitionId']['projectId']
      # matches project_id.
      path_components = []
      for item in key['path']:
        path_components.append(item['kind'])
        # An AllocateIds request semantically doesn't have an ID on the last
        # element in the path; REST implements it this way but App Engine
        # expects it to be set (because you can't make a key with neither ID
        # nor name) and simply ignores the value.  Additionally, REST uses
        # string IDs (presumably due to JSON limitations) whereas App Engine
        # uses longs.
        # TODO(benkraft): Give errors more like the real REST API here (which
        # will complain if you pass name or ID on the last path component, or
        # if you pass both name and ID in the same component).
        path_components.append(item.get('name', long(item.get('id', 1))))

      # The REST API is structured such that you pass a bunch of incomplete
      # keys; in App Engine instead you pass a single incomplete key and a
      # count of how big a range you'd like.
      # TODO(benkraft): Do these requests async (if there are multiple).
      # TODO(benkraft): Pass through the namespace
      namespace = key.get('partitionId', {}).get('namespaceId')
      start, _ = datastore.AllocateIds(
        datastore.Key.from_path(*path_components, namespace=namespace))

      # For convenience, we just modify the input in place.
      key['path'][-1]['id'] = str(start)

    return {'keys': keys}
