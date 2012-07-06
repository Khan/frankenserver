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




"""Serves the stub App Engine APIs (e.g. memcache, datastore) over HTTP.

The Remote API protocol is used for communication.
"""

from __future__ import with_statement


import BaseHTTPServer
import httplib
import logging
import os.path
import pickle
import socket
import SocketServer
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib2
import urlparse

import google
import yaml


from google.appengine.api import mail_stub
from google.appengine.api import urlfetch_stub
from google.appengine.api import user_service_stub
from google.appengine.api.app_identity import app_identity_stub
from google.appengine.api.blobstore import blobstore_stub
from google.appengine.api.blobstore import file_blob_storage
from google.appengine.api.capabilities import capability_stub
from google.appengine.api.conversion import conversion_stub
from google.appengine.api.channel import channel_service_stub
from google.appengine.api.files import file_service_stub
from google.appengine.api.logservice import logservice_stub
from google.appengine.api.search import simple_search_stub
from google.appengine.api.taskqueue import taskqueue_stub
from google.appengine.api.prospective_search import prospective_search_stub
from google.appengine.api.memcache import memcache_stub
from google.appengine.api.system import system_stub
from google.appengine.api.xmpp import xmpp_service_stub
from google.appengine.api import datastore_file_stub
from google.appengine.datastore import datastore_sqlite_stub
from google.appengine.datastore import datastore_stub_util

from google.appengine.api import apiproxy_stub_map
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.ext.remote_api import remote_api_services
from google.appengine.runtime import apiproxy_errors


QUIT_PATH = '/quit'


GLOBAL_API_LOCK = threading.RLock()


class Error(Exception):
  pass


def _ClearDatastoreStorage(datastore_path):
  """Delete the datastore storage file at the given path."""

  if os.path.lexists(datastore_path):
    try:
      os.remove(datastore_path)
    except OSError, e:
      logging.warning('Failed to remove datastore file %r: %s',
                      datastore_path,
                      e)


def _ClearProspectiveSearchStorage(prospective_search_path):
  """Delete the perspective search storage file at the given path."""

  if os.path.lexists(prospective_search_path):
    try:
      os.remove(prospective_search_path)
    except OSError, e:
      logging.warning('Failed to remove prospective search file %r: %s',
                      prospective_search_path,
                      e)




THREAD_SAFE_SERVICES = frozenset((
    'app_identity_service',
    'capability_service',
    'channel',
    'conversion',
    'mail',
    'memcache',
    'urlfetch',
    'user',
    'xmpp',
))


def _ExecuteRequest(request):
  """Executes an API method call and returns the response object.

  Args:
    request: A remote_api.Request object representing the API call e.g. a call
        to memcache.Get.

  Returns:
    A ProtocolBuffer.ProtocolMessage representing the API response e.g. a
    memcache_service_pb.MemcacheGetResponse.

  Raises:
    apiproxy_errors.CallNotFoundError: if the requested method doesn't exist.
    apiproxy_errors.ApplicationError: if the API method calls fails.
  """
  service = request.service_name()
  method = request.method()
  service_methods = remote_api_services.SERVICE_PB_MAP.get(service, {})
  request_class, response_class = service_methods.get(method, (None, None))
  if not request_class:
    raise apiproxy_errors.CallNotFoundError('%s.%s does not exist' % (service,
                                                                      method))

  request_data = request_class()
  request_data.ParseFromString(request.request())
  response_data = response_class()

  def MakeRequest():
    apiproxy_stub_map.MakeSyncCall(service, method, request_data,
                                   response_data)



  if service in THREAD_SAFE_SERVICES:
    MakeRequest()
  else:
    with GLOBAL_API_LOCK:
      MakeRequest()
  return response_data


class APIRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  """Handler for all API server HTTP requests."""

  def log_message(self, format, *args):
    logging.debug(format, *args)

  def do_GET(self):
    if self.path == QUIT_PATH:
      self._HandleShutdown()
    else:
      params = urlparse.parse_qs(urlparse.urlparse(self.path).query)
      rtok = params.get('rtok', ['0'])[0]

      self.send_response(httplib.OK)
      self.send_header('Content-Type', 'text/plain')
      self.end_headers()
      self.wfile.write(yaml.dump({
          'app_id': self.server.app_id,
          'rtok': rtok,
          }))

  def _HandleShutdown(self):
    """Handles a request for the API Server to exit."""
    self.send_response(httplib.OK)
    self.send_header('Content-Type', 'text/plain')
    self.end_headers()
    self.wfile.write('API Server Quitting')
    self.server.shutdown()

  def do_POST(self):
    """Handles a single API request e.g. memcache.Get()."""
    self.send_response(httplib.OK)
    self.send_header('Content-Type', 'application/octet-stream')
    self.end_headers()

    response = remote_api_pb.Response()
    try:
      request = remote_api_pb.Request()



      request.ParseFromString(
          self.rfile.read(int(self.headers['content-length'])))
      api_response = _ExecuteRequest(request).Encode()
      response.set_response(api_response)
    except Exception, e:
      logging.debug('Exception while handling %s\n%s',
                    request,
                    traceback.format_exc())
      response.set_exception(pickle.dumps(e))
      if isinstance(e, apiproxy_errors.ApplicationError):
        application_error = response.mutable_application_error()
        application_error.set_code(e.application_error)
        application_error.set_detail(e.error_detail)
    self.wfile.write(response.Encode())


class APIServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
  """Serves API calls over HTTP."""

  def __init__(self, server_address, app_id):
    BaseHTTPServer.HTTPServer.__init__(self, server_address, APIRequestHandler)
    self.app_id = app_id


