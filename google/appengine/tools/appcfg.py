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

"""Tool for deploying apps to an app server.

Currently, the application only uploads new appversions. To do this, it first
walks the directory tree rooted at the path the user specifies, adding all the
files it finds to a list. It then uploads the application configuration
(app.yaml) to the server using HTTP, followed by uploading each of the files.
It then commits the transaction with another request.

The bulk of this work is handled by the AppVersionUpload class, which exposes
methods to add to the list of files, fetch a list of modified files, upload
files, and commit or rollback the transaction.
"""


import cookielib
import datetime
import getpass
import logging
import mimetypes
import optparse
import os
import re
import sha
import socket
import sys
import time
import urllib
import urllib2

import google
from google.appengine.api import appinfo
from google.appengine.api import validation
from google.appengine.api import yaml_errors
from google.appengine.api import yaml_object
from google.appengine.datastore import datastore_index
import yaml


MAX_FILES_TO_CLONE = 100
LIST_DELIMITER = "\n"
TUPLE_DELIMITER = "|"

VERSION_FILE = "../VERSION"

UPDATE_CHECK_TIMEOUT = 3

NAG_FILE = ".appcfg_nag"

verbosity = 1


def StatusUpdate(msg):
  """Print a status message to stdout.

  If 'verbosity' is greater than 0, print the message.

  Args:
    msg: The string to print.
  """
  if verbosity > 0:
    print msg


class ClientLoginError(urllib2.HTTPError):
  """Raised to indicate there was an error authenticating with ClientLogin."""

  def __init__(self, url, code, msg, headers, args):
    urllib2.HTTPError.__init__(self, url, code, msg, headers, None)
    self.args = args
    self.reason = args["Error"]


class AbstractRpcServer(object):
  """Provides a common interface for a simple RPC server."""

  def __init__(self, host, auth_function, host_override=None,
               extra_headers=None, save_cookies=False):
    """Creates a new HttpRpcServer.

    Args:
      host: The host to send requests to.
      auth_function: A function that takes no arguments and returns an
        (email, password) tuple when called. Will be called if authentication
        is required.
      host_override: The host header to send to the server (defaults to host).
      extra_headers: A dict of extra headers to append to every request. Values
        supplied here will override other default headers that are supplied.
      save_cookies: If True, save the authentication cookies to local disk.
        If False, use an in-memory cookiejar instead.  Subclasses must
        implement this functionality.  Defaults to False.
    """
    self.host = host
    self.host_override = host_override
    self.auth_function = auth_function
    self.authenticated = False

    self.extra_headers = {
      "User-agent": GetUserAgent()
    }
    if extra_headers:
      self.extra_headers.update(extra_headers)

    self.save_cookies = save_cookies
    self.cookie_jar = cookielib.MozillaCookieJar()
    self.opener = self._GetOpener()
    if self.host_override:
      logging.info("Server: %s; Host: %s", self.host, self.host_override)
    else:
      logging.info("Server: %s", self.host)

  def _GetOpener(self):
    """Returns an OpenerDirector for making HTTP requests.

    Returns:
      A urllib2.OpenerDirector object.
    """
    raise NotImplemented()

  def _CreateRequest(self, url, data=None):
    """Creates a new urllib request."""
    logging.debug("Creating request for: '%s' with payload:\n%s", url, data)
    req = urllib2.Request(url, data=data)
    if self.host_override:
      req.add_header("Host", self.host_override)
    for key, value in self.extra_headers.iteritems():
      req.add_header(key, value)
    return req

  def _GetAuthToken(self, email, password):
    """Uses ClientLogin to authenticate the user, returning an auth token.

    Args:
      email:    The user's email address
      password: The user's password

    Raises:
      ClientLoginError: If there was an error authenticating with ClientLogin.
      HTTPError: If there was some other form of HTTP error.

    Returns:
      The authentication token returned by ClientLogin.
    """
    req = self._CreateRequest(
        url="https://www.google.com/accounts/ClientLogin",
        data=urllib.urlencode({
            "Email": email,
            "Passwd": password,
            "service": "ah",
            "source": "Google-appcfg-1.0",
            "accountType": "HOSTED_OR_GOOGLE"
        })
    )
    try:
      response = self.opener.open(req)
      response_body = response.read()
      response_dict = dict(x.split("=")
                           for x in response_body.split("\n") if x)
      return response_dict["Auth"]
    except urllib2.HTTPError, e:
      if e.code == 403:
        body = e.read()
        response_dict = dict(x.split("=", 1) for x in body.split("\n") if x)
        raise ClientLoginError(req.get_full_url(), e.code, e.msg,
                               e.headers, response_dict)
      else:
        raise

  def _GetAuthCookie(self, auth_token):
    """Fetches authentication cookies for an authentication token.

    Args:
      auth_token: The authentication token returned by ClientLogin.

    Raises:
      HTTPError: If there was an error fetching the authentication cookies.
    """
    continue_location = "http://localhost/"
    args = {"continue": continue_location, "auth": auth_token}
    req = self._CreateRequest("http://%s/_ah/login?%s" %
                              (self.host, urllib.urlencode(args)))
    try:
      response = self.opener.open(req)
    except urllib2.HTTPError, e:
      response = e
    if (response.code != 302 or
        response.info()["location"] != continue_location):
      raise urllib2.HTTPError(req.get_full_url(), response.code, response.msg,
                              response.headers, response.fp)
    self.authenticated = True

  def _Authenticate(self):
    """Authenticates the user.

    The authentication process works as follows:
     1) We get a username and password from the user
     2) We use ClientLogin to obtain an AUTH token for the user
        (see http://code.google.com/apis/accounts/AuthForInstalledApps.html).
     3) We pass the auth token to /_ah/login on the server to obtain an
        authentication cookie. If login was successful, it tries to redirect
        us to the URL we provided.

    If we attempt to access the upload API without first obtaining an
    authentication cookie, it returns a 401 response and directs us to
    authenticate ourselves with ClientLogin.
    """
    for i in range(3):
      credentials = self.auth_function()
      try:
        auth_token = self._GetAuthToken(credentials[0], credentials[1])
      except ClientLoginError, e:
        if e.reason == "BadAuthentication":
          print >>sys.stderr, "Invalid username or password."
          continue
        if e.reason == "CaptchaRequired":
          print >>sys.stderr, (
              "Please go to\n"
              "https://www.google.com/accounts/DisplayUnlockCaptcha\n"
              "and verify you are a human.  Then try again.")
          break;
        if e.reason == "NotVerified":
          print >>sys.stderr, "Account not verified."
          break
        if e.reason == "TermsNotAgreed":
          print >>sys.stderr, "User has not agreed to TOS."
          break
        if e.reason == "AccountDeleted":
          print >>sys.stderr, "The user account has been deleted."
          break
        if e.reason == "AccountDisabled":
          print >>sys.stderr, "The user account has been disabled."
          break
        if e.reason == "ServiceDisabled":
          print >>sys.stderr, ("The user's access to the service has been "
                               "disabled.")
          break
        if e.reason == "ServiceUnavailable":
          print >>sys.stderr, "The service is not available; try again later."
          break
        raise
      self._GetAuthCookie(auth_token)
      return

  def Send(self, request_path, payload="",
           content_type="application/octet-stream",
           timeout=None,
           **kwargs):
    """Sends an RPC and returns the response.

    Args:
      request_path: The path to send the request to, eg /api/appversion/create.
      payload: The body of the request, or None to send an empty request.
      content_type: The Content-Type header to use.
      timeout: timeout in seconds; default None i.e. no timeout.
        (Note: for large requests on OS X, the timeout doesn't work right.)
      kwargs: Any keyword arguments are converted into query string parameters.

    Returns:
      The response body, as a string.
    """
    if not self.authenticated:
      self._Authenticate()

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
      tries = 0
      while True:
        tries += 1
        args = dict(kwargs)
        url = "http://%s%s?%s" % (self.host, request_path,
                                  urllib.urlencode(args))
        req = self._CreateRequest(url=url, data=payload)
        req.add_header("Content-Type", content_type)
        req.add_header("X-appcfg-api-version", "1")
        try:
          f = self.opener.open(req)
          response = f.read()
          f.close()
          return response
        except urllib2.HTTPError, e:
          if tries > 3:
            raise
          elif e.code == 401:
            self._Authenticate()
          elif e.code >= 500 and e.code < 600:
            continue
          else:
            raise
    finally:
      socket.setdefaulttimeout(old_timeout)


