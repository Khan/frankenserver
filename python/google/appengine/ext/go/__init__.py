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




"""A bridge between dev_appserver.py and a Go app."""























import asyncore
import atexit
import datetime
import errno
import getpass
import logging
import os
import shutil
import signal
import socket
import subprocess
import stat
import sys
import tempfile
import time

from google.appengine.ext.remote_api import handler
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.tools import dev_appserver

GAB_WORK_DIR = None
GO_APP = None
GO_APP_NAME = '_go_app'
RAPI_HANDLER = None
SOCKET_HTTP = os.path.join(tempfile.gettempdir(),
                           'dev_appserver_%s_socket_http')
SOCKET_API = os.path.join(tempfile.gettempdir(), 'dev_appserver_%s_socket_api')
HEALTH_CHECK_PATH = '/_appengine_delegate_health_check'
INTERNAL_SERVER_ERROR = ('Status: 500 Internal Server Error\r\n' +
    'Content-Type: text/plain\r\n\r\nInternal Server Error')
MAX_START_TIME = 1



HEADER_MAP = {
    'APPLICATION_ID': 'X-AppEngine-Inbound-AppId',
    'CONTENT_TYPE': 'Content-Type',
    'CURRENT_VERSION_ID': 'X-AppEngine-Inbound-Version-Id',
    'HTTP_HOST': 'X-AppEngine-Default-Version-Hostname',
    'REMOTE_ADDR': 'X-AppEngine-Remote-Addr',
    'USER_EMAIL': 'X-AppEngine-Inbound-User-Email',
    'USER_ID': 'X-AppEngine-Inbound-User-Id',
    'USER_IS_ADMIN': 'X-AppEngine-Inbound-User-Is-Admin',
}


APP_CONFIG = None


def gab_work_dir():
  base = os.getenv('XDG_CACHE_HOME')
  if not base:
    if sys.platform == 'darwin':
      base = os.path.join(os.getenv('HOME'), 'Library', 'Caches',
                          'com.google.GoAppEngine')
    else:

      base = os.path.join(os.getenv('HOME'), '.cache')


  if os.path.islink(base):
    try:
      os.makedirs(os.path.realpath(base))
    except OSError, e:

      if e.errno != errno.EEXIST:
        raise
  return os.path.join(base, 'dev_appserver_%s_go_app_work_dir')


def cleanup():
  try:
    shutil.rmtree(GAB_WORK_DIR)
  except:
    pass
  for fn in [SOCKET_HTTP, SOCKET_API]:
    try:
      os.remove(fn)
    except:
      pass


class DelegateClient(asyncore.dispatcher):
  def __init__(self, http_req):
    asyncore.dispatcher.__init__(self)
    self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.connect(SOCKET_HTTP)
    self.buffer = http_req
    self.result = ''
    self.closed = False

  def handle_close(self):
    self.close()
    self.closed = True

  def handle_connect(self):
    pass

  def handle_read(self):
    self.result += self.recv(8192)

  def handle_write(self):
    sent = self.send(self.buffer)
    self.buffer = self.buffer[sent:]

  def writable(self):
    return len(self.buffer) > 0


class DelegateServer(asyncore.dispatcher):
  def __init__(self):
    asyncore.dispatcher.__init__(self)
    self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
      os.remove(SOCKET_API)
    except OSError:
      pass
    self.bind(SOCKET_API)
    self.listen(5)

  def handle_accept(self):
    pair = self.accept()
    if not pair:
      return
    sock, addr = pair
    RemoteAPIHandler(sock)

  def writable(self):
    return False


class RemoteAPIHandler(asyncore.dispatcher_with_send):
  def __init__(self, sock):
    asyncore.dispatcher_with_send.__init__(self, sock)



    self.n = -1
    self.data = ''

  def handle_read(self):
    self.data += self.recv(8192)
    if self.n == -1:
      i = self.data.find('\n')
      if i == -1:

        return
      try:
        self.n = int(self.data[:i])
      except:
        self.n = -2
      if self.n < 0:

        self.n = -2
        self.data = ''
        return
      self.data = self.data[i+1:]
    elif self.n == -2:
      self.data = ''
      return
    if len(self.data) < self.n:

      return

    req = remote_api_pb.Request()
    req.ParseFromString(self.data[:self.n])
    self.data, self.n = self.data[self.n:], -1
    rapi_result = None
    rapi_error = 'unknown error'
    try:
      rapi_result = RAPI_HANDLER.ExecuteRequest(req)
    except Exception, e:
      rapi_error = str(e)

    res = remote_api_pb.Response()
    if rapi_result:
      res.set_response(rapi_result.Encode())
    else:
      ae = res.mutable_application_error()


      ae.set_code(1)
      ae.set_detail(rapi_error)
    res1 = res.Encode()
    self.send('%d\n' % len(res1))
    self.send(res1)




def find_app_files(basedir):
  if not basedir.endswith(os.path.sep):
    basedir = basedir + os.path.sep
  files, dirs = {}, [basedir]
  while dirs:
    dname = dirs.pop()
    for entry in os.listdir(dname):
      ename = os.path.join(dname, entry)
      if APP_CONFIG.skip_files.match(ename):
        continue
      s = os.stat(ename)
      if stat.S_ISDIR(s[stat.ST_MODE]):
        dirs.append(ename)
        continue
      files[ename[len(basedir):]] = s[stat.ST_MTIME]
  return files




def find_go_files_mtime(app_files):
  files, mtime = [], 0
  for f, mt in app_files.items():
    if not f.endswith('.go'):
      continue
    if APP_CONFIG.nobuild_files.match(f):
      continue
    files.append(f)
    mtime = max(mtime, mt)
  return files, mtime


