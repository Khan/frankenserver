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




"""PageSpeed configuration tools.

Library for parsing pagespeed.yaml files and working with these in memory.
"""







import google

from google.appengine.api import validation
from google.appengine.api import yaml_builder
from google.appengine.api import yaml_listener
from google.appengine.api import yaml_object

_URL_BLACKLIST_REGEX = r'http(s)?://\S{0,499}'
_REWRITER_NAME_REGEX = r'[a-zA-Z0-9_]+'

URL_BLACKLIST = 'url_blacklist'
ENABLED_REWRITERS = 'enabled_rewriters'
DISABLED_REWRITERS = 'disabled_rewriters'


class MalformedPagespeedConfiguration(Exception):
  """Configuration file for PageSpeed API is malformed."""






class PagespeedInfoExternal(validation.Validated):
  """Describes the format of a pagespeed.yaml file.

  URL blacklist entries are patterns (with '?' and '*' as wildcards).  Any URLs
  that match a pattern on the blacklist will not be optimized by PageSpeed.

  Rewriter names are strings (like 'CombineCss' or 'RemoveComments') describing
  individual PageSpeed rewriters.  A full list of valid rewriter names can be
  found in the PageSpeed documentation.
  """
  ATTRIBUTES = {
      URL_BLACKLIST: validation.Optional(
          validation.Repeated(validation.Regex(_URL_BLACKLIST_REGEX))),
      ENABLED_REWRITERS: validation.Optional(
          validation.Repeated(validation.Regex(_REWRITER_NAME_REGEX))),
      DISABLED_REWRITERS: validation.Optional(
          validation.Repeated(validation.Regex(_REWRITER_NAME_REGEX))),
  }


def LoadSinglePagespeed(pagespeed_info, open_fn=None):
  """Load a pagespeed.yaml file or string and return a PagespeedInfoExternal.

  Args:
    pagespeed_info: The contents of a pagespeed.yaml file as a string, or an
      open file object.
    open_fn: Function for opening files. Unused.

  Returns:
    A PagespeedInfoExternal instance which represents the contents of the parsed
    yaml file.

  Raises:
    yaml_errors.EventError: An error occured while parsing the yaml file.
    MalformedPagespeedConfiguration: The configuration is parseable but invalid.
  """
  builder = yaml_object.ObjectBuilder(PagespeedInfoExternal)
  handler = yaml_builder.BuilderHandler(builder)
  listener = yaml_listener.EventListener(handler)
  listener.Parse(pagespeed_info)

  parsed_yaml = handler.GetResults()
  if not parsed_yaml:
    return PagespeedInfoExternal()

  if len(parsed_yaml) > 1:
    raise MalformedPagespeedConfiguration(
        'Multiple configuration sections in pagespeed.yaml')

  return parsed_yaml[0]
