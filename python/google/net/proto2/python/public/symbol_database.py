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
"""A database of Python protocol buffer generated symbols.

SymbolDatabase is the MessageFactory for messages generated at compile time,
and makes it easy to create new instances of a registered type, given only the
type's protocol buffer symbol name.

Example usage:

  db = symbol_database.SymbolDatabase()

  # Register symbols of interest, from one or multiple files.
  db.RegisterFileDescriptor(my_proto_pb2.DESCRIPTOR)
  db.RegisterMessage(my_proto_pb2.MyMessage)
  db.RegisterEnumDescriptor(my_proto_pb2.MyEnum.DESCRIPTOR)

  # The database can be used as a MessageFactory, to generate types based on
  # their name:
  types = db.GetMessages(['my_proto.proto'])
  my_message_instance = types['MyMessage']()

  # The database's underlying descriptor pool can be queried, so it's not
  # necessary to know a type's filename to be able to generate it:
  filename = db.pool.FindFileContainingSymbol('MyMessage')
  my_message_instance = db.GetMessages([filename])['MyMessage']()

  # This functionality is also provided directly via a convenience method:
  my_message_instance = db.GetSymbol('MyMessage')()
"""


from google.net.proto2.python.public import descriptor_pool
from google.net.proto2.python.public import message_factory


class SymbolDatabase(message_factory.MessageFactory):
  """A database of Python generated symbols."""

  def RegisterMessage(self, message):
    """Registers the given message type in the local database.

    Calls to GetSymbol() and GetMessages() will return messages registered here.

    Args:
      message: a message.Message, to be registered.

    Returns:
      The provided message.
    """

    desc = message.DESCRIPTOR
    self._classes[desc] = message
    self.RegisterMessageDescriptor(desc)
    return message

  def RegisterMessageDescriptor(self, message_descriptor):
    """Registers the given message descriptor in the local database.

    Args:
      message_descriptor: a descriptor.MessageDescriptor.
    """
    self.pool.AddDescriptor(message_descriptor)

  def RegisterEnumDescriptor(self, enum_descriptor):
    """Registers the given enum descriptor in the local database.

    Args:
      enum_descriptor: a descriptor.EnumDescriptor.

    Returns:
      The provided descriptor.
    """
    self.pool.AddEnumDescriptor(enum_descriptor)
    return enum_descriptor

  def RegisterServiceDescriptor(self, service_descriptor):
    """Registers the given service descriptor in the local database.

    Args:
      service_descriptor: a descriptor.ServiceDescriptor.

    Returns:
      The provided descriptor.
    """
    self.pool.AddServiceDescriptor(service_descriptor)

  def RegisterFileDescriptor(self, file_descriptor):
    """Registers the given file descriptor in the local database.

    Args:
      file_descriptor: a descriptor.FileDescriptor.

    Returns:
      The provided descriptor.
    """
    self.pool.AddFileDescriptor(file_descriptor)

  def GetSymbol(self, symbol):
    """Tries to find a symbol in the local database.

    Currently, this method only returns message.Message instances, however, if
    may be extended in future to support other symbol types.

    Args:
      symbol: A str, a protocol buffer symbol.

    Returns:
      A Python class corresponding to the symbol.

    Raises:
      KeyError: if the symbol could not be found.
    """

    return self._classes[self.pool.FindMessageTypeByName(symbol)]

  def GetMessages(self, files):

    """Gets all registered messages from a specified file.

    Only messages already created and registered will be returned; (this is the
    case for imported _pb2 modules)
    But unlike MessageFactory, this version also returns already defined nested
    messages, but does not register any message extensions.

    Args:
      files: The file names to extract messages from.

    Returns:
      A dictionary mapping proto names to the message classes.

    Raises:
      KeyError: if a file could not be found.
    """

    def _GetAllMessages(desc):
      """Walk a message Descriptor and recursively yields all message names."""
      yield desc
      for msg_desc in desc.nested_types:
        for nested_desc in _GetAllMessages(msg_desc):
          yield nested_desc

    result = {}
    for file_name in files:
      file_desc = self.pool.FindFileByName(file_name)
      for msg_desc in file_desc.message_types_by_name.values():
        for desc in _GetAllMessages(msg_desc):
          try:
            result[desc.full_name] = self._classes[desc]
          except KeyError:

            pass
    return result


_DEFAULT = SymbolDatabase(pool=descriptor_pool.Default())


def Default():
  """Returns the default SymbolDatabase."""
  return _DEFAULT
