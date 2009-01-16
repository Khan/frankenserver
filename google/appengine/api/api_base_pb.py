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
import dummy_thread as thread

__pychecker__ = """maxreturns=0 maxbranches=0 no-callinit
                   unusednames=printElemNumber,debug_strs no-special"""

class StringProto(ProtocolBuffer.ProtocolMessage):
  has_value_ = 0
  value_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def value(self): return self.value_

  def set_value(self, x):
    self.has_value_ = 1
    self.value_ = x

  def clear_value(self):
    self.has_value_ = 0
    self.value_ = ""

  def has_value(self): return self.has_value_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.value_))
    return n + 1

  def Clear(self):
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_value(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatString(self.value_))
    return res

  kvalue = 1

  _TEXT = (
   "ErrorCode",
   "value",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.STRING,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class Integer32Proto(ProtocolBuffer.ProtocolMessage):
  has_value_ = 0
  value_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def value(self): return self.value_

  def set_value(self, x):
    self.has_value_ = 1
    self.value_ = x

  def clear_value(self):
    self.has_value_ = 0
    self.value_ = 0

  def has_value(self): return self.has_value_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.value_)
    return n + 1

  def Clear(self):
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putVarInt32(self.value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_value(d.getVarInt32())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatInt32(self.value_))
    return res

  kvalue = 1

  _TEXT = (
   "ErrorCode",
   "value",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.NUMERIC,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class Integer64Proto(ProtocolBuffer.ProtocolMessage):
  has_value_ = 0
  value_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def value(self): return self.value_

  def set_value(self, x):
    self.has_value_ = 1
    self.value_ = x

  def clear_value(self):
    self.has_value_ = 0
    self.value_ = 0

  def has_value(self): return self.has_value_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.value_)
    return n + 1

  def Clear(self):
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putVarInt64(self.value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_value(d.getVarInt64())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatInt64(self.value_))
    return res

  kvalue = 1

  _TEXT = (
   "ErrorCode",
   "value",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.NUMERIC,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class BoolProto(ProtocolBuffer.ProtocolMessage):
  has_value_ = 0
  value_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def value(self): return self.value_

  def set_value(self, x):
    self.has_value_ = 1
    self.value_ = x

  def clear_value(self):
    self.has_value_ = 0
    self.value_ = 0

  def has_value(self): return self.has_value_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    return n + 2

  def Clear(self):
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putBoolean(self.value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_value(d.getBoolean())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatBool(self.value_))
    return res

  kvalue = 1

  _TEXT = (
   "ErrorCode",
   "value",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.NUMERIC,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class DoubleProto(ProtocolBuffer.ProtocolMessage):
  has_value_ = 0
  value_ = 0.0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def value(self): return self.value_

  def set_value(self, x):
    self.has_value_ = 1
    self.value_ = x

  def clear_value(self):
    self.has_value_ = 0
    self.value_ = 0.0

  def has_value(self): return self.has_value_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    return n + 9

  def Clear(self):
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(9)
    out.putDouble(self.value_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 9:
        self.set_value(d.getDouble())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormat(self.value_))
    return res

  kvalue = 1

  _TEXT = (
   "ErrorCode",
   "value",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.DOUBLE,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class VoidProto(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    pass
    if contents is not None: self.MergeFromString(contents)


  def MergeFrom(self, x):
    assert x is not self

  def Equals(self, x):
    if x is self: return 1
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    return n + 0

  def Clear(self):
    pass

  def OutputUnchecked(self, out):
    pass

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    return res


  _TEXT = (
   "ErrorCode",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""

__all__ = ['StringProto','Integer32Proto','Integer64Proto','BoolProto','DoubleProto','VoidProto']
