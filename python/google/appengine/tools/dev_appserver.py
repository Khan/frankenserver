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
"""Pure-Python application server for testing applications locally.

Given a port and the paths to a valid application directory (with an 'app.yaml'
file), the external library directory, and a relative URL to use for logins,
creates an HTTP server that can be used to test an application locally. Uses
stubs instead of actual APIs when SetupStubs() is called first.

Example:
  root_path = '/path/to/application/directory'
  login_url = '/login'
  port = 8080
  template_dir = '/path/to/appserver/templates'
  server = dev_appserver.CreateServer(root_path, login_url, port, template_dir)
  server.serve_forever()
"""


from google.appengine.tools import os_compat

import __builtin__
import BaseHTTPServer
import Cookie
import cStringIO
import cgi
import cgitb
import dummy_thread
import email.Utils
import errno
import httplib
import imp
import inspect
import itertools
import locale
import logging
import mimetools
import mimetypes
import os
import pickle
import pprint
import random

import re
import sre_compile
import sre_constants
import sre_parse

import mimetypes
import socket
import sys
import time
import traceback
import types
import urlparse
import urllib

import google
from google.pyglib import gexcept

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import appinfo
from google.appengine.api import croninfo
from google.appengine.api import datastore_admin
from google.appengine.api import datastore_file_stub
from google.appengine.api import mail_stub
from google.appengine.api import urlfetch_stub
from google.appengine.api import user_service_stub
from google.appengine.api import yaml_errors
from google.appengine.api.capabilities import capability_stub
from google.appengine.api.memcache import memcache_stub

from google.appengine import dist

from google.appengine.tools import dev_appserver_index
from google.appengine.tools import dev_appserver_login


PYTHON_LIB_VAR = '$PYTHON_LIB'
DEVEL_CONSOLE_PATH = PYTHON_LIB_VAR + '/google/appengine/ext/admin'

FILE_MISSING_EXCEPTIONS = frozenset([errno.ENOENT, errno.ENOTDIR])

MAX_URL_LENGTH = 2047

HEADER_TEMPLATE = 'logging_console_header.html'
SCRIPT_TEMPLATE = 'logging_console.js'
MIDDLE_TEMPLATE = 'logging_console_middle.html'
FOOTER_TEMPLATE = 'logging_console_footer.html'

DEFAULT_ENV = {
  'GATEWAY_INTERFACE': 'CGI/1.1',
  'AUTH_DOMAIN': 'gmail.com',
  'TZ': 'UTC',
}

for ext, mime_type in (('.asc', 'text/plain'),
                       ('.diff', 'text/plain'),
                       ('.csv', 'text/comma-separated-values'),
                       ('.rss', 'application/rss+xml'),
                       ('.text', 'text/plain'),
                       ('.wbmp', 'image/vnd.wap.wbmp')):
  mimetypes.add_type(mime_type, ext)

MAX_RUNTIME_RESPONSE_SIZE = 10 << 20

MAX_REQUEST_SIZE = 10 * 1024 * 1024

API_VERSION = '1'


class Error(Exception):
  """Base-class for exceptions in this module."""

class InvalidAppConfigError(Error):
  """The supplied application configuration file is invalid."""

class AppConfigNotFoundError(Error):
  """Application configuration file not found."""

class TemplatesNotLoadedError(Error):
  """Templates for the debugging console were not loaded."""


def SplitURL(relative_url):
  """Splits a relative URL into its path and query-string components.

  Args:
    relative_url: String containing the relative URL (often starting with '/')
      to split. Should be properly escaped as www-form-urlencoded data.

  Returns:
    Tuple (script_name, query_string) where:
      script_name: Relative URL of the script that was accessed.
      query_string: String containing everything after the '?' character.
  """
  scheme, netloc, path, query, fragment = urlparse.urlsplit(relative_url)
  return path, query


def GetFullURL(server_name, server_port, relative_url):
  """Returns the full, original URL used to access the relative URL.

  Args:
    server_name: Name of the local host, or the value of the 'host' header
      from the request.
    server_port: Port on which the request was served (string or int).
    relative_url: Relative URL that was accessed, including query string.

  Returns:
    String containing the original URL.
  """
  if str(server_port) != '80':
    netloc = '%s:%s' % (server_name, server_port)
  else:
    netloc = server_name
  return 'http://%s%s' % (netloc, relative_url)


class URLDispatcher(object):
  """Base-class for handling HTTP requests."""

  def Dispatch(self,
               relative_url,
               path,
               headers,
               infile,
               outfile,
               base_env_dict=None):
    """Dispatch and handle an HTTP request.

    base_env_dict should contain at least these CGI variables:
      REQUEST_METHOD, REMOTE_ADDR, SERVER_SOFTWARE, SERVER_NAME,
      SERVER_PROTOCOL, SERVER_PORT

    Args:
      relative_url: String containing the URL accessed.
      path: Local path of the resource that was matched; back-references will be
        replaced by values matched in the relative_url. Path may be relative
        or absolute, depending on the resource being served (e.g., static files
        will have an absolute path; scripts will be relative).
      headers: Instance of mimetools.Message with headers from the request.
      infile: File-like object with input data from the request.
      outfile: File-like object where output data should be written.
      base_env_dict: Dictionary of CGI environment parameters if available.
        Defaults to None.

    Returns:
      None if request handling is complete.
      Tuple (path, headers, input_file) for an internal redirect:
        path: Path of URL to redirect to.
        headers: Headers to send to other dispatcher.
        input_file: New input to send to new dispatcher.
    """
    raise NotImplementedError

  def EndRedirect(self, dispatched_output, original_output):
    """Process the end of an internal redirect.

    This method is called after all subsequent dispatch requests have finished.
    By default the output from the dispatched process is copied to the original.

    This will not be called on dispatchers that do not return an internal
    redirect.

    Args:
      dispatched_output: StringIO buffer containing the results from the
       dispatched
    """
    original_output.write(dispatched_output.read())


class URLMatcher(object):
  """Matches an arbitrary URL using a list of URL patterns from an application.

  Each URL pattern has an associated URLDispatcher instance and path to the
  resource's location on disk. See AddURL for more details. The first pattern
  that matches an inputted URL will have its associated values returned by
  Match().
  """

  def __init__(self):
    """Initializer."""
    self._url_patterns = []

  def AddURL(self, regex, dispatcher, path, requires_login, admin_only):
    """Adds a URL pattern to the list of patterns.

    If the supplied regex starts with a '^' or ends with a '$' an
    InvalidAppConfigError exception will be raised. Start and end symbols
    and implicitly added to all regexes, meaning we assume that all regexes
    consume all input from a URL.

    Args:
      regex: String containing the regular expression pattern.
      dispatcher: Instance of URLDispatcher that should handle requests that
        match this regex.
      path: Path on disk for the resource. May contain back-references like
        r'\1', r'\2', etc, which will be replaced by the corresponding groups
        matched by the regex if present.
      requires_login: True if the user must be logged-in before accessing this
        URL; False if anyone can access this URL.
      admin_only: True if the user must be a logged-in administrator to
        access the URL; False if anyone can access the URL.
    """
    if not isinstance(dispatcher, URLDispatcher):
      raise TypeError, 'dispatcher must be a URLDispatcher sub-class'

    if regex.startswith('^') or regex.endswith('$'):
      raise InvalidAppConfigError, 'regex starts with "^" or ends with "$"'

    adjusted_regex = '^%s$' % regex

    try:
      url_re = re.compile(adjusted_regex)
    except re.error, e:
      raise InvalidAppConfigError, 'regex invalid: %s' % e

    match_tuple = (url_re, dispatcher, path, requires_login, admin_only)
    self._url_patterns.append(match_tuple)

  def Match(self,
            relative_url,
            split_url=SplitURL):
    """Matches a URL from a request against the list of URL patterns.

    The supplied relative_url may include the query string (i.e., the '?'
    character and everything following).

    Args:
      relative_url: Relative URL being accessed in a request.

    Returns:
      Tuple (dispatcher, matched_path, requires_login, admin_only), which are
      the corresponding values passed to AddURL when the matching URL pattern
      was added to this matcher. The matched_path will have back-references
      replaced using values matched by the URL pattern. If no match was found,
      dispatcher will be None.
    """
    adjusted_url, query_string = split_url(relative_url)

    for url_tuple in self._url_patterns:
      url_re, dispatcher, path, requires_login, admin_only = url_tuple
      the_match = url_re.match(adjusted_url)

      if the_match:
        adjusted_path = the_match.expand(path)
        return dispatcher, adjusted_path, requires_login, admin_only

    return None, None, None, None

  def GetDispatchers(self):
    """Retrieves the URLDispatcher objects that could be matched.

    Should only be used in tests.

    Returns:
      A set of URLDispatcher objects.
    """
    return set([url_tuple[1] for url_tuple in self._url_patterns])


class MatcherDispatcher(URLDispatcher):
  """Dispatcher across multiple URLMatcher instances."""

  def __init__(self,
               login_url,
               url_matchers,
               get_user_info=dev_appserver_login.GetUserInfo,
               login_redirect=dev_appserver_login.LoginRedirect):
    """Initializer.

    Args:
      login_url: Relative URL which should be used for handling user logins.
      url_matchers: Sequence of URLMatcher objects.
      get_user_info, login_redirect: Used for dependency injection.
    """
    self._login_url = login_url
    self._url_matchers = tuple(url_matchers)
    self._get_user_info = get_user_info
    self._login_redirect = login_redirect

  def Dispatch(self,
               relative_url,
               path,
               headers,
               infile,
               outfile,
               base_env_dict=None):
    """Dispatches a request to the first matching dispatcher.

    Matchers are checked in the order they were supplied to the constructor.
    If no matcher matches, a 404 error will be written to the outfile. The
    path variable supplied to this method is ignored.
    """
    cookies = ', '.join(headers.getheaders('cookie'))
    email, admin = self._get_user_info(cookies)

    for matcher in self._url_matchers:
      dispatcher, matched_path, requires_login, admin_only = matcher.Match(relative_url)
      if dispatcher is None:
        continue

      logging.debug('Matched "%s" to %s with path %s',
                    relative_url, dispatcher, matched_path)

      if (requires_login or admin_only) and not email:
        logging.debug('Login required, redirecting user')
        self._login_redirect(
          self._login_url,
          base_env_dict['SERVER_NAME'],
          base_env_dict['SERVER_PORT'],
          relative_url,
          outfile)
      elif admin_only and not admin:
        outfile.write('Status: %d Not authorized\r\n'
                      '\r\n'
                      'Current logged in user %s is not '
                      'authorized to view this page.'
                      % (httplib.FORBIDDEN, email))
      else:
        forward = dispatcher.Dispatch(relative_url,
                                      matched_path,
                                      headers,
                                      infile,
                                      outfile,
                                      base_env_dict=base_env_dict)

        if forward:
          new_path, new_headers, new_input = forward
          logging.info('Internal redirection to %s' % new_path)
          new_outfile = cStringIO.StringIO()
          self.Dispatch(new_path,
                        None,
                        new_headers,
                        new_input,
                        new_outfile,
                        dict(base_env_dict))
          new_outfile.seek(0)
          dispatcher.EndRedirect(new_outfile, outfile)

      return

    outfile.write('Status: %d URL did not match\r\n'
                  '\r\n'
                  'Not found error: %s did not match any patterns '
                  'in application configuration.'
                  % (httplib.NOT_FOUND, relative_url))


