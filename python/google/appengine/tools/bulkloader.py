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

"""Imports data over HTTP.

Usage:
  %(arg0)s [flags]

    --debug                 Show debugging information. (Optional)
    --app_id=<string>       Application ID of endpoint (Optional for
                            *.appspot.com)
    --auth_domain=<domain>  The auth domain to use for logging in and for
                            UserProperties. (Default: gmail.com)
    --bandwidth_limit=<int> The maximum number of bytes per second for the
                            aggregate transfer of data to the server. Bursts
                            may exceed this, but overall transfer rate is
                            restricted to this rate. (Default 250000)
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
    --download              Export entities to a file.
    --email=<string>        The username to use. Will prompt if omitted.
    --exporter_opts=<string>
                            A string to pass to the Exporter.initialize method.
    --filename=<path>       Path to the file to import. (Required)
    --has_header            Skip the first row of the input.
    --http_limit=<int>      The maximum numer of HTTP requests per second to
                            send to the server. (Default: 8)
    --kind=<string>         Name of the Entity object kind to put in the
                            datastore. (Required)
    --loader_opts=<string>  A string to pass to the Loader.initialize method.
    --log_file=<path>       File to write bulkloader logs.  If not supplied
                            then a new log file will be created, named:
                            bulkloader-log-TIMESTAMP.
    --num_threads=<int>     Number of threads to use for uploading entities
                            (Default 10)
    --passin                Read the login password from stdin.
    --result_db_filename=<path>
                            Result database to write to for downloads.
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



import cPickle
import csv
import errno
import getopt
import getpass
import imp
import logging
import os
import Queue
import re
import signal
import StringIO
import sys
import threading
import time
import urllib2
import urlparse

from google.appengine.api import datastore_errors
from google.appengine.ext import db
from google.appengine.ext.db import polymodel
from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.runtime import apiproxy_errors
from google.appengine.tools import appengine_rpc

try:
  import sqlite3
except ImportError:
  pass

logger = logging.getLogger('google.appengine.tools.bulkloader')

DEFAULT_THREAD_COUNT = 10

DEFAULT_BATCH_SIZE = 10

DEFAULT_QUEUE_SIZE = DEFAULT_THREAD_COUNT * 10

_THREAD_SHOULD_EXIT = '_THREAD_SHOULD_EXIT'

STATE_READ = 0
STATE_SENDING = 1
STATE_SENT = 2
STATE_NOT_SENT = 3

STATE_GETTING = 1
STATE_GOT = 2
STATE_NOT_GOT = 3

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

MAXIMUM_INCREASE_DURATION = 8.0
MAXIMUM_HOLD_DURATION = 10.0


def ImportStateMessage(state):
  """Converts a numeric state identifier to a status message."""
  return ({
      STATE_READ: 'Batch read from file.',
      STATE_SENDING: 'Sending batch to server.',
      STATE_SENT: 'Batch successfully sent.',
      STATE_NOT_SENT: 'Error while sending batch.'
  }[state])


def ExportStateMessage(state):
  """Converts a numeric state identifier to a status message."""
  return ({
      STATE_READ: 'Batch read from file.',
      STATE_GETTING: 'Fetching batch from server',
      STATE_GOT: 'Batch successfully fetched.',
      STATE_NOT_GOT: 'Error while fetching batch'
  }[state])


def ExportStateName(state):
  """Converts a numeric state identifier to a string."""
  return ({
      STATE_READ: 'READ',
      STATE_GETTING: 'GETTING',
      STATE_GOT: 'GOT',
      STATE_NOT_GOT: 'NOT_GOT'
  }[state])


def ImportStateName(state):
  """Converts a numeric state identifier to a string."""
  return ({
      STATE_READ: 'READ',
      STATE_GETTING: 'SENDING',
      STATE_GOT: 'SENT',
      STATE_NOT_GOT: 'NOT_SENT'
  }[state])


class Error(Exception):
  """Base-class for exceptions in this module."""


class MissingPropertyError(Error):
  """An expected field is missing from an entity, and no default was given."""


class FatalServerError(Error):
  """An unrecoverable error occurred while posting data to the server."""


class ResumeError(Error):
  """Error while trying to resume a partial upload."""


class ConfigurationError(Error):
  """Error in configuration options."""


class AuthenticationError(Error):
  """Error while trying to authenticate with the server."""


class FileNotFoundError(Error):
  """A filename passed in by the user refers to a non-existent input file."""


class FileNotReadableError(Error):
  """A filename passed in by the user refers to a non-readable input file."""


class FileExistsError(Error):
  """A filename passed in by the user refers to an existing output file."""


class FileNotWritableError(Error):
  """A filename passed in by the user refers to a non-writable output file."""


class KeyRangeError(Error):
  """Error while trying to generate a KeyRange."""


class BadStateError(Error):
  """A work item in an unexpected state was encountered."""


class NameClashError(Error):
  """A name clash occurred while trying to alias old method names."""
  def __init__(self, old_name, new_name, klass):
    Error.__init__(self, old_name, new_name, klass)
    self.old_name = old_name
    self.new_name = new_name
    self.klass = klass


def GetCSVGeneratorFactory(kind, csv_filename, batch_size, csv_has_header,
                           openfile=open, create_csv_reader=csv.reader):
  """Return a factory that creates a CSV-based WorkItem generator.

  Args:
    kind: The kind of the entities being uploaded.
    csv_filename: File on disk containing CSV data.
    batch_size: Maximum number of CSV rows to stash into a WorkItem.
    csv_has_header: Whether to skip the first row of the CSV.
    openfile: Used for dependency injection.
    create_csv_reader: Used for dependency injection.

  Returns:
    A callable (accepting the Progress Queue and Progress Generators
    as input) which creates the WorkItem generator.
  """
  loader = Loader.RegisteredLoader(kind)
  loader._Loader__openfile = openfile
  loader._Loader__create_csv_reader = create_csv_reader
  record_generator = loader.generate_records(csv_filename)

  def CreateGenerator(progress_queue, progress_generator):
    """Initialize a WorkItem generator linked to a progress generator and queue.

    Args:
      progress_queue: A ProgressQueue instance to send progress information.
      progress_generator: A generator of progress information or None.

    Returns:
      A WorkItemGenerator instance.
    """
    return WorkItemGenerator(progress_queue,
                             progress_generator,
                             record_generator,
                             csv_has_header,
                             batch_size)

  return CreateGenerator


class WorkItemGenerator(object):
  """Reads rows from a row generator and generates WorkItems of batches."""

  def __init__(self,
               progress_queue,
               progress_generator,
               record_generator,
               skip_first,
               batch_size):
    """Initialize a WorkItemGenerator.

    Args:
      progress_queue: A progress queue with which to associate WorkItems.
      progress_generator: A generator of progress information.
      record_generator: A generator of data records.
      skip_first: Whether to skip the first data record.
      batch_size: The number of data records per WorkItem.
    """
    self.progress_queue = progress_queue
    self.progress_generator = progress_generator
    self.reader = record_generator
    self.skip_first = skip_first
    self.batch_size = batch_size
    self.line_number = 1
    self.column_count = None
    self.read_rows = []
    self.row_count = 0
    self.xfer_count = 0

  def _AdvanceTo(self, line):
    """Advance the reader to the given line.

    Args:
      line: A line number to advance to.
    """
    while self.line_number < line:
      self.reader.next()
      self.line_number += 1
      self.row_count += 1
      self.xfer_count += 1

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
    """Reads from the record_generator and generates WorkItems.

    Yields:
      Instances of class WorkItem

    Raises:
      ResumeError: If the progress database and data file indicate a different
        number of rows.
    """
    if self.skip_first:
      logger.info('Skipping header line.')
      try:
        self.reader.next()
      except StopIteration:
        return

    exhausted = False

    self.line_number = 1
    self.column_count = None

    logger.info('Starting import; maximum %d entities per post',
                self.batch_size)

    state = None
    if self.progress_generator:
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
            logger.error('Mismatch between data file and progress database')
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


class CSVGenerator(object):
  """Reads a CSV file and generates data records."""

  def __init__(self,
               csv_filename,
               openfile=open,
               create_csv_reader=csv.reader):
    """Initializes a CSV generator.

    Args:
      csv_filename: File on disk containing CSV data.
      openfile: Used for dependency injection of 'open'.
      create_csv_reader: Used for dependency injection of 'csv.reader'.
    """
    self.csv_filename = csv_filename
    self.openfile = openfile
    self.create_csv_reader = create_csv_reader

  def Records(self):
    """Reads the CSV data file and generates row records.

    Yields:
      Lists of strings

    Raises:
      ResumeError: If the progress database and data file indicate a different
        number of rows.
    """
    csv_file = self.openfile(self.csv_filename, 'rb')
    reader = self.create_csv_reader(csv_file, skipinitialspace=True)
    return reader


class KeyRangeGenerator(object):
  """Generates ranges of keys to download.

  Reads progress information from the progress database and creates
  KeyRange objects corresponding to incompletely downloaded parts of an
  export.
  """

  def __init__(self, kind, progress_queue, progress_generator):
    """Initialize the KeyRangeGenerator.

    Args:
      kind: The kind of entities being transferred.
      progress_queue: A queue used for tracking progress information.
      progress_generator: A generator of prior progress information, or None
        if there is no prior status.
    """
    self.kind = kind
    self.row_count = 0
    self.xfer_count = 0
    self.progress_queue = progress_queue
    self.progress_generator = progress_generator

  def Batches(self):
    """Iterate through saved progress information.

    Yields:
      KeyRange instances corresponding to undownloaded key ranges.
    """
    if self.progress_generator is not None:
      for progress_key, state, key_start, key_end in self.progress_generator:
        if state is not None and state != STATE_GOT and key_start is not None:
          key_start = ParseKey(key_start)
          key_end = ParseKey(key_end)

          result = KeyRange(self.progress_queue,
                            self.kind,
                            key_start=key_start,
                            key_end=key_end,
                            progress_key=progress_key,
                            direction=KeyRange.ASC,
                            state=STATE_READ)
          yield result
    else:

      yield KeyRange(
          self.progress_queue, self.kind,
          key_start=None,
          key_end=None,
          direction=KeyRange.DESC)


class ReQueue(object):
  """A special thread-safe queue.

  A ReQueue allows unfinished work items to be returned with a call to
  reput().  When an item is reput, task_done() should *not* be called
  in addition, getting an item that has been reput does not increase
  the number of outstanding tasks.

  This class shares an interface with Queue.Queue and provides the
  additional reput method.
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
    TaskDone has not been called.

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

  def qsize(self):
    return self.queue.qsize() + self.requeue.qsize()


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
    """Factory to produce a ThrottledHttpRpcServer.

    Args:
      args: Positional args to pass to ThrottledHttpRpcServer.
      kwargs: Keyword args to pass to ThrottledHttpRpcServer.

    Returns:
      A ThrottledHttpRpcServer instance.
    """
    kwargs['account_type'] = 'HOSTED_OR_GOOGLE'
    kwargs['save_cookies'] = True
    return ThrottledHttpRpcServer(throttle, request_manager, *args, **kwargs)
  return MakeRpcServer


class ExportResult(object):
  """Holds the decoded content for the result of an export requests."""

  def __init__(self, continued, direction, keys, entities):
    self.continued = continued
    self.direction = direction
    self.keys = keys
    self.entities = entities
    self.count = len(keys)
    assert self.count == len(entities)
    assert direction in (KeyRange.ASC, KeyRange.DESC)
    if self.count > 0:
      if direction == KeyRange.ASC:
        self.key_start = keys[0]
        self.key_end = keys[-1]
      else:
        self.key_start = keys[-1]
        self.key_end = keys[0]

  def __str__(self):
    return 'continued = %s\n%s' % (
        str(self.continued), '\n'.join(self.entities))


