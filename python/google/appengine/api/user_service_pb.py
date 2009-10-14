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

from google.appengine.api.api_base_pb import *
class UserServiceError(ProtocolBuffer.ProtocolMessage):

  OK           =    0
  REDIRECT_URL_TOO_LONG =    1
  NOT_ALLOWED  =    2
  OAUTH_INVALID_TOKEN =    3
  OAUTH_INVALID_REQUEST =    4
  OAUTH_ERROR  =    5

  _ErrorCode_NAMES = {
    0: "OK",
    1: "REDIRECT_URL_TOO_LONG",
    2: "NOT_ALLOWED",
    3: "OAUTH_INVALID_TOKEN",
    4: "OAUTH_INVALID_REQUEST",
    5: "OAUTH_ERROR",
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
class CreateLoginURLRequest(ProtocolBuffer.ProtocolMessage):
  has_destination_url_ = 0
  destination_url_ = ""
  has_auth_domain_ = 0
  auth_domain_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def destination_url(self): return self.destination_url_

  def set_destination_url(self, x):
    self.has_destination_url_ = 1
    self.destination_url_ = x

  def clear_destination_url(self):
    if self.has_destination_url_:
      self.has_destination_url_ = 0
      self.destination_url_ = ""

  def has_destination_url(self): return self.has_destination_url_

  def auth_domain(self): return self.auth_domain_

  def set_auth_domain(self, x):
    self.has_auth_domain_ = 1
    self.auth_domain_ = x

  def clear_auth_domain(self):
    if self.has_auth_domain_:
      self.has_auth_domain_ = 0
      self.auth_domain_ = ""

  def has_auth_domain(self): return self.has_auth_domain_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_destination_url()): self.set_destination_url(x.destination_url())
    if (x.has_auth_domain()): self.set_auth_domain(x.auth_domain())

  def Equals(self, x):
    if x is self: return 1
    if self.has_destination_url_ != x.has_destination_url_: return 0
    if self.has_destination_url_ and self.destination_url_ != x.destination_url_: return 0
    if self.has_auth_domain_ != x.has_auth_domain_: return 0
    if self.has_auth_domain_ and self.auth_domain_ != x.auth_domain_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_destination_url_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: destination_url not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.destination_url_))
    if (self.has_auth_domain_): n += 1 + self.lengthString(len(self.auth_domain_))
    return n + 1

  def Clear(self):
    self.clear_destination_url()
    self.clear_auth_domain()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.destination_url_)
    if (self.has_auth_domain_):
      out.putVarInt32(18)
      out.putPrefixedString(self.auth_domain_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_destination_url(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_auth_domain(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_destination_url_: res+=prefix+("destination_url: %s\n" % self.DebugFormatString(self.destination_url_))
    if self.has_auth_domain_: res+=prefix+("auth_domain: %s\n" % self.DebugFormatString(self.auth_domain_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kdestination_url = 1
  kauth_domain = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "destination_url",
    2: "auth_domain",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class CreateLoginURLResponse(ProtocolBuffer.ProtocolMessage):
  has_login_url_ = 0
  login_url_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def login_url(self): return self.login_url_

  def set_login_url(self, x):
    self.has_login_url_ = 1
    self.login_url_ = x

  def clear_login_url(self):
    if self.has_login_url_:
      self.has_login_url_ = 0
      self.login_url_ = ""

  def has_login_url(self): return self.has_login_url_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_login_url()): self.set_login_url(x.login_url())

  def Equals(self, x):
    if x is self: return 1
    if self.has_login_url_ != x.has_login_url_: return 0
    if self.has_login_url_ and self.login_url_ != x.login_url_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_login_url_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: login_url not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.login_url_))
    return n + 1

  def Clear(self):
    self.clear_login_url()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.login_url_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_login_url(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_login_url_: res+=prefix+("login_url: %s\n" % self.DebugFormatString(self.login_url_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  klogin_url = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "login_url",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class CreateLogoutURLRequest(ProtocolBuffer.ProtocolMessage):
  has_destination_url_ = 0
  destination_url_ = ""
  has_auth_domain_ = 0
  auth_domain_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def destination_url(self): return self.destination_url_

  def set_destination_url(self, x):
    self.has_destination_url_ = 1
    self.destination_url_ = x

  def clear_destination_url(self):
    if self.has_destination_url_:
      self.has_destination_url_ = 0
      self.destination_url_ = ""

  def has_destination_url(self): return self.has_destination_url_

  def auth_domain(self): return self.auth_domain_

  def set_auth_domain(self, x):
    self.has_auth_domain_ = 1
    self.auth_domain_ = x

  def clear_auth_domain(self):
    if self.has_auth_domain_:
      self.has_auth_domain_ = 0
      self.auth_domain_ = ""

  def has_auth_domain(self): return self.has_auth_domain_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_destination_url()): self.set_destination_url(x.destination_url())
    if (x.has_auth_domain()): self.set_auth_domain(x.auth_domain())

  def Equals(self, x):
    if x is self: return 1
    if self.has_destination_url_ != x.has_destination_url_: return 0
    if self.has_destination_url_ and self.destination_url_ != x.destination_url_: return 0
    if self.has_auth_domain_ != x.has_auth_domain_: return 0
    if self.has_auth_domain_ and self.auth_domain_ != x.auth_domain_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_destination_url_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: destination_url not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.destination_url_))
    if (self.has_auth_domain_): n += 1 + self.lengthString(len(self.auth_domain_))
    return n + 1

  def Clear(self):
    self.clear_destination_url()
    self.clear_auth_domain()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.destination_url_)
    if (self.has_auth_domain_):
      out.putVarInt32(18)
      out.putPrefixedString(self.auth_domain_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_destination_url(d.getPrefixedString())
        continue
      if tt == 18:
        self.set_auth_domain(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_destination_url_: res+=prefix+("destination_url: %s\n" % self.DebugFormatString(self.destination_url_))
    if self.has_auth_domain_: res+=prefix+("auth_domain: %s\n" % self.DebugFormatString(self.auth_domain_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kdestination_url = 1
  kauth_domain = 2

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "destination_url",
    2: "auth_domain",
  }, 2)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
    2: ProtocolBuffer.Encoder.STRING,
  }, 2, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class CreateLogoutURLResponse(ProtocolBuffer.ProtocolMessage):
  has_logout_url_ = 0
  logout_url_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def logout_url(self): return self.logout_url_

  def set_logout_url(self, x):
    self.has_logout_url_ = 1
    self.logout_url_ = x

  def clear_logout_url(self):
    if self.has_logout_url_:
      self.has_logout_url_ = 0
      self.logout_url_ = ""

  def has_logout_url(self): return self.has_logout_url_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_logout_url()): self.set_logout_url(x.logout_url())

  def Equals(self, x):
    if x is self: return 1
    if self.has_logout_url_ != x.has_logout_url_: return 0
    if self.has_logout_url_ and self.logout_url_ != x.logout_url_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_logout_url_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: logout_url not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.logout_url_))
    return n + 1

  def Clear(self):
    self.clear_logout_url()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.logout_url_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_logout_url(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_logout_url_: res+=prefix+("logout_url: %s\n" % self.DebugFormatString(self.logout_url_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  klogout_url = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "logout_url",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class GetOAuthUserRequest(ProtocolBuffer.ProtocolMessage):

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
class GetOAuthUserResponse(ProtocolBuffer.ProtocolMessage):
  has_email_ = 0
  email_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def email(self): return self.email_

  def set_email(self, x):
    self.has_email_ = 1
    self.email_ = x

  def clear_email(self):
    if self.has_email_:
      self.has_email_ = 0
      self.email_ = ""

  def has_email(self): return self.has_email_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_email()): self.set_email(x.email())

  def Equals(self, x):
    if x is self: return 1
    if self.has_email_ != x.has_email_: return 0
    if self.has_email_ and self.email_ != x.email_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_email_): n += 1 + self.lengthString(len(self.email_))
    return n + 0

  def Clear(self):
    self.clear_email()

  def OutputUnchecked(self, out):
    if (self.has_email_):
      out.putVarInt32(10)
      out.putPrefixedString(self.email_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_email(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_email_: res+=prefix+("email: %s\n" % self.DebugFormatString(self.email_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  kemail = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "email",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class CheckOAuthSignatureRequest(ProtocolBuffer.ProtocolMessage):

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
class CheckOAuthSignatureResponse(ProtocolBuffer.ProtocolMessage):
  has_oauth_consumer_key_ = 0
  oauth_consumer_key_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def oauth_consumer_key(self): return self.oauth_consumer_key_

  def set_oauth_consumer_key(self, x):
    self.has_oauth_consumer_key_ = 1
    self.oauth_consumer_key_ = x

  def clear_oauth_consumer_key(self):
    if self.has_oauth_consumer_key_:
      self.has_oauth_consumer_key_ = 0
      self.oauth_consumer_key_ = ""

  def has_oauth_consumer_key(self): return self.has_oauth_consumer_key_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_oauth_consumer_key()): self.set_oauth_consumer_key(x.oauth_consumer_key())

  def Equals(self, x):
    if x is self: return 1
    if self.has_oauth_consumer_key_ != x.has_oauth_consumer_key_: return 0
    if self.has_oauth_consumer_key_ and self.oauth_consumer_key_ != x.oauth_consumer_key_: return 0
    return 1

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_oauth_consumer_key_): n += 1 + self.lengthString(len(self.oauth_consumer_key_))
    return n + 0

  def Clear(self):
    self.clear_oauth_consumer_key()

  def OutputUnchecked(self, out):
    if (self.has_oauth_consumer_key_):
      out.putVarInt32(10)
      out.putPrefixedString(self.oauth_consumer_key_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_oauth_consumer_key(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_oauth_consumer_key_: res+=prefix+("oauth_consumer_key: %s\n" % self.DebugFormatString(self.oauth_consumer_key_))
    return res


  def _BuildTagLookupTable(sparse, maxtag, default=None):
    return tuple([sparse.get(i, default) for i in xrange(0, 1+maxtag)])

  koauth_consumer_key = 1

  _TEXT = _BuildTagLookupTable({
    0: "ErrorCode",
    1: "oauth_consumer_key",
  }, 1)

  _TYPES = _BuildTagLookupTable({
    0: ProtocolBuffer.Encoder.NUMERIC,
    1: ProtocolBuffer.Encoder.STRING,
  }, 1, ProtocolBuffer.Encoder.MAX_TYPE)

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""

__all__ = ['UserServiceError','CreateLoginURLRequest','CreateLoginURLResponse','CreateLogoutURLRequest','CreateLogoutURLResponse','GetOAuthUserRequest','GetOAuthUserResponse','CheckOAuthSignatureRequest','CheckOAuthSignatureResponse']