class ApplicationLoggingHandler(logging.Handler):
  """Python Logging handler that displays the debugging console to users."""

  _COOKIE_NAME = '_ah_severity'

  _TEMPLATES_INITIALIZED = False
  _HEADER = None
  _SCRIPT = None
  _MIDDLE = None
  _FOOTER = None

  @staticmethod
  def InitializeTemplates(header, script, middle, footer):
    """Initializes the templates used to render the debugging console.

    This method must be called before any ApplicationLoggingHandler instances
    are created.

    Args:
      header: The header template that is printed first.
      script: The script template that is printed after the logging messages.
      middle: The middle element that's printed before the footer.
      footer; The last element that's printed at the end of the document.
    """
    ApplicationLoggingHandler._HEADER = header
    ApplicationLoggingHandler._SCRIPT = script
    ApplicationLoggingHandler._MIDDLE = middle
    ApplicationLoggingHandler._FOOTER = footer
    ApplicationLoggingHandler._TEMPLATES_INITIALIZED = True

  @staticmethod
  def AreTemplatesInitialized():
    """Returns True if InitializeTemplates has been called, False otherwise."""
    return ApplicationLoggingHandler._TEMPLATES_INITIALIZED

  def __init__(self, *args, **kwargs):
    """Initializer.

    Args:
      args, kwargs: See logging.Handler.

    Raises:
      TemplatesNotLoadedError exception if the InitializeTemplates method was
      not called before creating this instance.
    """
    if not self._TEMPLATES_INITIALIZED:
      raise TemplatesNotLoadedError

    logging.Handler.__init__(self, *args, **kwargs)
    self._record_list = []
    self._start_time = time.time()

  def emit(self, record):
    """Called by the logging module each time the application logs a message.

    Args:
      record: logging.LogRecord instance corresponding to the newly logged
        message.
    """
    self._record_list.append(record)

  def AddDebuggingConsole(self, relative_url, env, outfile):
    """Prints an HTML debugging console to an output stream, if requested.

    Args:
      relative_url: Relative URL that was accessed, including the query string.
        Used to determine if the parameter 'debug' was supplied, in which case
        the console will be shown.
      env: Dictionary containing CGI environment variables. Checks for the
        HTTP_COOKIE entry to see if the accessing user has any logging-related
        cookies set.
      outfile: Output stream to which the console should be written if either
        a debug parameter was supplied or a logging cookie is present.
    """
    script_name, query_string = SplitURL(relative_url)
    param_dict = cgi.parse_qs(query_string, True)
    cookie_dict = Cookie.SimpleCookie(env.get('HTTP_COOKIE', ''))
    if 'debug' not in param_dict and self._COOKIE_NAME not in cookie_dict:
      return

    outfile.write(self._HEADER)
    for record in self._record_list:
      self._PrintRecord(record, outfile)

    outfile.write(self._MIDDLE)
    outfile.write(self._SCRIPT)
    outfile.write(self._FOOTER)

  def _PrintRecord(self, record, outfile):
    """Prints a single logging record to an output stream.

    Args:
      record: logging.LogRecord instance to print.
      outfile: Output stream to which the LogRecord should be printed.
    """
    message = cgi.escape(record.getMessage())
    level_name = logging.getLevelName(record.levelno).lower()
    level_letter = level_name[:1].upper()
    time_diff = record.created - self._start_time
    outfile.write('<span class="_ah_logline_%s">\n' % level_name)
    outfile.write('<span class="_ah_logline_%s_prefix">%2.5f %s &gt;</span>\n'
                  % (level_name, time_diff, level_letter))
    outfile.write('%s\n' % message)
    outfile.write('</span>\n')


_IGNORE_REQUEST_HEADERS = frozenset(['content-type', 'content-length',
                                     'accept-encoding', 'transfer-encoding'])

def SetupEnvironment(cgi_path,
                     relative_url,
                     headers,
                     split_url=SplitURL,
                     get_user_info=dev_appserver_login.GetUserInfo):
  """Sets up environment variables for a CGI.

  Args:
    cgi_path: Full file-system path to the CGI being executed.
    relative_url: Relative URL used to access the CGI.
    headers: Instance of mimetools.Message containing request headers.
    split_url, get_user_info: Used for dependency injection.

  Returns:
    Dictionary containing CGI environment variables.
  """
  env = DEFAULT_ENV.copy()

  script_name, query_string = split_url(relative_url)

  env['SCRIPT_NAME'] = ''
  env['QUERY_STRING'] = query_string
  env['PATH_INFO'] = urllib.unquote(script_name)
  env['PATH_TRANSLATED'] = cgi_path
  env['CONTENT_TYPE'] = headers.getheader('content-type',
                                          'application/x-www-form-urlencoded')
  env['CONTENT_LENGTH'] = headers.getheader('content-length', '')

  cookies = ', '.join(headers.getheaders('cookie'))
  email, admin = get_user_info(cookies)
  env['USER_EMAIL'] = email
  if admin:
    env['USER_IS_ADMIN'] = '1'

  for key in headers:
    if key in _IGNORE_REQUEST_HEADERS:
      continue
    adjusted_name = key.replace('-', '_').upper()
    env['HTTP_' + adjusted_name] = ', '.join(headers.getheaders(key))

  return env


def NotImplementedFake(*args, **kwargs):
  """Fake for methods/functions that are not implemented in the production
  environment.
  """
  raise NotImplementedError("This class/method is not available.")


class NotImplementedFakeClass(object):
  """Fake class for classes that are not implemented in the production
  environment.
  """
  __init__ = NotImplementedFake


def IsEncodingsModule(module_name):
  """Determines if the supplied module is related to encodings in any way.

  Encodings-related modules cannot be reloaded, so they need to be treated
  specially when sys.modules is modified in any way.

  Args:
    module_name: Absolute name of the module regardless of how it is imported
      into the local namespace (e.g., foo.bar.baz).

  Returns:
    True if it's an encodings-related module; False otherwise.
  """
  if (module_name in ('codecs', 'encodings') or
      module_name.startswith('encodings.')):
    return True
  return False


def ClearAllButEncodingsModules(module_dict):
  """Clear all modules in a module dictionary except for those modules that
  are in any way related to encodings.

  Args:
    module_dict: Dictionary in the form used by sys.modules.
  """
  for module_name in module_dict.keys():
    if not IsEncodingsModule(module_name):
      del module_dict[module_name]


def FakeURandom(n):
  """Fake version of os.urandom."""
  bytes = ''
  for i in xrange(n):
    bytes += chr(random.randint(0, 255))
  return bytes


def FakeUname():
  """Fake version of os.uname."""
  return ('Linux', '', '', '', '')


def FakeUnlink(path):
  """Fake version of os.unlink."""
  if os.path.isdir(path):
    raise OSError(2, "Is a directory", path)
  else:
    raise OSError(1, "Operation not permitted", path)


def FakeReadlink(path):
  """Fake version of os.readlink."""
  raise OSError(22, "Invalid argument", path)


def FakeAccess(path, mode):
  """Fake version of os.access where only reads are supported."""
  if not os.path.exists(path) or mode != os.R_OK:
    return False
  else:
    return True


def FakeSetLocale(category, value=None, original_setlocale=locale.setlocale):
  """Fake version of locale.setlocale that only supports the default."""
  if value not in (None, '', 'C', 'POSIX'):
    raise locale.Error, 'locale emulation only supports "C" locale'
  return original_setlocale(category, 'C')


def IsPathInSubdirectories(filename,
                           subdirectories,
                           normcase=os.path.normcase):
  """Determines if a filename is contained within one of a set of directories.

  Args:
    filename: Path of the file (relative or absolute).
    subdirectories: Iterable collection of paths to subdirectories which the
      given filename may be under.
    normcase: Used for dependency injection.

  Returns:
    True if the supplied filename is in one of the given sub-directories or
    its hierarchy of children. False otherwise.
  """
  file_dir = normcase(os.path.dirname(os.path.abspath(filename)))
  for parent in subdirectories:
    fixed_parent = normcase(os.path.abspath(parent))
    if os.path.commonprefix([file_dir, fixed_parent]) == fixed_parent:
      return True
  return False

SHARED_MODULE_PREFIXES = set([
  'google',
  'logging',
  'sys',
  'warnings',




  're',
  'sre_compile',
  'sre_constants',
  'sre_parse',




  'wsgiref',
])

NOT_SHARED_MODULE_PREFIXES = set([
  'google.appengine.ext',
])


def ModuleNameHasPrefix(module_name, prefix_set):
  """Determines if a module's name belongs to a set of prefix strings.

  Args:
    module_name: String containing the fully qualified module name.
    prefix_set: Iterable set of module name prefixes to check against.

  Returns:
    True if the module_name belongs to the prefix set or is a submodule of
    any of the modules specified in the prefix_set. Otherwise False.
  """
  for prefix in prefix_set:
    if prefix == module_name:
      return True

    if module_name.startswith(prefix + '.'):
      return True

  return False


def SetupSharedModules(module_dict):
  """Creates a module dictionary for the hardened part of the process.

  Module dictionary will contain modules that should be shared between the
  hardened and unhardened parts of the process.

  Args:
    module_dict: Module dictionary from which existing modules should be
      pulled (usually sys.modules).

  Returns:
    A new module dictionary.
  """
  output_dict = {}
  for module_name, module in module_dict.iteritems():
    if module is None:
      continue

    if IsEncodingsModule(module_name):
      output_dict[module_name] = module
      continue

    shared_prefix = ModuleNameHasPrefix(module_name, SHARED_MODULE_PREFIXES)
    banned_prefix = ModuleNameHasPrefix(module_name, NOT_SHARED_MODULE_PREFIXES)

    if shared_prefix and not banned_prefix:
      output_dict[module_name] = module

  return output_dict


