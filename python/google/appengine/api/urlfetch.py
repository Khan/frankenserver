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

"""URL downloading API.

Methods defined in this module:
   Fetch(): fetchs a given URL using an HTTP GET or POST
"""





import os
import UserDict
import urllib2
import urlparse

from google.appengine.api import apiproxy_rpc
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import urlfetch_service_pb
from google.appengine.api.urlfetch_errors import *
from google.appengine.runtime import apiproxy_errors

MAX_REDIRECTS = 5

GET = 1
POST = 2
HEAD = 3
PUT = 4
DELETE = 5


_URL_STRING_MAP = {
    'GET': GET,
    'POST': POST,
    'HEAD': HEAD,
    'PUT': PUT,
    'DELETE': DELETE,
}


_VALID_METHODS = frozenset(_URL_STRING_MAP.values())


class _CaselessDict(UserDict.IterableUserDict):
  """Case insensitive dictionary.

  This class was lifted from os.py and slightly modified.
  """

  def __init__(self):
    UserDict.IterableUserDict.__init__(self)
    self.caseless_keys = {}

  def __setitem__(self, key, item):
    """Set dictionary item.

    Args:
      key: Key of new item.  Key is case insensitive, so "d['Key'] = value "
        will replace previous values set by "d['key'] = old_value".
      item: Item to store.
    """
    caseless_key = key.lower()
    if caseless_key in self.caseless_keys:
      del self.data[self.caseless_keys[caseless_key]]
    self.caseless_keys[caseless_key] = key
    self.data[key] = item

  def __getitem__(self, key):
    """Get dictionary item.

    Args:
      key: Key of item to get.  Key is case insensitive, so "d['Key']" is the
        same as "d['key']".

    Returns:
      Item associated with key.
    """
    return self.data[self.caseless_keys[key.lower()]]

  def __delitem__(self, key):
    """Remove item from dictionary.

    Args:
      key: Key of item to remove.  Key is case insensitive, so "del d['Key']" is
        the same as "del d['key']"
    """
    caseless_key = key.lower()
    del self.data[self.caseless_keys[caseless_key]]
    del self.caseless_keys[caseless_key]

  def has_key(self, key):
    """Determine if dictionary has item with specific key.

    Args:
      key: Key to check for presence.  Key is case insensitive, so
        "d.has_key('Key')" evaluates to the same value as "d.has_key('key')".

    Returns:
      True if dictionary contains key, else False.
    """
    return key.lower() in self.caseless_keys

  def __contains__(self, key):
    """Same as 'has_key', but used for 'in' operator.'"""
    return self.has_key(key)

  def get(self, key, failobj=None):
    """Get dictionary item, defaulting to another value if it does not exist.

    Args:
      key: Key of item to get.  Key is case insensitive, so "d['Key']" is the
        same as "d['key']".
      failobj: Value to return if key not in dictionary.
    """
    try:
      cased_key = self.caseless_keys[key.lower()]
    except KeyError:
      return failobj
    return self.data[cased_key]

  def update(self, dict=None, **kwargs):
    """Update dictionary using values from another dictionary and keywords.

    Args:
      dict: Dictionary to update from.
      kwargs: Keyword arguments to update from.
    """
    if dict:
      try:
        keys = dict.keys()
      except AttributeError:
        for k, v in dict:
          self[k] = v
      else:
        for k in keys:
          self[k] = dict[k]
    if kwargs:
      self.update(kwargs)

  def copy(self):
    """Make a shallow, case sensitive copy of self."""
    return dict(self)


def _is_fetching_self(url, method):
  """Checks if the fetch is for the same URL from which it originated.

  Args:
    url: str, The URL being fetched.
    method: value from _VALID_METHODS.

  Returns:
    boolean indicating whether or not it seems that the app is trying to fetch
      itself.
  """
  if (method != GET or
      "HTTP_HOST" not in os.environ or
      "PATH_INFO" not in os.environ):
    return False

  scheme, host_port, path, query, fragment = urlparse.urlsplit(url)

  if host_port == os.environ['HTTP_HOST']:
    current_path = urllib2.unquote(os.environ['PATH_INFO'])
    desired_path = urllib2.unquote(path)

    if (current_path == desired_path or
        (current_path in ('', '/') and desired_path in ('', '/'))):
      return True

  return False


