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
"""General utility functions for devappserver2."""




import BaseHTTPServer
import os
import socket
import wsgiref.headers
from google.appengine.tools import sdk_update_checker


# The SDK version returned when there is no available VERSION file.
_DEFAULT_SDK_VERSION = '(Internal)'


def get_headers_from_environ(environ):
  """Get a wsgiref.headers.Headers object with headers from the environment.

  Headers in environ are prefixed with 'HTTP_', are all uppercase, and have
  had dashes replaced with underscores.  This strips the HTTP_ prefix and
  changes underscores back to dashes before adding them to the returned set
  of headers.

  Args:
    environ: An environ dict for the request as defined in PEP-333.

  Returns:
    A wsgiref.headers.Headers object that's been filled in with any HTTP
    headers found in environ.
  """
  headers = wsgiref.headers.Headers([])
  for header, value in environ.iteritems():
    if header.startswith('HTTP_'):
      headers[header[5:].replace('_', '-')] = value
  # Content-Type is special; it does not start with 'HTTP_'.
  if 'CONTENT_TYPE' in environ:
    headers['CONTENT-TYPE'] = environ['CONTENT_TYPE']
  return headers


def put_headers_in_environ(headers, environ):
  """Given a list of headers, put them into environ based on PEP-333.

  This converts headers to uppercase, prefixes them with 'HTTP_', and
  converts dashes to underscores before adding them to the environ dict.

  Args:
    headers: A list of (header, value) tuples.  The HTTP headers to add to the
      environment.
    environ: An environ dict for the request as defined in PEP-333.
  """
  for key, value in headers:
    environ['HTTP_%s' % key.upper().replace('-', '_')] = value


def is_env_flex(env):
  return env in ['2', 'flex', 'flexible']


class HTTPServerIPv6(BaseHTTPServer.HTTPServer):
  """An HTTPServer that supports IPv6 connections.

  The standard HTTPServer has address_family hardcoded to socket.AF_INET.
  """
  address_family = socket.AF_INET6


def get_sdk_version():
  """Parses the SDK VERSION file for the SDK version.

  Returns:
    A semver string representing the SDK version, eg 1.9.55. If no VERSION file
    is available, eg for internal SDK builds, a non-semver default string is
    provided.
  """
  version_object = sdk_update_checker.GetVersionObject()
  if version_object:
    return version_object['release']
  else:
    return _DEFAULT_SDK_VERSION


def setup_environ(app_id):
  """Sets up the os.environ dictionary for the front-end server and API server.

  This function should only be called once.

  Args:
    app_id: The id of the application.
  """
  os.environ['APPLICATION_ID'] = app_id
