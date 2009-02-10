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

"""Stub replacement for Python's imp module."""


import os
import sys


PY_SOURCE, PY_COMPILED, C_EXTENSION = 1, 2, 3
PKG_DIRECTORY, C_BUILTIN, PY_FROZEN = 5, 6, 7


def get_magic():
  return '\0\0\0\0'


def get_suffixes():
  return [('.py', 'U', PY_SOURCE)]


def new_module(name):
  return type(sys.modules[__name__])(name)


def lock_held():
  """Return False since threading is not supported."""
  return False

def acquire_lock():
  """Acquiring the lock is a no-op since no threading is supported."""
  pass

def release_lock():
  """There is no lock to release since acquiring is a no-op when there is no
  threading."""
  pass


def is_builtin(name):
  return name in sys.builtin_module_names


def is_frozen(name):
  return False


class NullImporter(object):

  def __init__(self, path_string):
    if not path_string:
      raise ImportError("empty pathname")
    elif os.path.isdir(path_string):
      raise ImportError("existing directory")

  def find_module(self, fullname):
    return None
