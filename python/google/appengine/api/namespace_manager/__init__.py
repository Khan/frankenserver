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

"""Control the namespacing system used by various APIs.

Each API call can specify an alternate namespace, but the functions
here can be used to change the default namespace. The default is set
before user code begins executing.
"""



import os

ENV_DEFAULT_NAMESPACE = 'HTTP_X_APPENGINE_DEFAULT_NAMESPACE'
ENV_CURRENT_NAMESPACE = '__INTERNAL_CURRENT_NAMESPACE'


def set_request_namespace(namespace):
  """Set the default namespace to use for future calls, for this request only.

  Args:
    namespace: A string naming the new namespace to use. The empty
      string specifies the root namespace for this app.
  """
  os.environ[ENV_CURRENT_NAMESPACE] = namespace


def get_request_namespace():
  """Get the name of the current default namespace.

  The empty string indicates that the root namespace is the default.
  """
  return os.getenv(ENV_CURRENT_NAMESPACE, '')


def _enable_request_namespace():
  """Automatically enable namespace to default for domain.

  Calling this function will automatically default the namespace to the
  chosen Google Apps domain for the current request.
  """
  if ENV_CURRENT_NAMESPACE not in os.environ:
    if ENV_DEFAULT_NAMESPACE in os.environ:
      os.environ[ENV_CURRENT_NAMESPACE] = os.environ[ENV_DEFAULT_NAMESPACE]
    else:
      os.environ[ENV_CURRENT_NAMESPACE] = ''


def _add_name_space(request, namespace=None):
  """Add a name_space field to a request.

  Args:
    request: A protocol buffer supporting the set_name_space() operation.
    namespace: The name of the namespace part. If None, use the
      default namespace.
  """
  if namespace is None:
    request.set_name_space(get_request_namespace())
  else:
    request.set_name_space(namespace)
