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

"""Imports CSV data over HTTP.

Usage:
  %(arg0)s [flags]

    --debug                 Show debugging information. (Optional)
    --app_id=<string>       Application ID of endpoint (Optional for
                            *.appspot.com)
    --auth_domain=<domain>  The auth domain to use for logging in and for
                            UserProperties. (Default: gmail.com)
    --bandwidth_limit=<int> The maximum number of bytes per second for the
                            aggregate transfer of data to the server. Bursts
    --batch_size=<int>      Number of Entity objects to include in each post to
                            the URL endpoint. The more data per row/Entity, the
                            smaller the batch size should be. (Default 10)
    --config_file=<path>    File containing Model and Loader definitions.
                            (Required)
    --db_filename=<path>    Specific progress database to write to, or to
                            resume from. If not supplied, then a new database
                            will be started, named:
                            bulkloader-progress-TIMESTAMP.
                            The special filename "skip" may be used to simply
                            skip reading/writing any progress information.
    --filename=<path>       Path to the CSV file to import. (Required)
    --http_limit=<int>      The maximum numer of HTTP requests per second to
                            send to the server. (Default: 8)
    --kind=<string>         Name of the Entity object kind to put in the
                            datastore. (Required)
    --num_threads=<int>     Number of threads to use for uploading entities
                            (Default 10)
                            may exceed this, but overall transfer rate is
                            restricted to this rate. (Default 250000)
    --rps_limit=<int>       The maximum number of records per second to
                            transfer to the server. (Default: 20)
    --url=<string>          URL endpoint to post to for importing data.
                            (Required)

The exit status will be 0 on success, non-zero on import failure.

Works with the remote_api mix-in library for google.appengine.ext.remote_api.
Please look there for documentation about how to setup the server side.

Example:

%(arg0)s --url=http://app.appspot.com/remote_api --kind=Model \
 --filename=data.csv --config_file=loader_config.py

"""



import csv
import getopt
import getpass
import logging
import new
import os
import Queue
import signal
import sys
import threading
import time
import traceback
import urllib2
import urlparse

from google.appengine.ext import db
from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.tools import appengine_rpc

try:
  import sqlite3
except ImportError:
  pass

UPLOADER_VERSION = '1'

DEFAULT_THREAD_COUNT = 10

DEFAULT_BATCH_SIZE = 10

DEFAULT_QUEUE_SIZE = DEFAULT_THREAD_COUNT * 10

_THREAD_SHOULD_EXIT = '_THREAD_SHOULD_EXIT'

STATE_READ = 0
STATE_SENDING = 1
STATE_SENT = 2
STATE_NOT_SENT = 3

MINIMUM_THROTTLE_SLEEP_DURATION = 0.001

DATA_CONSUMED_TO_HERE = 'DATA_CONSUMED_TO_HERE'

INITIAL_BACKOFF = 1.0

BACKOFF_FACTOR = 2.0


DEFAULT_BANDWIDTH_LIMIT = 250000

DEFAULT_RPS_LIMIT = 20

DEFAULT_REQUEST_LIMIT = 8

BANDWIDTH_UP = 'http-bandwidth-up'
BANDWIDTH_DOWN = 'http-bandwidth-down'
REQUESTS = 'http-requests'
HTTPS_BANDWIDTH_UP = 'https-bandwidth-up'
HTTPS_BANDWIDTH_DOWN = 'https-bandwidth-down'
HTTPS_REQUESTS = 'https-requests'
RECORDS = 'records'


def StateMessage(state):
  """Converts a numeric state identifier to a status message."""
  return ({
      STATE_READ: 'Batch read from file.',
      STATE_SENDING: 'Sending batch to server.',
      STATE_SENT: 'Batch successfully sent.',
      STATE_NOT_SENT: 'Error while sending batch.'
  }[state])


class Error(Exception):
  """Base-class for exceptions in this module."""


class FatalServerError(Error):
  """An unrecoverable error occurred while trying to post data to the server."""


class ResumeError(Error):
  """Error while trying to resume a partial upload."""


class ConfigurationError(Error):
  """Error in configuration options."""


class AuthenticationError(Error):
  """Error while trying to authenticate with the server."""


def GetCSVGeneratorFactory(csv_filename, batch_size,
                           openfile=open, create_csv_reader=csv.reader):
  """Return a factory that creates a CSV-based WorkItem generator.

  Args:
    csv_filename: File on disk containing CSV data.
    batch_size: Maximum number of CSV rows to stash into a WorkItem.
    openfile: Used for dependency injection.
    create_csv_reader: Used for dependency injection.

  Returns: A callable (accepting the Progress Queue and Progress
    Generators as input) which creates the WorkItem generator.
  """

  def CreateGenerator(progress_queue, progress_generator):
    """Initialize a CSV generator linked to a progress generator and queue.

    Args:
      progress_queue: A ProgressQueue instance to send progress information.
      progress_generator: A generator of progress information or None.

    Returns:
      A CSVGenerator instance.
    """
    return CSVGenerator(progress_queue,
                        progress_generator,
                        csv_filename,
                        batch_size,
                        openfile,
                        create_csv_reader)
  return CreateGenerator


class CSVGenerator(object):
  """Reads a CSV file and generates WorkItems containing batches of records."""

  def __init__(self,
               progress_queue,
               progress_generator,
               csv_filename,
               batch_size,
               openfile,
               create_csv_reader):
    """Initializes a CSV generator.

    Args:
      progress_queue: A queue used for tracking progress information.
      progress_generator: A generator of prior progress information, or None
        if there is no prior status.
      csv_filename: File on disk containing CSV data.
      batch_size: Maximum number of CSV rows to stash into a WorkItem.
      openfile: Used for dependency injection of 'open'.
      create_csv_reader: Used for dependency injection of 'csv.reader'.
    """
    self.progress_queue = progress_queue
    self.progress_generator = progress_generator
    self.csv_filename = csv_filename
    self.batch_size = batch_size
    self.openfile = openfile
    self.create_csv_reader = create_csv_reader
    self.line_number = 1
    self.column_count = None
    self.read_rows = []
    self.reader = None
    self.row_count = 0
    self.sent_count = 0

  def _AdvanceTo(self, line):
    """Advance the reader to the given line.

    Args:
      line: A line number to advance to.
    """
    while self.line_number < line:
      self.reader.next()
      self.line_number += 1
      self.row_count += 1
      self.sent_count += 1

  def _ReadRows(self, key_start, key_end):
    """Attempts to read and encode rows [key_start, key_end].

    The encoded rows are stored in self.read_rows.

    Args:
      key_start: The starting line number.
      key_end: The ending line number.

    Raises:
      StopIteration: if the reader runs out of rows
      ResumeError: if there are an inconsistent number of columns.
    """
    assert self.line_number == key_start
    self.read_rows = []
    while self.line_number <= key_end:
      row = self.reader.next()
      self.row_count += 1
      if self.column_count is None:
        self.column_count = len(row)
      else:
        if self.column_count != len(row):
          raise ResumeError('Column count mismatch, %d: %s' %
                            (self.column_count, str(row)))
      self.read_rows.append((self.line_number, row))
      self.line_number += 1

  def _MakeItem(self, key_start, key_end, rows, progress_key=None):
    """Makes a WorkItem containing the given rows, with the given keys.

    Args:
      key_start: The start key for the WorkItem.
      key_end: The end key for the WorkItem.
      rows: A list of the rows for the WorkItem.
      progress_key: The progress key for the WorkItem

    Returns:
      A WorkItem instance for the given batch.
    """
    assert rows

    item = WorkItem(self.progress_queue, rows,
                    key_start, key_end,
                    progress_key=progress_key)

    return item

  def Batches(self):
    """Reads the CSV data file and generates WorkItems.

    Yields:
      Instances of class WorkItem

    Raises:
      ResumeError: If the progress database and data file indicate a different
        number of rows.
    """
    csv_file = self.openfile(self.csv_filename, 'r')
    csv_content = csv_file.read()
    if csv_content:
      has_headers = csv.Sniffer().has_header(csv_content)
    else:
      has_headers = False
    csv_file.seek(0)
    self.reader = self.create_csv_reader(csv_file, skipinitialspace=True)
    if has_headers:
      logging.info('The CSV file appears to have a header line, skipping.')
      self.reader.next()

    exhausted = False

    self.line_number = 1
    self.column_count = None

    logging.info('Starting import; maximum %d entities per post',
                 self.batch_size)

    state = None
    if self.progress_generator is not None:
      for progress_key, state, key_start, key_end in self.progress_generator:
        if key_start:
          try:
            self._AdvanceTo(key_start)
            self._ReadRows(key_start, key_end)
            yield self._MakeItem(key_start,
                                 key_end,
                                 self.read_rows,
                                 progress_key=progress_key)
          except StopIteration:
            logging.error('Mismatch between data file and progress database')
            raise ResumeError(
                'Mismatch between data file and progress database')
        elif state == DATA_CONSUMED_TO_HERE:
          try:
            self._AdvanceTo(key_end + 1)
          except StopIteration:
            state = None

    if self.progress_generator is None or state == DATA_CONSUMED_TO_HERE:
      while not exhausted:
        key_start = self.line_number
        key_end = self.line_number + self.batch_size - 1
        try:
          self._ReadRows(key_start, key_end)
        except StopIteration:
          exhausted = True
          key_end = self.line_number - 1
        if key_start <= key_end:
          yield self._MakeItem(key_start, key_end, self.read_rows)


