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



import unittest

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


if __name__ == '__main__':
  unittest.main()
