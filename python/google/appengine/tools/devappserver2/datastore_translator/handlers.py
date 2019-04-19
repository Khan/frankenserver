"""Handlers for the REST APIs.

This includes the toplevel translation logic for each RPC, although common
parts are generally extracted out to separate files.
"""
from __future__ import absolute_import

import json
import logging
import os

import webapp2

from google.appengine.api import datastore
from google.appengine.tools.devappserver2.datastore_translator import grpc
from google.appengine.tools.devappserver2.datastore_translator import (
  translate_key)


class Ping(webapp2.RequestHandler):
  """Handler that returns a simple 200, as a health check."""
  def get(self):
    self.response.status_int = 200
    self.response.content_type = 'text/plain'
    self.response.write('Ok')


class _DatastoreApiHandlerBase(webapp2.RequestHandler):
  """Base handler for Datastore REST API requests.

  Handlers should subclass this, and implement json_post, which should accept
  and return JSON (or may call self.error() and return nothing to return an
  error).
  """
  def json_post(self, project_id, json_input):
    """Extension point for subclasses to implement their logic.

    This will be called (with project_id as the project ID and json_input as
    the POST data parsed from JSON.  It should return a JSON-serializable
    response, or call self.error() and return nothing.
    """
    raise NotImplementedError("Subclasses must implement!")

  def post(self, project_id):
    try:
      # Check that the project IDs match (up to dev~ which devappserver adds).
      devappserver_project_id = os.environ.get('APPLICATION_ID')
      if 'dev~%s' % project_id != devappserver_project_id:
        raise grpc.Error("INVALID_ARGUMENT",
                         "requested project ID %s does not match "
                         "devappserver's project ID %s" % (
                             project_id, devappserver_project_id))

      # TODO(benkraft): Assert that project_id matches the project ID this
      # server was started with (which is the actual one that the App Engine
      # API will use when talking to the sqlite db).
      self.response.content_type = 'application/json'
      if self.request.headers.get('content-type') != 'application/json':
        raise grpc.Error("INVALID_ARGUMENT", "Missing content-type header.")

      try:
        json_input = json.loads(self.request.body)
      except Exception as e:
        raise grpc.Error("INVALID_ARGUMENT", "Invalid JSON: %s" % e)

      try:
        self.response.status_int = 200
        json_output = self.json_post(project_id, json_input)
        json.dump(json_output, self.response)
      except grpc.Error:
        raise
      except KeyError as e:   # a common case, we just guess it's a bad request
        raise grpc.Error("INVALID_ARGUMENT",
                         "Invalid request: missing key %s." % e)
      except Exception as e:
        raise grpc.Error("UNKNOWN", "Internal server error: %s" % e)

    except grpc.Error as e:
      self.response.status_int = e.http_code
      if e.http_code >= 500:
        logging.error(e)
      else:
        logging.debug(e)
      json.dump(e.as_serializable(), self.response)
      return


class AllocateIds(_DatastoreApiHandlerBase):
  """Translate the REST allocateIds call (to App Engine's AllocateIds)."""
  def json_post(self, project_id, json_input):
    keys = json_input.get('keys')
    if not keys:
      # Strangely, the API returns an empty OK for any missing or empty keys.
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
