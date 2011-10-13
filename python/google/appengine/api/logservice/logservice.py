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




"""
LogService API.

This module allows apps to flush logs, provide status messages, as well as the
ability to programmatically access their log files.
"""






import cStringIO
import os
import re
import sys
import threading
import time

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api.logservice import log_service_pb
from google.appengine.api.logservice import logsutil


AUTOFLUSH_ENABLED = True


AUTOFLUSH_EVERY_SECONDS = 60


AUTOFLUSH_EVERY_BYTES = 4096


AUTOFLUSH_EVERY_LINES = 50






DEFAULT_ITEMS_PER_FETCH = 20


MAX_ITEMS_PER_FETCH = 100


LOG_LEVEL_DEBUG = 0
LOG_LEVEL_INFO = 1
LOG_LEVEL_WARNING = 2
LOG_LEVEL_ERROR = 3
LOG_LEVEL_CRITICAL = 4

_MAJOR_VERSION_ID_PATTERN = r'[a-z\d][a-z\d\-]{0,99}'
_MAJOR_VERSION_ID_RE = re.compile(_MAJOR_VERSION_ID_PATTERN)


class Error(Exception):
  """Base error class for this module."""


class InvalidArgumentError(Error):
  """Function argument has invalid value."""


class LogsBuffer(object):
  """Threadsafe buffer for storing and periodically flushing app logs."""

  def __init__(self, stream=None, stderr=False):
    """Initializes the buffer, which wraps the given stream or sys.stderr.

    The state of the LogsBuffer is protected by a separate lock.  The lock is
    acquired before any variables are mutated or accessed, and released
    afterward.  A recursive lock is used so that a single thread can acquire the
    lock multiple times, and release it only when an identical number of
    'unlock()' calls have been performed.

    Args:
      stream: A file-like object to store logs. Defaults to a cStringIO object.
      stderr: If specified, use sys.stderr as the underlying stream.
    """
    self._stderr = stderr
    if self._stderr:
      assert stream is None
    else:
      self._stream = stream or cStringIO.StringIO()
    self._lock = threading.RLock()
    self._reset()

  def _lock_and_call(self, method, *args):
    """Calls 'method' while holding the buffer lock."""
    self._lock.acquire()
    try:
      return method(*args)
    finally:
      self._lock.release()

  def stream(self):
    """Returns the underlying file-like object used to buffer logs."""
    if self._stderr:


      return sys.stderr
    else:
      return self._stream

  def lines(self):
    """Returns the number of log lines currently buffered."""
    return self._lock_and_call(lambda: self._lines)

  def bytes(self):
    """Returns the size of the log buffer, in bytes."""
    return self._lock_and_call(lambda: self._bytes)

  def age(self):
    """Returns the number of seconds since the log buffer was flushed."""
    return self._lock_and_call(lambda: time.time() - self._flush_time)

  def flush_time(self):
    """Returns last time that the log buffer was flushed."""
    return self._lock_and_call(lambda: self._flush_time)

  def contents(self):
    """Returns the contents of the logs buffer."""
    return self._lock_and_call(self._contents)

  def _contents(self):
    """Internal version of contents() with no locking."""
    try:
      return self.stream().getvalue()
    except AttributeError:


      return ''

  def reset(self):
    """Resets the buffer state, without clearing the underlying stream."""
    self._lock_and_call(self._reset)

  def _reset(self):
    """Internal version of reset() with no locking."""
    contents = self._contents()
    self._bytes = len(contents)
    self._lines = len(contents.split('\n')) - 1
    self._flush_time = time.time()
    self._request = logsutil.RequestID()

  def clear(self):
    """Clears the contents of the logs buffer, and resets autoflush state."""
    self._lock_and_call(self._clear)

  def _clear(self):
    """Internal version of clear() with no locking."""
    if self._bytes > 0:
      self.stream().truncate(0)
    self._reset()

  def close(self):
    """Closes the underlying stream, flushing the current contents."""
    self._lock_and_call(self._close)

  def _close(self):
    """Internal version of close() with no locking."""
    self._flush()
    self.stream().close()

  def parse_logs(self):
    """Parse the contents of the buffer and return an array of log lines."""
    return logsutil.ParseLogs(self.contents())

  def write(self, line):
    """Writes a line to the logs buffer."""
    return self._lock_and_call(self._write, line)

  def writelines(self, seq):
    """Writes each line in the given sequence to the logs buffer."""
    for line in seq:
      self.write(line)

  def _write(self, line):
    """Writes a line to the logs buffer."""
    if self._request != logsutil.RequestID():


      self._reset()
    self.stream().write(line)




    self.stream().flush()
    self._lines += 1
    self._bytes += len(line)
    self._autoflush()

  def flush(self):
    """Flushes the contents of the logs buffer.

    This method holds the buffer lock until the API call has finished to ensure
    that flush calls are performed in the correct order, so that log messages
    written during the flush call aren't dropped or accidentally wiped, and so
    that the other buffer state variables (flush time, lines, bytes) are updated
    synchronously with the flush.
    """
    self._lock_and_call(self._flush)

  def _flush(self):
    """Internal version of flush() with no locking."""
    logs = self.parse_logs()
    self._clear()

    if len(logs) == 0:
      return

    request = log_service_pb.FlushRequest()
    group = log_service_pb.UserAppLogGroup()
    for entry in logs:
      line = group.add_log_line()
      line.set_timestamp_usec(entry[0])
      line.set_level(entry[1])
      line.set_message(entry[2])
    request.set_logs(group.Encode())
    response = api_base_pb.VoidProto()
    apiproxy_stub_map.MakeSyncCall('logservice', 'Flush', request, response)

  def autoflush(self):
    """Flushes the buffer if certain conditions have been met."""
    self._lock_and_call(self._autoflush)

  def _autoflush(self):
    """Internal version of autoflush() with no locking."""
    if not self.autoflush_enabled():
      return

    if ((AUTOFLUSH_EVERY_SECONDS and self.age() >= AUTOFLUSH_EVERY_SECONDS) or
        (AUTOFLUSH_EVERY_LINES and self.lines() >= AUTOFLUSH_EVERY_LINES) or
        (AUTOFLUSH_EVERY_BYTES and self.bytes() >= AUTOFLUSH_EVERY_BYTES)):
      self._flush()

  def autoflush_enabled(self):
    """Indicates if the buffer will periodically flush logs during a request."""
    return AUTOFLUSH_ENABLED



