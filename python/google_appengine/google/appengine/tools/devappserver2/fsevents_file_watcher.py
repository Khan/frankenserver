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
"""Monitors a directory tree for changes using the Mac OS X FSEvents API."""


import os.path
import threading

try:
  import AppKit
  import FSEvents
except ImportError:
  AppKit = None
  FSEvents = None


class FSEventsFileWatcher(object):
  """Monitors a directory tree for changes using FSEVents."""

  def __init__(self, directory):
    """Initializer for FSEventsFileWatcher.

    Args:
      directory: A string representing the path to a directory that should
          be monitored for changes i.e. files and directories added, renamed,
          deleted or changed.
    """
    self._directory = os.path.abspath(directory)
    self._has_changes = None
    self._quit_event = threading.Event()
    self._event_watcher_thread = threading.Thread(target=self._watch_changes)

  @staticmethod
  def is_available():
    return FSEvents is not None

  def _fsevents_callback(self, *unused_args):
    self._has_changes = True

  def _watch_changes(self):
    # Do the file watching in a thread to ensure that
    # FSEventStreamScheduleWithRunLoop and CFRunLoopRunInMode are called in the
    # same thread.

    # Each thread needs its own AutoreleasePool.
    pool = AppKit.NSAutoreleasePool.alloc().init()
    event_stream = FSEvents.FSEventStreamCreate(
        None,
        self._fsevents_callback,
        None,
        [self._directory],
        FSEvents.kFSEventStreamEventIdSinceNow,
        1,  # Seconds to wait to between received events.
        FSEvents.kFSEventStreamCreateFlagNone,
        )

    FSEvents.FSEventStreamScheduleWithRunLoop(event_stream,
                                              FSEvents.CFRunLoopGetCurrent(),
                                              FSEvents.kCFRunLoopDefaultMode)

    assert FSEvents.FSEventStreamStart(event_stream), (
        'event stream could not be started')
    while not self._quit_event.is_set():
      FSEvents.CFRunLoopRunInMode(FSEvents.kCFRunLoopDefaultMode,
                                  0.1,    # seconds
                                  False)  # returnAfterSourceHandled

    FSEvents.FSEventStreamRelease(event_stream)
    del pool  # del is recommended by the PyObjc programming guide.

  def start(self):
    """Start watching the directory for changes."""
    self._has_changes = False
    self._event_watcher_thread.start()

  def quit(self):
    """Stop watching the directory for changes."""
    self._quit_event.set()

  def has_changes(self):
    assert self._event_watcher_thread.is_alive(), (
        'watcher thread exited or was not started')
    try:
      return self._has_changes
    finally:
      self._has_changes = False
