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
"""The main entry point for the new development server."""


import argparse
import errno
import getpass
import itertools
import logging
import os
import signal
import sys
import tempfile
import time

from google.appengine.datastore import datastore_stub_util
from google.appengine.tools import boolean_action
from google.appengine.tools.devappserver2.admin import admin_server
from google.appengine.tools.devappserver2 import api_server
from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import dispatcher
from google.appengine.tools.devappserver2 import login
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import update_checker
from google.appengine.tools.devappserver2 import wsgi_request_info

# Initialize logging early -- otherwise some library packages may
# pre-empt our log formatting.  NOTE: the level is provisional; it may
# be changed in main() based on the --debug flag.
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(asctime)s %(filename)s:%(lineno)s] %(message)s')

# Valid choices for --log_level and their corresponding numeric logging levels
LOG_LEVEL_MAP = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}


def _generate_storage_paths(app_id):
  """Yield an infinite sequence of possible storage paths."""
  try:
    user_name = getpass.getuser()
  except Exception:  # The possible set of exceptions is not documented.
    user_format = ''
  else:
    user_format = '.%s' % user_name

  tempdir = tempfile.gettempdir()
  yield os.path.join(tempdir, 'appengine.%s%s' % (app_id, user_format))
  for i in itertools.count(1):
    yield os.path.join(tempdir, 'appengine.%s%s.%d' % (app_id, user_format, i))


def _get_storage_path(path, app_id):
  """Returns a path to the directory where stub data can be stored."""
  if path is None:
    for path in _generate_storage_paths(app_id):
      try:
        os.mkdir(path, 0700)
      except OSError, e:
        if e.errno == errno.EEXIST:
          # Check that the directory is only accessable by the current user to
          # protect against an attacker creating the directory in advance in
          # order to access any created files. Windows has per-user temporary
          # directories and st_mode does not include per-user permission
          # information so assume that it is safe.
          if sys.platform == 'win32' or (
              (os.stat(path).st_mode & 0777) == 0700 and os.path.isdir(path)):
            return path
          else:
            continue
        raise
      else:
        return path
  elif not os.path.exists(path):
    os.mkdir(path)
    return path
  elif not os.path.isdir(path):
    raise IOError('the given storage path %r is a file, a directory was '
                  'expected' % path)
  else:
    return path


class PortParser(object):
  """A parser for ints that represent ports."""

  def __init__(self, allow_port_zero=True):
    self._min_port = 0 if allow_port_zero else 1

  def __call__(self, value):
    try:
      port = int(value)
    except ValueError:
      raise argparse.ArgumentTypeError('Invalid port: %r' % value)
    if port < self._min_port or port >= (1 << 16):
      raise argparse.ArgumentTypeError('Invalid port: %d' % port)
    return port