class FakeFile(file):
  """File sub-class that enforces the security restrictions of the production
  environment.
  """

  ALLOWED_MODES = frozenset(['r', 'rb', 'U', 'rU'])

  ALLOWED_FILES = set(os.path.normcase(filename)
                      for filename in mimetypes.knownfiles
                      if os.path.isfile(filename))

  ALLOWED_DIRS = set([
    os.path.normcase(os.path.realpath(os.path.dirname(os.__file__))),
    os.path.normcase(os.path.abspath(os.path.dirname(os.__file__))),
  ])

  NOT_ALLOWED_DIRS = set([




    os.path.normcase(os.path.join(os.path.dirname(os.__file__),
                                  'site-packages'))
  ])

  ALLOWED_SITE_PACKAGE_DIRS = set(
    os.path.normcase(os.path.abspath(os.path.join(
      os.path.dirname(os.__file__), 'site-packages', path)))
    for path in [

  ])

  _original_file = file

  _root_path = None
  _application_paths = None
  _skip_files = None
  _static_file_config_matcher = None

  _allow_skipped_files = True

  _availability_cache = {}

  @staticmethod
  def SetAllowedPaths(root_path, application_paths):
    """Configures which paths are allowed to be accessed.

    Must be called at least once before any file objects are created in the
    hardened environment.

    Args:
      root_path: Absolute path to the root of the application.
      application_paths: List of additional paths that the application may
                         access, this must include the App Engine runtime but
                         not the Python library directories.
    """
    FakeFile._application_paths = (set(os.path.realpath(path)
                                       for path in application_paths) |
                                   set(os.path.abspath(path)
                                       for path in application_paths))
    FakeFile._application_paths.add(root_path)

    FakeFile._root_path = os.path.join(root_path, '')

    FakeFile._availability_cache = {}

  @staticmethod
  def SetAllowSkippedFiles(allow_skipped_files):
    """Configures access to files matching FakeFile._skip_files

    Args:
      allow_skipped_files: Boolean whether to allow access to skipped files
    """
    FakeFile._allow_skipped_files = allow_skipped_files
    FakeFile._availability_cache = {}

  @staticmethod
  def SetSkippedFiles(skip_files):
    """Sets which files in the application directory are to be ignored.

    Must be called at least once before any file objects are created in the
    hardened environment.

    Must be called whenever the configuration was updated.

    Args:
      skip_files: Object with .match() method (e.g. compiled regexp).
    """
    FakeFile._skip_files = skip_files
    FakeFile._availability_cache = {}

  @staticmethod
  def SetStaticFileConfigMatcher(static_file_config_matcher):
    """Sets StaticFileConfigMatcher instance for checking if a file is static.

    Must be called at least once before any file objects are created in the
    hardened environment.

    Must be called whenever the configuration was updated.

    Args:
      static_file_config_matcher: StaticFileConfigMatcher instance.
    """
    FakeFile._static_file_config_matcher = static_file_config_matcher
    FakeFile._availability_cache = {}

  @staticmethod
  def IsFileAccessible(filename, normcase=os.path.normcase):
    """Determines if a file's path is accessible.

    SetAllowedPaths(), SetSkippedFiles() and SetStaticFileConfigMatcher() must
    be called before this method or else all file accesses will raise an error.

    Args:
      filename: Path of the file to check (relative or absolute). May be a
        directory, in which case access for files inside that directory will
        be checked.
      normcase: Used for dependency injection.

    Returns:
      True if the file is accessible, False otherwise.
    """
    logical_filename = normcase(os.path.abspath(filename))

    if os.path.isdir(logical_filename):
      logical_filename = os.path.join(logical_filename, 'foo')

    result = FakeFile._availability_cache.get(logical_filename)
    if result is None:
      result = FakeFile._IsFileAccessibleNoCache(logical_filename,
                                                 normcase=normcase)
      FakeFile._availability_cache[logical_filename] = result
    return result

  @staticmethod
  def _IsFileAccessibleNoCache(logical_filename, normcase=os.path.normcase):
    """Determines if a file's path is accessible.

    This is an internal part of the IsFileAccessible implementation.

    Args:
      logical_filename: Absolute path of the file to check.
      normcase: Used for dependency injection.

    Returns:
      True if the file is accessible, False otherwise.
    """
    if IsPathInSubdirectories(logical_filename, [FakeFile._root_path],
                              normcase=normcase):
      relative_filename = logical_filename[len(FakeFile._root_path):]

      if (not FakeFile._allow_skipped_files and
          FakeFile._skip_files.match(relative_filename)):
        logging.warning('Blocking access to skipped file "%s"',
                        logical_filename)
        return False

      if FakeFile._static_file_config_matcher.IsStaticFile(relative_filename):
        logging.warning('Blocking access to static file "%s"',
                        logical_filename)
        return False

    if logical_filename in FakeFile.ALLOWED_FILES:
      return True

    if IsPathInSubdirectories(logical_filename,
                              FakeFile.ALLOWED_SITE_PACKAGE_DIRS,
                              normcase=normcase):
      return True

    allowed_dirs = FakeFile._application_paths | FakeFile.ALLOWED_DIRS
    if (IsPathInSubdirectories(logical_filename,
                               allowed_dirs,
                               normcase=normcase) and
        not IsPathInSubdirectories(logical_filename,
                                   FakeFile.NOT_ALLOWED_DIRS,
                                   normcase=normcase)):
      return True

    return False

  def __init__(self, filename, mode='r', bufsize=-1, **kwargs):
    """Initializer. See file built-in documentation."""
    if mode not in FakeFile.ALLOWED_MODES:
      raise IOError('invalid mode: %s' % mode)

    if not FakeFile.IsFileAccessible(filename):
      raise IOError(errno.EACCES, 'file not accessible')

    super(FakeFile, self).__init__(filename, mode, bufsize, **kwargs)


class RestrictedPathFunction(object):
  """Enforces access restrictions for functions that have a file or
  directory path as their first argument."""

  _original_os = os

  def __init__(self, original_func):
    """Initializer.

    Args:
      original_func: Callable that takes as its first argument the path to a
        file or directory on disk; all subsequent arguments may be variable.
    """
    self._original_func = original_func

  def __call__(self, path, *args, **kwargs):
    """Enforces access permissions for the function passed to the constructor.
    """
    if not FakeFile.IsFileAccessible(path):
      raise OSError(errno.EACCES, 'path not accessible')

    return self._original_func(path, *args, **kwargs)


def GetSubmoduleName(fullname):
  """Determines the leaf submodule name of a full module name.

  Args:
    fullname: Fully qualified module name, e.g. 'foo.bar.baz'

  Returns:
    Submodule name, e.g. 'baz'. If the supplied module has no submodule (e.g.,
    'stuff'), the returned value will just be that module name ('stuff').
  """
  return fullname.rsplit('.', 1)[-1]


class CouldNotFindModuleError(ImportError):
  """Raised when a module could not be found.

  In contrast to when a module has been found, but cannot be loaded because of
  hardening restrictions.
  """


def Trace(func):
  """Decorator that logs the call stack of the HardenedModulesHook class as
  it executes, indenting logging messages based on the current stack depth.
  """
  def decorate(self, *args, **kwargs):
    args_to_show = []
    if args is not None:
      args_to_show.extend(str(argument) for argument in args)
    if kwargs is not None:
      args_to_show.extend('%s=%s' % (key, value)
                          for key, value in kwargs.iteritems())

    args_string = ', '.join(args_to_show)

    self.log('Entering %s(%s)', func.func_name, args_string)
    self._indent_level += 1
    try:
      return func(self, *args, **kwargs)
    finally:
      self._indent_level -= 1
      self.log('Exiting %s(%s)', func.func_name, args_string)

  return decorate