class ReQueue(object):
  """A special thread-safe queue.

  A ReQueue allows unfinished work items to be returned with a call to
  reput().  When an item is reput, task_done() should *not* be called
  in addition, getting an item that has been reput does not increase
  the number of outstanding tasks.

  This class shares an interface with Queue.Queue and provides the
  additional Reput method.
  """

  def __init__(self,
               queue_capacity,
               requeue_capacity=None,
               queue_factory=Queue.Queue,
               get_time=time.time):
    """Initialize a ReQueue instance.

    Args:
      queue_capacity: The number of items that can be put in the ReQueue.
      requeue_capacity: The numer of items that can be reput in the ReQueue.
      queue_factory: Used for dependency injection.
      get_time: Used for dependency injection.
    """
    if requeue_capacity is None:
      requeue_capacity = queue_capacity

    self.get_time = get_time
    self.queue = queue_factory(queue_capacity)
    self.requeue = queue_factory(requeue_capacity)
    self.lock = threading.Lock()
    self.put_cond = threading.Condition(self.lock)
    self.get_cond = threading.Condition(self.lock)

  def _DoWithTimeout(self,
                     action,
                     exc,
                     wait_cond,
                     done_cond,
                     lock,
                     timeout=None,
                     block=True):
    """Performs the given action with a timeout.

    The action must be non-blocking, and raise an instance of exc on a
    recoverable failure.  If the action fails with an instance of exc,
    we wait on wait_cond before trying again.  Failure after the
    timeout is reached is propagated as an exception.  Success is
    signalled by notifying on done_cond and returning the result of
    the action.  If action raises any exception besides an instance of
    exc, it is immediately propagated.

    Args:
      action: A callable that performs a non-blocking action.
      exc: An exception type that is thrown by the action to indicate
        a recoverable error.
      wait_cond: A condition variable which should be waited on when
        action throws exc.
      done_cond: A condition variable to signal if the action returns.
      lock: The lock used by wait_cond and done_cond.
      timeout: A non-negative float indicating the maximum time to wait.
      block: Whether to block if the action cannot complete immediately.

    Returns:
      The result of the action, if it is successful.

    Raises:
      ValueError: If the timeout argument is negative.
    """
    if timeout is not None and timeout < 0.0:
      raise ValueError('\'timeout\' must not be a negative  number')
    if not block:
      timeout = 0.0
    result = None
    success = False
    start_time = self.get_time()
    lock.acquire()
    try:
      while not success:
        try:
          result = action()
          success = True
        except Exception, e:
          if not isinstance(e, exc):
            raise e
          if timeout is not None:
            elapsed_time = self.get_time() - start_time
            timeout -= elapsed_time
            if timeout <= 0.0:
              raise e
          wait_cond.wait(timeout)
    finally:
      if success:
        done_cond.notify()
      lock.release()
    return result

  def put(self, item, block=True, timeout=None):
    """Put an item into the requeue.

    Args:
      item: An item to add to the requeue.
      block: Whether to block if the requeue is full.
      timeout: Maximum on how long to wait until the queue is non-full.

    Raises:
      Queue.Full if the queue is full and the timeout expires.
    """
    def PutAction():
      self.queue.put(item, block=False)
    self._DoWithTimeout(PutAction,
                        Queue.Full,
                        self.get_cond,
                        self.put_cond,
                        self.lock,
                        timeout=timeout,
                        block=block)

  def reput(self, item, block=True, timeout=None):
    """Re-put an item back into the requeue.

    Re-putting an item does not increase the number of outstanding
    tasks, so the reput item should be uniquely associated with an
    item that was previously removed from the requeue and for which
    task_done has not been called.

    Args:
      item: An item to add to the requeue.
      block: Whether to block if the requeue is full.
      timeout: Maximum on how long to wait until the queue is non-full.

    Raises:
      Queue.Full is the queue is full and the timeout expires.
    """
    def ReputAction():
      self.requeue.put(item, block=False)
    self._DoWithTimeout(ReputAction,
                        Queue.Full,
                        self.get_cond,
                        self.put_cond,
                        self.lock,
                        timeout=timeout,
                        block=block)

  def get(self, block=True, timeout=None):
    """Get an item from the requeue.

    Args:
      block: Whether to block if the requeue is empty.
      timeout: Maximum on how long to wait until the requeue is non-empty.

    Returns:
      An item from the requeue.

    Raises:
      Queue.Empty if the queue is empty and the timeout expires.
    """
    def GetAction():
      try:
        result = self.requeue.get(block=False)
        self.requeue.task_done()
      except Queue.Empty:
        result = self.queue.get(block=False)
      return result
    return self._DoWithTimeout(GetAction,
                               Queue.Empty,
                               self.put_cond,
                               self.get_cond,
                               self.lock,
                               timeout=timeout,
                               block=block)

  def join(self):
    """Blocks until all of the items in the requeue have been processed."""
    self.queue.join()

  def task_done(self):
    """Indicate that a previously enqueued item has been fully processed."""
    self.queue.task_done()

  def empty(self):
    """Returns true if the requeue is empty."""
    return self.queue.empty() and self.requeue.empty()

  def get_nowait(self):
    """Try to get an item from the queue without blocking."""
    return self.get(block=False)


class ThrottleHandler(urllib2.BaseHandler):
  """A urllib2 handler for http and https requests that adds to a throttle."""

  def __init__(self, throttle):
    """Initialize a ThrottleHandler.

    Args:
      throttle: A Throttle instance to call for bandwidth and http/https request
        throttling.
    """
    self.throttle = throttle

  def AddRequest(self, throttle_name, req):
    """Add to bandwidth throttle for given request.

    Args:
      throttle_name: The name of the bandwidth throttle to add to.
      req: The request whose size will be added to the throttle.
    """
    size = 0
    for key, value in req.headers.iteritems():
      size += len('%s: %s\n' % (key, value))
    for key, value in req.unredirected_hdrs.iteritems():
      size += len('%s: %s\n' % (key, value))
    (unused_scheme,
     unused_host_port, url_path,
     unused_query, unused_fragment) = urlparse.urlsplit(req.get_full_url())
    size += len('%s %s HTTP/1.1\n' % (req.get_method(), url_path))
    data = req.get_data()
    if data:
      size += len(data)
    self.throttle.AddTransfer(throttle_name, size)

  def AddResponse(self, throttle_name, res):
    """Add to bandwidth throttle for given response.

    Args:
      throttle_name: The name of the bandwidth throttle to add to.
      res: The response whose size will be added to the throttle.
    """
    content = res.read()
    def ReturnContent():
      return content
    res.read = ReturnContent
    size = len(content)
    headers = res.info()
    for key, value in headers.items():
      size += len('%s: %s\n' % (key, value))
    self.throttle.AddTransfer(throttle_name, size)

  def http_request(self, req):
    """Process an HTTP request.

    If the throttle is over quota, sleep first.  Then add request size to
    throttle before returning it to be sent.

    Args:
      req: A urllib2.Request object.

    Returns:
      The request passed in.
    """
    self.throttle.Sleep()
    self.AddRequest(BANDWIDTH_UP, req)
    return req

  def https_request(self, req):
    """Process an HTTPS request.

    If the throttle is over quota, sleep first.  Then add request size to
    throttle before returning it to be sent.

    Args:
      req: A urllib2.Request object.

    Returns:
      The request passed in.
    """
    self.throttle.Sleep()
    self.AddRequest(HTTPS_BANDWIDTH_UP, req)
    return req

  def http_response(self, unused_req, res):
    """Process an HTTP response.

    The size of the response is added to the bandwidth throttle and the request
    throttle is incremented by one.

    Args:
      unused_req: The urllib2 request for this response.
      res: A urllib2 response object.

    Returns:
      The response passed in.
    """
    self.AddResponse(BANDWIDTH_DOWN, res)
    self.throttle.AddTransfer(REQUESTS, 1)
    return res

  def https_response(self, unused_req, res):
    """Process an HTTPS response.

    The size of the response is added to the bandwidth throttle and the request
    throttle is incremented by one.

    Args:
      unused_req: The urllib2 request for this response.
      res: A urllib2 response object.

    Returns:
      The response passed in.
    """
    self.AddResponse(HTTPS_BANDWIDTH_DOWN, res)
    self.throttle.AddTransfer(HTTPS_REQUESTS, 1)
    return res


class ThrottledHttpRpcServer(appengine_rpc.HttpRpcServer):
  """Provides a simplified RPC-style interface for HTTP requests.

  This RPC server uses a Throttle to prevent exceeding quotas.
  """

  def __init__(self, throttle, request_manager, *args, **kwargs):
    """Initialize a ThrottledHttpRpcServer.

    Also sets request_manager.rpc_server to the ThrottledHttpRpcServer instance.

    Args:
      throttle: A Throttles instance.
      request_manager: A RequestManager instance.
      args: Positional arguments to pass through to
        appengine_rpc.HttpRpcServer.__init__
      kwargs: Keyword arguments to pass through to
        appengine_rpc.HttpRpcServer.__init__
    """
    self.throttle = throttle
    appengine_rpc.HttpRpcServer.__init__(self, *args, **kwargs)
    request_manager.rpc_server = self

  def _GetOpener(self):
    """Returns an OpenerDirector that supports cookies and ignores redirects.

    Returns:
      A urllib2.OpenerDirector object.
    """
    opener = appengine_rpc.HttpRpcServer._GetOpener(self)
    opener.add_handler(ThrottleHandler(self.throttle))

    return opener


