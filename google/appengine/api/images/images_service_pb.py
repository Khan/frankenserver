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

class ImagesServiceError(ProtocolBuffer.ProtocolMessage):

  UNSPECIFIED_ERROR =    1
  BAD_TRANSFORM_DATA =    2
  NOT_IMAGE    =    3
  BAD_IMAGE_DATA =    4
  IMAGE_TOO_LARGE =    5

  _ErrorCode_NAMES = {
    1: "UNSPECIFIED_ERROR",
    2: "BAD_TRANSFORM_DATA",
    3: "NOT_IMAGE",
    4: "BAD_IMAGE_DATA",
    5: "IMAGE_TOO_LARGE",
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

  def __eq__(self, other):
    return (other is not None) and (other.__class__ == self.__class__) and self.Equals(other)

  def __ne__(self, other):
    return not (self == other)

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
class ImagesServiceTransform(ProtocolBuffer.ProtocolMessage):

  RESIZE       =    1
  ROTATE       =    2
  HORIZONTAL_FLIP =    3
  VERTICAL_FLIP =    4
  CROP         =    5
  IM_FEELING_LUCKY =    6

  _Type_NAMES = {
    1: "RESIZE",
    2: "ROTATE",
    3: "HORIZONTAL_FLIP",
    4: "VERTICAL_FLIP",
    5: "CROP",
    6: "IM_FEELING_LUCKY",
  }

  def Type_Name(cls, x): return cls._Type_NAMES.get(x, "")
  Type_Name = classmethod(Type_Name)


  def __init__(self, contents=None):
    pass
    if contents is not None: self.MergeFromString(contents)


  def MergeFrom(self, x):
    assert x is not self

  def Equals(self, x):
    if x is self: return 1
    return 1

  def __eq__(self, other):
    return (other is not None) and (other.__class__ == self.__class__) and self.Equals(other)

  def __ne__(self, other):
    return not (self == other)

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
class Transform(ProtocolBuffer.ProtocolMessage):
  has_width_ = 0
  width_ = 0
  has_height_ = 0
  height_ = 0
  has_rotate_ = 0
  rotate_ = 0
  has_horizontal_flip_ = 0
  horizontal_flip_ = 0
  has_vertical_flip_ = 0
  vertical_flip_ = 0
  has_crop_left_x_ = 0
  crop_left_x_ = 0.0
  has_crop_top_y_ = 0
  crop_top_y_ = 0.0
  has_crop_right_x_ = 0
  crop_right_x_ = 1.0
  has_crop_bottom_y_ = 0
  crop_bottom_y_ = 1.0
  has_autolevels_ = 0
  autolevels_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def width(self): return self.width_

  def set_width(self, x):
    self.has_width_ = 1
    self.width_ = x

  def clear_width(self):
    self.has_width_ = 0
    self.width_ = 0

  def has_width(self): return self.has_width_

  def height(self): return self.height_

  def set_height(self, x):
    self.has_height_ = 1
    self.height_ = x

  def clear_height(self):
    self.has_height_ = 0
    self.height_ = 0

  def has_height(self): return self.has_height_

  def rotate(self): return self.rotate_

  def set_rotate(self, x):
    self.has_rotate_ = 1
    self.rotate_ = x

  def clear_rotate(self):
    self.has_rotate_ = 0
    self.rotate_ = 0

  def has_rotate(self): return self.has_rotate_

  def horizontal_flip(self): return self.horizontal_flip_

  def set_horizontal_flip(self, x):
    self.has_horizontal_flip_ = 1
    self.horizontal_flip_ = x

  def clear_horizontal_flip(self):
    self.has_horizontal_flip_ = 0
    self.horizontal_flip_ = 0

  def has_horizontal_flip(self): return self.has_horizontal_flip_

  def vertical_flip(self): return self.vertical_flip_

  def set_vertical_flip(self, x):
    self.has_vertical_flip_ = 1
    self.vertical_flip_ = x

  def clear_vertical_flip(self):
    self.has_vertical_flip_ = 0
    self.vertical_flip_ = 0

  def has_vertical_flip(self): return self.has_vertical_flip_

  def crop_left_x(self): return self.crop_left_x_

  def set_crop_left_x(self, x):
    self.has_crop_left_x_ = 1
    self.crop_left_x_ = x

  def clear_crop_left_x(self):
    self.has_crop_left_x_ = 0
    self.crop_left_x_ = 0.0

  def has_crop_left_x(self): return self.has_crop_left_x_

  def crop_top_y(self): return self.crop_top_y_

  def set_crop_top_y(self, x):
    self.has_crop_top_y_ = 1
    self.crop_top_y_ = x

  def clear_crop_top_y(self):
    self.has_crop_top_y_ = 0
    self.crop_top_y_ = 0.0

  def has_crop_top_y(self): return self.has_crop_top_y_

  def crop_right_x(self): return self.crop_right_x_

  def set_crop_right_x(self, x):
    self.has_crop_right_x_ = 1
    self.crop_right_x_ = x

  def clear_crop_right_x(self):
    self.has_crop_right_x_ = 0
    self.crop_right_x_ = 1.0

  def has_crop_right_x(self): return self.has_crop_right_x_

  def crop_bottom_y(self): return self.crop_bottom_y_

  def set_crop_bottom_y(self, x):
    self.has_crop_bottom_y_ = 1
    self.crop_bottom_y_ = x

  def clear_crop_bottom_y(self):
    self.has_crop_bottom_y_ = 0
    self.crop_bottom_y_ = 1.0

  def has_crop_bottom_y(self): return self.has_crop_bottom_y_

  def autolevels(self): return self.autolevels_

  def set_autolevels(self, x):
    self.has_autolevels_ = 1
    self.autolevels_ = x

  def clear_autolevels(self):
    self.has_autolevels_ = 0
    self.autolevels_ = 0

  def has_autolevels(self): return self.has_autolevels_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_width()): self.set_width(x.width())
    if (x.has_height()): self.set_height(x.height())
    if (x.has_rotate()): self.set_rotate(x.rotate())
    if (x.has_horizontal_flip()): self.set_horizontal_flip(x.horizontal_flip())
    if (x.has_vertical_flip()): self.set_vertical_flip(x.vertical_flip())
    if (x.has_crop_left_x()): self.set_crop_left_x(x.crop_left_x())
    if (x.has_crop_top_y()): self.set_crop_top_y(x.crop_top_y())
    if (x.has_crop_right_x()): self.set_crop_right_x(x.crop_right_x())
    if (x.has_crop_bottom_y()): self.set_crop_bottom_y(x.crop_bottom_y())
    if (x.has_autolevels()): self.set_autolevels(x.autolevels())

  def Equals(self, x):
    if x is self: return 1
    if self.has_width_ != x.has_width_: return 0
    if self.has_width_ and self.width_ != x.width_: return 0
    if self.has_height_ != x.has_height_: return 0
    if self.has_height_ and self.height_ != x.height_: return 0
    if self.has_rotate_ != x.has_rotate_: return 0
    if self.has_rotate_ and self.rotate_ != x.rotate_: return 0
    if self.has_horizontal_flip_ != x.has_horizontal_flip_: return 0
    if self.has_horizontal_flip_ and self.horizontal_flip_ != x.horizontal_flip_: return 0
    if self.has_vertical_flip_ != x.has_vertical_flip_: return 0
    if self.has_vertical_flip_ and self.vertical_flip_ != x.vertical_flip_: return 0
    if self.has_crop_left_x_ != x.has_crop_left_x_: return 0
    if self.has_crop_left_x_ and self.crop_left_x_ != x.crop_left_x_: return 0
    if self.has_crop_top_y_ != x.has_crop_top_y_: return 0
    if self.has_crop_top_y_ and self.crop_top_y_ != x.crop_top_y_: return 0
    if self.has_crop_right_x_ != x.has_crop_right_x_: return 0
    if self.has_crop_right_x_ and self.crop_right_x_ != x.crop_right_x_: return 0
    if self.has_crop_bottom_y_ != x.has_crop_bottom_y_: return 0
    if self.has_crop_bottom_y_ and self.crop_bottom_y_ != x.crop_bottom_y_: return 0
    if self.has_autolevels_ != x.has_autolevels_: return 0
    if self.has_autolevels_ and self.autolevels_ != x.autolevels_: return 0
    return 1

  def __eq__(self, other):
    return (other is not None) and (other.__class__ == self.__class__) and self.Equals(other)

  def __ne__(self, other):
    return not (self == other)

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_width_): n += 1 + self.lengthVarInt64(self.width_)
    if (self.has_height_): n += 1 + self.lengthVarInt64(self.height_)
    if (self.has_rotate_): n += 1 + self.lengthVarInt64(self.rotate_)
    if (self.has_horizontal_flip_): n += 2
    if (self.has_vertical_flip_): n += 2
    if (self.has_crop_left_x_): n += 5
    if (self.has_crop_top_y_): n += 5
    if (self.has_crop_right_x_): n += 5
    if (self.has_crop_bottom_y_): n += 5
    if (self.has_autolevels_): n += 2
    return n + 0

  def Clear(self):
    self.clear_width()
    self.clear_height()
    self.clear_rotate()
    self.clear_horizontal_flip()
    self.clear_vertical_flip()
    self.clear_crop_left_x()
    self.clear_crop_top_y()
    self.clear_crop_right_x()
    self.clear_crop_bottom_y()
    self.clear_autolevels()

  def OutputUnchecked(self, out):
    if (self.has_width_):
      out.putVarInt32(8)
      out.putVarInt32(self.width_)
    if (self.has_height_):
      out.putVarInt32(16)
      out.putVarInt32(self.height_)
    if (self.has_rotate_):
      out.putVarInt32(24)
      out.putVarInt32(self.rotate_)
    if (self.has_horizontal_flip_):
      out.putVarInt32(32)
      out.putBoolean(self.horizontal_flip_)
    if (self.has_vertical_flip_):
      out.putVarInt32(40)
      out.putBoolean(self.vertical_flip_)
    if (self.has_crop_left_x_):
      out.putVarInt32(53)
      out.putFloat(self.crop_left_x_)
    if (self.has_crop_top_y_):
      out.putVarInt32(61)
      out.putFloat(self.crop_top_y_)
    if (self.has_crop_right_x_):
      out.putVarInt32(69)
      out.putFloat(self.crop_right_x_)
    if (self.has_crop_bottom_y_):
      out.putVarInt32(77)
      out.putFloat(self.crop_bottom_y_)
    if (self.has_autolevels_):
      out.putVarInt32(80)
      out.putBoolean(self.autolevels_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_width(d.getVarInt32())
        continue
      if tt == 16:
        self.set_height(d.getVarInt32())
        continue
      if tt == 24:
        self.set_rotate(d.getVarInt32())
        continue
      if tt == 32:
        self.set_horizontal_flip(d.getBoolean())
        continue
      if tt == 40:
        self.set_vertical_flip(d.getBoolean())
        continue
      if tt == 53:
        self.set_crop_left_x(d.getFloat())
        continue
      if tt == 61:
        self.set_crop_top_y(d.getFloat())
        continue
      if tt == 69:
        self.set_crop_right_x(d.getFloat())
        continue
      if tt == 77:
        self.set_crop_bottom_y(d.getFloat())
        continue
      if tt == 80:
        self.set_autolevels(d.getBoolean())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_width_: res+=prefix+("width: %s\n" % self.DebugFormatInt32(self.width_))
    if self.has_height_: res+=prefix+("height: %s\n" % self.DebugFormatInt32(self.height_))
    if self.has_rotate_: res+=prefix+("rotate: %s\n" % self.DebugFormatInt32(self.rotate_))
    if self.has_horizontal_flip_: res+=prefix+("horizontal_flip: %s\n" % self.DebugFormatBool(self.horizontal_flip_))
    if self.has_vertical_flip_: res+=prefix+("vertical_flip: %s\n" % self.DebugFormatBool(self.vertical_flip_))
    if self.has_crop_left_x_: res+=prefix+("crop_left_x: %s\n" % self.DebugFormatFloat(self.crop_left_x_))
    if self.has_crop_top_y_: res+=prefix+("crop_top_y: %s\n" % self.DebugFormatFloat(self.crop_top_y_))
    if self.has_crop_right_x_: res+=prefix+("crop_right_x: %s\n" % self.DebugFormatFloat(self.crop_right_x_))
    if self.has_crop_bottom_y_: res+=prefix+("crop_bottom_y: %s\n" % self.DebugFormatFloat(self.crop_bottom_y_))
    if self.has_autolevels_: res+=prefix+("autolevels: %s\n" % self.DebugFormatBool(self.autolevels_))
    return res

  kwidth = 1
  kheight = 2
  krotate = 3
  khorizontal_flip = 4
  kvertical_flip = 5
  kcrop_left_x = 6
  kcrop_top_y = 7
  kcrop_right_x = 8
  kcrop_bottom_y = 9
  kautolevels = 10

  _TEXT = (
   "ErrorCode",
   "width",
   "height",
   "rotate",
   "horizontal_flip",
   "vertical_flip",
   "crop_left_x",
   "crop_top_y",
   "crop_right_x",
   "crop_bottom_y",
   "autolevels",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.NUMERIC,

   ProtocolBuffer.Encoder.NUMERIC,

   ProtocolBuffer.Encoder.NUMERIC,

   ProtocolBuffer.Encoder.NUMERIC,

   ProtocolBuffer.Encoder.NUMERIC,

   ProtocolBuffer.Encoder.FLOAT,

   ProtocolBuffer.Encoder.FLOAT,

   ProtocolBuffer.Encoder.FLOAT,

   ProtocolBuffer.Encoder.FLOAT,

   ProtocolBuffer.Encoder.NUMERIC,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class ImageData(ProtocolBuffer.ProtocolMessage):
  has_content_ = 0
  content_ = ""

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def content(self): return self.content_

  def set_content(self, x):
    self.has_content_ = 1
    self.content_ = x

  def clear_content(self):
    self.has_content_ = 0
    self.content_ = ""

  def has_content(self): return self.has_content_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_content()): self.set_content(x.content())

  def Equals(self, x):
    if x is self: return 1
    if self.has_content_ != x.has_content_: return 0
    if self.has_content_ and self.content_ != x.content_: return 0
    return 1

  def __eq__(self, other):
    return (other is not None) and (other.__class__ == self.__class__) and self.Equals(other)

  def __ne__(self, other):
    return not (self == other)

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_content_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: content not set.')
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(len(self.content_))
    return n + 1

  def Clear(self):
    self.clear_content()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putPrefixedString(self.content_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        self.set_content(d.getPrefixedString())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_content_: res+=prefix+("content: %s\n" % self.DebugFormatString(self.content_))
    return res

  kcontent = 1

  _TEXT = (
   "ErrorCode",
   "content",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.STRING,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class OutputSettings(ProtocolBuffer.ProtocolMessage):

  PNG          =    0
  JPEG         =    1

  _MIME_TYPE_NAMES = {
    0: "PNG",
    1: "JPEG",
  }

  def MIME_TYPE_Name(cls, x): return cls._MIME_TYPE_NAMES.get(x, "")
  MIME_TYPE_Name = classmethod(MIME_TYPE_Name)

  has_mime_type_ = 0
  mime_type_ = 0

  def __init__(self, contents=None):
    if contents is not None: self.MergeFromString(contents)

  def mime_type(self): return self.mime_type_

  def set_mime_type(self, x):
    self.has_mime_type_ = 1
    self.mime_type_ = x

  def clear_mime_type(self):
    self.has_mime_type_ = 0
    self.mime_type_ = 0

  def has_mime_type(self): return self.has_mime_type_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_mime_type()): self.set_mime_type(x.mime_type())

  def Equals(self, x):
    if x is self: return 1
    if self.has_mime_type_ != x.has_mime_type_: return 0
    if self.has_mime_type_ and self.mime_type_ != x.mime_type_: return 0
    return 1

  def __eq__(self, other):
    return (other is not None) and (other.__class__ == self.__class__) and self.Equals(other)

  def __ne__(self, other):
    return not (self == other)

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    return initialized

  def ByteSize(self):
    n = 0
    if (self.has_mime_type_): n += 1 + self.lengthVarInt64(self.mime_type_)
    return n + 0

  def Clear(self):
    self.clear_mime_type()

  def OutputUnchecked(self, out):
    if (self.has_mime_type_):
      out.putVarInt32(8)
      out.putVarInt32(self.mime_type_)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 8:
        self.set_mime_type(d.getVarInt32())
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_mime_type_: res+=prefix+("mime_type: %s\n" % self.DebugFormatInt32(self.mime_type_))
    return res

  kmime_type = 1

  _TEXT = (
   "ErrorCode",
   "mime_type",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.NUMERIC,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class ImagesTransformRequest(ProtocolBuffer.ProtocolMessage):
  has_image_ = 0
  has_output_ = 0

  def __init__(self, contents=None):
    self.image_ = ImageData()
    self.transform_ = []
    self.output_ = OutputSettings()
    if contents is not None: self.MergeFromString(contents)

  def image(self): return self.image_

  def mutable_image(self): self.has_image_ = 1; return self.image_

  def clear_image(self):self.has_image_ = 0; self.image_.Clear()

  def has_image(self): return self.has_image_

  def transform_size(self): return len(self.transform_)
  def transform_list(self): return self.transform_

  def transform(self, i):
    return self.transform_[i]

  def mutable_transform(self, i):
    return self.transform_[i]

  def add_transform(self):
    x = Transform()
    self.transform_.append(x)
    return x

  def clear_transform(self):
    self.transform_ = []
  def output(self): return self.output_

  def mutable_output(self): self.has_output_ = 1; return self.output_

  def clear_output(self):self.has_output_ = 0; self.output_.Clear()

  def has_output(self): return self.has_output_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_image()): self.mutable_image().MergeFrom(x.image())
    for i in xrange(x.transform_size()): self.add_transform().CopyFrom(x.transform(i))
    if (x.has_output()): self.mutable_output().MergeFrom(x.output())

  def Equals(self, x):
    if x is self: return 1
    if self.has_image_ != x.has_image_: return 0
    if self.has_image_ and self.image_ != x.image_: return 0
    if len(self.transform_) != len(x.transform_): return 0
    for e1, e2 in zip(self.transform_, x.transform_):
      if e1 != e2: return 0
    if self.has_output_ != x.has_output_: return 0
    if self.has_output_ and self.output_ != x.output_: return 0
    return 1

  def __eq__(self, other):
    return (other is not None) and (other.__class__ == self.__class__) and self.Equals(other)

  def __ne__(self, other):
    return not (self == other)

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_image_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: image not set.')
    elif not self.image_.IsInitialized(debug_strs): initialized = 0
    for p in self.transform_:
      if not p.IsInitialized(debug_strs): initialized=0
    if (not self.has_output_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: output not set.')
    elif not self.output_.IsInitialized(debug_strs): initialized = 0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(self.image_.ByteSize())
    n += 1 * len(self.transform_)
    for i in xrange(len(self.transform_)): n += self.lengthString(self.transform_[i].ByteSize())
    n += self.lengthString(self.output_.ByteSize())
    return n + 2

  def Clear(self):
    self.clear_image()
    self.clear_transform()
    self.clear_output()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putVarInt32(self.image_.ByteSize())
    self.image_.OutputUnchecked(out)
    for i in xrange(len(self.transform_)):
      out.putVarInt32(18)
      out.putVarInt32(self.transform_[i].ByteSize())
      self.transform_[i].OutputUnchecked(out)
    out.putVarInt32(26)
    out.putVarInt32(self.output_.ByteSize())
    self.output_.OutputUnchecked(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_image().TryMerge(tmp)
        continue
      if tt == 18:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.add_transform().TryMerge(tmp)
        continue
      if tt == 26:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_output().TryMerge(tmp)
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_image_:
      res+=prefix+"image <\n"
      res+=self.image_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    cnt=0
    for e in self.transform_:
      elm=""
      if printElemNumber: elm="(%d)" % cnt
      res+=prefix+("transform%s <\n" % elm)
      res+=e.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
      cnt+=1
    if self.has_output_:
      res+=prefix+"output <\n"
      res+=self.output_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    return res

  kimage = 1
  ktransform = 2
  koutput = 3

  _TEXT = (
   "ErrorCode",
   "image",
   "transform",
   "output",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.STRING,

   ProtocolBuffer.Encoder.STRING,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""
class ImagesTransformResponse(ProtocolBuffer.ProtocolMessage):
  has_image_ = 0

  def __init__(self, contents=None):
    self.image_ = ImageData()
    if contents is not None: self.MergeFromString(contents)

  def image(self): return self.image_

  def mutable_image(self): self.has_image_ = 1; return self.image_

  def clear_image(self):self.has_image_ = 0; self.image_.Clear()

  def has_image(self): return self.has_image_


  def MergeFrom(self, x):
    assert x is not self
    if (x.has_image()): self.mutable_image().MergeFrom(x.image())

  def Equals(self, x):
    if x is self: return 1
    if self.has_image_ != x.has_image_: return 0
    if self.has_image_ and self.image_ != x.image_: return 0
    return 1

  def __eq__(self, other):
    return (other is not None) and (other.__class__ == self.__class__) and self.Equals(other)

  def __ne__(self, other):
    return not (self == other)

  def IsInitialized(self, debug_strs=None):
    initialized = 1
    if (not self.has_image_):
      initialized = 0
      if debug_strs is not None:
        debug_strs.append('Required field: image not set.')
    elif not self.image_.IsInitialized(debug_strs): initialized = 0
    return initialized

  def ByteSize(self):
    n = 0
    n += self.lengthString(self.image_.ByteSize())
    return n + 1

  def Clear(self):
    self.clear_image()

  def OutputUnchecked(self, out):
    out.putVarInt32(10)
    out.putVarInt32(self.image_.ByteSize())
    self.image_.OutputUnchecked(out)

  def TryMerge(self, d):
    while d.avail() > 0:
      tt = d.getVarInt32()
      if tt == 10:
        length = d.getVarInt32()
        tmp = ProtocolBuffer.Decoder(d.buffer(), d.pos(), d.pos() + length)
        d.skip(length)
        self.mutable_image().TryMerge(tmp)
        continue
      if (tt == 0): raise ProtocolBuffer.ProtocolBufferDecodeError
      d.skipData(tt)


  def __str__(self, prefix="", printElemNumber=0):
    res=""
    if self.has_image_:
      res+=prefix+"image <\n"
      res+=self.image_.__str__(prefix + "  ", printElemNumber)
      res+=prefix+">\n"
    return res

  kimage = 1

  _TEXT = (
   "ErrorCode",
   "image",
  )

  _TYPES = (
   ProtocolBuffer.Encoder.NUMERIC,
   ProtocolBuffer.Encoder.STRING,

  )

  _STYLE = """"""
  _STYLE_CONTENT_TYPE = """"""

__all__ = ['ImagesServiceError','ImagesServiceTransform','Transform','ImageData','OutputSettings','ImagesTransformRequest','ImagesTransformResponse']
