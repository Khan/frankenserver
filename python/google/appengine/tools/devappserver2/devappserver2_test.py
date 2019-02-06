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
"""Tests for google.apphosting.tools.devappserver2.devappserver2."""



import argparse
import os
import platform
import unittest

import google
import mock
from google.appengine.tools.devappserver2 import devappserver2


class WinError(Exception):
  pass


class FakeApplicationConfiguration(object):

  def __init__(self, modules):
    self.modules = modules


class FakeModuleConfiguration(object):

  def __init__(self, module_name):
    self.module_name = module_name


class CreateModuleToSettingTest(unittest.TestCase):

  def setUp(self):
    self.application_configuration = FakeApplicationConfiguration([
        FakeModuleConfiguration('m1'), FakeModuleConfiguration('m2'),
        FakeModuleConfiguration('m3')])

  def test_none(self):
    self.assertEquals(
        {},
        devappserver2.DevelopmentServer._create_module_to_setting(
            None, self.application_configuration, '--option'))

  def test_dict(self):
    self.assertEquals(
        {'m1': 3, 'm3': 1},
        devappserver2.DevelopmentServer._create_module_to_setting(
            {'m1': 3, 'm3': 1}, self.application_configuration, '--option'))

  def test_single_value(self):
    self.assertEquals(
        {'m1': True, 'm2': True, 'm3': True},
        devappserver2.DevelopmentServer._create_module_to_setting(
            True, self.application_configuration, '--option'))

  def test_dict_with_unknown_modules(self):
    self.assertEquals(
        {'m1': 3.5},
        devappserver2.DevelopmentServer._create_module_to_setting(
            {'m1': 3.5, 'm4': 2.7}, self.application_configuration, '--option'))


class DatastoreEmulatorSupportcheckTest(unittest.TestCase):

  @mock.patch.object(os.path, 'exists', return_value=False)
  @mock.patch.object(devappserver2.DevelopmentServer,
                     '_correct_datastore_emulator_cmd', return_value=None)
  def test_fail_missing_emulator(self, mock_correction, unused_mock):
    options = argparse.Namespace()
    # Following flags simulate the scenario of invoking dev_appserver.py from
    # google-cloud-sdk/platform/google_appengine
    options.support_datastore_emulator = True
    options.datastore_emulator_cmd = None
    with self.assertRaises(devappserver2.MissingDatastoreEmulatorError) as ctx:
      dev_server = devappserver2.DevelopmentServer()
      dev_server._options = options
      dev_server._check_datastore_emulator_support()
      mock_correction.assert_called_once_with()
    self.assertIn('Cannot find Cloud Datastore Emulator', ctx.exception.message)


class PlatformSupportCheckTest(unittest.TestCase):

  def test_succeed_non_python3_windows(self):
    with mock.patch.object(platform, 'system', return_value='Windows'):
      devappserver2.DevelopmentServer._check_platform_support({'python2'})
      platform.system.assert_not_called()

  def test_succeed_python3_non_windows(self):
    with mock.patch.object(platform, 'system', return_value='Linux'):
      devappserver2.DevelopmentServer._check_platform_support({'python3'})
      platform.system.assert_called_once_with()

  def test_fail_python3_windows(self):
    with mock.patch.object(platform, 'system', return_value='Windows'):
      with self.assertRaises(OSError):
        devappserver2.DevelopmentServer._check_platform_support(
            {'python3', 'python2'})
      platform.system.assert_called_once_with()


if __name__ == '__main__':
  unittest.main()
