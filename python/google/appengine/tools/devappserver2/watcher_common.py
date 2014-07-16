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


# A prefix for files and directories that we should not watch at all.
_IGNORED_PREFIX = '.'
# File suffixes that should be ignored.
_IGNORED_FILE_SUFFIXES = (
    # Python temporaries
    '.pyc',
    '.pyo',
    # Backups
    '~',
    # Emacs
    '#',
    # Vim
    '.swp',
    '.swo',
)


def ignore_file(filename):
  """Report whether a file should not be watched."""
  return (
      filename.startswith(_IGNORED_PREFIX) or
      any(filename.endswith(suffix) for suffix in _IGNORED_FILE_SUFFIXES))


def _remove_pred(lst, pred):
  """Remove items from a list that match a predicate."""

  # Walk the list in reverse because once an item is deleted,
  # the indexes of any subsequent items change.
  for idx in reversed(xrange(len(lst))):
    if pred(lst[idx]):
      del lst[idx]


def remove_ignored_dirs(dirs):
  """Remove directories from dirs that should not be watched."""

  _remove_pred(dirs, lambda d: d.startswith(_IGNORED_PREFIX))