class HardenedModulesHook(object):
  """Meta import hook that restricts the modules used by applications to match
  the production environment.

  Module controls supported:
  - Disallow native/extension modules from being loaded
  - Disallow built-in and/or Python-distributed modules from being loaded
  - Replace modules with completely empty modules
  - Override specific module attributes
  - Replace one module with another

  After creation, this object should be added to the front of the sys.meta_path
  list (which may need to be created). The sys.path_importer_cache dictionary
  should also be cleared, to prevent loading any non-restricted modules.

  See PEP302 for more info on how this works:
    http://www.python.org/dev/peps/pep-0302/
  """

  ENABLE_LOGGING = False

  def log(self, message, *args):
    """Logs an import-related message to stderr, with indentation based on
    current call-stack depth.

    Args:
      message: Logging format string.
      args: Positional format parameters for the logging message.
    """
    if HardenedModulesHook.ENABLE_LOGGING:
      indent = self._indent_level * '  '
      print >>sys.stderr, indent + (message % args)

  _WHITE_LIST_C_MODULES = [
    'array',
    'binascii',
    'bz2',
    'cmath',
    'collections',
    'crypt',
    'cStringIO',
    'datetime',
    'errno',
    'exceptions',
    'gc',
    'itertools',
    'math',
    'md5',
    'operator',
    'posix',
    'posixpath',
    'pyexpat',
    'sha',
    'struct',
    'sys',
    'time',
    'timing',
    'unicodedata',
    'zlib',
    '_bisect',
    '_codecs',
    '_codecs_cn',
    '_codecs_hk',
    '_codecs_iso2022',
    '_codecs_jp',
    '_codecs_kr',
    '_codecs_tw',
    '_collections',
    '_csv',
    '_elementtree',
    '_functools',
    '_hashlib',
    '_heapq',
    '_locale',
    '_lsprof',
    '_md5',
    '_multibytecodec',
    '_random',
    '_sha',
    '_sha256',
    '_sha512',
    '_sre',
    '_struct',
    '_types',
    '_weakref',
    '__main__',
  ]

  _WHITE_LIST_PARTIAL_MODULES = {
    'gc': [
      'enable',
      'disable',
      'isenabled',
      'collect',
      'get_debug',
      'set_threshold',
      'get_threshold',
      'get_count'
    ],



    'os': [
      'access',
      'altsep',
      'curdir',
      'defpath',
      'devnull',
      'environ',
      'error',
      'extsep',
      'EX_NOHOST',
      'EX_NOINPUT',
      'EX_NOPERM',
      'EX_NOUSER',
      'EX_OK',
      'EX_OSERR',
      'EX_OSFILE',
      'EX_PROTOCOL',
      'EX_SOFTWARE',
      'EX_TEMPFAIL',
      'EX_UNAVAILABLE',
      'EX_USAGE',
      'F_OK',
      'getcwd',
      'getcwdu',
      'getenv',
      'listdir',
      'lstat',
      'name',
      'NGROUPS_MAX',
      'O_APPEND',
      'O_CREAT',
      'O_DIRECT',
      'O_DIRECTORY',
      'O_DSYNC',
      'O_EXCL',
      'O_LARGEFILE',
      'O_NDELAY',
      'O_NOCTTY',
      'O_NOFOLLOW',
      'O_NONBLOCK',
      'O_RDONLY',
      'O_RDWR',
      'O_RSYNC',
      'O_SYNC',
      'O_TRUNC',
      'O_WRONLY',
      'pardir',
      'path',
      'pathsep',
      'R_OK',
      'readlink',
      'remove',
      'SEEK_CUR',
      'SEEK_END',
      'SEEK_SET',
      'sep',
      'stat',
      'stat_float_times',
      'stat_result',
      'strerror',
      'TMP_MAX',
      'unlink',
      'urandom',
      'walk',
      'WCOREDUMP',
      'WEXITSTATUS',
      'WIFEXITED',
      'WIFSIGNALED',
      'WIFSTOPPED',
      'WNOHANG',
      'WSTOPSIG',
      'WTERMSIG',
      'WUNTRACED',
      'W_OK',
      'X_OK',
    ],
  }

  _MODULE_OVERRIDES = {
    'locale': {
      'setlocale': FakeSetLocale,
    },

    'os': {
      'access': FakeAccess,
      'listdir': RestrictedPathFunction(os.listdir),

      'lstat': RestrictedPathFunction(os.stat),
      'readlink': FakeReadlink,
      'remove': FakeUnlink,
      'stat': RestrictedPathFunction(os.stat),
      'uname': FakeUname,
      'unlink': FakeUnlink,
      'urandom': FakeURandom,
    },
  }

  _ENABLED_FILE_TYPES = (
    imp.PKG_DIRECTORY,
    imp.PY_SOURCE,
    imp.PY_COMPILED,
    imp.C_BUILTIN,
  )

  def __init__(self,
               module_dict,
               imp_module=imp,
               os_module=os,
               dummy_thread_module=dummy_thread,
               pickle_module=pickle):
    """Initializer.

    Args:
      module_dict: Module dictionary to use for managing system modules.
        Should be sys.modules.
      imp_module, os_module, dummy_thread_module, pickle_module: References to
        modules that exist in the dev_appserver that must be used by this class
        in order to function, even if these modules have been unloaded from
        sys.modules.
    """
    self._module_dict = module_dict
    self._imp = imp_module
    self._os = os_module
    self._dummy_thread = dummy_thread_module
    self._pickle = pickle
    self._indent_level = 0

  @Trace
  def find_module(self, fullname, path=None):
    """See PEP 302."""
    if fullname in ('cPickle', 'thread'):
      return self

    search_path = path
    all_modules = fullname.split('.')
    try:
      for index, current_module in enumerate(all_modules):
        current_module_fullname = '.'.join(all_modules[:index + 1])
        if (current_module_fullname == fullname and not
            self.StubModuleExists(fullname)):
          self.FindModuleRestricted(current_module,
                                    current_module_fullname,
                                    search_path)
        else:
          if current_module_fullname in self._module_dict:
            module = self._module_dict[current_module_fullname]
          else:
            module = self.FindAndLoadModule(current_module,
                                            current_module_fullname,
                                            search_path)

          if hasattr(module, '__path__'):
            search_path = module.__path__
    except CouldNotFindModuleError:
      return None

    return self

  def StubModuleExists(self, name):
    """Check if the named module has a stub replacement."""
    if name in sys.builtin_module_names:
      name = 'py_%s' % name
    if name in dist.__all__:
      return True
    return False

  def ImportStubModule(self, name):
    """Import the stub module replacement for the specified module."""
    if name in sys.builtin_module_names:
      name = 'py_%s' % name
    module = __import__(dist.__name__, {}, {}, [name])
    return getattr(module, name)

  @Trace
  def FixModule(self, module):
    """Prunes and overrides restricted module attributes.

    Args:
      module: The module to prune. This should be a new module whose attributes
        reference back to the real module's __dict__ members.
    """
    if module.__name__ in self._WHITE_LIST_PARTIAL_MODULES:
      allowed_symbols = self._WHITE_LIST_PARTIAL_MODULES[module.__name__]
      for symbol in set(module.__dict__) - set(allowed_symbols):
        if not (symbol.startswith('__') and symbol.endswith('__')):
          del module.__dict__[symbol]

    if module.__name__ in self._MODULE_OVERRIDES:
      module.__dict__.update(self._MODULE_OVERRIDES[module.__name__])

  @Trace
  def FindModuleRestricted(self,
                           submodule,
                           submodule_fullname,
                           search_path):
    """Locates a module while enforcing module import restrictions.

    Args:
      submodule: The short name of the submodule (i.e., the last section of
        the fullname; for 'foo.bar' this would be 'bar').
      submodule_fullname: The fully qualified name of the module to find (e.g.,
        'foo.bar').
      search_path: List of paths to search for to find this module. Should be
        None if the current sys.path should be used.

    Returns:
      Tuple (source_file, pathname, description) where:
        source_file: File-like object that contains the module; in the case
          of packages, this will be None, which implies to look at __init__.py.
        pathname: String containing the full path of the module on disk.
        description: Tuple returned by imp.find_module().
      However, in the case of an import using a path hook (e.g. a zipfile),
      source_file will be a PEP-302-style loader object, pathname will be None,
      and description will be a tuple filled with None values.

    Raises:
      ImportError exception if the requested module was found, but importing
      it is disallowed.

      CouldNotFindModuleError exception if the request module could not even
      be found for import.
    """
    if search_path is None:
      search_path = [None] + sys.path
    for path_entry in search_path:
      result = self.FindPathHook(submodule, submodule_fullname, path_entry)
      if result is not None:
        source_file, pathname, description = result
        if description == (None, None, None):
          return result
        else:
          break
    else:
      self.log('Could not find module "%s"', submodule_fullname)
      raise CouldNotFindModuleError()

    suffix, mode, file_type = description

    if (file_type not in (self._imp.C_BUILTIN, self._imp.C_EXTENSION) and
        not FakeFile.IsFileAccessible(pathname)):
      error_message = 'Access to module file denied: %s' % pathname
      logging.debug(error_message)
      raise ImportError(error_message)

    if (file_type not in self._ENABLED_FILE_TYPES and
        submodule not in self._WHITE_LIST_C_MODULES):
      error_message = ('Could not import "%s": Disallowed C-extension '
                       'or built-in module' % submodule_fullname)
      logging.debug(error_message)
      raise ImportError(error_message)

    return source_file, pathname, description

  def FindPathHook(self, submodule, submodule_fullname, path_entry):
    """Helper for FindModuleRestricted to find a module in a sys.path entry.

    Args:
      submodule:
      submodule_fullname:
      path_entry: A single sys.path entry, or None representing the builtins.

    Returns:
      Either None (if nothing was found), or a triple (source_file, path_name,
      description).  See the doc string for FindModuleRestricted() for the
      meaning of the latter.
    """
    if path_entry is None:
      if submodule_fullname in sys.builtin_module_names:
        try:
          result = self._imp.find_module(submodule)
        except ImportError:
          pass
        else:
          source_file, pathname, description = result
          suffix, mode, file_type = description
          if file_type == self._imp.C_BUILTIN:
            return result
      return None


    if path_entry in sys.path_importer_cache:
      importer = sys.path_importer_cache[path_entry]
    else:
      importer = None
      for hook in sys.path_hooks:
        try:
          importer = hook(path_entry)
          break
        except ImportError:
          pass
      sys.path_importer_cache[path_entry] = importer

    if importer is None:
      try:
        return self._imp.find_module(submodule, [path_entry])
      except ImportError:
        pass
    else:
      loader = importer.find_module(submodule)
      if loader is not None:
        return (loader, None, (None, None, None))

    return None

  @Trace
  def LoadModuleRestricted(self,
                           submodule_fullname,
                           source_file,
                           pathname,
                           description):
    """Loads a module while enforcing module import restrictions.

    As a byproduct, the new module will be added to the module dictionary.

    Args:
      submodule_fullname: The fully qualified name of the module to find (e.g.,
        'foo.bar').
      source_file: File-like object that contains the module's source code,
        or a PEP-302-style loader object.
      pathname: String containing the full path of the module on disk.
      description: Tuple returned by imp.find_module(), or (None, None, None)
        in case source_file is a PEP-302-style loader object.

    Returns:
      The new module.

    Raises:
      ImportError exception of the specified module could not be loaded for
      whatever reason.
    """
    if description == (None, None, None):
      return source_file.load_module(submodule_fullname)

    try:
      try:
        return self._imp.load_module(submodule_fullname,
                                     source_file,
                                     pathname,
                                     description)
      except:
        if submodule_fullname in self._module_dict:
          del self._module_dict[submodule_fullname]
        raise

    finally:
      if source_file is not None:
        source_file.close()

  @Trace
  def FindAndLoadModule(self,
                        submodule,
                        submodule_fullname,
                        search_path):
    """Finds and loads a module, loads it, and adds it to the module dictionary.

    Args:
      submodule: Name of the module to import (e.g., baz).
      submodule_fullname: Full name of the module to import (e.g., foo.bar.baz).
      search_path: Path to use for searching for this submodule. For top-level
        modules this should be None; otherwise it should be the __path__
        attribute from the parent package.

    Returns:
      A new module instance that has been inserted into the module dictionary
      supplied to __init__.

    Raises:
      ImportError exception if the module could not be loaded for whatever
      reason (e.g., missing, not allowed).
    """
    module = self._imp.new_module(submodule_fullname)

    if submodule_fullname == 'thread':
      module.__dict__.update(self._dummy_thread.__dict__)
      module.__name__ = 'thread'
    elif submodule_fullname == 'cPickle':
      module.__dict__.update(self._pickle.__dict__)
      module.__name__ = 'cPickle'
    elif submodule_fullname == 'os':
      module.__dict__.update(self._os.__dict__)
      self._module_dict['os.path'] = module.path
    elif self.StubModuleExists(submodule_fullname):
      module = self.ImportStubModule(submodule_fullname)
    else:
      source_file, pathname, description = self.FindModuleRestricted(submodule, submodule_fullname, search_path)
      module = self.LoadModuleRestricted(submodule_fullname,
                                         source_file,
                                         pathname,
                                         description)

    module.__loader__ = self
    self.FixModule(module)
    if submodule_fullname not in self._module_dict:
      self._module_dict[submodule_fullname] = module

    return module

  @Trace
  def GetParentPackage(self, fullname):
    """Retrieves the parent package of a fully qualified module name.

    Args:
      fullname: Full name of the module whose parent should be retrieved (e.g.,
        foo.bar).

    Returns:
      Module instance for the parent or None if there is no parent module.

    Raise:
      ImportError exception if the module's parent could not be found.
    """
    all_modules = fullname.split('.')
    parent_module_fullname = '.'.join(all_modules[:-1])
    if parent_module_fullname:
      if self.find_module(fullname) is None:
        raise ImportError('Could not find module %s' % fullname)

      return self._module_dict[parent_module_fullname]
    return None

  @Trace
  def GetParentSearchPath(self, fullname):
    """Determines the search path of a module's parent package.

    Args:
      fullname: Full name of the module to look up (e.g., foo.bar).

    Returns:
      Tuple (submodule, search_path) where:
        submodule: The last portion of the module name from fullname (e.g.,
          if fullname is foo.bar, then this is bar).
        search_path: List of paths that belong to the parent package's search
          path or None if there is no parent package.

    Raises:
      ImportError exception if the module or its parent could not be found.
    """
    submodule = GetSubmoduleName(fullname)
    parent_package = self.GetParentPackage(fullname)
    search_path = None
    if parent_package is not None and hasattr(parent_package, '__path__'):
      search_path = parent_package.__path__
    return submodule, search_path

  @Trace
  def GetModuleInfo(self, fullname):
    """Determines the path on disk and the search path of a module or package.

    Args:
      fullname: Full name of the module to look up (e.g., foo.bar).

    Returns:
      Tuple (pathname, search_path, submodule) where:
        pathname: String containing the full path of the module on disk,
          or None if the module wasn't loaded from disk (e.g. from a zipfile).
        search_path: List of paths that belong to the found package's search
          path or None if found module is not a package.
        submodule: The relative name of the submodule that's being imported.
    """
    submodule, search_path = self.GetParentSearchPath(fullname)
    source_file, pathname, description = self.FindModuleRestricted(submodule, fullname, search_path)
    suffix, mode, file_type = description
    module_search_path = None
    if file_type == self._imp.PKG_DIRECTORY:
      module_search_path = [pathname]
      pathname = os.path.join(pathname, '__init__%spy' % os.extsep)
    return pathname, module_search_path, submodule

  @Trace
  def load_module(self, fullname):
    """See PEP 302."""
    all_modules = fullname.split('.')
    submodule = all_modules[-1]
    parent_module_fullname = '.'.join(all_modules[:-1])
    search_path = None
    if parent_module_fullname and parent_module_fullname in self._module_dict:
      parent_module = self._module_dict[parent_module_fullname]
      if hasattr(parent_module, '__path__'):
        search_path = parent_module.__path__

    return self.FindAndLoadModule(submodule, fullname, search_path)

  @Trace
  def is_package(self, fullname):
    """See PEP 302 extensions."""
    submodule, search_path = self.GetParentSearchPath(fullname)
    source_file, pathname, description = self.FindModuleRestricted(submodule, fullname, search_path)
    suffix, mode, file_type = description
    if file_type == self._imp.PKG_DIRECTORY:
      return True
    return False

  @Trace
  def get_source(self, fullname):
    """See PEP 302 extensions."""
    full_path, search_path, submodule = self.GetModuleInfo(fullname)
    if full_path is None:
      return None
    source_file = open(full_path)
    try:
      return source_file.read()
    finally:
      source_file.close()

  @Trace
  def get_code(self, fullname):
    """See PEP 302 extensions."""
    full_path, search_path, submodule = self.GetModuleInfo(fullname)
    if full_path is None:
      return None
    source_file = open(full_path)
    try:
      source_code = source_file.read()
    finally:
      source_file.close()

    source_code = source_code.replace('\r\n', '\n')
    if not source_code.endswith('\n'):
      source_code += '\n'

    return compile(source_code, full_path, 'exec')


def ModuleHasValidMainFunction(module):
  """Determines if a module has a main function that takes no arguments.

  This includes functions that have arguments with defaults that are all
  assigned, thus requiring no additional arguments in order to be called.

  Args:
    module: A types.ModuleType instance.

  Returns:
    True if the module has a valid, reusable main function; False otherwise.
  """
  if hasattr(module, 'main') and type(module.main) is types.FunctionType:
    arg_names, var_args, var_kwargs, default_values = inspect.getargspec(module.main)
    if len(arg_names) == 0:
      return True
    if default_values is not None and len(arg_names) == len(default_values):
      return True
  return False


def GetScriptModuleName(handler_path):
  """Determines the fully-qualified Python module name of a script on disk.

  Args:
    handler_path: CGI path stored in the application configuration (as a path
      like 'foo/bar/baz.py'). May contain $PYTHON_LIB references.

  Returns:
    String containing the corresponding module name (e.g., 'foo.bar.baz').
  """
  if handler_path.startswith(PYTHON_LIB_VAR + '/'):
    handler_path = handler_path[len(PYTHON_LIB_VAR):]
  handler_path = os.path.normpath(handler_path)

  extension_index = handler_path.rfind('.py')
  if extension_index != -1:
    handler_path = handler_path[:extension_index]
  module_fullname = handler_path.replace(os.sep, '.')
  module_fullname = module_fullname.strip('.')
  module_fullname = re.sub('\.+', '.', module_fullname)

  if module_fullname.endswith('.__init__'):
    module_fullname = module_fullname[:-len('.__init__')]

  return module_fullname