class HttpRpcServer(AbstractRpcServer):
  """Provides a simplified RPC-style interface for HTTP requests."""

  DEFAULT_COOKIE_FILE_PATH = "~/.appcfg_cookies"

  def _Authenticate(self):
    """Save the cookie jar after authentication."""
    super(HttpRpcServer, self)._Authenticate()
    if self.cookie_jar.filename is not None and self.save_cookies:
      StatusUpdate("Saving authentication cookies to %s" %
                   self.cookie_jar.filename)
      self.cookie_jar.save()

  def _GetOpener(self):
    """Returns an OpenerDirector that supports cookies and ignores redirects.

    Returns:
      A urllib2.OpenerDirector object.
    """
    opener = urllib2.OpenerDirector()
    opener.add_handler(urllib2.ProxyHandler())
    opener.add_handler(urllib2.UnknownHandler())
    opener.add_handler(urllib2.HTTPHandler())
    opener.add_handler(urllib2.HTTPDefaultErrorHandler())
    opener.add_handler(urllib2.HTTPSHandler())
    opener.add_handler(urllib2.HTTPErrorProcessor())

    if self.save_cookies:
      self.cookie_jar.filename = os.path.expanduser(HttpRpcServer.DEFAULT_COOKIE_FILE_PATH)

      if os.path.exists(self.cookie_jar.filename):
        try:
          self.cookie_jar.load()
          self.authenticated = True
          StatusUpdate("Loaded authentication cookies from %s" %
                       self.cookie_jar.filename)
        except (OSError, IOError, cookielib.LoadError), e:
          logging.debug("Could not load authentication cookies; %s: %s",
                        e.__class__.__name__, e)
          self.cookie_jar.filename = None
      else:
        try:
          fd = os.open(self.cookie_jar.filename, os.O_CREAT, 0600)
          os.close(fd)
        except (OSError, IOError), e:
          logging.debug("Could not create authentication cookies file; %s: %s",
                        e.__class__.__name__, e)
          self.cookie_jar.filename = None

    opener.add_handler(urllib2.HTTPCookieProcessor(self.cookie_jar))
    return opener


def GetMimeTypeIfStaticFile(config, filename):
  """Looks up the mime type for 'filename'.

  Uses the handlers in 'config' to determine if the file should
  be treated as a static file.

  Args:
    config: The app.yaml object to check the filename against.
    filename: The name of the file.

  Returns:
    The mime type string.  For example, 'text/plain' or 'image/gif'.
    None if this is not a static file.
  """
  for handler in config.handlers:
    handler_type = handler.GetHandlerType()
    if handler_type in ("static_dir", "static_files"):
      if handler_type == "static_dir":
        regex = os.path.join(re.escape(handler.GetHandler()), ".*")
      else:
        regex = handler.upload
      if re.match(regex, filename):
        if handler.mime_type is not None:
          return handler.mime_type
        else:
          guess = mimetypes.guess_type(filename)[0]
          if guess is None:
            default = "application/octet-stream"
            print >>sys.stderr, ("Could not guess mimetype for %s.  Using %s."
                                 % (filename, default))
            return default
          return guess
  return None


def BuildClonePostBody(file_tuples):
  """Build the post body for the /api/clone{files,blobs} urls.

  Args:
    file_tuples: A list of tuples.  Each tuple should contain the entries
      appropriate for the endpoint in question.

  Returns:
    A string containing the properly delimited tuples.
  """
  file_list = []
  for tup in file_tuples:
    path = tup[0]
    tup = tup[1:]
    file_list.append(TUPLE_DELIMITER.join([path] + list(tup)))
  return LIST_DELIMITER.join(file_list)


class NagFile(validation.Validated):
  """A validated YAML class to represent the user's nag preferences.

  Attributes:
    timestamp: The timestamp of the last nag.
    opt_in: True if the user wants to check for updates on dev_appserver
      start.  False if not.  May be None if we have not asked the user yet.
  """

  ATTRIBUTES = {
    "timestamp": validation.TYPE_FLOAT,
    "opt_in": validation.Optional(validation.TYPE_BOOL),
  }

  @staticmethod
  def Load(nag_file):
    """Load a single NagFile object where one and only one is expected.

    Args:
      nag_file: A file-like object or string containing the yaml data to parse.

    Returns:
      A NagFile instance.
    """
    return yaml_object.BuildSingleObject(NagFile, nag_file)