class _WorkItem(object):
  """Holds a description of a unit of upload or download work."""

  def __init__(self, progress_queue, key_start, key_end, state_namer,
               state=STATE_READ, progress_key=None):
    """Initialize the _WorkItem instance.

    Args:
      progress_queue: A queue used for tracking progress information.
      key_start: The starting key, inclusive.
      key_end: The ending key, inclusive.
      state_namer: Function to describe work item states.
      state: The initial state of the work item.
      progress_key: If this WorkItem represents state from a prior run,
        then this will be the key within the progress database.
    """
    self.progress_queue = progress_queue
    self.key_start = key_start
    self.key_end = key_end
    self.state_namer = state_namer
    self.state = state
    self.progress_key = progress_key
    self.progress_event = threading.Event()

  def _AssertInState(self, *states):
    """Raises an Error if the state of this range is not in states."""
    if not self.state in states:
      raise BadStateError('%s:%s not in %s' %
                          (str(self),
                           self.state_namer(self.state),
                           map(self.state_namer, states)))

  def _AssertProgressKey(self):
    """Raises an Error if the progress key is None."""
    if self.progress_key is None:
      raise BadStateError('%s: Progress key is missing' % str(self))

  def MarkAsRead(self):
    """Mark this _WorkItem as read, updating the progress database."""
    self._AssertInState(STATE_READ)
    self._StateTransition(STATE_READ, blocking=True)

  def MarkAsTransferring(self):
    """Mark this _WorkItem as transferring, updating the progress database."""
    self._AssertInState(STATE_READ, STATE_NOT_GOT)
    self._AssertProgressKey()
    self._StateTransition(STATE_GETTING, blocking=True)

  def MarkAsTransferred(self):
    """Mark this _WorkItem as transferred, updating the progress database."""
    raise NotImplementedError()

  def MarkAsError(self):
    """Mark this _WorkItem as failed, updating the progress database."""
    self._AssertInState(STATE_GETTING)
    self._AssertProgressKey()
    self._StateTransition(STATE_NOT_GOT, blocking=True)

  def _StateTransition(self, new_state, blocking=False):
    """Transition the work item to a new state, storing progress information.

    Args:
      new_state: The state to transition to.
      blocking: Whether to block for the progress thread to acknowledge the
        transition.
    """
    assert not self.progress_event.isSet()

    self.state = new_state

    self.progress_queue.put(self)

    if blocking:
      self.progress_event.wait()

      self.progress_event.clear()



class WorkItem(_WorkItem):
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
    _WorkItem.__init__(self, progress_queue, key_start, key_end,
                       ImportStateName, state=STATE_READ,
                       progress_key=progress_key)

    assert isinstance(key_start, (int, long))
    assert isinstance(key_end, (int, long))
    assert key_start <= key_end

    self.rows = rows
    self.content = None
    self.count = len(rows)

  def __str__(self):
    return '[%s-%s]' % (self.key_start, self.key_end)

  def MarkAsTransferred(self):
    """Mark this WorkItem as sucessfully-sent to the server."""

    self._AssertInState(STATE_SENDING)
    self._AssertProgressKey()

    self._StateTransition(STATE_SENT, blocking=False)


def GetImplementationClass(kind_or_class_key):
  """Returns the implementation class for a given kind or class key.

  Args:
    kind_or_class_key: A kind string or a tuple of kind strings.

  Return:
    A db.Model subclass for the given kind or class key.
  """
  if isinstance(kind_or_class_key, tuple):
    try:
      implementation_class = polymodel._class_map[kind_or_class_key]
    except KeyError:
      raise db.KindError('No implementation for class \'%s\'' %
                         kind_or_class_key)
  else:
    implementation_class = db.class_for_kind(kind_or_class_key)
  return implementation_class

class EmptyQuery(db.Query):
  def get(self):
    return None

  def fetch(self, limit=1000, offset=0):
    return []

  def count(self, limit=1000):
    return 0


def KeyLEQ(key1, key2):
  """Compare two keys for less-than-or-equal-to.

  All keys with numeric ids come before all keys with names.

  Args:
    key1: An int or db.Key instance.
    key2: An int or db.Key instance.

  Returns:
    True if key1 <= key2
  """
  if isinstance(key1, int) and isinstance(key2, int):
    return key1 <= key2
  if key1 is None or key2 is None:
    return True
  if key1.id() and not key2.id():
    return True
  return key1.id_or_name() <= key2.id_or_name()


class KeyRange(_WorkItem):
  """Represents an item of download work.

  A KeyRange object represents a key range (key_start, key_end) and a
  scan direction (KeyRange.DESC or KeyRange.ASC).  The KeyRange object
  has an associated state: STATE_READ, STATE_GETTING, STATE_GOT, and
  STATE_ERROR.

  - STATE_READ indicates the range ready to be downloaded by a worker thread.
  - STATE_GETTING indicates the range is currently being downloaded.
  - STATE_GOT indicates that the range was successfully downloaded
  - STATE_ERROR indicates that an error occurred during the last download
    attempt

  KeyRanges not in the STATE_GOT state are stored in the progress database.
  When a piece of KeyRange work is downloaded, the download may cover only
  a portion of the range.  In this case, the old KeyRange is removed from
  the progress database and ranges covering the undownloaded range are
  generated and stored as STATE_READ in the export progress database.
  """

  DESC = 0
  ASC = 1

  MAX_KEY_LEN = 500

  def __init__(self,
               progress_queue,
               kind,
               direction,
               key_start=None,
               key_end=None,
               include_start=True,
               include_end=True,
               progress_key=None,
               state=STATE_READ):
    """Initialize a KeyRange object.

    Args:
      progress_queue: A queue used for tracking progress information.
      kind: The kind of entities for this range.
      direction: The direction of the query for this range.
      key_start: The starting key for this range.
      key_end: The ending key for this range.
      include_start: Whether the start key should be included in the range.
      include_end: Whether the end key should be included in the range.
      progress_key: The key for this range within the progress database.
      state: The initial state of this range.

    Raises:
      KeyRangeError: if key_start is None.
    """
    assert direction in (KeyRange.ASC, KeyRange.DESC)
    _WorkItem.__init__(self, progress_queue, key_start, key_end,
                       ExportStateName, state=state, progress_key=progress_key)
    self.kind = kind
    self.direction = direction
    self.export_result = None
    self.count = 0
    self.include_start = include_start
    self.include_end = include_end
    self.SPLIT_KEY = db.Key.from_path(self.kind, unichr(0))

  def __str__(self):
    return '[%s-%s]' % (PrettyKey(self.key_start), PrettyKey(self.key_end))

  def __repr__(self):
    return self.__str__()

  def MarkAsTransferred(self):
    """Mark this KeyRange as transferred, updating the progress database."""
    pass

  def Process(self, export_result, num_threads, batch_size, work_queue):
    """Mark this KeyRange as success, updating the progress database.

    Process will split this KeyRange based on the content of export_result and
    adds the unfinished ranges to the work queue.

    Args:
      export_result: An ExportResult instance.
      num_threads: The number of threads for parallel transfers.
      batch_size: The number of entities to transfer per request.
      work_queue: The work queue to add unfinished ranges to.

    Returns:
      A list of KeyRanges representing undownloaded datastore key ranges.
    """
    self._AssertInState(STATE_GETTING)
    self._AssertProgressKey()

    self.export_result = export_result
    self.count = len(export_result.keys)
    if export_result.continued:
      self._FinishedRange()._StateTransition(STATE_GOT, blocking=True)
      self._AddUnfinishedRanges(num_threads, batch_size, work_queue)
    else:
      self._StateTransition(STATE_GOT, blocking=True)

  def _FinishedRange(self):
    """Returns the range completed by the export_result.

    Returns:
      A KeyRange representing a completed range.
    """
    assert self.export_result is not None

    if self.direction == KeyRange.ASC:
      key_start = self.key_start
      if self.export_result.continued:
        key_end = self.export_result.key_end
      else:
        key_end = self.key_end
    else:
      key_end = self.key_end
      if self.export_result.continued:
        key_start = self.export_result.key_start
      else:
        key_start = self.key_start

    result = KeyRange(self.progress_queue,
                      self.kind,
                      key_start=key_start,
                      key_end=key_end,
                      direction=self.direction)

    result.progress_key = self.progress_key
    result.export_result = self.export_result
    result.state = self.state
    result.count = self.count
    return result

  def FilterQuery(self, query):
    """Add query filter to restrict to this key range.

    Args:
      query: A db.Query instance.
    """
    if self.key_start == self.key_end and not (
        self.include_start or self.include_end):
      return EmptyQuery()
    if self.include_start:
      start_comparator = '>='
    else:
      start_comparator = '>'
    if self.include_end:
      end_comparator = '<='
    else:
      end_comparator = '<'
    if self.key_start and self.key_end:
      query.filter('__key__ %s' % start_comparator, self.key_start)
      query.filter('__key__ %s' % end_comparator, self.key_end)
    elif self.key_start:
      query.filter('__key__ %s' % start_comparator, self.key_start)
    elif self.key_end:
      query.filter('__key__ %s' % end_comparator, self.key_end)

    return query

  def MakeParallelQuery(self):
    """Construct a query for this key range, for parallel downloading.

    Returns:
      A db.Query instance.

    Raises:
      KeyRangeError: if self.direction is not one of
        KeyRange.ASC, KeyRange.DESC
    """
    if self.direction == KeyRange.ASC:
      direction = ''
    elif self.direction == KeyRange.DESC:
      direction = '-'
    else:
      raise KeyRangeError('KeyRange direction unexpected: %s', self.direction)
    query = db.Query(GetImplementationClass(self.kind))
    query.order('%s__key__' % direction)

    return self.FilterQuery(query)

  def MakeSerialQuery(self):
    """Construct a query for this key range without descending __key__ scan.

    Returns:
      A db.Query instance.
    """
    query = db.Query(GetImplementationClass(self.kind))
    query.order('__key__')

    return self.FilterQuery(query)

  def _BisectStringRange(self, start, end):
    if start == end:
      return (start, start, end)
    start += '\0'
    end += '\0'
    midpoint = []
    expected_max = 127
    for i in xrange(min(len(start), len(end))):
      if start[i] == end[i]:
        midpoint.append(start[i])
      else:
        ord_sum = ord(start[i]) + ord(end[i])
        midpoint.append(unichr(ord_sum / 2))
        if ord_sum % 2:
          if len(start) > i + 1:
            ord_start = ord(start[i+1])
          else:
            ord_start = 0
          if ord_start < expected_max:
            ord_split = (expected_max + ord_start) / 2
          else:
            ord_split = (0xFFFF + ord_start) / 2
          midpoint.append(unichr(ord_split))
        break
    return (start[:-1], ''.join(midpoint), end[:-1])

  def SplitRange(self, key_start, include_start, key_end, include_end,
                 export_result, num_threads, batch_size, work_queue):
    """Split the key range [key_start, key_end] into a list of ranges."""
    if export_result.direction == KeyRange.ASC:
      key_start = export_result.key_end
      include_start = False
    else:
      key_end = export_result.key_start
      include_end = False
    key_pairs = []
    if not key_start:
      key_pairs.append((key_start, include_start, key_end, include_end,
                        KeyRange.ASC))
    elif not key_end:
      key_pairs.append((key_start, include_start, key_end, include_end,
                        KeyRange.DESC))
    elif work_queue.qsize() > 2 * num_threads:
      key_pairs.append((key_start, include_start, key_end, include_end,
                        KeyRange.ASC))
    elif key_start.id() and key_end.id():
      if key_end.id() - key_start.id() > batch_size:
        key_half = db.Key.from_path(self.kind,
                                    (key_start.id() + key_end.id()) / 2)
        key_pairs.append((key_start, include_start,
                          key_half, True,
                          KeyRange.DESC))
        key_pairs.append((key_half, False,
                          key_end, include_end,
                          KeyRange.ASC))
      else:
        key_pairs.append((key_start, include_start, key_end, include_end,
                          KeyRange.ASC))
    elif key_start.name() and key_end.name():
      (start, middle, end) = self._BisectStringRange(key_start.name(),
                                                     key_end.name())
      key_pairs.append((key_start, include_start,
                        db.Key.from_path(self.kind, middle), True,
                        KeyRange.DESC))
      key_pairs.append((db.Key.from_path(self.kind, middle), False,
                        key_end, include_end,
                        KeyRange.ASC))
    else:
      assert key_start.id() and key_end.name()
      key_pairs.append((key_start, include_start,
                        self.SPLIT_KEY, False,
                        KeyRange.DESC))
      key_pairs.append((self.SPLIT_KEY, True,
                        key_end, include_end,
                        KeyRange.ASC))

    ranges = [KeyRange(self.progress_queue,
                       self.kind,
                       key_start=start,
                       include_start=include_start,
                       key_end=end,
                       include_end=include_end,
                       direction=direction)
              for (start, include_start, end, include_end, direction)
              in key_pairs]

    for key_range in ranges:
      key_range.MarkAsRead()
      work_queue.put(key_range, block=True)

  def _AddUnfinishedRanges(self, num_threads, batch_size, work_queue):
    """Adds incomplete KeyRanges to the work_queue.

    Args:
      num_threads: The number of threads for parallel transfers.
      batch_size: The number of entities to transfer per request.
      work_queue: The work queue to add unfinished ranges to.

    Returns:
      A list of KeyRanges representing incomplete datastore key ranges.

    Raises:
      KeyRangeError: if this key range has already been completely transferred.
    """
    assert self.export_result is not None
    if self.export_result.continued:
      self.SplitRange(self.key_start, self.include_start, self.key_end,
                      self.include_end, self.export_result,
                      num_threads, batch_size, work_queue)
    else:
      raise KeyRangeError('No unfinished part of key range.')


