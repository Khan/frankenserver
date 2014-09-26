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


"""Utility methods for working with logs."""


import os
import time



REQUEST_LOG_ID = 'REQUEST_LOG_ID'


_U_SEC = 1000000

LOG_LEVEL_DEBUG = 0
LOG_LEVEL_INFO = 1
LOG_LEVEL_WARNING = 2
LOG_LEVEL_ERROR = 3
LOG_LEVEL_CRITICAL = 4

LOG_LEVELS = [LOG_LEVEL_DEBUG,
              LOG_LEVEL_INFO,
              LOG_LEVEL_WARNING,
              LOG_LEVEL_ERROR,
              LOG_LEVEL_CRITICAL]



_DEFAULT_LEVEL = LOG_LEVEL_ERROR


def _CurrentTimeMicro():
  return int(time.time() * _U_SEC)


def _Clean(e):
  return e.replace('\0', '\n')


def RequestID():
  """Returns the ID of the current request assigned by App Engine."""
  return os.environ.get(REQUEST_LOG_ID, None)


def _StrictParseLogEntry(entry):
  """Parses a single log entry emitted by app_logging.AppLogsHandler.

  Parses a log entry of the form LOG <level> <timestamp> <message> where the
  level is in the range [0, 4]. If the entry is not of that form, ValueError is
  raised.

  Args:
    entry: The log entry to parse.

  Returns:
    A (timestamp, level, message) tuple.

  Raises:
    ValueError: if the entry failed to be parsed.
  """
  magic, level, timestamp, message = entry.split(' ', 3)
  if magic != 'LOG':
    raise ValueError()

  timestamp, level = int(timestamp), int(level)
  if level not in LOG_LEVELS:
    raise ValueError()

  return timestamp, level, _Clean(message)


def ParseLogEntry(entry):
  """Parses a single log entry emitted by app_logging.AppLogsHandler.

  Parses a log entry of the form LOG <level> <timestamp> <message> where the
  level is in the range [0, 4]. If the entry is not of that form, take the whole
  entry to be the message. Null characters in the entry are replaced by
  newlines.

  Args:
    entry: The log entry to parse.

  Returns:
    A (timestamp, level, message) tuple.
  """
  try:
    return _StrictParseLogEntry(entry)
  except ValueError:

    return _CurrentTimeMicro(), _DEFAULT_LEVEL, _Clean(entry)


def ParseLogs(logs):
  """Parses a str containing newline separated log entries.

  Parses a series of log entries in the form LOG <level> <timestamp> <message>
  where the level is in the range [0, 4].  Null characters in the entry are
  replaced by newlines.

  Args:
    logs: A string containing the log entries.

  Returns:
    A list of (timestamp, level, message) tuples.
  """
  return [ParseLogEntry(line) for line in logs.split('\n') if line]