def FindMissingInitFiles(cgi_path, module_fullname, isfile=os.path.isfile):
  """Determines which __init__.py files are missing from a module's parent
  packages.

  Args:
    cgi_path: Absolute path of the CGI module file on disk.
    module_fullname: Fully qualified Python module name used to import the
      cgi_path module.

  Returns:
    List containing the paths to the missing __init__.py files.
  """
  missing_init_files = []

  if cgi_path.endswith('.py'):
    module_base = os.path.dirname(cgi_path)
  else:
    module_base = cgi_path

  depth_count = module_fullname.count('.')
  if cgi_path.endswith('__init__.py') or not cgi_path.endswith('.py'):
    depth_count += 1

  for index in xrange(depth_count):
    current_init_file = os.path.abspath(
        os.path.join(module_base, '__init__.py'))

    if not isfile(current_init_file):
      missing_init_files.append(current_init_file)

    module_base = os.path.abspath(os.path.join(module_base, os.pardir))

  return missing_init_files


def LoadTargetModule(handler_path,
                     cgi_path,
                     import_hook,
                     module_dict=sys.modules):
  """Loads a target CGI script by importing it as a Python module.

  If the module for the target CGI script has already been loaded before,
  the new module will be loaded in its place using the same module object,
  possibly overwriting existing module attributes.

  Args:
    handler_path: CGI path stored in the application configuration (as a path
      like 'foo/bar/baz.py'). Should not have $PYTHON_LIB references.
    cgi_path: Absolute path to the CGI script file on disk.
    import_hook: Instance of HardenedModulesHook to use for module loading.
    module_dict: Used for dependency injection.

  Returns:
    Tuple (module_fullname, script_module, module_code) where:
      module_fullname: Fully qualified module name used to import the script.
      script_module: The ModuleType object corresponding to the module_fullname.
        If the module has not already been loaded, this will be an empty
        shell of a module.
      module_code: Code object (returned by compile built-in) corresponding
        to the cgi_path to run. If the script_module was previously loaded
        and has a main() function that can be reused, this will be None.
  """
  module_fullname = GetScriptModuleName(handler_path)
  script_module = module_dict.get(module_fullname)
  module_code = None
  if script_module != None and ModuleHasValidMainFunction(script_module):
    logging.debug('Reusing main() function of module "%s"', module_fullname)
  else:
    if script_module is None:
      script_module = imp.new_module(module_fullname)
      script_module.__loader__ = import_hook

    try:
      module_code = import_hook.get_code(module_fullname)
      full_path, search_path, submodule = import_hook.GetModuleInfo(module_fullname)
      script_module.__file__ = full_path
      if search_path is not None:
        script_module.__path__ = search_path
    except:
      exc_type, exc_value, exc_tb = sys.exc_info()
      import_error_message = str(exc_type)
      if exc_value:
        import_error_message += ': ' + str(exc_value)

      logging.exception('Encountered error loading module "%s": %s',
                    module_fullname, import_error_message)
      missing_inits = FindMissingInitFiles(cgi_path, module_fullname)
      if missing_inits:
        logging.warning('Missing package initialization files: %s',
                        ', '.join(missing_inits))
      else:
        logging.error('Parent package initialization files are present, '
                      'but must be broken')

      independent_load_successful = True

      if not os.path.isfile(cgi_path):
        independent_load_successful = False
      else:
        try:
          source_file = open(cgi_path)
          try:
            module_code = compile(source_file.read(), cgi_path, 'exec')
            script_module.__file__ = cgi_path
          finally:
            source_file.close()

        except OSError:
          independent_load_successful = False

      if not independent_load_successful:
        raise exc_type, exc_value, exc_tb

    module_dict[module_fullname] = script_module

  return module_fullname, script_module, module_code


def ExecuteOrImportScript(handler_path, cgi_path, import_hook):
  """Executes a CGI script by importing it as a new module; possibly reuses
  the module's main() function if it is defined and takes no arguments.

  Basic technique lifted from PEP 338 and Python2.5's runpy module. See:
    http://www.python.org/dev/peps/pep-0338/

  See the section entitled "Import Statements and the Main Module" to understand
  why a module named '__main__' cannot do relative imports. To get around this,
  the requested module's path could be added to sys.path on each request.

  Args:
    handler_path: CGI path stored in the application configuration (as a path
      like 'foo/bar/baz.py'). Should not have $PYTHON_LIB references.
    cgi_path: Absolute path to the CGI script file on disk.
    import_hook: Instance of HardenedModulesHook to use for module loading.

  Returns:
    True if the response code had an error status (e.g., 404), or False if it
    did not.

  Raises:
    Any kind of exception that could have been raised when loading the target
    module, running a target script, or executing the application code itself.
  """
  module_fullname, script_module, module_code = LoadTargetModule(
      handler_path, cgi_path, import_hook)
  script_module.__name__ = '__main__'
  sys.modules['__main__'] = script_module
  try:
    if module_code:
      exec module_code in script_module.__dict__
    else:
      script_module.main()

    sys.stdout.flush()
    sys.stdout.seek(0)
    try:
      headers = mimetools.Message(sys.stdout)
    finally:
      sys.stdout.seek(0, 2)
    status_header = headers.get('status')
    error_response = False
    if status_header:
      try:
        status_code = int(status_header.split(' ', 1)[0])
        error_response = status_code >= 400
      except ValueError:
        error_response = True

    if not error_response:
      try:
        parent_package = import_hook.GetParentPackage(module_fullname)
      except Exception:
        parent_package = None

      if parent_package is not None:
        submodule = GetSubmoduleName(module_fullname)
        setattr(parent_package, submodule, script_module)

    return error_response
  finally:
    script_module.__name__ = module_fullname


def ExecuteCGI(root_path,
               handler_path,
               cgi_path,
               env,
               infile,
               outfile,
               module_dict,
               exec_script=ExecuteOrImportScript):
  """Executes Python file in this process as if it were a CGI.

  Does not return an HTTP response line. CGIs should output headers followed by
  the body content.

  The modules in sys.modules should be the same before and after the CGI is
  executed, with the specific exception of encodings-related modules, which
  cannot be reloaded and thus must always stay in sys.modules.

  Args:
    root_path: Path to the root of the application.
    handler_path: CGI path stored in the application configuration (as a path
      like 'foo/bar/baz.py'). May contain $PYTHON_LIB references.
    cgi_path: Absolute path to the CGI script file on disk.
    env: Dictionary of environment variables to use for the execution.
    infile: File-like object to read HTTP request input data from.
    outfile: FIle-like object to write HTTP response data to.
    module_dict: Dictionary in which application-loaded modules should be
      preserved between requests. This removes the need to reload modules that
      are reused between requests, significantly increasing load performance.
      This dictionary must be separate from the sys.modules dictionary.
    exec_script: Used for dependency injection.
  """
  old_module_dict = sys.modules.copy()
  old_builtin = __builtin__.__dict__.copy()
  old_argv = sys.argv
  old_stdin = sys.stdin
  old_stdout = sys.stdout
  old_env = os.environ.copy()
  old_cwd = os.getcwd()
  old_file_type = types.FileType
  reset_modules = False

  try:
    ClearAllButEncodingsModules(sys.modules)
    sys.modules.update(module_dict)
    sys.argv = [cgi_path]
    sys.stdin = infile
    sys.stdout = outfile
    os.environ.clear()
    os.environ.update(env)
    before_path = sys.path[:]
    cgi_dir = os.path.normpath(os.path.dirname(cgi_path))
    root_path = os.path.normpath(os.path.abspath(root_path))
    if cgi_dir.startswith(root_path + os.sep):
      os.chdir(cgi_dir)
    else:
      os.chdir(root_path)

    hook = HardenedModulesHook(sys.modules)
    sys.meta_path = [hook]
    if hasattr(sys, 'path_importer_cache'):
      sys.path_importer_cache.clear()

    __builtin__.file = FakeFile
    __builtin__.open = FakeFile
    types.FileType = FakeFile

    __builtin__.buffer = NotImplementedFakeClass

    logging.debug('Executing CGI with env:\n%s', pprint.pformat(env))
    try:
      reset_modules = exec_script(handler_path, cgi_path, hook)
    except SystemExit, e:
      logging.debug('CGI exited with status: %s', e)
    except:
      reset_modules = True
      raise

  finally:
    sys.meta_path = []
    sys.path_importer_cache.clear()

    _ClearTemplateCache(sys.modules)

    module_dict.update(sys.modules)
    ClearAllButEncodingsModules(sys.modules)
    sys.modules.update(old_module_dict)

    __builtin__.__dict__.update(old_builtin)
    sys.argv = old_argv
    sys.stdin = old_stdin
    sys.stdout = old_stdout

    sys.path[:] = before_path

    os.environ.clear()
    os.environ.update(old_env)
    os.chdir(old_cwd)

    types.FileType = old_file_type


class CGIDispatcher(URLDispatcher):
  """Dispatcher that executes Python CGI scripts."""

  def __init__(self,
               module_dict,
               root_path,
               path_adjuster,
               setup_env=SetupEnvironment,
               exec_cgi=ExecuteCGI,
               create_logging_handler=ApplicationLoggingHandler):
    """Initializer.

    Args:
      module_dict: Dictionary in which application-loaded modules should be
        preserved between requests. This dictionary must be separate from the
        sys.modules dictionary.
      path_adjuster: Instance of PathAdjuster to use for finding absolute
        paths of CGI files on disk.
      setup_env, exec_cgi, create_logging_handler: Used for dependency
        injection.
    """
    self._module_dict = module_dict
    self._root_path = root_path
    self._path_adjuster = path_adjuster
    self._setup_env = setup_env
    self._exec_cgi = exec_cgi
    self._create_logging_handler = create_logging_handler

  def Dispatch(self,
               relative_url,
               path,
               headers,
               infile,
               outfile,
               base_env_dict=None):
    """Dispatches the Python CGI."""
    handler = self._create_logging_handler()
    logging.getLogger().addHandler(handler)
    before_level = logging.root.level
    try:
      env = {}
      if base_env_dict:
        env.update(base_env_dict)
      cgi_path = self._path_adjuster.AdjustPath(path)
      env.update(self._setup_env(cgi_path, relative_url, headers))
      self._exec_cgi(self._root_path,
                     path,
                     cgi_path,
                     env,
                     infile,
                     outfile,
                     self._module_dict)
      handler.AddDebuggingConsole(relative_url, env, outfile)
    finally:
      logging.root.level = before_level
      logging.getLogger().removeHandler(handler)

  def __str__(self):
    """Returns a string representation of this dispatcher."""
    return 'CGI dispatcher'


class LocalCGIDispatcher(CGIDispatcher):
  """Dispatcher that executes local functions like they're CGIs.

  The contents of sys.modules will be preserved for local CGIs running this
  dispatcher, but module hardening will still occur for any new imports. Thus,
  be sure that any local CGIs have loaded all of their dependent modules
  _before_ they are executed.
  """

  def __init__(self, module_dict, path_adjuster, cgi_func):
    """Initializer.

    Args:
      module_dict: Passed to CGIDispatcher.
      path_adjuster: Passed to CGIDispatcher.
      cgi_func: Callable function taking no parameters that should be
        executed in a CGI environment in the current process.
    """
    self._cgi_func = cgi_func

    def curried_exec_script(*args, **kwargs):
      cgi_func()
      return False

    def curried_exec_cgi(*args, **kwargs):
      kwargs['exec_script'] = curried_exec_script
      return ExecuteCGI(*args, **kwargs)

    CGIDispatcher.__init__(self,
                           module_dict,
                           '',
                           path_adjuster,
                           exec_cgi=curried_exec_cgi)

  def Dispatch(self, *args, **kwargs):
    """Preserves sys.modules for CGIDispatcher.Dispatch."""
    self._module_dict.update(sys.modules)
    CGIDispatcher.Dispatch(self, *args, **kwargs)

  def __str__(self):
    """Returns a string representation of this dispatcher."""
    return 'Local CGI dispatcher for %s' % self._cgi_func