def GetVersionObject(isfile=os.path.isfile, open_fn=open):
  """Gets the version of the SDK by parsing the VERSION file.

  Args:
    isfile, open_fn: Used for testing.

  Returns:
    A Yaml object or None if the VERSION file does not exist.
  """
  version_filename = os.path.join(os.path.dirname(google.__file__),
                                  VERSION_FILE)
  if not isfile(version_filename):
    logging.error("Could not find version file at %s", version_filename)
    return None

  version_fh = open_fn(version_filename, "r")
  try:
    version = yaml.safe_load(version_fh)
  finally:
    version_fh.close()

  return version


class UpdateCheck(object):
  """Determines if the local SDK is the latest version.

  Nags the user when there are updates to the SDK.  As the SDK becomes
  more out of date, the language in the nagging gets stronger.  We
  store a little yaml file in the user's home directory so that we nag
  the user only once a week.

  The yaml file has the following field:
    'timestamp': Last time we nagged the user in seconds since the epoch.

  Attributes:
    server: An AbstractRpcServer instance used to check for the latest SDK.
    config: The app's AppInfoExternal.  Needed to determine which api_version
      the app is using.
  """

  def __init__(self,
               server,
               config,
               isdir=os.path.isdir,
               isfile=os.path.isfile,
               open_fn=open):
    """Create a new UpdateCheck.

    Args:
      server: The AbstractRpcServer to use.
      config: The yaml object that specifies the configuration of this
        application.

    Args for testing:
      isdir: Replacement for os.path.isdir.
      isfile: Replacement for os.path.isfile.
      open: Replacement for the open builtin.
    """
    self.server = server
    self.config = config
    self.isdir = isdir
    self.isfile = isfile
    self.open = open_fn

  @staticmethod
  def MakeNagFilename():
    """Returns the filename for the nag file for this user."""
    user_homedir = os.path.expanduser("~/")
    if not os.path.isdir(user_homedir):
      drive, tail = os.path.splitdrive(os.__file__)
      if drive:
        os.environ["HOMEDRIVE"] = drive

    return os.path.expanduser("~/" + NAG_FILE)

  def _ParseVersionFile(self):
    """Parse the local VERSION file.

    Returns:
      A Yaml object or None if the file does not exist.
    """
    return GetVersionObject(isfile=self.isfile, open_fn=self.open)

  def CheckSupportedVersion(self):
    """Determines if the app's api_version is supported by the SDK.

    Uses the api_version field from the AppInfoExternal to determine if
    the SDK supports that api_version.

    Raises:
      SystemExit if the api_version is not supported.
    """
    version = self._ParseVersionFile()
    if version is None:
      logging.error("Could not determine if the SDK supports the api_version "
                    "requested in app.yaml.")
      return
    if self.config.api_version not in version["api_versions"]:
      logging.critical("The api_version specified in app.yaml (%s) is not "
                       "supported by this release of the SDK.  The supported "
                       "api_versions are %s.",
                       self.config.api_version, version["api_versions"])
      sys.exit(1)

  def CheckForUpdates(self):
    """Queries the server for updates and nags the user if appropriate.

    Queries the server for the latest SDK version at the same time reporting
    the local SDK version.  The server will respond with a yaml document
    containing the fields:
      "release": The name of the release (e.g. 1.2).
      "timestamp": The time the release was created (YYYY-MM-DD HH:MM AM/PM TZ).
      "api_versions": A list of api_version strings (e.g. ['1', 'beta']).

    We will nag the user with increasing severity if:
    - There is a new release.
    - There is a new release with a new api_version.
    - There is a new release that does not support the api_version named in
      self.config.
    """
    version = self._ParseVersionFile()
    if version is None:
      logging.info("Skipping update check")
      return
    logging.info("Checking for updates to the SDK.")

    try:
      response = self.server.Send("/api/updatecheck",
                                  timeout=UPDATE_CHECK_TIMEOUT,
                                  release=version["release"],
                                  timestamp=version["timestamp"],
                                  api_versions=version["api_versions"])
    except urllib2.URLError, e:
      logging.info("Update check failed: %s", e)
      return

    latest = yaml.safe_load(response)
    if latest["release"] == version["release"]:
      logging.info("The SDK is up to date.")
      return

    api_versions = latest["api_versions"]
    if self.config.api_version not in api_versions:
      self._Nag(
          "The api version you are using (%s) is obsolete!  You should\n"
          "upgrade your SDK and test that your code works with the new\n"
          "api version." % self.config.api_version,
          latest, version, force=True)
      return

    if self.config.api_version != api_versions[len(api_versions) - 1]:
      self._Nag(
          "The api version you are using (%s) is deprecated. You should\n"
          "upgrade your SDK to try the new functionality." %
          self.config.api_version, latest, version)
      return

    self._Nag("There is a new release of the SDK available.",
              latest, version)

  def _ParseNagFile(self):
    """Parses the nag file.

    Returns:
      A NagFile if the file was present else None.
    """
    nag_filename = UpdateCheck.MakeNagFilename()
    if self.isfile(nag_filename):
      fh = self.open(nag_filename, "r")
      try:
        nag = NagFile.Load(fh)
      finally:
        fh.close()
      return nag
    return None

  def _WriteNagFile(self, nag):
    """Writes the NagFile to the user's nag file.

    If the destination path does not exist, this method will log an error
    and fail silently.

    Args:
      nag: The NagFile to write.
    """
    nagfilename = UpdateCheck.MakeNagFilename()
    try:
      fh = self.open(nagfilename, "w")
      try:
        fh.write(nag.ToYAML())
      finally:
        fh.close()
    except (OSError, IOError), e:
      logging.error("Could not write nag file to %s. Error: %s", nagfilename, e)

  def _Nag(self, msg, latest, version, force=False):
    """Prints a nag message and updates the nag file's timestamp.

    Because we don't want to nag the user everytime, we store a simple
    yaml document in the user's home directory.  If the timestamp in this
    doc is over a week old, we'll nag the user.  And when we nag the user,
    we update the timestamp in this doc.

    Args:
      msg: The formatted message to print to the user.
      latest: The yaml document received from the server.
      version: The local yaml version document.
      force: If True, always nag the user, ignoring the nag file.
    """
    nag = self._ParseNagFile()
    if nag and not force:
      last_nag = datetime.datetime.fromtimestamp(nag.timestamp)
      if datetime.datetime.now() - last_nag < datetime.timedelta(weeks=1):
        logging.debug("Skipping nag message")
        return

    if nag is None:
      nag = NagFile()
    nag.timestamp = time.time()
    self._WriteNagFile(nag)

    print "****************************************************************"
    print msg
    print "-----------"
    print "Latest SDK:"
    print yaml.dump(latest)
    print "-----------"
    print "Your SDK:"
    print yaml.dump(version)
    print "-----------"
    print "Please visit http://code.google.com/appengine for the latest SDK"
    print "****************************************************************"

  def AllowedToCheckForUpdates(self, input_fn=raw_input):
    """Determines if the user wants to check for updates.

    On startup, the dev_appserver wants to check for updates to the SDK.
    Because this action reports usage to Google when the user is not
    otherwise communicating with Google (e.g. pushing a new app version),
    the user must opt in.

    If the user does not have a nag file, we will query the user and
    save the response in the nag file.  Subsequent calls to this function
    will re-use that response.

    Returns:
      True if the user wants to check for updates.  False otherwise.
    """
    nag = self._ParseNagFile()
    if nag is None:
      nag = NagFile()
      nag.timestamp = time.time()

    if nag.opt_in is None:
      answer = input_fn("Allow dev_appserver to check for updates on startup? "
                        "(Y/n): ")
      answer = answer.strip().lower()
      if answer == "n" or answer == "no":
        print ("dev_appserver will not check for updates on startup.  To "
               "change this setting, edit %s" % UpdateCheck.MakeNagFilename())
        nag.opt_in = False
      else:
        print ("dev_appserver will check for updates on startup.  To change "
               "this setting, edit %s" % UpdateCheck.MakeNagFilename())
        nag.opt_in = True
      self._WriteNagFile(nag)
    return nag.opt_in


