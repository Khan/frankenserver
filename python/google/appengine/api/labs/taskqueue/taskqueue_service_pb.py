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

from google.appengine.datastore.datastore_v3_pb import *
class TaskQueueServiceError(ProtocolBuffer.ProtocolMessage):

  OK           =    0
  UNKNOWN_QUEUE =    1
  TRANSIENT_ERROR =    2
  INTERNAL_ERROR =    3
  TASK_TOO_LARGE =    4
  INVALID_TASK_NAME =    5
  INVALID_QUEUE_NAME =    6
  INVALID_URL  =    7
  INVALID_QUEUE_RATE =    8
  PERMISSION_DENIED =    9
  TASK_ALREADY_EXISTS =   10
  TOMBSTONED_TASK =   11
  INVALID_ETA  =   12
  INVALID_REQUEST =   13
  UNKNOWN_TASK =   14
  DATASTORE_ERROR = 10000

  _ErrorCode_NAMES = {
    0: "OK",
    1: "UNKNOWN_QUEUE",
    2: "TRANSIENT_ERROR",
    3: "INTERNAL_ERROR",
    4: "TASK_TOO_LARGE",
    5: "INVALID_TASK_NAME",
    6: "INVALID_QUEUE_NAME",
    7: "INVALID_URL",
    8: "INVALID_QUEUE_RATE",
    9: "PERMISSION_DENIED",
    10: "TASK_ALREADY_EXISTS",
    11: "TOMBSTONED_TASK",
    12: "INVALID_ETA",
    13: "INVALID_REQUEST",
    14: "UNKNOWN_TASK",
    10000: "DATASTORE_ERROR",
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


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])


  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
  }, 0)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
  }, 0, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueAddRequest_Header(ProtocolBuffer.ProtocolMessage):
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
    out.putVarInt32(58)
    out.putPrefixedString(self.key_)
    out.putVarInt32(66)
    out.putPrefixedString(self.value_)

  def TryMerge(self, d):
    while 1:
      tt = d.getVarInt32()
      if tt == 52: break
      if tt == 58:
        self.set_key(d.getPrefixedString())
        continue
      if tt == 66:
        self.set_value(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_key_: res+=prefix+("key: %s\n" % self.DebugFormatString(self.key_))
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatString(self.value_))
    return res

