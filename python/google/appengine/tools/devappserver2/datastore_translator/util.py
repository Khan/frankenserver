"""Utilities for the datastore translator."""
from __future__ import absolute_import

from google.appengine.tools.devappserver2.datastore_translator import grpc


def get_from_union(obj, fields, name_for_debugging="Object", required=False):
  """Given an object, and a set of fields, get the unique one.

  This is useful for the pattern, common in the REST API (and derived from
  proto), where there is a "union" field of which at most one entry may be set.
  This helper asserts as much, and extracts the field and its value.

  Arguments:
    obj (dict[str, Any]): Some object (dictionary) with a union field.
    fields (set[str]): The options in the union field.
    name_for_debugging (str): A description of this object, for error messages.
    required (bool): Set to True to assert that the union field has a value.

  Returns: (field name, field value), or (None, None) if it was not set.

  Raises: grpc.Error("INVALID_ARGUMENT") if invalid.
  """
  present_fields = set(obj) & fields
  if len(present_fields) > 1:
    raise grpc.Error("INVALID_ARGUMENT",
                     "%s should have at most one of: %s"
                     % (name_for_debugging, ', '.join(present_fields)))
  elif not present_fields:
    if required:
      raise grpc.Error("INVALID_ARGUMENT",
                       "%s must have one of: %s"
                       % (name_for_debugging, ', '.join(fields)))
    else:
      return None, None
  field = present_fields.pop()
  return field, obj[field]
