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






"""Contains a metaclass and helper functions used to create
protocol message classes from Descriptor objects at runtime.

Recall that a metaclass is the "type" of a class.
(A class is to a metaclass what an instance is to a class.)

In this case, we use the GeneratedProtocolMessageType metaclass
to inject all the useful functionality into the classes
output by the protocol compiler at compile-time.

The upshot of all this is that the real implementation
details for ALL pure-Python protocol buffers are *here in
this file*.
"""




from google.net.proto2.python.internal import api_implementation
from google.net.proto2.python.public import message


if api_implementation.Type() == 'cpp':
  from google.net.proto2.python.internal.cpp import cpp_message as message_impl
else:
  from google.net.proto2.python.internal import python_message as message_impl



GeneratedProtocolMessageType = message_impl.GeneratedProtocolMessageType

MESSAGE_CLASS_CACHE = {}



def ParseMessage(descriptor, byte_str):
  """Generate a new Message instance from this Descriptor and a byte string.

  DEPRECATED: ParseMessage is deprecated because it is using MakeClass().
  Please use MessageFactory.GetPrototype() instead.

  Args:
    descriptor: Protobuf Descriptor object
    byte_str: Serialized protocol buffer byte string

  Returns:
    Newly created protobuf Message object.
  """
  result_class = MakeClass(descriptor)
  new_msg = result_class()
  new_msg.ParseFromString(byte_str)
  return new_msg



def MakeClass(descriptor):
  """Construct a class object for a protobuf described by descriptor.

  DEPRECATED: use MessageFactory.GetPrototype() instead.
  This function will lead to duplicate message classes, which won't play well
  with extensions. Message factory info is also missing.

  Composite descriptors are handled by defining the new class as a member of the
  parent class, recursing as deep as necessary.
  This is the dynamic equivalent to:

  class Parent(message.Message):
    __metaclass__ = GeneratedProtocolMessageType
    DESCRIPTOR = descriptor
    class Child(message.Message):
      __metaclass__ = GeneratedProtocolMessageType
      DESCRIPTOR = descriptor.nested_types[0]

  Sample usage:
    file_descriptor = descriptor_pb2.FileDescriptorProto()
    file_descriptor.ParseFromString(proto2_string)
    msg_descriptor = descriptor.MakeDescriptor(file_descriptor.message_type[0])
    msg_class = reflection.MakeClass(msg_descriptor)
    msg = msg_class()

  Args:
    descriptor: A descriptor.Descriptor object describing the protobuf.
  Returns:
    The Message class object described by the descriptor.
  """
  if descriptor in MESSAGE_CLASS_CACHE:
    return MESSAGE_CLASS_CACHE[descriptor]

  attributes = {}
  for name, nested_type in descriptor.nested_types_by_name.items():
    attributes[name] = MakeClass(nested_type)

  attributes[GeneratedProtocolMessageType._DESCRIPTOR_KEY] = descriptor

  result = GeneratedProtocolMessageType(
      str(descriptor.name), (message.Message,), attributes)
  MESSAGE_CLASS_CACHE[descriptor] = result
  return result