class IndexDefinitionUpload(object):
  """Provides facilities to upload index definitions to the hosting service."""

  def __init__(self, server, config, definitions):
    """Creates a new DatastoreIndexUpload.

    Args:
      server: The RPC server to use.  Should be an instance of HttpRpcServer
        or TestRpcServer.
      config: The AppInfoExternal object derived from the app.yaml file.
      definitions: An IndexDefinitions object.
    """
    self.server = server
    self.config = config
    self.definitions = definitions

  def DoUpload(self):
    StatusUpdate("Uploading index definitions.")
    self.server.Send("/api/datastore/index/add",
                     app_id=self.config.application,
                     version=self.config.version,
                     payload=self.definitions.ToYAML())


class IndexOperation(object):
  """Provide facilities for writing Index operation commands."""

  def __init__(self, server, config):
    """Creates a new IndexOperation.

    Args:
      server: The RPC server to use.  Should be an instance of HttpRpcServer
        or TestRpcServer.
      config: appinfo.AppInfoExternal configuration object.
    """
    self.server = server
    self.config = config

  def DoDiff(self, definitions):
    """Retrieve diff file from the server.

    Args:
      definitions: datastore_index.IndexDefinitions as loaded from users
        index.yaml file.

    Returns:
      A pair of datastore_index.IndexDefinitions objects.  The first record
      is the set of indexes that are present in the index.yaml file but missing
      from the server.  The second record is the set of indexes that are
      present on the server but missing from the index.yaml file (indicating
      that these indexes should probably be vacuumed).
    """
    StatusUpdate("Fetching index definitions diff.")
    response = self.server.Send("/api/datastore/index/diff",
                                app_id=self.config.application,
                                payload=definitions.ToYAML())
    return datastore_index.ParseMultipleIndexDefinitions(response)

  def DoDelete(self, definitions):
    """Delete indexes from the server.

    Args:
      definitions: Index definitions to delete from datastore.

    Returns:
      A single datstore_index.IndexDefinitions containing indexes that were
      not deleted, probably because they were already removed.  This may
      be normal behavior as there is a potential race condition between fetching
      the index-diff and sending deletion confirmation through.
    """
    StatusUpdate("Deleting selected index definitions.")
    response = self.server.Send("/api/datastore/index/delete",
                                app_id=self.config.application,
                                payload=definitions.ToYAML())
    return datastore_index.ParseIndexDefinitions(response)


class VacuumIndexesOperation(IndexOperation):
  """Provide facilities to request the deletion of datastore indexes."""

  def __init__(self, server, config, force,
               confirmation_fn=raw_input):
    """Creates a new VacuumIndexesOperation.

    Args:
      server: The RPC server to use.  Should be an instance of HttpRpcServer
        or TestRpcServer.
      config: appinfo.AppInfoExternal configuration object.
      force: True to force deletion of indexes, else False.
      confirmation_fn: Function used for getting input form user.
    """
    super(VacuumIndexesOperation, self).__init__(server, config)
    self.force = force
    self.confirmation_fn = confirmation_fn

  def GetConfirmation(self, index):
    """Get confirmation from user to delete an index.

    This method will enter an input loop until the user provides a
    response it is expecting.  Valid input is one of three responses:

      y: Confirm deletion of index.
      n: Do not delete index.
      a: Delete all indexes without asking for further confirmation.

    If the user enters nothing at all, the default action is to skip
    that index and do not delete.

    If the user selects 'a', as a side effect, the 'force' flag is set.

    Args:
      index: Index to confirm.

    Returns:
      True if user enters 'y' or 'a'.  False if user enter 'n'.
    """
    while True:
      print "This index is no longer defined in your index.yaml file."
      print
      print index.ToYAML()
      print

      confirmation = self.confirmation_fn(
          "Are you sure you want to delete this index? (N/y/a): ")
      confirmation = confirmation.strip().lower()

      if confirmation == 'y':
        return True
      elif confirmation == 'n' or confirmation == '':
        return False
      elif confirmation == 'a':
        self.force = True
        return True
      else:
        print "Did not understand your response."

  def DoVacuum(self, definitions):
    """Vacuum indexes in datastore.

    This method will query the server to determine which indexes are not
    being used according to the user's local index.yaml file.  Once it has
    made this determination, it confirms with the user which unused indexes
    should be deleted.  Once confirmation for each index is receives, it
    deletes those indexes.

    Because another user may in theory delete the same indexes at the same
    time as the user, there is a potential race condition.  In this rare cases,
    some of the indexes previously confirmed for deletion will not be found.
    The user is notified which indexes these were.

    Args:
      definitions: datastore_index.IndexDefinitions as loaded from users
        index.yaml file.
    """
    new_indexes, unused_indexes = self.DoDiff(definitions)

    deletions = datastore_index.IndexDefinitions(indexes=[])
    if unused_indexes.indexes is not None:
      for index in unused_indexes.indexes:
        if self.force or self.GetConfirmation(index):
          deletions.indexes.append(index)

    if len(deletions.indexes) > 0:
      not_deleted = self.DoDelete(deletions)

      if not_deleted.indexes:
        not_deleted_count = len(not_deleted.indexes)
        if not_deleted_count == 1:
          warning_message = ('An index was not deleted.  Most likely this is '
                             'because it no longer exists.\n\n')
        else:
          warning_message = ('%d indexes were not deleted.  Most likely this '
                             'is because they no longer exist.\n\n'
                             % not_deleted_count)
        for index in not_deleted.indexes:
          warning_message = warning_message + index.ToYAML()
        logging.warning(warning_message)