class RequestManager(object):
  """A class which wraps a connection to the server."""

  def __init__(self,
               app_id,
               host_port,
               url_path,
               kind,
               throttle,
               batch_size,
               secure,
               email,
               passin):
    """Initialize a RequestManager object.

    Args:
      app_id: String containing the application id for requests.
      host_port: String containing the "host:port" pair; the port is optional.
      url_path: partial URL (path) to post entity data to.
      kind: Kind of the Entity records being posted.
      throttle: A Throttle instance.
      batch_size: The number of entities to transfer per request.
      secure: Use SSL when communicating with server.
      email: If not none, the username to log in with.
      passin: If True, the password will be read from standard in.
    """
    self.app_id = app_id
    self.host_port = host_port
    self.host = host_port.split(':')[0]
    if url_path and url_path[0] != '/':
      url_path = '/' + url_path
    self.url_path = url_path
    self.kind = kind
    self.throttle = throttle
    self.batch_size = batch_size
    self.secure = secure
    self.authenticated = False
    self.auth_called = False
    self.parallel_download = True
    self.email = email
    self.passin = passin
    throttled_rpc_server_factory = ThrottledHttpRpcServerFactory(
        self.throttle, self)
    logger.debug('Configuring remote_api. url_path = %s, '
                 'servername = %s' % (url_path, host_port))
    remote_api_stub.ConfigureRemoteDatastore(
        app_id,
        url_path,
        self.AuthFunction,
        servername=host_port,
        rpc_server_factory=throttled_rpc_server_factory,
        secure=self.secure)
    logger.debug('Bulkloader using app_id: %s', os.environ['APPLICATION_ID'])

  def Authenticate(self):
    """Invoke authentication if necessary."""
    logger.info('Connecting to %s', self.url_path)
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
    if self.email:
      email = self.email
    else:
      print 'Please enter login credentials for %s' % (
          self.host)
      email = raw_input_fn('Email: ')

    if email:
      password_prompt = 'Password for %s: ' % email
      if self.passin:
        password = raw_input_fn(password_prompt)
      else:
        password = password_input_fn(password_prompt)
    else:
      password = None

    self.auth_called = True
    return (email, password)

  def EncodeContent(self, rows, loader=None):
    """Encodes row data to the wire format.

    Args:
      rows: A list of pairs of a line number and a list of column values.
      loader: Used for dependency injection.

    Returns:
      A list of db.Model instances.

    Raises:
      ConfigurationError: if no loader is defined for self.kind
    """
    if not loader:
      try:
        loader = Loader.RegisteredLoader(self.kind)
      except KeyError:
        logger.error('No Loader defined for kind %s.' % self.kind)
        raise ConfigurationError('No Loader defined for kind %s.' % self.kind)
    entities = []
    for line_number, values in rows:
      key = loader.generate_key(line_number, values)
      if isinstance(key, db.Key):
        parent = key.parent()
        key = key.name()
      else:
        parent = None
      entity = loader.create_entity(values, key_name=key, parent=parent)
      if isinstance(entity, list):
        entities.extend(entity)
      elif entity:
        entities.append(entity)

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

  def GetEntities(self, key_range):
    """Gets Entity records from a remote endpoint over HTTP.

    Args:
     key_range: Range of keys to get.

    Returns:
      An ExportResult instance.

    Raises:
      ConfigurationError: if no Exporter is defined for self.kind
    """
    try:
      Exporter.RegisteredExporter(self.kind)
    except KeyError:
      raise ConfigurationError('No Exporter defined for kind %s.' % self.kind)

    keys = []
    entities = []

    if self.parallel_download:
      query = key_range.MakeParallelQuery()
      try:
        results = query.fetch(self.batch_size)
      except datastore_errors.NeedIndexError:
        logger.info('%s: No descending index on __key__, '
                    'performing serial download', self.kind)
        self.parallel_download = False

    if not self.parallel_download:
      key_range.direction = KeyRange.ASC
      query = key_range.MakeSerialQuery()
      results = query.fetch(self.batch_size)

    size = len(results)

    for model in results:
      key = model.key()
      entities.append(cPickle.dumps(model))
      keys.append(key)

    continued = (size == self.batch_size)
    key_range.count = size

    return ExportResult(continued, key_range.direction, keys, entities)


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

  def __init__(self, enabled,
               threshhold1=MAXIMUM_INCREASE_DURATION,
               threshhold2=MAXIMUM_HOLD_DURATION,
               sleep=InterruptibleSleep):
    """Constructor for ThreadGate instances.

    Args:
      enabled: Whether the thread gate is enabled
      threshhold1: Maximum duration (in seconds) for a transfer to increase
        the number of active threads.
      threshhold2: Maximum duration (in seconds) for a transfer to not decrease
        the number of active threads.
    """
    self.enabled = enabled
    self.enabled_count = 1
    self.lock = threading.Lock()
    self.thread_semaphore = threading.Semaphore(self.enabled_count)
    self._threads = []
    self.backoff_time = 0
    self.sleep = sleep
    self.threshhold1 = threshhold1
    self.threshhold2 = threshhold2

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
    for unused_idx in xrange(len(self._threads) - self.enabled_count):
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
          logger.info('Backing off: %.1f seconds',
                      self.backoff_time)
        self.sleep(self.backoff_time)

  def FinishWork(self):
    """Ends a critical section started with self.StartWork()."""
    if self.enabled:
      self.thread_semaphore.release()

  def TransferSuccess(self, duration):
    """Informs the throttler that an item was successfully sent.

    If thread throttling is enabled and the duration is low enough, this
    method will cause an additional thread to run in the critical section.

    Args:
      duration: The duration of the transfer in seconds.
    """
    if duration > self.threshhold2:
      logger.debug('Transfer took %s, decreasing workers.', duration)
      self.DecreaseWorkers(backoff=False)
      return
    elif duration > self.threshhold1:
      logger.debug('Transfer took %s, not increasing workers.', duration)
      return
    elif self.enabled:
      if self.backoff_time > 0.0:
        logger.info('Resetting backoff to 0.0')
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
        logger.debug('Increasing active thread count to %d',
                     self.enabled_count)
        self.thread_semaphore.release()

  def DecreaseWorkers(self, backoff=True):
    """Informs the thread_gate that an item failed to send.

    If thread throttling is enabled, this method will cause the
    throttler to allow one fewer thread in the critical section. If
    there is only one thread remaining, failures will result in
    exponential backoff until there is a success.

    Args:
      backoff: Whether to increase exponential backoff if there is only
        one thread enabled.
    """
    if self.enabled:
      do_disable = False
      self.lock.acquire()
      try:
        if self.enabled:
          if self.enabled_count > 1:
            do_disable = True
            self.enabled_count -= 1
          elif backoff:
            if self.backoff_time == 0.0:
              self.backoff_time = INITIAL_BACKOFF
            else:
              self.backoff_time *= BACKOFF_FACTOR
      finally:
        self.lock.release()
      if do_disable:
        logger.debug('Decreasing the number of active threads to %d',
                     self.enabled_count)
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

      logger.debug('[%s] Throttling on %s. Sleeping for %.1f ms '
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
    logger.info('[%s] %s: started', self.getName(), self.__class__.__name__)

    try:
      self.PerformWork()
    except:
      self.error = sys.exc_info()[1]
      logger.exception('[%s] %s:', self.getName(), self.__class__.__name__)

    logger.info('[%s] %s: exiting', self.getName(), self.__class__.__name__)

  def PerformWork(self):
    """Perform the thread-specific work."""
    raise NotImplementedError()

  def CheckError(self):
    """If an error is present, then log it."""
    if self.error:
      logger.error('Error in %s: %s', self.GetFriendlyName(), self.error)

  def GetFriendlyName(self):
    """Returns a human-friendly description of the thread."""
    if hasattr(self, 'NAME'):
      return self.NAME
    return 'unknown thread'


non_fatal_error_codes = set([errno.EAGAIN,
                             errno.ENETUNREACH,
                             errno.ENETRESET,
                             errno.ECONNRESET,
                             errno.ETIMEDOUT,
                             errno.EHOSTUNREACH])


def IsURLErrorFatal(error):
  """Returns False if the given URLError may be from a transient failure.

  Args:
    error: A urllib2.URLError instance.
  """
  assert isinstance(error, urllib2.URLError)
  if not hasattr(error, 'reason'):
    return True
  if not isinstance(error.reason[0], int):
    return True
  return error.reason[0] not in non_fatal_error_codes


def PrettyKey(key):
  """Returns a nice string representation of the given key."""
  if key is None:
    return None
  elif isinstance(key, db.Key):
    return repr(key.id_or_name())
  return str(key)


class _BulkWorkerThread(_ThreadBase):
  """A base class for worker threads.

  This thread will read WorkItem instances from the work_queue and upload
  the entities to the server application. Progress information will be
  pushed into the progress_queue as the work is being performed.

  If a _BulkWorkerThread encounters a transient error, the entities will be
  resent, if a fatal error is encoutered the BulkWorkerThread exits.

  Subclasses must provide implementations for PreProcessItem, TransferItem,
  and ProcessResponse.
  """

  def __init__(self,
               work_queue,
               throttle,
               thread_gate,
               request_manager,
               num_threads,
               batch_size,
               state_message,
               get_time):
    """Initialize the BulkLoaderThread instance.

    Args:
      work_queue: A queue containing WorkItems for processing.
      throttle: A Throttles to control upload bandwidth.
      thread_gate: A ThreadGate to control number of simultaneous uploads.
      request_manager: A RequestManager instance.
      num_threads: The number of threads for parallel transfers.
      batch_size: The number of entities to transfer per request.
      state_message: Used for dependency injection.
      get_time: Used for dependency injection.
    """
    _ThreadBase.__init__(self)

    self.work_queue = work_queue
    self.throttle = throttle
    self.thread_gate = thread_gate
    self.request_manager = request_manager
    self.num_threads = num_threads
    self.batch_size = batch_size
    self.state_message = state_message
    self.get_time = get_time

  def PreProcessItem(self, item):
    """Performs pre transfer processing on a work item."""
    raise NotImplementedError()

  def TransferItem(self, item):
    """Transfers the entities associated with an item.

    Args:
      item: An item of upload (WorkItem) or download (KeyRange) work.

    Returns:
      A tuple of (estimated transfer size, response)
    """
    raise NotImplementedError()

  def ProcessResponse(self, item, result):
    """Processes the response from the server application."""
    raise NotImplementedError()

  def PerformWork(self):
    """Perform the work of a _BulkWorkerThread."""
    while not self.exit_flag:
      transferred = False
      self.thread_gate.StartWork()
      try:
        try:
          item = self.work_queue.get(block=True, timeout=1.0)
        except Queue.Empty:
          continue
        if item == _THREAD_SHOULD_EXIT:
          break

        logger.debug('[%s] Got work item %s', self.getName(), item)

        try:

          item.MarkAsTransferring()
          self.PreProcessItem(item)
          response = None
          try:
            try:
              t = self.get_time()
              response = self.TransferItem(item)
              status = 200
              transferred = True
              transfer_time = self.get_time() - t
              logger.debug('[%s] %s Transferred %d entities in %0.1f seconds',
                           self.getName(), item, item.count, transfer_time)
              self.throttle.AddTransfer(RECORDS, item.count)
            except (db.InternalError, db.NotSavedError, db.Timeout,
                    apiproxy_errors.OverQuotaError,
                    apiproxy_errors.DeadlineExceededError), e:
              logger.exception('Caught non-fatal datastore error: %s', e)
            except urllib2.HTTPError, e:
              status = e.code
              if status == 403 or (status >= 500 and status < 600):
                logger.exception('Caught non-fatal HTTP error: %d %s',
                                 status, e.msg)
              else:
                raise e
            except urllib2.URLError, e:
              if IsURLErrorFatal(e):
                raise e
              else:
                logger.exception('Caught non-fatal URL error: %s', e.reason)

            self.ProcessResponse(item, response)

          except:
            self.error = sys.exc_info()[1]
            logger.exception('[%s] %s: caught exception %s', self.getName(),
                             self.__class__.__name__, str(sys.exc_info()))
            raise

        finally:
          if transferred:
            item.MarkAsTransferred()
            self.work_queue.task_done()
            self.thread_gate.TransferSuccess(transfer_time)
          else:
            item.MarkAsError()
            try:
              self.work_queue.reput(item, block=False)
            except Queue.Full:
              logger.error('[%s] Failed to reput work item.', self.getName())
              raise Error('Failed to reput work item')
            self.thread_gate.DecreaseWorkers()
          logger.info('%s %s',
                      item,
                      self.state_message(item.state))

      finally:
        self.thread_gate.FinishWork()


  def GetFriendlyName(self):
    """Returns a human-friendly name for this thread."""
    return 'worker [%s]' % self.getName()


class BulkLoaderThread(_BulkWorkerThread):
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
               request_manager,
               num_threads,
               batch_size,
               get_time=time.time):
    """Initialize the BulkLoaderThread instance.

    Args:
      work_queue: A queue containing WorkItems for processing.
      throttle: A Throttles to control upload bandwidth.
      thread_gate: A ThreadGate to control number of simultaneous uploads.
      request_manager: A RequestManager instance.
      num_threads: The number of threads for parallel transfers.
      batch_size: The number of entities to transfer per request.
      get_time: Used for dependency injection.
    """
    _BulkWorkerThread.__init__(self,
                               work_queue,
                               throttle,
                               thread_gate,
                               request_manager,
                               num_threads,
                               batch_size,
                               ImportStateMessage,
                               get_time)

  def PreProcessItem(self, item):
    """Performs pre transfer processing on a work item."""
    if item and not item.content:
      item.content = self.request_manager.EncodeContent(item.rows)

  def TransferItem(self, item):
    """Transfers the entities associated with an item.

    Args:
      item: An item of upload (WorkItem) work.

    Returns:
      A tuple of (estimated transfer size, response)
    """
    return self.request_manager.PostEntities(item)

  def ProcessResponse(self, item, response):
    """Processes the response from the server application."""
    pass


