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
"""Utility class for testbed only used for py_test.

This file wraps imports and attributes that testbed would need for accessing
api_server and datastore_emulator.
testbed uses cloud datastore emulator if and only if emulator_util can be
import by it.
"""

import atexit
import datetime
import functools
import os
import subprocess
import sys
import tempfile
import google

from google.appengine.tools.devappserver2 import constants


def _get_cloud_sdk_platform_dir():
  """Returns the path of google-cloud-sdk/platform directory."""
  res = os.path.dirname(os.path.realpath(__file__))




  for _ in range(5):
    res = os.path.dirname(res)
  if not os.path.exists(res):
    raise OSError('Cannot locate Google Cloud SDK. Please make sure you are '
                  'using testbed from Google Cloud SDK.')
  return res


def _get_emulator_cmd_inside_cloud_sdk():
  """Try to get the path to datastore emulator in cloud sdk.

  Returns:
    A string representing the path to the Cloud Datastore Emulator shell script.

  Raises:
    OSError: cannot find Datastore Emulator.
  """
  emulator_script = (
      'cloud_datastore_emulator.cmd' if sys.platform.startswith('win')
      else 'cloud_datastore_emulator')
  res = os.path.join(
      _get_cloud_sdk_platform_dir(), 'cloud-datastore-emulator',
      emulator_script)
  if not os.path.exists(res):
    raise OSError('Cannot find Cloud Datastore Emulator. Please make sure you '
                  'installed it with Google Cloud SDK.')
  return res


def _get_api_server_cmd():
  """Get the command to invoke api_server.

  Returns:
    A list of strings representing the command.

  Raises:
    OSError: cannot find api server.
  """











  api_server_path = os.path.join(_get_cloud_sdk_platform_dir(),
                                 'google_appengine', 'api_server.py')
  if not os.path.exists(api_server_path):
    raise OSError('Cannot find api_server.py. Please make sure you have '
                  'installed gcloud app Python Extensions.')
  return [sys.executable, api_server_path,
          '--support_datastore_emulator',
          '--datastore_emulator_cmd',
          _get_emulator_cmd_inside_cloud_sdk()]
































def get_port(line):
  """Get port number out of a line like "some message: localhost:[port]."""
  stripped = line.strip()
  separator_index = stripped.rfind(':')
  return int(stripped[separator_index+1:])


def read_lines_until(in_file, stop_string, timeout=30):
  """Read lines in an input file until stop_string is found."""
  lines = []
  t1 = datetime.datetime.now()
  while True:
    line = in_file.readline()
    if line:
      lines.append(line)
      if constants.GRPC_API_SERVER_STARTING_MSG in line:
        return lines
    else:
      t2 = datetime.datetime.now()
      if (t2 - t1).total_seconds() <= timeout:
        continue
      raise AssertionError('Did not see string "%s" in input: %s' %
                           (stop_string, ''.join(lines)))





def setup_api_server():
  """Launches api_server.

  Returns:
    Two integers, first is the port number for api_server's http endpoint,
    second is the port number of the Cloud Datastore Emulator.
  """
  api_server_output = tempfile.NamedTemporaryFile()
  api_server_proc = subprocess.Popen(
      _get_api_server_cmd(),
      stdout=api_server_output,
      stderr=subprocess.STDOUT)

  with open(api_server_output.name, 'r') as in_file:


    lines = read_lines_until(in_file, constants.GRPC_API_SERVER_STARTING_MSG)
  atexit.register(api_server_proc.terminate)

  api_server_starting_line = next(
      x for x in lines if constants.API_SERVER_STARTING_MSG in x)
  datastore_emulator_starting_line = next(
      x for x in lines if constants.DATASTORE_EMULATOR_STARTING_MSG in x)
  return (get_port(api_server_starting_line),
          get_port(datastore_emulator_starting_line))