def ThrottledHttpRpcServerFactory(throttle, request_manager):
  """Create a factory to produce ThrottledHttpRpcServer for a given throttle.

  Args:
    throttle: A Throttle instance to use for the ThrottledHttpRpcServer.
    request_manager: A RequestManager instance.

  Returns:
    A factory to produce a ThrottledHttpRpcServer.
  """
  def MakeRpcServer(*args, **kwargs):
    kwargs['account_type'] = 'HOSTED_OR_GOOGLE'
    kwargs['save_cookies'] = True
    return ThrottledHttpRpcServer(throttle, request_manager, *args, **kwargs)
  return MakeRpcServer


class RequestManager(object):
  """A class which wraps a connection to the server."""

  source = 'google-bulkloader-%s' % UPLOADER_VERSION
  user_agent = source

  def __init__(self,
               app_id,
               host_port,
               url_path,
               kind,
               throttle):
    """Initialize a RequestManager object.

    Args:
      app_id: String containing the application id for requests.
      host_port: String containing the "host:port" pair; the port is optional.
      url_path: partial URL (path) to post entity data to.
      kind: Kind of the Entity records being posted.
      throttle: A Throttle instance.
    """
    self.app_id = app_id
    self.host_port = host_port
    self.host = host_port.split(':')[0]
    if url_path and url_path[0] != '/':
      url_path = '/' + url_path
    self.url_path = url_path
    self.kind = kind
    self.throttle = throttle
    self.credentials = None
    throttled_rpc_server_factory = ThrottledHttpRpcServerFactory(
        self.throttle, self)
    logging.debug('Configuring remote_api. app_id = %s, url_path = %s, '
                  'servername = %s' % (app_id, url_path, host_port))
    remote_api_stub.ConfigureRemoteDatastore(
        app_id,
        url_path,
        self.AuthFunction,
        servername=host_port,
        rpc_server_factory=throttled_rpc_server_factory)
    self.authenticated = False

  def Authenticate(self):
    """Invoke authentication if necessary."""
    self.rpc_server.Send(self.url_path, payload=None)
    self.authenticated = True

  def AuthFunction(self,
                   raw_input_fn=raw_input,
                   password_input_fn=getpass.getpass):
    """Prompts the user for a username and password.

    Caches the results the first time it is called and returns the
    same result every subsequent time.

    Args:
      raw_input_fn: Used for dependency injection.
      password_input_fn: Used for dependency injection.

    Returns:
      A pair of the username and password.
    """
    if self.credentials is not None:
      return self.credentials
    print 'Please enter login credentials for %s (%s)' % (
        self.host, self.app_id)
    email = raw_input_fn('Email: ')
    if email:
      password_prompt = 'Password for %s: ' % email
      password = password_input_fn(password_prompt)
    else:
      password = None
    self.credentials = (email, password)
    return self.credentials

  def _GetHeaders(self):
    """Constructs a dictionary of extra headers to send with a request."""
    headers = {
        'GAE-Uploader-Version': UPLOADER_VERSION,
        'GAE-Uploader-Kind': self.kind
        }
    return headers

  def EncodeContent(self, rows):
    """Encodes row data to the wire format.

    Args:
      rows: A list of pairs of a line number and a list of column values.

    Returns:
      A list of db.Model instances.
    """
    try:
      loader = Loader.RegisteredLoaders()[self.kind]
    except KeyError:
      logging.error('No Loader defined for kind %s.' % self.kind)
      raise ConfigurationError('No Loader defined for kind %s.' % self.kind)
    entities = []
    for line_number, values in rows:
      key = loader.GenerateKey(line_number, values)
      entity = loader.CreateEntity(values, key_name=key)
      entities.extend(entity)

    return entities

  def PostEntities(self, item):
    """Posts Entity records to a remote endpoint over HTTP.

    Args:
      item: A workitem containing the entities to post.

    Returns:
      A pair of the estimated size of the request in bytes and the response
        from the server as a str.
    """
    entities = item.content
    db.put(entities)


class WorkItem(object):
  """Holds a unit of uploading work.

  A WorkItem represents a number of entities that need to be uploaded to
  Google App Engine. These entities are encoded in the "content" field of
  the WorkItem, and will be POST'd as-is to the server.

  The entities are identified by a range of numeric keys, inclusively. In
  the case of a resumption of an upload, or a replay to correct errors,
  these keys must be able to identify the same set of entities.

  Note that keys specify a range. The entities do not have to sequentially
  fill the entire range, they must simply bound a range of valid keys.
  """

  def __init__(self, progress_queue, rows, key_start, key_end,
               progress_key=None):
    """Initialize the WorkItem instance.

    Args:
      progress_queue: A queue used for tracking progress information.
      rows: A list of pairs of a line number and a list of column values
      key_start: The (numeric) starting key, inclusive.
      key_end: The (numeric) ending key, inclusive.
      progress_key: If this WorkItem represents state from a prior run,
        then this will be the key within the progress database.
    """
    self.state = STATE_READ

    self.progress_queue = progress_queue

    assert isinstance(key_start, (int, long))
    assert isinstance(key_end, (int, long))
    assert key_start <= key_end

    self.key_start = key_start
    self.key_end = key_end
    self.progress_key = progress_key

    self.progress_event = threading.Event()

    self.rows = rows
    self.content = None
    self.count = len(rows)

  def MarkAsRead(self):
    """Mark this WorkItem as read/consumed from the data source."""

    assert self.state == STATE_READ

    self._StateTransition(STATE_READ, blocking=True)

    assert self.progress_key is not None

  def MarkAsSending(self):
    """Mark this WorkItem as in-process on being uploaded to the server."""

    assert self.state == STATE_READ or self.state == STATE_NOT_SENT
    assert self.progress_key is not None

    self._StateTransition(STATE_SENDING, blocking=True)

  def MarkAsSent(self):
    """Mark this WorkItem as sucessfully-sent to the server."""

    assert self.state == STATE_SENDING
    assert self.progress_key is not None

    self._StateTransition(STATE_SENT, blocking=False)

  def MarkAsError(self):
    """Mark this WorkItem as required manual error recovery."""

    assert self.state == STATE_SENDING
    assert self.progress_key is not None

    self._StateTransition(STATE_NOT_SENT, blocking=True)

  def _StateTransition(self, new_state, blocking=False):
    """Transition the work item to a new state, storing progress information.

    Args:
      new_state: The state to transition to.
      blocking: Whether to block for the progress thread to acknowledge the
        transition.
    """
    logging.debug('[%s-%s] %s' %
                  (self.key_start, self.key_end, StateMessage(self.state)))
    assert not self.progress_event.isSet()

    self.state = new_state

    self.progress_queue.put(self)

    if blocking:
      self.progress_event.wait()

      self.progress_event.clear()



def InterruptibleSleep(sleep_time):
  """Puts thread to sleep, checking this threads exit_flag twice a second.

  Args:
    sleep_time: Time to sleep.
  """
  slept = 0.0
  epsilon = .0001
  thread = threading.currentThread()
  while slept < sleep_time - epsilon:
    remaining = sleep_time - slept
    this_sleep_time = min(remaining, 0.5)
    time.sleep(this_sleep_time)
    slept += this_sleep_time
    if thread.exit_flag:
      return


class ThreadGate(object):
  """Manage the number of active worker threads.

  The ThreadGate limits the number of threads that are simultaneously
  uploading batches of records in order to implement adaptive rate
  control.  The number of simultaneous upload threads that it takes to
  start causing timeout varies widely over the course of the day, so
  adaptive rate control allows the uploader to do many uploads while
  reducing the error rate and thus increasing the throughput.

  Initially the ThreadGate allows only one uploader thread to be active.
  For each successful upload, another thread is activated and for each
  failed upload, the number of active threads is reduced by one.
  """

  def __init__(self, enabled, sleep=InterruptibleSleep):
    self.enabled = enabled
    self.enabled_count = 1
    self.lock = threading.Lock()
    self.thread_semaphore = threading.Semaphore(self.enabled_count)
    self._threads = []
    self.backoff_time = 0
    self.sleep = sleep

  def Register(self, thread):
    """Register a thread with the thread gate."""
    self._threads.append(thread)

  def Threads(self):
    """Yields the registered threads."""
    for thread in self._threads:
      yield thread

  def EnableThread(self):
    """Enable one more worker thread."""
    self.lock.acquire()
    try:
      self.enabled_count += 1
    finally:
      self.lock.release()
    self.thread_semaphore.release()

  def EnableAllThreads(self):
    """Enable all worker threads."""
    for unused_idx in range(len(self._threads) - self.enabled_count):
      self.EnableThread()

  def StartWork(self):
    """Starts a critical section in which the number of workers is limited.

    If thread throttling is enabled then this method starts a critical
    section which allows self.enabled_count simultaneously operating
    threads. The critical section is ended by calling self.FinishWork().
    """
    if self.enabled:
      self.thread_semaphore.acquire()
      if self.backoff_time > 0.0:
        if not threading.currentThread().exit_flag:
          logging.info('Backing off: %.1f seconds',
                       self.backoff_time)
        self.sleep(self.backoff_time)

  def FinishWork(self):
    """Ends a critical section started with self.StartWork()."""
    if self.enabled:
      self.thread_semaphore.release()

  def IncreaseWorkers(self):
    """Informs the throttler that an item was successfully sent.

    If thread throttling is enabled, this method will cause an
    additional thread to run in the critical section.
    """
    if self.enabled:
      if self.backoff_time > 0.0:
        logging.info('Resetting backoff to 0.0')
        self.backoff_time = 0.0
      do_enable = False
      self.lock.acquire()
      try:
        if self.enabled and len(self._threads) > self.enabled_count:
          do_enable = True
          self.enabled_count += 1
      finally:
        self.lock.release()
      if do_enable:
        self.thread_semaphore.release()

  def DecreaseWorkers(self):
    """Informs the thread_gate that an item failed to send.

    If thread throttling is enabled, this method will cause the
    throttler to allow one fewer thread in the critical section. If
    there is only one thread remaining, failures will result in
    exponential backoff until there is a success.
    """
    if self.enabled:
      do_disable = False
      self.lock.acquire()
      try:
        if self.enabled:
          if self.enabled_count > 1:
            do_disable = True
            self.enabled_count -= 1
          else:
            if self.backoff_time == 0.0:
              self.backoff_time = INITIAL_BACKOFF
            else:
              self.backoff_time *= BACKOFF_FACTOR
      finally:
        self.lock.release()
      if do_disable:
        self.thread_semaphore.acquire()