def _SetupStubs(
    app_id,
    application_root,
    trusted,
    blobstore_path,
    use_sqlite,
    high_replication,
    datastore_path,
    datastore_require_indexes,
    images_host_prefix,
    persist_logs,
    mail_smtp_host,
    mail_smtp_port,
    mail_smtp_user,
    mail_smtp_password,
    mail_enable_sendmail,
    mail_show_mail_body,
    matcher_prospective_search_path,
    taskqueue_auto_run_tasks,
    taskqueue_task_retry_seconds,
    taskqueue_default_http_server,
    user_login_url,
    user_logout_url):
  """Configures the APIs hosted by this server.

  Args:
    app_id: The str application id e.g. "guestbook".
    application_root: The path to the directory containing the user's
        application e.g. "/home/bquinlan/myapp".
    trusted: A bool indicating if privileged APIs should be made available.
    blobstore_path: The path to the file that should be used for blobstore
        storage.
    use_sqlite: A bool indicating whether DatastoreSqliteStub or
        DatastoreFileStub should be used.
    high_replication: A bool indicating whether to use the high replication
        consistency model.
    datastore_path: The path to the file that should be used for datastore
        storage.
    datastore_require_indexes: A bool indicating if the same production
        datastore indexes requirements should be enforced i.e. if True then
        a google.appengine.ext.db.NeedIndexError will be be raised if a query
        is executed without the required indexes.
    images_host_prefix: The URL prefix (protocol://host:port) to preprend to
        image urls on calls to images.GetUrlBase.
    persist_logs: A bool indicating if request and application logs should be
         persisted for later access.
    mail_smtp_host: The SMTP hostname that should be used when sending e-mails.
        If None then the mail_enable_sendmail argument is considered.
    mail_smtp_port: The SMTP port number that should be used when sending
        e-mails. If this value is None then mail_smtp_host must also be None.
    mail_smtp_user: The username to use when authenticating with the
        SMTP server. This value may be None if mail_smtp_host is also None or if
        the SMTP server does not require authentication.
    mail_smtp_password: The password to use when authenticating with the
        SMTP server. This value may be None if mail_smtp_host or mail_smtp_user
        is also None.
    mail_enable_sendmail: A bool indicating if sendmail should be used when
        sending e-mails. This argument is ignored if mail_smtp_host is not None.
    mail_show_mail_body: A bool indicating whether the body of sent e-mails
        should be written to the logs.
    matcher_prospective_search_path: The path to the file that should be used to
        save prospective search subscriptions.
    taskqueue_auto_run_tasks: A bool indicating whether taskqueue tasks should
        be run automatically or it the must be manually triggered.
    taskqueue_task_retry_seconds: An int representing the number of seconds to
        wait before a retrying a failed taskqueue task.
    taskqueue_default_http_server: A str containing the address of the http
        server that should be used to execute tasks.
    user_login_url: A str containing the url that should be used for user login.
    user_logout_url: A str containing the url that should be used for user
        logout.
  """





  os.environ['APPLICATION_ID'] = app_id



  apiproxy_stub_map.apiproxy.RegisterStub(
      'app_identity_service',
      app_identity_stub.AppIdentityServiceStub())

  blob_storage = file_blob_storage.FileBlobStorage(blobstore_path, app_id)
  apiproxy_stub_map.apiproxy.RegisterStub(
      'blobstore',
      blobstore_stub.BlobstoreServiceStub(blob_storage))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'capability_service',
      capability_stub.CapabilityServiceStub())








  apiproxy_stub_map.apiproxy.RegisterStub(
      'channel',
      channel_service_stub.ChannelServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub(
      'conversion',
      conversion_stub.ConversionServiceStub())

  if use_sqlite:
    datastore = datastore_sqlite_stub.DatastoreSqliteStub(
        app_id,
        datastore_path,
        datastore_require_indexes,
        trusted,
        root_path=application_root)
  else:
    datastore = datastore_file_stub.DatastoreFileStub(
        app_id,
        datastore_path,
        datastore_require_indexes,
        trusted,
        root_path=application_root)

  if high_replication:
    datastore.SetConsistencyPolicy(
        datastore_stub_util.TimeBasedHRConsistencyPolicy())

  apiproxy_stub_map.apiproxy.RegisterStub(
      'datastore_v3', datastore)

  apiproxy_stub_map.apiproxy.RegisterStub(
      'file',
      file_service_stub.FileServiceStub(blob_storage))

  try:
    from google.appengine.api.images import images_stub
  except ImportError:


    logging.warning('Could not initialize images API; you are likely missing '
                    'the Python "PIL" module.')

    from google.appengine.api.images import images_not_implemented_stub
    apiproxy_stub_map.apiproxy.RegisterStub(
        'images',
        images_not_implemented_stub.ImagesNotImplementedServiceStub())
  else:
    apiproxy_stub_map.apiproxy.RegisterStub(
        'images',
        images_stub.ImagesServiceStub(host_prefix=images_host_prefix))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'logservice',
      logservice_stub.LogServiceStub(persist_logs))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'mail',
      mail_stub.MailServiceStub(mail_smtp_host,
                                mail_smtp_port,
                                mail_smtp_user,
                                mail_smtp_password,
                                enable_sendmail=mail_enable_sendmail,
                                show_mail_body=mail_show_mail_body))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'memcache',
      memcache_stub.MemcacheServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub(
      'search',
      simple_search_stub.SearchServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub('system',
                                          system_stub.SystemServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub(
      'taskqueue',
      taskqueue_stub.TaskQueueServiceStub(
          root_path=application_root,
          auto_task_running=taskqueue_auto_run_tasks,
          task_retry_seconds=taskqueue_task_retry_seconds,
          default_http_server=taskqueue_default_http_server))
  apiproxy_stub_map.apiproxy.GetStub('taskqueue').StartBackgroundExecution()

  apiproxy_stub_map.apiproxy.RegisterStub(
      'urlfetch',
      urlfetch_stub.URLFetchServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub(
      'user',
      user_service_stub.UserServiceStub(login_url=user_login_url,
                                        logout_url=user_logout_url))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'xmpp',
      xmpp_service_stub.XmppServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub(
      'matcher',
      prospective_search_stub.ProspectiveSearchStub(
          matcher_prospective_search_path,
          apiproxy_stub_map.apiproxy.GetStub('taskqueue')))


def _TearDownStubs():
  """Clean up any stubs that need cleanup."""

  logging.info('Applying all pending transactions and saving the datastore')
  datastore_stub = apiproxy_stub_map.apiproxy.GetStub('datastore_v3')
  datastore_stub.Write()


def ParseCommandArguments(args):
  """Parses and the application's command line arguments.

  Args:
    args: A list of command line arguments *not* including the executable or
        script e.g. ['-A' 'myapp', '--api_port=8000'].

  Returns:
    An object containing the values passed in the commandline as attributes.

  Raises:
    SystemExit: if the argument parsing fails.
  """



  import argparse
  from google.appengine.tools import boolean_action

  parser = argparse.ArgumentParser()
  parser.add_argument('-A', '--application', required=True)
  parser.add_argument('--api_host', default='')

  parser.add_argument('--api_port', default=8000, type=int)
  parser.add_argument('--trusted',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)
  parser.add_argument('--application_root', default=None)
  parser.add_argument('--application_host', default='localhost')
  parser.add_argument('--application_port', default=None)


  parser.add_argument('--blobstore_path', default=None)


  parser.add_argument('--datastore_path', default=None)
  parser.add_argument('--use_sqlite',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)
  parser.add_argument('--high_replication',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)
  parser.add_argument('--require_indexes',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)
  parser.add_argument('--clear_datastore',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)


  parser.add_argument('--persist_logs',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)


  parser.add_argument('--enable_sendmail',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)
  parser.add_argument('--smtp_host', default='')

  parser.add_argument('--smtp_port', default=25, type=int)
  parser.add_argument('--smtp_user', default='')
  parser.add_argument('--smtp_password', default='')
  parser.add_argument('--show_mail_body',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)


  parser.add_argument('--prospective_search_path', default=None)
  parser.add_argument('--clear_prospective_search',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=False)


  parser.add_argument('--enable_task_running',
                      action=boolean_action.BooleanAction,
                      const=True,
                      default=True)

  parser.add_argument('--task_retry_seconds', default=30, type=int)


  parser.add_argument('--user_login_url', default=None)
  parser.add_argument('--user_logout_url', default=None)

  return parser.parse_args(args)


class APIServerProcess(object):
  """Manages an API Server running as a seperate process."""






  def __init__(self,
               executable,
               host,
               port,
               app_id,
               script=None,
               application_host=None,
               application_port=None,
               application_root=None,
               blobstore_path=None,
               clear_datastore=None,
               clear_prospective_search=None,
               datastore_path=None,
               enable_sendmail=None,
               enable_task_running=None,
               high_replication=None,
               persist_logs=None,
               prospective_search_path=None,
               require_indexes=None,
               show_mail_body=None,
               smtp_host=None,
               smtp_password=None,
               smtp_port=None,
               smtp_user=None,
               task_retry_seconds=None,
               trusted=None,
               use_sqlite=None):
    """Configures the APIs hosted by this server.

    Args:
      executable: The path of the executable to use when running the API Server
          e.g. "/usr/bin/python".
      host: The host name that should be used by the API Server e.g.
          "localhost".
      port: The port number that should be used by the API Server e.g. 8080.
      app_id: The str application id e.g. "guestbook".
      script: The name of the script that should be used, along with the
          executable argument, to run the API Server e.g. "api_server.py".
          If None then the executable is run without a script argument.
      application_host: The name of the host where the development application
          server is running e.g. "localhost".
      application_port: The port where the application server is running e.g.
          8000.
      application_root: The path to the directory containing the user's
          application e.g. "/home/bquinlan/myapp".
      blobstore_path: The path to the file that should be used for blobstore
          storage.
      clear_datastore: Clears the file at datastore_path, emptying the
          datastore from previous runs.
      clear_prospective_search: Clears the file at prospective_search_path,
          emptying the perspective search state from previous runs.
      datastore_path: The path to the file that should be used for datastore
          storage.
      enable_sendmail: A bool indicating if sendmail should be used when sending
          e-mails. This argument is ignored if mail_smtp_host is not None.
      enable_task_running: A bool indicating whether taskqueue tasks should
          be run automatically or it the must be manually triggered.
      high_replication: A bool indicating whether to use the high replication
          consistency model.
      persist_logs: A bool indicating if request and application logs should be
           persisted for later access.
      prospective_search_path: The path to the file that should be used to
          save prospective search subscriptions.
      require_indexes: A bool indicating if the same production
          datastore indexes requirements should be enforced i.e. if True then
          a google.appengine.ext.db.NeedIndexError will be be raised if a query
          is executed without the required indexes.
      show_mail_body: A bool indicating whether the body of sent e-mails
        should be written to the logs.
      smtp_host: The SMTP hostname that should be used when sending e-mails.
          If None then the enable_sendmail argument is considered.
      smtp_password: The password to use when authenticating with the
          SMTP server. This value may be None if smtp_host or smtp_user
          is also None.
      smtp_port: The SMTP port number that should be used when sending
          e-mails. If this value is None then smtp_host must also be None.
      smtp_user: The username to use when authenticating with the
          SMTP server. This value may be None if smtp_host is also None or if
          the SMTP server does not require authentication.
      task_retry_seconds: An int representing the number of seconds to
          wait before a retrying a failed taskqueue task.
      trusted: A bool indicating if privileged APIs should be made available.
      use_sqlite: A bool indicating whether DatastoreSqliteStub or
          DatastoreFileStub should be used.
    """
    self._process = None
    self._host = host
    self._port = port
    if script:
      self._args = [executable, script]
    else:
      self._args = [executable]
    self._BindArgument('--api_host', host)
    self._BindArgument('--api_port', port)
    self._BindArgument('--application_host', application_host)
    self._BindArgument('--application_port', application_port)
    self._BindArgument('--application_root', application_root)
    self._BindArgument('--application', app_id)
    self._BindArgument('--blobstore_path', blobstore_path)
    self._BindArgument('--clear_datastore', clear_datastore)
    self._BindArgument('--clear_prospective_search', clear_prospective_search)
    self._BindArgument('--datastore_path', datastore_path)
    self._BindArgument('--enable_sendmail', enable_sendmail)
    self._BindArgument('--enable_task_running', enable_task_running)
    self._BindArgument('--high_replication', high_replication)
    self._BindArgument('--persist_logs', persist_logs)
    self._BindArgument('--prospective_search_path', prospective_search_path)
    self._BindArgument('--require_indexes', require_indexes)
    self._BindArgument('--show_mail_body', show_mail_body)
    self._BindArgument('--smtp_host', smtp_host)
    self._BindArgument('--smtp_password', smtp_password)
    self._BindArgument('--smtp_port', smtp_port)
    self._BindArgument('--smtp_user', smtp_user)
    self._BindArgument('--task_retry_seconds', task_retry_seconds)
    self._BindArgument('--trusted', trusted)
    self._BindArgument('--use_sqlite', use_sqlite)

  @property
  def url(self):
    """Returns the URL that should be used to communicate with the server."""
    return 'http://%s:%d' % (self._host, self._port)

  def __repr__(self):
    return '<APIServerProcess command=%r>' % ' '.join(self._args)

  def Start(self):
    """Starts the API Server process."""



    assert not self._process, 'Start() can only be called once'
    self._process = subprocess.Popen(self._args)

  def _CanConnect(self):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      s.connect((self._host, self._port))
    except socket.error:
      connected = False
    else:
      connected = True
    s.close()
    return connected

  def WaitUntilServing(self, timeout=30.0):
    """Waits until the API Server is ready to handle requests.

    Args:
      timeout: The maximum number of seconds to wait for the server to be ready.

    Raises:
      Error: if the server process exits or is not ready in "timeout" seconds.
    """
    assert self._process, 'server was not started'
    finish_time = time.time() + timeout
    while time.time() < finish_time:
      if self._process.poll() is not None:
        raise Error('server has already exited with return: %r',
                    self._process.returncode)
      if self._CanConnect():
        return
      time.sleep(0.2)
    raise Error('server did not start after %f seconds', timeout)

  def _BindArgument(self, argument, value):
    if value is not None:
      self._args.append('%s=%s' % (argument, value))

  def Quit(self, timeout=5.0):
    """Causes the API Server process to exit.

    Args:
      timeout: The maximum number of seconds to wait for an orderly shutdown
          before forceably killing the process.
    """
    assert self._process, 'server was not started'
    if self._process.poll() is None:
      try:
        urllib2.urlopen(self.url + QUIT_PATH)
      except urllib2.URLError:


        pass

      finish_time = time.time() + timeout
      while time.time() < finish_time and self._process.poll() is None:
        time.sleep(0.2)
      if self._process.returncode is None:
        logging.warning('api_server did not quit cleanly, killing')
        self._process.kill()


def main():

  logging.basicConfig(
      level=logging.INFO,
      format='[API Server] [%(filename)s:%(lineno)d] %(levelname)s %(message)s')

  args = ParseCommandArguments(sys.argv[1:])

  if args.clear_datastore:
    _ClearDatastoreStorage(args.datastore_path)

  if args.clear_prospective_search:
    _ClearProspectiveSearchStorage(args.prospective_search_path)

  if args.blobstore_path is None:
    _, blobstore_temp_filename = tempfile.mkstemp(prefix='ae-blobstore')
    args.blobstore_path = blobstore_temp_filename

  if args.datastore_path is None:
    _, datastore_temp_filename = tempfile.mkstemp(prefix='ae-datastore')
    args.datastore_path = datastore_temp_filename

  if args.prospective_search_path is None:
    _, prospective_search_temp_filename = tempfile.mkstemp(
        prefix='ae-prospective_search')
    args.prospective_search_path = prospective_search_temp_filename

  if args.application_host:
    application_address = args.application_host
    if args.application_port and args.application_port != 80:
      application_address += ':' + str(args.application_port)
  else:
    application_address = None

  _SetupStubs(app_id=args.application,
              application_root=args.application_root,
              trusted=args.trusted,
              blobstore_path=args.blobstore_path,
              datastore_path=args.datastore_path,
              use_sqlite=args.use_sqlite,
              high_replication=args.high_replication,
              datastore_require_indexes=args.require_indexes,
              images_host_prefix=application_address,
              persist_logs=args.persist_logs,
              mail_smtp_host=args.smtp_host,
              mail_smtp_port=args.smtp_port,
              mail_smtp_user=args.smtp_user,
              mail_smtp_password=args.smtp_password,
              mail_enable_sendmail=args.enable_sendmail,
              mail_show_mail_body=args.show_mail_body,
              matcher_prospective_search_path=args.prospective_search_path,
              taskqueue_auto_run_tasks=args.enable_task_running,
              taskqueue_task_retry_seconds=args.task_retry_seconds,
              taskqueue_default_http_server=application_address,
              user_login_url=args.user_login_url,
              user_logout_url=args.user_logout_url)
  server = APIServer((args.api_host, args.api_port), args.application)
  try:
    server.serve_forever()
  finally:
    _TearDownStubs()


if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    pass
