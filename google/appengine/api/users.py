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

"""Python datastore class User to be used as a datastore data type.

Classes defined here:
  User: object representing a user.
  Error: base exception type
  BadRequestError: UserService exception
  UserNotFoundError: UserService exception
  BackendError: UserService exception
"""






import os
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import user_service_pb
from google.appengine.api import api_base_pb
from google.appengine.runtime import apiproxy_errors


class Error(Exception):
  """Base User error type."""


class UserNotFoundError(Error):
  """Raised by User.__init__() when there's no email argument and no user is
  logged in."""


class RedirectTooLongError(Error):
  """Raised by UserService calls if the generated redirect URL was too long.
  """


class User(object):
  """A user.

  We provide here the email address, nickname, and auth domain for a user.

  A nickname is a human-readable string which uniquely identifies a Google
  user, akin to a username. It will be an email address for some users, but
  not all.
  """


  def __init__(self, email=None, _auth_domain=None):
    """Constructor.

    Args:
      # email is optional. it defaults to the current user.
      email: string
    """
    if _auth_domain is None:
      _auth_domain = os.environ.get('AUTH_DOMAIN')
    else:
      assert email is not None

    assert _auth_domain

    if email is None:
      assert 'USER_EMAIL' in os.environ
      email = os.environ['USER_EMAIL']

    if not email:
      raise UserNotFoundError

    self.__email = email
    self.__auth_domain = _auth_domain

  def nickname(self):
    """Return this user's nickname.

    The nickname will be a unique, human readable identifier for this user
    with respect to this application. It will be an email address for some
    users, but not all.
    """
    if (self.__email and self.__auth_domain and
        self.__email.endswith('@' + self.__auth_domain)):
      suffix_len = len(self.__auth_domain) + 1
      return self.__email[:-suffix_len]
    else:
      return self.__email

  def email(self):
    """Return this user's email address."""
    return self.__email

  def auth_domain(self):
    """Return this user's auth domain."""
    return self.__auth_domain

  def __unicode__(self):
    return unicode(self.nickname())

  def __str__(self):
    return str(self.nickname())

  def __repr__(self):
    return "users.User(email='%s')" % self.email()

  def __hash__(self):
    return hash((self.__email, self.__auth_domain))

  def __cmp__(self, other):
    if not isinstance(other, User):
      return NotImplemented
    return cmp((self.__email, self.__auth_domain),
               (other.__email, other.__auth_domain))


def create_login_url(dest_url):
  """Computes the login URL for this request and specified destination URL.

  Args:
    dest_url: String that is the desired final destination URL for the user
              once login is complete. If 'dest_url' does not have a host
              specified, we will use the host from the current request.

  Returns:
    string
  """
  req = user_service_pb.StringProto()
  resp = user_service_pb.StringProto()
  req.set_value(dest_url)
  try:
    apiproxy_stub_map.MakeSyncCall('user', 'CreateLoginURL', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        user_service_pb.UserServiceError.REDIRECT_URL_TOO_LONG):
      raise RedirectTooLongError
    else:
      raise e
  return resp.value()

CreateLoginURL = create_login_url


def create_logout_url(dest_url):
  """Computes the logout URL for this request and specified destination URL.

  Args:
    dest_url: String that is the desired final destination URL for the user
              once logout is complete. If 'dest_url' does not have a host
              specified, we will use the host from the current request.

  Returns:
    string
  """
  req = user_service_pb.StringProto()
  resp = user_service_pb.StringProto()
  req.set_value(dest_url)
  try:
    apiproxy_stub_map.MakeSyncCall('user', 'CreateLogoutURL', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        user_service_pb.UserServiceError.REDIRECT_URL_TOO_LONG):
      raise RedirectTooLongError
    else:
      raise e
  return resp.value()

CreateLogoutURL = create_logout_url


def get_current_user():
  try:
    return User()
  except UserNotFoundError:
    return None

GetCurrentUser = get_current_user


def is_current_user_admin():
  """Return true if the user making this request is an admin for this
  application, false otherwise.

  We specifically make this a separate function, and not a member function of
  the User class, because admin status is not persisted in the datastore. It
  only exists for the user making this request right now.
  """
  return (os.environ.get('USER_IS_ADMIN', '0')) == "1"

IsCurrentUserAdmin = is_current_user_admin
