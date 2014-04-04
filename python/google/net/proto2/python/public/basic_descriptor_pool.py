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
"""A minimal DescriptorPool implementation.

BasicDescriptorPool is a DescriptorPool with no underlying DescriptorDatabase.
This makes it suitable for use with SymbolDatabase, since the messages
registered there are not generated via a DescriptorDatabase.
"""


def _NormalizeFullyQualifiedName(name):
  """Remove leading period from fully-qualified type name.

  Sometimes the proto generator prepends a period (.) in front of fully
  qualified packages, but this isn't consistent and varies depending on if you
  are using a pre-compiled file descriptor proto, one from the proto file
  parser, or one from other dynamic sources. This function normalizes these
  names by removing the leading period.

  Args:
    name: A str, the fully-qualified symbol name.

  Returns:
    A str, the normalized fully-qualified symbol name.
  """
  return name.lstrip('.')


class BasicDescriptorPool(object):
  """A pool of related Descriptor, EnumDescriptor and FileDescriptors."""

  def __init__(self):
    """Initializes a Pool of proto buffs."""
    self._descriptors = {}
    self._enum_descriptors = {}
    self._file_descriptors = {}

  def AddMessage(self, desc):
    """Adds a Descriptor to the pool, non-recursively.

    If the Descriptor contains nested messages or enums, the caller must
    explicitly register them. This method also registers the FileDescriptor
    associated with the message.

    Args:
      desc: A Descriptor.
    """

    self._descriptors[desc.full_name] = desc
    self.AddFile(desc.file)

  def AddEnum(self, enum_desc):
    """Adds an EnumDescriptor to the pool.

    This method also registers the FileDescriptor associated with the message.

    Args:
      enum_desc: An EnumDescriptor.
    """

    self._enum_descriptors[enum_desc.full_name] = enum_desc
    self.AddFile(enum_desc.file)

  def AddFile(self, file_desc):
    """Adds a FileDescriptor to the pool, non-recursively.

    If the FileDescriptor contains messages or enums, the caller must explicitly
    register them.

    Args:
      file_desc: A FileDescriptor.
    """

    self._file_descriptors[file_desc.name] = file_desc

  def FindFileByName(self, file_name):
    """Gets a FileDescriptor by file name.

    Args:
      file_name: The path to the file to get a descriptor for.

    Returns:
      A FileDescriptor for the named file.

    Raises:
      KeyError: if the file can not be found in the pool.
    """

    return self._file_descriptors[file_name]

  def FindFileContainingSymbol(self, symbol):
    """Gets the FileDescriptor for the file containing the specified symbol.

    Args:
      symbol: The name of the symbol to search for.

    Returns:
      A FileDescriptor that contains the specified symbol.

    Raises:
      KeyError: if the file can not be found in the pool.
    """

    symbol = _NormalizeFullyQualifiedName(symbol)
    try:
      return self._descriptors[symbol].file
    except KeyError:
      return self._enum_descriptors[symbol].file

  def FindMessageTypeByName(self, full_name):
    """Loads the named descriptor from the pool.

    Args:
      full_name: The full name of the descriptor to load.

    Returns:
      The descriptor for the named type.
    """

    full_name = _NormalizeFullyQualifiedName(full_name)
    return self._descriptors[full_name]

  def FindEnumTypeByName(self, full_name):
    """Loads the named enum descriptor from the pool.

    Args:
      full_name: The full name of the enum descriptor to load.

    Returns:
      The enum descriptor for the named type.
    """

    full_name = _NormalizeFullyQualifiedName(full_name)
    return self._enum_descriptors[full_name]
