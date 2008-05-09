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

"""Container of APIProxy stubs for more convenient unittesting.

Classes/variables/functions defined here:
  APIProxyStubMap: container of APIProxy stubs.
  apiproxy: global instance of an APIProxyStubMap.
  MakeSyncCall: APIProxy entry point.
"""





import sys

def MakeSyncCall(service, call, request, response):
  """The APIProxy entry point.

  Args:
    service: string representing which service to call
    call: string representing which function to call
    request: protocol buffer for the request
    response: protocol buffer for the response

  Raises:
    apiproxy_errors.Error or a subclass.
  """
  stub = apiproxy.GetStub(service)
  assert stub, ("No api proxy found for service %s!"
                " Was a default api proxy provided?" % service)
  stub.MakeSyncCall(service, call, request, response)


class APIProxyStubMap:
  """Container of APIProxy stubs for more convenient unittesting.

  Stubs may be either trivial implementations of APIProxy services (e.g.
  DatastoreFileStub, UserServiceStub) or "real" implementations.

  For unittests, we may want to mix and match real and trivial implementations
  of services in order to better focus testing on individual service
  implementations. To achieve this, we allow the client to attach stubs to
  service names, as well as define a default stub to be used if no specific
  matching stub is identified.
  """


  def __init__(self, default_stub=None):
    """Constructor.

    Args:
      default_stub: optional stub

    'default_stub' will be used whenever no specific matching stub is found.
    """
    self.__stub_map = {}
    self.__default_stub = default_stub

  def RegisterStub(self, service, stub):
    """Register the provided stub for the specified service.

    Args:
      service: string
      stub: stub
    """
    assert not self.__stub_map.has_key(service)
    self.__stub_map[service] = stub

    if service == 'datastore':
      self.RegisterStub('datastore_v3', stub)

  def GetStub(self, service):
    """Retrieve the stub registered for the specified service.

    Args:
      service: string

    Returns:
      stub

    Returns the stub registered for 'service', and returns the default stub
    if no such stub is found.
    """
    return self.__stub_map.get(service, self.__default_stub)

def GetDefaultAPIProxy():
  try:
    runtime = __import__('google.appengine.runtime', globals(), locals(),
                         ['apiproxy'])
    return APIProxyStubMap(runtime.apiproxy)
  except (AttributeError, ImportError):
    return APIProxyStubMap()

apiproxy = GetDefaultAPIProxy()