class AppVersionUpload(object):
  """Provides facilities to upload a new appversion to the hosting service.

  Attributes:
    server: The AbstractRpcServer to use for the upload.
    config: The AppInfoExternal object derived from the app.yaml file.
    app_id: The application string from 'config'.
    version: The version string from 'config'.
    files: A dictionary of files to upload to the server, mapping path to
      hash of the file contents.
    in_transaction: True iff a transaction with the server has started.
      An AppVersionUpload can do only one transaction at a time.
  """

  def __init__(self, server, config):
    """Creates a new AppVersionUpload.

    Args:
      server: The RPC server to use. Should be an instance of HttpRpcServer or
        TestRpcServer.
      config: An AppInfoExternal object that specifies the configuration for
        this application.
    """
    self.server = server
    self.config = config
    self.app_id = self.config.application
    self.version = self.config.version
    self.files = {}
    self.in_transaction = False

  def _Hash(self, content):
    """Compute the hash of the content.

    Arg:
      content: The data to hash as a string.

    Returns:
      The string representation of the hash.
    """
    h = sha.new(content).hexdigest()
    return '%s_%s_%s_%s_%s' % (h[0:8], h[8:16], h[16:24], h[24:32], h[32:40])

  def AddFile(self, path, file_handle):
    """Adds the provided file to the list to be pushed to the server.

    Args:
      path: The path the file should be uploaded as.
      file_handle: A stream containing data to upload.
    """
    assert not self.in_transaction, "Already in a transaction."
    assert file_handle is not None

    reason = appinfo.ValidFilename(path)
    if reason != '':
      logging.error(reason)
      return

    pos = file_handle.tell()
    content_hash = self._Hash(file_handle.read())
    file_handle.seek(pos, 0)

    self.files[path] = content_hash

  def Begin(self):
    """Begins the transaction, returning a list of files that need uploading.

    All calls to AddFile must be made before calling Begin().

    Returns:
      A list of pathnames for files that should be uploaded using UploadFile()
      before Commit() can be called.
    """
    assert not self.in_transaction, "Already in a transaction."

    StatusUpdate("Initiating update.")
    self.server.Send("/api/appversion/create", app_id=self.app_id,
                     version=self.version, payload=self.config.ToYAML())
    self.in_transaction = True

    files_to_clone = []
    blobs_to_clone = []
    for path, content_hash in self.files.iteritems():
      mime_type = GetMimeTypeIfStaticFile(self.config, path)
      if mime_type is not None:
        blobs_to_clone.append((path, content_hash, mime_type))
      else:
        files_to_clone.append((path, content_hash))

    files_to_upload = {}

    def CloneFiles(url, files, file_type):
      if len(files) == 0:
        return

      StatusUpdate("Cloning %d %s file%s." %
                   (len(files), file_type, len(files) != 1 and "s" or ""))
      for i in xrange(0, len(files), MAX_FILES_TO_CLONE):
        if i > 0 and i % MAX_FILES_TO_CLONE == 0:
          StatusUpdate("Cloned %d files." % i)

        chunk = files[i:min(len(files), i + MAX_FILES_TO_CLONE)]
        result = self.server.Send(url,
                                  app_id=self.app_id, version=self.version,
                                  payload=BuildClonePostBody(chunk))
        if result:
          files_to_upload.update(dict(
              (f, self.files[f]) for f in result.split(LIST_DELIMITER)))

    CloneFiles("/api/appversion/cloneblobs", blobs_to_clone, "static")
    CloneFiles("/api/appversion/clonefiles", files_to_clone, "application")

    logging.info('Files to upload: ' + str(files_to_upload))

    self.files = files_to_upload
    return sorted(files_to_upload.iterkeys())

  def UploadFile(self, path, file_handle):
    """Uploads a file to the hosting service.

    Must only be called after Begin().
    The path provided must be one of those that were returned by Begin().

    Args:
      path: The path the file is being uploaded as.
      file_handle: A file-like object containing the data to upload.

    Raises:
      KeyError: The provided file is not amongst those to be uploaded.
    """
    assert self.in_transaction, "Begin() must be called before UploadFile()."
    if path not in self.files:
      raise KeyError("File '%s' is not in the list of files to be uploaded."
                     % path)

    del self.files[path]
    mime_type = GetMimeTypeIfStaticFile(self.config, path)
    if mime_type is not None:
      self.server.Send("/api/appversion/addblob", app_id=self.app_id,
                       version=self.version, path=path, content_type=mime_type,
                       payload=file_handle.read())
    else:
      self.server.Send("/api/appversion/addfile", app_id=self.app_id,
                       version=self.version, path=path,
                       payload=file_handle.read())

  def Commit(self):
    """Commits the transaction, making the new app version available.

    All the files returned by Begin() must have been uploaded with UploadFile()
    before Commit() can be called.

    Raises:
      Exception: Some required files were not uploaded.
    """
    assert self.in_transaction, "Begin() must be called before Commit()."
    if self.files:
      raise Exception("Not all required files have been uploaded.")

    StatusUpdate("Closing update.")
    self.server.Send("/api/appversion/commit", app_id=self.app_id,
                     version=self.version)
    self.in_transaction = False

  def Rollback(self):
    """Rolls back the transaction if one is in progress."""
    if not self.in_transaction:
      return
    StatusUpdate("Rolling back the update.")
    self.server.Send("/api/appversion/rollback", app_id=self.app_id,
                     version=self.version)
    self.in_transaction = False
    self.files = {}

  def DoUpload(self, paths, max_size, openfunc):
    """Uploads a new appversion with the given config and files to the server.

    Args:
      paths: An iterator that yields the relative paths of the files to upload.
      max_size: The maximum size file to upload.
      openfunc: A function that takes a path and returns a file-like object.
    """
    logging.info("Reading app configuration.")

    try:
      StatusUpdate("Scanning files on local disk.")
      num_files = 0
      for path in paths:
        file_handle = openfunc(path)
        try:
          if self.config.skip_files.match(path):
            logging.info("Ignoring file '%s': File matches ignore regex.",
                         path)
          else:
            file_length = GetFileLength(file_handle)
            if file_length > max_size:
              logging.error("Ignoring file '%s': Too long "
                            "(max %d bytes, file is %d bytes)",
                            path, max_size, file_length)
            else:
              logging.info("Processing file '%s'", path)
              self.AddFile(path, file_handle)
        finally:
          file_handle.close()
        num_files += 1
        if num_files % 500 == 0:
          StatusUpdate("Scanned %d files." % num_files)
    except KeyboardInterrupt:
      logging.info("User interrupted. Aborting.")
      raise
    except EnvironmentError, e:
      logging.error("An error occurred processing file '%s': %s. Aborting.",
                    path, e)
      raise

    try:
      missing_files = self.Begin()
      if len(missing_files) > 0:
        StatusUpdate("Uploading %d files." % len(missing_files))
        num_files = 0
        for missing_file in missing_files:
          logging.info("Uploading file '%s'" % missing_file)
          file_handle = openfunc(missing_file)
          try:
            self.UploadFile(missing_file, file_handle)
          finally:
            file_handle.close()
          num_files += 1
          if num_files % 500 == 0:
            StatusUpdate("Uploaded %d files." % num_files)

      self.Commit()
    except KeyboardInterrupt:
      logging.info("User interrupted. Aborting.")
      self.Rollback()
      raise
    except:
      logging.error("An unexpected error occurred. Aborting.")
      self.Rollback()
      raise

    logging.info("Done!")


