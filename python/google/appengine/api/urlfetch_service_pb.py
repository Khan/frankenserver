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

from google.appengine.api.api_base_pb import StringProto
class URLFetchServiceError(ProtocolBuffer.ProtocolMessage):

  OK           =    0
  INVALID_URL  =    1
  FETCH_ERROR  =    2
  UNSPECIFIED_ERROR =    3
  RESPONSE_TOO_LARGE =    4
  DEADLINE_EXCEEDED =    5

  _ErrorCode_NAMES = {
    0: "OK",
    1: "INVALID_URL",
    2: "FETCH_ERROR",
    3: "UNSPECIFIED_ERROR",
    4: "RESPONSE_TOO_LARGE",
    5: "DEADLINE_EXCEEDED",
  }

  def ErrorCode_Name(cls, x): return cls._ErrorCode_NAMES.get(x, "")
  ErrorCode_Name = classmethod(ErrorCode_Name)


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
class URLFetchRequest_Header(ProtocolBuffer.ProtocolMessage):
  has_key_ = 0
  key_ = ""
  has_value_ = 0
  value_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def key(self): return self.key_

  def set_key(self, x):
    self.has_key_ = 1
    self.key_ = x

  def clear_key(self):
    if self.has_key_:
      self.has_key_ = 0
      self.key_ = ""

  def has_key(self): return self.has_key_

  def value(self): return self.value_

  def set_value(self, x):
    self.has_value_ = 1
    self.value_ = x

  def clear_value(self):
    if self.has_value_:
      self.has_value_ = 0
      self.value_ = ""

  def has_value(self): return self.has_value_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_key()): self.set_key(x.key())
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_key_ != x.has_key_: return 0
    if self.has_key_ and self.key_ != x.key_: return 0
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_key_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: key not set.')
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.key_))
    n += self.lengthString(len(self.value_))
    return n + 2

  def Clear(self):
    self.clear_key()
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(34)
    out.putPrefixedString(self.key_)
    out.putVarInt32(42)
    out.putPrefixedString(self.value_)

  def TryMerge(self, d):
    while 1:
      tt = d.getVarInt32()
      if tt == 28: break
      if tt == 34:
        self.set_key(d.getPrefixedString())
        continue
      if tt == 42:
        self.set_value(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_key_: res+=prefix+("Key: %s\n" % self.DebugFormatString(self.key_))
    if self.has_value_: res+=prefix+("Value: %s\n" % self.DebugFormatString(self.value_))
    return res

class URLFetchRequest(ProtocolBuffer.ProtocolMessage):

  GET          =    1
  POST         =    2
  HEAD         =    3
  PUT          =    4
  DELETE       =    5

  _RequestMethod_NAMES = {
    1: "GET",
    2: "POST",
    3: "HEAD",
    4: "PUT",
    5: "DELETE",
  }

  def RequestMethod_Name(cls, x): return cls._RequestMethod_NAMES.get(x, "")
  RequestMethod_Name = classmethod(RequestMethod_Name)

  has_method_ = 0
  method_ = 0
  has_url_ = 0
  url_ = ""
  has_payload_ = 0
  payload_ = ""
  has_followredirects_ = 0
  followredirects_ = 1

  def __init__(self, contents=None):
    self.header_ = []
    if contents is not None: self.MergeFromString(contents)

  def method(self): return self.method_

  def set_method(self, x):
    self.has_method_ = 1
    self.method_ = x

  def clear_method(self):
    if self.has_method_:
      self.has_method_ = 0
      self.method_ = 0

  def has_method(self): return self.has_method_

  def url(self): return self.url_

  def set_url(self, x):
    self.has_url_ = 1
    self.url_ = x

  def clear_url(self):
    if self.has_url_:
      self.has_url_ = 0
      self.url_ = ""

  def has_url(self): return self.has_url_

  def header_size(self): return len(self.header_)
  def header_list(self): return self.header_

  def header(self, i):
    return self.header_[i]

  def mutable_header(self, i):
    return self.header_[i]

  def add_header(self):
    x = URLFetchRequest_Header()
    self.header_.append(x)
    return x

  def clear_header(self):
    self.header_ = []
  def payload(self): return self.payload_

  def set_payload(self, x):
    self.has_payload_ = 1
    self.payload_ = x

  def clear_payload(self):
    if self.has_payload_:
      self.has_payload_ = 0
      self.payload_ = ""

  def has_payload(self): return self.has_payload_

  def followredirects(self): return self.followredirects_

  def set_followredirects(self, x):
    self.has_followredirects_ = 1
    self.followredirects_ = x

  def clear_followredirects(self):
    if self.has_followredirects_:
      self.has_followredirects_ = 0
      self.followredirects_ = 1

  def has_followredirects(self): return self.has_followredirects_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_method()): self.set_method(x.method())
    if (x.has_url()): self.set_url(x.url())
    for i in xrange(x.header_size()): self.add_header().CopyFrom(x.header(i))
    if (x.has_payload()): self.set_payload(x.payload())
    if (x.has_followredirects()): self.set_followredirects(x.followredirects())

  def Equals(self, x):
    if x is self: return 1
    if self.has_method_ != x.has_method_: return 0
    if self.has_method_ and self.method_ != x.method_: return 0
    if self.has_url_ != x.has_url_: return 0
    if self.has_url_ and self.url_ != x.url_: return 0
    if len(self.header_) != len(x.header_): return 0
    for e1, e2 in zip(self.header_, x.header_):
      if e1 != e2: return 0
    if self.has_payload_ != x.has_payload_: return 0
    if self.has_payload_ and self.payload_ != x.payload_: return 0
    if self.has_followredirects_ != x.has_followredirects_: return 0
    if self.has_followredirects_ and self.followredirects_ != x.followredirects_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_method_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: method not set.')
    if (not self.has_url_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: url not set.')
    for p in self.header_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.method_)
    n += self.lengthString(len(self.url_))
    n += 2 * len(self.header_)
    for i in xrange(len(self.header_)): n += self.header_[i].ByteSize()
    if (self.has_payload_): n += 1 + self.lengthString(len(self.payload_))
    if (self.has_followredirects_): n += 2
    return n + 2

  def Clear(self):
    self.clear_method()
    self.clear_url()
    self.clear_header()
    self.clear_payload()
    self.clear_followredirects()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putVarInt32(self.method_)
    out.putVarInt32(18)
    out.putPrefixedString(self.url_)
    for i in xrange(len(self.header_)):
      out.putVarInt32(27)
      self.header_[i].OutputUnchecked(out)
      out.putVarInt32(28)
    if (self.has_payload_):
      out.putVarInt32(50)
      out.putPrefixedString(self.payload_)
    if (self.has_followredirects_):
      out.putVarInt32(56)
      out.putBoolean(self.followredirects_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_method(d.getVarInt32())
        continue
      if tt == 18:
        self.set_url(d.getPrefixedString())
        continue
      if tt == 27:
        self.add_header().TryMerge(d)
        continue
      if tt == 50:
        self.set_payload(d.getPrefixedString())
        continue
      if tt == 56:
        self.set_followredirects(d.getBoolean())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_method_: res+=prefix+("Method: %s\n" % self.DebugFormatInt32(self.method_))
    if self.has_url_: res+=prefix+("Url: %s\n" % self.DebugFormatString(self.url_))
    cnt=0
    for e in self.header_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("Header%s {\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+"}\n"
      cnt+=1
    if self.has_payload_: res+=prefix+("Payload: %s\n" % self.DebugFormatString(self.payload_))
    if self.has_followredirects_: res+=prefix+("FollowRedirects: %s\n" % self.DebugFormatBool(self.followredirects_))
    return res

  kMethod = 1
  kUrl = 2
  kHeaderGroup = 3
  kHeaderKey = 4
  kHeaderValue = 5
  kPayload = 6
  kFollowRedirects = 7

  _TEXT = (
   "ErrorCode",
   "Method",
   "Url",
   "Header",
   "Key",
   "Value",
   "Payload",
   "FollowRedirects",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.NUMERIC,

   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.STARTGROUP,

   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.NUMERIC,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class URLFetchResponse_Header(ProtocolBuffer.ProtocolMessage):
  has_key_ = 0
  key_ = ""
  has_value_ = 0
  value_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def key(self): return self.key_

  def set_key(self, x):
    self.has_key_ = 1
    self.key_ = x

  def clear_key(self):
    if self.has_key_:
      self.has_key_ = 0
      self.key_ = ""

  def has_key(self): return self.has_key_

  def value(self): return self.value_

  def set_value(self, x):
    self.has_value_ = 1
    self.value_ = x

  def clear_value(self):
    if self.has_value_:
      self.has_value_ = 0
      self.value_ = ""

  def has_value(self): return self.has_value_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_key()): self.set_key(x.key())
    if (x.has_value()): self.set_value(x.value())

  def Equals(self, x):
    if x is self: return 1
    if self.has_key_ != x.has_key_: return 0
    if self.has_key_ and self.key_ != x.key_: return 0
    if self.has_value_ != x.has_value_: return 0
    if self.has_value_ and self.value_ != x.value_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_key_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: key not set.')
    if (not self.has_value_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: value not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.key_))
    n += self.lengthString(len(self.value_))
    return n + 2

  def Clear(self):
    self.clear_key()
    self.clear_value()

  def OutputUnchecked(self, out):
    out.putVarInt32(34)
    out.putPrefixedString(self.key_)
    out.putVarInt32(42)
    out.putPrefixedString(self.value_)

  def TryMerge(self, d):
    while 1:
      tt = d.getVarInt32()
      if tt == 28: break
      if tt == 34:
        self.set_key(d.getPrefixedString())
        continue
      if tt == 42:
        self.set_value(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_key_: res+=prefix+("Key: %s\n" % self.DebugFormatString(self.key_))
    if self.has_value_: res+=prefix+("Value: %s\n" % self.DebugFormatString(self.value_))
    return res

class URLFetchResponse(ProtocolBuffer.ProtocolMessage):
  has_content_ = 0
  content_ = ""
  has_statuscode_ = 0
  statuscode_ = 0
  has_contentwastruncated_ = 0
  contentwastruncated_ = 0

  def __init__(self, contents=None):
    self.header_ = []
    if contents is not None: self.MergeFromString(contents)

  def content(self): return self.content_

  def set_content(self, x):
    self.has_content_ = 1
    self.content_ = x

  def clear_content(self):
    if self.has_content_:
      self.has_content_ = 0
      self.content_ = ""

  def has_content(self): return self.has_content_

  def statuscode(self): return self.statuscode_

  def set_statuscode(self, x):
    self.has_statuscode_ = 1
    self.statuscode_ = x

  def clear_statuscode(self):
    if self.has_statuscode_:
      self.has_statuscode_ = 0
      self.statuscode_ = 0

  def has_statuscode(self): return self.has_statuscode_

  def header_size(self): return len(self.header_)
  def header_list(self): return self.header_

  def header(self, i):
    return self.header_[i]

  def mutable_header(self, i):
    return self.header_[i]

  def add_header(self):
    x = URLFetchResponse_Header()
    self.header_.append(x)
    return x

  def clear_header(self):
    self.header_ = []
  def contentwastruncated(self): return self.contentwastruncated_

  def set_contentwastruncated(self, x):
    self.has_contentwastruncated_ = 1
    self.contentwastruncated_ = x

  def clear_contentwastruncated(self):
    if self.has_contentwastruncated_:
      self.has_contentwastruncated_ = 0
      self.contentwastruncated_ = 0

  def has_contentwastruncated(self): return self.has_contentwastruncated_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_content()): self.set_content(x.content())
    if (x.has_statuscode()): self.set_statuscode(x.statuscode())
    for i in xrange(x.header_size()): self.add_header().CopyFrom(x.header(i))
    if (x.has_contentwastruncated()): self.set_contentwastruncated(x.contentwastruncated())

  def Equals(self, x):
    if x is self: return 1
    if self.has_content_ != x.has_content_: return 0
    if self.has_content_ and self.content_ != x.content_: return 0
    if self.has_statuscode_ != x.has_statuscode_: return 0
    if self.has_statuscode_ and self.statuscode_ != x.statuscode_: return 0
    if len(self.header_) != len(x.header_): return 0
    for e1, e2 in zip(self.header_, x.header_):
      if e1 != e2: return 0
    if self.has_contentwastruncated_ != x.has_contentwastruncated_: return 0
    if self.has_contentwastruncated_ and self.contentwastruncated_ != x.contentwastruncated_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_statuscode_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: statuscode not set.')
    for p in self.header_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_content_): n += 1 + self.lengthString(len(self.content_))
    n += self.lengthVarInt64(self.statuscode_)
    n += 2 * len(self.header_)
    for i in xrange(len(self.header_)): n += self.header_[i].ByteSize()
    if (self.has_contentwastruncated_): n += 2
    return n + 1

  def Clear(self):
    self.clear_content()
    self.clear_statuscode()
    self.clear_header()
    self.clear_contentwastruncated()

  def OutputUnchecked(self, out):
    if (self.has_content_):
      out.putVarInt32(10)
      out.putPrefixedString(self.content_)
    out.putVarInt32(16)
    out.putVarInt32(self.statuscode_)
    for i in xrange(len(self.header_)):
      out.putVarInt32(27)
      self.header_[i].OutputUnchecked(out)
      out.putVarInt32(28)
    if (self.has_contentwastruncated_):
      out.putVarInt32(48)
      out.putBoolean(self.contentwastruncated_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_content(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_statuscode(d.getVarInt32())
        continue
      if tt == 27:
        self.add_header().TryMerge(d)
        continue
      if tt == 48:
        self.set_contentwastruncated(d.getBoolean())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_content_: res+=prefix+("Content: %s\n" % self.DebugFormatString(self.content_))
    if self.has_statuscode_: res+=prefix+("StatusCode: %s\n" % self.DebugFormatInt32(self.statuscode_))
    cnt=0
    for e in self.header_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("Header%s {\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+"}\n"
      cnt+=1
    if self.has_contentwastruncated_: res+=prefix+("ContentWasTruncated: %s\n" % self.DebugFormatBool(self.contentwastruncated_))
    return res

  kContent = 1
  kStatusCode = 2
  kHeaderGroup = 3
  kHeaderKey = 4
  kHeaderValue = 5
  kContentWasTruncated = 6

  _TEXT = (
   "ErrorCode",
   "Content",
   "StatusCode",
   "Header",
   "Key",
   "Value",
   "ContentWasTruncated",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.NUMERIC,

   ProtocolBuffer.Encoder.STARTGROUP,

   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.NUMERIC,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""

__all__ = ['URLFetchServiceError','URLFetchRequest','URLFetchRequest_Header','URLFetchResponse','URLFetchResponse_Header']