class BulkExporterThread(_BulkWorkerThread):
  """A thread which recieved entities to the server application.

  This thread will read KeyRange instances from the work_queue and export
  the entities from the server application. Progress information will be
  pushed into the progress_queue as the work is being performed.

  If a BulkExporterThread encounters an error when trying to post data,
  the thread will exit and cause the application to terminate.
  """

  def __init__(self,
               work_queue,
               throttle,
               thread_gate,
               request_manager,
               num_threads,
               batch_size,
               get_time=time.time):

    """Initialize the BulkExporterThread instance.

    Args:
      work_queue: A queue containing KeyRanges for processing.
      throttle: A Throttles to control upload bandwidth.
      thread_gate: A ThreadGate to control number of simultaneous uploads.
      request_manager: A RequestManager instance.
      num_threads: The number of threads for parallel transfers.
      batch_size: The number of entities to transfer per request.
      get_time: Used for dependency injection.
    """
    _BulkWorkerThread.__init__(self,
                               work_queue,
                               throttle,
                               thread_gate,
                               request_manager,
                               num_threads,
                               batch_size,
                               ExportStateMessage,
                               get_time)

  def PreProcessItem(self, unused_item):
    """Performs pre transfer processing on a work item."""
    pass

  def TransferItem(self, item):
    """Transfers the entities associated with an item.

    Args:
      item: An item of download (KeyRange) work.

    Returns:
      A tuple of (estimated transfer size, response)
    """
    return self.request_manager.GetEntities(item)

  def ProcessResponse(self, item, export_result):
    """Processes the response from the server application."""
    if export_result:
      item.Process(export_result, self.num_threads, self.batch_size,
                   self.work_queue)
    item.state = STATE_GOT


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

    self.xfer_count = 0
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
    self.xfer_count = content_gen.xfer_count



def _RunningInThread(thread):
  """Return True if we are running within the specified thread."""
  return threading.currentThread().getName() == thread.getName()


class _Database(object):
  """Base class for database connections in this module.

  The table is created by a primary thread (the python main thread)
  but all future lookups and updates are performed by a secondary
  thread.
  """

  SIGNATURE_TABLE_NAME = 'bulkloader_database_signature'

  def __init__(self,
               db_filename,
               create_table,
               signature,
               index=None,
               commit_periodicity=100):
    """Initialize the _Database instance.

    Args:
      db_filename: The sqlite3 file to use for the database.
      create_table: A string containing the SQL table creation command.
      signature: A string identifying the important invocation options,
        used to make sure we are not using an old database.
      index: An optional string to create an index for the database.
      commit_periodicity: Number of operations between database commits.
    """
    self.db_filename = db_filename

    logger.info('Opening database: %s', db_filename)
    self.primary_conn = sqlite3.connect(db_filename, isolation_level=None)
    self.primary_thread = threading.currentThread()

    self.secondary_conn = None
    self.secondary_thread = None

    self.operation_count = 0
    self.commit_periodicity = commit_periodicity

    try:
      self.primary_conn.execute(create_table)
    except sqlite3.OperationalError, e:
      if 'already exists' not in e.message:
        raise

    if index:
      try:
        self.primary_conn.execute(index)
      except sqlite3.OperationalError, e:
        if 'already exists' not in e.message:
          raise

    self.existing_table = False
    signature_cursor = self.primary_conn.cursor()
    create_signature = """
      create table %s (
      value TEXT not null)
    """ % _Database.SIGNATURE_TABLE_NAME
    try:
      self.primary_conn.execute(create_signature)
      self.primary_conn.cursor().execute(
          'insert into %s (value) values (?)' % _Database.SIGNATURE_TABLE_NAME,
          (signature,))
    except sqlite3.OperationalError, e:
      if 'already exists' not in e.message:
        logger.exception('Exception creating table:')
        raise
      else:
        self.existing_table = True
        signature_cursor.execute(
            'select * from %s' % _Database.SIGNATURE_TABLE_NAME)
        (result,) = signature_cursor.fetchone()
        if result and result != signature:
          logger.error('Database signature mismatch:\n\n'
                       'Found:\n'
                       '%s\n\n'
                       'Expecting:\n'
                       '%s\n',
                       result, signature)
          raise ResumeError('Database signature mismatch: %s != %s' % (
                            signature, result))

  def ThreadComplete(self):
    """Finalize any operations the secondary thread has performed.

    The database aggregates lots of operations into a single commit, and
    this method is used to commit any pending operations as the thread
    is about to shut down.
    """
    if self.secondary_conn:
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
      self.secondary_conn.commit()

  def _OpenSecondaryConnection(self):
    """Possibly open a database connection for the secondary thread.

    If the connection is not open (for the calling thread, which is assumed
    to be the unique secondary thread), then open it. We also open a couple
    cursors for later use (and reuse).
    """
    if self.secondary_conn:
      return

    assert not _RunningInThread(self.primary_thread)

    self.secondary_thread = threading.currentThread()

    self.secondary_conn = sqlite3.connect(self.db_filename)

    self.insert_cursor = self.secondary_conn.cursor()
    self.update_cursor = self.secondary_conn.cursor()


class ResultDatabase(_Database):
  """Persistently record all the entities downloaded during an export.

  The entities are held in the database by their unique datastore key
  in order to avoid duplication if an export is restarted.
  """

  def __init__(self, db_filename, signature, commit_periodicity=1):
    """Initialize a ResultDatabase object.

    Args:
      db_filename: The name of the SQLite database to use.
      signature: A string identifying the important invocation options,
        used to make sure we are not using an old database.
      commit_periodicity: How many operations to perform between commits.
    """
    self.complete = False
    create_table = ('create table result (\n'
                    'id TEXT primary key,\n'
                    'value BLOB not null)')

    _Database.__init__(self,
                       db_filename,
                       create_table,
                       signature,
                       commit_periodicity=commit_periodicity)
    if self.existing_table:
      cursor = self.primary_conn.cursor()
      cursor.execute('select count(*) from result')
      self.existing_count = int(cursor.fetchone()[0])
    else:
      self.existing_count = 0
    self.count = self.existing_count

  def _StoreEntity(self, entity_id, value):
    """Store an entity in the result database.

    Args:
      entity_id: A db.Key for the entity.
      value: A string of the contents of the entity.

    Returns:
      True if this entities is not already present in the result database.
    """

    assert _RunningInThread(self.secondary_thread)
    assert isinstance(entity_id, db.Key)

    entity_id = entity_id.id_or_name()
    self.insert_cursor.execute(
        'select count(*) from result where id = ?', (unicode(entity_id),))
    already_present = self.insert_cursor.fetchone()[0]
    result = True
    if already_present:
      result = False
      self.insert_cursor.execute('delete from result where id = ?',
                                 (unicode(entity_id),))
    else:
      self.count += 1
    self.insert_cursor.execute(
        'insert into result (id, value) values (?, ?)',
        (unicode(entity_id), buffer(value)))
    return result

  def StoreEntities(self, keys, entities):
    """Store a group of entities in the result database.

    Args:
      keys: A list of entity keys.
      entities: A list of entities.

    Returns:
      The number of new entities stored in the result database.
    """
    self._OpenSecondaryConnection()
    t = time.time()
    count = 0
    for entity_id, value in zip(keys,
                                entities):
      if self._StoreEntity(entity_id, value):
        count += 1
    logger.debug('%s insert: delta=%.3f',
                 self.db_filename,
                 time.time() - t)
    logger.debug('Entities transferred total: %s', self.count)
    self._MaybeCommit()
    return count

  def ResultsComplete(self):
    """Marks the result database as containing complete results."""
    self.complete = True

  def AllEntities(self):
    """Yields all pairs of (id, value) from the result table."""
    conn = sqlite3.connect(self.db_filename, isolation_level=None)
    cursor = conn.cursor()

    cursor.execute(
        'select id, value from result order by id')

    for unused_entity_id, entity in cursor:
      yield cPickle.loads(str(entity))