def FileIterator(base, separator=os.path.sep):
  """Walks a directory tree, returning all the files. Follows symlinks.

  Args:
    base: The base path to search for files under.
    separator: Path separator used by the running system's platform.

  Yields:
    Paths of files found, relative to base.
  """
  dirs = [""]
  while dirs:
    current_dir = dirs.pop()
    for entry in os.listdir(os.path.join(base, current_dir)):
      name = os.path.join(current_dir, entry)
      fullname = os.path.join(base, name)
      if os.path.isfile(fullname):
        if separator == "\\":
          name = name.replace("\\", "/")
        yield name
      elif os.path.isdir(fullname):
        dirs.append(name)


def GetFileLength(fh):
  """Returns the length of the file represented by fh.

  This function is capable of finding the length of any seekable stream,
  unlike os.fstat, which only works on file streams.

  Args:
    fh: The stream to get the length of.

  Returns:
    The length of the stream.
  """
  pos = fh.tell()
  fh.seek(0, 2)
  length = fh.tell()
  fh.seek(pos, 0)
  return length


def GetPlatformToken(os_module=os, sys_module=sys, platform=sys.platform):
  """Returns a 'User-agent' token for the host system platform.

  Args:
    os_module, sys_module, platform: Used for testing.

  Returns:
    String containing the platform token for the host system.
  """
  if hasattr(sys_module, "getwindowsversion"):
    windows_version = sys_module.getwindowsversion()
    version_info = ".".join(str(i) for i in windows_version[:4])
    return platform + "/" + version_info
  elif hasattr(os_module, "uname"):
    uname = os_module.uname()
    return "%s/%s" % (uname[0], uname[2])
  else:
    return "unknown"


def GetUserAgent(get_version=GetVersionObject, get_platform=GetPlatformToken):
  """Determines the value of the 'User-agent' header to use for HTTP requests.

  If the 'APPCFG_SDK_NAME' environment variable is present, that will be
  used as the first product token in the user-agent.

  Args:
    get_version, get_platform: Used for testing.

  Returns:
    String containing the 'user-agent' header value, which includes the SDK
    version, the platform information, and the version of Python;
    e.g., "appcfg_py/1.0.1 Darwin/9.2.0 Python/2.5.2".
  """
  product_tokens = []

  sdk_name = os.environ.get("APPCFG_SDK_NAME")
  if sdk_name:
    product_tokens.append(sdk_name)
  else:
    version = get_version()
    if version is None:
      release = "unknown"
    else:
      release = version["release"]

    product_tokens.append("appcfg_py/%s" % release)

  product_tokens.append(get_platform())

  python_version = ".".join(str(i) for i in sys.version_info)
  product_tokens.append("Python/%s" % python_version)

  return " ".join(product_tokens)