class Throttle(object):
  """A base class for upload rate throttling.

  Transferring large number of records, too quickly, to an application
  could trigger quota limits and cause the transfer process to halt.
  In order to stay within the application's quota, we throttle the
  data transfer to a specified limit (across all transfer threads).
  This limit defaults to about half of the Google App Engine default
  for an application, but can be manually adjusted faster/slower as
  appropriate.

  This class tracks a moving average of some aspect of the transfer
  rate (bandwidth, records per second, http connections per
  second). It keeps two windows of counts of bytes transferred, on a
  per-thread basis. One block is the "current" block, and the other is
  the "prior" block. It will rotate the counts from current to prior
  when ROTATE_PERIOD has passed.  Thus, the current block will
  represent from 0 seconds to ROTATE_PERIOD seconds of activity
  (determined by: time.time() - self.last_rotate).  The prior block
  will always represent a full ROTATE_PERIOD.

  Sleeping is performed just before a transfer of another block, and is
  based on the counts transferred *before* the next transfer. It really
  does not matter how much will be transferred, but only that for all the
  data transferred SO FAR that we have interspersed enough pauses to
  ensure the aggregate transfer rate is within the specified limit.

  These counts are maintained on a per-thread basis, so we do not require
  any interlocks around incrementing the counts. There IS an interlock on
  the rotation of the counts because we do not want multiple threads to
  multiply-rotate the counts.

  There are various race conditions in the computation and collection
  of these counts. We do not require precise values, but simply to
  keep the overall transfer within the bandwidth limits. If a given
  pause is a little short, or a little long, then the aggregate delays
  will be correct.
  """

  ROTATE_PERIOD = 600

  def __init__(self,
               get_time=time.time,
               thread_sleep=InterruptibleSleep,
               layout=None):
    self.get_time = get_time
    self.thread_sleep = thread_sleep

    self.start_time = get_time()
    self.transferred = {}
    self.prior_block = {}
    self.totals = {}
    self.throttles = {}

    self.last_rotate = {}
    self.rotate_mutex = {}
    if layout:
      self.AddThrottles(layout)

  def AddThrottle(self, name, limit):
    self.throttles[name] = limit
    self.transferred[name] = {}
    self.prior_block[name] = {}
    self.totals[name] = {}
    self.last_rotate[name] = self.get_time()
    self.rotate_mutex[name] = threading.Lock()

  def AddThrottles(self, layout):
    for key, value in layout.iteritems():
      self.AddThrottle(key, value)

  def Register(self, thread):
    """Register this thread with the throttler."""
    thread_name = thread.getName()
    for throttle_name in self.throttles.iterkeys():
      self.transferred[throttle_name][thread_name] = 0
      self.prior_block[throttle_name][thread_name] = 0
      self.totals[throttle_name][thread_name] = 0

  def VerifyName(self, throttle_name):
    if throttle_name not in self.throttles:
      raise AssertionError('%s is not a registered throttle' % throttle_name)

  def AddTransfer(self, throttle_name, token_count):
    """Add a count to the amount this thread has transferred.

    Each time a thread transfers some data, it should call this method to
    note the amount sent. The counts may be rotated if sufficient time
    has passed since the last rotation.

    Note: this method should only be called by the BulkLoaderThread
    instances. The token count is allocated towards the
    "current thread".

    Args:
      throttle_name: The name of the throttle to add to.
      token_count: The number to add to the throttle counter.
    """
    self.VerifyName(throttle_name)
    transferred = self.transferred[throttle_name]
    transferred[threading.currentThread().getName()] += token_count

    if self.last_rotate[throttle_name] + self.ROTATE_PERIOD < self.get_time():
      self._RotateCounts(throttle_name)

  def Sleep(self, throttle_name=None):
    """Possibly sleep in order to limit the transfer rate.

    Note that we sleep based on *prior* transfers rather than what we
    may be about to transfer. The next transfer could put us under/over
    and that will be rectified *after* that transfer. Net result is that
    the average transfer rate will remain within bounds. Spiky behavior
    or uneven rates among the threads could possibly bring the transfer
    rate above the requested limit for short durations.

    Args:
      throttle_name: The name of the throttle to sleep on.  If None or
        omitted, then sleep on all throttles.
    """
    if throttle_name is None:
      for throttle_name in self.throttles:
        self.Sleep(throttle_name=throttle_name)
      return

    self.VerifyName(throttle_name)

    thread = threading.currentThread()

    while True:
      duration = self.get_time() - self.last_rotate[throttle_name]

      total = 0
      for count in self.prior_block[throttle_name].values():
        total += count

      if total:
        duration += self.ROTATE_PERIOD

      for count in self.transferred[throttle_name].values():
        total += count

      sleep_time = (float(total) / self.throttles[throttle_name]) - duration

      if sleep_time < MINIMUM_THROTTLE_SLEEP_DURATION:
        break

      logging.debug('[%s] Throttling on %s. Sleeping for %.1f ms '
                    '(duration=%.1f ms, total=%d)',
                    thread.getName(), throttle_name,
                    sleep_time * 1000, duration * 1000, total)
      self.thread_sleep(sleep_time)
      if thread.exit_flag:
        break
      self._RotateCounts(throttle_name)

  def _RotateCounts(self, throttle_name):
    """Rotate the transfer counters.

    If sufficient time has passed, then rotate the counters from active to
    the prior-block of counts.

    This rotation is interlocked to ensure that multiple threads do not
    over-rotate the counts.

    Args:
      throttle_name: The name of the throttle to rotate.
    """
    self.VerifyName(throttle_name)
    self.rotate_mutex[throttle_name].acquire()
    try:
      next_rotate_time = self.last_rotate[throttle_name] + self.ROTATE_PERIOD
      if next_rotate_time >= self.get_time():
        return

      for name, count in self.transferred[throttle_name].items():


        self.prior_block[throttle_name][name] = count
        self.transferred[throttle_name][name] = 0

        self.totals[throttle_name][name] += count

      self.last_rotate[throttle_name] = self.get_time()

    finally:
      self.rotate_mutex[throttle_name].release()

  def TotalTransferred(self, throttle_name):
    """Return the total transferred, and over what period.

    Args:
      throttle_name: The name of the throttle to total.

    Returns:
      A tuple of the total count and running time for the given throttle name.
    """
    total = 0
    for count in self.totals[throttle_name].values():
      total += count
    for count in self.transferred[throttle_name].values():
      total += count
    return total, self.get_time() - self.start_time


class _ThreadBase(threading.Thread):
  """Provide some basic features for the threads used in the uploader.

  This abstract base class is used to provide some common features:

  * Flag to ask thread to exit as soon as possible.
  * Record exit/error status for the primary thread to pick up.
  * Capture exceptions and record them for pickup.
  * Some basic logging of thread start/stop.
  * All threads are "daemon" threads.
  * Friendly names for presenting to users.

  Concrete sub-classes must implement PerformWork().

  Either self.NAME should be set or GetFriendlyName() be overridden to
  return a human-friendly name for this thread.

  The run() method starts the thread and prints start/exit messages.

  self.exit_flag is intended to signal that this thread should exit
  when it gets the chance.  PerformWork() should check self.exit_flag
  whenever it has the opportunity to exit gracefully.
  """

  def __init__(self):
    threading.Thread.__init__(self)

    self.setDaemon(True)

    self.exit_flag = False
    self.error = None

  def run(self):
    """Perform the work of the thread."""
    logging.info('[%s] %s: started', self.getName(), self.__class__.__name__)

    try:
      self.PerformWork()
    except:
      self.error = sys.exc_info()[1]
      logging.exception('[%s] %s:', self.getName(), self.__class__.__name__)

    logging.info('[%s] %s: exiting', self.getName(), self.__class__.__name__)

  def PerformWork(self):
    """Perform the thread-specific work."""
    raise NotImplementedError()

  def CheckError(self):
    """If an error is present, then log it."""
    if self.error:
      logging.error('Error in %s: %s', self.GetFriendlyName(), self.error)

  def GetFriendlyName(self):
    """Returns a human-friendly description of the thread."""
    if hasattr(self, 'NAME'):
      return self.NAME
    return 'unknown thread'