def __create_rpc(deadline=None, callback=None):
  """DO NOT USE.  WILL CHANGE AND BREAK YOUR CODE.

  Creates an RPC object for use with the urlfetch API.

  Args:
    deadline: deadline in seconds for the operation.
    callback: callable to invoke on completion.

  Returns:
    A _URLFetchRPC object.
  """
  return _URLFetchRPC(deadline, callback)


def fetch(url, payload=None, method=GET, headers={}, allow_truncated=False,
          follow_redirects=True, deadline=None):
  """Fetches the given HTTP URL, blocking until the result is returned.

  Other optional parameters are:
     method: GET, POST, HEAD, PUT, or DELETE
     payload: POST or PUT payload (implies method is not GET, HEAD, or DELETE).
       this is ignored if the method is not POST or PUT.
     headers: dictionary of HTTP headers to send with the request
     allow_truncated: if true, truncate large responses and return them without
       error. otherwise, ResponseTooLargeError will be thrown when a response is
       truncated.
     follow_redirects: if true (the default), redirects are
       transparently followed and the response (if less than 5
       redirects) contains the final destination's payload and the
       response status is 200.  You lose, however, the redirect chain
       information.  If false, you see the HTTP response yourself,
       including the 'Location' header, and redirects are not
       followed.
     deadline: deadline in seconds for the operation.

  We use a HTTP/1.1 compliant proxy to fetch the result.

  The returned data structure has the following fields:
     content: string containing the response from the server
     status_code: HTTP status code returned by the server
     headers: dictionary of headers returned by the server

  If the URL is an empty string or obviously invalid, we throw an
  urlfetch.InvalidURLError. If the server cannot be contacted, we throw a
  urlfetch.DownloadError.  Note that HTTP errors are returned as a part
  of the returned structure, so HTTP errors like 404 do not result in an
  exception.
  """
  rpc = __create_rpc(deadline=deadline)
  rpc.make_call(url, payload, method, headers, follow_redirects)
  return rpc.get_result(allow_truncated)