class PathAdjuster(object):
  """Adjusts application file paths to paths relative to the application or
  external library directories."""

  def __init__(self, root_path):
    """Initializer.

    Args:
      root_path: Path to the root of the application running on the server.
    """
    self._root_path = os.path.abspath(root_path)

  def AdjustPath(self, path):
    """Adjusts application file path to paths relative to the application or
    external library directories.

    Handler paths that start with $PYTHON_LIB will be converted to paths
    relative to the google directory.

    Args:
      path: File path that should be adjusted.

    Returns:
      The adjusted path.
    """
    if path.startswith(PYTHON_LIB_VAR):
      path = os.path.join(os.path.dirname(os.path.dirname(google.__file__)),
                          path[len(PYTHON_LIB_VAR) + 1:])
    else:
      path = os.path.join(self._root_path, path)

    return path


class StaticFileConfigMatcher(object):
  """Keeps track of file/directory specific application configuration.

  Specifically:
  - Computes mime type based on URLMap and file extension.
  - Decides on cache expiration time based on URLMap and default expiration.

  To determine the mime type, we first see if there is any mime-type property
  on each URLMap entry. If non is specified, we use the mimetypes module to
  guess the mime type from the file path extension, and use
  application/octet-stream if we can't find the mimetype.
  """

  def __init__(self,
               url_map_list,
               path_adjuster,
               default_expiration):
    """Initializer.

    Args:
      url_map_list: List of appinfo.URLMap objects.
        If empty or None, then we always use the mime type chosen by the
        mimetypes module.
      path_adjuster: PathAdjuster object used to adjust application file paths.
      default_expiration: String describing default expiration time for browser
        based caching of static files.  If set to None this disallows any
        browser caching of static content.
    """
    if default_expiration is not None:
      self._default_expiration = appinfo.ParseExpiration(default_expiration)
    else:
      self._default_expiration = None

    self._patterns = []

    if url_map_list:
      for entry in url_map_list:
        handler_type = entry.GetHandlerType()
        if handler_type not in (appinfo.STATIC_FILES, appinfo.STATIC_DIR):
          continue

        if handler_type == appinfo.STATIC_FILES:
          regex = entry.upload + '$'
        else:
          path = entry.static_dir
          if path[-1] == '/':
            path = path[:-1]
          regex = re.escape(path + os.path.sep) + r'(.*)'

        try:
          path_re = re.compile(regex)
        except re.error, e:
          raise InvalidAppConfigError('regex %s does not compile: %s' %
                                      (regex, e))

        if self._default_expiration is None:
          expiration = 0
        elif entry.expiration is None:
          expiration = self._default_expiration
        else:
          expiration = appinfo.ParseExpiration(entry.expiration)

        self._patterns.append((path_re, entry.mime_type, expiration))

  def IsStaticFile(self, path):
    """Tests if the given path points to a "static" file.

    Args:
      path: String containing the file's path relative to the app.

    Returns:
      Boolean, True if the file was configured to be static.
    """
    for (path_re, _, _) in self._patterns:
      if path_re.match(path):
        return True
    return False

  def GetMimeType(self, path):
    """Returns the mime type that we should use when serving the specified file.

    Args:
      path: String containing the file's path relative to the app.

    Returns:
      String containing the mime type to use. Will be 'application/octet-stream'
      if we have no idea what it should be.
    """
    for (path_re, mime_type, expiration) in self._patterns:
      if mime_type is not None:
        the_match = path_re.match(path)
        if the_match:
          return mime_type

    filename, extension = os.path.splitext(path)
    return mimetypes.types_map.get(extension, 'application/octet-stream')

  def GetExpiration(self, path):
    """Returns the cache expiration duration to be users for the given file.

    Args:
      path: String containing the file's path relative to the app.

    Returns:
      Integer number of seconds to be used for browser cache expiration time.
    """
    for (path_re, mime_type, expiration) in self._patterns:
      the_match = path_re.match(path)
      if the_match:
        return expiration

    return self._default_expiration or 0



def ReadDataFile(data_path, openfile=file):
  """Reads a file on disk, returning a corresponding HTTP status and data.

  Args:
    data_path: Path to the file on disk to read.
    openfile: Used for dependency injection.

  Returns:
    Tuple (status, data) where status is an HTTP response code, and data is
      the data read; will be an empty string if an error occurred or the
      file was empty.
  """
  status = httplib.INTERNAL_SERVER_ERROR
  data = ""

  try:
    data_file = openfile(data_path, 'rb')
    try:
      data = data_file.read()
    finally:
      data_file.close()
      status = httplib.OK
  except (OSError, IOError), e:
    logging.error('Error encountered reading file "%s":\n%s', data_path, e)
    if e.errno in FILE_MISSING_EXCEPTIONS:
      status = httplib.NOT_FOUND
    else:
      status = httplib.FORBIDDEN

  return status, data


class FileDispatcher(URLDispatcher):
  """Dispatcher that reads data files from disk."""

  def __init__(self,
               path_adjuster,
               static_file_config_matcher,
               read_data_file=ReadDataFile):
    """Initializer.

    Args:
      path_adjuster: Instance of PathAdjuster to use for finding absolute
        paths of data files on disk.
      static_file_config_matcher: StaticFileConfigMatcher object.
      read_data_file: Used for dependency injection.
    """
    self._path_adjuster = path_adjuster
    self._static_file_config_matcher = static_file_config_matcher
    self._read_data_file = read_data_file

  def Dispatch(self,
               relative_url,
               path,
               headers,
               infile,
               outfile,
               base_env_dict=None):
    """Reads the file and returns the response status and data."""
    full_path = self._path_adjuster.AdjustPath(path)
    status, data = self._read_data_file(full_path)
    content_type = self._static_file_config_matcher.GetMimeType(path)
    expiration = self._static_file_config_matcher.GetExpiration(path)

    outfile.write('Status: %d\r\n' % status)
    outfile.write('Content-type: %s\r\n' % content_type)
    if expiration:
      outfile.write('Expires: %s\r\n'
                    % email.Utils.formatdate(time.time() + expiration,
                                             usegmt=True))
      outfile.write('Cache-Control: public, max-age=%i\r\n' % expiration)
    outfile.write('\r\n')
    outfile.write(data)

  def __str__(self):
    """Returns a string representation of this dispatcher."""
    return 'File dispatcher'


_IGNORE_RESPONSE_HEADERS = frozenset([
    'content-encoding', 'accept-encoding', 'transfer-encoding',
    'server', 'date',
    ])


def IgnoreHeadersRewriter(status_code, status_message, headers, body):
  """Ignore specific response headers.

  Certain response headers cannot be modified by an Application.  For a
  complete list of these headers please see:

    http://code.google.com/appengine/docs/webapp/responseclass.html#Disallowed_HTTP_Response_Headers

  This rewriter simply removes those headers.
  """
  for h in _IGNORE_RESPONSE_HEADERS:
    if h in headers:
      del headers[h]

  return status_code, status_message, headers, body


def ParseStatusRewriter(status_code, status_message, headers, body):
  """Parse status header, if it exists.

  Handles the server-side 'status' header, which instructs the server to change
  the HTTP response code accordingly. Handles the 'location' header, which
  issues an HTTP 302 redirect to the client. Also corrects the 'content-length'
  header to reflect actual content length in case extra information has been
  appended to the response body.

  If the 'status' header supplied by the client is invalid, this method will
  set the response to a 500 with an error message as content.
  """
  location_value = headers.getheader('location')
  status_value = headers.getheader('status')
  if status_value:
    response_status = status_value
    del headers['status']
  elif location_value:
    response_status = '%d Redirecting' % httplib.FOUND
  else:
    return status_code, status_message, headers, body

  status_parts = response_status.split(' ', 1)
  status_code, status_message = (status_parts + [''])[:2]
  try:
    status_code = int(status_code)
  except ValueError:
    status_code = 500
    body = cStringIO.StringIO('Error: Invalid "status" header value returned.')

  return status_code, status_message, headers, body


def CacheRewriter(status_code, status_message, headers, body):
  """Update the cache header."""
  if not 'Cache-Control' in headers:
    headers['Cache-Control'] = 'no-cache'
  return status_code, status_message, headers, body


def ContentLengthRewriter(status_code, status_message, headers, body):
  """Rewrite the Content-Length header.

  Even though Content-Length is not a user modifiable header, App Engine
  sends a correct Content-Length to the user based on the actual response.
  """
  current_position = body.tell()
  body.seek(0, 2)

  headers['Content-Length'] = str(body.tell() - current_position)
  body.seek(current_position)
  return status_code, status_message, headers, body


def CreateResponseRewritersChain():
  """Create the default response rewriter chain.

  A response rewriter is the a function that gets a final chance to change part
  of the dev_appservers response.  A rewriter is not like a dispatcher in that
  it is called after every request has been handled by the dispatchers
  regardless of which dispatcher was used.

  The order in which rewriters are registered will be the order in which they
  are used to rewrite the response.  Modifications from earlier rewriters
  are used as input to later rewriters.

  A response rewriter is a function that can rewrite the request in any way.
  Thefunction can returned modified values or the original values it was
  passed.

  A rewriter function has the following parameters and return values:

    Args:
      status_code: Status code of response from dev_appserver or previous
        rewriter.
      status_message: Text corresponding to status code.
      headers: mimetools.Message instance with parsed headers.  NOTE: These
        headers can contain its own 'status' field, but the default
        dev_appserver implementation will remove this.  Future rewriters
        should avoid re-introducing the status field and return new codes
        instead.
      body: File object containing the body of the response.  This position of
        this file may not be at the start of the file.  Any content before the
        files position is considered not to be part of the final body.

     Returns:
      status_code: Rewritten status code or original.
      status_message: Rewritter message or original.
      headers: Rewritten/modified headers or original.
      body: Rewritten/modified body or original.

  Returns:
    List of response rewriters.
  """
  return [IgnoreHeadersRewriter,
          ParseStatusRewriter,
          CacheRewriter,
          ContentLengthRewriter,
  ]


def RewriteResponse(response_file, response_rewriters=None):
  """Allows final rewrite of dev_appserver response.

  This function receives the unparsed HTTP response from the application
  or internal handler, parses out the basic structure and feeds that structure
  in to a chain of response rewriters.

  It also makes sure the final HTTP headers are properly terminated.

  For more about response rewriters, please see documentation for
  CreateResponeRewritersChain.

  Args:
    response_file: File-like object containing the full HTTP response including
      the response code, all headers, and the request body.
    response_rewriters: A list of response rewriters.  If none is provided it
      will create a new chain using CreateResponseRewritersChain.

  Returns:
    Tuple (status_code, status_message, header, body) where:
      status_code: Integer HTTP response status (e.g., 200, 302, 404, 500)
      status_message: String containing an informational message about the
        response code, possibly derived from the 'status' header, if supplied.
      header: String containing the HTTP headers of the response, without
        a trailing new-line (CRLF).
      body: String containing the body of the response.
  """
  if response_rewriters is None:
    response_rewriters = CreateResponseRewritersChain()

  status_code = 200
  status_message = 'Good to go'
  headers = mimetools.Message(response_file)

  for response_rewriter in response_rewriters:
    status_code, status_message, headers, response_file = response_rewriter(
        status_code,
        status_message,
        headers,
        response_file)

  header_list = []
  for header in headers.headers:
    header = header.rstrip('\n')
    header = header.rstrip('\r')
    header_list.append(header)

  header_data = '\r\n'.join(header_list) + '\r\n'
  return status_code, status_message, header_data, response_file.read()


