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
"""Dispatcher to handle Google Cloud Storage stub requests."""









import re
import urllib
import urlparse
import xml.etree.ElementTree as ET

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import urlfetch_stub
from google.appengine.ext.cloudstorage import cloudstorage_stub
from google.appengine.ext.cloudstorage import common



_MAX_GET_BUCKET_RESULT = 1000



def _urlfetch_to_gcs_stub(url, payload, method, headers, request, response,
                          follow_redirects=False, deadline=None,
                          validate_certificate=None):

  """Forwards gcs urlfetch requests to gcs_dispatcher.

  See apphosting.api.urlfetch_stub.URLFetchServiceStub._RetrieveURL.
  """
  headers_map = dict(
      (header.key().lower(), header.value()) for header in headers)
  result = dispatch(method, headers_map, url, payload)
  response.set_statuscode(result.status_code)
  response.set_content(result.content[:urlfetch_stub.MAX_RESPONSE_SIZE])
  for k, v in result.headers.iteritems():
    if k.lower() == 'content-length' and method != 'HEAD':
      v = len(response.content())
    header_proto = response.add_header()
    header_proto.set_key(k)
    header_proto.set_value(str(v))
  if len(result.content) > urlfetch_stub.MAX_RESPONSE_SIZE:
    response.set_contentwastruncated(True)


def _urlmatcher_for_gcs_stub(url):
  """Determines whether a url should be handled by gcs stub."""
  _, host, _, _, _ = urlparse.urlsplit(url)
  return host == common.LOCAL_API_HOST



URLMATCHERS_TO_FETCH_FUNCTIONS = [
    (_urlmatcher_for_gcs_stub, _urlfetch_to_gcs_stub)]


class _FakeUrlFetchResult(object):
  def __init__(self, status, headers, content):
    self.status_code = status
    self.headers = headers
    self.content = content


def dispatch(method, headers, url, payload):
  """Dispatches incoming request and returns response.

  In dev appserver or unittest environment, this method is called instead of
  urlfetch.

  Args:
    method: urlfetch method.
    headers: urlfetch headers.
    url: urlfetch url.
    payload: urlfecth payload.

  Returns:
    A _FakeUrlFetchResult.

  Raises:
    ValueError: invalid request method.
  """
  method, headers, filename, param_dict = _preprocess(method, headers, url)
  gs_stub = cloudstorage_stub.CloudStorageStub(
      apiproxy_stub_map.apiproxy.GetStub('blobstore').storage)

  if method == 'POST':
    return _handle_post(gs_stub, filename, headers)
  elif method == 'PUT':
    return _handle_put(gs_stub, filename, param_dict, headers, payload)
  elif method == 'GET':
    return _handle_get(gs_stub, filename, param_dict, headers)
  elif method == 'HEAD':
    return _handle_head(gs_stub, filename)
  elif method == 'DELETE':
    return _handle_delete(gs_stub, filename)
  raise ValueError('Unrecognized request method %r.' % method)


def _preprocess(method, headers, url):
  """Unify input.

  Example:
    _preprocess('POST', {'Content-Type': 'Foo'}, http://gs.com/b/f?foo=bar)
    -> 'POST', {'content-type': 'Foo'}, '/b/f', {'foo':'bar'}

  Args:
    method: HTTP method used by the request.
    headers: HTTP request headers in a dict.
    url: HTTP request url.

  Returns:
    method: method in all upper case.
    headers: headers with keys in all lower case.
    filename: a google storage filename of form /bucket/filename or
      a bucket path of form /bucket
    param_dict: a dict of query parameters.
  """
  _, _, filename, query, _ = urlparse.urlsplit(url)
  param_dict = urlparse.parse_qs(query, True)
  for k in param_dict:
    param_dict[k] = urllib.unquote(param_dict[k][0])

  headers = dict((k.lower(), v) for k, v in headers.iteritems())
  return method, headers, filename, param_dict


def _handle_post(gs_stub, filename, headers):
  """Handle POST that starts object creation."""
  content_type = _ContentType(headers)
  token = gs_stub.post_start_creation(filename, headers)
  response_headers = {
      'location': 'https://storage.googleapis.com/%s?%s' % (
          filename,
          urllib.urlencode({'upload_id': token})),
      'content-type': content_type.value,
      'content-length': 0
  }
  return _FakeUrlFetchResult(201, response_headers, '')


def _handle_put(gs_stub, filename, param_dict, headers, payload):
  """Handle PUT that continues object creation."""
  token = _get_param('upload_id', param_dict)
  content_range = _ContentRange(headers)

  if content_range.value and not content_range.finished:
    gs_stub.put_continue_creation(token,
                                  payload,
                                  (content_range.start, content_range.end))
    response_headers = {}
    response_status = 308
  elif content_range.value and content_range.finished:
    gs_stub.put_continue_creation(token,
                                  payload,
                                  (content_range.start, content_range.end),
                                  last=True)
    filestat = gs_stub.head_object(filename)
    response_headers = {
        'content-length': filestat.st_size,
    }
    response_status = 200
  elif not payload:

    gs_stub.put_continue_creation(token, '', None, True)
    filestat = gs_stub.head_object(filename)
    response_headers = {
        'content-length': filestat.st_size,
    }
    response_status = 200
  else:
    raise ValueError('Missing header content-range but has payload')
  return _FakeUrlFetchResult(response_status, response_headers, '')