_global_buffer = LogsBuffer(stderr=True)


def logs_buffer():
  """Returns the LogsBuffer used by the current request."""




  return _global_buffer


def write(message):
  """Adds 'message' to the logs buffer, and checks for autoflush.

  Args:
    message: A message (string) to be written to application logs.
  """
  logs_buffer().write(message)


def clear():
  """Clear the logs buffer and reset the autoflush state."""
  logs_buffer().clear()


def autoflush():
  """If AUTOFLUSH conditions have been met, performs a Flush API call."""
  logs_buffer().autoflush()


def flush():
  """Flushes log lines that are currently buffered."""
  logs_buffer().flush()


def flush_time():
  """Returns last time that the logs buffer was flushed."""
  return logs_buffer().flush_time()


def log_buffer_age():
  """Returns the number of seconds since the logs buffer was flushed."""
  return logs_buffer().age()


def log_buffer_contents():
  """Returns the contents of the logs buffer."""
  return logs_buffer().contents()


def log_buffer_bytes():
  """Returns the size of the logs buffer, in bytes."""
  return logs_buffer().bytes()


def log_buffer_lines():
  """Returns the number of log lines currently buffered."""
  return logs_buffer().lines()


class _LogQueryResult(object):
  """A container that holds a log request and provides an iterator to read logs.

  A _LogQueryResult object is the standard returned item for a call to fetch().
  It is iterable - each value returned is a log that the user has queried for,
  and internally, it holds a cursor that it uses to fetch more results once the
  current, locally held set, are exhausted.

  Properties:
    _request: A LogReadRequest that contains the parameters the user has set for
      the initial fetch call, which will be updated with a more current cursor
      if more logs are requested.
    _logs: A list of RequestLogs corresponding to logs the user has asked for.
  """

  def __init__(self, request):
    """Constructor.

    Args:
      request: A LogReadRequest object that will be used for Read calls.
    """
    self._request = request
    self._logs = []
    self._read_called = False

  def __iter__(self):
    """Provides an iterator that yields log records one at a time.

    This iterator yields items held locally first, and once these items have
    been exhausted, it fetched more items via _advance() and yields them. The
    number of items it holds is min(MAX_ITEMS_PER_FETCH, batch_size) - the
    latter value can be provided by the user on an initial call to fetch().
    """
    while True:
      for log_item in self._logs:
        yield log_item
      if not self._read_called or self._request.has_offset():
        self._read_called = True
        self._advance()
      else:
        break

  def _advance(self):
    """Acquires additional logs via cursor.

    This method is used by the iterator when it has exhausted its current set of
    logs to acquire more logs and update its internal structures accordingly.
    """
    response = log_service_pb.LogReadResponse()

    apiproxy_stub_map.MakeSyncCall('logservice', 'Read', self._request,
                                   response)
    self._logs = response.log_list()
    self._request.clear_offset()
    if response.has_offset():
      self._request.mutable_offset().CopyFrom(response.offset())


