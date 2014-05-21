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
"""Common functionality for file watchers."""

import os
import re


# A mapping of module names to regular expressions. Each regular expression
# represents the skip_files directive in that module's yaml configuration file.
_SKIP_FILES_RES = {}


# A regular expression of paths that should be globally ignored.
# TODO(dylan): Use re.escape(os.sep) instead of '/'
_IGNORED_RE = re.compile('|'.join([
  # From _IGNORED_DIRS
  r'^(.*/)?\.git(/.*)?$',  # Git
  r'^(.*/)?\.hg(/.*)?$',   # Mercurial
  r'^(.*/)?\.svn(/.*)?$',  # Subversion

  # From frankenserver's _IGNORED_FILE_PREFIXES
  r'^(.*/)?\.#([^/]*)$',  # Emacs

  # From _IGNORED_FILE_SUFFIXES
  r'\.py[co]$',  # Python temporaries
  r'~$',         # Backups
  r'#$',         # Emacs
  r'\.sw[po]$',  # Vim

  # Specific to Khan Academy
  r'^(.*/)?genfiles(/.*)?$'
]))


def set_skip_files_regexp(module, regexp):
  """Set a new regexp that represents a module's skip_files directive."""
  _SKIP_FILES_RES[module] = regexp


def ignore_path(path, module='default'):
  """Report whether a path should not be watched.

  TODO(dylan): Have the watchers pass in the right module parameter for the
  current request to make module-specific file skipping work.
  """
  assert not os.path.isabs(path)

  # We always want to reload to pick up configuration changes in yaml files.
  if path.endswith('.yaml'):
    return False

  if _IGNORED_RE.match(path):
    return True

  if module in _SKIP_FILES_RES:
    # We must check all components of the path because a skip_files entry like
    # '^deploy$' should cause us to ignore files like 'deploy/deploy.py'.
    while path:
      if _SKIP_FILES_RES[module].match(path):
        return True
      path = os.path.dirname(path)

  return False
