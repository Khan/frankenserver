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

"""Trivial implementation of the UserService."""


import os
import urllib
import urlparse
from google.appengine.api import user_service_pb


_DEFAULT_LOGIN_URL = 'https://www.google.com/accounts/Login?continue=%s'
_DEFAULT_LOGOUT_URL = 'https://www.google.com/accounts/Logout?continue=%s'


class UserServiceStub(object):
  """Trivial implementation of the UserService."""

  def __init__(self,
               login_url=_DEFAULT_LOGIN_URL,
               logout_url=_DEFAULT_LOGOUT_URL):
    """Initializer.

    Args:
      login_url: String containing the URL to use for logging in.
      logout_url: String containing the URL to use for logging out.

    Note: Both the login_url and logout_url arguments must contain one format
    parameter, which will be replaced with the continuation URL where the user
    should be redirected after log-in or log-out has been completed.
    """
    self.__num_requests = 0
    self._login_url = login_url
    self._logout_url = logout_url

    os.environ['AUTH_DOMAIN'] = 'gmail.com'

  def num_requests(self):
    return self.__num_requests

  def MakeSyncCall(self, service, call, request, response):
    """The apiproxy entry point.

    Args:
      service: must be 'user'
      call: string representing which function to call
      request: the URL to redirect to, a base.StringProto
      response: the URL, a base.StringProto

    Currently, CreateLoginURL and CreateLogoutURL are supported.
    """
    assert service == 'user'

    method = getattr(self, "_Dynamic_" + call)
    method(request, response)

  def _Dynamic_CreateLoginURL(self, request, response):
    """Trivial implementation of UserService.CreateLoginURL().

    Args:
      request: the URL to redirect to after login; a base.StringProto
      response: the login URL; a base.StringProto
    """
    self.__num_requests += 1
    response.set_value(
        self._login_url %
        urllib.quote(self._AddHostToContinueURL(request.value())))

  def _Dynamic_CreateLogoutURL(self, request, response):
    """Trivial implementation of UserService.CreateLogoutURL().

    Args:
      request: the URL to redirect to after logout; a base.StringProto
      response: the logout URL; a base.StringProto
    """
    self.__num_requests += 1
    response.set_value(
        self._logout_url %
        urllib.quote(self._AddHostToContinueURL(request.value())))

  def _AddHostToContinueURL(self, continue_url):
    """Adds the request host to the continue url if no host is specified.

    Args:
      continue_url: the URL which may or may not have a host specified

    Returns:
      string
    """
    (protocol, host, path, parameters, query, fragment) = urlparse.urlparse(continue_url, 'http')

    if host:
      return continue_url

    host = os.environ['SERVER_NAME']
    if os.environ['SERVER_PORT'] != '80':
      host = host + ":" + os.environ['SERVER_PORT']

    if path == '':
      path = '/'

    return urlparse.urlunparse(
      (protocol, host, path, parameters, query, fragment))
