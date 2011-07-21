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


from google.net.proto2.python.public import descriptor
from google.net.proto2.python.public import message
from google.net.proto2.python.public import reflection
from google.net.proto2.proto import descriptor_pb2
import sys
try:
  __import__('google.net.rpc.python.rpc_internals_lite')
  __import__('google.net.rpc.python.pywraprpc_lite')
  rpc_internals = sys.modules.get('google.net.rpc.python.rpc_internals_lite')
  pywraprpc = sys.modules.get('google.net.rpc.python.pywraprpc_lite')
  _client_stub_base_class = rpc_internals.StubbyRPCBaseStub
except ImportError:
  _client_stub_base_class = object
try:
  __import__('google.net.rpc.python.rpcserver')
  rpcserver = sys.modules.get('google.net.rpc.python.rpcserver')
  _server_stub_base_class = rpcserver.BaseRpcServer
except ImportError:
  _server_stub_base_class = object





DESCRIPTOR = descriptor.FileDescriptor(
  name='apphosting/api/conversion/conversion_service.proto',
  package='apphosting',
  serialized_pb='\n2apphosting/api/conversion/conversion_service.proto\x12\napphosting\"\xc9\x01\n\x16\x43onversionServiceError\"\xae\x01\n\tErrorCode\x12\x06\n\x02OK\x10\x00\x12\x0b\n\x07TIMEOUT\x10\x01\x12\x13\n\x0fTRANSIENT_ERROR\x10\x02\x12\x12\n\x0eINTERNAL_ERROR\x10\x03\x12\x1a\n\x16UNSUPPORTED_CONVERSION\x10\x04\x12\x18\n\x14\x43ONVERSION_TOO_LARGE\x10\x05\x12\x18\n\x14TOO_MANY_CONVERSIONS\x10\x06\x12\x13\n\x0fINVALID_REQUEST\x10\x07\">\n\tAssetInfo\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x10\n\x04\x64\x61ta\x18\x02 \x01(\x0c\x42\x02\x08\x01\x12\x11\n\tmime_type\x18\x03 \x01(\t\"4\n\x0c\x44ocumentInfo\x12$\n\x05\x61sset\x18\x01 \x03(\x0b\x32\x15.apphosting.AssetInfo\"\xae\x01\n\x0f\x43onversionInput\x12\'\n\x05input\x18\x01 \x02(\x0b\x32\x18.apphosting.DocumentInfo\x12\x18\n\x10output_mime_type\x18\x02 \x02(\t\x12\x31\n\x04\x66lag\x18\x03 \x03(\x0b\x32#.apphosting.ConversionInput.AuxData\x1a%\n\x07\x41uxData\x12\x0b\n\x03key\x18\x01 \x02(\t\x12\r\n\x05value\x18\x02 \x01(\t\"~\n\x10\x43onversionOutput\x12@\n\nerror_code\x18\x01 \x02(\x0e\x32,.apphosting.ConversionServiceError.ErrorCode\x12(\n\x06output\x18\x02 \x01(\x0b\x32\x18.apphosting.DocumentInfo\"D\n\x11\x43onversionRequest\x12/\n\nconversion\x18\x01 \x03(\x0b\x32\x1b.apphosting.ConversionInput\"B\n\x12\x43onversionResponse\x12,\n\x06result\x18\x01 \x03(\x0b\x32\x1c.apphosting.ConversionOutput2]\n\x11\x43onversionService\x12H\n\x07\x43onvert\x12\x1d.apphosting.ConversionRequest\x1a\x1e.apphosting.ConversionResponseB@\n#com.google.appengine.api.conversion\x10\x02 \x02(\x02\x42\x13\x43onversionServicePb')