class _ProgressDatabase(_Database):
  """Persistently record all progress information during an upload.

  This class wraps a very simple SQLite database which records each of
  the relevant details from a chunk of work. If the loader is
  resumed, then data is replayed out of the database.
  """

  def __init__(self,
               db_filename,
               sql_type,
               py_type,
               signature,
               commit_periodicity=100):
    """Initialize the ProgressDatabase instance.

    Args:
      db_filename: The name of the SQLite database to use.
      sql_type: A string of the SQL type to use for entity keys.
      py_type: The python type of entity keys.
      signature: A string identifying the important invocation options,
        used to make sure we are not using an old database.
      commit_periodicity: How many operations to perform between commits.
    """
    self.prior_key_end = None

    create_table = ('create table progress (\n'
                    'id integer primary key autoincrement,\n'
                    'state integer not null,\n'
                    'key_start %s,\n'
                    'key_end %s)'
                    % (sql_type, sql_type))
    self.py_type = py_type

    index = 'create index i_state on progress (state)'
    _Database.__init__(self,
                       db_filename,
                       create_table,
                       signature,
                       index=index,
                       commit_periodicity=commit_periodicity)

  def UseProgressData(self):
    """Returns True if the database has progress information.

    Note there are two basic cases for progress information:
    1) All saved records indicate a successful upload. In this case, we
       need to skip everything transmitted so far and then send the rest.
    2) Some records for incomplete transfer are present. These need to be
       sent again, and then we resume sending after all the successful
       data.

    Returns:
      True: if the database has progress information.

    Raises:
      ResumeError: if there is an error retrieving rows from the database.
    """
    assert _RunningInThread(self.primary_thread)

    cursor = self.primary_conn.cursor()
    cursor.execute('select count(*) from progress')
    row = cursor.fetchone()
    if row is None:
      raise ResumeError('Cannot retrieve progress information from database.')

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
    self._OpenSecondaryConnection()

    assert _RunningInThread(self.secondary_thread)
    assert not key_start or isinstance(key_start, self.py_type)
    assert not key_end or isinstance(key_end, self.py_type), '%s is a %s' % (
        key_end, key_end.__class__)
    assert KeyLEQ(key_start, key_end), '%s not less than %s' % (
        repr(key_start), repr(key_end))

    self.insert_cursor.execute(
        'insert into progress (state, key_start, key_end) values (?, ?, ?)',
        (STATE_READ, unicode(key_start), unicode(key_end)))

    progress_key = self.insert_cursor.lastrowid

    self._MaybeCommit()

    return progress_key

  def UpdateState(self, key, new_state):
    """Update a specified progress record with new information.

    Args:
      key: The key for this progress record, returned from StoreKeys
      new_state: The new state to associate with this progress record.
    """
    self._OpenSecondaryConnection()

    assert _RunningInThread(self.secondary_thread)
    assert isinstance(new_state, int)

    self.update_cursor.execute('update progress set state=? where id=?',
                               (new_state, key))

    self._MaybeCommit()

  def DeleteKey(self, progress_key):
    """Delete the entities with the given key from the result database."""
    self._OpenSecondaryConnection()

    assert _RunningInThread(self.secondary_thread)

    t = time.time()
    self.insert_cursor.execute(
        'delete from progress where rowid = ?', (progress_key,))

    logger.debug('delete: delta=%.3f', time.time() - t)

    self._MaybeCommit()

  def GetProgressStatusGenerator(self):
    """Get a generator which yields progress information.

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
      Four-tuples of (progress_key, state, key_start, key_end)
    """
    conn = sqlite3.connect(self.db_filename, isolation_level=None)
    cursor = conn.cursor()

    cursor.execute('select max(key_end) from progress')

    result = cursor.fetchone()
    if result is not None:
      key_end = result[0]
    else:
      logger.debug('No rows in progress database.')
      return

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
      progress_key, state, key_start, key_end = row

      yield progress_key, state, key_start, key_end

    yield None, DATA_CONSUMED_TO_HERE, None, key_end


def ProgressDatabase(db_filename, signature):
  """Returns a database to store upload progress information."""
  return _ProgressDatabase(db_filename, 'INTEGER', int, signature)


class ExportProgressDatabase(_ProgressDatabase):
  """A database to store download progress information."""

  def __init__(self, db_filename, signature):
    """Initialize an ExportProgressDatabase."""
    _ProgressDatabase.__init__(self,
                               db_filename,
                               'TEXT',
                               db.Key,
                               signature,
                               commit_periodicity=1)

  def UseProgressData(self):
    """Check if the progress database contains progress data.

    Returns:
      True: if the database contains progress data.
    """
    return self.existing_table


class StubProgressDatabase(object):
  """A stub implementation of ProgressDatabase which does nothing."""

  def UseProgressData(self):
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


class _ProgressThreadBase(_ThreadBase):
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
    self.entities_transferred = 0

  def EntitiesTransferred(self):
    """Return the total number of unique entities transferred."""
    return self.entities_transferred

  def UpdateProgress(self, item):
    """Updates the progress information for the given item.

    Args:
      item: A work item whose new state will be recorded
    """
    raise NotImplementedError()

  def WorkFinished(self):
    """Performs final actions after the entity transfer is complete."""
    raise NotImplementedError()

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
        self.UpdateProgress(item)

      item.progress_event.set()

      self.progress_queue.task_done()

    self.db.ThreadComplete()



class ProgressTrackerThread(_ProgressThreadBase):
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
    _ProgressThreadBase.__init__(self, progress_queue, progress_db)

  def UpdateProgress(self, item):
    """Update the state of the given WorkItem.

    Args:
      item: A WorkItem instance.
    """
    self.db.UpdateState(item.progress_key, item.state)
    if item.state == STATE_SENT:
      self.entities_transferred += item.count

  def WorkFinished(self):
    """Performs final actions after the entity transfer is complete."""
    pass


class ExportProgressThread(_ProgressThreadBase):
  """A thread to record progress information and write record data for exports.

  The progress information is stored into a provided progress database.
  Exported results are stored in the result database and dumped to an output
  file at the end of the download.
  """

  def __init__(self, kind, progress_queue, progress_db, result_db):
    """Initialize the ExportProgressThread instance.

    Args:
      kind: The kind of entities being stored in the database.
      progress_queue: A Queue used for tracking progress information.
      progress_db: The database for tracking progress information; should
        be an instance of ProgressDatabase.
      result_db: The database for holding exported entities; should be an
        instance of ResultDatabase.
    """
    _ProgressThreadBase.__init__(self, progress_queue, progress_db)

    self.kind = kind
    self.existing_count = result_db.existing_count
    self.result_db = result_db

  def EntitiesTransferred(self):
    """Return the total number of unique entities transferred."""
    return self.result_db.count

  def WorkFinished(self):
    """Write the contents of the result database."""
    exporter = Exporter.RegisteredExporter(self.kind)
    exporter.output_entities(self.result_db.AllEntities())

  def UpdateProgress(self, item):
    """Update the state of the given KeyRange.

    Args:
      item: A KeyRange instance.
    """
    if item.state == STATE_GOT:
      count = self.result_db.StoreEntities(item.export_result.keys,
                                           item.export_result.entities)
      self.db.DeleteKey(item.progress_key)
      self.entities_transferred += count
    else:
      self.db.UpdateState(item.progress_key, item.state)


def ParseKey(key_string):
  """Turn a key stored in the database into a db.Key or None.

  Args:
    key_string: The string representation of a db.Key.

  Returns:
    A db.Key instance or None
  """
  if not key_string:
    return None
  if key_string == 'None':
    return None
  return db.Key(encoded=key_string)


def Validate(value, typ):
  """Checks that value is non-empty and of the right type.

  Args:
    value: any value
    typ: a type or tuple of types

  Raises:
    ValueError: if value is None or empty.
    TypeError: if it's not the given type.
  """
  if not value:
    raise ValueError('Value should not be empty; received %s.' % value)
  elif not isinstance(value, typ):
    raise TypeError('Expected a %s, but received %s (a %s).' %
                    (typ, value, value.__class__))


def CheckFile(filename):
  """Check that the given file exists and can be opened for reading.

  Args:
    filename: The name of the file.

  Raises:
    FileNotFoundError: if the given filename is not found
    FileNotReadableError: if the given filename is not readable.
  """
  if not os.path.exists(filename):
    raise FileNotFoundError('%s: file not found' % filename)
  elif not os.access(filename, os.R_OK):
    raise FileNotReadableError('%s: file not readable' % filename)


