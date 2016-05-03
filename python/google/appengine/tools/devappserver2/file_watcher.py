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



import logging
import sys
import types

from google.appengine.tools.devappserver2 import fsevents_file_watcher
from google.appengine.tools.devappserver2 import inotify_file_watcher
from google.appengine.tools.devappserver2 import mtime_file_watcher


class _MultipleFileWatcher(object):
  """A FileWatcher that combines multiple file watchers.

  For file watchers that can only watch a single directory, this class can
  manage multiple watchers and allows the caller to treat them as a single
  unit.
  """

  def __init__(self, watchers):
    """Initialize a MultipleFileWatcher instance.

    Args:
      watchers: a list of watchers to treat as a single watcher.
    """
    self._file_watchers = watchers

  def start(self):
    for watcher in self._file_watchers:
      watcher.start()

  def quit(self):
    for watcher in self._file_watchers:
      watcher.quit()

  def changes(self, timeout_ms=0):
    """Returns the paths changed in the watched directories since the last call.

    start() must be called before this method.

    Args:
      timeout_ms: the maximum number of mulliseconds you allow this function to
                  wait for a filesystem change.

    Returns:
       An iterable of changed directories/files.
    """

    # Splits the allocated time between the watchers.
    timeout_ms /= len(self._file_watchers)
    return set.union(
        *[watcher.changes(timeout_ms) for watcher in self._file_watchers])


def _create_watcher(directories, watcher_class):
  """Creates the best watcher based on multiple directory support.

  For file watchers that can support multiple directories, directly instantiate
  an instance passing in an iterable of directories names. For file watchers
  that only support single directories, instantiate one directly if there is
  only a single directory to watch or wrap them in a MultipleFileWatcher if
  there are multiple directories to watch.

  Args:
    directories: an iterable of all the directories to watch.
    watcher_class: a callable that creates the per-directory FileWatcher
      instance. Must be callable with a single item of the type held by
      directories.

  Returns:
    A FileWatcher appropriate for the list of directories.
  """
  if watcher_class.SUPPORTS_MULTIPLE_DIRECTORIES:
    return watcher_class(directories)
  elif len(directories) == 1:
    return watcher_class(directories[0])
  else:
    return _MultipleFileWatcher([watcher_class(d) for d in directories])


def _create_linux_watcher(directories):
  """Create a watcher for Linux.

  While we prefer InotifyFileWatcher for Linux, there are only a limited number
  of inotify instances available per user (for example, 128 on a Goobuntu 12.04
  install). Try to create an InotifyFileWatcher but fall back on
  MTimeFileWatcher if the user is out of resources.

  Args:
    directories: A list representing the paths of the directories to monitor.

  Returns:
    An InotifyFileWatcher if the user has available resources and an
    MtimeFileWatcher if not.
  """

  # TODO: develop a way to check if the filesystem supports inotify.
  # (for example, NFS does not) and also use MTimeFileWatcher in that case.

  try:
    return _create_watcher(directories,
                           inotify_file_watcher.InotifyFileWatcher)
  except OSError as e:
    logging.warning('Could not create InotifyFileWatcher;'
                    ' falling back to MTimeFileWatcher: %s', e)
    return _create_watcher(directories, mtime_file_watcher.MtimeFileWatcher)


def _create_mac_watcher(directories):
  """Create a watcher for Mac OS X.

  While we prefer FSEventsFileWatcher for Mac OS X, the user may not have the
  Python wrapper for the FSEvents framework installed. Try to create a
  FSEventsFileWatcher but fall back on MTimeFileWatcher if the required Python
  package is not available.

  Args:
    directories: A list representing the paths of the directories to monitor.

  Returns:
    A FSEventsFileWatcher if the required Python package is available and an
    MTimeFileWatcher if not.
  """
  if fsevents_file_watcher.FSEventsFileWatcher.is_available():
    return _create_watcher(directories,
                           fsevents_file_watcher.FSEventsFileWatcher)
  else:
    logging.warning('Could not create FSEventsFileWatcher; falling back to '
                    'the slower MTimeFileWatcher. To fix this, run '
                    '"pip install -r requirements.txt" from your '
                    'frankenserver directory.')
    return _create_watcher(directories, mtime_file_watcher.MtimeFileWatcher)


def get_file_watcher(directories, use_mtime_file_watcher):
  """Returns an instance that monitors a hierarchy of directories.

  Args:
    directories: A list representing the paths of the directories to monitor.
    use_mtime_file_watcher: A bool containing whether to use mtime polling to
        monitor file changes even if other options are available on the current
        platform.

  Returns:
    A FileWatcher appropriate for the current platform. start() must be called
    before changes().
  """
  assert not isinstance(directories, types.StringTypes), 'expected list got str'

  if use_mtime_file_watcher:
    return _create_watcher(directories, mtime_file_watcher.MtimeFileWatcher)
  elif sys.platform.startswith('linux'):
    return _create_linux_watcher(directories)
  elif sys.platform.startswith('darwin'):
    return _create_mac_watcher(directories)
  else:
    return _create_watcher(directories, mtime_file_watcher.MtimeFileWatcher)