class BulkLoaderThread(_ThreadBase):
  """A thread which transmits entities to the server application.

  This thread will read WorkItem instances from the work_queue and upload
  the entities to the server application. Progress information will be
  pushed into the progress_queue as the work is being performed.

  If a BulkLoaderThread encounters a transient error, the entities will be
  resent, if a fatal error is encoutered the BulkLoaderThread exits.
  """

  def __init__(self,
               work_queue,
               throttle,
               thread_gate,
               request_manager):
    """Initialize the BulkLoaderThread instance.

    Args:
      work_queue: A queue containing WorkItems for processing.
      throttle: A Throttles to control upload bandwidth.
      thread_gate: A ThreadGate to control number of simultaneous uploads.
      request_manager: A RequestManager instance.
    """
    _ThreadBase.__init__(self)

    self.work_queue = work_queue
    self.throttle = throttle
    self.thread_gate = thread_gate

    self.request_manager = request_manager

  def PerformWork(self):
    """Perform the work of a BulkLoaderThread."""
    while not self.exit_flag:
      success = False
      self.thread_gate.StartWork()
      try:
        try:
          item = self.work_queue.get(block=True, timeout=1.0)
        except Queue.Empty:
          continue
        if item == _THREAD_SHOULD_EXIT:
          break

        logging.debug('[%s] Got work item [%d-%d]',
                      self.getName(), item.key_start, item.key_end)

        try:

          item.MarkAsSending()
          try:
            if item.content is None:
              item.content = self.request_manager.EncodeContent(item.rows)
            try:
              self.request_manager.PostEntities(item)
              success = True
              logging.debug(
                  '[%d-%d] Sent %d entities',
                  item.key_start, item.key_end, item.count)
              self.throttle.AddTransfer(RECORDS, item.count)
            except (db.InternalError, db.NotSavedError, db.Timeout), e:
              logging.debug('Caught non-fatal error: %s', e)
            except urllib2.HTTPError, e:
              if e.code == 403 or (e.code >= 500 and e.code < 600):
                logging.debug('Caught HTTP error %d', e.code)
                logging.debug('%s', e.read())
              else:
                raise e

          except:
            self.error = sys.exc_info()[1]
            logging.exception('[%s] %s: caught exception %s', self.getName(),
                              self.__class__.__name__, str(sys.exc_info()))
            raise

        finally:
          if success:
            item.MarkAsSent()
            self.thread_gate.IncreaseWorkers()
            self.work_queue.task_done()
          else:
            item.MarkAsError()
            self.thread_gate.DecreaseWorkers()
            try:
              self.work_queue.reput(item, block=False)
            except Queue.Full:
              logging.error('[%s] Failed to reput work item.', self.getName())
              raise Error('Failed to reput work item')
          logging.info('[%d-%d] %s',
                       item.key_start, item.key_end, StateMessage(item.state))

      finally:
        self.thread_gate.FinishWork()


  def GetFriendlyName(self):
    """Returns a human-friendly name for this thread."""
    return 'worker [%s]' % self.getName()


class DataSourceThread(_ThreadBase):
  """A thread which reads WorkItems and pushes them into queue.

  This thread will read/consume WorkItems from a generator (produced by
  the generator factory). These WorkItems will then be pushed into the
  work_queue. Note that reading will block if/when the work_queue becomes
  full. Information on content consumed from the generator will be pushed
  into the progress_queue.
  """

  NAME = 'data source thread'

  def __init__(self,
               work_queue,
               progress_queue,
               workitem_generator_factory,
               progress_generator_factory):
    """Initialize the DataSourceThread instance.

    Args:
      work_queue: A queue containing WorkItems for processing.
      progress_queue: A queue used for tracking progress information.
      workitem_generator_factory: A factory that creates a WorkItem generator
      progress_generator_factory: A factory that creates a generator which
        produces prior progress status, or None if there is no prior status
        to use.
    """
    _ThreadBase.__init__(self)

    self.work_queue = work_queue
    self.progress_queue = progress_queue
    self.workitem_generator_factory = workitem_generator_factory
    self.progress_generator_factory = progress_generator_factory
    self.entity_count = 0

  def PerformWork(self):
    """Performs the work of a DataSourceThread."""
    if self.progress_generator_factory:
      progress_gen = self.progress_generator_factory()
    else:
      progress_gen = None

    content_gen = self.workitem_generator_factory(self.progress_queue,
                                                  progress_gen)

    self.sent_count = 0
    self.read_count = 0
    self.read_all = False

    for item in content_gen.Batches():
      item.MarkAsRead()

      while not self.exit_flag:
        try:
          self.work_queue.put(item, block=True, timeout=1.0)
          self.entity_count += item.count
          break
        except Queue.Full:
          pass

      if self.exit_flag:
        break

    if not self.exit_flag:
      self.read_all = True
    self.read_count = content_gen.row_count
    self.sent_count = content_gen.sent_count



def _RunningInThread(thread):
  """Return True if we are running within the specified thread."""
  return threading.currentThread().getName() == thread.getName()


class ProgressDatabase(object):
  """Persistently record all progress information during an upload.

  This class wraps a very simple SQLite database which records each of
  the relevant details from the WorkItem instances. If the uploader is
  resumed, then data is replayed out of the database.
  """

  def __init__(self, db_filename, commit_periodicity=100):
    """Initialize the ProgressDatabase instance.

    Args:
      db_filename: The name of the SQLite database to use.
      commit_periodicity: How many operations to perform between commits.
    """
    self.db_filename = db_filename

    logging.info('Using progress database: %s', db_filename)
    self.primary_conn = sqlite3.connect(db_filename, isolation_level=None)
    self.primary_thread = threading.currentThread()

    self.progress_conn = None
    self.progress_thread = None

    self.operation_count = 0
    self.commit_periodicity = commit_periodicity

    self.prior_key_end = None

    try:
      self.primary_conn.execute(
          """create table progress (
          id integer primary key autoincrement,
          state integer not null,
          key_start integer not null,
          key_end integer not null
          )
          """)
    except sqlite3.OperationalError, e:
      if 'already exists' not in e.message:
        raise

    try:
      self.primary_conn.execute('create index i_state on progress (state)')
    except sqlite3.OperationalError, e:
      if 'already exists' not in e.message:
        raise

  def ThreadComplete(self):
    """Finalize any operations the progress thread has performed.

    The database aggregates lots of operations into a single commit, and
    this method is used to commit any pending operations as the thread
    is about to shut down.
    """
    if self.progress_conn:
      self._MaybeCommit(force_commit=True)

  def _MaybeCommit(self, force_commit=False):
    """Periodically commit changes into the SQLite database.

    Committing every operation is quite expensive, and slows down the
    operation of the script. Thus, we only commit after every N operations,
    as determined by the self.commit_periodicity value. Optionally, the
    caller can force a commit.

    Args:
      force_commit: Pass True in order for a commit to occur regardless
        of the current operation count.
    """
    self.operation_count += 1
    if force_commit or (self.operation_count % self.commit_periodicity) == 0:
      self.progress_conn.commit()

  def _OpenProgressConnection(self):
    """Possibly open a database connection for the progress tracker thread.

    If the connection is not open (for the calling thread, which is assumed
    to be the progress tracker thread), then open it. We also open a couple
    cursors for later use (and reuse).
    """
    if self.progress_conn:
      return

    assert not _RunningInThread(self.primary_thread)

    self.progress_thread = threading.currentThread()

    self.progress_conn = sqlite3.connect(self.db_filename)

    self.insert_cursor = self.progress_conn.cursor()
    self.update_cursor = self.progress_conn.cursor()

  def HasUnfinishedWork(self):
    """Returns True if the database has progress information.

    Note there are two basic cases for progress information:
    1) All saved records indicate a successful upload. In this case, we
       need to skip everything transmitted so far and then send the rest.
    2) Some records for incomplete transfer are present. These need to be
       sent again, and then we resume sending after all the successful
       data.

    Returns:
      True if the database has progress information, False otherwise.

    Raises:
      ResumeError: If there is an error reading the progress database.
    """
    assert _RunningInThread(self.primary_thread)

    cursor = self.primary_conn.cursor()
    cursor.execute('select count(*) from progress')
    row = cursor.fetchone()
    if row is None:
      raise ResumeError('Error reading progress information.')

    return row[0] != 0

  def StoreKeys(self, key_start, key_end):
    """Record a new progress record, returning a key for later updates.

    The specified progress information will be persisted into the database.
    A unique key will be returned that identifies this progress state. The
    key is later used to (quickly) update this record.

    For the progress resumption to proceed properly, calls to StoreKeys
    MUST specify monotonically increasing key ranges. This will result in
    a database whereby the ID, KEY_START, and KEY_END rows are all
    increasing (rather than having ranges out of order).

    NOTE: the above precondition is NOT tested by this method (since it
    would imply an additional table read or two on each invocation).

    Args:
      key_start: The starting key of the WorkItem (inclusive)
      key_end: The end key of the WorkItem (inclusive)

    Returns:
      A string to later be used as a unique key to update this state.
    """
    self._OpenProgressConnection()

    assert _RunningInThread(self.progress_thread)
    assert isinstance(key_start, int)
    assert isinstance(key_end, int)
    assert key_start <= key_end

    if self.prior_key_end is not None:
      assert key_start > self.prior_key_end
    self.prior_key_end = key_end

    self.insert_cursor.execute(
        'insert into progress (state, key_start, key_end) values (?, ?, ?)',
        (STATE_READ, key_start, key_end))

    progress_key = self.insert_cursor.lastrowid

    self._MaybeCommit()

    return progress_key

  def UpdateState(self, key, new_state):
    """Update a specified progress record with new information.

    Args:
      key: The key for this progress record, returned from StoreKeys
      new_state: The new state to associate with this progress record.
    """
    self._OpenProgressConnection()

    assert _RunningInThread(self.progress_thread)
    assert isinstance(new_state, int)

    self.update_cursor.execute('update progress set state=? where id=?',
                               (new_state, key))

    self._MaybeCommit()

  def GetProgressStatusGenerator(self):
    """Get a generator which returns progress information.

    The returned generator will yield a series of 4-tuples that specify
    progress information about a prior run of the uploader. The 4-tuples
    have the following values:

      progress_key: The unique key to later update this record with new
                    progress information.
      state: The last state saved for this progress record.
      key_start: The starting key of the items for uploading (inclusive).
      key_end: The ending key of the items for uploading (inclusive).

    After all incompletely-transferred records are provided, then one
    more 4-tuple will be generated:

      None
      DATA_CONSUMED_TO_HERE: A unique string value indicating this record
                             is being provided.
      None
      key_end: An integer value specifying the last data source key that
               was handled by the previous run of the uploader.

    The caller should begin uploading records which occur after key_end.

    Yields:
      Progress information as tuples (progress_key, state, key_start, key_end).
    """
    conn = sqlite3.connect(self.db_filename, isolation_level=None)
    cursor = conn.cursor()

    cursor.execute('select max(id) from progress')
    batch_id = cursor.fetchone()[0]

    cursor.execute('select key_end from progress where id = ?', (batch_id,))
    key_end = cursor.fetchone()[0]

    self.prior_key_end = key_end

    cursor.execute(
        'select id, state, key_start, key_end from progress'
        '  where state != ?'
        '  order by id',
        (STATE_SENT,))

    rows = cursor.fetchall()

    for row in rows:
      if row is None:
        break

      yield row

    yield None, DATA_CONSUMED_TO_HERE, None, key_end