def parse_command_arguments(args):
  """Parses and the application's command line arguments.

  Args:
    args: A list of command line arguments *not* including the executable or
        script e.g. ['--log_level=debug', '--api_port=8000'].

  Returns:
    An object containing the values passed in the commandline as attributes.

  Raises:
    SystemExit: if the argument parsing fails.
  """
  # TODO: Add more robust argument validation. Consider what flags
  # are actually needed.
  parser = argparse.ArgumentParser(
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('yaml_files', nargs='+')
  parser.add_argument('--host', default='localhost',
                      help='host name to which application servers should bind')
  parser.add_argument('--admin_host', default='localhost',
                      help='host name to which the admin server should bind')
  parser.add_argument('--storage_path', metavar='PATH',
                      help='path to the data (datastore, blobstore, etc.) '
                      'associated with the application.')

  parser.add_argument(
      '--log_level', default='info',
      choices=LOG_LEVEL_MAP.keys(),
      help='the log level below which logging messages will not be displayed')

  parser.add_argument(
      '--port', type=PortParser(), default=8080,
      help='lowest port to which application servers should bind')

  parser.add_argument('--admin_port', type=PortParser(), default=8000,
                      help='port to which the admin server should bind')

  parser.add_argument('--api_port', type=PortParser(), default=0,
                      help='port to which the server for API calls should bind')



  parser.add_argument(
      '--skip_sdk_update_check',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='skip checking for SDK updates (if false, use .appcfg_nag to '
      'decide)')

  # Blobstore
  parser.add_argument('--blobstore_path',
                      help='path to directory used to store blob contents '
                      '(defaults to a subdirectory of --storage_path if not '
                      'set)',
                      default=None)

  # Cloud SQL
  parser.add_argument(
      '--mysql_host',
      default='localhost',
      help='host name of a running MySQL server used for simulated Google '
      'Cloud SQL storage')

  parser.add_argument(
      '--mysql_port', type=PortParser(allow_port_zero=False),
      default=3306,
      help='port number of a running MySQL server used for simulated Google '
      'Cloud SQL storage')

  parser.add_argument(
      '--mysql_user',
      default='',
      help='username to use when connecting to the MySQL server specified in '
      '--mysql_host and --mysql_port or --mysql_socket')

  parser.add_argument(
      '--mysql_password',
      default='',
      help='passpord to use when connecting to the MySQL server specified in '
      '--mysql_host and --mysql_port or --mysql_socket')


  parser.add_argument(
      '--mysql_socket',
      help='path to a Unix socket file to use when connecting to a running '
      'MySQL server used for simulated Google Cloud SQL storage')

  # Datastore
  parser.add_argument('--datastore_path', default=None,
                      help='path to a file used to store datastore contents '
                      '(defaults to a file in --storage_path if not set)',)
  parser.add_argument(
      '--datastore_consistency_policy',
      default='time',
      choices=['consistent', 'random', 'time'],
      help='the policy to apply when deciding whether a datastore write should '
      'appear in global queries')

  parser.add_argument('--require_indexes',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False,
                      help='generate an error on datastore queries that '
                      'requires a composite index not found in index.yaml')
  parser.add_argument('--clear_datastore',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False,
                      help='clear the datastore on startup')

  # Logs
  parser.add_argument('--logs_path', default=None,
                      help='path to a file used to store request logs '
                      '(defaults to a file in --storage_path if not set)',)

  # Mail
  parser.add_argument('--enable_sendmail',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False,
                      help='use the "sendmail" tool to transmit e-mail sent '
                      'using the Mail API (ignored if --smpt_host is set)')
  parser.add_argument('--smtp_host', default='',
                      help='host name of an SMTP server to use to transmit '
                      'e-mail sent using the Mail API')
  parser.add_argument('--smtp_port', default=25,
                      type=PortParser(allow_port_zero=False),
                      help='port number of an SMTP server to use to transmit '
                      'e-mail sent using the Mail API (ignored if --smtp_host '
                      'is not set)')
  parser.add_argument('--smtp_user', default='',
                      help='username to use when connecting to the SMTP server '
                      'specified in --smtp_host and --smtp_port')
  parser.add_argument('--smtp_password', default='',
                      help='password to use when connecting to the SMTP server '
                      'specified in --smtp_host and --smtp_port')
  parser.add_argument('--show_mail_body',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False,
                      help='logs the contents of e-mails sent using the Mail '
                      'API')

  # Matcher
  parser.add_argument('--prospective_search_path', default=None,
                      help='path to a file used to store the prospective '
                      'search subscription index (defaults to a file in '
                      '--storage_path if not set)')

  parser.add_argument('--clear_prospective_search',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False,
                      help='clear the prospective search subscription index')

  # Search
  parser.add_argument('--search_indexes_path', default=None,
                      help='path to a file used to store search indexes '
                      '(defaults to a file in --storage_path if not set)',)
  parser.add_argument('--clear_search_indexes',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False,
                      help='clear the search indexes')

  # Taskqueue
  parser.add_argument('--enable_task_running',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=True,
                      help='run "push" tasks created using the taskqueue API '
                      'automatically')

  options = parser.parse_args(args)
  return options


def _clear_datastore_storage(datastore_path):
  """Delete the datastore storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(datastore_path):
    try:
      os.remove(datastore_path)
    except OSError, e:
      logging.warning('Failed to remove datastore file %r: %s',
                      datastore_path,
                      e)


def _clear_prospective_search_storage(prospective_search_path):
  """Delete the perspective search storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(prospective_search_path):
    try:
      os.remove(prospective_search_path)
    except OSError, e:
      logging.warning('Failed to remove prospective search file %r: %s',
                      prospective_search_path,
                      e)


def _clear_search_indexes_storage(search_index_path):
  """Delete the search indexes storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(search_index_path):
    try:
      os.remove(search_index_path)
    except OSError, e:
      logging.warning('Failed to remove search indexes file %r: %s',
                      search_index_path,
                      e)


def _setup_environ(app_id):
  """Sets up the os.environ dictionary for the front-end server and API server.

  This function should only be called once.

  Args:
    app_id: The id of the application.
  """
  os.environ['APPLICATION_ID'] = app_id


class DevelopmentServer(object):
  """Encapsulates the logic for the development server.

  Only a single instance of the class may be created per process. See
  _setup_environ.
  """

  def __init__(self):
    # A list of servers that are currently running.
    self._running_servers = []
    self._server_to_port = {}

  def server_to_address(self, server_name, instance=None):
    """Returns the address of a server."""
    return self._dispatcher.get_hostname(
        server_name,
        self._dispatcher.get_default_version(server_name),
        instance)

  def start(self, options):
    """Start devappserver2 servers based on the provided command line arguments.

    Args:
      options: An argparse.Namespace containing the command line arguments.
    """
    # Set the default logger's log level as configured by the user
    log_level = LOG_LEVEL_MAP[options.log_level]
    logging.getLogger().setLevel(log_level)

    configuration = application_configuration.ApplicationConfiguration(
        options.yaml_files)

    if options.skip_sdk_update_check:
      logging.info('Skipping SDK update check.')
    else:
      update_checker.check_for_updates(configuration)

    _setup_environ(configuration.app_id)

    cloud_sql_config = runtime_config_pb2.CloudSQL()
    cloud_sql_config.mysql_host = options.mysql_host
    cloud_sql_config.mysql_port = options.mysql_port
    cloud_sql_config.mysql_user = options.mysql_user
    cloud_sql_config.mysql_password = options.mysql_password
    if options.mysql_socket:
      cloud_sql_config.mysql_socket = options.mysql_socket

    self._dispatcher = dispatcher.Dispatcher(configuration,
                                             options.host,
                                             options.port,

                                             cloud_sql_config)
    request_data = wsgi_request_info.WSGIRequestInfo(self._dispatcher)

    storage_path = _get_storage_path(options.storage_path, configuration.app_id)
    datastore_path = options.datastore_path or os.path.join(storage_path,
                                                            'datastore.db')
    logs_path = options.logs_path or os.path.join(storage_path, 'logs.db')
    xsrf_path = os.path.join(storage_path, 'xsrf')

    search_index_path = options.search_indexes_path or os.path.join(
        storage_path, 'search_indexes')

    prospective_search_path = options.prospective_search_path or os.path.join(
        storage_path, 'prospective-search')

    blobstore_path = options.blobstore_path or os.path.join(storage_path,
                                                            'blobs')

    if options.clear_datastore:
      _clear_datastore_storage(datastore_path)

    if options.clear_prospective_search:
      _clear_prospective_search_storage(prospective_search_path)

    if options.clear_search_indexes:
      _clear_search_indexes_storage(search_index_path)

    application_address = '%s' % options.host
    if options.port and options.port != 80:
      application_address += ':' + str(options.port)

    user_login_url = '/%s?%s=%%s' % (login.LOGIN_URL_RELATIVE,
                                     login.CONTINUE_PARAM)
    user_logout_url = '%s&%s=%s' % (user_login_url, login.ACTION_PARAM,
                                    login.LOGOUT_ACTION)

    if options.datastore_consistency_policy == 'time':
      consistency = datastore_stub_util.TimeBasedHRConsistencyPolicy()
    elif options.datastore_consistency_policy == 'random':
      consistency = datastore_stub_util.PseudoRandomHRConsistencyPolicy()
    elif options.datastore_consistency_policy == 'consistent':
      consistency = datastore_stub_util.PseudoRandomHRConsistencyPolicy(1.0)
    else:
      assert 0, ('unknown consistency policy: %r' %
                 options.datastore_consistency_policy)

    api_server.setup_stubs(
        request_data=request_data,
        app_id=configuration.app_id,
        application_root=configuration.servers[0].application_root,
        # The "trusted" flag is only relevant for Google administrative
        # applications.
        trusted=getattr(options, 'trusted', False),
        blobstore_path=blobstore_path,
        datastore_path=datastore_path,
        datastore_consistency=consistency,
        datastore_require_indexes=options.require_indexes,
        images_host_prefix='http://%s' % application_address,
        logs_path=logs_path,
        mail_smtp_host=options.smtp_host,
        mail_smtp_port=options.smtp_port,
        mail_smtp_user=options.smtp_user,
        mail_smtp_password=options.smtp_password,
        mail_enable_sendmail=options.enable_sendmail,
        mail_show_mail_body=options.show_mail_body,
        matcher_prospective_search_path=prospective_search_path,
        search_index_path=search_index_path,
        taskqueue_auto_run_tasks=options.enable_task_running,
        taskqueue_default_http_server=application_address,
        user_login_url=user_login_url,
        user_logout_url=user_logout_url)

    # The APIServer must bind to localhost because that is what the runtime
    # instances talk to.
    apis = api_server.APIServer('localhost', options.api_port,
                                configuration.app_id)
    apis.start()
    self._running_servers.append(apis)

    self._running_servers.append(self._dispatcher)
    self._dispatcher.start(apis.port, request_data)

    admin = admin_server.AdminServer(options.admin_host, options.admin_port,
                                     self._dispatcher, configuration, xsrf_path)
    admin.start()
    self._running_servers.append(admin)

  def stop(self):
    """Stops all running devappserver2 servers."""
    while self._running_servers:
      self._running_servers.pop().quit()


def _install_signal_handler():
  signal.signal(signal.SIGTERM, signal.getsignal(signal.SIGINT))


def main():
  logging.warning(
      'devappserver2.py is currently experimental but will eventually replace '
      'dev_appserver.py in the App Engine Python SDK. For more information and '
      'to report bugs, please see: '
      'http://code.google.com/p/appengine-devappserver2-experiment/')

  _install_signal_handler()
  # The timezone must be set in the devappserver2 process rather than just in
  # the runtime so printed log timestamps are consistent and the taskqueue stub
  # expects the timezone to be UTC. The runtime inherits the environment.
  os.environ['TZ'] = 'UTC'
  if hasattr(time, 'tzset'):
    # time.tzet() should be called on Unix, but doesn't exist on Windows.
    time.tzset()
  options = parse_command_arguments(sys.argv[1:])
  dev_server = DevelopmentServer()
  try:
    dev_server.start(options)
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    pass
  finally:
    dev_server.stop()


if __name__ == '__main__':
  main()
