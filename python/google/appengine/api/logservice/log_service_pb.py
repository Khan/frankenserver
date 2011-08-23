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



from google.net.proto import ProtocolBuffer
import array
import base64
import dummy_thread as thread
try:
  from google3.net.proto import _net_proto___parse__python
except ImportError:
  _net_proto___parse__python = None
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

__pychecker__ = """maxreturns=0 maxbranches=0 no-callinit
                   unusednames=printElemNumber,debug_strs no-special"""

from google.appengine.api.api_base_pb import *
import google.appengine.api.api_base_pb
class FlushRequest(ProtocolBuffer.ProtocolMessage):
  has_logs_ = 0
  logs_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def logs(self): return self.logs_

  def set_logs(self, x):
    self.has_logs_ = 1
    self.logs_ = x

  def clear_logs(self):
    if self.has_logs_:
      self.has_logs_ = 0
      self.logs_ = ""

  def has_logs(self): return self.has_logs_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_logs()): self.set_logs(x.logs())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.FlushRequest', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.FlushRequest')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.FlushRequest')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.FlushRequest', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.FlushRequest', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.FlushRequest', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_logs_ != x.has_logs_: return 0
    if self.has_logs_ and self.logs_ != x.logs_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_logs_): n += 1 + self.lengthString(len(self.logs_))
    return n

  def ByteSizePartial(self):
    n = 0
    if (self.has_logs_): n += 1 + self.lengthString(len(self.logs_))
    return n

  def Clear(self):
    self.clear_logs()

  def OutputUnchecked(self, out):
    if (self.has_logs_):
      out.putVarInt32(10)
      out.putPrefixedString(self.logs_)

  def OutputPartial(self, out):
    if (self.has_logs_):
      out.putVarInt32(10)
      out.putPrefixedString(self.logs_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_logs(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_logs_: res+=prefix+("logs: %s\n" % self.DebugFormatString(self.logs_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  klogs = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "logs",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChdhcHBob3N0aW5nLkZsdXNoUmVxdWVzdBMaBGxvZ3MgASgCMAk4ARS6Ab0MCithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvEgphcHBob3N0aW5nGh1hcHBob3N0aW5nL2FwaS9hcGlfYmFzZS5wcm90byIcCgxGbHVzaFJlcXVlc3QSDAoEbG9ncxgBIAEoDCIiChBTZXRTdGF0dXNSZXF1ZXN0Eg4KBnN0YXR1cxgBIAIoCSIfCglMb2dPZmZzZXQSEgoKcmVxdWVzdF9pZBgBIAEoCSI7CgdMb2dMaW5lEgwKBHRpbWUYASACKAMSDQoFbGV2ZWwYAiACKAUSEwoLbG9nX21lc3NhZ2UYAyACKAki1wUKClJlcXVlc3RMb2cSDgoGYXBwX2lkGAEgAigJEhIKCnZlcnNpb25faWQYAiACKAkSEgoKcmVxdWVzdF9pZBgDIAIoCRIKCgJpcBgEIAIoCRIQCghuaWNrbmFtZRgFIAEoCRISCgpzdGFydF90aW1lGAYgAigDEhAKCGVuZF90aW1lGAcgAigDEg8KB2xhdGVuY3kYCCACKAMSDwoHbWN5Y2xlcxgJIAIoAxIOCgZtZXRob2QYCiACKAkSEAoIcmVzb3VyY2UYCyACKAkSFAoMaHR0cF92ZXJzaW9uGAwgAigJEg4KBnN0YXR1cxgNIAIoBRIVCg1yZXNwb25zZV9zaXplGA4gAigDEhAKCHJlZmVycmVyGA8gASgJEhIKCnVzZXJfYWdlbnQYECABKAkSFQoNdXJsX21hcF9lbnRyeRgRIAIoCRIQCghjb21iaW5lZBgSIAIoCRITCgthcGlfbWN5Y2xlcxgTIAEoAxIMCgRob3N0GBQgASgJEgwKBGNvc3QYFSABKAESFwoPdGFza19xdWV1ZV9uYW1lGBYgASgJEhEKCXRhc2tfbmFtZRgXIAEoCRIbChN3YXNfbG9hZGluZ19yZXF1ZXN0GBggASgIEhQKDHBlbmRpbmdfdGltZRgZIAEoAxIZCg1yZXBsaWNhX2luZGV4GBogASgFOgItMRIWCghmaW5pc2hlZBgbIAEoCDoEdHJ1ZRIRCgljbG9uZV9rZXkYHCABKAwSIQoEbGluZRgdIAMoCzITLmFwcGhvc3RpbmcuTG9nTGluZRITCgtleGl0X3JlYXNvbhgeIAEoBRIeChZ3YXNfdGhyb3R0bGVkX2Zvcl90aW1lGB8gASgIEiIKGndhc190aHJvdHRsZWRfZm9yX3JlcXVlc3RzGCAgASgIEhYKDnRocm90dGxlZF90aW1lGCEgASgDEhMKC3NlcnZlcl9uYW1lGCIgASgMIrgCCg5Mb2dSZWFkUmVxdWVzdBIOCgZhcHBfaWQYASACKAkSEgoKdmVyc2lvbl9pZBgCIAMoCRISCgpzdGFydF90aW1lGAMgASgDEhAKCGVuZF90aW1lGAQgASgDEiUKBm9mZnNldBgFIAEoCzIVLmFwcGhvc3RpbmcuTG9nT2Zmc2V0EhIKCnJlcXVlc3RfaWQYBiADKAkSGQoRbWluaW11bV9sb2dfbGV2ZWwYByABKAUSGgoSaW5jbHVkZV9pbmNvbXBsZXRlGAggASgIEg0KBWNvdW50GAkgASgDEhgKEGluY2x1ZGVfYXBwX2xvZ3MYCiABKAgSFAoMaW5jbHVkZV9ob3N0GAsgASgIEhMKC2luY2x1ZGVfYWxsGAwgASgIEhYKDmNhY2hlX2l0ZXJhdG9yGA0gASgIIl0KD0xvZ1JlYWRSZXNwb25zZRIjCgNsb2cYASADKAsyFi5hcHBob3N0aW5nLlJlcXVlc3RMb2cSJQoGb2Zmc2V0GAIgASgLMhUuYXBwaG9zdGluZy5Mb2dPZmZzZXQykgEKCkxvZ1NlcnZpY2USPQoFRmx1c2gSGC5hcHBob3N0aW5nLkZsdXNoUmVxdWVzdBoaLmFwcGhvc3RpbmcuYmFzZS5Wb2lkUHJvdG8SRQoJU2V0U3RhdHVzEhwuYXBwaG9zdGluZy5TZXRTdGF0dXNSZXF1ZXN0GhouYXBwaG9zdGluZy5iYXNlLlZvaWRQcm90b0I6CiRjb20uZ29vZ2xlLmFwcGhvc3RpbmcuYXBpLmxvZ3NlcnZpY2UQASABKAFCDExvZ1NlcnZpY2VQYg=="))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

class SetStatusRequest(ProtocolBuffer.ProtocolMessage):
  has_status_ = 0
  status_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def status(self): return self.status_

  def set_status(self, x):
    self.has_status_ = 1
    self.status_ = x

  def clear_status(self):
    if self.has_status_:
      self.has_status_ = 0
      self.status_ = ""

  def has_status(self): return self.has_status_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_status()): self.set_status(x.status())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.SetStatusRequest', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.SetStatusRequest')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.SetStatusRequest')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.SetStatusRequest', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.SetStatusRequest', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.SetStatusRequest', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_status_ != x.has_status_: return 0
    if self.has_status_ and self.status_ != x.status_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_status_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: status not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.status_))
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_status_):
      n += 1
      n += self.lengthString(len(self.status_))
    return n

  def Clear(self):
    self.clear_status()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.status_)

  def OutputPartial(self, out):
    if (self.has_status_):
      out.putVarInt32(10)
      out.putPrefixedString(self.status_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_status(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_status_: res+=prefix+("status: %s\n" % self.DebugFormatString(self.status_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kstatus = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "status",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChthcHBob3N0aW5nLlNldFN0YXR1c1JlcXVlc3QTGgZzdGF0dXMgASgCMAk4AhTCARdhcHBob3N0aW5nLkZsdXNoUmVxdWVzdA=="))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

class LogOffset(ProtocolBuffer.ProtocolMessage):
  has_request_id_ = 0
  request_id_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def request_id(self): return self.request_id_

  def set_request_id(self, x):
    self.has_request_id_ = 1
    self.request_id_ = x

  def clear_request_id(self):
    if self.has_request_id_:
      self.has_request_id_ = 0
      self.request_id_ = ""

  def has_request_id(self): return self.has_request_id_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_request_id()): self.set_request_id(x.request_id())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.LogOffset', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.LogOffset')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.LogOffset')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.LogOffset', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.LogOffset', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.LogOffset', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_request_id_ != x.has_request_id_: return 0
    if self.has_request_id_ and self.request_id_ != x.request_id_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_request_id_): n += 1 + self.lengthString(len(self.request_id_))
    return n

  def ByteSizePartial(self):
    n = 0
    if (self.has_request_id_): n += 1 + self.lengthString(len(self.request_id_))
    return n

  def Clear(self):
    self.clear_request_id()

  def OutputUnchecked(self, out):
    if (self.has_request_id_):
      out.putVarInt32(10)
      out.putPrefixedString(self.request_id_)

  def OutputPartial(self, out):
    if (self.has_request_id_):
      out.putVarInt32(10)
      out.putPrefixedString(self.request_id_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_request_id(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_request_id_: res+=prefix+("request_id: %s\n" % self.DebugFormatString(self.request_id_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  krequest_id = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "request_id",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChRhcHBob3N0aW5nLkxvZ09mZnNldBMaCnJlcXVlc3RfaWQgASgCMAk4ARTCARdhcHBob3N0aW5nLkZsdXNoUmVxdWVzdA=="))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

class LogLine(ProtocolBuffer.ProtocolMessage):
  has_time_ = 0
  time_ = 0
  has_level_ = 0
  level_ = 0
  has_log_message_ = 0
  log_message_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def time(self): return self.time_

  def set_time(self, x):
    self.has_time_ = 1
    self.time_ = x

  def clear_time(self):
    if self.has_time_:
      self.has_time_ = 0
      self.time_ = 0

  def has_time(self): return self.has_time_

  def level(self): return self.level_

  def set_level(self, x):
    self.has_level_ = 1
    self.level_ = x

  def clear_level(self):
    if self.has_level_:
      self.has_level_ = 0
      self.level_ = 0

  def has_level(self): return self.has_level_

  def log_message(self): return self.log_message_

  def set_log_message(self, x):
    self.has_log_message_ = 1
    self.log_message_ = x

  def clear_log_message(self):
    if self.has_log_message_:
      self.has_log_message_ = 0
      self.log_message_ = ""

  def has_log_message(self): return self.has_log_message_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_time()): self.set_time(x.time())
    if (x.has_level()): self.set_level(x.level())
    if (x.has_log_message()): self.set_log_message(x.log_message())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.LogLine', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.LogLine')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.LogLine')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.LogLine', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.LogLine', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.LogLine', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_time_ != x.has_time_: return 0
    if self.has_time_ and self.time_ != x.time_: return 0
    if self.has_level_ != x.has_level_: return 0
    if self.has_level_ and self.level_ != x.level_: return 0
    if self.has_log_message_ != x.has_log_message_: return 0
    if self.has_log_message_ and self.log_message_ != x.log_message_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_time_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: time not set.')
    if (not self.has_level_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: level not set.')
    if (not self.has_log_message_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: log_message not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.time_)
    n += self.lengthVarInt64(self.level_)
    n += self.lengthString(len(self.log_message_))
    return n + 3

  def ByteSizePartial(self):
    n = 0
    if (self.has_time_):
      n += 1
      n += self.lengthVarInt64(self.time_)
    if (self.has_level_):
      n += 1
      n += self.lengthVarInt64(self.level_)
    if (self.has_log_message_):
      n += 1
      n += self.lengthString(len(self.log_message_))
    return n

  def Clear(self):
    self.clear_time()
    self.clear_level()
    self.clear_log_message()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putVarInt64(self.time_)
    out.putVarInt32(16)
    out.putVarInt32(self.level_)
    out.putVarInt32(26)
    out.putPrefixedString(self.log_message_)

  def OutputPartial(self, out):
    if (self.has_time_):
      out.putVarInt32(8)
      out.putVarInt64(self.time_)
    if (self.has_level_):
      out.putVarInt32(16)
      out.putVarInt32(self.level_)
    if (self.has_log_message_):
      out.putVarInt32(26)
      out.putPrefixedString(self.log_message_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_time(d.getVarInt64())
        continue
      if tt == 16:
        self.set_level(d.getVarInt32())
        continue
      if tt == 26:
        self.set_log_message(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_time_: res+=prefix+("time: %s\n" % self.DebugFormatInt64(self.time_))
    if self.has_level_: res+=prefix+("level: %s\n" % self.DebugFormatInt32(self.level_))
    if self.has_log_message_: res+=prefix+("log_message: %s\n" % self.DebugFormatString(self.log_message_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  ktime = 1
  klevel = 2
  klog_message = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "time",
    2: "level",
    3: "log_message",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.NUMERIC,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.STRING,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChJhcHBob3N0aW5nLkxvZ0xpbmUTGgR0aW1lIAEoADADOAIUExoFbGV2ZWwgAigAMAU4AhQTGgtsb2dfbWVzc2FnZSADKAIwCTgCFMIBF2FwcGhvc3RpbmcuRmx1c2hSZXF1ZXN0"))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

class RequestLog(ProtocolBuffer.ProtocolMessage):
  has_app_id_ = 0
  app_id_ = ""
  has_version_id_ = 0
  version_id_ = ""
  has_request_id_ = 0
  request_id_ = ""
  has_ip_ = 0
  ip_ = ""
  has_nickname_ = 0
  nickname_ = ""
  has_start_time_ = 0
  start_time_ = 0
  has_end_time_ = 0
  end_time_ = 0
  has_latency_ = 0
  latency_ = 0
  has_mcycles_ = 0
  mcycles_ = 0
  has_method_ = 0
  method_ = ""
  has_resource_ = 0
  resource_ = ""
  has_http_version_ = 0
  http_version_ = ""
  has_status_ = 0
  status_ = 0
  has_response_size_ = 0
  response_size_ = 0
  has_referrer_ = 0
  referrer_ = ""
  has_user_agent_ = 0
  user_agent_ = ""
  has_url_map_entry_ = 0
  url_map_entry_ = ""
  has_combined_ = 0
  combined_ = ""
  has_api_mcycles_ = 0
  api_mcycles_ = 0
  has_host_ = 0
  host_ = ""
  has_cost_ = 0
  cost_ = 0.0
  has_task_queue_name_ = 0
  task_queue_name_ = ""
  has_task_name_ = 0
  task_name_ = ""
  has_was_loading_request_ = 0
  was_loading_request_ = 0
  has_pending_time_ = 0
  pending_time_ = 0
  has_replica_index_ = 0
  replica_index_ = -1
  has_finished_ = 0
  finished_ = 1
  has_clone_key_ = 0
  clone_key_ = ""
  has_exit_reason_ = 0
  exit_reason_ = 0
  has_was_throttled_for_time_ = 0
  was_throttled_for_time_ = 0
  has_was_throttled_for_requests_ = 0
  was_throttled_for_requests_ = 0
  has_throttled_time_ = 0
  throttled_time_ = 0
  has_server_name_ = 0
  server_name_ = ""

  def __init__(self, contents=None):
    self.line_ = []
    if contents is not None: self.MergeFromString(contents)

  def app_id(self): return self.app_id_

  def set_app_id(self, x):
    self.has_app_id_ = 1
    self.app_id_ = x

  def clear_app_id(self):
    if self.has_app_id_:
      self.has_app_id_ = 0
      self.app_id_ = ""

  def has_app_id(self): return self.has_app_id_

  def version_id(self): return self.version_id_

  def set_version_id(self, x):
    self.has_version_id_ = 1
    self.version_id_ = x

  def clear_version_id(self):
    if self.has_version_id_:
      self.has_version_id_ = 0
      self.version_id_ = ""

  def has_version_id(self): return self.has_version_id_

  def request_id(self): return self.request_id_

  def set_request_id(self, x):
    self.has_request_id_ = 1
    self.request_id_ = x

  def clear_request_id(self):
    if self.has_request_id_:
      self.has_request_id_ = 0
      self.request_id_ = ""

  def has_request_id(self): return self.has_request_id_

  def ip(self): return self.ip_

  def set_ip(self, x):
    self.has_ip_ = 1
    self.ip_ = x

  def clear_ip(self):
    if self.has_ip_:
      self.has_ip_ = 0
      self.ip_ = ""

  def has_ip(self): return self.has_ip_

  def nickname(self): return self.nickname_

  def set_nickname(self, x):
    self.has_nickname_ = 1
    self.nickname_ = x

  def clear_nickname(self):
    if self.has_nickname_:
      self.has_nickname_ = 0
      self.nickname_ = ""

  def has_nickname(self): return self.has_nickname_

  def start_time(self): return self.start_time_

  def set_start_time(self, x):
    self.has_start_time_ = 1
    self.start_time_ = x

  def clear_start_time(self):
    if self.has_start_time_:
      self.has_start_time_ = 0
      self.start_time_ = 0

  def has_start_time(self): return self.has_start_time_

  def end_time(self): return self.end_time_

  def set_end_time(self, x):
    self.has_end_time_ = 1
    self.end_time_ = x

  def clear_end_time(self):
    if self.has_end_time_:
      self.has_end_time_ = 0
      self.end_time_ = 0

  def has_end_time(self): return self.has_end_time_

  def latency(self): return self.latency_

  def set_latency(self, x):
    self.has_latency_ = 1
    self.latency_ = x

  def clear_latency(self):
    if self.has_latency_:
      self.has_latency_ = 0
      self.latency_ = 0

  def has_latency(self): return self.has_latency_

  def mcycles(self): return self.mcycles_

  def set_mcycles(self, x):
    self.has_mcycles_ = 1
    self.mcycles_ = x

  def clear_mcycles(self):
    if self.has_mcycles_:
      self.has_mcycles_ = 0
      self.mcycles_ = 0

  def has_mcycles(self): return self.has_mcycles_

  def method(self): return self.method_

  def set_method(self, x):
    self.has_method_ = 1
    self.method_ = x

  def clear_method(self):
    if self.has_method_:
      self.has_method_ = 0
      self.method_ = ""

  def has_method(self): return self.has_method_

  def resource(self): return self.resource_

  def set_resource(self, x):
    self.has_resource_ = 1
    self.resource_ = x

  def clear_resource(self):
    if self.has_resource_:
      self.has_resource_ = 0
      self.resource_ = ""

  def has_resource(self): return self.has_resource_

  def http_version(self): return self.http_version_

  def set_http_version(self, x):
    self.has_http_version_ = 1
    self.http_version_ = x

  def clear_http_version(self):
    if self.has_http_version_:
      self.has_http_version_ = 0
      self.http_version_ = ""

  def has_http_version(self): return self.has_http_version_

  def status(self): return self.status_

  def set_status(self, x):
    self.has_status_ = 1
    self.status_ = x

  def clear_status(self):
    if self.has_status_:
      self.has_status_ = 0
      self.status_ = 0

  def has_status(self): return self.has_status_

  def response_size(self): return self.response_size_

  def set_response_size(self, x):
    self.has_response_size_ = 1
    self.response_size_ = x

  def clear_response_size(self):
    if self.has_response_size_:
      self.has_response_size_ = 0
      self.response_size_ = 0

  def has_response_size(self): return self.has_response_size_

  def referrer(self): return self.referrer_

  def set_referrer(self, x):
    self.has_referrer_ = 1
    self.referrer_ = x

  def clear_referrer(self):
    if self.has_referrer_:
      self.has_referrer_ = 0
      self.referrer_ = ""

  def has_referrer(self): return self.has_referrer_

  def user_agent(self): return self.user_agent_

  def set_user_agent(self, x):
    self.has_user_agent_ = 1
    self.user_agent_ = x

  def clear_user_agent(self):
    if self.has_user_agent_:
      self.has_user_agent_ = 0
      self.user_agent_ = ""

  def has_user_agent(self): return self.has_user_agent_

  def url_map_entry(self): return self.url_map_entry_

  def set_url_map_entry(self, x):
    self.has_url_map_entry_ = 1
    self.url_map_entry_ = x

  def clear_url_map_entry(self):
    if self.has_url_map_entry_:
      self.has_url_map_entry_ = 0
      self.url_map_entry_ = ""

  def has_url_map_entry(self): return self.has_url_map_entry_

  def combined(self): return self.combined_

  def set_combined(self, x):
    self.has_combined_ = 1
    self.combined_ = x

  def clear_combined(self):
    if self.has_combined_:
      self.has_combined_ = 0
      self.combined_ = ""

  def has_combined(self): return self.has_combined_

  def api_mcycles(self): return self.api_mcycles_

  def set_api_mcycles(self, x):
    self.has_api_mcycles_ = 1
    self.api_mcycles_ = x

  def clear_api_mcycles(self):
    if self.has_api_mcycles_:
      self.has_api_mcycles_ = 0
      self.api_mcycles_ = 0

  def has_api_mcycles(self): return self.has_api_mcycles_

  def host(self): return self.host_

  def set_host(self, x):
    self.has_host_ = 1
    self.host_ = x

  def clear_host(self):
    if self.has_host_:
      self.has_host_ = 0
      self.host_ = ""

  def has_host(self): return self.has_host_

  def cost(self): return self.cost_

  def set_cost(self, x):
    self.has_cost_ = 1
    self.cost_ = x

  def clear_cost(self):
    if self.has_cost_:
      self.has_cost_ = 0
      self.cost_ = 0.0

  def has_cost(self): return self.has_cost_

  def task_queue_name(self): return self.task_queue_name_

  def set_task_queue_name(self, x):
    self.has_task_queue_name_ = 1
    self.task_queue_name_ = x

  def clear_task_queue_name(self):
    if self.has_task_queue_name_:
      self.has_task_queue_name_ = 0
      self.task_queue_name_ = ""

  def has_task_queue_name(self): return self.has_task_queue_name_

  def task_name(self): return self.task_name_

  def set_task_name(self, x):
    self.has_task_name_ = 1
    self.task_name_ = x

  def clear_task_name(self):
    if self.has_task_name_:
      self.has_task_name_ = 0
      self.task_name_ = ""

  def has_task_name(self): return self.has_task_name_

  def was_loading_request(self): return self.was_loading_request_

  def set_was_loading_request(self, x):
    self.has_was_loading_request_ = 1
    self.was_loading_request_ = x

  def clear_was_loading_request(self):
    if self.has_was_loading_request_:
      self.has_was_loading_request_ = 0
      self.was_loading_request_ = 0

  def has_was_loading_request(self): return self.has_was_loading_request_

  def pending_time(self): return self.pending_time_

  def set_pending_time(self, x):
    self.has_pending_time_ = 1
    self.pending_time_ = x

  def clear_pending_time(self):
    if self.has_pending_time_:
      self.has_pending_time_ = 0
      self.pending_time_ = 0

  def has_pending_time(self): return self.has_pending_time_

  def replica_index(self): return self.replica_index_

  def set_replica_index(self, x):
    self.has_replica_index_ = 1
    self.replica_index_ = x

  def clear_replica_index(self):
    if self.has_replica_index_:
      self.has_replica_index_ = 0
      self.replica_index_ = -1

  def has_replica_index(self): return self.has_replica_index_

  def finished(self): return self.finished_

  def set_finished(self, x):
    self.has_finished_ = 1
    self.finished_ = x

  def clear_finished(self):
    if self.has_finished_:
      self.has_finished_ = 0
      self.finished_ = 1

  def has_finished(self): return self.has_finished_

  def clone_key(self): return self.clone_key_

  def set_clone_key(self, x):
    self.has_clone_key_ = 1
    self.clone_key_ = x

  def clear_clone_key(self):
    if self.has_clone_key_:
      self.has_clone_key_ = 0
      self.clone_key_ = ""

  def has_clone_key(self): return self.has_clone_key_

  def line_size(self): return len(self.line_)
  def line_list(self): return self.line_

  def line(self, i):
    return self.line_[i]

  def mutable_line(self, i):
    return self.line_[i]

  def add_line(self):
    x = LogLine()
    self.line_.append(x)
    return x

  def clear_line(self):
    self.line_ = []
  def exit_reason(self): return self.exit_reason_

  def set_exit_reason(self, x):
    self.has_exit_reason_ = 1
    self.exit_reason_ = x

  def clear_exit_reason(self):
    if self.has_exit_reason_:
      self.has_exit_reason_ = 0
      self.exit_reason_ = 0

  def has_exit_reason(self): return self.has_exit_reason_

  def was_throttled_for_time(self): return self.was_throttled_for_time_

  def set_was_throttled_for_time(self, x):
    self.has_was_throttled_for_time_ = 1
    self.was_throttled_for_time_ = x

  def clear_was_throttled_for_time(self):
    if self.has_was_throttled_for_time_:
      self.has_was_throttled_for_time_ = 0
      self.was_throttled_for_time_ = 0

  def has_was_throttled_for_time(self): return self.has_was_throttled_for_time_

  def was_throttled_for_requests(self): return self.was_throttled_for_requests_

  def set_was_throttled_for_requests(self, x):
    self.has_was_throttled_for_requests_ = 1
    self.was_throttled_for_requests_ = x

  def clear_was_throttled_for_requests(self):
    if self.has_was_throttled_for_requests_:
      self.has_was_throttled_for_requests_ = 0
      self.was_throttled_for_requests_ = 0

  def has_was_throttled_for_requests(self): return self.has_was_throttled_for_requests_

  def throttled_time(self): return self.throttled_time_

  def set_throttled_time(self, x):
    self.has_throttled_time_ = 1
    self.throttled_time_ = x

  def clear_throttled_time(self):
    if self.has_throttled_time_:
      self.has_throttled_time_ = 0
      self.throttled_time_ = 0

  def has_throttled_time(self): return self.has_throttled_time_

  def server_name(self): return self.server_name_

  def set_server_name(self, x):
    self.has_server_name_ = 1
    self.server_name_ = x

  def clear_server_name(self):
    if self.has_server_name_:
      self.has_server_name_ = 0
      self.server_name_ = ""

  def has_server_name(self): return self.has_server_name_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_app_id()): self.set_app_id(x.app_id())
    if (x.has_version_id()): self.set_version_id(x.version_id())
    if (x.has_request_id()): self.set_request_id(x.request_id())
    if (x.has_ip()): self.set_ip(x.ip())
    if (x.has_nickname()): self.set_nickname(x.nickname())
    if (x.has_start_time()): self.set_start_time(x.start_time())
    if (x.has_end_time()): self.set_end_time(x.end_time())
    if (x.has_latency()): self.set_latency(x.latency())
    if (x.has_mcycles()): self.set_mcycles(x.mcycles())
    if (x.has_method()): self.set_method(x.method())
    if (x.has_resource()): self.set_resource(x.resource())
    if (x.has_http_version()): self.set_http_version(x.http_version())
    if (x.has_status()): self.set_status(x.status())
    if (x.has_response_size()): self.set_response_size(x.response_size())
    if (x.has_referrer()): self.set_referrer(x.referrer())
    if (x.has_user_agent()): self.set_user_agent(x.user_agent())
    if (x.has_url_map_entry()): self.set_url_map_entry(x.url_map_entry())
    if (x.has_combined()): self.set_combined(x.combined())
    if (x.has_api_mcycles()): self.set_api_mcycles(x.api_mcycles())
    if (x.has_host()): self.set_host(x.host())
    if (x.has_cost()): self.set_cost(x.cost())
    if (x.has_task_queue_name()): self.set_task_queue_name(x.task_queue_name())
    if (x.has_task_name()): self.set_task_name(x.task_name())
    if (x.has_was_loading_request()): self.set_was_loading_request(x.was_loading_request())
    if (x.has_pending_time()): self.set_pending_time(x.pending_time())
    if (x.has_replica_index()): self.set_replica_index(x.replica_index())
    if (x.has_finished()): self.set_finished(x.finished())
    if (x.has_clone_key()): self.set_clone_key(x.clone_key())
    for i in xrange(x.line_size()): self.add_line().CopyFrom(x.line(i))
    if (x.has_exit_reason()): self.set_exit_reason(x.exit_reason())
    if (x.has_was_throttled_for_time()): self.set_was_throttled_for_time(x.was_throttled_for_time())
    if (x.has_was_throttled_for_requests()): self.set_was_throttled_for_requests(x.was_throttled_for_requests())
    if (x.has_throttled_time()): self.set_throttled_time(x.throttled_time())
    if (x.has_server_name()): self.set_server_name(x.server_name())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.RequestLog', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.RequestLog')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.RequestLog')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.RequestLog', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.RequestLog', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.RequestLog', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_app_id_ != x.has_app_id_: return 0
    if self.has_app_id_ and self.app_id_ != x.app_id_: return 0
    if self.has_version_id_ != x.has_version_id_: return 0
    if self.has_version_id_ and self.version_id_ != x.version_id_: return 0
    if self.has_request_id_ != x.has_request_id_: return 0
    if self.has_request_id_ and self.request_id_ != x.request_id_: return 0
    if self.has_ip_ != x.has_ip_: return 0
    if self.has_ip_ and self.ip_ != x.ip_: return 0
    if self.has_nickname_ != x.has_nickname_: return 0
    if self.has_nickname_ and self.nickname_ != x.nickname_: return 0
    if self.has_start_time_ != x.has_start_time_: return 0
    if self.has_start_time_ and self.start_time_ != x.start_time_: return 0
    if self.has_end_time_ != x.has_end_time_: return 0
    if self.has_end_time_ and self.end_time_ != x.end_time_: return 0
    if self.has_latency_ != x.has_latency_: return 0
    if self.has_latency_ and self.latency_ != x.latency_: return 0
    if self.has_mcycles_ != x.has_mcycles_: return 0
    if self.has_mcycles_ and self.mcycles_ != x.mcycles_: return 0
    if self.has_method_ != x.has_method_: return 0
    if self.has_method_ and self.method_ != x.method_: return 0
    if self.has_resource_ != x.has_resource_: return 0
    if self.has_resource_ and self.resource_ != x.resource_: return 0
    if self.has_http_version_ != x.has_http_version_: return 0
    if self.has_http_version_ and self.http_version_ != x.http_version_: return 0
    if self.has_status_ != x.has_status_: return 0
    if self.has_status_ and self.status_ != x.status_: return 0
    if self.has_response_size_ != x.has_response_size_: return 0
    if self.has_response_size_ and self.response_size_ != x.response_size_: return 0
    if self.has_referrer_ != x.has_referrer_: return 0
    if self.has_referrer_ and self.referrer_ != x.referrer_: return 0
    if self.has_user_agent_ != x.has_user_agent_: return 0
    if self.has_user_agent_ and self.user_agent_ != x.user_agent_: return 0
    if self.has_url_map_entry_ != x.has_url_map_entry_: return 0
    if self.has_url_map_entry_ and self.url_map_entry_ != x.url_map_entry_: return 0
    if self.has_combined_ != x.has_combined_: return 0
    if self.has_combined_ and self.combined_ != x.combined_: return 0
    if self.has_api_mcycles_ != x.has_api_mcycles_: return 0
    if self.has_api_mcycles_ and self.api_mcycles_ != x.api_mcycles_: return 0
    if self.has_host_ != x.has_host_: return 0
    if self.has_host_ and self.host_ != x.host_: return 0
    if self.has_cost_ != x.has_cost_: return 0
    if self.has_cost_ and self.cost_ != x.cost_: return 0
    if self.has_task_queue_name_ != x.has_task_queue_name_: return 0
    if self.has_task_queue_name_ and self.task_queue_name_ != x.task_queue_name_: return 0
    if self.has_task_name_ != x.has_task_name_: return 0
    if self.has_task_name_ and self.task_name_ != x.task_name_: return 0
    if self.has_was_loading_request_ != x.has_was_loading_request_: return 0
    if self.has_was_loading_request_ and self.was_loading_request_ != x.was_loading_request_: return 0
    if self.has_pending_time_ != x.has_pending_time_: return 0
    if self.has_pending_time_ and self.pending_time_ != x.pending_time_: return 0
    if self.has_replica_index_ != x.has_replica_index_: return 0
    if self.has_replica_index_ and self.replica_index_ != x.replica_index_: return 0
    if self.has_finished_ != x.has_finished_: return 0
    if self.has_finished_ and self.finished_ != x.finished_: return 0
    if self.has_clone_key_ != x.has_clone_key_: return 0
    if self.has_clone_key_ and self.clone_key_ != x.clone_key_: return 0
    if len(self.line_) != len(x.line_): return 0
    for e1, e2 in zip(self.line_, x.line_):
      if e1 != e2: return 0
    if self.has_exit_reason_ != x.has_exit_reason_: return 0
    if self.has_exit_reason_ and self.exit_reason_ != x.exit_reason_: return 0
    if self.has_was_throttled_for_time_ != x.has_was_throttled_for_time_: return 0
    if self.has_was_throttled_for_time_ and self.was_throttled_for_time_ != x.was_throttled_for_time_: return 0
    if self.has_was_throttled_for_requests_ != x.has_was_throttled_for_requests_: return 0
    if self.has_was_throttled_for_requests_ and self.was_throttled_for_requests_ != x.was_throttled_for_requests_: return 0
    if self.has_throttled_time_ != x.has_throttled_time_: return 0
    if self.has_throttled_time_ and self.throttled_time_ != x.throttled_time_: return 0
    if self.has_server_name_ != x.has_server_name_: return 0
    if self.has_server_name_ and self.server_name_ != x.server_name_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_app_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: app_id not set.')
    if (not self.has_version_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: version_id not set.')
    if (not self.has_request_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: request_id not set.')
    if (not self.has_ip_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: ip not set.')
    if (not self.has_start_time_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: start_time not set.')
    if (not self.has_end_time_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: end_time not set.')
    if (not self.has_latency_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: latency not set.')
    if (not self.has_mcycles_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: mcycles not set.')
    if (not self.has_method_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: method not set.')
    if (not self.has_resource_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: resource not set.')
    if (not self.has_http_version_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: http_version not set.')
    if (not self.has_status_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: status not set.')
    if (not self.has_response_size_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: response_size not set.')
    if (not self.has_url_map_entry_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: url_map_entry not set.')
    if (not self.has_combined_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: combined not set.')
    for p in self.line_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.app_id_))
    n += self.lengthString(len(self.version_id_))
    n += self.lengthString(len(self.request_id_))
    n += self.lengthString(len(self.ip_))
    if (self.has_nickname_): n += 1 + self.lengthString(len(self.nickname_))
    n += self.lengthVarInt64(self.start_time_)
    n += self.lengthVarInt64(self.end_time_)
    n += self.lengthVarInt64(self.latency_)
    n += self.lengthVarInt64(self.mcycles_)
    n += self.lengthString(len(self.method_))
    n += self.lengthString(len(self.resource_))
    n += self.lengthString(len(self.http_version_))
    n += self.lengthVarInt64(self.status_)
    n += self.lengthVarInt64(self.response_size_)
    if (self.has_referrer_): n += 1 + self.lengthString(len(self.referrer_))
    if (self.has_user_agent_): n += 2 + self.lengthString(len(self.user_agent_))
    n += self.lengthString(len(self.url_map_entry_))
    n += self.lengthString(len(self.combined_))
    if (self.has_api_mcycles_): n += 2 + self.lengthVarInt64(self.api_mcycles_)
    if (self.has_host_): n += 2 + self.lengthString(len(self.host_))
    if (self.has_cost_): n += 10
    if (self.has_task_queue_name_): n += 2 + self.lengthString(len(self.task_queue_name_))
    if (self.has_task_name_): n += 2 + self.lengthString(len(self.task_name_))
    if (self.has_was_loading_request_): n += 3
    if (self.has_pending_time_): n += 2 + self.lengthVarInt64(self.pending_time_)
    if (self.has_replica_index_): n += 2 + self.lengthVarInt64(self.replica_index_)
    if (self.has_finished_): n += 3
    if (self.has_clone_key_): n += 2 + self.lengthString(len(self.clone_key_))
    n += 2 * len(self.line_)
    for i in xrange(len(self.line_)): n += self.lengthString(self.line_[i].ByteSize())
    if (self.has_exit_reason_): n += 2 + self.lengthVarInt64(self.exit_reason_)
    if (self.has_was_throttled_for_time_): n += 3
    if (self.has_was_throttled_for_requests_): n += 3
    if (self.has_throttled_time_): n += 2 + self.lengthVarInt64(self.throttled_time_)
    if (self.has_server_name_): n += 2 + self.lengthString(len(self.server_name_))
    return n + 17

  def ByteSizePartial(self):
    n = 0
    if (self.has_app_id_):
      n += 1
      n += self.lengthString(len(self.app_id_))
    if (self.has_version_id_):
      n += 1
      n += self.lengthString(len(self.version_id_))
    if (self.has_request_id_):
      n += 1
      n += self.lengthString(len(self.request_id_))
    if (self.has_ip_):
      n += 1
      n += self.lengthString(len(self.ip_))
    if (self.has_nickname_): n += 1 + self.lengthString(len(self.nickname_))
    if (self.has_start_time_):
      n += 1
      n += self.lengthVarInt64(self.start_time_)
    if (self.has_end_time_):
      n += 1
      n += self.lengthVarInt64(self.end_time_)
    if (self.has_latency_):
      n += 1
      n += self.lengthVarInt64(self.latency_)
    if (self.has_mcycles_):
      n += 1
      n += self.lengthVarInt64(self.mcycles_)
    if (self.has_method_):
      n += 1
      n += self.lengthString(len(self.method_))
    if (self.has_resource_):
      n += 1
      n += self.lengthString(len(self.resource_))
    if (self.has_http_version_):
      n += 1
      n += self.lengthString(len(self.http_version_))
    if (self.has_status_):
      n += 1
      n += self.lengthVarInt64(self.status_)
    if (self.has_response_size_):
      n += 1
      n += self.lengthVarInt64(self.response_size_)
    if (self.has_referrer_): n += 1 + self.lengthString(len(self.referrer_))
    if (self.has_user_agent_): n += 2 + self.lengthString(len(self.user_agent_))
    if (self.has_url_map_entry_):
      n += 2
      n += self.lengthString(len(self.url_map_entry_))
    if (self.has_combined_):
      n += 2
      n += self.lengthString(len(self.combined_))
    if (self.has_api_mcycles_): n += 2 + self.lengthVarInt64(self.api_mcycles_)
    if (self.has_host_): n += 2 + self.lengthString(len(self.host_))
    if (self.has_cost_): n += 10
    if (self.has_task_queue_name_): n += 2 + self.lengthString(len(self.task_queue_name_))
    if (self.has_task_name_): n += 2 + self.lengthString(len(self.task_name_))
    if (self.has_was_loading_request_): n += 3
    if (self.has_pending_time_): n += 2 + self.lengthVarInt64(self.pending_time_)
    if (self.has_replica_index_): n += 2 + self.lengthVarInt64(self.replica_index_)
    if (self.has_finished_): n += 3
    if (self.has_clone_key_): n += 2 + self.lengthString(len(self.clone_key_))
    n += 2 * len(self.line_)
    for i in xrange(len(self.line_)): n += self.lengthString(self.line_[i].ByteSizePartial())
    if (self.has_exit_reason_): n += 2 + self.lengthVarInt64(self.exit_reason_)
    if (self.has_was_throttled_for_time_): n += 3
    if (self.has_was_throttled_for_requests_): n += 3
    if (self.has_throttled_time_): n += 2 + self.lengthVarInt64(self.throttled_time_)
    if (self.has_server_name_): n += 2 + self.lengthString(len(self.server_name_))
    return n

  def Clear(self):
    self.clear_app_id()
    self.clear_version_id()
    self.clear_request_id()
    self.clear_ip()
    self.clear_nickname()
    self.clear_start_time()
    self.clear_end_time()
    self.clear_latency()
    self.clear_mcycles()
    self.clear_method()
    self.clear_resource()
    self.clear_http_version()
    self.clear_status()
    self.clear_response_size()
    self.clear_referrer()
    self.clear_user_agent()
    self.clear_url_map_entry()
    self.clear_combined()
    self.clear_api_mcycles()
    self.clear_host()
    self.clear_cost()
    self.clear_task_queue_name()
    self.clear_task_name()
    self.clear_was_loading_request()
    self.clear_pending_time()
    self.clear_replica_index()
    self.clear_finished()
    self.clear_clone_key()
    self.clear_line()
    self.clear_exit_reason()
    self.clear_was_throttled_for_time()
    self.clear_was_throttled_for_requests()
    self.clear_throttled_time()
    self.clear_server_name()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.app_id_)
    out.putVarInt32(18)
    out.putPrefixedString(self.version_id_)
    out.putVarInt32(26)
    out.putPrefixedString(self.request_id_)
    out.putVarInt32(34)
    out.putPrefixedString(self.ip_)
    if (self.has_nickname_):
      out.putVarInt32(42)
      out.putPrefixedString(self.nickname_)
    out.putVarInt32(48)
    out.putVarInt64(self.start_time_)
    out.putVarInt32(56)
    out.putVarInt64(self.end_time_)
    out.putVarInt32(64)
    out.putVarInt64(self.latency_)
    out.putVarInt32(72)
    out.putVarInt64(self.mcycles_)
    out.putVarInt32(82)
    out.putPrefixedString(self.method_)
    out.putVarInt32(90)
    out.putPrefixedString(self.resource_)
    out.putVarInt32(98)
    out.putPrefixedString(self.http_version_)
    out.putVarInt32(104)
    out.putVarInt32(self.status_)
    out.putVarInt32(112)
    out.putVarInt64(self.response_size_)
    if (self.has_referrer_):
      out.putVarInt32(122)
      out.putPrefixedString(self.referrer_)
    if (self.has_user_agent_):
      out.putVarInt32(130)
      out.putPrefixedString(self.user_agent_)
    out.putVarInt32(138)
    out.putPrefixedString(self.url_map_entry_)
    out.putVarInt32(146)
    out.putPrefixedString(self.combined_)
    if (self.has_api_mcycles_):
      out.putVarInt32(152)
      out.putVarInt64(self.api_mcycles_)
    if (self.has_host_):
      out.putVarInt32(162)
      out.putPrefixedString(self.host_)
    if (self.has_cost_):
      out.putVarInt32(169)
      out.putDouble(self.cost_)
    if (self.has_task_queue_name_):
      out.putVarInt32(178)
      out.putPrefixedString(self.task_queue_name_)
    if (self.has_task_name_):
      out.putVarInt32(186)
      out.putPrefixedString(self.task_name_)
    if (self.has_was_loading_request_):
      out.putVarInt32(192)
      out.putBoolean(self.was_loading_request_)
    if (self.has_pending_time_):
      out.putVarInt32(200)
      out.putVarInt64(self.pending_time_)
    if (self.has_replica_index_):
      out.putVarInt32(208)
      out.putVarInt32(self.replica_index_)
    if (self.has_finished_):
      out.putVarInt32(216)
      out.putBoolean(self.finished_)
    if (self.has_clone_key_):
      out.putVarInt32(226)
      out.putPrefixedString(self.clone_key_)
    for i in xrange(len(self.line_)):
      out.putVarInt32(234)
      out.putVarInt32(self.line_[i].ByteSize())
      self.line_[i].OutputUnchecked(out)
    if (self.has_exit_reason_):
      out.putVarInt32(240)
      out.putVarInt32(self.exit_reason_)
    if (self.has_was_throttled_for_time_):
      out.putVarInt32(248)
      out.putBoolean(self.was_throttled_for_time_)
    if (self.has_was_throttled_for_requests_):
      out.putVarInt32(256)
      out.putBoolean(self.was_throttled_for_requests_)
    if (self.has_throttled_time_):
      out.putVarInt32(264)
      out.putVarInt64(self.throttled_time_)
    if (self.has_server_name_):
      out.putVarInt32(274)
      out.putPrefixedString(self.server_name_)

  def OutputPartial(self, out):
    if (self.has_app_id_):
      out.putVarInt32(10)
      out.putPrefixedString(self.app_id_)
    if (self.has_version_id_):
      out.putVarInt32(18)
      out.putPrefixedString(self.version_id_)
    if (self.has_request_id_):
      out.putVarInt32(26)
      out.putPrefixedString(self.request_id_)
    if (self.has_ip_):
      out.putVarInt32(34)
      out.putPrefixedString(self.ip_)
    if (self.has_nickname_):
      out.putVarInt32(42)
      out.putPrefixedString(self.nickname_)
    if (self.has_start_time_):
      out.putVarInt32(48)
      out.putVarInt64(self.start_time_)
    if (self.has_end_time_):
      out.putVarInt32(56)
      out.putVarInt64(self.end_time_)
    if (self.has_latency_):
      out.putVarInt32(64)
      out.putVarInt64(self.latency_)
    if (self.has_mcycles_):
      out.putVarInt32(72)
      out.putVarInt64(self.mcycles_)
    if (self.has_method_):
      out.putVarInt32(82)
      out.putPrefixedString(self.method_)
    if (self.has_resource_):
      out.putVarInt32(90)
      out.putPrefixedString(self.resource_)
    if (self.has_http_version_):
      out.putVarInt32(98)
      out.putPrefixedString(self.http_version_)
    if (self.has_status_):
      out.putVarInt32(104)
      out.putVarInt32(self.status_)
    if (self.has_response_size_):
      out.putVarInt32(112)
      out.putVarInt64(self.response_size_)
    if (self.has_referrer_):
      out.putVarInt32(122)
      out.putPrefixedString(self.referrer_)
    if (self.has_user_agent_):
      out.putVarInt32(130)
      out.putPrefixedString(self.user_agent_)
    if (self.has_url_map_entry_):
      out.putVarInt32(138)
      out.putPrefixedString(self.url_map_entry_)
    if (self.has_combined_):
      out.putVarInt32(146)
      out.putPrefixedString(self.combined_)
    if (self.has_api_mcycles_):
      out.putVarInt32(152)
      out.putVarInt64(self.api_mcycles_)
    if (self.has_host_):
      out.putVarInt32(162)
      out.putPrefixedString(self.host_)
    if (self.has_cost_):
      out.putVarInt32(169)
      out.putDouble(self.cost_)
    if (self.has_task_queue_name_):
      out.putVarInt32(178)
      out.putPrefixedString(self.task_queue_name_)
    if (self.has_task_name_):
      out.putVarInt32(186)
      out.putPrefixedString(self.task_name_)
    if (self.has_was_loading_request_):
      out.putVarInt32(192)
      out.putBoolean(self.was_loading_request_)
    if (self.has_pending_time_):
      out.putVarInt32(200)
      out.putVarInt64(self.pending_time_)
    if (self.has_replica_index_):
      out.putVarInt32(208)
      out.putVarInt32(self.replica_index_)
    if (self.has_finished_):
      out.putVarInt32(216)
      out.putBoolean(self.finished_)
    if (self.has_clone_key_):
      out.putVarInt32(226)
      out.putPrefixedString(self.clone_key_)
    for i in xrange(len(self.line_)):
      out.putVarInt32(234)
      out.putVarInt32(self.line_[i].ByteSizePartial())
      self.line_[i].OutputPartial(out)
    if (self.has_exit_reason_):
      out.putVarInt32(240)
      out.putVarInt32(self.exit_reason_)
    if (self.has_was_throttled_for_time_):
      out.putVarInt32(248)
      out.putBoolean(self.was_throttled_for_time_)
    if (self.has_was_throttled_for_requests_):
      out.putVarInt32(256)
      out.putBoolean(self.was_throttled_for_requests_)
    if (self.has_throttled_time_):
      out.putVarInt32(264)
      out.putVarInt64(self.throttled_time_)
    if (self.has_server_name_):
      out.putVarInt32(274)
      out.putPrefixedString(self.server_name_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_app_id(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_version_id(d.getPrefixedString())
        continue
      if tt == 26:
        self.set_request_id(d.getPrefixedString())
        continue
      if tt == 34:
        self.set_ip(d.getPrefixedString())
        continue
      if tt == 42:
        self.set_nickname(d.getPrefixedString())
        continue
      if tt == 48:
        self.set_start_time(d.getVarInt64())
        continue
      if tt == 56:
        self.set_end_time(d.getVarInt64())
        continue
      if tt == 64:
        self.set_latency(d.getVarInt64())
        continue
      if tt == 72:
        self.set_mcycles(d.getVarInt64())
        continue
      if tt == 82:
        self.set_method(d.getPrefixedString())
        continue
      if tt == 90:
        self.set_resource(d.getPrefixedString())
        continue
      if tt == 98:
        self.set_http_version(d.getPrefixedString())
        continue
      if tt == 104:
        self.set_status(d.getVarInt32())
        continue
      if tt == 112:
        self.set_response_size(d.getVarInt64())
        continue
      if tt == 122:
        self.set_referrer(d.getPrefixedString())
        continue
      if tt == 130:
        self.set_user_agent(d.getPrefixedString())
        continue
      if tt == 138:
        self.set_url_map_entry(d.getPrefixedString())
        continue
      if tt == 146:
        self.set_combined(d.getPrefixedString())
        continue
      if tt == 152:
        self.set_api_mcycles(d.getVarInt64())
        continue
      if tt == 162:
        self.set_host(d.getPrefixedString())
        continue
      if tt == 169:
        self.set_cost(d.getDouble())
        continue
      if tt == 178:
        self.set_task_queue_name(d.getPrefixedString())
        continue
      if tt == 186:
        self.set_task_name(d.getPrefixedString())
        continue
      if tt == 192:
        self.set_was_loading_request(d.getBoolean())
        continue
      if tt == 200:
        self.set_pending_time(d.getVarInt64())
        continue
      if tt == 208:
        self.set_replica_index(d.getVarInt32())
        continue
      if tt == 216:
        self.set_finished(d.getBoolean())
        continue
      if tt == 226:
        self.set_clone_key(d.getPrefixedString())
        continue
      if tt == 234:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_line().TryMerge(tmp)
        continue
      if tt == 240:
        self.set_exit_reason(d.getVarInt32())
        continue
      if tt == 248:
        self.set_was_throttled_for_time(d.getBoolean())
        continue
      if tt == 256:
        self.set_was_throttled_for_requests(d.getBoolean())
        continue
      if tt == 264:
        self.set_throttled_time(d.getVarInt64())
        continue
      if tt == 274:
        self.set_server_name(d.getPrefixedString())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_app_id_: res+=prefix+("app_id: %s\n" % self.DebugFormatString(self.app_id_))
    if self.has_version_id_: res+=prefix+("version_id: %s\n" % self.DebugFormatString(self.version_id_))
    if self.has_request_id_: res+=prefix+("request_id: %s\n" % self.DebugFormatString(self.request_id_))
    if self.has_ip_: res+=prefix+("ip: %s\n" % self.DebugFormatString(self.ip_))
    if self.has_nickname_: res+=prefix+("nickname: %s\n" % self.DebugFormatString(self.nickname_))
    if self.has_start_time_: res+=prefix+("start_time: %s\n" % self.DebugFormatInt64(self.start_time_))
    if self.has_end_time_: res+=prefix+("end_time: %s\n" % self.DebugFormatInt64(self.end_time_))
    if self.has_latency_: res+=prefix+("latency: %s\n" % self.DebugFormatInt64(self.latency_))
    if self.has_mcycles_: res+=prefix+("mcycles: %s\n" % self.DebugFormatInt64(self.mcycles_))
    if self.has_method_: res+=prefix+("method: %s\n" % self.DebugFormatString(self.method_))
    if self.has_resource_: res+=prefix+("resource: %s\n" % self.DebugFormatString(self.resource_))
    if self.has_http_version_: res+=prefix+("http_version: %s\n" % self.DebugFormatString(self.http_version_))
    if self.has_status_: res+=prefix+("status: %s\n" % self.DebugFormatInt32(self.status_))
    if self.has_response_size_: res+=prefix+("response_size: %s\n" % self.DebugFormatInt64(self.response_size_))
    if self.has_referrer_: res+=prefix+("referrer: %s\n" % self.DebugFormatString(self.referrer_))
    if self.has_user_agent_: res+=prefix+("user_agent: %s\n" % self.DebugFormatString(self.user_agent_))
    if self.has_url_map_entry_: res+=prefix+("url_map_entry: %s\n" % self.DebugFormatString(self.url_map_entry_))
    if self.has_combined_: res+=prefix+("combined: %s\n" % self.DebugFormatString(self.combined_))
    if self.has_api_mcycles_: res+=prefix+("api_mcycles: %s\n" % self.DebugFormatInt64(self.api_mcycles_))
    if self.has_host_: res+=prefix+("host: %s\n" % self.DebugFormatString(self.host_))
    if self.has_cost_: res+=prefix+("cost: %s\n" % self.DebugFormat(self.cost_))
    if self.has_task_queue_name_: res+=prefix+("task_queue_name: %s\n" % self.DebugFormatString(self.task_queue_name_))
    if self.has_task_name_: res+=prefix+("task_name: %s\n" % self.DebugFormatString(self.task_name_))
    if self.has_was_loading_request_: res+=prefix+("was_loading_request: %s\n" % self.DebugFormatBool(self.was_loading_request_))
    if self.has_pending_time_: res+=prefix+("pending_time: %s\n" % self.DebugFormatInt64(self.pending_time_))
    if self.has_replica_index_: res+=prefix+("replica_index: %s\n" % self.DebugFormatInt32(self.replica_index_))
    if self.has_finished_: res+=prefix+("finished: %s\n" % self.DebugFormatBool(self.finished_))
    if self.has_clone_key_: res+=prefix+("clone_key: %s\n" % self.DebugFormatString(self.clone_key_))
    cnt=0
    for e in self.line_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("line%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    if self.has_exit_reason_: res+=prefix+("exit_reason: %s\n" % self.DebugFormatInt32(self.exit_reason_))
    if self.has_was_throttled_for_time_: res+=prefix+("was_throttled_for_time: %s\n" % self.DebugFormatBool(self.was_throttled_for_time_))
    if self.has_was_throttled_for_requests_: res+=prefix+("was_throttled_for_requests: %s\n" % self.DebugFormatBool(self.was_throttled_for_requests_))
    if self.has_throttled_time_: res+=prefix+("throttled_time: %s\n" % self.DebugFormatInt64(self.throttled_time_))
    if self.has_server_name_: res+=prefix+("server_name: %s\n" % self.DebugFormatString(self.server_name_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kapp_id = 1
  kversion_id = 2
  krequest_id = 3
  kip = 4
  knickname = 5
  kstart_time = 6
  kend_time = 7
  klatency = 8
  kmcycles = 9
  kmethod = 10
  kresource = 11
  khttp_version = 12
  kstatus = 13
  kresponse_size = 14
  kreferrer = 15
  kuser_agent = 16
  kurl_map_entry = 17
  kcombined = 18
  kapi_mcycles = 19
  khost = 20
  kcost = 21
  ktask_queue_name = 22
  ktask_name = 23
  kwas_loading_request = 24
  kpending_time = 25
  kreplica_index = 26
  kfinished = 27
  kclone_key = 28
  kline = 29
  kexit_reason = 30
  kwas_throttled_for_time = 31
  kwas_throttled_for_requests = 32
  kthrottled_time = 33
  kserver_name = 34

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "app_id",
    2: "version_id",
    3: "request_id",
    4: "ip",
    5: "nickname",
    6: "start_time",
    7: "end_time",
    8: "latency",
    9: "mcycles",
    10: "method",
    11: "resource",
    12: "http_version",
    13: "status",
    14: "response_size",
    15: "referrer",
    16: "user_agent",
    17: "url_map_entry",
    18: "combined",
    19: "api_mcycles",
    20: "host",
    21: "cost",
    22: "task_queue_name",
    23: "task_name",
    24: "was_loading_request",
    25: "pending_time",
    26: "replica_index",
    27: "finished",
    28: "clone_key",
    29: "line",
    30: "exit_reason",
    31: "was_throttled_for_time",
    32: "was_throttled_for_requests",
    33: "throttled_time",
    34: "server_name",
  }, 34)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
    4: ProtocolBuffer.Encoder.STRING,
    5: ProtocolBuffer.Encoder.STRING,
    6: ProtocolBuffer.Encoder.NUMERIC,
    7: ProtocolBuffer.Encoder.NUMERIC,
    8: ProtocolBuffer.Encoder.NUMERIC,
    9: ProtocolBuffer.Encoder.NUMERIC,
    10: ProtocolBuffer.Encoder.STRING,
    11: ProtocolBuffer.Encoder.STRING,
    12: ProtocolBuffer.Encoder.STRING,
    13: ProtocolBuffer.Encoder.NUMERIC,
    14: ProtocolBuffer.Encoder.NUMERIC,
    15: ProtocolBuffer.Encoder.STRING,
    16: ProtocolBuffer.Encoder.STRING,
    17: ProtocolBuffer.Encoder.STRING,
    18: ProtocolBuffer.Encoder.STRING,
    19: ProtocolBuffer.Encoder.NUMERIC,
    20: ProtocolBuffer.Encoder.STRING,
    21: ProtocolBuffer.Encoder.DOUBLE,
    22: ProtocolBuffer.Encoder.STRING,
    23: ProtocolBuffer.Encoder.STRING,
    24: ProtocolBuffer.Encoder.NUMERIC,
    25: ProtocolBuffer.Encoder.NUMERIC,
    26: ProtocolBuffer.Encoder.NUMERIC,
    27: ProtocolBuffer.Encoder.NUMERIC,
    28: ProtocolBuffer.Encoder.STRING,
    29: ProtocolBuffer.Encoder.STRING,
    30: ProtocolBuffer.Encoder.NUMERIC,
    31: ProtocolBuffer.Encoder.NUMERIC,
    32: ProtocolBuffer.Encoder.NUMERIC,
    33: ProtocolBuffer.Encoder.NUMERIC,
    34: ProtocolBuffer.Encoder.STRING,
  }, 34, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChVhcHBob3N0aW5nLlJlcXVlc3RMb2cTGgZhcHBfaWQgASgCMAk4AhQTGgp2ZXJzaW9uX2lkIAIoAjAJOAIUExoKcmVxdWVzdF9pZCADKAIwCTgCFBMaAmlwIAQoAjAJOAIUExoIbmlja25hbWUgBSgCMAk4ARQTGgpzdGFydF90aW1lIAYoADADOAIUExoIZW5kX3RpbWUgBygAMAM4AhQTGgdsYXRlbmN5IAgoADADOAIUExoHbWN5Y2xlcyAJKAAwAzgCFBMaBm1ldGhvZCAKKAIwCTgCFBMaCHJlc291cmNlIAsoAjAJOAIUExoMaHR0cF92ZXJzaW9uIAwoAjAJOAIUExoGc3RhdHVzIA0oADAFOAIUExoNcmVzcG9uc2Vfc2l6ZSAOKAAwAzgCFBMaCHJlZmVycmVyIA8oAjAJOAEUExoKdXNlcl9hZ2VudCAQKAIwCTgBFBMaDXVybF9tYXBfZW50cnkgESgCMAk4AhQTGghjb21iaW5lZCASKAIwCTgCFBMaC2FwaV9tY3ljbGVzIBMoADADOAEUExoEaG9zdCAUKAIwCTgBFBMaBGNvc3QgFSgBMAE4ARQTGg90YXNrX3F1ZXVlX25hbWUgFigCMAk4ARQTGgl0YXNrX25hbWUgFygCMAk4ARQTGhN3YXNfbG9hZGluZ19yZXF1ZXN0IBgoADAIOAEUExoMcGVuZGluZ190aW1lIBkoADADOAEUExoNcmVwbGljYV9pbmRleCAaKAAwBTgBQgItMaMBqgEHZGVmYXVsdLIBAi0xpAEUExoIZmluaXNoZWQgGygAMAg4AUIEdHJ1ZaMBqgEHZGVmYXVsdLIBBHRydWWkARQTGgljbG9uZV9rZXkgHCgCMAk4ARQTGgRsaW5lIB0oAjALOANKEmFwcGhvc3RpbmcuTG9nTGluZRQTGgtleGl0X3JlYXNvbiAeKAAwBTgBFBMaFndhc190aHJvdHRsZWRfZm9yX3RpbWUgHygAMAg4ARQTGhp3YXNfdGhyb3R0bGVkX2Zvcl9yZXF1ZXN0cyAgKAAwCDgBFBMaDnRocm90dGxlZF90aW1lICEoADADOAEUExoLc2VydmVyX25hbWUgIigCMAk4ARTCARdhcHBob3N0aW5nLkZsdXNoUmVxdWVzdA=="))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

class LogReadRequest(ProtocolBuffer.ProtocolMessage):
  has_app_id_ = 0
  app_id_ = ""
  has_start_time_ = 0
  start_time_ = 0
  has_end_time_ = 0
  end_time_ = 0
  has_offset_ = 0
  offset_ = None
  has_minimum_log_level_ = 0
  minimum_log_level_ = 0
  has_include_incomplete_ = 0
  include_incomplete_ = 0
  has_count_ = 0
  count_ = 0
  has_include_app_logs_ = 0
  include_app_logs_ = 0
  has_include_host_ = 0
  include_host_ = 0
  has_include_all_ = 0
  include_all_ = 0
  has_cache_iterator_ = 0
  cache_iterator_ = 0

  def __init__(self, contents=None):
    self.version_id_ = []
    self.request_id_ = []
    self.lazy_init_lock_ = thread.allocate_lock()
    if contents is not None: self.MergeFromString(contents)

  def app_id(self): return self.app_id_

  def set_app_id(self, x):
    self.has_app_id_ = 1
    self.app_id_ = x

  def clear_app_id(self):
    if self.has_app_id_:
      self.has_app_id_ = 0
      self.app_id_ = ""

  def has_app_id(self): return self.has_app_id_

  def version_id_size(self): return len(self.version_id_)
  def version_id_list(self): return self.version_id_

  def version_id(self, i):
    return self.version_id_[i]

  def set_version_id(self, i, x):
    self.version_id_[i] = x

  def add_version_id(self, x):
    self.version_id_.append(x)

  def clear_version_id(self):
    self.version_id_ = []

  def start_time(self): return self.start_time_

  def set_start_time(self, x):
    self.has_start_time_ = 1
    self.start_time_ = x

  def clear_start_time(self):
    if self.has_start_time_:
      self.has_start_time_ = 0
      self.start_time_ = 0

  def has_start_time(self): return self.has_start_time_

  def end_time(self): return self.end_time_

  def set_end_time(self, x):
    self.has_end_time_ = 1
    self.end_time_ = x

  def clear_end_time(self):
    if self.has_end_time_:
      self.has_end_time_ = 0
      self.end_time_ = 0

  def has_end_time(self): return self.has_end_time_

  def offset(self):
    if self.offset_ is None:
      self.lazy_init_lock_.acquire()
      try:
        if self.offset_ is None: self.offset_ = LogOffset()
      finally:
        self.lazy_init_lock_.release()
    return self.offset_

  def mutable_offset(self): self.has_offset_ = 1; return self.offset()

  def clear_offset(self):

    if self.has_offset_:
      self.has_offset_ = 0;
      if self.offset_ is not None: self.offset_.Clear()

  def has_offset(self): return self.has_offset_

  def request_id_size(self): return len(self.request_id_)
  def request_id_list(self): return self.request_id_

  def request_id(self, i):
    return self.request_id_[i]

  def set_request_id(self, i, x):
    self.request_id_[i] = x

  def add_request_id(self, x):
    self.request_id_.append(x)

  def clear_request_id(self):
    self.request_id_ = []

  def minimum_log_level(self): return self.minimum_log_level_

  def set_minimum_log_level(self, x):
    self.has_minimum_log_level_ = 1
    self.minimum_log_level_ = x

  def clear_minimum_log_level(self):
    if self.has_minimum_log_level_:
      self.has_minimum_log_level_ = 0
      self.minimum_log_level_ = 0

  def has_minimum_log_level(self): return self.has_minimum_log_level_

  def include_incomplete(self): return self.include_incomplete_

  def set_include_incomplete(self, x):
    self.has_include_incomplete_ = 1
    self.include_incomplete_ = x

  def clear_include_incomplete(self):
    if self.has_include_incomplete_:
      self.has_include_incomplete_ = 0
      self.include_incomplete_ = 0

  def has_include_incomplete(self): return self.has_include_incomplete_

  def count(self): return self.count_

  def set_count(self, x):
    self.has_count_ = 1
    self.count_ = x

  def clear_count(self):
    if self.has_count_:
      self.has_count_ = 0
      self.count_ = 0

  def has_count(self): return self.has_count_

  def include_app_logs(self): return self.include_app_logs_

  def set_include_app_logs(self, x):
    self.has_include_app_logs_ = 1
    self.include_app_logs_ = x

  def clear_include_app_logs(self):
    if self.has_include_app_logs_:
      self.has_include_app_logs_ = 0
      self.include_app_logs_ = 0

  def has_include_app_logs(self): return self.has_include_app_logs_

  def include_host(self): return self.include_host_

  def set_include_host(self, x):
    self.has_include_host_ = 1
    self.include_host_ = x

  def clear_include_host(self):
    if self.has_include_host_:
      self.has_include_host_ = 0
      self.include_host_ = 0

  def has_include_host(self): return self.has_include_host_

  def include_all(self): return self.include_all_

  def set_include_all(self, x):
    self.has_include_all_ = 1
    self.include_all_ = x

  def clear_include_all(self):
    if self.has_include_all_:
      self.has_include_all_ = 0
      self.include_all_ = 0

  def has_include_all(self): return self.has_include_all_

  def cache_iterator(self): return self.cache_iterator_

  def set_cache_iterator(self, x):
    self.has_cache_iterator_ = 1
    self.cache_iterator_ = x

  def clear_cache_iterator(self):
    if self.has_cache_iterator_:
      self.has_cache_iterator_ = 0
      self.cache_iterator_ = 0

  def has_cache_iterator(self): return self.has_cache_iterator_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_app_id()): self.set_app_id(x.app_id())
    for i in xrange(x.version_id_size()): self.add_version_id(x.version_id(i))
    if (x.has_start_time()): self.set_start_time(x.start_time())
    if (x.has_end_time()): self.set_end_time(x.end_time())
    if (x.has_offset()): self.mutable_offset().MergeFrom(x.offset())
    for i in xrange(x.request_id_size()): self.add_request_id(x.request_id(i))
    if (x.has_minimum_log_level()): self.set_minimum_log_level(x.minimum_log_level())
    if (x.has_include_incomplete()): self.set_include_incomplete(x.include_incomplete())
    if (x.has_count()): self.set_count(x.count())
    if (x.has_include_app_logs()): self.set_include_app_logs(x.include_app_logs())
    if (x.has_include_host()): self.set_include_host(x.include_host())
    if (x.has_include_all()): self.set_include_all(x.include_all())
    if (x.has_cache_iterator()): self.set_cache_iterator(x.cache_iterator())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.LogReadRequest', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.LogReadRequest')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.LogReadRequest')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.LogReadRequest', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.LogReadRequest', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.LogReadRequest', s)


  def Equals(self, x):
    if x is self: return 1
    if self.has_app_id_ != x.has_app_id_: return 0
    if self.has_app_id_ and self.app_id_ != x.app_id_: return 0
    if len(self.version_id_) != len(x.version_id_): return 0
    for e1, e2 in zip(self.version_id_, x.version_id_):
      if e1 != e2: return 0
    if self.has_start_time_ != x.has_start_time_: return 0
    if self.has_start_time_ and self.start_time_ != x.start_time_: return 0
    if self.has_end_time_ != x.has_end_time_: return 0
    if self.has_end_time_ and self.end_time_ != x.end_time_: return 0
    if self.has_offset_ != x.has_offset_: return 0
    if self.has_offset_ and self.offset_ != x.offset_: return 0
    if len(self.request_id_) != len(x.request_id_): return 0
    for e1, e2 in zip(self.request_id_, x.request_id_):
      if e1 != e2: return 0
    if self.has_minimum_log_level_ != x.has_minimum_log_level_: return 0
    if self.has_minimum_log_level_ and self.minimum_log_level_ != x.minimum_log_level_: return 0
    if self.has_include_incomplete_ != x.has_include_incomplete_: return 0
    if self.has_include_incomplete_ and self.include_incomplete_ != x.include_incomplete_: return 0
    if self.has_count_ != x.has_count_: return 0
    if self.has_count_ and self.count_ != x.count_: return 0
    if self.has_include_app_logs_ != x.has_include_app_logs_: return 0
    if self.has_include_app_logs_ and self.include_app_logs_ != x.include_app_logs_: return 0
    if self.has_include_host_ != x.has_include_host_: return 0
    if self.has_include_host_ and self.include_host_ != x.include_host_: return 0
    if self.has_include_all_ != x.has_include_all_: return 0
    if self.has_include_all_ and self.include_all_ != x.include_all_: return 0
    if self.has_cache_iterator_ != x.has_cache_iterator_: return 0
    if self.has_cache_iterator_ and self.cache_iterator_ != x.cache_iterator_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_app_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: app_id not set.')
    if (self.has_offset_ and not self.offset_.IsInitialized(debug_strs)): initialized = 0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.app_id_))
    n += 1 * len(self.version_id_)
    for i in xrange(len(self.version_id_)): n += self.lengthString(len(self.version_id_[i]))
    if (self.has_start_time_): n += 1 + self.lengthVarInt64(self.start_time_)
    if (self.has_end_time_): n += 1 + self.lengthVarInt64(self.end_time_)
    if (self.has_offset_): n += 1 + self.lengthString(self.offset_.ByteSize())
    n += 1 * len(self.request_id_)
    for i in xrange(len(self.request_id_)): n += self.lengthString(len(self.request_id_[i]))
    if (self.has_minimum_log_level_): n += 1 + self.lengthVarInt64(self.minimum_log_level_)
    if (self.has_include_incomplete_): n += 2
    if (self.has_count_): n += 1 + self.lengthVarInt64(self.count_)
    if (self.has_include_app_logs_): n += 2
    if (self.has_include_host_): n += 2
    if (self.has_include_all_): n += 2
    if (self.has_cache_iterator_): n += 2
    return n + 1

  def ByteSizePartial(self):
    n = 0
    if (self.has_app_id_):
      n += 1
      n += self.lengthString(len(self.app_id_))
    n += 1 * len(self.version_id_)
    for i in xrange(len(self.version_id_)): n += self.lengthString(len(self.version_id_[i]))
    if (self.has_start_time_): n += 1 + self.lengthVarInt64(self.start_time_)
    if (self.has_end_time_): n += 1 + self.lengthVarInt64(self.end_time_)
    if (self.has_offset_): n += 1 + self.lengthString(self.offset_.ByteSizePartial())
    n += 1 * len(self.request_id_)
    for i in xrange(len(self.request_id_)): n += self.lengthString(len(self.request_id_[i]))
    if (self.has_minimum_log_level_): n += 1 + self.lengthVarInt64(self.minimum_log_level_)
    if (self.has_include_incomplete_): n += 2
    if (self.has_count_): n += 1 + self.lengthVarInt64(self.count_)
    if (self.has_include_app_logs_): n += 2
    if (self.has_include_host_): n += 2
    if (self.has_include_all_): n += 2
    if (self.has_cache_iterator_): n += 2
    return n

  def Clear(self):
    self.clear_app_id()
    self.clear_version_id()
    self.clear_start_time()
    self.clear_end_time()
    self.clear_offset()
    self.clear_request_id()
    self.clear_minimum_log_level()
    self.clear_include_incomplete()
    self.clear_count()
    self.clear_include_app_logs()
    self.clear_include_host()
    self.clear_include_all()
    self.clear_cache_iterator()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.app_id_)
    for i in xrange(len(self.version_id_)):
      out.putVarInt32(18)
      out.putPrefixedString(self.version_id_[i])
    if (self.has_start_time_):
      out.putVarInt32(24)
      out.putVarInt64(self.start_time_)
    if (self.has_end_time_):
      out.putVarInt32(32)
      out.putVarInt64(self.end_time_)
    if (self.has_offset_):
      out.putVarInt32(42)
      out.putVarInt32(self.offset_.ByteSize())
      self.offset_.OutputUnchecked(out)
    for i in xrange(len(self.request_id_)):
      out.putVarInt32(50)
      out.putPrefixedString(self.request_id_[i])
    if (self.has_minimum_log_level_):
      out.putVarInt32(56)
      out.putVarInt32(self.minimum_log_level_)
    if (self.has_include_incomplete_):
      out.putVarInt32(64)
      out.putBoolean(self.include_incomplete_)
    if (self.has_count_):
      out.putVarInt32(72)
      out.putVarInt64(self.count_)
    if (self.has_include_app_logs_):
      out.putVarInt32(80)
      out.putBoolean(self.include_app_logs_)
    if (self.has_include_host_):
      out.putVarInt32(88)
      out.putBoolean(self.include_host_)
    if (self.has_include_all_):
      out.putVarInt32(96)
      out.putBoolean(self.include_all_)
    if (self.has_cache_iterator_):
      out.putVarInt32(104)
      out.putBoolean(self.cache_iterator_)

  def OutputPartial(self, out):
    if (self.has_app_id_):
      out.putVarInt32(10)
      out.putPrefixedString(self.app_id_)
    for i in xrange(len(self.version_id_)):
      out.putVarInt32(18)
      out.putPrefixedString(self.version_id_[i])
    if (self.has_start_time_):
      out.putVarInt32(24)
      out.putVarInt64(self.start_time_)
    if (self.has_end_time_):
      out.putVarInt32(32)
      out.putVarInt64(self.end_time_)
    if (self.has_offset_):
      out.putVarInt32(42)
      out.putVarInt32(self.offset_.ByteSizePartial())
      self.offset_.OutputPartial(out)
    for i in xrange(len(self.request_id_)):
      out.putVarInt32(50)
      out.putPrefixedString(self.request_id_[i])
    if (self.has_minimum_log_level_):
      out.putVarInt32(56)
      out.putVarInt32(self.minimum_log_level_)
    if (self.has_include_incomplete_):
      out.putVarInt32(64)
      out.putBoolean(self.include_incomplete_)
    if (self.has_count_):
      out.putVarInt32(72)
      out.putVarInt64(self.count_)
    if (self.has_include_app_logs_):
      out.putVarInt32(80)
      out.putBoolean(self.include_app_logs_)
    if (self.has_include_host_):
      out.putVarInt32(88)
      out.putBoolean(self.include_host_)
    if (self.has_include_all_):
      out.putVarInt32(96)
      out.putBoolean(self.include_all_)
    if (self.has_cache_iterator_):
      out.putVarInt32(104)
      out.putBoolean(self.cache_iterator_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_app_id(d.getPrefixedString())
        continue
      if tt == 18:
        self.add_version_id(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_start_time(d.getVarInt64())
        continue
      if tt == 32:
        self.set_end_time(d.getVarInt64())
        continue
      if tt == 42:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_offset().TryMerge(tmp)
        continue
      if tt == 50:
        self.add_request_id(d.getPrefixedString())
        continue
      if tt == 56:
        self.set_minimum_log_level(d.getVarInt32())
        continue
      if tt == 64:
        self.set_include_incomplete(d.getBoolean())
        continue
      if tt == 72:
        self.set_count(d.getVarInt64())
        continue
      if tt == 80:
        self.set_include_app_logs(d.getBoolean())
        continue
      if tt == 88:
        self.set_include_host(d.getBoolean())
        continue
      if tt == 96:
        self.set_include_all(d.getBoolean())
        continue
      if tt == 104:
        self.set_cache_iterator(d.getBoolean())
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_app_id_: res+=prefix+("app_id: %s\n" % self.DebugFormatString(self.app_id_))
    cnt=0
    for e in self.version_id_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("version_id%s: %s\n" % (elm, self.DebugFormatString(e)))
      cnt+=1
    if self.has_start_time_: res+=prefix+("start_time: %s\n" % self.DebugFormatInt64(self.start_time_))
    if self.has_end_time_: res+=prefix+("end_time: %s\n" % self.DebugFormatInt64(self.end_time_))
    if self.has_offset_:
      res+=prefix+"offset <\n"
      res+=self.offset_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    cnt=0
    for e in self.request_id_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("request_id%s: %s\n" % (elm, self.DebugFormatString(e)))
      cnt+=1
    if self.has_minimum_log_level_: res+=prefix+("minimum_log_level: %s\n" % self.DebugFormatInt32(self.minimum_log_level_))
    if self.has_include_incomplete_: res+=prefix+("include_incomplete: %s\n" % self.DebugFormatBool(self.include_incomplete_))
    if self.has_count_: res+=prefix+("count: %s\n" % self.DebugFormatInt64(self.count_))
    if self.has_include_app_logs_: res+=prefix+("include_app_logs: %s\n" % self.DebugFormatBool(self.include_app_logs_))
    if self.has_include_host_: res+=prefix+("include_host: %s\n" % self.DebugFormatBool(self.include_host_))
    if self.has_include_all_: res+=prefix+("include_all: %s\n" % self.DebugFormatBool(self.include_all_))
    if self.has_cache_iterator_: res+=prefix+("cache_iterator: %s\n" % self.DebugFormatBool(self.cache_iterator_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kapp_id = 1
  kversion_id = 2
  kstart_time = 3
  kend_time = 4
  koffset = 5
  krequest_id = 6
  kminimum_log_level = 7
  kinclude_incomplete = 8
  kcount = 9
  kinclude_app_logs = 10
  kinclude_host = 11
  kinclude_all = 12
  kcache_iterator = 13

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "app_id",
    2: "version_id",
    3: "start_time",
    4: "end_time",
    5: "offset",
    6: "request_id",
    7: "minimum_log_level",
    8: "include_incomplete",
    9: "count",
    10: "include_app_logs",
    11: "include_host",
    12: "include_all",
    13: "cache_iterator",
  }, 13)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
    4: ProtocolBuffer.Encoder.NUMERIC,
    5: ProtocolBuffer.Encoder.STRING,
    6: ProtocolBuffer.Encoder.STRING,
    7: ProtocolBuffer.Encoder.NUMERIC,
    8: ProtocolBuffer.Encoder.NUMERIC,
    9: ProtocolBuffer.Encoder.NUMERIC,
    10: ProtocolBuffer.Encoder.NUMERIC,
    11: ProtocolBuffer.Encoder.NUMERIC,
    12: ProtocolBuffer.Encoder.NUMERIC,
    13: ProtocolBuffer.Encoder.NUMERIC,
  }, 13, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChlhcHBob3N0aW5nLkxvZ1JlYWRSZXF1ZXN0ExoGYXBwX2lkIAEoAjAJOAIUExoKdmVyc2lvbl9pZCACKAIwCTgDFBMaCnN0YXJ0X3RpbWUgAygAMAM4ARQTGghlbmRfdGltZSAEKAAwAzgBFBMaBm9mZnNldCAFKAIwCzgBShRhcHBob3N0aW5nLkxvZ09mZnNldBQTGgpyZXF1ZXN0X2lkIAYoAjAJOAMUExoRbWluaW11bV9sb2dfbGV2ZWwgBygAMAU4ARQTGhJpbmNsdWRlX2luY29tcGxldGUgCCgAMAg4ARQTGgVjb3VudCAJKAAwAzgBFBMaEGluY2x1ZGVfYXBwX2xvZ3MgCigAMAg4ARQTGgxpbmNsdWRlX2hvc3QgCygAMAg4ARQTGgtpbmNsdWRlX2FsbCAMKAAwCDgBFBMaDmNhY2hlX2l0ZXJhdG9yIA0oADAIOAEUwgEXYXBwaG9zdGluZy5GbHVzaFJlcXVlc3Q="))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())

class LogReadResponse(ProtocolBuffer.ProtocolMessage):
  has_offset_ = 0
  offset_ = None

  def __init__(self, contents=None):
    self.log_ = []
    self.lazy_init_lock_ = thread.allocate_lock()
    if contents is not None: self.MergeFromString(contents)

  def log_size(self): return len(self.log_)
  def log_list(self): return self.log_

  def log(self, i):
    return self.log_[i]

  def mutable_log(self, i):
    return self.log_[i]

  def add_log(self):
    x = RequestLog()
    self.log_.append(x)
    return x

  def clear_log(self):
    self.log_ = []
  def offset(self):
    if self.offset_ is None:
      self.lazy_init_lock_.acquire()
      try:
        if self.offset_ is None: self.offset_ = LogOffset()
      finally:
        self.lazy_init_lock_.release()
    return self.offset_

  def mutable_offset(self): self.has_offset_ = 1; return self.offset()

  def clear_offset(self):

    if self.has_offset_:
      self.has_offset_ = 0;
      if self.offset_ is not None: self.offset_.Clear()

  def has_offset(self): return self.has_offset_


  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.log_size()): self.add_log().CopyFrom(x.log(i))
    if (x.has_offset()): self.mutable_offset().MergeFrom(x.offset())

  if _net_proto___parse__python is not None:
    def _CMergeFromString(self, s):
      _net_proto___parse__python.MergeFromString(self, 'apphosting.LogReadResponse', s)

  if _net_proto___parse__python is not None:
    def _CEncode(self):
      return _net_proto___parse__python.Encode(self, 'apphosting.LogReadResponse')

  if _net_proto___parse__python is not None:
    def _CEncodePartial(self):
      return _net_proto___parse__python.EncodePartial(self, 'apphosting.LogReadResponse')

  if _net_proto___parse__python is not None:
    def _CToASCII(self, output_format):
      return _net_proto___parse__python.ToASCII(self, 'apphosting.LogReadResponse', output_format)


  if _net_proto___parse__python is not None:
    def ParseASCII(self, s):
      _net_proto___parse__python.ParseASCII(self, 'apphosting.LogReadResponse', s)


  if _net_proto___parse__python is not None:
    def ParseASCIIIgnoreUnknown(self, s):
      _net_proto___parse__python.ParseASCIIIgnoreUnknown(self, 'apphosting.LogReadResponse', s)


  def Equals(self, x):
    if x is self: return 1
    if len(self.log_) != len(x.log_): return 0
    for e1, e2 in zip(self.log_, x.log_):
      if e1 != e2: return 0
    if self.has_offset_ != x.has_offset_: return 0
    if self.has_offset_ and self.offset_ != x.offset_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.log_:
      if not p.IsInitialized(debug_strs): initialized=0
    if (self.has_offset_ and not self.offset_.IsInitialized(debug_strs)): initialized = 0
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.log_)
    for i in xrange(len(self.log_)): n += self.lengthString(self.log_[i].ByteSize())
    if (self.has_offset_): n += 1 + self.lengthString(self.offset_.ByteSize())
    return n

  def ByteSizePartial(self):
    n = 0
    n += 1 * len(self.log_)
    for i in xrange(len(self.log_)): n += self.lengthString(self.log_[i].ByteSizePartial())
    if (self.has_offset_): n += 1 + self.lengthString(self.offset_.ByteSizePartial())
    return n

  def Clear(self):
    self.clear_log()
    self.clear_offset()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.log_)):
      out.putVarInt32(10)
      out.putVarInt32(self.log_[i].ByteSize())
      self.log_[i].OutputUnchecked(out)
    if (self.has_offset_):
      out.putVarInt32(18)
      out.putVarInt32(self.offset_.ByteSize())
      self.offset_.OutputUnchecked(out)

  def OutputPartial(self, out):
    for i in xrange(len(self.log_)):
      out.putVarInt32(10)
      out.putVarInt32(self.log_[i].ByteSizePartial())
      self.log_[i].OutputPartial(out)
    if (self.has_offset_):
      out.putVarInt32(18)
      out.putVarInt32(self.offset_.ByteSizePartial())
      self.offset_.OutputPartial(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_log().TryMerge(tmp)
        continue
      if tt == 18:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_offset().TryMerge(tmp)
        continue


      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.log_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("log%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    if self.has_offset_:
      res+=prefix+"offset <\n"
      res+=self.offset_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  klog = 1
  koffset = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "log",
    2: "offset",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)


  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
  _SERIALIZED_DESCRIPTOR = array.array('B')
  _SERIALIZED_DESCRIPTOR.fromstring(base64.decodestring("WithcHBob3N0aW5nL2FwaS9sb2dzZXJ2aWNlL2xvZ19zZXJ2aWNlLnByb3RvChphcHBob3N0aW5nLkxvZ1JlYWRSZXNwb25zZRMaA2xvZyABKAIwCzgDShVhcHBob3N0aW5nLlJlcXVlc3RMb2cUExoGb2Zmc2V0IAIoAjALOAFKFGFwcGhvc3RpbmcuTG9nT2Zmc2V0FMIBF2FwcGhvc3RpbmcuRmx1c2hSZXF1ZXN0"))
  if _net_proto___parse__python is not None:
    _net_proto___parse__python.RegisterType(
        _SERIALIZED_DESCRIPTOR.tostring())



class _LogService_ClientBaseStub(_client_stub_base_class):
  """Makes Stubby RPC calls to a LogService server."""

  __slots__ = (
      '_protorpc_Flush', '_full_name_Flush',
      '_protorpc_SetStatus', '_full_name_SetStatus',
  )

  def __init__(self, rpc_stub):
    self._stub = rpc_stub

    self._protorpc_Flush = pywraprpc.RPC()
    self._full_name_Flush = self._stub.GetFullMethodName(
        'Flush')

    self._protorpc_SetStatus = pywraprpc.RPC()
    self._full_name_SetStatus = self._stub.GetFullMethodName(
        'SetStatus')

  def Flush(self, request, rpc=None, callback=None, response=None):
    """Make a Flush RPC call.

    Args:
      request: a FlushRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The google.appengine.api.api_base_pb.VoidProto if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = google.appengine.api.api_base_pb.VoidProto
    return self._MakeCall(rpc,
                          self._full_name_Flush,
                          'Flush',
                          request,
                          response,
                          callback,
                          self._protorpc_Flush)

  def SetStatus(self, request, rpc=None, callback=None, response=None):
    """Make a SetStatus RPC call.

    Args:
      request: a SetStatusRequest instance.
      rpc: Optional RPC instance to use for the call.
      callback: Optional final callback. Will be called as
          callback(rpc, result) when the rpc completes. If None, the
          call is synchronous.
      response: Optional ProtocolMessage to be filled in with response.

    Returns:
      The google.appengine.api.api_base_pb.VoidProto if callback is None. Otherwise, returns None.
    """

    if response is None:
      response = google.appengine.api.api_base_pb.VoidProto
    return self._MakeCall(rpc,
                          self._full_name_SetStatus,
                          'SetStatus',
                          request,
                          response,
                          callback,
                          self._protorpc_SetStatus)


class _LogService_ClientStub(_LogService_ClientBaseStub):
  __slots__ = ('_params',)
  def __init__(self, rpc_stub_parameters, service_name):
    if service_name is None:
      service_name = 'LogService'
    _LogService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, rpc_stub_parameters))
    self._params = rpc_stub_parameters


class _LogService_RPC2ClientStub(_LogService_ClientBaseStub):
  __slots__ = ()
  def __init__(self, server, channel, service_name):
    if service_name is None:
      service_name = 'LogService'
    if channel is not None:
      if channel.version() == 1:
        raise RuntimeError('Expecting an RPC2 channel to create the stub')
      _LogService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, channel))
    elif server is not None:
      _LogService_ClientBaseStub.__init__(self, pywraprpc.RPC_GenericStub(service_name, pywraprpc.NewClientChannel(server)))
    else:
      raise RuntimeError('Invalid argument combination to create a stub')


class LogService(_server_stub_base_class):
  """Base class for LogService Stubby servers."""

  def __init__(self, *args, **kwargs):
    """Creates a Stubby RPC server.

    See BaseRpcServer.__init__ in rpcserver.py for detail on arguments.
    """
    if _server_stub_base_class is object:
      raise NotImplementedError('Add //net/rpc/python:rpcserver as a '
                                'dependency for Stubby server support.')
    _server_stub_base_class.__init__(self, 'apphosting.LogService', *args, **kwargs)

  @staticmethod
  def NewStub(rpc_stub_parameters, service_name=None):
    """Creates a new LogService Stubby client stub.

    Args:
      rpc_stub_parameters: an RPC_StubParameter instance.
      service_name: the service name used by the Stubby server.
    """

    if _client_stub_base_class is object:
      raise RuntimeError('Add //net/rpc/python as a dependency to use Stubby')
    return _LogService_ClientStub(rpc_stub_parameters, service_name)

  @staticmethod
  def NewRPC2Stub(server=None, channel=None, service_name=None):
    """Creates a new LogService Stubby2 client stub.

    Args:
      server: host:port or bns address.
      channel: directly use a channel to create a stub. Will ignore server
          argument if this is specified.
      service_name: the service name used by the Stubby server.
    """

    if _client_stub_base_class is object:
      raise RuntimeError('Add //net/rpc/python as a dependency to use Stubby')
    return _LogService_RPC2ClientStub(server, channel, service_name)

  def Flush(self, rpc, request, response):
    """Handles a Flush RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a FlushRequest that contains the client request
      response: a google.appengine.api.api_base_pb.VoidProto that should be modified to send the response
    """
    raise NotImplementedError


  def SetStatus(self, rpc, request, response):
    """Handles a SetStatus RPC call. You should override this.

    Args:
      rpc: a Stubby RPC object
      request: a SetStatusRequest that contains the client request
      response: a google.appengine.api.api_base_pb.VoidProto that should be modified to send the response
    """
    raise NotImplementedError

  def _AddMethodAttributes(self):
    """Sets attributes on Python RPC handlers.

    See BaseRpcServer in rpcserver.py for details.
    """
    rpcserver._GetHandlerDecorator(
        self.Flush.im_func,
        FlushRequest,
        google.appengine.api.api_base_pb.VoidProto,
        None,
        'none')
    rpcserver._GetHandlerDecorator(
        self.SetStatus.im_func,
        SetStatusRequest,
        google.appengine.api.api_base_pb.VoidProto,
        None,
        'none')


__all__ = ['FlushRequest','SetStatusRequest','LogOffset','LogLine','RequestLog','LogReadRequest','LogReadResponse','LogService']
