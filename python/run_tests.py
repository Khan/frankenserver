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
"""Runs the unit test suite for devappserver2."""



import argparse
import cStringIO
import logging
import os.path
import random
import sys
import unittest

DIR_PATH = os.path.dirname(__file__)

TEST_LIBRARY_PATHS = [
    DIR_PATH,
    os.path.join(DIR_PATH, 'lib', 'cherrypy'),
    os.path.join(DIR_PATH, 'lib', 'fancy_urllib'),
    os.path.join(DIR_PATH, 'lib', 'yaml-3.10'),
    os.path.join(DIR_PATH, 'lib', 'antlr3'),
    os.path.join(DIR_PATH, 'lib', 'concurrent'),
    os.path.join(DIR_PATH, 'lib', 'ipaddr'),
    os.path.join(DIR_PATH, 'lib', 'jinja2-2.6'),
    os.path.join(DIR_PATH, 'lib', 'webob-1.2.3'),
    os.path.join(DIR_PATH, 'lib', 'webapp2-2.5.1'),
    os.path.join(DIR_PATH, 'lib', 'mox'),
    os.path.join(DIR_PATH, 'lib', 'protorpc-1.0'),
    os.path.join(DIR_PATH, 'lib', 'httplib2'),
    os.path.join(DIR_PATH, 'lib', 'oauth2client'),
    os.path.join(DIR_PATH, 'lib', 'pyasn1'),
    os.path.join(DIR_PATH, 'lib', 'pyasn1_modules'),
    os.path.join(DIR_PATH, 'lib', 'rsa'),
    os.path.join(DIR_PATH, 'lib', 'portpicker'),
    os.path.join(DIR_PATH, 'lib', 'grpcio-1.9.1'),
]


def main():
  sys.path.extend(TEST_LIBRARY_PATHS)

  parser = argparse.ArgumentParser(
      description='Run the devappserver2 test suite.')
  parser.add_argument(
      '--frankenserver', action='store_true',
      help='Run only tests added by frankenserver -- these should all pass!')
  parser.add_argument(
      'tests', nargs='*',
      help='The fully qualified names of the tests to run (e.g. '
      'google.appengine.tools.devappserver2.api_server_test). If not given '
      'then the full test suite will be run.')

  args = parser.parse_args()

  loader = unittest.TestLoader()
  if args.frankenserver:
    # TODO(benkraft): Are there other frankenserver-added tests we should run?
    tests = loader.discover(
        os.path.join(
            DIR_PATH,
            'google/appengine/tools/devappserver2/datastore_translator'),
        '*_test.py')
  elif args.tests:
    tests = loader.loadTestsFromNames(args.tests)
  else:
    tests = loader.discover(
        os.path.join(DIR_PATH, 'google/appengine/tools/devappserver2'),
        '*_test.py')

  runner = unittest.TextTestRunner(verbosity=2)
  runner.run(tests)

if __name__ == '__main__':
  main()