class ModuleManager(object):
  """Manages loaded modules in the runtime.

  Responsible for monitoring and reporting about file modification times.
  Modules can be loaded from source or precompiled byte-code files.  When a
  file has source code, the ModuleManager monitors the modification time of
  the source file even if the module itself is loaded from byte-code.
  """

  def __init__(self, modules):
    """Initializer.

    Args:
      modules: Dictionary containing monitored modules.
    """
    self._modules = modules
    self._default_modules = self._modules.copy()
    self._save_path_hooks = sys.path_hooks[:]
    self._modification_times = {}

  @staticmethod
  def GetModuleFile(module, is_file=os.path.isfile):
    """Helper method to try to determine modules source file.

    Args:
      module: Module object to get file for.
      is_file: Function used to determine if a given path is a file.

    Returns:
      Path of the module's corresponding Python source file if it exists, or
      just the module's compiled Python file. If the module has an invalid
      __file__ attribute, None will be returned.
      """
    module_file = getattr(module, '__file__', None)
    if module_file is None:
      return None

    source_file = module_file[:module_file.rfind('py') + 2]

    if is_file(source_file):
      return source_file
    return module.__file__

  def AreModuleFilesModified(self):
    """Determines if any monitored files have been modified.

    Returns:
      True if one or more files have been modified, False otherwise.
    """
    for name, (mtime, fname) in self._modification_times.iteritems():
      if name not in self._modules:
        continue

      module = self._modules[name]

      if not os.path.isfile(fname):
        return True

      if mtime != os.path.getmtime(fname):
        return True

    return False

  def UpdateModuleFileModificationTimes(self):
    """Records the current modification times of all monitored modules.
    """
    self._modification_times.clear()
    for name, module in self._modules.items():
      if not isinstance(module, types.ModuleType):
        continue
      module_file = self.GetModuleFile(module)
      if not module_file:
        continue
      try:
        self._modification_times[name] = (os.path.getmtime(module_file),
                                          module_file)
      except OSError, e:
        if e.errno not in FILE_MISSING_EXCEPTIONS:
          raise e

  def ResetModules(self):
    """Clear modules so that when request is run they are reloaded."""
    self._modules.clear()
    self._modules.update(self._default_modules)
    sys.path_hooks[:] = self._save_path_hooks


def _ClearTemplateCache(module_dict=sys.modules):
  """Clear template cache in webapp.template module.

  Attempts to load template module.  Ignores failure.  If module loads, the
  template cache is cleared.
  """
  template_module = module_dict.get('google.appengine.ext.webapp.template')
  if template_module is not None:
    template_module.template_cache.clear()


def CreateRequestHandler(root_path,
                         login_url,
                         require_indexes=False,
                         static_caching=True):
  """Creates a new BaseHTTPRequestHandler sub-class for use with the Python
  BaseHTTPServer module's HTTP server.

  Python's built-in HTTP server does not support passing context information
  along to instances of its request handlers. This function gets around that
  by creating a sub-class of the handler in a closure that has access to
  this context information.

  Args:
    root_path: Path to the root of the application running on the server.
    login_url: Relative URL which should be used for handling user logins.
    require_indexes: True if index.yaml is read-only gospel; default False.
    static_caching: True if browser caching of static files should be allowed.

  Returns:
    Sub-class of BaseHTTPRequestHandler.
  """
  application_module_dict = SetupSharedModules(sys.modules)

  if require_indexes:
    index_yaml_updater = None
  else:
    index_yaml_updater = dev_appserver_index.IndexYamlUpdater(root_path)

  application_config_cache = AppConfigCache()

  class DevAppServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """Dispatches URLs using patterns from a URLMatcher, which is created by
    loading an application's configuration file. Executes CGI scripts in the
    local process so the scripts can use mock versions of APIs.

    HTTP requests that correctly specify a user info cookie
    (dev_appserver_login.COOKIE_NAME) will have the 'USER_EMAIL' environment
    variable set accordingly. If the user is also an admin, the
    'USER_IS_ADMIN' variable will exist and be set to '1'. If the user is not
    logged in, 'USER_EMAIL' will be set to the empty string.

    On each request, raises an InvalidAppConfigError exception if the
    application configuration file in the directory specified by the root_path
    argument is invalid.
    """
    server_version = 'Development/1.0'

    module_dict = application_module_dict
    module_manager = ModuleManager(application_module_dict)

    config_cache = application_config_cache

    rewriter_chain = CreateResponseRewritersChain()

    def __init__(self, *args, **kwargs):
      """Initializer.

      Args:
        args, kwargs: Positional and keyword arguments passed to the constructor
          of the super class.
      """
      BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def version_string(self):
      """Returns server's version string used for Server HTTP header"""
      return self.server_version

    def do_GET(self):
      """Handle GET requests."""
      self._HandleRequest()

    def do_POST(self):
      """Handles POST requests."""
      self._HandleRequest()

    def do_PUT(self):
      """Handle PUT requests."""
      self._HandleRequest()

    def do_HEAD(self):
      """Handle HEAD requests."""
      self._HandleRequest()

    def do_OPTIONS(self):
      """Handles OPTIONS requests."""
      self._HandleRequest()

    def do_DELETE(self):
      """Handle DELETE requests."""
      self._HandleRequest()

    def do_TRACE(self):
      """Handles TRACE requests."""
      self._HandleRequest()

    def _HandleRequest(self):
      """Handles any type of request and prints exceptions if they occur."""
      server_name = self.headers.get('host') or self.server.server_name
      server_name = server_name.split(':', 1)[0]

      env_dict = {
        'REQUEST_METHOD': self.command,
        'REMOTE_ADDR': self.client_address[0],
        'SERVER_SOFTWARE': self.server_version,
        'SERVER_NAME': server_name,
        'SERVER_PROTOCOL': self.protocol_version,
        'SERVER_PORT': str(self.server.server_port),
      }

      full_url = GetFullURL(server_name, self.server.server_port, self.path)
      if len(full_url) > MAX_URL_LENGTH:
        msg = 'Requested URI too long: %s' % full_url
        logging.error(msg)
        self.send_response(httplib.REQUEST_URI_TOO_LONG, msg)
        return

      tbhandler = cgitb.Hook(file=self.wfile).handle
      try:
        if self.module_manager.AreModuleFilesModified():
          self.module_manager.ResetModules()

        implicit_matcher = CreateImplicitMatcher(self.module_dict,
                                                 root_path,
                                                 login_url)
        config, explicit_matcher = LoadAppConfig(root_path, self.module_dict,
                                                 cache=self.config_cache,
                                                 static_caching=static_caching)
        if config.api_version != API_VERSION:
          logging.error("API versions cannot be switched dynamically: %r != %r"
                        % (config.api_version, API_VERSION))
          sys.exit(1)
        env_dict['CURRENT_VERSION_ID'] = config.version + ".1"
        env_dict['APPLICATION_ID'] = config.application
        dispatcher = MatcherDispatcher(login_url,
                                       [implicit_matcher, explicit_matcher])

        if require_indexes:
          dev_appserver_index.SetupIndexes(config.application, root_path)

        infile = cStringIO.StringIO(self.rfile.read(
            int(self.headers.get('content-length', 0))))

        request_size = len(infile.getvalue())
        if request_size > MAX_REQUEST_SIZE:
          msg = ('HTTP request was too large: %d.  The limit is: %d.'
                 % (request_size, MAX_REQUEST_SIZE))
          logging.error(msg)
          self.send_response(httplib.REQUEST_ENTITY_TOO_LARGE, msg)
          return

        outfile = cStringIO.StringIO()
        try:
          dispatcher.Dispatch(self.path,
                              None,
                              self.headers,
                              infile,
                              outfile,
                              base_env_dict=env_dict)
        finally:
          self.module_manager.UpdateModuleFileModificationTimes()

        outfile.flush()
        outfile.seek(0)

        status_code, status_message, header_data, body = RewriteResponse(outfile, self.rewriter_chain)

        runtime_response_size = len(outfile.getvalue())
        if runtime_response_size > MAX_RUNTIME_RESPONSE_SIZE:
          status_code = 403
          status_message = 'Forbidden'
          new_headers = []
          for header in header_data.split('\n'):
            if not header.lower().startswith('content-length'):
              new_headers.append(header)
          header_data = '\n'.join(new_headers)
          body = ('HTTP response was too large: %d.  The limit is: %d.'
                  % (runtime_response_size, MAX_RUNTIME_RESPONSE_SIZE))

      except yaml_errors.EventListenerError, e:
        title = 'Fatal error when loading application configuration'
        msg = '%s:\n%s' % (title, str(e))
        logging.error(msg)
        self.send_response(httplib.INTERNAL_SERVER_ERROR, title)
        self.wfile.write('Content-Type: text/html\n\n')
        self.wfile.write('<pre>%s</pre>' % cgi.escape(msg))
      except:
        msg = 'Exception encountered handling request'
        logging.exception(msg)
        self.send_response(httplib.INTERNAL_SERVER_ERROR, msg)
        tbhandler()
      else:
        try:
          self.send_response(status_code, status_message)
          self.wfile.write(header_data)
          self.wfile.write('\r\n')
          if self.command != 'HEAD':
            self.wfile.write(body)
          elif body:
            logging.warning('Dropping unexpected body in response '
                            'to HEAD request')
        except (IOError, OSError), e:
          if e.errno != errno.EPIPE:
            raise e
        except socket.error, e:
          if len(e.args) >= 1 and e.args[0] != errno.EPIPE:
            raise e
        else:
          if index_yaml_updater is not None:
            index_yaml_updater.UpdateIndexYaml()

    def log_error(self, format, *args):
      """Redirect error messages through the logging module."""
      logging.error(format, *args)

    def log_message(self, format, *args):
      """Redirect log messages through the logging module."""
      logging.info(format, *args)

  return DevAppServerRequestHandler


def ReadAppConfig(appinfo_path, parse_app_config=appinfo.LoadSingleAppInfo):
  """Reads app.yaml file and returns its app id and list of URLMap instances.

  Args:
    appinfo_path: String containing the path to the app.yaml file.
    parse_app_config: Used for dependency injection.

  Returns:
    AppInfoExternal instance.

  Raises:
    If the config file could not be read or the config does not contain any
    URLMap instances, this function will raise an InvalidAppConfigError
    exception.
  """
  try:
    appinfo_file = file(appinfo_path, 'r')
  except IOError, e:
    raise InvalidAppConfigError(
      'Application configuration could not be read from "%s"' % appinfo_path)
  try:
    return parse_app_config(appinfo_file)
  finally:
    appinfo_file.close()


