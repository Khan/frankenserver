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
"""Monitors a directory tree for changes."""


import sys
import warnings

from google.appengine.tools.devappserver2 import fsevents_file_watcher
from google.appengine.tools.devappserver2 import inotify_file_watcher
from google.appengine.tools.devappserver2 import win32_file_watcher


class DummyFileWatcher(object):
  def start(self):
    """Start watching a directory for changes."""

  def quit(self):
    """Stop watching a directory for changes."""

  def has_changes(self):
    """Returns True if the watched directory has changed since the last call.

    start() must be called before this method.

    Returns:
      Returns True if the watched directory has changed since the last call to
      has_changes or, if has_changes has never been called, since start was
      called. The result is always False in this dummy implementation.
    """
    return False


def get_file_watcher(directory):
  """Returns an instance that monitors a tree for changes.

  Args:
    directory: A string representing the path of the directory to monitor.

  Returns:
    A FileWatcher appropriate for the current platform. start() must be called
    before has_changes().
  """
  if sys.platform.startswith('linux'):
    return inotify_file_watcher.InotifyFileWatcher(directory)
  elif sys.platform.startswith('win'):
    return win32_file_watcher.Win32FileWatcher(directory)
  elif sys.platform.startswith('darwin'):
    if fsevents_file_watcher.FSEventsFileWatcher.is_available():
      return fsevents_file_watcher.FSEventsFileWatcher(directory)
    else:
      warnings.warn('Detecting source code changes is not supported because '
                    'your Python version does not include PyObjC '
                    '(http://pyobjc.sourceforge.net/). Please install PyObjC '
                    'or, if that is not practical, file a bug at '
                    'http://code.google.com/p/'
                    'appengine-devappserver2-experiment/issues/list.')
  else:
    warnings.warn('Detecting source code changes is not supported on your '
                  'platform. Please file a bug at http://code.google.com/p/'
                  'appengine-devappserver2-experiment/issues/list.')
  return DummyFileWatcher()