def fetch(start_time_usec=None,
          end_time_usec=None,
          batch_size=DEFAULT_ITEMS_PER_FETCH,
          min_log_level=None,
          include_incomplete=False,
          include_app_logs=False,
          version_ids=None):
  """Fetches an application's request and/or application-level logs.

  Args:
    start_time_usec: A long corresponding to the earliest time (in microseconds
      since epoch) that results should be fetched for.
    end_time_usec: A long corresponding to the latest time (in microseconds
      since epoch) that results should be fetched for.
    batch_size: The maximum number of log records that this request should
      return. A log record corresponds to a web request made to the
      application. Therefore, it may include a single request log and multiple
      application level logs (e.g., WARN and INFO messages).
    min_log_level: The minimum app log level that this request should be
      returned. This means that querying for a certain log level always returns
      that log level and all log levels above it. In ascending order, the log
      levels available are: logs.DEBUG, logs.INFO, logs.WARNING, logs.ERROR,
      and logs.CRITICAL.
    include_incomplete: Whether or not to include requests that have started but
      not yet finished, as a boolean.
    include_app_logs: Whether or not to include application level logs in the
      results, as a boolean.
    version_ids: A list of version ids whose logs should be queried against.
      Defaults to the application's current version id only.

  Returns:
    An iterable object containing the logs that the user has queried for.

  Raises:
    InvalidArgumentError: Raised if any of the input parameters are not of the
      correct type.
  """

  request = log_service_pb.LogReadRequest()

  request.set_app_id(os.environ['APPLICATION_ID'])

  if start_time_usec:
    if not isinstance(start_time_usec, long):
      raise InvalidArgumentError('start_time_usec must be a long')
    request.set_start_time(start_time_usec)

  if end_time_usec:
    if not isinstance(end_time_usec, long):
      raise InvalidArgumentError('end_time_usec must be a long')
    request.set_end_time(end_time_usec)

  if not isinstance(batch_size, int):
    raise InvalidArgumentError('batch_size must be an integer')

  if batch_size < 1:
    raise InvalidArgumentError('batch_size must be greater than zero')

  if batch_size > MAX_ITEMS_PER_FETCH:
    raise InvalidArgumentError('batch_size specified was too large')
  request.set_count(batch_size)

  if min_log_level:
    if not isinstance(min_log_level, int):
      raise InvalidArgumentError('min_log_level must be an int')

    if not min_log_level in range(LOG_LEVEL_CRITICAL+1):
      raise InvalidArgumentError("""min_log_level must be between 0 and 4
                                 inclusive""")
    request.set_minimum_log_level(min_log_level)

  if not isinstance(include_incomplete, bool):
    raise InvalidArgumentError('include_incomplete must be boolean')

  request.set_include_incomplete(include_incomplete)

  if not isinstance(include_app_logs, bool):
    raise InvalidArgumentError('include_app_logs must be boolean')

  request.set_include_app_logs(include_app_logs)

  if version_ids is None:
    version_id = os.environ['CURRENT_VERSION_ID']
    version_ids = [version_id.split('.')[0]]
  else:
    if not isinstance(version_ids, list):
      raise InvalidArgumentError('version_ids must be a list')
    for version_id in version_ids:
      if not _MAJOR_VERSION_ID_RE.match(version_id):
        raise InvalidArgumentError(
            'version_ids must only contain valid major version identifiers')

  request.version_id_list()[:] = version_ids

  return _LogQueryResult(request)