class Loader(object):
  """A base class for creating datastore entities from input data.

  To add a handler for bulk loading a new entity kind into your datastore,
  write a subclass of this class that calls Loader.__init__ from your
  class's __init__.

  If you need to run extra code to convert entities from the input
  data, create new properties, or otherwise modify the entities before
  they're inserted, override handle_entity.

  See the create_entity method for the creation of entities from the
  (parsed) input data.
  """

  __loaders = {}
  kind = None
  __properties = None

  def __init__(self, kind, properties):
    """Constructor.

    Populates this Loader's kind and properties map. Also registers it with
    the bulk loader, so that all you need to do is instantiate your Loader,
    and the bulkload handler will automatically use it.

    Args:
      kind: a string containing the entity kind that this loader handles

      properties: list of (name, converter) tuples.

        This is used to automatically convert the input columns into
        properties.  The converter should be a function that takes one
        argument, a string value from the input file, and returns a
        correctly typed property value that should be inserted. The
        tuples in this list should match the columns in your input file,
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
    Validate(kind, (basestring, tuple))
    self.kind = kind
    self.__openfile = open
    self.__create_csv_reader = csv.reader

    GetImplementationClass(kind)

    Validate(properties, list)
    for name, fn in properties:
      Validate(name, basestring)
      assert callable(fn), (
        'Conversion function %s for property %s is not callable.' % (fn, name))

    self.__properties = properties

  @staticmethod
  def RegisterLoader(loader):

    Loader.__loaders[loader.kind] = loader

  def alias_old_names(self):
    """Aliases method names so that Loaders defined with old names work."""
    aliases = (
        ('CreateEntity', 'create_entity'),
        ('HandleEntity', 'handle_entity'),
        ('GenerateKey', 'generate_key'),
        )
    for old_name, new_name in aliases:
      setattr(Loader, old_name, getattr(Loader, new_name))
      if hasattr(self.__class__, old_name) and not (
          getattr(self.__class__, old_name).im_func ==
          getattr(Loader, new_name).im_func):
        if hasattr(self.__class__, new_name) and not (
            getattr(self.__class__, new_name).im_func ==
            getattr(Loader, new_name).im_func):
          raise NameClashError(old_name, new_name, self.__class__)
        setattr(self, new_name, getattr(self, old_name))

  def create_entity(self, values, key_name=None, parent=None):
    """Creates a entity from a list of property values.

    Args:
      values: list/tuple of str
      key_name: if provided, the name for the (single) resulting entity
      parent: A db.Key instance for the parent, or None

    Returns:
      list of db.Model

      The returned entities are populated with the property values from the
      argument, converted to native types using the properties map given in
      the constructor, and passed through handle_entity. They're ready to be
      inserted.

    Raises:
      AssertionError: if the number of values doesn't match the number
        of properties in the properties map.
      ValueError: if any element of values is None or empty.
      TypeError: if values is not a list or tuple.
    """
    Validate(values, (list, tuple))
    assert len(values) == len(self.__properties), (
        'Expected %d columns, found %d.' %
        (len(self.__properties), len(values)))

    model_class = GetImplementationClass(self.kind)

    properties = {
        'key_name': key_name,
        'parent': parent,
        }
    for (name, converter), val in zip(self.__properties, values):
      if converter is bool and val.lower() in ('0', 'false', 'no'):
        val = False
      properties[name] = converter(val)

    entity = model_class(**properties)
    entities = self.handle_entity(entity)

    if entities:
      if not isinstance(entities, (list, tuple)):
        entities = [entities]

      for entity in entities:
        if not isinstance(entity, db.Model):
          raise TypeError('Expected a db.Model, received %s (a %s).' %
                          (entity, entity.__class__))

    return entities

  def generate_key(self, i, values):
    """Generates a key_name to be used in creating the underlying object.

    The default implementation returns None.

    This method can be overridden to control the key generation for
    uploaded entities. The value returned should be None (to use a
    server generated numeric key), or a string which neither starts
    with a digit nor has the form __*__ (see
    http://code.google.com/appengine/docs/python/datastore/keysandentitygroups.html),
    or a db.Key instance.

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

  def handle_entity(self, entity):
    """Subclasses can override this to add custom entity conversion code.

    This is called for each entity, after its properties are populated
    from the input but before it is stored. Subclasses can override
    this to add custom entity handling code.

    The entity to be inserted should be returned. If multiple entities
    should be inserted, return a list of entities. If no entities
    should be inserted, return None or [].

    Args:
      entity: db.Model

    Returns:
      db.Model or list of db.Model
    """
    return entity

  def initialize(self, filename, loader_opts):
    """Performs initialization and validation of the input file.

    This implementation checks that the input file exists and can be
    opened for reading.

    Args:
      filename: The string given as the --filename flag argument.
      loader_opts: The string given as the --loader_opts flag argument.
    """
    CheckFile(filename)

  def finalize(self):
    """Performs finalization actions after the upload completes."""
    pass

  def generate_records(self, filename):
    """Subclasses can override this to add custom data input code.

    This method must yield fixed-length lists of strings.

    The default implementation uses csv.reader to read CSV rows
    from filename.

    Args:
      filename: The string input for the --filename option.

    Yields:
      Lists of strings.
    """
    csv_generator = CSVGenerator(filename, openfile=self.__openfile,
                                 create_csv_reader=self.__create_csv_reader
                                ).Records()
    return csv_generator

  @staticmethod
  def RegisteredLoaders():
    """Returns a dict of the Loader instances that have been created."""
    return dict(Loader.__loaders)

  @staticmethod
  def RegisteredLoader(kind):
    """Returns the loader instance for the given kind if it exists."""
    return Loader.__loaders[kind]


class Exporter(object):
  """A base class for serializing datastore entities.

  To add a handler for exporting an entity kind from your datastore,
  write a subclass of this class that calls Exporter.__init__ from your
  class's __init__.

  If you need to run extra code to convert entities from the input
  data, create new properties, or otherwise modify the entities before
  they're inserted, override handle_entity.

  See the output_entities method for the writing of data from entities.
  """

  __exporters = {}
  kind = None
  __properties = None

  def __init__(self, kind, properties):
    """Constructor.

    Populates this Exporters's kind and properties map. Also registers
    it so that all you need to do is instantiate your Exporter, and
    the bulkload handler will automatically use it.

    Args:
      kind: a string containing the entity kind that this exporter handles

      properties: list of (name, converter, default) tuples.

      This is used to automatically convert the entities to strings.
      The converter should be a function that takes one argument, a property
      value of the appropriate type, and returns a str or unicode.  The default
      is a string to be used if the property is not present, or None to fail
      with an error if the property is missing.

      For example:
        [('name', str, None),
         ('id_number', str, None),
         ('email', str, ''),
         ('user', str, None),
         ('birthdate',
          lambda x: str(datetime.datetime.fromtimestamp(float(x))),
          None),
         ('description', str, ''),
         ]
    """
    Validate(kind, basestring)
    self.kind = kind

    GetImplementationClass(kind)

    Validate(properties, list)
    for name, fn, default in properties:
      Validate(name, basestring)
      assert callable(fn), (
          'Conversion function %s for property %s is not callable.' % (
              fn, name))
      if default:
        Validate(default, basestring)

    self.__properties = properties

  @staticmethod
  def RegisterExporter(exporter):

    Exporter.__exporters[exporter.kind] = exporter

  def __ExtractProperties(self, entity):
    """Converts an entity into a list of string values.

    Args:
      entity: An entity to extract the properties from.

    Returns:
      A list of the properties of the entity.

    Raises:
      MissingPropertyError: if an expected field on the entity is missing.
    """
    encoding = []
    for name, fn, default in self.__properties:
      try:
        encoding.append(fn(getattr(entity, name)))
      except AttributeError:
        if default is None:
          raise MissingPropertyError(name)
        else:
          encoding.append(default)
    return encoding

  def __EncodeEntity(self, entity):
    """Convert the given entity into CSV string.

    Args:
      entity: The entity to encode.

    Returns:
      A CSV string.
    """
    output = StringIO.StringIO()
    writer = csv.writer(output, lineterminator='')
    writer.writerow(self.__ExtractProperties(entity))
    return output.getvalue()

  def __SerializeEntity(self, entity):
    """Creates a string representation of an entity.

    Args:
      entity: The entity to serialize.

    Returns:
      A serialized representation of an entity.
    """
    encoding = self.__EncodeEntity(entity)
    if not isinstance(encoding, unicode):
      encoding = unicode(encoding, 'utf-8')
    encoding = encoding.encode('utf-8')
    return encoding

  def output_entities(self, entity_generator):
    """Outputs the downloaded entities.

    This implementation writes CSV.

    Args:
      entity_generator: A generator that yields the downloaded entities
        in key order.
    """
    CheckOutputFile(self.output_filename)
    output_file = open(self.output_filename, 'w')
    logger.debug('Export complete, writing to file')
    output_file.writelines(self.__SerializeEntity(entity) + '\n'
                           for entity in entity_generator)

  def initialize(self, filename, exporter_opts):
    """Performs initialization and validation of the output file.

    This implementation checks that the input file exists and can be
    opened for writing.

    Args:
      filename: The string given as the --filename flag argument.
      exporter_opts: The string given as the --exporter_opts flag argument.
    """
    CheckOutputFile(filename)
    self.output_filename = filename

  def finalize(self):
    """Performs finalization actions after the download completes."""
    pass

  @staticmethod
  def RegisteredExporters():
    """Returns a dictionary of the exporter instances that have been created."""
    return dict(Exporter.__exporters)

  @staticmethod
  def RegisteredExporter(kind):
    """Returns an exporter instance for the given kind if it exists."""
    return Exporter.__exporters[kind]


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
                           queue_join_thread_factory=QueueJoinThread,
                           check_workers=True):
  """Repeatedly joins the given ReQueue or Queue.Queue with short timeout.

  Between each timeout on the join, worker threads are checked.

  Args:
    queue: A Queue.Queue or ReQueue instance.
    thread_local: A threading.local instance which indicates interrupts.
    thread_gate: A ThreadGate instance.
    queue_join_thread_factory: Used for dependency injection.
    check_workers: Whether to interrupt the join on worker death.

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
      logger.debug('Queue join interrupted')
      return False
    if check_workers:
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
  logger.info('An error occurred. Shutting down...')

  data_source_thread.exit_flag = True

  for thread in thread_gate.Threads():
    thread.exit_flag = True

  for unused_thread in thread_gate.Threads():
    thread_gate.EnableThread()

  data_source_thread.join(timeout=3.0)
  if data_source_thread.isAlive():
    logger.warn('%s hung while trying to exit',
                data_source_thread.GetFriendlyName())

  while not work_queue.empty():
    try:
      unused_item = work_queue.get_nowait()
      work_queue.task_done()
    except Queue.Empty:
      pass


class BulkTransporterApp(object):
  """Class to wrap bulk transport application functionality."""

  def __init__(self,
               arg_dict,
               input_generator_factory,
               throttle,
               progress_db,
               workerthread_factory,
               progresstrackerthread_factory,
               max_queue_size=DEFAULT_QUEUE_SIZE,
               request_manager_factory=RequestManager,
               datasourcethread_factory=DataSourceThread,
               work_queue_factory=ReQueue,
               progress_queue_factory=Queue.Queue):
    """Instantiate a BulkTransporterApp.

    Uploads or downloads data to or from application using HTTP requests.
    When run, the class will spin up a number of threads to read entities
    from the data source, pass those to a number of worker threads
    for sending to the application, and track all of the progress in a
    small database in case an error or pause/termination requires a
    restart/resumption of the upload process.

    Args:
      arg_dict: Dictionary of command line options.
      input_generator_factory: A factory that creates a WorkItem generator.
      throttle: A Throttle instance.
      progress_db: The database to use for replaying/recording progress.
      workerthread_factory: A factory for worker threads.
      progresstrackerthread_factory: Used for dependency injection.
      max_queue_size: Maximum size of the queues before they should block.
      request_manager_factory: Used for dependency injection.
      datasourcethread_factory: Used for dependency injection.
      work_queue_factory: Used for dependency injection.
      progress_queue_factory: Used for dependency injection.
    """
    self.app_id = arg_dict['app_id']
    self.post_url = arg_dict['url']
    self.kind = arg_dict['kind']
    self.batch_size = arg_dict['batch_size']
    self.input_generator_factory = input_generator_factory
    self.num_threads = arg_dict['num_threads']
    self.email = arg_dict['email']
    self.passin = arg_dict['passin']
    self.throttle = throttle
    self.progress_db = progress_db
    self.workerthread_factory = workerthread_factory
    self.progresstrackerthread_factory = progresstrackerthread_factory
    self.max_queue_size = max_queue_size
    self.request_manager_factory = request_manager_factory
    self.datasourcethread_factory = datasourcethread_factory
    self.work_queue_factory = work_queue_factory
    self.progress_queue_factory = progress_queue_factory
    (scheme,
     self.host_port, self.url_path,
     unused_query, unused_fragment) = urlparse.urlsplit(self.post_url)
    self.secure = (scheme == 'https')

  def Run(self):
    """Perform the work of the BulkTransporterApp.

    Raises:
      AuthenticationError: If authentication is required and fails.

    Returns:
      Error code suitable for sys.exit, e.g. 0 on success, 1 on failure.
    """
    thread_gate = ThreadGate(True)

    self.throttle.Register(threading.currentThread())
    threading.currentThread().exit_flag = False

    work_queue = self.work_queue_factory(self.max_queue_size)

    progress_queue = self.progress_queue_factory(self.max_queue_size)
    request_manager = self.request_manager_factory(self.app_id,
                                                   self.host_port,
                                                   self.url_path,
                                                   self.kind,
                                                   self.throttle,
                                                   self.batch_size,
                                                   self.secure,
                                                   self.email,
                                                   self.passin)
    try:
      request_manager.Authenticate()
    except Exception, e:
      if not isinstance(e, urllib2.HTTPError) or (
          e.code != 302 and e.code != 401):
        logger.exception('Exception during authentication')
      raise AuthenticationError()
    if (request_manager.auth_called and
        not request_manager.authenticated):
      raise AuthenticationError('Authentication failed')

    for unused_idx in xrange(self.num_threads):
      thread = self.workerthread_factory(work_queue,
                                         self.throttle,
                                         thread_gate,
                                         request_manager,
                                         self.num_threads,
                                         self.batch_size)
      self.throttle.Register(thread)
      thread_gate.Register(thread)

    self.progress_thread = self.progresstrackerthread_factory(
        progress_queue, self.progress_db)

    if self.progress_db.UseProgressData():
      logger.debug('Restarting upload using progress database')
      progress_generator_factory = self.progress_db.GetProgressStatusGenerator
    else:
      progress_generator_factory = None

    self.data_source_thread = (
        self.datasourcethread_factory(work_queue,
                                      progress_queue,
                                      self.input_generator_factory,
                                      progress_generator_factory))

    thread_local = threading.local()
    thread_local.shut_down = False

    def Interrupt(unused_signum, unused_frame):
      """Shutdown gracefully in response to a signal."""
      thread_local.shut_down = True

    signal.signal(signal.SIGINT, Interrupt)

    self.progress_thread.start()
    self.data_source_thread.start()
    for thread in thread_gate.Threads():
      thread.start()


    while not thread_local.shut_down:
      self.data_source_thread.join(timeout=0.25)

      if self.data_source_thread.isAlive():
        for thread in list(thread_gate.Threads()) + [self.progress_thread]:
          if not thread.isAlive():
            logger.info('Unexpected thread death: %s', thread.getName())
            thread_local.shut_down = True
            break
      else:
        break

    if thread_local.shut_down:
      ShutdownThreads(self.data_source_thread, work_queue, thread_gate)

    def _Join(ob, msg):
      logger.debug('Waiting for %s...', msg)
      if isinstance(ob, threading.Thread):
        ob.join(timeout=3.0)
        if ob.isAlive():
          logger.debug('Joining %s failed', ob.GetFriendlyName())
        else:
          logger.debug('... done.')
      elif isinstance(ob, (Queue.Queue, ReQueue)):
        if not InterruptibleQueueJoin(ob, thread_local, thread_gate):
          ShutdownThreads(self.data_source_thread, work_queue, thread_gate)
      else:
        ob.join()
        logger.debug('... done.')

    _Join(work_queue, 'work_queue to flush')

    for unused_thread in thread_gate.Threads():
      work_queue.put(_THREAD_SHOULD_EXIT)

    for unused_thread in thread_gate.Threads():
      thread_gate.EnableThread()

    for thread in thread_gate.Threads():
      _Join(thread, 'thread [%s] to terminate' % thread.getName())

      thread.CheckError()

    if self.progress_thread.isAlive():
      InterruptibleQueueJoin(progress_queue, thread_local, thread_gate,
                             check_workers=False)
    else:
      logger.warn('Progress thread exited prematurely')

    progress_queue.put(_THREAD_SHOULD_EXIT)
    _Join(self.progress_thread, 'progress_thread to terminate')
    self.progress_thread.CheckError()
    if not thread_local.shut_down:
      self.progress_thread.WorkFinished()

    self.data_source_thread.CheckError()

    return self.ReportStatus()

  def ReportStatus(self):
    """Display a message reporting the final status of the transfer."""
    raise NotImplementedError()


class BulkUploaderApp(BulkTransporterApp):
  """Class to encapsulate bulk uploader functionality."""

  def __init__(self, *args, **kwargs):
    BulkTransporterApp.__init__(self, *args, **kwargs)

  def ReportStatus(self):
    """Display a message reporting the final status of the transfer."""
    total_up, duration = self.throttle.TotalTransferred(BANDWIDTH_UP)
    s_total_up, unused_duration = self.throttle.TotalTransferred(
        HTTPS_BANDWIDTH_UP)
    total_up += s_total_up
    total = total_up
    logger.info('%d entites total, %d previously transferred',
                self.data_source_thread.read_count,
                self.data_source_thread.xfer_count)
    transfer_count = self.progress_thread.EntitiesTransferred()
    logger.info('%d entities (%d bytes) transferred in %.1f seconds',
                transfer_count, total, duration)
    if (self.data_source_thread.read_all and
        transfer_count +
        self.data_source_thread.xfer_count >=
        self.data_source_thread.read_count):
      logger.info('All entities successfully transferred')
      return 0
    else:
      logger.info('Some entities not successfully transferred')
      return 1


class BulkDownloaderApp(BulkTransporterApp):
  """Class to encapsulate bulk downloader functionality."""

  def __init__(self, *args, **kwargs):
    BulkTransporterApp.__init__(self, *args, **kwargs)

  def ReportStatus(self):
    """Display a message reporting the final status of the transfer."""
    total_down, duration = self.throttle.TotalTransferred(BANDWIDTH_DOWN)
    s_total_down, unused_duration = self.throttle.TotalTransferred(
        HTTPS_BANDWIDTH_DOWN)
    total_down += s_total_down
    total = total_down
    existing_count = self.progress_thread.existing_count
    xfer_count = self.progress_thread.EntitiesTransferred()
    logger.info('Have %d entities, %d previously transferred',
                xfer_count + existing_count, existing_count)
    logger.info('%d entities (%d bytes) transferred in %.1f seconds',
                xfer_count, total, duration)
    return 0


def PrintUsageExit(code):
  """Prints usage information and exits with a status code.

  Args:
    code: Status code to pass to sys.exit() after displaying usage information.
  """
  print __doc__ % {'arg0': sys.argv[0]}
  sys.stdout.flush()
  sys.stderr.flush()
  sys.exit(code)


REQUIRED_OPTION = object()


FLAG_SPEC = ['debug',
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
             'has_header',
             'csv_has_header',
             'auth_domain=',
             'result_db_filename=',
             'download',
             'loader_opts=',
             'exporter_opts=',
             'log_file=',
             'email=',
             'passin',
             ]


def ParseArguments(argv):
  """Parses command-line arguments.

  Prints out a help message if -h or --help is supplied.

  Args:
    argv: List of command-line arguments.

  Returns:
    A dictionary containing the value of command-line options.
  """
  opts, unused_args = getopt.getopt(
      argv[1:],
      'h',
      FLAG_SPEC)

  arg_dict = {}

  arg_dict['url'] = REQUIRED_OPTION
  arg_dict['filename'] = REQUIRED_OPTION
  arg_dict['config_file'] = REQUIRED_OPTION
  arg_dict['kind'] = REQUIRED_OPTION

  arg_dict['batch_size'] = DEFAULT_BATCH_SIZE
  arg_dict['num_threads'] = DEFAULT_THREAD_COUNT
  arg_dict['bandwidth_limit'] = DEFAULT_BANDWIDTH_LIMIT
  arg_dict['rps_limit'] = DEFAULT_RPS_LIMIT
  arg_dict['http_limit'] = DEFAULT_REQUEST_LIMIT

  arg_dict['db_filename'] = None
  arg_dict['app_id'] = ''
  arg_dict['auth_domain'] = 'gmail.com'
  arg_dict['has_header'] = False
  arg_dict['result_db_filename'] = None
  arg_dict['download'] = False
  arg_dict['loader_opts'] = None
  arg_dict['exporter_opts'] = None
  arg_dict['debug'] = False
  arg_dict['log_file'] = None
  arg_dict['email'] = None
  arg_dict['passin'] = False

  def ExpandFilename(filename):
    """Expand shell variables and ~usernames in filename."""
    return os.path.expandvars(os.path.expanduser(filename))

  for option, value in opts:
    if option == '--debug':
      arg_dict['debug'] = True
    elif option in ('-h', '--help'):
      PrintUsageExit(0)
    elif option == '--url':
      arg_dict['url'] = value
    elif option == '--filename':
      arg_dict['filename'] = ExpandFilename(value)
    elif option == '--batch_size':
      arg_dict['batch_size'] = int(value)
    elif option == '--kind':
      arg_dict['kind'] = value
    elif option == '--num_threads':
      arg_dict['num_threads'] = int(value)
    elif option == '--bandwidth_limit':
      arg_dict['bandwidth_limit'] = int(value)
    elif option == '--rps_limit':
      arg_dict['rps_limit'] = int(value)
    elif option == '--http_limit':
      arg_dict['http_limit'] = int(value)
    elif option == '--db_filename':
      arg_dict['db_filename'] = ExpandFilename(value)
    elif option == '--app_id':
      arg_dict['app_id'] = value
    elif option == '--config_file':
      arg_dict['config_file'] = ExpandFilename(value)
    elif option == '--auth_domain':
      arg_dict['auth_domain'] = value
    elif option == '--has_header':
      arg_dict['has_header'] = True
    elif option == '--csv_has_header':
      print >>sys.stderr, ('--csv_has_header is deprecated, please use '
                           '--has_header.')
      arg_dict['has_header'] = True
    elif option == '--result_db_filename':
      arg_dict['result_db_filename'] = ExpandFilename(value)
    elif option == '--download':
      arg_dict['download'] = True
    elif option == '--loader_opts':
      arg_dict['loader_opts'] = value
    elif option == '--exporter_opts':
      arg_dict['exporter_opts'] = value
    elif option == '--log_file':
      arg_dict['log_file'] = value
    elif option == '--email':
      arg_dict['email'] = value
    elif option == '--passin':
      arg_dict['passin'] = True

  return ProcessArguments(arg_dict, die_fn=lambda: PrintUsageExit(1))


def ThrottleLayout(bandwidth_limit, http_limit, rps_limit):
  """Return a dictionary indicating the throttle options."""
  return {
      BANDWIDTH_UP: bandwidth_limit,
      BANDWIDTH_DOWN: bandwidth_limit,
      REQUESTS: http_limit,
      HTTPS_BANDWIDTH_UP: bandwidth_limit / 5,
      HTTPS_BANDWIDTH_DOWN: bandwidth_limit / 5,
      HTTPS_REQUESTS: http_limit / 5,
      RECORDS: rps_limit,
  }


def CheckOutputFile(filename):
  """Check that the given file does not exist and can be opened for writing.

  Args:
    filename: The name of the file.

  Raises:
    FileExistsError: if the given filename is not found
    FileNotWritableError: if the given filename is not readable.
  """
  if os.path.exists(filename):
    raise FileExistsError('%s: output file exists' % filename)
  elif not os.access(os.path.dirname(filename), os.W_OK):
    raise FileNotWritableError(
        '%s: not writable' % os.path.dirname(filename))


def LoadConfig(config_file_name, exit_fn=sys.exit):
  """Loads a config file and registers any Loader classes present.

  Args:
    config_file_name: The name of the configuration file.
    exit_fn: Used for dependency injection.
  """
  if config_file_name:
    config_file = open(config_file_name, 'r')
    try:
      bulkloader_config = imp.load_module(
          'bulkloader_config', config_file, config_file_name,
          ('', 'r', imp.PY_SOURCE))
      sys.modules['bulkloader_config'] = bulkloader_config

      if hasattr(bulkloader_config, 'loaders'):
        for cls in bulkloader_config.loaders:
          Loader.RegisterLoader(cls())

      if hasattr(bulkloader_config, 'exporters'):
        for cls in bulkloader_config.exporters:
          Exporter.RegisterExporter(cls())
    except NameError, e:
      m = re.search(r"[^']*'([^']*)'.*", str(e))
      if m.groups() and m.group(1) == 'Loader':
        print >>sys.stderr, """