def wait_until_go_app_ready(pid):

  deadline = (datetime.datetime.now() +
              datetime.timedelta(seconds=MAX_START_TIME))
  while datetime.datetime.now() < deadline:
    try:
      s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      s.connect(SOCKET_HTTP)
      s.send('HEAD %s HTTP/1.0\r\n\r\n' % HEALTH_CHECK_PATH)
      s.close()
      return
    except:
      time.sleep(0.1)
  os.kill(pid, signal.SIGTERM)
  raise Exception('unable to start ' + GO_APP_NAME)


def up(path, n):
  """Return the nth parent directory of the given path."""
  for _ in range(n):
    path = os.path.dirname(path)
  return path


class GoApp:
  def __init__(self, root_path):
    self.root_path = root_path
    self.proc = None
    self.proc_start = 0
    self.goroot = os.path.join(

        up(__file__, 5),
        "goroot")
    if not os.path.isdir(self.goroot):
      raise Exception('no goroot found at ' + self.goroot)


    for bin in os.listdir(os.path.join(self.goroot, 'bin')):
      if len(bin) == 2 and bin[1] == 'g':
        self.arch = bin[0]
        break
    if not self.arch:
      raise Exception('bad goroot: no compiler found')

    atexit.register(self.cleanup)

  def cleanup(self):
    if self.proc:
      os.kill(self.proc.pid, signal.SIGTERM)

  def make_and_run(self):
    app_files = find_app_files(self.root_path)
    go_files, go_mtime = find_go_files_mtime(app_files)
    if not go_files:
      raise Exception('no .go files in %s', self.root_path)
    app_mtime = max(app_files.values())
    bin_name, bin_mtime = os.path.join(GAB_WORK_DIR, GO_APP_NAME), 0
    try:
      bin_mtime = os.stat(bin_name)[stat.ST_MTIME]
    except:
      pass




    rebuild, restart = False, False
    if go_mtime >= bin_mtime:
      rebuild, restart = True, True
    elif app_mtime > self.proc_start:
      restart = True

    if restart and self.proc:
      os.kill(self.proc.pid, signal.SIGTERM)
      self.proc.wait()
      self.proc = None
    if rebuild:
      self.build(go_files)


    if not self.proc or self.proc.poll() is not None:
      logging.info('running ' + GO_APP_NAME)

      env = {
          'PWD': self.root_path,
          'TZ': 'UTC',
      }
      self.proc_start = app_mtime
      self.proc = subprocess.Popen([bin_name,
          '-addr_http', 'unix:' + SOCKET_HTTP,
          '-addr_api', 'unix:' + SOCKET_API],
          cwd=self.root_path, env=env)
      wait_until_go_app_ready(self.proc.pid)

  def build(self, go_files):
    logging.info('building ' + GO_APP_NAME)
    if not os.path.exists(GAB_WORK_DIR):
      os.makedirs(GAB_WORK_DIR)
    gab_argv = [
        os.path.join(self.goroot, 'bin', 'go-app-builder'),
        '-app_base', self.root_path,
        '-arch', self.arch,
        '-binary_name', GO_APP_NAME,
        '-dynamic',
        '-goroot', self.goroot,
        '-unsafe',
        '-work_dir', GAB_WORK_DIR] + go_files
    try:
      p = subprocess.Popen(gab_argv, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env={})
      gab_retcode = p.wait()
    except Exception, e:
      raise Exception('cannot call go-app-builder', e)
    if gab_retcode != 0:
      raise dev_appserver.CompileError(p.stdout.read() + '\n' + p.stderr.read())


def execute_go_cgi(root_path, handler_path, cgi_path, env, infile, outfile):

  global RAPI_HANDLER, GAB_WORK_DIR, SOCKET_HTTP, SOCKET_API, GO_APP
  if not RAPI_HANDLER:
    user_port = '%s_%s' % (getpass.getuser(), env['SERVER_PORT'])
    GAB_WORK_DIR = gab_work_dir() % user_port
    SOCKET_HTTP = SOCKET_HTTP % user_port
    SOCKET_API = SOCKET_API % user_port
    atexit.register(cleanup)
    DelegateServer()
    RAPI_HANDLER = handler.ApiCallHandler()
    GO_APP = GoApp(root_path)
  GO_APP.make_and_run()


  request_method = env['REQUEST_METHOD']
  server_protocol = env['SERVER_PROTOCOL']
  request_uri = env['PATH_INFO']
  if env.get('QUERY_STRING'):
    request_uri += '?' + env['QUERY_STRING']
  content = infile.getvalue()
  headers = []
  for k, v in env.items():
    if k in HEADER_MAP:
      headers.append('%s: %s' % (HEADER_MAP[k], v))
    elif k.startswith('HTTP_'):
      hk = k[5:].replace("_", "-")
      if hk.title() == 'Connection':
        continue
      headers.append('%s: %s' % (hk, v))

  headers.append('Content-Length: %d' % len(content))
  headers.append('Connection: close')
  http_req = (request_method + ' ' + request_uri + ' ' + server_protocol +
      '\r\n' + '\r\n'.join(headers) + '\r\n\r\n' + content)





  old_env = os.environ.copy()
  try:
    os.environ.clear()
    os.environ.update(env)


    x = DelegateClient(http_req)
    while not x.closed:
      asyncore.loop(30.0, False, None, 1)
    res = x.result
  finally:
    os.environ.clear()
    os.environ.update(old_env)



  if res.startswith('HTTP/1.0 ') or res.startswith('HTTP/1.1 '):
    res = 'Status:' + res[8:]
  else:
    res = INTERNAL_SERVER_ERROR
  outfile.write(res)
