"""Utilities for the datastore translator."""
from __future__ import absolute_import

from google.appengine.tools.devappserver2.datastore_translator import grpc


def get_matching_key(d, keys, name_for_debugging="Object", required=False):
  """Given a dict, return the 1 (or 0) given keys found in the dict.

  This is useful for the pattern, common in the REST API (and derived from
  proto), where there is a "union" field (on some proto message -- a dict in
  pytho) of which at most one entry may be set.

  Arguments:
    d (dict[str, Any]): The dict in which to look for the keys.
    keys (set[str]): The keys to look for.
    name_for_debugging (str): A description of this dict, for error messages.
    required (bool): Set to True to assert that we find a value.

  Returns: (the key found, the corresponding dict value),
    or (None, None) if no key was found (if required=False).

  Raises: grpc.Error("INVALID_ARGUMENT") if invalid.
  """
  present_keys = set(d) & keys
  if len(present_keys) > 1:
    raise grpc.Error("INVALID_ARGUMENT",
                     "%s should have at most one of: %s"
                     % (name_for_debugging, ', '.join(present_keys)))
  elif not present_keys:
    if required:
      raise grpc.Error("INVALID_ARGUMENT",
                       "%s must have one of: %s"
                       % (name_for_debugging, ', '.join(keys)))
    else:
      return None, None
  key = present_keys.pop()
  return key, d[key]
