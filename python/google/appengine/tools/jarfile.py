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
"""Code for handling Java jar files.

Jar files are just zip files with a particular interpretation for certain files
in the zip under the META-INF/ directory. So we can read and write them using
the standard zipfile module.

The specification for jar files is at
http://docs.oracle.com/javase/7/docs/technotes/guides/jar/jar.html
"""
from __future__ import with_statement


import os
import sys
import zipfile


_MANIFEST_NAME = 'META-INF/MANIFEST.MF'


class Error(Exception):
  pass


class InvalidJarError(Error):
  pass


class JarWriteError(Error):
  pass


class Manifest(object):
  """The parsed manifest from a jar file.

  Attributes:
    main_section: a dict representing the main (first) section of the manifest.
      Each key is a string that is an attribute, such as 'Manifest-Version', and
      the corresponding value is a string that is the value of the attribute,
      such as '1.0'.
    sections: a dict representing the other sections of the manifest. Each key
      is a string that is the value of the 'Name' attribute for the section,
      and the corresponding value is a dict like the main_section one, for the
      other attributes.
  """

  def __init__(self, main_section, sections):
    self.main_section = main_section
    self.sections = sections


def ReadManifest(jar_file_name):
  """Read and parse the manifest out of the given jar.

  Args:
    jar_file_name: the name of the jar from which the manifest is to be read.

  Returns:
    A parsed Manifest object, or None if the jar has no manifest.

  Raises:
    IOError: if the jar does not exist or cannot be read.
  """
  with zipfile.ZipFile(jar_file_name) as jar:
    try:
      manifest_string = jar.read(_MANIFEST_NAME)
    except KeyError:
      return None
    return _ParseManifest(manifest_string)


def _ParseManifest(manifest_string):
  """Parse a Manifest object out of the given string.

  Args:
    manifest_string: a str or unicode that is the manifest contents.

  Returns:
    A Manifest object parsed out of the string.

  Raises:
    InvalidJarError: if the manifest is not well-formed.
  """

  manifest_string = '\n'.join(manifest_string.splitlines()).rstrip('\n')
  section_strings = manifest_string.split('\n\n')
  parsed_sections = [_ParseManifestSection(s) for s in section_strings]
  main_section = parsed_sections[0]
  try:
    sections = dict((entry['Name'], entry) for entry in parsed_sections[1:])
  except KeyError:
    raise InvalidJarError('Manifest entry has no Name attribute: %s' % entry)
  return Manifest(main_section, sections)


def _ParseManifestSection(section):
  """Parse a dict out of the given manifest section string.

  Args:
    section: a str or unicode that is the manifest section. It looks something
      like this (without the >):
      > Name: section-name
      > Some-Attribute: some value
      > Another-Attribute: another value

  Returns:
    A dict where the keys are the attributes (here, 'Name', 'Some-Attribute',
    'Another-Attribute'), and the values are the corresponding attribute values.

  Raises:
    InvalidJarError: if the manifest section is not well-formed.
  """

  section = section.replace('\n ', '')
  try:
    return dict(line.split(': ', 1) for line in section.split('\n'))
  except ValueError:
    raise InvalidJarError('Invalid manifest %r' % section)


def Make(input_directory, output_directory, base_name,
         maximum_size=sys.maxint,
         include_predicate=lambda name: True):
  """Makes one or more jars.

  Args:
    input_directory: the root of the directory hierarchy from which files will
      be put in the jar.
    output_directory: the directory into which the output jars will be put.
    base_name: the name to be used for each output jar. If the name is 'foo'
      then each jar will be called 'foo-nnnn.jar', where nnnn is a sequence of
      digits.
    maximum_size: the maximum allowed total uncompressed size of the files in
      any given jar.
    include_predicate: a function that is called once for each file in the
      directory hierarchy. It is given the absolute path name of the file, and
      must return a true value if the file is to be included.
  """
  _Make(input_directory, output_directory, base_name, maximum_size,
        include_predicate)


class _Make(object):
  """Makes one or more jars when it is constructed."""

  def __init__(self, input_directory, output_directory, base_name,
               maximum_size=sys.maxint,
               include_predicate=lambda name: True):
    self.base_name = base_name
    self.input_directory = input_directory
    self.output_directory = output_directory.rstrip(r'\/')
    self.maximum_size = maximum_size
    self.include_predicate = include_predicate

    if not os.path.exists(self.output_directory):
      os.makedirs(self.output_directory)
    elif not os.path.isdir(self.output_directory):
      raise JarWriteError('Not a directory: %s' % self.output_directory)




    self.current_jar = None
    self.current_jar_size = 0
    self.jar_suffix = 0
    self._Write('')
    if self.current_jar:
      self.current_jar.close()

  def _Write(self, relative_dir):





    absolute_dir = os.path.join(self.input_directory, relative_dir)
    for entry in sorted(os.listdir(absolute_dir)):
      absolute_entry = os.path.join(absolute_dir, entry)
      if os.path.isdir(absolute_entry):
        self._Write(os.path.join(relative_dir, entry).replace(os.sep, '/'))
      elif os.path.isfile(absolute_entry):
        self._WriteEntry(relative_dir, entry, absolute_entry)
      else:
        raise JarWriteError(
            'Item %s is neither a file nor a directory' % absolute_entry)

  def _WriteEntry(self, relative_dir, entry, absolute_entry):
    if not self.include_predicate(absolute_entry):
      return
    size = os.path.getsize(absolute_entry)
    if size > self.maximum_size:
      raise JarWriteError(
          'File %s has size %d which is bigger than the maximum '
          'jar size %d' % (absolute_entry, size, self.maximum_size))
    if self.current_jar_size + size > self.maximum_size:
      self.current_jar.close()
      self.current_jar = None
    if not self.current_jar:
      jar_name = '%s-%04d.jar' % (self.base_name, self.jar_suffix)
      self.jar_suffix += 1
      full_jar_name = os.path.join(self.output_directory, jar_name)
      self.current_jar = zipfile.ZipFile(
          full_jar_name, 'w', zipfile.ZIP_DEFLATED)
      self.current_jar_size = 0
    self.current_jar_size += size
    entry_name = relative_dir + '/' + entry
    self.current_jar.write(absolute_entry, entry_name)
