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
"""Tests for google.apphosting.tools.devappserver2.fsevents_file_watcher."""


import os.path
import unittest

import google
import mox

from google.appengine.tools.devappserver2 import fsevents_file_watcher


class FSEventsFileWatcherTest(unittest.TestCase):
  """Tests for fsevents_file_watcher.FSEventsFileWatcher"""

  def setUp(self):
    self.mox = mox.Mox()
    self.saved_fsevents = fsevents_file_watcher.FSEvents
    self.saved_appkit = fsevents_file_watcher.AppKit

    class _AppKit(object):
      NSAutoreleasePool = self.mox.CreateMockAnything()
    fsevents_file_watcher.AppKit = _AppKit

    class _FSEvents(object):
      kCFRunLoopDefaultMode = object()
      kFSEventStreamEventIdSinceNow = object()
      kFSEventStreamCreateFlagNone = object()

      FSEventStreamCreate = self.mox.CreateMockAnything()
      FSEventStreamScheduleWithRunLoop = self.mox.CreateMockAnything()
      FSEventStreamStart = self.mox.CreateMockAnything()
      CFRunLoopGetCurrent = self.mox.CreateMockAnything()
      CFRunLoopRunInMode = self.mox.CreateMockAnything()
      FSEventStreamRelease = self.mox.CreateMockAnything()
    fsevents_file_watcher.FSEvents = _FSEvents


  def tearDown(self):
    self.mox.UnsetStubs()
    fsevents_file_watcher.FSEvents = self.saved_fsevents
    fsevents_file_watcher.AppKit = self.saved_appkit

  def test_watch_changes(self):
    watcher = fsevents_file_watcher.FSEventsFileWatcher('/tmp')

    self.mox.StubOutWithMock(watcher._quit_event, 'is_set')

    pool = self.mox.CreateMockAnything()
    fsevents_file_watcher.AppKit.NSAutoreleasePool.alloc().AndReturn(pool)
    pool.init()

    event_stream = object()
    fsevents_file_watcher.FSEvents.FSEventStreamCreate(
        None,
        watcher._fsevents_callback,
        None,
        [os.path.abspath('/tmp')],
        fsevents_file_watcher.FSEvents.kFSEventStreamEventIdSinceNow,
        1,
        fsevents_file_watcher.FSEvents.kFSEventStreamCreateFlagNone).AndReturn(
            event_stream)

    current_run_loop = object()
    fsevents_file_watcher.FSEvents.CFRunLoopGetCurrent().AndReturn(
        current_run_loop)
    fsevents_file_watcher.FSEvents.FSEventStreamScheduleWithRunLoop(
        event_stream,
        current_run_loop,
        fsevents_file_watcher.FSEvents.kCFRunLoopDefaultMode)

    fsevents_file_watcher.FSEvents.FSEventStreamStart(event_stream).AndReturn(
        True)
    watcher._quit_event.is_set().AndReturn(False)
    fsevents_file_watcher.FSEvents.CFRunLoopRunInMode(
        fsevents_file_watcher.FSEvents.kCFRunLoopDefaultMode,
        0.1,
        False).WithSideEffects(lambda *args: watcher._fsevents_callback())

    watcher._quit_event.is_set().AndReturn(True)
    fsevents_file_watcher.FSEvents.FSEventStreamRelease(event_stream)

    self.mox.ReplayAll()
    watcher.start()
    watcher._event_watcher_thread.join()
    self.mox.VerifyAll()

    self.assertTrue(watcher._has_changes)

if __name__ == '__main__':
  unittest.main()