class TaskQueueAddRequest(ProtocolBuffer.ProtocolMessage):

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

  has_queue_name_ = 0
  queue_name_ = ""
  has_task_name_ = 0
  task_name_ = ""
  has_eta_usec_ = 0
  eta_usec_ = 0
  has_method_ = 0
  method_ = 2
  has_url_ = 0
  url_ = ""
  has_body_ = 0
  body_ = ""
  has_transaction_ = 0
  transaction_ = None

  def __init__(self, contents=None):
    self.header_ = []
    self.lazy_init_lock_ = thread.allocate_lock()
    if contents is not None: self.MergeFromString(contents)

  def queue_name(self): return self.queue_name_

  def set_queue_name(self, x):
    self.has_queue_name_ = 1
    self.queue_name_ = x

  def clear_queue_name(self):
    if self.has_queue_name_:
      self.has_queue_name_ = 0
      self.queue_name_ = ""

  def has_queue_name(self): return self.has_queue_name_

  def task_name(self): return self.task_name_

  def set_task_name(self, x):
    self.has_task_name_ = 1
    self.task_name_ = x

  def clear_task_name(self):
    if self.has_task_name_:
      self.has_task_name_ = 0
      self.task_name_ = ""

  def has_task_name(self): return self.has_task_name_

  def eta_usec(self): return self.eta_usec_

  def set_eta_usec(self, x):
    self.has_eta_usec_ = 1
    self.eta_usec_ = x

  def clear_eta_usec(self):
    if self.has_eta_usec_:
      self.has_eta_usec_ = 0
      self.eta_usec_ = 0

  def has_eta_usec(self): return self.has_eta_usec_

  def method(self): return self.method_

  def set_method(self, x):
    self.has_method_ = 1
    self.method_ = x

  def clear_method(self):
    if self.has_method_:
      self.has_method_ = 0
      self.method_ = 2

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
    x = TaskQueueAddRequest_Header()
    self.header_.append(x)
    return x

  def clear_header(self):
    self.header_ = []
  def body(self): return self.body_

  def set_body(self, x):
    self.has_body_ = 1
    self.body_ = x

  def clear_body(self):
    if self.has_body_:
      self.has_body_ = 0
      self.body_ = ""

  def has_body(self): return self.has_body_

  def transaction(self):
    if self.transaction_ is None:
      self.lazy_init_lock_.acquire()
      try:
        if self.transaction_ is None: self.transaction_ = Transaction()
      finally:
        self.lazy_init_lock_.release()
    return self.transaction_

  def mutable_transaction(self): self.has_transaction_ = 1; return self.transaction()

  def clear_transaction(self):
    if self.has_transaction_:
      self.has_transaction_ = 0;
      if self.transaction_ is not None: self.transaction_.Clear()

  def has_transaction(self): return self.has_transaction_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_queue_name()): self.set_queue_name(x.queue_name())
    if (x.has_task_name()): self.set_task_name(x.task_name())
    if (x.has_eta_usec()): self.set_eta_usec(x.eta_usec())
    if (x.has_method()): self.set_method(x.method())
    if (x.has_url()): self.set_url(x.url())
    for i in xrange(x.header_size()): self.add_header().CopyFrom(x.header(i))
    if (x.has_body()): self.set_body(x.body())
    if (x.has_transaction()): self.mutable_transaction().MergeFrom(x.transaction())

  def Equals(self, x):
    if x is self: return 1
    if self.has_queue_name_ != x.has_queue_name_: return 0
    if self.has_queue_name_ and self.queue_name_ != x.queue_name_: return 0
    if self.has_task_name_ != x.has_task_name_: return 0
    if self.has_task_name_ and self.task_name_ != x.task_name_: return 0
    if self.has_eta_usec_ != x.has_eta_usec_: return 0
    if self.has_eta_usec_ and self.eta_usec_ != x.eta_usec_: return 0
    if self.has_method_ != x.has_method_: return 0
    if self.has_method_ and self.method_ != x.method_: return 0
    if self.has_url_ != x.has_url_: return 0
    if self.has_url_ and self.url_ != x.url_: return 0
    if len(self.header_) != len(x.header_): return 0
    for e1, e2 in zip(self.header_, x.header_):
      if e1 != e2: return 0
    if self.has_body_ != x.has_body_: return 0
    if self.has_body_ and self.body_ != x.body_: return 0
    if self.has_transaction_ != x.has_transaction_: return 0
    if self.has_transaction_ and self.transaction_ != x.transaction_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_queue_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: queue_name not set.')
    if (not self.has_task_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: task_name not set.')
    if (not self.has_eta_usec_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: eta_usec not set.')
    if (not self.has_url_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: url not set.')
    for p in self.header_:
      if not p.IsInitialized(debug_strs): initialized=0
    if (self.has_transaction_ and not self.transaction_.IsInitialized(debug_strs)): initialized = 0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.queue_name_))
    n += self.lengthString(len(self.task_name_))
    n += self.lengthVarInt64(self.eta_usec_)
    if (self.has_method_): n += 1 + self.lengthVarInt64(self.method_)
    n += self.lengthString(len(self.url_))
    n += 2 * len(self.header_)
    for i in xrange(len(self.header_)): n += self.header_[i].ByteSize()
    if (self.has_body_): n += 1 + self.lengthString(len(self.body_))
    if (self.has_transaction_): n += 1 + self.lengthString(self.transaction_.ByteSize())
    return n + 4

  def Clear(self):
    self.clear_queue_name()
    self.clear_task_name()
    self.clear_eta_usec()
    self.clear_method()
    self.clear_url()
    self.clear_header()
    self.clear_body()
    self.clear_transaction()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.queue_name_)
    out.putVarInt32(18)
    out.putPrefixedString(self.task_name_)
    out.putVarInt32(24)
    out.putVarInt64(self.eta_usec_)
    out.putVarInt32(34)
    out.putPrefixedString(self.url_)
    if (self.has_method_):
      out.putVarInt32(40)
      out.putVarInt32(self.method_)
    for i in xrange(len(self.header_)):
      out.putVarInt32(51)
      self.header_[i].OutputUnchecked(out)
      out.putVarInt32(52)
    if (self.has_body_):
      out.putVarInt32(74)
      out.putPrefixedString(self.body_)
    if (self.has_transaction_):
      out.putVarInt32(82)
      out.putVarInt32(self.transaction_.ByteSize())
      self.transaction_.OutputUnchecked(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_queue_name(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_task_name(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_eta_usec(d.getVarInt64())
        continue
      if tt == 34:
        self.set_url(d.getPrefixedString())
        continue
      if tt == 40:
        self.set_method(d.getVarInt32())
        continue
      if tt == 51:
        self.add_header().TryMerge(d)
        continue
      if tt == 74:
        self.set_body(d.getPrefixedString())
        continue
      if tt == 82:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_transaction().TryMerge(tmp)
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_queue_name_: res+=prefix+("queue_name: %s\n" % self.DebugFormatString(self.queue_name_))
    if self.has_task_name_: res+=prefix+("task_name: %s\n" % self.DebugFormatString(self.task_name_))
    if self.has_eta_usec_: res+=prefix+("eta_usec: %s\n" % self.DebugFormatInt64(self.eta_usec_))
    if self.has_method_: res+=prefix+("method: %s\n" % self.DebugFormatInt32(self.method_))
    if self.has_url_: res+=prefix+("url: %s\n" % self.DebugFormatString(self.url_))
    cnt=0
    for e in self.header_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("Header%s {\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+"}\n"
      cnt+=1
    if self.has_body_: res+=prefix+("body: %s\n" % self.DebugFormatString(self.body_))
    if self.has_transaction_:
      res+=prefix+"transaction <\n"
      res+=self.transaction_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kqueue_name = 1
  ktask_name = 2
  keta_usec = 3
  kmethod = 5
  kurl = 4
  kHeaderGroup = 6
  kHeaderkey = 7
  kHeadervalue = 8
  kbody = 9
  ktransaction = 10

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "queue_name",
    2: "task_name",
    3: "eta_usec",
    4: "url",
    5: "method",
    6: "Header",
    7: "key",
    8: "value",
    9: "body",
    10: "transaction",
  }, 10)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
    4: ProtocolBuffer.Encoder.STRING,
    5: ProtocolBuffer.Encoder.NUMERIC,
    6: ProtocolBuffer.Encoder.STARTGROUP,
    7: ProtocolBuffer.Encoder.STRING,
    8: ProtocolBuffer.Encoder.STRING,
    9: ProtocolBuffer.Encoder.STRING,
    10: ProtocolBuffer.Encoder.STRING,
  }, 10, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueAddResponse(ProtocolBuffer.ProtocolMessage):
  has_chosen_task_name_ = 0
  chosen_task_name_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def chosen_task_name(self): return self.chosen_task_name_

  def set_chosen_task_name(self, x):
    self.has_chosen_task_name_ = 1
    self.chosen_task_name_ = x

  def clear_chosen_task_name(self):
    if self.has_chosen_task_name_:
      self.has_chosen_task_name_ = 0
      self.chosen_task_name_ = ""

  def has_chosen_task_name(self): return self.has_chosen_task_name_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_chosen_task_name()): self.set_chosen_task_name(x.chosen_task_name())

  def Equals(self, x):
    if x is self: return 1
    if self.has_chosen_task_name_ != x.has_chosen_task_name_: return 0
    if self.has_chosen_task_name_ and self.chosen_task_name_ != x.chosen_task_name_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_chosen_task_name_): n += 1 + self.lengthString(len(self.chosen_task_name_))
    return n + 0

  def Clear(self):
    self.clear_chosen_task_name()

  def OutputUnchecked(self, out):
    if (self.has_chosen_task_name_):
      out.putVarInt32(10)
      out.putPrefixedString(self.chosen_task_name_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_chosen_task_name(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_chosen_task_name_: res+=prefix+("chosen_task_name: %s\n" % self.DebugFormatString(self.chosen_task_name_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kchosen_task_name = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "chosen_task_name",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueDeleteRequest(ProtocolBuffer.ProtocolMessage):
  has_queue_name_ = 0
  queue_name_ = ""
  has_app_id_ = 0
  app_id_ = ""

  def __init__(self, contents=None):
    self.task_name_ = []
    if contents is not None: self.MergeFromString(contents)

  def queue_name(self): return self.queue_name_

  def set_queue_name(self, x):
    self.has_queue_name_ = 1
    self.queue_name_ = x

  def clear_queue_name(self):
    if self.has_queue_name_:
      self.has_queue_name_ = 0
      self.queue_name_ = ""

  def has_queue_name(self): return self.has_queue_name_

  def task_name_size(self): return len(self.task_name_)
  def task_name_list(self): return self.task_name_

  def task_name(self, i):
    return self.task_name_[i]

  def set_task_name(self, i, x):
    self.task_name_[i] = x

  def add_task_name(self, x):
    self.task_name_.append(x)

  def clear_task_name(self):
    self.task_name_ = []

  def app_id(self): return self.app_id_

  def set_app_id(self, x):
    self.has_app_id_ = 1
    self.app_id_ = x

  def clear_app_id(self):
    if self.has_app_id_:
      self.has_app_id_ = 0
      self.app_id_ = ""

  def has_app_id(self): return self.has_app_id_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_queue_name()): self.set_queue_name(x.queue_name())
    for i in xrange(x.task_name_size()): self.add_task_name(x.task_name(i))
    if (x.has_app_id()): self.set_app_id(x.app_id())

  def Equals(self, x):
    if x is self: return 1
    if self.has_queue_name_ != x.has_queue_name_: return 0
    if self.has_queue_name_ and self.queue_name_ != x.queue_name_: return 0
    if len(self.task_name_) != len(x.task_name_): return 0
    for e1, e2 in zip(self.task_name_, x.task_name_):
      if e1 != e2: return 0
    if self.has_app_id_ != x.has_app_id_: return 0
    if self.has_app_id_ and self.app_id_ != x.app_id_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_queue_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: queue_name not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.queue_name_))
    n += 1 * len(self.task_name_)
    for i in xrange(len(self.task_name_)): n += self.lengthString(len(self.task_name_[i]))
    if (self.has_app_id_): n += 1 + self.lengthString(len(self.app_id_))
    return n + 1

  def Clear(self):
    self.clear_queue_name()
    self.clear_task_name()
    self.clear_app_id()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.queue_name_)
    for i in xrange(len(self.task_name_)):
      out.putVarInt32(18)
      out.putPrefixedString(self.task_name_[i])
    if (self.has_app_id_):
      out.putVarInt32(26)
      out.putPrefixedString(self.app_id_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_queue_name(d.getPrefixedString())
        continue
      if tt == 18:
        self.add_task_name(d.getPrefixedString())
        continue
      if tt == 26:
        self.set_app_id(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_queue_name_: res+=prefix+("queue_name: %s\n" % self.DebugFormatString(self.queue_name_))
    cnt=0
    for e in self.task_name_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("task_name%s: %s\n" % (elm, self.DebugFormatString(e)))
      cnt+=1
    if self.has_app_id_: res+=prefix+("app_id: %s\n" % self.DebugFormatString(self.app_id_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kqueue_name = 1
  ktask_name = 2
  kapp_id = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "queue_name",
    2: "task_name",
    3: "app_id",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueDeleteResponse(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.result_ = []
    if contents is not None: self.MergeFromString(contents)

  def result_size(self): return len(self.result_)
  def result_list(self): return self.result_

  def result(self, i):
    return self.result_[i]

  def set_result(self, i, x):
    self.result_[i] = x

  def add_result(self, x):
    self.result_.append(x)

  def clear_result(self):
    self.result_ = []


  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.result_size()): self.add_result(x.result(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.result_) != len(x.result_): return 0
    for e1, e2 in zip(self.result_, x.result_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    n += 1 * len(self.result_)
    for i in xrange(len(self.result_)): n += self.lengthVarInt64(self.result_[i])
    return n + 0

  def Clear(self):
    self.clear_result()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.result_)):
      out.putVarInt32(24)
      out.putVarInt32(self.result_[i])

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 24:
        self.add_result(d.getVarInt32())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.result_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("result%s: %s\n" % (elm, self.DebugFormatInt32(e)))
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kresult = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    3: "result",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.NUMERIC,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueUpdateQueueRequest(ProtocolBuffer.ProtocolMessage):
  has_app_id_ = 0
  app_id_ = ""
  has_queue_name_ = 0
  queue_name_ = ""
  has_bucket_refill_per_second_ = 0
  bucket_refill_per_second_ = 0.0
  has_bucket_capacity_ = 0
  bucket_capacity_ = 0
  has_user_specified_rate_ = 0
  user_specified_rate_ = ""

  def __init__(self, contents=None):
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

  def queue_name(self): return self.queue_name_

  def set_queue_name(self, x):
    self.has_queue_name_ = 1
    self.queue_name_ = x

  def clear_queue_name(self):
    if self.has_queue_name_:
      self.has_queue_name_ = 0
      self.queue_name_ = ""

  def has_queue_name(self): return self.has_queue_name_

  def bucket_refill_per_second(self): return self.bucket_refill_per_second_

  def set_bucket_refill_per_second(self, x):
    self.has_bucket_refill_per_second_ = 1
    self.bucket_refill_per_second_ = x

  def clear_bucket_refill_per_second(self):
    if self.has_bucket_refill_per_second_:
      self.has_bucket_refill_per_second_ = 0
      self.bucket_refill_per_second_ = 0.0

  def has_bucket_refill_per_second(self): return self.has_bucket_refill_per_second_

  def bucket_capacity(self): return self.bucket_capacity_

  def set_bucket_capacity(self, x):
    self.has_bucket_capacity_ = 1
    self.bucket_capacity_ = x

  def clear_bucket_capacity(self):
    if self.has_bucket_capacity_:
      self.has_bucket_capacity_ = 0
      self.bucket_capacity_ = 0

  def has_bucket_capacity(self): return self.has_bucket_capacity_

  def user_specified_rate(self): return self.user_specified_rate_

  def set_user_specified_rate(self, x):
    self.has_user_specified_rate_ = 1
    self.user_specified_rate_ = x

  def clear_user_specified_rate(self):
    if self.has_user_specified_rate_:
      self.has_user_specified_rate_ = 0
      self.user_specified_rate_ = ""

  def has_user_specified_rate(self): return self.has_user_specified_rate_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_app_id()): self.set_app_id(x.app_id())
    if (x.has_queue_name()): self.set_queue_name(x.queue_name())
    if (x.has_bucket_refill_per_second()): self.set_bucket_refill_per_second(x.bucket_refill_per_second())
    if (x.has_bucket_capacity()): self.set_bucket_capacity(x.bucket_capacity())
    if (x.has_user_specified_rate()): self.set_user_specified_rate(x.user_specified_rate())

  def Equals(self, x):
    if x is self: return 1
    if self.has_app_id_ != x.has_app_id_: return 0
    if self.has_app_id_ and self.app_id_ != x.app_id_: return 0
    if self.has_queue_name_ != x.has_queue_name_: return 0
    if self.has_queue_name_ and self.queue_name_ != x.queue_name_: return 0
    if self.has_bucket_refill_per_second_ != x.has_bucket_refill_per_second_: return 0
    if self.has_bucket_refill_per_second_ and self.bucket_refill_per_second_ != x.bucket_refill_per_second_: return 0
    if self.has_bucket_capacity_ != x.has_bucket_capacity_: return 0
    if self.has_bucket_capacity_ and self.bucket_capacity_ != x.bucket_capacity_: return 0
    if self.has_user_specified_rate_ != x.has_user_specified_rate_: return 0
    if self.has_user_specified_rate_ and self.user_specified_rate_ != x.user_specified_rate_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_app_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: app_id not set.')
    if (not self.has_queue_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: queue_name not set.')
    if (not self.has_bucket_refill_per_second_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: bucket_refill_per_second not set.')
    if (not self.has_bucket_capacity_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: bucket_capacity not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.app_id_))
    n += self.lengthString(len(self.queue_name_))
    n += self.lengthVarInt64(self.bucket_capacity_)
    if (self.has_user_specified_rate_): n += 1 + self.lengthString(len(self.user_specified_rate_))
    return n + 12

  def Clear(self):
    self.clear_app_id()
    self.clear_queue_name()
    self.clear_bucket_refill_per_second()
    self.clear_bucket_capacity()
    self.clear_user_specified_rate()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.app_id_)
    out.putVarInt32(18)
    out.putPrefixedString(self.queue_name_)
    out.putVarInt32(25)
    out.putDouble(self.bucket_refill_per_second_)
    out.putVarInt32(32)
    out.putVarInt32(self.bucket_capacity_)
    if (self.has_user_specified_rate_):
      out.putVarInt32(42)
      out.putPrefixedString(self.user_specified_rate_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_app_id(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_queue_name(d.getPrefixedString())
        continue
      if tt == 25:
        self.set_bucket_refill_per_second(d.getDouble())
        continue
      if tt == 32:
        self.set_bucket_capacity(d.getVarInt32())
        continue
      if tt == 42:
        self.set_user_specified_rate(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_app_id_: res+=prefix+("app_id: %s\n" % self.DebugFormatString(self.app_id_))
    if self.has_queue_name_: res+=prefix+("queue_name: %s\n" % self.DebugFormatString(self.queue_name_))
    if self.has_bucket_refill_per_second_: res+=prefix+("bucket_refill_per_second: %s\n" % self.DebugFormat(self.bucket_refill_per_second_))
    if self.has_bucket_capacity_: res+=prefix+("bucket_capacity: %s\n" % self.DebugFormatInt32(self.bucket_capacity_))
    if self.has_user_specified_rate_: res+=prefix+("user_specified_rate: %s\n" % self.DebugFormatString(self.user_specified_rate_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kapp_id = 1
  kqueue_name = 2
  kbucket_refill_per_second = 3
  kbucket_capacity = 4
  kuser_specified_rate = 5

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "app_id",
    2: "queue_name",
    3: "bucket_refill_per_second",
    4: "bucket_capacity",
    5: "user_specified_rate",
  }, 5)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.DOUBLE,
    4: ProtocolBuffer.Encoder.NUMERIC,
    5: ProtocolBuffer.Encoder.STRING,
  }, 5, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueUpdateQueueResponse(ProtocolBuffer.ProtocolMessage):

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


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])


  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
  }, 0)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
  }, 0, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueFetchQueuesRequest(ProtocolBuffer.ProtocolMessage):
  has_app_id_ = 0
  app_id_ = ""
  has_max_rows_ = 0
  max_rows_ = 0

  def __init__(self, contents=None):
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

  def max_rows(self): return self.max_rows_

  def set_max_rows(self, x):
    self.has_max_rows_ = 1
    self.max_rows_ = x

  def clear_max_rows(self):
    if self.has_max_rows_:
      self.has_max_rows_ = 0
      self.max_rows_ = 0

  def has_max_rows(self): return self.has_max_rows_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_app_id()): self.set_app_id(x.app_id())
    if (x.has_max_rows()): self.set_max_rows(x.max_rows())

  def Equals(self, x):
    if x is self: return 1
    if self.has_app_id_ != x.has_app_id_: return 0
    if self.has_app_id_ and self.app_id_ != x.app_id_: return 0
    if self.has_max_rows_ != x.has_max_rows_: return 0
    if self.has_max_rows_ and self.max_rows_ != x.max_rows_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_app_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: app_id not set.')
    if (not self.has_max_rows_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: max_rows not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.app_id_))
    n += self.lengthVarInt64(self.max_rows_)
    return n + 2

  def Clear(self):
    self.clear_app_id()
    self.clear_max_rows()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.app_id_)
    out.putVarInt32(16)
    out.putVarInt32(self.max_rows_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_app_id(d.getPrefixedString())
        continue
      if tt == 16:
        self.set_max_rows(d.getVarInt32())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_app_id_: res+=prefix+("app_id: %s\n" % self.DebugFormatString(self.app_id_))
    if self.has_max_rows_: res+=prefix+("max_rows: %s\n" % self.DebugFormatInt32(self.max_rows_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kapp_id = 1
  kmax_rows = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "app_id",
    2: "max_rows",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.NUMERIC,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueFetchQueuesResponse_Queue(ProtocolBuffer.ProtocolMessage):
  has_queue_name_ = 0
  queue_name_ = ""
  has_bucket_refill_per_second_ = 0
  bucket_refill_per_second_ = 0.0
  has_bucket_capacity_ = 0
  bucket_capacity_ = 0.0
  has_user_specified_rate_ = 0
  user_specified_rate_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def queue_name(self): return self.queue_name_

  def set_queue_name(self, x):
    self.has_queue_name_ = 1
    self.queue_name_ = x

  def clear_queue_name(self):
    if self.has_queue_name_:
      self.has_queue_name_ = 0
      self.queue_name_ = ""

  def has_queue_name(self): return self.has_queue_name_

  def bucket_refill_per_second(self): return self.bucket_refill_per_second_

  def set_bucket_refill_per_second(self, x):
    self.has_bucket_refill_per_second_ = 1
    self.bucket_refill_per_second_ = x

  def clear_bucket_refill_per_second(self):
    if self.has_bucket_refill_per_second_:
      self.has_bucket_refill_per_second_ = 0
      self.bucket_refill_per_second_ = 0.0

  def has_bucket_refill_per_second(self): return self.has_bucket_refill_per_second_

  def bucket_capacity(self): return self.bucket_capacity_

  def set_bucket_capacity(self, x):
    self.has_bucket_capacity_ = 1
    self.bucket_capacity_ = x

  def clear_bucket_capacity(self):
    if self.has_bucket_capacity_:
      self.has_bucket_capacity_ = 0
      self.bucket_capacity_ = 0.0

  def has_bucket_capacity(self): return self.has_bucket_capacity_

  def user_specified_rate(self): return self.user_specified_rate_

  def set_user_specified_rate(self, x):
    self.has_user_specified_rate_ = 1
    self.user_specified_rate_ = x

  def clear_user_specified_rate(self):
    if self.has_user_specified_rate_:
      self.has_user_specified_rate_ = 0
      self.user_specified_rate_ = ""

  def has_user_specified_rate(self): return self.has_user_specified_rate_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_queue_name()): self.set_queue_name(x.queue_name())
    if (x.has_bucket_refill_per_second()): self.set_bucket_refill_per_second(x.bucket_refill_per_second())
    if (x.has_bucket_capacity()): self.set_bucket_capacity(x.bucket_capacity())
    if (x.has_user_specified_rate()): self.set_user_specified_rate(x.user_specified_rate())

  def Equals(self, x):
    if x is self: return 1
    if self.has_queue_name_ != x.has_queue_name_: return 0
    if self.has_queue_name_ and self.queue_name_ != x.queue_name_: return 0
    if self.has_bucket_refill_per_second_ != x.has_bucket_refill_per_second_: return 0
    if self.has_bucket_refill_per_second_ and self.bucket_refill_per_second_ != x.bucket_refill_per_second_: return 0
    if self.has_bucket_capacity_ != x.has_bucket_capacity_: return 0
    if self.has_bucket_capacity_ and self.bucket_capacity_ != x.bucket_capacity_: return 0
    if self.has_user_specified_rate_ != x.has_user_specified_rate_: return 0
    if self.has_user_specified_rate_ and self.user_specified_rate_ != x.user_specified_rate_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_queue_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: queue_name not set.')
    if (not self.has_bucket_refill_per_second_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: bucket_refill_per_second not set.')
    if (not self.has_bucket_capacity_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: bucket_capacity not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.queue_name_))
    if (self.has_user_specified_rate_): n += 1 + self.lengthString(len(self.user_specified_rate_))
    return n + 19

  def Clear(self):
    self.clear_queue_name()
    self.clear_bucket_refill_per_second()
    self.clear_bucket_capacity()
    self.clear_user_specified_rate()

  def OutputUnchecked(self, out):
    out.putVarInt32(18)
    out.putPrefixedString(self.queue_name_)
    out.putVarInt32(25)
    out.putDouble(self.bucket_refill_per_second_)
    out.putVarInt32(33)
    out.putDouble(self.bucket_capacity_)
    if (self.has_user_specified_rate_):
      out.putVarInt32(42)
      out.putPrefixedString(self.user_specified_rate_)

  def TryMerge(self, d):
    while 1:
      tt = d.getVarInt32()
      if tt == 12: break
      if tt == 18:
        self.set_queue_name(d.getPrefixedString())
        continue
      if tt == 25:
        self.set_bucket_refill_per_second(d.getDouble())
        continue
      if tt == 33:
        self.set_bucket_capacity(d.getDouble())
        continue
      if tt == 42:
        self.set_user_specified_rate(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_queue_name_: res+=prefix+("queue_name: %s\n" % self.DebugFormatString(self.queue_name_))
    if self.has_bucket_refill_per_second_: res+=prefix+("bucket_refill_per_second: %s\n" % self.DebugFormat(self.bucket_refill_per_second_))
    if self.has_bucket_capacity_: res+=prefix+("bucket_capacity: %s\n" % self.DebugFormat(self.bucket_capacity_))
    if self.has_user_specified_rate_: res+=prefix+("user_specified_rate: %s\n" % self.DebugFormatString(self.user_specified_rate_))
    return res

class TaskQueueFetchQueuesResponse(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.queue_ = []
    if contents is not None: self.MergeFromString(contents)

  def queue_size(self): return len(self.queue_)
  def queue_list(self): return self.queue_

  def queue(self, i):
    return self.queue_[i]

  def mutable_queue(self, i):
    return self.queue_[i]

  def add_queue(self):
    x = TaskQueueFetchQueuesResponse_Queue()
    self.queue_.append(x)
    return x

  def clear_queue(self):
    self.queue_ = []

  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.queue_size()): self.add_queue().CopyFrom(x.queue(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.queue_) != len(x.queue_): return 0
    for e1, e2 in zip(self.queue_, x.queue_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.queue_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += 2 * len(self.queue_)
    for i in xrange(len(self.queue_)): n += self.queue_[i].ByteSize()
    return n + 0

  def Clear(self):
    self.clear_queue()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.queue_)):
      out.putVarInt32(11)
      self.queue_[i].OutputUnchecked(out)
      out.putVarInt32(12)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 11:
        self.add_queue().TryMerge(d)
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.queue_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("Queue%s {\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+"}\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kQueueGroup = 1
  kQueuequeue_name = 2
  kQueuebucket_refill_per_second = 3
  kQueuebucket_capacity = 4
  kQueueuser_specified_rate = 5

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "Queue",
    2: "queue_name",
    3: "bucket_refill_per_second",
    4: "bucket_capacity",
    5: "user_specified_rate",
  }, 5)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STARTGROUP,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.DOUBLE,
    4: ProtocolBuffer.Encoder.DOUBLE,
    5: ProtocolBuffer.Encoder.STRING,
  }, 5, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueFetchQueueStatsRequest(ProtocolBuffer.ProtocolMessage):
  has_app_id_ = 0
  app_id_ = ""
  has_max_num_tasks_ = 0
  max_num_tasks_ = 0

  def __init__(self, contents=None):
    self.queue_name_ = []
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

  def queue_name_size(self): return len(self.queue_name_)
  def queue_name_list(self): return self.queue_name_

  def queue_name(self, i):
    return self.queue_name_[i]

  def set_queue_name(self, i, x):
    self.queue_name_[i] = x

  def add_queue_name(self, x):
    self.queue_name_.append(x)

  def clear_queue_name(self):
    self.queue_name_ = []

  def max_num_tasks(self): return self.max_num_tasks_

  def set_max_num_tasks(self, x):
    self.has_max_num_tasks_ = 1
    self.max_num_tasks_ = x

  def clear_max_num_tasks(self):
    if self.has_max_num_tasks_:
      self.has_max_num_tasks_ = 0
      self.max_num_tasks_ = 0

  def has_max_num_tasks(self): return self.has_max_num_tasks_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_app_id()): self.set_app_id(x.app_id())
    for i in xrange(x.queue_name_size()): self.add_queue_name(x.queue_name(i))
    if (x.has_max_num_tasks()): self.set_max_num_tasks(x.max_num_tasks())

  def Equals(self, x):
    if x is self: return 1
    if self.has_app_id_ != x.has_app_id_: return 0
    if self.has_app_id_ and self.app_id_ != x.app_id_: return 0
    if len(self.queue_name_) != len(x.queue_name_): return 0
    for e1, e2 in zip(self.queue_name_, x.queue_name_):
      if e1 != e2: return 0
    if self.has_max_num_tasks_ != x.has_max_num_tasks_: return 0
    if self.has_max_num_tasks_ and self.max_num_tasks_ != x.max_num_tasks_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_app_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: app_id not set.')
    if (not self.has_max_num_tasks_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: max_num_tasks not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.app_id_))
    n += 1 * len(self.queue_name_)
    for i in xrange(len(self.queue_name_)): n += self.lengthString(len(self.queue_name_[i]))
    n += self.lengthVarInt64(self.max_num_tasks_)
    return n + 2

  def Clear(self):
    self.clear_app_id()
    self.clear_queue_name()
    self.clear_max_num_tasks()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.app_id_)
    for i in xrange(len(self.queue_name_)):
      out.putVarInt32(18)
      out.putPrefixedString(self.queue_name_[i])
    out.putVarInt32(24)
    out.putVarInt32(self.max_num_tasks_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_app_id(d.getPrefixedString())
        continue
      if tt == 18:
        self.add_queue_name(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_max_num_tasks(d.getVarInt32())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_app_id_: res+=prefix+("app_id: %s\n" % self.DebugFormatString(self.app_id_))
    cnt=0
    for e in self.queue_name_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("queue_name%s: %s\n" % (elm, self.DebugFormatString(e)))
      cnt+=1
    if self.has_max_num_tasks_: res+=prefix+("max_num_tasks: %s\n" % self.DebugFormatInt32(self.max_num_tasks_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kapp_id = 1
  kqueue_name = 2
  kmax_num_tasks = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "app_id",
    2: "queue_name",
    3: "max_num_tasks",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueScannerQueueInfo(ProtocolBuffer.ProtocolMessage):
  has_executed_last_minute_ = 0
  executed_last_minute_ = 0
  has_executed_last_hour_ = 0
  executed_last_hour_ = 0
  has_sampling_duration_seconds_ = 0
  sampling_duration_seconds_ = 0.0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def executed_last_minute(self): return self.executed_last_minute_

  def set_executed_last_minute(self, x):
    self.has_executed_last_minute_ = 1
    self.executed_last_minute_ = x

  def clear_executed_last_minute(self):
    if self.has_executed_last_minute_:
      self.has_executed_last_minute_ = 0
      self.executed_last_minute_ = 0

  def has_executed_last_minute(self): return self.has_executed_last_minute_

  def executed_last_hour(self): return self.executed_last_hour_

  def set_executed_last_hour(self, x):
    self.has_executed_last_hour_ = 1
    self.executed_last_hour_ = x

  def clear_executed_last_hour(self):
    if self.has_executed_last_hour_:
      self.has_executed_last_hour_ = 0
      self.executed_last_hour_ = 0

  def has_executed_last_hour(self): return self.has_executed_last_hour_

  def sampling_duration_seconds(self): return self.sampling_duration_seconds_

  def set_sampling_duration_seconds(self, x):
    self.has_sampling_duration_seconds_ = 1
    self.sampling_duration_seconds_ = x

  def clear_sampling_duration_seconds(self):
    if self.has_sampling_duration_seconds_:
      self.has_sampling_duration_seconds_ = 0
      self.sampling_duration_seconds_ = 0.0

  def has_sampling_duration_seconds(self): return self.has_sampling_duration_seconds_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_executed_last_minute()): self.set_executed_last_minute(x.executed_last_minute())
    if (x.has_executed_last_hour()): self.set_executed_last_hour(x.executed_last_hour())
    if (x.has_sampling_duration_seconds()): self.set_sampling_duration_seconds(x.sampling_duration_seconds())

  def Equals(self, x):
    if x is self: return 1
    if self.has_executed_last_minute_ != x.has_executed_last_minute_: return 0
    if self.has_executed_last_minute_ and self.executed_last_minute_ != x.executed_last_minute_: return 0
    if self.has_executed_last_hour_ != x.has_executed_last_hour_: return 0
    if self.has_executed_last_hour_ and self.executed_last_hour_ != x.executed_last_hour_: return 0
    if self.has_sampling_duration_seconds_ != x.has_sampling_duration_seconds_: return 0
    if self.has_sampling_duration_seconds_ and self.sampling_duration_seconds_ != x.sampling_duration_seconds_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_executed_last_minute_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: executed_last_minute not set.')
    if (not self.has_executed_last_hour_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: executed_last_hour not set.')
    if (not self.has_sampling_duration_seconds_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: sampling_duration_seconds not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.executed_last_minute_)
    n += self.lengthVarInt64(self.executed_last_hour_)
    return n + 11

  def Clear(self):
    self.clear_executed_last_minute()
    self.clear_executed_last_hour()
    self.clear_sampling_duration_seconds()

  def OutputUnchecked(self, out):
    out.putVarInt32(8)
    out.putVarInt64(self.executed_last_minute_)
    out.putVarInt32(16)
    out.putVarInt64(self.executed_last_hour_)
    out.putVarInt32(25)
    out.putDouble(self.sampling_duration_seconds_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_executed_last_minute(d.getVarInt64())
        continue
      if tt == 16:
        self.set_executed_last_hour(d.getVarInt64())
        continue
      if tt == 25:
        self.set_sampling_duration_seconds(d.getDouble())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_executed_last_minute_: res+=prefix+("executed_last_minute: %s\n" % self.DebugFormatInt64(self.executed_last_minute_))
    if self.has_executed_last_hour_: res+=prefix+("executed_last_hour: %s\n" % self.DebugFormatInt64(self.executed_last_hour_))
    if self.has_sampling_duration_seconds_: res+=prefix+("sampling_duration_seconds: %s\n" % self.DebugFormat(self.sampling_duration_seconds_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kexecuted_last_minute = 1
  kexecuted_last_hour = 2
  ksampling_duration_seconds = 3

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "executed_last_minute",
    2: "executed_last_hour",
    3: "sampling_duration_seconds",
  }, 3)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.NUMERIC,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.DOUBLE,
  }, 3, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueFetchQueueStatsResponse_QueueStats(ProtocolBuffer.ProtocolMessage):
  has_num_tasks_ = 0
  num_tasks_ = 0
  has_oldest_eta_usec_ = 0
  oldest_eta_usec_ = 0
  has_scanner_info_ = 0
  scanner_info_ = None

  def __init__(self, contents=None):
    self.lazy_init_lock_ = thread.allocate_lock()
    if contents is not None: self.MergeFromString(contents)

  def num_tasks(self): return self.num_tasks_

  def set_num_tasks(self, x):
    self.has_num_tasks_ = 1
    self.num_tasks_ = x

  def clear_num_tasks(self):
    if self.has_num_tasks_:
      self.has_num_tasks_ = 0
      self.num_tasks_ = 0

  def has_num_tasks(self): return self.has_num_tasks_

  def oldest_eta_usec(self): return self.oldest_eta_usec_

  def set_oldest_eta_usec(self, x):
    self.has_oldest_eta_usec_ = 1
    self.oldest_eta_usec_ = x

  def clear_oldest_eta_usec(self):
    if self.has_oldest_eta_usec_:
      self.has_oldest_eta_usec_ = 0
      self.oldest_eta_usec_ = 0

  def has_oldest_eta_usec(self): return self.has_oldest_eta_usec_

  def scanner_info(self):
    if self.scanner_info_ is None:
      self.lazy_init_lock_.acquire()
      try:
        if self.scanner_info_ is None: self.scanner_info_ = TaskQueueScannerQueueInfo()
      finally:
        self.lazy_init_lock_.release()
    return self.scanner_info_

  def mutable_scanner_info(self): self.has_scanner_info_ = 1; return self.scanner_info()

  def clear_scanner_info(self):
    if self.has_scanner_info_:
      self.has_scanner_info_ = 0;
      if self.scanner_info_ is not None: self.scanner_info_.Clear()

  def has_scanner_info(self): return self.has_scanner_info_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_num_tasks()): self.set_num_tasks(x.num_tasks())
    if (x.has_oldest_eta_usec()): self.set_oldest_eta_usec(x.oldest_eta_usec())
    if (x.has_scanner_info()): self.mutable_scanner_info().MergeFrom(x.scanner_info())

  def Equals(self, x):
    if x is self: return 1
    if self.has_num_tasks_ != x.has_num_tasks_: return 0
    if self.has_num_tasks_ and self.num_tasks_ != x.num_tasks_: return 0
    if self.has_oldest_eta_usec_ != x.has_oldest_eta_usec_: return 0
    if self.has_oldest_eta_usec_ and self.oldest_eta_usec_ != x.oldest_eta_usec_: return 0
    if self.has_scanner_info_ != x.has_scanner_info_: return 0
    if self.has_scanner_info_ and self.scanner_info_ != x.scanner_info_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_num_tasks_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: num_tasks not set.')
    if (not self.has_oldest_eta_usec_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: oldest_eta_usec not set.')
    if (self.has_scanner_info_ and not self.scanner_info_.IsInitialized(debug_strs)): initialized = 0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthVarInt64(self.num_tasks_)
    n += self.lengthVarInt64(self.oldest_eta_usec_)
    if (self.has_scanner_info_): n += 1 + self.lengthString(self.scanner_info_.ByteSize())
    return n + 2

  def Clear(self):
    self.clear_num_tasks()
    self.clear_oldest_eta_usec()
    self.clear_scanner_info()

  def OutputUnchecked(self, out):
    out.putVarInt32(16)
    out.putVarInt32(self.num_tasks_)
    out.putVarInt32(24)
    out.putVarInt64(self.oldest_eta_usec_)
    if (self.has_scanner_info_):
      out.putVarInt32(34)
      out.putVarInt32(self.scanner_info_.ByteSize())
      self.scanner_info_.OutputUnchecked(out)

  def TryMerge(self, d):
    while 1:
      tt = d.getVarInt32()
      if tt == 12: break
      if tt == 16:
        self.set_num_tasks(d.getVarInt32())
        continue
      if tt == 24:
        self.set_oldest_eta_usec(d.getVarInt64())
        continue
      if tt == 34:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_scanner_info().TryMerge(tmp)
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_num_tasks_: res+=prefix+("num_tasks: %s\n" % self.DebugFormatInt32(self.num_tasks_))
    if self.has_oldest_eta_usec_: res+=prefix+("oldest_eta_usec: %s\n" % self.DebugFormatInt64(self.oldest_eta_usec_))
    if self.has_scanner_info_:
      res+=prefix+"scanner_info <\n"
      res+=self.scanner_info_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    return res

class TaskQueueFetchQueueStatsResponse(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.queuestats_ = []
    if contents is not None: self.MergeFromString(contents)

  def queuestats_size(self): return len(self.queuestats_)
  def queuestats_list(self): return self.queuestats_

  def queuestats(self, i):
    return self.queuestats_[i]

  def mutable_queuestats(self, i):
    return self.queuestats_[i]

  def add_queuestats(self):
    x = TaskQueueFetchQueueStatsResponse_QueueStats()
    self.queuestats_.append(x)
    return x

  def clear_queuestats(self):
    self.queuestats_ = []

  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.queuestats_size()): self.add_queuestats().CopyFrom(x.queuestats(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.queuestats_) != len(x.queuestats_): return 0
    for e1, e2 in zip(self.queuestats_, x.queuestats_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.queuestats_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += 2 * len(self.queuestats_)
    for i in xrange(len(self.queuestats_)): n += self.queuestats_[i].ByteSize()
    return n + 0

  def Clear(self):
    self.clear_queuestats()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.queuestats_)):
      out.putVarInt32(11)
      self.queuestats_[i].OutputUnchecked(out)
      out.putVarInt32(12)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 11:
        self.add_queuestats().TryMerge(d)
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.queuestats_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("QueueStats%s {\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+"}\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kQueueStatsGroup = 1
  kQueueStatsnum_tasks = 2
  kQueueStatsoldest_eta_usec = 3
  kQueueStatsscanner_info = 4

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "QueueStats",
    2: "num_tasks",
    3: "oldest_eta_usec",
    4: "scanner_info",
  }, 4)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STARTGROUP,
    2: ProtocolBuffer.Encoder.NUMERIC,
    3: ProtocolBuffer.Encoder.NUMERIC,
    4: ProtocolBuffer.Encoder.STRING,
  }, 4, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueDeleteQueueRequest(ProtocolBuffer.ProtocolMessage):
  has_app_id_ = 0
  app_id_ = ""
  has_queue_name_ = 0
  queue_name_ = ""

  def __init__(self, contents=None):
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

  def queue_name(self): return self.queue_name_

  def set_queue_name(self, x):
    self.has_queue_name_ = 1
    self.queue_name_ = x

  def clear_queue_name(self):
    if self.has_queue_name_:
      self.has_queue_name_ = 0
      self.queue_name_ = ""

  def has_queue_name(self): return self.has_queue_name_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_app_id()): self.set_app_id(x.app_id())
    if (x.has_queue_name()): self.set_queue_name(x.queue_name())

  def Equals(self, x):
    if x is self: return 1
    if self.has_app_id_ != x.has_app_id_: return 0
    if self.has_app_id_ and self.app_id_ != x.app_id_: return 0
    if self.has_queue_name_ != x.has_queue_name_: return 0
    if self.has_queue_name_ and self.queue_name_ != x.queue_name_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_app_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: app_id not set.')
    if (not self.has_queue_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: queue_name not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.app_id_))
    n += self.lengthString(len(self.queue_name_))
    return n + 2

  def Clear(self):
    self.clear_app_id()
    self.clear_queue_name()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.app_id_)
    out.putVarInt32(18)
    out.putPrefixedString(self.queue_name_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_app_id(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_queue_name(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_app_id_: res+=prefix+("app_id: %s\n" % self.DebugFormatString(self.app_id_))
    if self.has_queue_name_: res+=prefix+("queue_name: %s\n" % self.DebugFormatString(self.queue_name_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kapp_id = 1
  kqueue_name = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "app_id",
    2: "queue_name",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueDeleteQueueResponse(ProtocolBuffer.ProtocolMessage):

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


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])


  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
  }, 0)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
  }, 0, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueQueryTasksRequest(ProtocolBuffer.ProtocolMessage):
  has_app_id_ = 0
  app_id_ = ""
  has_queue_name_ = 0
  queue_name_ = ""
  has_start_task_name_ = 0
  start_task_name_ = ""
  has_start_eta_usec_ = 0
  start_eta_usec_ = 0
  has_max_rows_ = 0
  max_rows_ = 1

  def __init__(self, contents=None):
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

  def queue_name(self): return self.queue_name_

  def set_queue_name(self, x):
    self.has_queue_name_ = 1
    self.queue_name_ = x

  def clear_queue_name(self):
    if self.has_queue_name_:
      self.has_queue_name_ = 0
      self.queue_name_ = ""

  def has_queue_name(self): return self.has_queue_name_

  def start_task_name(self): return self.start_task_name_

  def set_start_task_name(self, x):
    self.has_start_task_name_ = 1
    self.start_task_name_ = x

  def clear_start_task_name(self):
    if self.has_start_task_name_:
      self.has_start_task_name_ = 0
      self.start_task_name_ = ""

  def has_start_task_name(self): return self.has_start_task_name_

  def start_eta_usec(self): return self.start_eta_usec_

  def set_start_eta_usec(self, x):
    self.has_start_eta_usec_ = 1
    self.start_eta_usec_ = x

  def clear_start_eta_usec(self):
    if self.has_start_eta_usec_:
      self.has_start_eta_usec_ = 0
      self.start_eta_usec_ = 0

  def has_start_eta_usec(self): return self.has_start_eta_usec_

  def max_rows(self): return self.max_rows_

  def set_max_rows(self, x):
    self.has_max_rows_ = 1
    self.max_rows_ = x

  def clear_max_rows(self):
    if self.has_max_rows_:
      self.has_max_rows_ = 0
      self.max_rows_ = 1

  def has_max_rows(self): return self.has_max_rows_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_app_id()): self.set_app_id(x.app_id())
    if (x.has_queue_name()): self.set_queue_name(x.queue_name())
    if (x.has_start_task_name()): self.set_start_task_name(x.start_task_name())
    if (x.has_start_eta_usec()): self.set_start_eta_usec(x.start_eta_usec())
    if (x.has_max_rows()): self.set_max_rows(x.max_rows())

  def Equals(self, x):
    if x is self: return 1
    if self.has_app_id_ != x.has_app_id_: return 0
    if self.has_app_id_ and self.app_id_ != x.app_id_: return 0
    if self.has_queue_name_ != x.has_queue_name_: return 0
    if self.has_queue_name_ and self.queue_name_ != x.queue_name_: return 0
    if self.has_start_task_name_ != x.has_start_task_name_: return 0
    if self.has_start_task_name_ and self.start_task_name_ != x.start_task_name_: return 0
    if self.has_start_eta_usec_ != x.has_start_eta_usec_: return 0
    if self.has_start_eta_usec_ and self.start_eta_usec_ != x.start_eta_usec_: return 0
    if self.has_max_rows_ != x.has_max_rows_: return 0
    if self.has_max_rows_ and self.max_rows_ != x.max_rows_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_app_id_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: app_id not set.')
    if (not self.has_queue_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: queue_name not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.app_id_))
    n += self.lengthString(len(self.queue_name_))
    if (self.has_start_task_name_): n += 1 + self.lengthString(len(self.start_task_name_))
    if (self.has_start_eta_usec_): n += 1 + self.lengthVarInt64(self.start_eta_usec_)
    if (self.has_max_rows_): n += 1 + self.lengthVarInt64(self.max_rows_)
    return n + 2

  def Clear(self):
    self.clear_app_id()
    self.clear_queue_name()
    self.clear_start_task_name()
    self.clear_start_eta_usec()
    self.clear_max_rows()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.app_id_)
    out.putVarInt32(18)
    out.putPrefixedString(self.queue_name_)
    if (self.has_start_task_name_):
      out.putVarInt32(26)
      out.putPrefixedString(self.start_task_name_)
    if (self.has_start_eta_usec_):
      out.putVarInt32(32)
      out.putVarInt64(self.start_eta_usec_)
    if (self.has_max_rows_):
      out.putVarInt32(40)
      out.putVarInt32(self.max_rows_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_app_id(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_queue_name(d.getPrefixedString())
        continue
      if tt == 26:
        self.set_start_task_name(d.getPrefixedString())
        continue
      if tt == 32:
        self.set_start_eta_usec(d.getVarInt64())
        continue
      if tt == 40:
        self.set_max_rows(d.getVarInt32())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_app_id_: res+=prefix+("app_id: %s\n" % self.DebugFormatString(self.app_id_))
    if self.has_queue_name_: res+=prefix+("queue_name: %s\n" % self.DebugFormatString(self.queue_name_))
    if self.has_start_task_name_: res+=prefix+("start_task_name: %s\n" % self.DebugFormatString(self.start_task_name_))
    if self.has_start_eta_usec_: res+=prefix+("start_eta_usec: %s\n" % self.DebugFormatInt64(self.start_eta_usec_))
    if self.has_max_rows_: res+=prefix+("max_rows: %s\n" % self.DebugFormatInt32(self.max_rows_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kapp_id = 1
  kqueue_name = 2
  kstart_task_name = 3
  kstart_eta_usec = 4
  kmax_rows = 5

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "app_id",
    2: "queue_name",
    3: "start_task_name",
    4: "start_eta_usec",
    5: "max_rows",
  }, 5)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.STRING,
    4: ProtocolBuffer.Encoder.NUMERIC,
    5: ProtocolBuffer.Encoder.NUMERIC,
  }, 5, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class TaskQueueQueryTasksResponse_TaskHeader(ProtocolBuffer.ProtocolMessage):
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
    out.putVarInt32(66)
    out.putPrefixedString(self.key_)
    out.putVarInt32(74)
    out.putPrefixedString(self.value_)

  def TryMerge(self, d):
    while 1:
      tt = d.getVarInt32()
      if tt == 60: break
      if tt == 66:
        self.set_key(d.getPrefixedString())
        continue
      if tt == 74:
        self.set_value(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_key_: res+=prefix+("key: %s\n" % self.DebugFormatString(self.key_))
    if self.has_value_: res+=prefix+("value: %s\n" % self.DebugFormatString(self.value_))
    return res

class TaskQueueQueryTasksResponse_Task(ProtocolBuffer.ProtocolMessage):

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

  has_task_name_ = 0
  task_name_ = ""
  has_eta_usec_ = 0
  eta_usec_ = 0
  has_url_ = 0
  url_ = ""
  has_method_ = 0
  method_ = 0
  has_retry_count_ = 0
  retry_count_ = 0
  has_body_size_ = 0
  body_size_ = 0
  has_body_ = 0
  body_ = ""

  def __init__(self, contents=None):
    self.header_ = []
    if contents is not None: self.MergeFromString(contents)

  def task_name(self): return self.task_name_

  def set_task_name(self, x):
    self.has_task_name_ = 1
    self.task_name_ = x

  def clear_task_name(self):
    if self.has_task_name_:
      self.has_task_name_ = 0
      self.task_name_ = ""

  def has_task_name(self): return self.has_task_name_

  def eta_usec(self): return self.eta_usec_

  def set_eta_usec(self, x):
    self.has_eta_usec_ = 1
    self.eta_usec_ = x

  def clear_eta_usec(self):
    if self.has_eta_usec_:
      self.has_eta_usec_ = 0
      self.eta_usec_ = 0

  def has_eta_usec(self): return self.has_eta_usec_

  def url(self): return self.url_

  def set_url(self, x):
    self.has_url_ = 1
    self.url_ = x

  def clear_url(self):
    if self.has_url_:
      self.has_url_ = 0
      self.url_ = ""

  def has_url(self): return self.has_url_

  def method(self): return self.method_

  def set_method(self, x):
    self.has_method_ = 1
    self.method_ = x

  def clear_method(self):
    if self.has_method_:
      self.has_method_ = 0
      self.method_ = 0

  def has_method(self): return self.has_method_

  def retry_count(self): return self.retry_count_

  def set_retry_count(self, x):
    self.has_retry_count_ = 1
    self.retry_count_ = x

  def clear_retry_count(self):
    if self.has_retry_count_:
      self.has_retry_count_ = 0
      self.retry_count_ = 0

  def has_retry_count(self): return self.has_retry_count_

  def header_size(self): return len(self.header_)
  def header_list(self): return self.header_

  def header(self, i):
    return self.header_[i]

  def mutable_header(self, i):
    return self.header_[i]

  def add_header(self):
    x = TaskQueueQueryTasksResponse_TaskHeader()
    self.header_.append(x)
    return x

  def clear_header(self):
    self.header_ = []
  def body_size(self): return self.body_size_

  def set_body_size(self, x):
    self.has_body_size_ = 1
    self.body_size_ = x

  def clear_body_size(self):
    if self.has_body_size_:
      self.has_body_size_ = 0
      self.body_size_ = 0

  def has_body_size(self): return self.has_body_size_

  def body(self): return self.body_

  def set_body(self, x):
    self.has_body_ = 1
    self.body_ = x

  def clear_body(self):
    if self.has_body_:
      self.has_body_ = 0
      self.body_ = ""

  def has_body(self): return self.has_body_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_task_name()): self.set_task_name(x.task_name())
    if (x.has_eta_usec()): self.set_eta_usec(x.eta_usec())
    if (x.has_url()): self.set_url(x.url())
    if (x.has_method()): self.set_method(x.method())
    if (x.has_retry_count()): self.set_retry_count(x.retry_count())
    for i in xrange(x.header_size()): self.add_header().CopyFrom(x.header(i))
    if (x.has_body_size()): self.set_body_size(x.body_size())
    if (x.has_body()): self.set_body(x.body())

  def Equals(self, x):
    if x is self: return 1
    if self.has_task_name_ != x.has_task_name_: return 0
    if self.has_task_name_ and self.task_name_ != x.task_name_: return 0
    if self.has_eta_usec_ != x.has_eta_usec_: return 0
    if self.has_eta_usec_ and self.eta_usec_ != x.eta_usec_: return 0
    if self.has_url_ != x.has_url_: return 0
    if self.has_url_ and self.url_ != x.url_: return 0
    if self.has_method_ != x.has_method_: return 0
    if self.has_method_ and self.method_ != x.method_: return 0
    if self.has_retry_count_ != x.has_retry_count_: return 0
    if self.has_retry_count_ and self.retry_count_ != x.retry_count_: return 0
    if len(self.header_) != len(x.header_): return 0
    for e1, e2 in zip(self.header_, x.header_):
      if e1 != e2: return 0
    if self.has_body_size_ != x.has_body_size_: return 0
    if self.has_body_size_ and self.body_size_ != x.body_size_: return 0
    if self.has_body_ != x.has_body_: return 0
    if self.has_body_ and self.body_ != x.body_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_task_name_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: task_name not set.')
    if (not self.has_eta_usec_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: eta_usec not set.')
    if (not self.has_url_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: url not set.')
    if (not self.has_method_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: method not set.')
    for p in self.header_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.task_name_))
    n += self.lengthVarInt64(self.eta_usec_)
    n += self.lengthString(len(self.url_))
    n += self.lengthVarInt64(self.method_)
    if (self.has_retry_count_): n += 1 + self.lengthVarInt64(self.retry_count_)
    n += 2 * len(self.header_)
    for i in xrange(len(self.header_)): n += self.header_[i].ByteSize()
    if (self.has_body_size_): n += 1 + self.lengthVarInt64(self.body_size_)
    if (self.has_body_): n += 1 + self.lengthString(len(self.body_))
    return n + 4

  def Clear(self):
    self.clear_task_name()
    self.clear_eta_usec()
    self.clear_url()
    self.clear_method()
    self.clear_retry_count()
    self.clear_header()
    self.clear_body_size()
    self.clear_body()

  def OutputUnchecked(self, out):
    out.putVarInt32(18)
    out.putPrefixedString(self.task_name_)
    out.putVarInt32(24)
    out.putVarInt64(self.eta_usec_)
    out.putVarInt32(34)
    out.putPrefixedString(self.url_)
    out.putVarInt32(40)
    out.putVarInt32(self.method_)
    if (self.has_retry_count_):
      out.putVarInt32(48)
      out.putVarInt32(self.retry_count_)
    for i in xrange(len(self.header_)):
      out.putVarInt32(59)
      self.header_[i].OutputUnchecked(out)
      out.putVarInt32(60)
    if (self.has_body_size_):
      out.putVarInt32(80)
      out.putVarInt32(self.body_size_)
    if (self.has_body_):
      out.putVarInt32(90)
      out.putPrefixedString(self.body_)

  def TryMerge(self, d):
    while 1:
      tt = d.getVarInt32()
      if tt == 12: break
      if tt == 18:
        self.set_task_name(d.getPrefixedString())
        continue
      if tt == 24:
        self.set_eta_usec(d.getVarInt64())
        continue
      if tt == 34:
        self.set_url(d.getPrefixedString())
        continue
      if tt == 40:
        self.set_method(d.getVarInt32())
        continue
      if tt == 48:
        self.set_retry_count(d.getVarInt32())
        continue
      if tt == 59:
        self.add_header().TryMerge(d)
        continue
      if tt == 80:
        self.set_body_size(d.getVarInt32())
        continue
      if tt == 90:
        self.set_body(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_task_name_: res+=prefix+("task_name: %s\n" % self.DebugFormatString(self.task_name_))
    if self.has_eta_usec_: res+=prefix+("eta_usec: %s\n" % self.DebugFormatInt64(self.eta_usec_))
    if self.has_url_: res+=prefix+("url: %s\n" % self.DebugFormatString(self.url_))
    if self.has_method_: res+=prefix+("method: %s\n" % self.DebugFormatInt32(self.method_))
    if self.has_retry_count_: res+=prefix+("retry_count: %s\n" % self.DebugFormatInt32(self.retry_count_))
    cnt=0
    for e in self.header_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("Header%s {\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+"}\n"
      cnt+=1
    if self.has_body_size_: res+=prefix+("body_size: %s\n" % self.DebugFormatInt32(self.body_size_))
    if self.has_body_: res+=prefix+("body: %s\n" % self.DebugFormatString(self.body_))
    return res

class TaskQueueQueryTasksResponse(ProtocolBuffer.ProtocolMessage):

  def __init__(self, contents=None):
    self.task_ = []
    if contents is not None: self.MergeFromString(contents)

  def task_size(self): return len(self.task_)
  def task_list(self): return self.task_

  def task(self, i):
    return self.task_[i]

  def mutable_task(self, i):
    return self.task_[i]

  def add_task(self):
    x = TaskQueueQueryTasksResponse_Task()
    self.task_.append(x)
    return x

  def clear_task(self):
    self.task_ = []

  def MergeFrom(self, x):
    assert x is not self
    for i in xrange(x.task_size()): self.add_task().CopyFrom(x.task(i))

  def Equals(self, x):
    if x is self: return 1
    if len(self.task_) != len(x.task_): return 0
    for e1, e2 in zip(self.task_, x.task_):
      if e1 != e2: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    for p in self.task_:
      if not p.IsInitialized(debug_strs): initialized=0
    return initialized

  def ByteSize(self):
    n = 0
    n += 2 * len(self.task_)
    for i in xrange(len(self.task_)): n += self.task_[i].ByteSize()
    return n + 0

  def Clear(self):
    self.clear_task()

  def OutputUnchecked(self, out):
    for i in xrange(len(self.task_)):
      out.putVarInt32(11)
      self.task_[i].OutputUnchecked(out)
      out.putVarInt32(12)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 11:
        self.add_task().TryMerge(d)
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    cnt=0
    for e in self.task_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("Task%s {\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+"}\n"
      cnt+=1
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kTaskGroup = 1
  kTasktask_name = 2
  kTasketa_usec = 3
  kTaskurl = 4
  kTaskmethod = 5
  kTaskretry_count = 6
  kTaskHeaderGroup = 7
  kTaskHeaderkey = 8
  kTaskHeadervalue = 9
  kTaskbody_size = 10
  kTaskbody = 11

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "Task",
    2: "task_name",
    3: "eta_usec",
    4: "url",
    5: "method",
    6: "retry_count",
    7: "Header",
    8: "key",
    9: "value",
    10: "body_size",
    11: "body",
  }, 11)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STARTGROUP,
    2: ProtocolBuffer.Encoder.STRING,
    3: ProtocolBuffer.Encoder.NUMERIC,
    4: ProtocolBuffer.Encoder.STRING,
    5: ProtocolBuffer.Encoder.NUMERIC,
    6: ProtocolBuffer.Encoder.NUMERIC,
    7: ProtocolBuffer.Encoder.STARTGROUP,
    8: ProtocolBuffer.Encoder.STRING,
    9: ProtocolBuffer.Encoder.STRING,
    10: ProtocolBuffer.Encoder.NUMERIC,
    11: ProtocolBuffer.Encoder.STRING,
  }, 11, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""

__all__ = ['TaskQueueServiceError','TaskQueueAddRequest','TaskQueueAddRequest_Header','TaskQueueAddResponse','TaskQueueDeleteRequest','TaskQueueDeleteResponse','TaskQueueUpdateQueueRequest','TaskQueueUpdateQueueResponse','TaskQueueFetchQueuesRequest','TaskQueueFetchQueuesResponse','TaskQueueFetchQueuesResponse_Queue','TaskQueueFetchQueueStatsRequest','TaskQueueScannerQueueInfo','TaskQueueFetchQueueStatsResponse','TaskQueueFetchQueueStatsResponse_QueueStats','TaskQueueDeleteQueueRequest','TaskQueueDeleteQueueResponse','TaskQueueQueryTasksRequest','TaskQueueQueryTasksResponse','TaskQueueQueryTasksResponse_TaskHeader','TaskQueueQueryTasksResponse_Task']