class _URLFetchRPC(object):
  """A RPC object that manages the urlfetch RPC.

  Its primary functions are the following:
  1. Convert error codes to the URLFetchServiceError namespace and raise them
     when get_result is called.
  2. Wrap the urlfetch response with a _URLFetchResult object.
  """

  def __init__(self, deadline=None, callback=None):
    """Construct a new url fetch RPC.

    Args:
      deadline: deadline in seconds for the operation.
      callback: callable to invoke on completion.
    """
    self.__rpc = apiproxy_stub_map.CreateRPC('urlfetch')
    self.__rpc.deadline = deadline
    self.__rpc.callback = callback
    self.__called_hooks = False

  def make_call(self, url, payload=None, method=GET, headers={},
                follow_redirects=True):
    """Executes the RPC call to fetch a given HTTP URL.

    See urlfetch.fetch for a thorough description of arguments.
    """
    assert self.__rpc.state is apiproxy_rpc.RPC.IDLE
    if isinstance(method, basestring):
      method = method.upper()
    method = _URL_STRING_MAP.get(method, method)
    if method not in _VALID_METHODS:
      raise InvalidMethodError('Invalid method %s.' % str(method))

    if _is_fetching_self(url, method):
      raise InvalidURLError("App cannot fetch the same URL as the one used for "
                            "the request.")

    self.__request = urlfetch_service_pb.URLFetchRequest()
    self.__response = urlfetch_service_pb.URLFetchResponse()
    self.__result = None
    self.__request.set_url(url)

    if method == GET:
      self.__request.set_method(urlfetch_service_pb.URLFetchRequest.GET)
    elif method == POST:
      self.__request.set_method(urlfetch_service_pb.URLFetchRequest.POST)
    elif method == HEAD:
      self.__request.set_method(urlfetch_service_pb.URLFetchRequest.HEAD)
    elif method == PUT:
      self.__request.set_method(urlfetch_service_pb.URLFetchRequest.PUT)
    elif method == DELETE:
      self.__request.set_method(urlfetch_service_pb.URLFetchRequest.DELETE)

    if payload and (method == POST or method == PUT):
      self.__request.set_payload(payload)

    for key, value in headers.iteritems():
      header_proto = self.__request.add_header()
      header_proto.set_key(key)
      header_proto.set_value(str(value))

    self.__request.set_followredirects(follow_redirects)
    if self.__rpc.deadline:
      self.__request.set_deadline(self.__rpc.deadline)

    apiproxy_stub_map.apiproxy.GetPreCallHooks().Call(
        'urlfetch', 'Fetch', self.__request, self.__response)
    self.__rpc.MakeCall('urlfetch', 'Fetch', self.__request, self.__response)

  def wait(self):
    """Waits for the urlfetch RPC to finish.  Idempotent.
    """
    assert self.__rpc.state is not apiproxy_rpc.RPC.IDLE
    if self.__rpc.state is apiproxy_rpc.RPC.RUNNING:
      self.__rpc.Wait()

  def check_success(self, allow_truncated=False):
    """Check success and convert RPC exceptions to urlfetch exceptions.

    This method waits for the RPC if it has not yet finished, and calls the
    post-call hooks on the first invocation.

    Args:
      allow_truncated: if False, an error is raised if the response was
        truncated.

    Raises:
      InvalidURLError if the url was invalid.
      DownloadError if there was a problem fetching the url.
      ResponseTooLargeError if the response was either truncated (and
        allow_truncated is false) or if it was too big for us to download.
    """
    assert self.__rpc.state is not apiproxy_rpc.RPC.IDLE
    if self.__rpc.state is apiproxy_rpc.RPC.RUNNING:
      self.wait()

    try:
      self.__rpc.CheckSuccess()
      if not self.__called_hooks:
        self.__called_hooks = True
        apiproxy_stub_map.apiproxy.GetPostCallHooks().Call(
            'urlfetch', 'Fetch', self.__request, self.__response)
    except apiproxy_errors.ApplicationError, e:
      if (e.application_error ==
          urlfetch_service_pb.URLFetchServiceError.INVALID_URL):
        raise InvalidURLError(str(e))
      if (e.application_error ==
          urlfetch_service_pb.URLFetchServiceError.UNSPECIFIED_ERROR):
        raise DownloadError(str(e))
      if (e.application_error ==
          urlfetch_service_pb.URLFetchServiceError.FETCH_ERROR):
        raise DownloadError(str(e))
      if (e.application_error ==
          urlfetch_service_pb.URLFetchServiceError.RESPONSE_TOO_LARGE):
        raise ResponseTooLargeError(None)
      if (e.application_error ==
          urlfetch_service_pb.URLFetchServiceError.DEADLINE_EXCEEDED):
        raise DownloadError(str(e))
      raise e

    if self.__response.contentwastruncated() and not allow_truncated:
      raise ResponseTooLargeError(_URLFetchResult(self.__response))

  def get_result(self, allow_truncated=False):
    """Returns the RPC result or raises an exception if the rpc failed.

    This method waits for the RPC if not completed, and checks success.

    Args:
      allow_truncated: if False, an error is raised if the response was
        truncated.

    Returns:
      The urlfetch result.

    Raises:
      Error if the rpc has not yet finished.
      InvalidURLError if the url was invalid.
      DownloadError if there was a problem fetching the url.
      ResponseTooLargeError if the response was either truncated (and
        allow_truncated is false) or if it was too big for us to download.
    """
    if self.__result is None:
      self.check_success(allow_truncated)
      self.__result = _URLFetchResult(self.__response)
    return self.__result


Fetch = fetch


class _URLFetchResult(object):
  """A Pythonic representation of our fetch response protocol buffer.
  """

  def __init__(self, response_proto):
    """Constructor.

    Args:
      response_proto: the URLFetchResponse proto buffer to wrap.
    """
    self.__pb = response_proto
    self.content = response_proto.content()
    self.status_code = response_proto.statuscode()
    self.content_was_truncated = response_proto.contentwastruncated()
    self.headers = _CaselessDict()
    for header_proto in response_proto.header_list():
      self.headers[header_proto.key()] = header_proto.value()