class StubProgressDatabase(object):
  """A stub implementation of ProgressDatabase which does nothing."""

  def HasUnfinishedWork(self):
    """Whether the stub database has progress information (it doesn't)."""
    return False

  def StoreKeys(self, unused_key_start, unused_key_end):
    """Pretend to store a key in the stub database."""
    return 'fake-key'

  def UpdateState(self, unused_key, unused_new_state):
    """Pretend to update the state of a progress item."""
    pass

  def ThreadComplete(self):
    """Finalize operations on the stub database (i.e. do nothing)."""
    pass


class ProgressTrackerThread(_ThreadBase):
  """A thread which records progress information for the upload process.

  The progress information is stored into the provided progress database.
  This class is not responsible for replaying a prior run's progress
  information out of the database. Separate mechanisms must be used to
  resume a prior upload attempt.
  """

  NAME = 'progress tracking thread'

  def __init__(self, progress_queue, progress_db):
    """Initialize the ProgressTrackerThread instance.

    Args:
      progress_queue: A Queue used for tracking progress information.
      progress_db: The database for tracking progress information; should
        be an instance of ProgressDatabase.
    """
    _ThreadBase.__init__(self)

    self.progress_queue = progress_queue
    self.db = progress_db
    self.entities_sent = 0

  def PerformWork(self):
    """Performs the work of a ProgressTrackerThread."""
    while not self.exit_flag:
      try:
        item = self.progress_queue.get(block=True, timeout=1.0)
      except Queue.Empty:
        continue
      if item == _THREAD_SHOULD_EXIT:
        break

      if item.state == STATE_READ and item.progress_key is None:
        item.progress_key = self.db.StoreKeys(item.key_start, item.key_end)
      else:
        assert item.progress_key is not None

        self.db.UpdateState(item.progress_key, item.state)
        if item.state == STATE_SENT:
          self.entities_sent += item.count

      item.progress_event.set()

      self.progress_queue.task_done()

    self.db.ThreadComplete()



def Validate(value, typ):
  """Checks that value is non-empty and of the right type.

  Args:
    value: any value
    typ: a type or tuple of types

  Raises:
    ValueError if value is None or empty.
    TypeError if it's not the given type.

  """
  if not value:
    raise ValueError('Value should not be empty; received %s.' % value)
  elif not isinstance(value, typ):
    raise TypeError('Expected a %s, but received %s (a %s).' %
                    (typ, value, value.__class__))


class Loader(object):
  """A base class for creating datastore entities from input data.

  To add a handler for bulk loading a new entity kind into your datastore,
  write a subclass of this class that calls Loader.__init__ from your
  class's __init__.

  If you need to run extra code to convert entities from the input
  data, create new properties, or otherwise modify the entities before
  they're inserted, override HandleEntity.

  See the CreateEntity method for the creation of entities from the
  (parsed) input data.
  """

  __loaders = {}
  __kind = None
  __properties = None

  def __init__(self, kind, properties):
    """Constructor.

    Populates this Loader's kind and properties map. Also registers it with
    the bulk loader, so that all you need to do is instantiate your Loader,
    and the bulkload handler will automatically use it.

    Args:
      kind: a string containing the entity kind that this loader handles

      properties: list of (name, converter) tuples.

        This is used to automatically convert the CSV columns into
        properties.  The converter should be a function that takes one
        argument, a string value from the CSV file, and returns a
        correctly typed property value that should be inserted. The
        tuples in this list should match the columns in your CSV file,
        in order.

        For example:
          [('name', str),
           ('id_number', int),
           ('email', datastore_types.Email),
           ('user', users.User),
           ('birthdate', lambda x: datetime.datetime.fromtimestamp(float(x))),
           ('description', datastore_types.Text),
           ]
    """
    Validate(kind, basestring)
    self.__kind = kind

    db.class_for_kind(kind)

    Validate(properties, list)
    for name, fn in properties:
      Validate(name, basestring)
      assert callable(fn), (
        'Conversion function %s for property %s is not callable.' % (fn, name))

    self.__properties = properties

  @staticmethod
  def RegisterLoader(loader):

    Loader.__loaders[loader.__kind] = loader

  def kind(self):
    """ Return the entity kind that this Loader handes.
    """
    return self.__kind

  def CreateEntity(self, values, key_name=None):
    """Creates a entity from a list of property values.

    Args:
      values: list/tuple of str
      key_name: if provided, the name for the (single) resulting entity

    Returns:
      list of db.Model

      The returned entities are populated with the property values from the
      argument, converted to native types using the properties map given in
      the constructor, and passed through HandleEntity. They're ready to be
      inserted.

    Raises:
      AssertionError if the number of values doesn't match the number
        of properties in the properties map.
      ValueError if any element of values is None or empty.
      TypeError if values is not a list or tuple.
    """
    Validate(values, (list, tuple))
    assert len(values) == len(self.__properties), (
      'Expected %d CSV columns, found %d.' %
      (len(self.__properties), len(values)))

    model_class = db.class_for_kind(self.__kind)

    properties = {'key_name': key_name}
    for (name, converter), val in zip(self.__properties, values):
      if converter is bool and val.lower() in ('0', 'false', 'no'):
          val = False
      properties[name] = converter(val)

    entity = model_class(**properties)
    entities = self.HandleEntity(entity)

    if entities:
      if not isinstance(entities, (list, tuple)):
        entities = [entities]

      for entity in entities:
        if not isinstance(entity, db.Model):
          raise TypeError('Expected a db.Model, received %s (a %s).' %
                          (entity, entity.__class__))

    return entities

  def GenerateKey(self, i, values):
    """Generates a key_name to be used in creating the underlying object.

    The default implementation returns None.

    This method can be overridden to control the key generation for
    uploaded entities. The value returned should be None (to use a
    server generated numeric key), or a string which neither starts
    with a digit nor has the form __*__. (See
    http://code.google.com/appengine/docs/python/datastore/keysandentitygroups.html)

    If you generate your own string keys, keep in mind:

    1. The key name for each entity must be unique.
    2. If an entity of the same kind and key already exists in the
       datastore, it will be overwritten.

    Args:
      i: Number corresponding to this object (assume it's run in a loop,
        this is your current count.
      values: list/tuple of str.

    Returns:
      A string to be used as the key_name for an entity.
    """
    return None

  def HandleEntity(self, entity):
    """Subclasses can override this to add custom entity conversion code.

    This is called for each entity, after its properties are populated from
    CSV but before it is stored. Subclasses can override this to add custom
    entity handling code.

    The entity to be inserted should be returned. If multiple entities should
    be inserted, return a list of entities. If no entities should be inserted,
    return None or [].

    Args:
      entity: db.Model

    Returns:
      db.Model or list of db.Model
    """
    return entity


  @staticmethod
  def RegisteredLoaders():
    """Returns a list of the Loader instances that have been created.
    """
    return dict(Loader.__loaders)


