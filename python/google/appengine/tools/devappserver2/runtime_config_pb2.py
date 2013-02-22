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



from google.net.proto2.python.public import descriptor as _descriptor
from google.net.proto2.python.public import message as _message
from google.net.proto2.python.public import reflection as _reflection
from google.net.proto2.proto import descriptor_pb2





DESCRIPTOR = _descriptor.FileDescriptor(
  name='apphosting/tools/devappserver2/scrubbed/runtime_config.proto',
  package='apphosting.tools.devappserver2',
  serialized_pb='\n<apphosting/tools/devappserver2/scrubbed/runtime_config.proto\x12\x1e\x61pphosting.tools.devappserver2\"\xdf\x02\n\x06\x43onfig\x12\x0e\n\x06\x61pp_id\x18\x01 \x02(\x0c\x12\x12\n\nversion_id\x18\x02 \x02(\x0c\x12\x18\n\x10\x61pplication_root\x18\x03 \x02(\x0c\x12\x19\n\nthreadsafe\x18\x04 \x01(\x08:\x05\x66\x61lse\x12\x10\n\x08\x61pi_port\x18\x05 \x01(\x05\x12:\n\tlibraries\x18\x06 \x03(\x0b\x32\'.apphosting.tools.devappserver2.Library\x12\x16\n\nskip_files\x18\x07 \x01(\t:\x02^$\x12\x18\n\x0cstatic_files\x18\x08 \x01(\t:\x02^$\x12\x38\n\x07\x65nviron\x18\n \x03(\x0b\x32\'.apphosting.tools.devappserver2.Environ\x12\x42\n\x10\x63loud_sql_config\x18\x0b \x01(\x0b\x32(.apphosting.tools.devappserver2.CloudSQL\"t\n\x08\x43loudSQL\x12\x12\n\nmysql_host\x18\x01 \x02(\t\x12\x12\n\nmysql_port\x18\x02 \x02(\x05\x12\x12\n\nmysql_user\x18\x03 \x02(\t\x12\x16\n\x0emysql_password\x18\x04 \x02(\t\x12\x14\n\x0cmysql_socket\x18\x05 \x01(\t\"(\n\x07Library\x12\x0c\n\x04name\x18\x01 \x02(\t\x12\x0f\n\x07version\x18\x02 \x02(\t\"%\n\x07\x45nviron\x12\x0b\n\x03key\x18\x01 \x02(\x0c\x12\r\n\x05value\x18\x02 \x02(\x0c\x42\x02 \x02')




_CONFIG = _descriptor.Descriptor(
  name='Config',
  full_name='apphosting.tools.devappserver2.Config',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='app_id', full_name='apphosting.tools.devappserver2.Config.app_id', index=0,
      number=1, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='version_id', full_name='apphosting.tools.devappserver2.Config.version_id', index=1,
      number=2, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='application_root', full_name='apphosting.tools.devappserver2.Config.application_root', index=2,
      number=3, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='threadsafe', full_name='apphosting.tools.devappserver2.Config.threadsafe', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=True, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='api_port', full_name='apphosting.tools.devappserver2.Config.api_port', index=4,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='libraries', full_name='apphosting.tools.devappserver2.Config.libraries', index=5,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='skip_files', full_name='apphosting.tools.devappserver2.Config.skip_files', index=6,
      number=7, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("^$", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='static_files', full_name='apphosting.tools.devappserver2.Config.static_files', index=7,
      number=8, type=9, cpp_type=9, label=1,
      has_default_value=True, default_value=unicode("^$", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='environ', full_name='apphosting.tools.devappserver2.Config.environ', index=8,
      number=10, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='cloud_sql_config', full_name='apphosting.tools.devappserver2.Config.cloud_sql_config', index=9,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=97,
  serialized_end=448,
)


_CLOUDSQL = _descriptor.Descriptor(
  name='CloudSQL',
  full_name='apphosting.tools.devappserver2.CloudSQL',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='mysql_host', full_name='apphosting.tools.devappserver2.CloudSQL.mysql_host', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mysql_port', full_name='apphosting.tools.devappserver2.CloudSQL.mysql_port', index=1,
      number=2, type=5, cpp_type=1, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mysql_user', full_name='apphosting.tools.devappserver2.CloudSQL.mysql_user', index=2,
      number=3, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mysql_password', full_name='apphosting.tools.devappserver2.CloudSQL.mysql_password', index=3,
      number=4, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mysql_socket', full_name='apphosting.tools.devappserver2.CloudSQL.mysql_socket', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=450,
  serialized_end=566,
)


_LIBRARY = _descriptor.Descriptor(
  name='Library',
  full_name='apphosting.tools.devappserver2.Library',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='apphosting.tools.devappserver2.Library.name', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='version', full_name='apphosting.tools.devappserver2.Library.version', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=568,
  serialized_end=608,
)


_ENVIRON = _descriptor.Descriptor(
  name='Environ',
  full_name='apphosting.tools.devappserver2.Environ',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='key', full_name='apphosting.tools.devappserver2.Environ.key', index=0,
      number=1, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='value', full_name='apphosting.tools.devappserver2.Environ.value', index=1,
      number=2, type=12, cpp_type=9, label=2,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=610,
  serialized_end=647,
)

_CONFIG.fields_by_name['libraries'].message_type = _LIBRARY
_CONFIG.fields_by_name['environ'].message_type = _ENVIRON
_CONFIG.fields_by_name['cloud_sql_config'].message_type = _CLOUDSQL
DESCRIPTOR.message_types_by_name['Config'] = _CONFIG
DESCRIPTOR.message_types_by_name['CloudSQL'] = _CLOUDSQL
DESCRIPTOR.message_types_by_name['Library'] = _LIBRARY
DESCRIPTOR.message_types_by_name['Environ'] = _ENVIRON

class Config(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CONFIG



class CloudSQL(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CLOUDSQL



class Library(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _LIBRARY



class Environ(_message.Message):
  __metaclass__ = _reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ENVIRON




DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(descriptor_pb2.FileOptions(), ' \002')