The config file format has changed and you appear to be using an old-style
config file.  Please make the following changes:

1. At the top of the file, add this:

from google.appengine.tools.bulkloader import Loader

2. For each of your Loader subclasses add the following at the end of the
   __init__ definitioion:

self.alias_old_names()

3. At the bottom of the file, add this:

loaders = [MyLoader1,...,MyLoaderN]

Where MyLoader1,...,MyLoaderN are the Loader subclasses you want the bulkloader
to have access to.
"""
        exit_fn(1)
      else:
        raise
    except Exception, e:
      if isinstance(e, NameClashError) or 'bulkloader_config' in vars() and (
          hasattr(bulkloader_config, 'bulkloader') and
          isinstance(e, bulkloader_config.bulkloader.NameClashError)):
        print >> sys.stderr, (
            'Found both %s and %s while aliasing old names on %s.'%
            (e.old_name, e.new_name, e.klass))
        exit_fn(1)
      else:
        raise

def GetArgument(kwargs, name, die_fn):
  """Get the value of the key name in kwargs, or die with die_fn.

  Args:
    kwargs: A dictionary containing the options for the bulkloader.
    name: The name of a bulkloader option.
    die_fn: The function to call to exit the program.

  Returns:
    The value of kwargs[name] is name in kwargs
  """
  if name in kwargs:
    return kwargs[name]
  else:
    print >>sys.stderr, '%s argument required' % name
    die_fn()


def _MakeSignature(app_id=None,
                   url=None,
                   kind=None,
                   db_filename=None,
                   download=None,
                   has_header=None,
                   result_db_filename=None):
  """Returns a string that identifies the important options for the database."""
  if download:
    result_db_line = 'result_db: %s' % result_db_filename
  else:
    result_db_line = ''
  return u"""
  app_id: %s
  url: %s
  kind: %s
  download: %s
  progress_db: %s
  has_header: %s
  %s
  """ % (app_id, url, kind, download, db_filename, has_header, result_db_line)


def ProcessArguments(arg_dict,
                     die_fn=lambda: sys.exit(1)):
  """Processes non command-line input arguments.

  Args:
    arg_dict: Dictionary containing the values of bulkloader options.
    die_fn: Function to call in case of an error during argument processing.

  Returns:
    A dictionary of bulkloader options.
  """
  app_id = GetArgument(arg_dict, 'app_id', die_fn)
  url = GetArgument(arg_dict, 'url', die_fn)
  filename = GetArgument(arg_dict, 'filename', die_fn)
  batch_size = GetArgument(arg_dict, 'batch_size', die_fn)
  kind = GetArgument(arg_dict, 'kind', die_fn)
  db_filename = GetArgument(arg_dict, 'db_filename', die_fn)
  config_file = GetArgument(arg_dict, 'config_file', die_fn)
  result_db_filename = GetArgument(arg_dict, 'result_db_filename', die_fn)
  download = GetArgument(arg_dict, 'download', die_fn)
  log_file = GetArgument(arg_dict, 'log_file', die_fn)

  unused_passin = GetArgument(arg_dict, 'passin', die_fn)
  unused_email = GetArgument(arg_dict, 'email', die_fn)
  unused_debug = GetArgument(arg_dict, 'debug', die_fn)
  unused_num_threads = GetArgument(arg_dict, 'num_threads', die_fn)
  unused_bandwidth_limit = GetArgument(arg_dict, 'bandwidth_limit', die_fn)
  unused_rps_limit = GetArgument(arg_dict, 'rps_limit', die_fn)
  unused_http_limit = GetArgument(arg_dict, 'http_limit', die_fn)
  unused_auth_domain = GetArgument(arg_dict, 'auth_domain', die_fn)
  unused_has_headers = GetArgument(arg_dict, 'has_header', die_fn)
  unused_loader_opts = GetArgument(arg_dict, 'loader_opts', die_fn)
  unused_exporter_opts = GetArgument(arg_dict, 'exporter_opts', die_fn)

  errors = []

  if db_filename is None:
    arg_dict['db_filename'] = time.strftime(
        'bulkloader-progress-%Y%m%d.%H%M%S.sql3')

  if result_db_filename is None:
    arg_dict['result_db_filename'] = time.strftime(
        'bulkloader-results-%Y%m%d.%H%M%S.sql3')

  if log_file is None:
    arg_dict['log_file'] = time.strftime('bulkloader-log-%Y%m%d.%H%M%S')

  if batch_size <= 0:
    errors.append('batch_size must be at least 1')

  required = '%s argument required'

  if url is REQUIRED_OPTION:
    errors.append(required % 'url')

  if filename is REQUIRED_OPTION:
    errors.append(required % 'filename')

  if kind is REQUIRED_OPTION:
    errors.append(required % 'kind')

  if config_file is REQUIRED_OPTION:
    errors.append(required % 'config_file')

  if download:
    if result_db_filename is REQUIRED_OPTION:
      errors.append(required % 'result_db_filename')

  if not app_id:
    (unused_scheme, host_port, unused_url_path,
     unused_query, unused_fragment) = urlparse.urlsplit(url)
    suffix_idx = host_port.find('.appspot.com')
    if suffix_idx > -1:
      arg_dict['app_id'] = host_port[:suffix_idx]
    elif host_port.split(':')[0].endswith('google.com'):
      arg_dict['app_id'] = host_port.split('.')[0]
    else:
      errors.append('app_id argument required for non appspot.com domains')

  if errors:
    print >>sys.stderr, '\n'.join(errors)
    die_fn()

  return arg_dict


def ParseKind(kind):
  if kind and kind[0] == '(' and kind[-1] == ')':
    return tuple(kind[1:-1].split(','))
  else:
    return kind


def _PerformBulkload(arg_dict,
                     check_file=CheckFile,
                     check_output_file=CheckOutputFile):
  """Runs the bulkloader, given the command line options.

  Args:
    arg_dict: Dictionary of bulkloader options.
    check_file: Used for dependency injection.
    check_output_file: Used for dependency injection.

  Returns:
    An exit code.

  Raises:
    ConfigurationError: if inconsistent options are passed.
  """
  app_id = arg_dict['app_id']
  url = arg_dict['url']
  filename = arg_dict['filename']
  batch_size = arg_dict['batch_size']
  kind = arg_dict['kind']
  num_threads = arg_dict['num_threads']
  bandwidth_limit = arg_dict['bandwidth_limit']
  rps_limit = arg_dict['rps_limit']
  http_limit = arg_dict['http_limit']
  db_filename = arg_dict['db_filename']
  config_file = arg_dict['config_file']
  auth_domain = arg_dict['auth_domain']
  has_header = arg_dict['has_header']
  download = arg_dict['download']
  result_db_filename = arg_dict['result_db_filename']
  loader_opts = arg_dict['loader_opts']
  exporter_opts = arg_dict['exporter_opts']
  email = arg_dict['email']
  passin = arg_dict['passin']

  os.environ['AUTH_DOMAIN'] = auth_domain

  kind = ParseKind(kind)

  check_file(config_file)
  if not download:
    check_file(filename)
  else:
    check_output_file(filename)

  LoadConfig(config_file)

  os.environ['APPLICATION_ID'] = app_id

  throttle_layout = ThrottleLayout(bandwidth_limit, http_limit, rps_limit)

  throttle = Throttle(layout=throttle_layout)
  signature = _MakeSignature(app_id=app_id,
                             url=url,
                             kind=kind,
                             db_filename=db_filename,
                             download=download,
                             has_header=has_header,
                             result_db_filename=result_db_filename)


  max_queue_size = max(DEFAULT_QUEUE_SIZE, 3 * num_threads + 5)

  if db_filename == 'skip':
    progress_db = StubProgressDatabase()
  elif not download:
    progress_db = ProgressDatabase(db_filename, signature)
  else:
    progress_db = ExportProgressDatabase(db_filename, signature)

  if download:
    result_db = ResultDatabase(result_db_filename, signature)

  return_code = 1

  if not download:
    loader = Loader.RegisteredLoader(kind)
    try:
      loader.initialize(filename, loader_opts)
      workitem_generator_factory = GetCSVGeneratorFactory(
          kind, filename, batch_size, has_header)

      app = BulkUploaderApp(arg_dict,
                            workitem_generator_factory,
                            throttle,
                            progress_db,
                            BulkLoaderThread,
                            ProgressTrackerThread,
                            max_queue_size,
                            RequestManager,
                            DataSourceThread,
                            ReQueue,
                            Queue.Queue)
      try:
        return_code = app.Run()
      except AuthenticationError:
        logger.info('Authentication Failed')
    finally:
      loader.finalize()
  else:
    exporter = Exporter.RegisteredExporter(kind)
    try:
      exporter.initialize(filename, exporter_opts)

      def KeyRangeGeneratorFactory(progress_queue, progress_gen):
        return KeyRangeGenerator(kind, progress_queue, progress_gen)

      def ExportProgressThreadFactory(progress_queue, progress_db):
        return ExportProgressThread(kind,
                                    progress_queue,
                                    progress_db,
                                    result_db)
      app = BulkDownloaderApp(arg_dict,
                              KeyRangeGeneratorFactory,
                              throttle,
                              progress_db,
                              BulkExporterThread,
                              ExportProgressThreadFactory,
                              0,
                              RequestManager,
                              DataSourceThread,
                              ReQueue,
                              Queue.Queue)
      try:
        return_code = app.Run()
      except AuthenticationError:
        logger.info('Authentication Failed')
    finally:
      exporter.finalize()
  return return_code


def SetupLogging(arg_dict):
  """Sets up logging for the bulkloader.

  Args:
    arg_dict: Dictionary mapping flag names to their arguments.
  """
  format = '[%(levelname)-8s %(asctime)s %(filename)s] %(message)s'
  debug = arg_dict['debug']
  log_file = arg_dict['log_file']

  logger.setLevel(logging.DEBUG)

  logger.propagate = False

  file_handler = logging.FileHandler(log_file, 'w')
  file_handler.setLevel(logging.DEBUG)
  file_formatter = logging.Formatter(format)
  file_handler.setFormatter(file_formatter)
  logger.addHandler(file_handler)

  console = logging.StreamHandler()
  level = logging.INFO
  if debug:
    level = logging.DEBUG
  console.setLevel(level)
  console_format = '[%(levelname)-8s] %(message)s'
  formatter = logging.Formatter(console_format)
  console.setFormatter(formatter)
  logger.addHandler(console)

  logger.info('Logging to %s', log_file)

  appengine_rpc.logger.setLevel(logging.WARN)


def Run(arg_dict):
  """Sets up and runs the bulkloader, given the options as keyword arguments.

  Args:
    arg_dict: Dictionary of bulkloader options

  Returns:
    An exit code.
  """
  arg_dict = ProcessArguments(arg_dict)

  SetupLogging(arg_dict)

  return _PerformBulkload(arg_dict)


def main(argv):
  """Runs the importer from the command line."""

  arg_dict = ParseArguments(argv)

  errors = ['%s argument required' % key
            for (key, value) in arg_dict.iteritems()
            if value is REQUIRED_OPTION]
  if errors:
    print >>sys.stderr, '\n'.join(errors)
    PrintUsageExit(1)

  SetupLogging(arg_dict)
  return _PerformBulkload(arg_dict)


if __name__ == '__main__':
  sys.exit(main(sys.argv))
