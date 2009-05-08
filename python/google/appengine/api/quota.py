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

"""Access to quota usage for this application."""




try:
  from google3.apphosting.runtime import _apphosting_runtime___python__apiproxy
except ImportError:
  _apphosting_runtime___python__apiproxy = None

def get_request_cpu_usage():
  """Get the amount of CPU used so far for the current request.

  Returns the number of megacycles used so far for the current
  request. Does not include CPU used by API calls.

  Does nothing when used in the dev_appserver.
  """

  if _apphosting_runtime___python__apiproxy:
    return _apphosting_runtime___python__apiproxy.get_request_cpu_usage()
  return 0
