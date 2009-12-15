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

"""A Python blobstore API used by app developers.

Contains methods uses to interface with Blobstore API.  Defines db.Key-like
class representing a blob-key.  Contains API part that forward to apiproxy.
"""




import datetime
import time

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api import api_base_pb
from google.appengine.api.blobstore import blobstore_service_pb
from google.appengine.runtime import apiproxy_errors


__all__ = ['BASE_CREATION_HEADER_FORMAT',
           'BLOB_INFO_KIND',
           'BLOB_KEY_HEADER',
           'BlobKey',
           'CreationFormatError',
           'UPLOAD_INFO_CREATION_HEADER',
           'Error',
           'InternalError',
           'create_upload_url',
           'delete',
           'parse_creation',
          ]


BLOB_INFO_KIND = '__BlobInfo__'

BLOB_KEY_HEADER = 'X-AppEngine-BlobKey'

UPLOAD_INFO_CREATION_HEADER = 'X-AppEngine-Upload-Creation'

BASE_CREATION_HEADER_FORMAT = '%Y-%m-%d %H:%M:%S'

class Error(Exception):
  """Base blobstore error type."""


class InternalError(Error):
  """Raised when an internal error occurs within API."""


class CreationFormatError(Error):
  """Raised when attempting to parse bad creation date format."""


def _ToBlobstoreError(error):
  """Translate an application error to a datastore Error, if possible.

  Args:
    error: An ApplicationError to translate.
  """
  error_map = {
      blobstore_service_pb.BlobstoreServiceError.INTERNAL_ERROR:
      InternalError,
      }

  if error.application_error in error_map:
    return error_map[error.application_error](error.error_detail)
  else:
    return error


def create_upload_url(success_path,
                      _make_sync_call=apiproxy_stub_map.MakeSyncCall):
  """Create upload URL for POST form.

  Args:
    success_path: Path within application to call when POST is successful
      and upload is complete.
    _make_sync_call: Used for dependency injection in tests.
  """
  request = blobstore_service_pb.CreateUploadURLRequest()
  response = blobstore_service_pb.CreateUploadURLResponse()
  request.set_success_path(success_path)
  try:
    _make_sync_call('blobstore', 'CreateUploadURL', request, response)
  except apiproxy_errors.ApplicationError, e:
    raise _ToBlobstoreError(e)

  return response.url()


def delete(blob_keys, _make_sync_call=apiproxy_stub_map.MakeSyncCall):
  """Delete a blob from Blobstore.

  Args:
    blob_keys: Single instance or list of blob keys.  A blob-key can be either
      a string or an instance of BlobKey.
    _make_sync_call: Used for dependency injection in tests.
  """
  if isinstance(blob_keys, (basestring, BlobKey)):
    blob_keys = [blob_keys]
  request = blobstore_service_pb.DeleteBlobRequest()
  for blob_key in blob_keys:
    request.add_blob_key(str(blob_key))
  response = api_base_pb.VoidProto()
  try:
    _make_sync_call('blobstore', 'DeleteBlob', request, response)
  except apiproxy_errors.ApplicationError, e:
    raise _ToBlobstoreError(e)


def parse_creation(creation_string):
  """Parses creation string from header format.

  Parse creation date of the format:

    YYYY-mm-dd HH:MM:SS.ffffff

    Y: Year
    m: Month (01-12)
    d: Day (01-31)
    H: Hour (00-24)
    M: Minute (00-59)
    S: Second (00-59)
    f: Microsecond

  Args:
    creation_string: String creation date format.

  Returns:
    datetime object parsed from creation_string.

  Raises:
    CreationFormatError when the creation string is formatted incorrectly.
  """

  def split(string, by, count):
    result = string.split(by, count)
    if len(result) != count + 1:
      raise CreationFormatError(
          'Could not parse creation %s.' % creation_string)
    return result

  timestamp_string, microsecond = split(creation_string, '.', 1)

  try:
    timestamp = time.strptime(timestamp_string, BASE_CREATION_HEADER_FORMAT)
    microsecond = int(microsecond)
  except ValueError:
    raise CreationFormatError('Could not parse creation %s.' % creation_string)

  return datetime.datetime(*timestamp[:6] + tuple([microsecond]))


BlobKey = datastore_types.BlobKey