class QueueJoinThread(threading.Thread):
  """A thread that joins a queue and exits.

  Queue joins do not have a timeout.  To simulate a queue join with
  timeout, run this thread and join it with a timeout.
  """

  def __init__(self, queue):
    """Initialize a QueueJoinThread.

    Args:
      queue: The queue for this thread to join.
    """
    threading.Thread.__init__(self)
    assert isinstance(queue, (Queue.Queue, ReQueue))
    self.queue = queue

  def run(self):
    """Perform the queue join in this thread."""
    self.queue.join()


def InterruptibleQueueJoin(queue,
                           thread_local,
                           thread_gate,
                           queue_join_thread_factory=QueueJoinThread):
  """Repeatedly joins the given ReQueue or Queue.Queue with short timeout.

  Between each timeout on the join, worker threads are checked.

  Args:
    queue: A Queue.Queue or ReQueue instance.
    thread_local: A threading.local instance which indicates interrupts.
    thread_gate: A ThreadGate instance.
    queue_join_thread_factory: Used for dependency injection.

  Returns:
    True unless the queue join is interrupted by SIGINT or worker death.
  """
  thread = queue_join_thread_factory(queue)
  thread.start()
  while True:
    thread.join(timeout=.5)
    if not thread.isAlive():
      return True
    if thread_local.shut_down:
      logging.debug('Queue join interrupted')
      return False
    for worker_thread in thread_gate.Threads():
      if not worker_thread.isAlive():
        return False


def ShutdownThreads(data_source_thread, work_queue, thread_gate):
  """Shuts down the worker and data source threads.

  Args:
    data_source_thread: A running DataSourceThread instance.
    work_queue: The work queue.
    thread_gate: A ThreadGate instance with workers registered.
  """
  logging.info('An error occurred. Shutting down...')

  data_source_thread.exit_flag = True

  for thread in thread_gate.Threads():
    thread.exit_flag = True

  for unused_thread in thread_gate.Threads():
    thread_gate.EnableThread()

  data_source_thread.join(timeout=3.0)
  if data_source_thread.isAlive():
    logging.warn('%s hung while trying to exit',
                 data_source_thread.GetFriendlyName())

  while not work_queue.empty():
    try:
      unused_item = work_queue.get_nowait()
      work_queue.task_done()
    except Queue.Empty:
      pass


def PerformBulkUpload(app_id,
                      post_url,
                      kind,
                      workitem_generator_factory,
                      num_threads,
                      throttle,
                      progress_db,
                      max_queue_size=DEFAULT_QUEUE_SIZE,
                      request_manager_factory=RequestManager,
                      bulkloaderthread_factory=BulkLoaderThread,
                      progresstrackerthread_factory=ProgressTrackerThread,
                      datasourcethread_factory=DataSourceThread,
                      work_queue_factory=ReQueue,
                      progress_queue_factory=Queue.Queue):
  """Uploads data into an application using a series of HTTP POSTs.

  This function will spin up a number of threads to read entities from
  the data source, pass those to a number of worker ("uploader") threads
  for sending to the application, and track all of the progress in a
  small database in case an error or pause/termination requires a
  restart/resumption of the upload process.

  Args:
    app_id: String containing application id.
    post_url: URL to post the Entity data to.
    kind: Kind of the Entity records being posted.
    workitem_generator_factory: A factory that creates a WorkItem generator.
    num_threads: How many uploader threads should be created.
    throttle: A Throttle instance.
    progress_db: The database to use for replaying/recording progress.
    max_queue_size: Maximum size of the queues before they should block.
    request_manager_factory: Used for dependency injection.
    bulkloaderthread_factory: Used for dependency injection.
    progresstrackerthread_factory: Used for dependency injection.
    datasourcethread_factory: Used for dependency injection.
    work_queue_factory: Used for dependency injection.
    progress_queue_factory: Used for dependency injection.

  Raises:
    AuthenticationError: If authentication is required and fails.
  """
  thread_gate = ThreadGate(True)

  (unused_scheme,
   host_port, url_path,
   unused_query, unused_fragment) = urlparse.urlsplit(post_url)

  work_queue = work_queue_factory(max_queue_size)
  progress_queue = progress_queue_factory(max_queue_size)
  request_manager = request_manager_factory(app_id,
                                            host_port,
                                            url_path,
                                            kind,
                                            throttle)

  throttle.Register(threading.currentThread())
  try:
    request_manager.Authenticate()
  except Exception, e:
    logging.exception(e)
    raise AuthenticationError('Authentication failed')
  if (request_manager.credentials is not None and
      not request_manager.authenticated):
    raise AuthenticationError('Authentication failed')

  for unused_idx in range(num_threads):
    thread = bulkloaderthread_factory(work_queue,
                                      throttle,
                                      thread_gate,
                                      request_manager)
    throttle.Register(thread)
    thread_gate.Register(thread)

  progress_thread = progresstrackerthread_factory(progress_queue, progress_db)

  if progress_db.HasUnfinishedWork():
    logging.debug('Restarting upload using progress database')
    progress_generator_factory = progress_db.GetProgressStatusGenerator
  else:
    progress_generator_factory = None

  data_source_thread = datasourcethread_factory(work_queue,
                                                progress_queue,
                                                workitem_generator_factory,
                                                progress_generator_factory)

  thread_local = threading.local()
  thread_local.shut_down = False

  def Interrupt(unused_signum, unused_frame):
    """Shutdown gracefully in response to a signal."""
    thread_local.shut_down = True

  signal.signal(signal.SIGINT, Interrupt)

  progress_thread.start()
  data_source_thread.start()
  for thread in thread_gate.Threads():
    thread.start()


  while not thread_local.shut_down:
    data_source_thread.join(timeout=0.25)

    if data_source_thread.isAlive():
      for thread in list(thread_gate.Threads()) + [progress_thread]:
        if not thread.isAlive():
          logging.info('Unexpected thread death: %s', thread.getName())
          thread_local.shut_down = True
          break
    else:
      break

  if thread_local.shut_down:
    ShutdownThreads(data_source_thread, work_queue, thread_gate)

  def _Join(ob, msg):
    logging.debug('Waiting for %s...', msg)
    if isinstance(ob, threading.Thread):
      ob.join(timeout=3.0)
      if ob.isAlive():
        logging.debug('Joining %s failed', ob.GetFriendlyName())
      else:
        logging.debug('... done.')
    elif isinstance(ob, (Queue.Queue, ReQueue)):
      if not InterruptibleQueueJoin(ob, thread_local, thread_gate):
        ShutdownThreads(data_source_thread, work_queue, thread_gate)
    else:
      ob.join()
      logging.debug('... done.')

  _Join(work_queue, 'work_queue to flush')

  for unused_thread in thread_gate.Threads():
    work_queue.put(_THREAD_SHOULD_EXIT)

  for unused_thread in thread_gate.Threads():
    thread_gate.EnableThread()

  for thread in thread_gate.Threads():
    _Join(thread, 'thread [%s] to terminate' % thread.getName())

    thread.CheckError()

  if progress_thread.isAlive():
    _Join(progress_queue, 'progress_queue to finish')
  else:
    logging.warn('Progress thread exited prematurely')

  progress_queue.put(_THREAD_SHOULD_EXIT)
  _Join(progress_thread, 'progress_thread to terminate')
  progress_thread.CheckError()

  data_source_thread.CheckError()

  total_up, duration = throttle.TotalTransferred(BANDWIDTH_UP)
  s_total_up, unused_duration = throttle.TotalTransferred(HTTPS_BANDWIDTH_UP)
  total_up += s_total_up
  logging.info('%d entites read, %d previously transferred',
               data_source_thread.read_count,
               data_source_thread.sent_count)
  logging.info('%d entities (%d bytes) transferred in %.1f seconds',
               progress_thread.entities_sent, total_up, duration)
  if (data_source_thread.read_all and
      progress_thread.entities_sent + data_source_thread.sent_count >=
      data_source_thread.read_count):
    logging.info('All entities successfully uploaded')
  else:
    logging.info('Some entities not successfully uploaded')


def PrintUsageExit(code):
  """Prints usage information and exits with a status code.

  Args:
    code: Status code to pass to sys.exit() after displaying usage information.
  """
  print __doc__ % {'arg0': sys.argv[0]}
  sys.stdout.flush()
  sys.stderr.flush()
  sys.exit(code)


