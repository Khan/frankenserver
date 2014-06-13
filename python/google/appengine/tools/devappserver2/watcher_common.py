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
  r'^(.+)\.py[co]$',  # Python temporaries
  r'^(.+)~$',         # Backups
  r'^(.+)#$',         # Emacs
  r'^(.+)\.sw[po]$',  # Vim

  r'^(.+)\.sqlite-journal$',  # SQLite journal file

  # Specific to Khan Academy
  r'^(.*/)?genfiles(/.*)?$'
]))


def ignore_path(path, skip_files_re=None):
  """Report whether a path should not be watched."""
  assert not os.path.isabs(path)

  # We always want to reload to pick up configuration changes in yaml files.
  if path.endswith('.yaml'):
    return False

  if _IGNORED_RE.match(path):
    return True

  if skip_files_re:
    # We must check all components of the path because a skip_files entry like
    # '^deploy$' should cause us to ignore files like 'deploy/deploy.py'.
    while path:
      if skip_files_re.match(path):
        return True
      path = os.path.dirname(path)

  return False