class AppCfgApp(object):
  """Singleton class to wrap AppCfg tool functionality.

  This class is responsible for parsing the command line and executing
  the desired action on behalf of the user.  Processing files and
  communicating with the server is handled by other classes.

  Attributes:
    actions: A dictionary mapping action names to Action objects.
    action: The Action specified on the command line.
    parser: An instance of optparse.OptionParser.
    options: The command line options parsed by 'parser'.
    argv: The original command line as a list.
    args: The positional command line args left over after parsing the options.
    raw_input_fn: Function used for getting raw user input, like email.
    password_input_fn: Function used for getting user password.

  Attributes for testing:
    parser_class: The class to use for parsing the command line.  Because
      OptionsParser will exit the program when there is a parse failure, it
      is nice to subclass OptionsParser and catch the error before exiting.
  """

  def __init__(self, argv, parser_class=optparse.OptionParser,
               rpc_server_class=HttpRpcServer,
               raw_input_fn=raw_input,
               password_input_fn=getpass.getpass):
    """Initializer.  Parses the cmdline and selects the Action to use.

    Initializes all of the attributes described in the class docstring.
    Prints help or error messages if there is an error parsing the cmdline.

    Args:
      argv: The list of arguments passed to this program.
      parser_class: Options parser to use for this application.
      rpc_server_class: RPC server class to use for this application.
      raw_input_fn: Function used for getting user email.
      password_input_fn: Function used for getting user password.
    """
    self.parser_class = parser_class
    self.argv = argv
    self.rpc_server_class = rpc_server_class
    self.raw_input_fn = raw_input_fn
    self.password_input_fn = password_input_fn

    self.parser = self._GetOptionParser()
    for action in self.actions.itervalues():
      action.options(self, self.parser)

    self.options, self.args = self.parser.parse_args(argv[1:])

    if len(self.args) < 1:
      self._PrintHelpAndExit()
    if self.args[0] not in self.actions:
      self.parser.error("Unknown action '%s'\n%s" %
                        (self.args[0], self.parser.get_description()))
    action_name = self.args.pop(0)
    self.action = self.actions[action_name]

    self.parser, self.options = self._MakeSpecificParser(self.action)

    if self.options.help:
      self._PrintHelpAndExit()

    if self.options.verbose == 2:
      logging.getLogger().setLevel(logging.INFO)
    elif self.options.verbose == 3:
      logging.getLogger().setLevel(logging.DEBUG)

    global verbosity
    verbosity = self.options.verbose

  def Run(self, error_fh=sys.stderr):
    """Executes the requested action.

    Catches any HTTPErrors raised by the action and prints them to stderr.

    Args:
      error_fh: Print any HTTPErrors to this file handle.
    """
    try:
      self.action.function(self)
    except urllib2.HTTPError, e:
      body = e.read()
      print >>error_fh, ("Error %d: --- begin server output ---\n"
                         "%s\n--- end server output ---" %
                         (e.code, body.rstrip("\n")))
    except yaml_errors.EventListenerError, e:
      print >>error_fh, ("Error parsing yaml file:\n%s" % e)

  def _GetActionDescriptions(self):
    """Returns a formatted string containing the short_descs for all actions."""
    action_names = self.actions.keys()
    action_names.sort()
    desc = ""
    for action_name in action_names:
      desc += "  %s: %s\n" % (action_name, self.actions[action_name].short_desc)
    return desc

  def _GetOptionParser(self):
    """Creates an OptionParser with generic usage and description strings.

    Returns:
      An OptionParser instance.
    """

    class Formatter(optparse.IndentedHelpFormatter):
      """Custom help formatter that does not reformat the description."""
      def format_description(self, description):
        return description + "\n"

    desc = self._GetActionDescriptions()
    desc = ("Action must be one of:\n%s"
            "Use 'help <action>' for a detailed description.") % desc

    parser = self.parser_class(usage="%prog [options] <action>",
                               description=desc,
                               formatter=Formatter(),
                               conflict_handler="resolve")
    parser.add_option("-h", "--help", action="store_true",
                      dest="help", help="Show the help message and exit.")
    parser.add_option("-q", "--quiet", action="store_const", const=0,
                      dest="verbose", help="Print errors only.")
    parser.add_option("-v", "--verbose", action="store_const", const=2,
                      dest="verbose", default=1,
                      help="Print info level logs.")
    parser.add_option("--noisy", action="store_const", const=3,
                      dest="verbose", help="Print all logs.")
    parser.add_option("-s", "--server", action="store", dest="server",
                      default="appengine.google.com",
                      metavar="SERVER", help="The server to upload to.")
    parser.add_option("-e", "--email", action="store", dest="email",
                      metavar="EMAIL", default=None,
                      help="The username to use. Will prompt if omitted.")
    parser.add_option("-H", "--host", action="store", dest="host",
                      metavar="HOST", default=None,
                      help="Overrides the Host header sent with all RPCs.")
    parser.add_option("--no_cookies", action="store_false",
                      dest="save_cookies", default=True,
                      help="Do not save authentication cookies to local disk.")
    parser.add_option("--passin", action="store_true",
                      dest="passin", default=False,
                      help="Read the login password from stdin.")
    return parser

  def _MakeSpecificParser(self, action):
    """Creates a new parser with documentation specific to 'action'.

    Args:
      action: An Action instance to be used when initializing the new parser.

    Returns:
      A tuple containing:
      parser: An instance of OptionsParser customized to 'action'.
      options: The command line options after re-parsing.
    """
    parser = self._GetOptionParser()
    parser.set_usage(action.usage)
    parser.set_description("%s\n%s" % (action.short_desc, action.long_desc))
    action.options(self, parser)
    options, args = parser.parse_args(self.argv[1:])
    return parser, options

  def _PrintHelpAndExit(self, exit_code=2):
    """Prints the parser's help message and exits the program.

    Args:
      exit_code: The integer code to pass to sys.exit().
    """
    self.parser.print_help()
    sys.exit(exit_code)

  def _GetRpcServer(self):
    """Returns an instance of an AbstractRpcServer.

    Returns:
      A new AbstractRpcServer, on which RPC calls can be made.
    """

    def GetUserCredentials():
      """Prompts the user for a username and password."""
      email = self.options.email
      if email is None:
        email = self.raw_input_fn("Email: ")

      password_prompt = "Password for %s: " % email
      if self.options.passin:
        password = self.raw_input_fn(password_prompt)
      else:
        password = self.password_input_fn(password_prompt)

      return (email, password)

    if self.options.host and self.options.host == "localhost":
      email = self.options.email
      if email is None:
        email = "test@example.com"
        logging.info("Using debug user %s.  Override with --email" % email)
      server = self.rpc_server_class(
          self.options.server,
          lambda: (email, "password"),
          host_override=self.options.host,
          extra_headers={"Cookie": 'dev_appserver_login="%s:False"' % email},
          save_cookies=self.options.save_cookies)
      server.authenticated = True
      return server

    return self.rpc_server_class(self.options.server, GetUserCredentials,
                                 host_override=self.options.host,
                                 save_cookies=self.options.save_cookies)

  def _FindYaml(self, basepath, file_name):
    """Find yaml files in application directory.

    Args:
      basepath: Base application directory.
      file_name: Filename without extension to search for.

    Returns:
      Path to located yaml file if one exists, else None.
    """
    if not os.path.isdir(basepath):
      self.parser.error("Not a directory: %s" % basepath)

    for yaml_file in (file_name + '.yaml', file_name + '.yml'):
      yaml_path = os.path.join(basepath, yaml_file)
      if os.path.isfile(yaml_path):
        return yaml_path

    return None

  def _ParseAppYaml(self, basepath):
    """Parses the app.yaml file.

    Returns:
      An AppInfoExternal object.
    """
    appyaml_filename = self._FindYaml(basepath, "app")
    if appyaml_filename is None:
      self.parser.error("Directory does not contain an app.yaml "
                        "configuration file.")

    fh = open(appyaml_filename, "r")
    try:
      appyaml = appinfo.LoadSingleAppInfo(fh)
    finally:
      fh.close()
    return appyaml

  def _ParseIndexYaml(self, basepath):
    """Parses the index.yaml file.

    Returns:
      A single parsed yaml file or None if the file does not exist.
    """
    file_name = self._FindYaml(basepath, "index")
    if file_name is not None:
      fh = open(file_name, "r")
      try:
        index_defs = datastore_index.ParseIndexDefinitions(fh)
      finally:
        fh.close()
      return index_defs
    return None

  def Help(self):
    """Prints help for a specific action.

    Expects self.args[0] to contain the name of the action in question.
    Exits the program after printing the help message.
    """
    if len(self.args) != 1 or self.args[0] not in self.actions:
      self.parser.error("Expected a single action argument. Must be one of:\n" +
                        self._GetActionDescriptions())

    action = self.actions[self.args[0]]
    self.parser, options = self._MakeSpecificParser(action)
    self._PrintHelpAndExit(exit_code=0)

  def Update(self):
    """Updates and deploys a new appversion."""
    if len(self.args) != 1:
      self.parser.error("Expected a single <directory> argument.")

    basepath = self.args[0]
    appyaml = self._ParseAppYaml(basepath)
    rpc_server = self._GetRpcServer()

    updatecheck = UpdateCheck(rpc_server, appyaml)
    updatecheck.CheckForUpdates()

    appversion = AppVersionUpload(rpc_server, appyaml)
    appversion.DoUpload(FileIterator(basepath), self.options.max_size,
                        lambda path: open(os.path.join(basepath, path), "rb"))

    index_defs = self._ParseIndexYaml(basepath)
    if index_defs:
      index_upload = IndexDefinitionUpload(rpc_server, appyaml, index_defs)
      index_upload.DoUpload()

  def _UpdateOptions(self, parser):
    """Adds update-specific options to 'parser'.

    Args:
      parser: An instance of OptionsParser.
    """
    parser.add_option("-S", "--max_size", type="int", dest="max_size",
                      default=1048576, metavar="SIZE",
                      help="Maximum size of a file to upload.")

  def VacuumIndexes(self):
    """Deletes unused indexes."""
    if len(self.args) != 1:
      self.parser.error("Expected a single <directory> argument.")

    basepath = self.args[0]
    config = self._ParseAppYaml(basepath)

    index_defs = self._ParseIndexYaml(basepath)
    if index_defs is None:
      index_defs = datastore_index.IndexDefinitions()

    rpc_server = self._GetRpcServer()
    vacuum = VacuumIndexesOperation(rpc_server,
                                    config,
                                    self.options.force_delete)
    vacuum.DoVacuum(index_defs)

  def _VacuumIndexesOptions(self, parser):
    """Adds index-delete-specific options to 'parser'.

    Args:
      parser: An instance of OptionsParser.
    """
    parser.add_option("-f", "--force", action="store_true", dest="force_delete",
                      default=False,
                      help="Force deletion without being prompted.")

  def UpdateIndexes(self):
    """Updates indexes."""
    if len(self.args) != 1:
      self.parser.error("Expected a single <directory> argument.")

    basepath = self.args[0]
    appyaml = self._ParseAppYaml(basepath)
    rpc_server = self._GetRpcServer()

    index_defs = self._ParseIndexYaml(basepath)
    if index_defs:
      index_upload = IndexDefinitionUpload(rpc_server, appyaml, index_defs)
      index_upload.DoUpload()

  def Rollback(self):
    """Does a rollback of any existing transaction for this app version."""
    if len(self.args) != 1:
      self.parser.error("Expected a single <directory> argument.")

    basepath = self.args[0]
    appyaml = self._ParseAppYaml(basepath)

    appversion = AppVersionUpload(self._GetRpcServer(), appyaml)
    appversion.in_transaction = True
    appversion.Rollback()

  class Action(object):
    """Contains information about a command line action.

    Attributes:
      function: An AppCfgApp function that will perform the appropriate
        action.
      usage: A command line usage string.
      short_desc: A one-line description of the action.
      long_desc: A detailed description of the action.  Whitespace and
        formatting will be preserved.
      options: A function that will add extra options to a given OptionParser
        object.
    """

    def __init__(self, function, usage, short_desc, long_desc="",
                 options=lambda obj, parser: None):
      """Initializer for the class attributes."""
      self.function = function
      self.usage = usage
      self.short_desc = short_desc
      self.long_desc = long_desc
      self.options = options

  actions = {
      "help": Action(
        function=Help,
        usage="%prog help <action>",
        short_desc="Print help for a specific action."),
      "update": Action(
        function=Update,
        usage="%prog [options] update <directory>",
        options=_UpdateOptions,
        short_desc="Create or update an app version.",
        long_desc="""
Specify a directory that contains all of the files required by
the app, and appcfg.py will create/update the app version referenced
in the app.yaml file at the top level of that directory.  appcfg.py
will follow symlinks and recursively upload all files to the server.
Temporary or source control files (e.g. foo~, .svn/*) will be skipped."""),
      "update_indexes": Action(
        function=UpdateIndexes,
        usage="%prog [options] update_indexes <directory>",
        short_desc="Update application indexes.",
        long_desc="""
The 'update_indexes' command will add additional indexes which are not currently
in production as well as restart any indexes that were not completed."""),
      "vacuum_indexes": Action(
        function=VacuumIndexes,
        usage="%prog [options] vacuum_indexes <directory>",
        options=_VacuumIndexesOptions,
        short_desc="Delete unused indexes from application.",
        long_desc="""
The 'vacuum_indexes' command will help clean up indexes which are no longer
in use.  It does this by comparing the local index configuration with
indexes that are actually defined on the server.  If any indexes on the
server do not exist in the index configuration file, the user is given the
option to delete them."""),
      "rollback": Action(
        function=Rollback,
        usage="%prog [options] rollback <directory>",
        short_desc="Rollback an in-progress update.",
        long_desc="""
The 'update' command requires a server-side transaction.  Use 'rollback'
if you get an error message about another transaction being in progress
and you are sure that there is no such transaction."""),
  }


def main(argv):
  logging.basicConfig(format=("%(asctime)s %(levelname)s %(filename)s:"
                              "%(lineno)s %(message)s "))
  try:
    AppCfgApp(argv).Run()
  except KeyboardInterrupt:
    StatusUpdate("Interrupted.")
    sys.exit(1)


if __name__ == "__main__":
  main(sys.argv)
