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
    # Vim's crazy permissions-probing swap files
    # These take the form 4913 + 123n for n = 0, 1, 2...
    # More info:
    # https://groups.google.com/d/msg/vim_dev/sppdpElxY44/-5xZcvPRqbQJ
    # or search vim's fileio.c for "4913" (line 3704 at the time of writing)
    '4913',
    '5036',
    '5159',
    '5282',
)


def ignore_file(pathname, skip_files_re=None):
  """Report whether a file should not be watched.

  If skip_files_re is not None, then we say to ignore the path if
  pathname matches skip_files_re, in addition to looking at the
  _IGNORED_* variables above.  In that case, pathname must be relative
  to the same directory that the skip-files-re is constructed relative
  to.  (In practice, this will be the application-root directory.)
  """
  filename = os.path.basename(pathname)

  # Regardless of what skip_files_re may say, never ignore .yaml files:
  # we always need to restart if one of our configuration files changes.
  if filename.endswith('.yaml'):
    return False

  return (filename.startswith(_IGNORED_PREFIX) or
          filename.endswith(_IGNORED_FILE_SUFFIXES) or
          (skip_files_re and skip_files_re.match(pathname)))


def ignore_dir(dirpath, skip_files_re=None):

  """Report whether a directory should not be watched.

  If skip_files_re is not None, then we say to ignore the directory if
  dirpath matches skip_files_re, in addition to looking at the
  _IGNORED_* variables above.  In that case, dirpath must be relative
  to the same directory that the skip-files-re is constructed relative
  to.  (In practice, this will be the application-root directory.)
  """

  dirname = os.path.basename(dirpath)
  return (dirname.startswith(_IGNORED_PREFIX) or
          skip_files_re and skip_files_re.match(dirpath))


def _remove_pred(lst, pred):
  """Remove items from a list that match a predicate."""

  # Walk the list in reverse because once an item is deleted,
  # the indexes of any subsequent items change.
  for idx in reversed(xrange(len(lst))):
    if pred(lst[idx]):
      del lst[idx]


def skip_ignored_dirs(dirs, dirpath, skip_files_re=None):

  """Skip directories that should not be watched.

  If skip_files_re is not None, then we say to ignore directories in
  dirs that match skip_files_re, in addition to looking at the
  _IGNORED_* variables above.  In that case, dirpath must be set to
  the parent of all of the directories in dirs, and must be relative
  to the same directory that the skip-files-re is constructed relative
  to.  (In practice, this will be the application-root directory.)

  (We separate dirs and dirpath into separate variables because this
  is used in an os.walk() context.)

  Args:
     dirs: the directories to be removed.  These should be single
       directories, not paths (that is, they should not have a /).
     dirpath: the parent-path of all the dirs in 'dirs'.  For
       instance, if we wanted to test a/b/c and a/b/d, then
       dirpath would be 'a/b' (and dirs would be ['c', 'd']).
       dirpath must be relative to the same directory that holds
       the skip-files data, if skip_files_re is not None.
     skip_files_re: a regular expression to match against every
       input dirpath/dir.  If it matches, we skip that dir.
  """

  _remove_pred(dirs, lambda d: ignore_dir(os.path.join(dirpath, d),
                                          skip_files_re))


def skip_local_symlinks(roots, dirpath, directories):

  """Skip symlinks that link to another watched directory.

  Our algorithm gets confused when the same directory is watched multiple times
  due to symlinks.

  Args:
    roots: The realpath of the root of all directory trees being watched.
    dirpath: The base directory that each of the directories are in (i.e.
      the first element of a triplet obtained from os.walkpath).
    directories: A list of directories in dirpath. This list is modified so
      that any element which is a symlink to another directory is removed.
  """

  def is_local_symlink(d):
    d = os.path.join(dirpath, d)
    if not os.path.islink(d):
      return False
    d = os.path.realpath(d)
    return any(d.startswith(root) for root in roots)

  _remove_pred(directories, is_local_symlink)