def CreateURLMatcherFromMaps(root_path,
                             url_map_list,
                             module_dict,
                             default_expiration,
                             create_url_matcher=URLMatcher,
                             create_cgi_dispatcher=CGIDispatcher,
                             create_file_dispatcher=FileDispatcher,
                             create_path_adjuster=PathAdjuster,
                             normpath=os.path.normpath):
  """Creates a URLMatcher instance from URLMap.

  Creates all of the correct URLDispatcher instances to handle the various
  content types in the application configuration.

  Args:
    root_path: Path to the root of the application running on the server.
    url_map_list: List of appinfo.URLMap objects to initialize this
      matcher with. Can be an empty list if you would like to add patterns
      manually.
    module_dict: Dictionary in which application-loaded modules should be
      preserved between requests. This dictionary must be separate from the
      sys.modules dictionary.
    default_expiration: String describing default expiration time for browser
      based caching of static files.  If set to None this disallows any
      browser caching of static content.
    create_url_matcher, create_cgi_dispatcher, create_file_dispatcher,
    create_path_adjuster: Used for dependency injection.

  Returns:
    Instance of URLMatcher with the supplied URLMap objects properly loaded.
  """
  url_matcher = create_url_matcher()
  path_adjuster = create_path_adjuster(root_path)
  cgi_dispatcher = create_cgi_dispatcher(module_dict, root_path, path_adjuster)
  static_file_config_matcher = StaticFileConfigMatcher(url_map_list,
                                                       path_adjuster,
                                                       default_expiration)
  file_dispatcher = create_file_dispatcher(path_adjuster,
                                           static_file_config_matcher)

  FakeFile.SetStaticFileConfigMatcher(static_file_config_matcher)

  for url_map in url_map_list:
    admin_only = url_map.login == appinfo.LOGIN_ADMIN
    requires_login = url_map.login == appinfo.LOGIN_REQUIRED or admin_only

    handler_type = url_map.GetHandlerType()
    if handler_type == appinfo.HANDLER_SCRIPT:
      dispatcher = cgi_dispatcher
    elif handler_type in (appinfo.STATIC_FILES, appinfo.STATIC_DIR):
      dispatcher = file_dispatcher
    else:
      raise InvalidAppConfigError('Unknown handler type "%s"' % handler_type)

    regex = url_map.url
    path = url_map.GetHandler()
    if handler_type == appinfo.STATIC_DIR:
      if regex[-1] == r'/':
        regex = regex[:-1]
      if path[-1] == os.path.sep:
        path = path[:-1]
      regex = '/'.join((re.escape(regex), '(.*)'))
      if os.path.sep == '\\':
        backref = r'\\1'
      else:
        backref = r'\1'
      path = (normpath(path).replace('\\', '\\\\') +
              os.path.sep + backref)

    url_matcher.AddURL(regex,
                       dispatcher,
                       path,
                       requires_login, admin_only)

  return url_matcher


class AppConfigCache(object):
  """Cache used by LoadAppConfig.

  If given to LoadAppConfig instances of this class are used to cache contents
  of the app config (app.yaml or app.yml) and the Matcher created from it.

  Code outside LoadAppConfig should treat instances of this class as opaque
  objects and not access its members.
  """

  path = None
  mtime = None
  config = None
  matcher = None


def LoadAppConfig(root_path,
                  module_dict,
                  cache=None,
                  static_caching=True,
                  read_app_config=ReadAppConfig,
                  create_matcher=CreateURLMatcherFromMaps):
  """Creates a Matcher instance for an application configuration file.

  Raises an InvalidAppConfigError exception if there is anything wrong with
  the application configuration file.

  Args:
    root_path: Path to the root of the application to load.
    module_dict: Dictionary in which application-loaded modules should be
      preserved between requests. This dictionary must be separate from the
      sys.modules dictionary.
    cache: Instance of AppConfigCache or None.
    static_caching: True if browser caching of static files should be allowed.
    read_app_config, create_matcher: Used for dependency injection.

  Returns:
     tuple: (AppInfoExternal, URLMatcher)
  """
  for appinfo_path in [os.path.join(root_path, 'app.yaml'),
                       os.path.join(root_path, 'app.yml')]:

    if os.path.isfile(appinfo_path):
      if cache is not None:
        mtime = os.path.getmtime(appinfo_path)
        if cache.path == appinfo_path and cache.mtime == mtime:
          return (cache.config, cache.matcher)

        cache.config = cache.matcher = cache.path = None
        cache.mtime = mtime

      try:
        config = read_app_config(appinfo_path, appinfo.LoadSingleAppInfo)

        if static_caching:
          if config.default_expiration:
            default_expiration = config.default_expiration
          else:
            default_expiration = '0'
        else:
          default_expiration = None

        matcher = create_matcher(root_path,
                                 config.handlers,
                                 module_dict,
                                 default_expiration)

        FakeFile.SetSkippedFiles(config.skip_files)

        if cache is not None:
          cache.path = appinfo_path
          cache.config = config
          cache.matcher = matcher

        return (config, matcher)
      except gexcept.AbstractMethod:
        pass

  raise AppConfigNotFoundError


def ReadCronConfig(croninfo_path, parse_cron_config=croninfo.LoadSingleCron):
  """Reads cron.yaml file and returns a list of CronEntry instances.

  Args:
    croninfo_path: String containing the path to the cron.yaml file.
    parse_cron_config: Used for dependency injection.

  Returns:
    A CronInfoExternal object.

  Raises:
    If the config file is unreadable, empty or invalid, this function will
    raise an InvalidAppConfigError or a MalformedCronConfiguration exception.
    """
  try:
    croninfo_file = file(croninfo_path, 'r')
  except IOError, e:
    raise InvalidAppConfigError(
        'Cron configuration could not be read from "%s"' % croninfo_path)
  try:
    return parse_cron_config(croninfo_file)
  finally:
    croninfo_file.close()


def SetupStubs(app_id, **config):
  """Sets up testing stubs of APIs.

  Args:
    app_id: Application ID being served.

  Keywords:
    login_url: Relative URL which should be used for handling user login/logout.
    datastore_path: Path to the file to store Datastore file stub data in.
    history_path: Path to the file to store Datastore history in.
    clear_datastore: If the datastore and history should be cleared on startup.
    smtp_host: SMTP host used for sending test mail.
    smtp_port: SMTP port.
    smtp_user: SMTP user.
    smtp_password: SMTP password.
    enable_sendmail: Whether to use sendmail as an alternative to SMTP.
    show_mail_body: Whether to log the body of emails.
    remove: Used for dependency injection.
  """
  login_url = config['login_url']
  datastore_path = config['datastore_path']
  history_path = config['history_path']
  clear_datastore = config['clear_datastore']
  require_indexes = config.get('require_indexes', False)
  smtp_host = config.get('smtp_host', None)
  smtp_port = config.get('smtp_port', 25)
  smtp_user = config.get('smtp_user', '')
  smtp_password = config.get('smtp_password', '')
  enable_sendmail = config.get('enable_sendmail', False)
  show_mail_body = config.get('show_mail_body', False)
  remove = config.get('remove', os.remove)

  os.environ['APPLICATION_ID'] = app_id

  if clear_datastore:
    for path in (datastore_path, history_path):
      if os.path.lexists(path):
        logging.info('Attempting to remove file at %s', path)
        try:
          remove(path)
        except OSError, e:
          logging.warning('Removing file failed: %s', e)

  apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()

  datastore = datastore_file_stub.DatastoreFileStub(
      app_id, datastore_path, history_path, require_indexes=require_indexes)
  apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', datastore)

  fixed_login_url = '%s?%s=%%s' % (login_url,
                                   dev_appserver_login.CONTINUE_PARAM)
  fixed_logout_url = '%s&%s' % (fixed_login_url,
                                dev_appserver_login.LOGOUT_PARAM)

  apiproxy_stub_map.apiproxy.RegisterStub(
    'user',
    user_service_stub.UserServiceStub(login_url=fixed_login_url,
                                      logout_url=fixed_logout_url))

  apiproxy_stub_map.apiproxy.RegisterStub(
    'urlfetch',
    urlfetch_stub.URLFetchServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub(
    'mail',
    mail_stub.MailServiceStub(smtp_host,
                              smtp_port,
                              smtp_user,
                              smtp_password,
                              enable_sendmail=enable_sendmail,
                              show_mail_body=show_mail_body))

  apiproxy_stub_map.apiproxy.RegisterStub(
    'memcache',
    memcache_stub.MemcacheServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub(
    'capability_service',
    capability_stub.CapabilityServiceStub())

  try:
    from google.appengine.api.images import images_stub
    apiproxy_stub_map.apiproxy.RegisterStub(
      'images',
      images_stub.ImagesServiceStub())
  except ImportError, e:
    logging.warning('Could not initialize images API; you are likely missing '
                    'the Python "PIL" module. ImportError: %s', e)
    from google.appengine.api.images import images_not_implemented_stub
    apiproxy_stub_map.apiproxy.RegisterStub('images',
      images_not_implemented_stub.ImagesNotImplementedServiceStub())


def CreateImplicitMatcher(module_dict,
                          root_path,
                          login_url,
                          create_path_adjuster=PathAdjuster,
                          create_local_dispatcher=LocalCGIDispatcher,
                          create_cgi_dispatcher=CGIDispatcher):
  """Creates a URLMatcher instance that handles internal URLs.

  Used to facilitate handling user login/logout, debugging, info about the
  currently running app, etc.

  Args:
    module_dict: Dictionary in the form used by sys.modules.
    root_path: Path to the root of the application.
    login_url: Relative URL which should be used for handling user login/logout.
    create_local_dispatcher: Used for dependency injection.

  Returns:
    Instance of URLMatcher with appropriate dispatchers.
  """
  url_matcher = URLMatcher()
  path_adjuster = create_path_adjuster(root_path)

  login_dispatcher = create_local_dispatcher(sys.modules, path_adjuster,
                                             dev_appserver_login.main)
  url_matcher.AddURL(login_url,
                     login_dispatcher,
                     '',
                     False,
                     False)


  admin_dispatcher = create_cgi_dispatcher(module_dict, root_path,
                                           path_adjuster)
  url_matcher.AddURL('/_ah/admin(?:/.*)?',
                     admin_dispatcher,
                     DEVEL_CONSOLE_PATH,
                     False,
                     False)

  return url_matcher


def SetupTemplates(template_dir):
  """Reads debugging console template files and initializes the console.

  Does nothing if templates have already been initialized.

  Args:
    template_dir: Path to the directory containing the templates files.

  Raises:
    OSError or IOError if any of the template files could not be read.
  """
  if ApplicationLoggingHandler.AreTemplatesInitialized():
    return

  try:
    header = open(os.path.join(template_dir, HEADER_TEMPLATE)).read()
    script = open(os.path.join(template_dir, SCRIPT_TEMPLATE)).read()
    middle = open(os.path.join(template_dir, MIDDLE_TEMPLATE)).read()
    footer = open(os.path.join(template_dir, FOOTER_TEMPLATE)).read()
  except (OSError, IOError):
    logging.error('Could not read template files from %s', template_dir)
    raise

  ApplicationLoggingHandler.InitializeTemplates(header, script, middle, footer)


def CreateServer(root_path,
                 login_url,
                 port,
                 template_dir,
                 serve_address='',
                 require_indexes=False,
                 allow_skipped_files=False,
                 static_caching=True,
                 python_path_list=sys.path,
                 sdk_dir=os.path.dirname(os.path.dirname(google.__file__))):
  """Creates an new HTTPServer for an application.

  The sdk_dir argument must be specified for the directory storing all code for
  the SDK so as to allow for the sandboxing of module access to work for any
  and all SDK code. While typically this is where the 'google' package lives,
  it can be in another location because of API version support.

  Args:
    root_path: String containing the path to the root directory of the
      application where the app.yaml file is.
    login_url: Relative URL which should be used for handling user login/logout.
    port: Port to start the application server on.
    template_dir: Path to the directory in which the debug console templates
      are stored.
    serve_address: Address on which the server should serve.
    require_indexes: True if index.yaml is read-only gospel; default False.
    static_caching: True if browser caching of static files should be allowed.
    python_path_list: Used for dependency injection.
    sdk_dir: Directory where the SDK is stored.

  Returns:
    Instance of BaseHTTPServer.HTTPServer that's ready to start accepting.
  """
  absolute_root_path = os.path.realpath(root_path)

  SetupTemplates(template_dir)
  FakeFile.SetAllowedPaths(absolute_root_path,
                           [sdk_dir,
                            template_dir])
  FakeFile.SetAllowSkippedFiles(allow_skipped_files)

  handler_class = CreateRequestHandler(absolute_root_path,
                                       login_url,
                                       require_indexes,
                                       static_caching)

  if absolute_root_path not in python_path_list:
    python_path_list.insert(0, absolute_root_path)

  return BaseHTTPServer.HTTPServer((serve_address, port), handler_class)