_CONVERSIONSERVICEERROR_ERRORCODE = descriptor.EnumDescriptor(
  name='ErrorCode',
  full_name='apphosting.ConversionServiceError.ErrorCode',
  filename=None,
  file=DESCRIPTOR,
  values=[
    descriptor.EnumValueDescriptor(
      name='OK', index=0, number=0,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='TIMEOUT', index=1, number=1,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='TRANSIENT_ERROR', index=2, number=2,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='INTERNAL_ERROR', index=3, number=3,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='UNSUPPORTED_CONVERSION', index=4, number=4,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='CONVERSION_TOO_LARGE', index=5, number=5,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='TOO_MANY_CONVERSIONS', index=6, number=6,
      options=None,
      type=None),
    descriptor.EnumValueDescriptor(
      name='INVALID_REQUEST', index=7, number=7,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=94,
  serialized_end=268,
)


_CONVERSIONSERVICEERROR = descriptor.Descriptor(
  name='ConversionServiceError',
  full_name='apphosting.ConversionServiceError',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _CONVERSIONSERVICEERROR_ERRORCODE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=67,
  serialized_end=268,
)


_ASSETINFO = descriptor.Descriptor(
  name='AssetInfo',
  full_name='apphosting.AssetInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='name', full_name='apphosting.AssetInfo.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='data', full_name='apphosting.AssetInfo.data', index=1,
      number=2, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value="",
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=descriptor._ParseOptions(descriptor_pb2.FieldOptions(), '\010\001')),
    descriptor.FieldDescriptor(
      name='mime_type', full_name='apphosting.AssetInfo.mime_type', index=2,
      number=3, type=9, cpp_type=9, label=1,
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
  serialized_start=270,
  serialized_end=332,
)


_DOCUMENTINFO = descriptor.Descriptor(
  name='DocumentInfo',
  full_name='apphosting.DocumentInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='asset', full_name='apphosting.DocumentInfo.asset', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
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
  serialized_start=334,
  serialized_end=386,
)


_CONVERSIONINPUT_AUXDATA = descriptor.Descriptor(
  name='AuxData',
  full_name='apphosting.ConversionInput.AuxData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='key', full_name='apphosting.ConversionInput.AuxData.key', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='value', full_name='apphosting.ConversionInput.AuxData.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
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
  serialized_start=526,
  serialized_end=563,
)

_CONVERSIONINPUT = descriptor.Descriptor(
  name='ConversionInput',
  full_name='apphosting.ConversionInput',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='input', full_name='apphosting.ConversionInput.input', index=0,
      number=1, type=11, cpp_type=10, label=2,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='output_mime_type', full_name='apphosting.ConversionInput.output_mime_type', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=unicode("", "utf-8"),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='flag', full_name='apphosting.ConversionInput.flag', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_CONVERSIONINPUT_AUXDATA, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  serialized_start=389,
  serialized_end=563,
)


_CONVERSIONOUTPUT = descriptor.Descriptor(
  name='ConversionOutput',
  full_name='apphosting.ConversionOutput',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='error_code', full_name='apphosting.ConversionOutput.error_code', index=0,
      number=1, type=14, cpp_type=8, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    descriptor.FieldDescriptor(
      name='output', full_name='apphosting.ConversionOutput.output', index=1,
      number=2, type=11, cpp_type=10, label=1,
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
  serialized_start=565,
  serialized_end=691,
)


_CONVERSIONREQUEST = descriptor.Descriptor(
  name='ConversionRequest',
  full_name='apphosting.ConversionRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='conversion', full_name='apphosting.ConversionRequest.conversion', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
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
  serialized_start=693,
  serialized_end=761,
)


_CONVERSIONRESPONSE = descriptor.Descriptor(
  name='ConversionResponse',
  full_name='apphosting.ConversionResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    descriptor.FieldDescriptor(
      name='result', full_name='apphosting.ConversionResponse.result', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
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
  serialized_start=763,
  serialized_end=829,
)

_CONVERSIONSERVICEERROR_ERRORCODE.containing_type = _CONVERSIONSERVICEERROR;
_DOCUMENTINFO.fields_by_name['asset'].message_type = _ASSETINFO
_CONVERSIONINPUT_AUXDATA.containing_type = _CONVERSIONINPUT;
_CONVERSIONINPUT.fields_by_name['input'].message_type = _DOCUMENTINFO
_CONVERSIONINPUT.fields_by_name['flag'].message_type = _CONVERSIONINPUT_AUXDATA
_CONVERSIONOUTPUT.fields_by_name['error_code'].enum_type = _CONVERSIONSERVICEERROR_ERRORCODE
_CONVERSIONOUTPUT.fields_by_name['output'].message_type = _DOCUMENTINFO
_CONVERSIONREQUEST.fields_by_name['conversion'].message_type = _CONVERSIONINPUT
_CONVERSIONRESPONSE.fields_by_name['result'].message_type = _CONVERSIONOUTPUT
DESCRIPTOR.message_types_by_name['ConversionServiceError'] = _CONVERSIONSERVICEERROR
DESCRIPTOR.message_types_by_name['AssetInfo'] = _ASSETINFO
DESCRIPTOR.message_types_by_name['DocumentInfo'] = _DOCUMENTINFO
DESCRIPTOR.message_types_by_name['ConversionInput'] = _CONVERSIONINPUT
DESCRIPTOR.message_types_by_name['ConversionOutput'] = _CONVERSIONOUTPUT
DESCRIPTOR.message_types_by_name['ConversionRequest'] = _CONVERSIONREQUEST
DESCRIPTOR.message_types_by_name['ConversionResponse'] = _CONVERSIONRESPONSE

class ConversionServiceError(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CONVERSIONSERVICEERROR



class AssetInfo(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _ASSETINFO



class DocumentInfo(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _DOCUMENTINFO



class ConversionInput(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType

  class AuxData(message.Message):
    __metaclass__ = reflection.GeneratedProtocolMessageType
    DESCRIPTOR = _CONVERSIONINPUT_AUXDATA


  DESCRIPTOR = _CONVERSIONINPUT



class ConversionOutput(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CONVERSIONOUTPUT



class ConversionRequest(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CONVERSIONREQUEST



class ConversionResponse(message.Message):
  __metaclass__ = reflection.GeneratedProtocolMessageType
  DESCRIPTOR = _CONVERSIONRESPONSE





class _ConversionService_ClientBaseStub(_client_stub_base_class):
  """Makes Stubby RPC calls to a ConversionService server."""

  __slots__ = (
      '_protorpc_Convert', '_full_name_Convert',
  )

  def __init__(self, rpc_stub):
    self._stub = rpc_stub

    self._protorpc_Convert = pywraprpc.RPC()
    self._full_name_Convert = self._stub.GetFullMethodName(
        'Convert')

  def Convert(self, request, rpc=None, callback=None, response=None):
    """Make a Convert RPC call.

    Args:
      request: a ConversionRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The ConversionResponse if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = ConversionResponse
    return self._MakeCall(rpc,
                          self._full_name_Convert,
                          'Convert',
                          request,
                          response,
                          callback,
                          self._protorpc_Convert)


class _ConversionService_ClientStub(_ConversionService_ClientBaseStub):
  __slots__ = ('_params',)
  def __init__(self, rpc_stub_parameters, service_name):
    if service_name is None:
      service_name = 'ConversionService'
    _ConversionService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, rpc_stub_parameters))
    self._params = rpc_stub_parameters


class _ConversionService_RPC2ClientStub(_ConversionService_ClientBaseStub):
  __slots__ = ()
  def __init__(self, server, channel, service_name):
    if service_name is None:
      service_name = 'ConversionService'
    if channel is not None:
      if channel.version() == 1:
        raise RuntimeError('Expecting an RPC2 channel to create the stub')
      _ConversionService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, channel))
    elif server is not None:
      _ConversionService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, pywraprpc.NewClientChannel(server)))
    else:
      raise RuntimeError('Invalid argument combination to create a stub')


class ConversionService(_server_stub_base_class):
  """Base class for ConversionService Stubby servers."""

  def __init__(self, *args, **kwargs):
    """Creates a Stubby RPC server.

    See BaseRpcServer.__init__ in rpcserver.py for detail on arguments.
    """
    if _server_stub_base_class is object:
      raise NotImplementedError('Add //net/rpc/python:rpcserver as a '
                                'dependency for Stubby server support.')
    _server_stub_base_class.__init__(self, 'apphosting.ConversionService', *args, **kwargs)

  @staticmethod
  def NewStub(rpc_stub_parameters, service_name=None):
    """Creates a new ConversionService Stubby client stub.

    Args:
      rpc_stub_parameters: an RPC_StubParameter instance.
      service_name: the service name used by the Stubby server.
    """

    if _client_stub_base_class is object:
      raise RuntimeError('Add //net/rpc/python as a dependency to use Stubby')
    return _ConversionService_ClientStub(rpc_stub_parameters, service_name)

  @staticmethod
  def NewRPC2Stub(server=None, channel=None, service_name=None):
    """Creates a new ConversionService Stubby2 client stub.

    Args:
      server: host:port or bns address.
      channel: directly use a channel to create a stub. Will ignore server
          argument if this is specified.
      service_name: the service name used by the Stubby server.
    """

    if _client_stub_base_class is object:
      raise RuntimeError('Add //net/rpc/python as a dependency to use Stubby')
    return _ConversionService_RPC2ClientStub(server, channel, service_name)

  def Convert(self, rpc, request, response):
    """Handles a Convert RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a ConversionRequest that contains the client request
      response: a ConversionResponse that should be modified to send the response
    """
    raise NotImplementedError

  def _AddMethodAttributes(self):
    """Sets attributes on Python RPC handlers.

    See BaseRpcServer in rpcserver.py for details.
    """
    rpcserver._GetHandlerDecorator(
        self.Convert.im_func,
        ConversionRequest,
        ConversionResponse,
        None,
        'none')


