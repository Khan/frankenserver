# Copyright (c) 2010-2018 Benjamin Peterson
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Subset of six-style functionality needed to port shared apphosting code."""

from __future__ import absolute_import
import sys
import types

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

# pylint: disable=invalid-name
if PY3:
  string_types = str,
  integer_types = int,
  text_type = str
  binary_type = bytes
  class_types = type,

  def is_basestring(t):
    """Return true if t is (referentially) the abstract basestring."""
    del t
    return False

else:
  string_types = basestring,
  integer_types = (int, long)
  text_type = unicode
  binary_type = str
  class_types = (type, types.ClassType)

  def is_basestring(t):
    """Return true if t is (referentially) the abstract basestring."""
    return t is basestring


def with_metaclass(meta, *bases):
  """Create a base class with a metaclass."""

  class metaclass(type):

    def __new__(mcs, name, this_bases, d):
      del this_bases
      return meta(name, bases, d)

    @classmethod
    def __prepare__(mcs, name, this_bases):
      del this_bases
      return meta.__prepare__(name, bases)
  return type.__new__(metaclass, 'temporary_class', (), {})


def ensure_binary(s, encoding='utf-8', errors='strict'):
  """Coerce **s** to six.binary_type.
  For Python 2:
    - `unicode` -> encoded to `str`
    - `str` -> `str`
  For Python 3:
    - `str` -> encoded to `bytes`
    - `bytes` -> `bytes`
  """
  if isinstance(s, text_type):
    return s.encode(encoding, errors)
  elif isinstance(s, binary_type):
    return s
  else:
    raise TypeError("not expecting type '%s'" % type(s))