def _handle_get(gs_stub, filename, param_dict, headers):
  """Handle GET object and GET bucket."""
  if filename.rfind('/') == 0:

    return _handle_get_bucket(gs_stub, filename, param_dict)
  else:

    result = _handle_head(gs_stub, filename)
    if result.status_code == 404:
      return result
    start, end = _Range(headers).value
    st_size = result.headers['content-length']
    if end is None:
      end = st_size - 1
    result.headers['content-range'] = 'bytes: %d-%d/%d' % (start,
                                                           end,
                                                           st_size)
    result.content = gs_stub.get_object(filename, start, end)
    return result


def _handle_get_bucket(gs_stub, bucketpath, param_dict):
  """Handle get bucket request."""
  prefix = _get_param('prefix', param_dict, '')
  max_keys = _get_param('max-keys', param_dict, _MAX_GET_BUCKET_RESULT)
  marker = _get_param('marker', param_dict, '')

  stats = gs_stub.get_bucket(bucketpath,
                             prefix,
                             marker,
                             max_keys)

  builder = ET.TreeBuilder()
  builder.start('ListBucketResult', {'xmlns': common.CS_XML_NS})
  last_object_name = ''
  for stat in stats:
    builder.start('Contents', {})

    builder.start('Key', {})
    last_object_name = stat.filename[len(bucketpath) + 1:]
    builder.data(last_object_name)
    builder.end('Key')

    builder.start('LastModified', {})
    builder.data(common.posix_to_dt_str(stat.st_ctime))
    builder.end('LastModified')

    builder.start('ETag', {})
    builder.data(stat.etag)
    builder.end('ETag')

    builder.start('Size', {})
    builder.data(str(stat.st_size))
    builder.end('Size')

    builder.end('Contents')

  if last_object_name:
    builder.start('NextMarker', {})
    builder.data(last_object_name)
    builder.end('NextMarker')

  max_keys = _get_param('max-keys', param_dict)
  if max_keys is not None:
    builder.start('MaxKeys', {})
    builder.data(str(max_keys))
    builder.end('MaxKeys')

  builder.end('ListBucketResult')
  root = builder.close()

  body = ET.tostring(root)
  response_headers = {'content-length': len(body),
                      'content-type': 'application/xml'}
  return _FakeUrlFetchResult(200, response_headers, body)


def _handle_head(gs_stub, filename):
  """Handle HEAD request."""
  filestat = gs_stub.head_object(filename)
  if not filestat:
    return _FakeUrlFetchResult(404, {}, '')

  http_time = common.posix_time_to_http(filestat.st_ctime)

  response_headers = {
      'content-length': filestat.st_size,
      'content-type': filestat.content_type,
      'etag': filestat.etag,
      'last-modified': http_time
  }

  if filestat.metadata:
    response_headers.update(filestat.metadata)

  return _FakeUrlFetchResult(200, response_headers, '')


def _handle_delete(gs_stub, filename):
  """Handle DELETE object."""
  if gs_stub.delete_object(filename):
    return _FakeUrlFetchResult(204, {}, '')
  else:
    return _FakeUrlFetchResult(404, {}, '')


class _Header(object):
  """Wrapper class for a header.

  A subclass helps to parse a specific header.
  """

  HEADER = ''
  DEFAULT = None

  def __init__(self, headers):
    """Initialize.

    Initializes self.value to the value in request header, or DEFAULT if
    not defined in headers.

    Args:
      headers: request headers.
    """
    self.value = self.DEFAULT
    for k in headers:
      if k.lower() == self.HEADER.lower():
        self.value = headers[k]
        break


class _ContentType(_Header):
  """Content-type header."""

  HEADER = 'Content-Type'
  DEFAULT = 'binary/octet-stream'


class _ContentRange(_Header):
  """Content-Range header.

  Used by resumable upload. Possible formats:
    Content-Range: bytes 2-4/5 or Content-Range: bytes 1-3/*
  """

  HEADER = 'Content-Range'
  RE_PATTERN = re.compile(r'^bytes ([0-9]+)-([0-9]+)/([0-9]+|\*)$')

  def __init__(self, headers):
    super(_ContentRange, self).__init__(headers)
    if self.value:
      result = self.RE_PATTERN.match(self.value)
      if not result:
        raise ValueError('Invalid content-range header %s' % self.value)
      self.start = long(result.group(1))
      self.end = long(result.group(2))
      self.finished = result.group(3) != '*'


class _Range(_Header):
  """_Range header.

  Used by read. Format: Range: bytes=1-3.
  """

  HEADER = 'Range'

  def __init__(self, headers):
    super(_Range, self).__init__(headers)
    if self.value:
      start, end = self.value.rsplit('=', 1)[-1].split('-')
      start, end = long(start), long(end)
    else:
      start, end = 0, None
    self.value = start, end


def _get_param(param, param_dict, default=None):
  """Gets a parameter value from request query parameters.

  Args:
    param: name of the parameter to get.
    param_dict: a dict of request query parameters.
    default: default value if not defined.

  Returns:
    Value of the parameter or default if not defined.
  """
  result = param_dict.get(param, default)
  if param in ['max-keys'] and result:
    return long(result)
  return result