def ParseArguments(argv):
  """Parses command-line arguments.

  Prints out a help message if -h or --help is supplied.

  Args:
    argv: List of command-line arguments.

  Returns:
    Tuple (url, filename, cookie, batch_size, kind) containing the values from
    each corresponding command-line flag.
  """
  opts, unused_args = getopt.getopt(
      argv[1:],
      'h',
      ['debug',
       'help',
       'url=',
       'filename=',
       'batch_size=',
       'kind=',
       'num_threads=',
       'bandwidth_limit=',
       'rps_limit=',
       'http_limit=',
       'db_filename=',
       'app_id=',
       'config_file=',
       'auth_domain=',
      ])

  url = None
  filename = None
  batch_size = DEFAULT_BATCH_SIZE
  kind = None
  num_threads = DEFAULT_THREAD_COUNT
  bandwidth_limit = DEFAULT_BANDWIDTH_LIMIT
  rps_limit = DEFAULT_RPS_LIMIT
  http_limit = DEFAULT_REQUEST_LIMIT
  db_filename = None
  app_id = None
  config_file = None
  auth_domain = 'gmail.com'

  for option, value in opts:
    if option == '--debug':
      logging.getLogger().setLevel(logging.DEBUG)
    elif option in ('-h', '--help'):
      PrintUsageExit(0)
    elif option == '--url':
      url = value
    elif option == '--filename':
      filename = value
    elif option == '--batch_size':
      batch_size = int(value)
    elif option == '--kind':
      kind = value
    elif option == '--num_threads':
      num_threads = int(value)
    elif option == '--bandwidth_limit':
      bandwidth_limit = int(value)
    elif option == '--rps_limit':
      rps_limit = int(value)
    elif option == '--http_limit':
      http_limit = int(value)
    elif option == '--db_filename':
      db_filename = value
    elif option == '--app_id':
      app_id = value
    elif option == '--config_file':
      config_file = value
    elif option == '--auth_domain':
      auth_domain = value

  return ProcessArguments(app_id=app_id,
                          url=url,
                          filename=filename,
                          batch_size=batch_size,
                          kind=kind,
                          num_threads=num_threads,
                          bandwidth_limit=bandwidth_limit,
                          rps_limit=rps_limit,
                          http_limit=http_limit,
                          db_filename=db_filename,
                          config_file=config_file,
                          auth_domain=auth_domain,
                          die_fn=lambda: PrintUsageExit(1))


def ThrottleLayout(bandwidth_limit, http_limit, rps_limit):
  return {
      BANDWIDTH_UP: bandwidth_limit,
      BANDWIDTH_DOWN: bandwidth_limit,
      REQUESTS: http_limit,
      HTTPS_BANDWIDTH_UP: bandwidth_limit / 5,
      HTTPS_BANDWIDTH_DOWN: bandwidth_limit / 5,
      HTTPS_REQUESTS: http_limit / 5,
      RECORDS: rps_limit,
  }


def LoadConfig(config_file):
  """Loads a config file and registers any Loader classes present."""
  if config_file:
    global_dict = dict(globals())
    execfile(config_file, global_dict)
    for cls in Loader.__subclasses__():
      Loader.RegisterLoader(cls())


def _MissingArgument(arg_name, die_fn):
  """Print error message about missing argument and die."""
  print >>sys.stderr, '%s argument required' % arg_name
  die_fn()


def ProcessArguments(app_id=None,
                     url=None,
                     filename=None,
                     batch_size=DEFAULT_BATCH_SIZE,
                     kind=None,
                     num_threads=DEFAULT_THREAD_COUNT,
                     bandwidth_limit=DEFAULT_BANDWIDTH_LIMIT,
                     rps_limit=DEFAULT_RPS_LIMIT,
                     http_limit=DEFAULT_REQUEST_LIMIT,
                     db_filename=None,
                     config_file=None,
                     auth_domain='gmail.com',
                     die_fn=lambda: sys.exit(1)):
  """Processes non command-line input arguments."""
  if db_filename is None:
    db_filename = time.strftime('bulkloader-progress-%Y%m%d.%H%M%S.sql3')

  if batch_size <= 0:
    print >>sys.stderr, 'batch_size must be 1 or larger'
    die_fn()

  if url is None:
    _MissingArgument('url', die_fn)

  if filename is None:
    _MissingArgument('filename', die_fn)

  if kind is None:
    _MissingArgument('kind', die_fn)

  if config_file is None:
    _MissingArgument('config_file', die_fn)

  if app_id is None:
    (unused_scheme, host_port, unused_url_path,
     unused_query, unused_fragment) = urlparse.urlsplit(url)
    suffix_idx = host_port.find('.appspot.com')
    if suffix_idx > -1:
      app_id = host_port[:suffix_idx]
    elif host_port.split(':')[0].endswith('google.com'):
      app_id = host_port.split('.')[0]
    else:
      print >>sys.stderr, 'app_id required for non appspot.com domains'
      die_fn()

  return (app_id, url, filename, batch_size, kind, num_threads,
          bandwidth_limit, rps_limit, http_limit, db_filename, config_file,
          auth_domain)


def _PerformBulkload(app_id=None,
                     url=None,
                     filename=None,
                     batch_size=DEFAULT_BATCH_SIZE,
                     kind=None,
                     num_threads=DEFAULT_THREAD_COUNT,
                     bandwidth_limit=DEFAULT_BANDWIDTH_LIMIT,
                     rps_limit=DEFAULT_RPS_LIMIT,
                     http_limit=DEFAULT_REQUEST_LIMIT,
                     db_filename=None,
                     config_file=None,
                     auth_domain='gmail.com'):
  """Runs the bulkloader, given the options as keyword arguments.

  Args:
    app_id: The application id.
    url: The url of the remote_api endpoint.
    filename: The name of the file containing the CSV data.
    batch_size: The number of records to send per request.
    kind: The kind of entity to transfer.
    num_threads: The number of threads to use to transfer data.
    bandwidth_limit: Maximum bytes/second to transfers.
    rps_limit: Maximum records/second to transfer.
    http_limit: Maximum requests/second for transfers.
    db_filename: The name of the SQLite3 progress database file.
    config_file: The name of the configuration file.
    auth_domain: The auth domain to use for logins and UserProperty.

  Returns:
    An exit code.
  """
  os.environ['AUTH_DOMAIN'] = auth_domain
  LoadConfig(config_file)

  throttle_layout = ThrottleLayout(bandwidth_limit, http_limit, rps_limit)

  throttle = Throttle(layout=throttle_layout)


  workitem_generator_factory = GetCSVGeneratorFactory(filename, batch_size)

  if db_filename == 'skip':
    progress_db = StubProgressDatabase()
  else:
    progress_db = ProgressDatabase(db_filename)


  max_queue_size = max(DEFAULT_QUEUE_SIZE, 2 * num_threads + 5)

  PerformBulkUpload(app_id,
                    url,
                    kind,
                    workitem_generator_factory,
                    num_threads,
                    throttle,
                    progress_db,
                    max_queue_size=max_queue_size)

  return 0


def Run(app_id=None,
        url=None,
        filename=None,
        batch_size=DEFAULT_BATCH_SIZE,
        kind=None,
        num_threads=DEFAULT_THREAD_COUNT,
        bandwidth_limit=DEFAULT_BANDWIDTH_LIMIT,
        rps_limit=DEFAULT_RPS_LIMIT,
        http_limit=DEFAULT_REQUEST_LIMIT,
        db_filename=None,
        auth_domain='gmail.com',
        config_file=None):
  """Sets up and runs the bulkloader, given the options as keyword arguments.

  Args:
    app_id: The application id.
    url: The url of the remote_api endpoint.
    filename: The name of the file containing the CSV data.
    batch_size: The number of records to send per request.
    kind: The kind of entity to transfer.
    num_threads: The number of threads to use to transfer data.
    bandwidth_limit: Maximum bytes/second to transfers.
    rps_limit: Maximum records/second to transfer.
    http_limit: Maximum requests/second for transfers.
    db_filename: The name of the SQLite3 progress database file.
    config_file: The name of the configuration file.
    auth_domain: The auth domain to use for logins and UserProperty.

  Returns:
    An exit code.
  """
  logging.basicConfig(
      format='%(levelname)-8s %(asctime)s %(filename)s] %(message)s')
  args = ProcessArguments(app_id=app_id,
                          url=url,
                          filename=filename,
                          batch_size=batch_size,
                          kind=kind,
                          num_threads=num_threads,
                          bandwidth_limit=bandwidth_limit,
                          rps_limit=rps_limit,
                          http_limit=http_limit,
                          db_filename=db_filename,
                          config_file=config_file)

  (app_id, url, filename, batch_size, kind, num_threads, bandwidth_limit,
   rps_limit, http_limit, db_filename, config_file, auth_domain) = args

  return _PerformBulkload(app_id=app_id,
                          url=url,
                          filename=filename,
                          batch_size=batch_size,
                          kind=kind,
                          num_threads=num_threads,
                          bandwidth_limit=bandwidth_limit,
                          rps_limit=rps_limit,
                          http_limit=http_limit,
                          db_filename=db_filename,
                          config_file=config_file,
                          auth_domain=auth_domain)


def main(argv):
  """Runs the importer from the command line."""
  logging.basicConfig(
      level=logging.INFO,
      format='%(levelname)-8s %(asctime)s %(filename)s] %(message)s')

  args = ParseArguments(argv)
  if None in args:
    print >>sys.stderr, 'Invalid arguments'
    PrintUsageExit(1)

  (app_id, url, filename, batch_size, kind, num_threads,
   bandwidth_limit, rps_limit, http_limit, db_filename, config_file,
   auth_domain) = args

  return _PerformBulkload(app_id=app_id,
                          url=url,
                          filename=filename,
                          batch_size=batch_size,
                          kind=kind,
                          num_threads=num_threads,
                          bandwidth_limit=bandwidth_limit,
                          rps_limit=rps_limit,
                          http_limit=http_limit,
                          db_filename=db_filename,
                          config_file=config_file,
                          auth_domain=auth_domain)


if __name__ == '__main__':
  sys.exit(main(sys.argv))
