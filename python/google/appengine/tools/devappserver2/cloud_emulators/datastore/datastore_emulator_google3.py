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
"""Helper methods for GAE SDK to invoke Cloud Datastore emulator in google."""

import glob
import os
import shutil
import tempfile
import zipfile
from google.pyglib import resources


def prepare_google_command():
  """Preparations for running emulator in google.

  This includes:
  - Finding(and possibly extracting) emulator zip.
  - Finding(and possibly extracting) java binary for running the emulator jar.

  Returns:
    A string representing the path to an executable script that invokes the
      emulator.

  Raises:
    ValueError: Either emulator zip or java binary is missing.
  """
  emulator_zip_relpath = (
      'google/java/com/google/cloud/datastore/emulator/opensource/'
      'cloud-datastore-emulator.zip')
  jdk_relpath_common = 'google/third_party/java/jdk'

  # When running from .par, GetARootDirWithAllResources extracts resources.
  root_dir = resources.GetARootDirWithAllResources(
      lambda x: x.startswith(emulator_zip_relpath) or x.startswith(  # pylint: disable=g-long-lambda
          jdk_relpath_common), True)
  emulator_zip_path = os.path.join(root_dir, emulator_zip_relpath)
  if not os.path.exists(emulator_zip_path):
    raise ValueError('Missing //java/com/google/cloud/datastore/emulator/'
                     'opensource:cloud-datastore-emulator data dependency.')

  # Depending on --java_base, we may see jdk-64 or jdk7-64 in the glob below.
  java_path_pattern = os.path.join(
      root_dir, jdk_relpath_common, 'jdk*-64/bin/java')
  java_paths = glob.glob(java_path_pattern)
  if not java_paths:
    raise ValueError('Missing //third_party/java/jdk:java data dependency.')
  os.environ['JAVA'] = java_paths[0]

  working_directory = (
      os.getenv('TEST_TMPDIR') if os.environ.get('TEST_TMPDIR')
      else tempfile.mkdtemp())
  emulator_path = os.path.join(working_directory, 'cloud-datastore-emulator')
  if os.path.exists(emulator_path):
    shutil.rmtree(emulator_path)
  zipped_file = zipfile.ZipFile(emulator_zip_path)
  zipped_file.extractall(working_directory)
  emulator_cmd = os.path.join(emulator_path, 'cloud_datastore_emulator')
  os.chmod(emulator_cmd, 0700)  # executable
  return emulator_cmd
