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





import inspect
import sys

def CreateRPC(service):
  """Creates a RPC instance for the given service.

  The instance is suitable for talking to remote services.
  Each RPC instance can be used only once, and should not be reused.

  Args:
    service: string representing which service to call.

  Returns:
    the rpc object.

  Raises:
    AssertionError or RuntimeError if the stub for service doesn't supply a
    CreateRPC method.
  """
  stub = apiproxy.GetStub(service)
  assert stub, 'No api proxy found for service "%s"' % service
  assert hasattr(stub, 'CreateRPC'), ('The service "%s" doesn\'t have ' +
                                      'a CreateRPC method.' % service)
  return stub.CreateRPC()


def MakeSyncCall(service, call, request, response):
  """The APIProxy entry point for a synchronous API call.

  Args:
    service: string representing which service to call
    call: string representing which function to call
    request: protocol buffer for the request
    response: protocol buffer for the response

  Raises:
    apiproxy_errors.Error or a subclass.
  """
  apiproxy.MakeSyncCall(service, call, request, response)


class ListOfHooks(object):
  """An ordered collection of hooks for a particular API call.

  A hook is a function that has exactly the same signature as
  a service stub. It will be called before or after an api hook is
  executed, depending on whether this list is for precall of postcall hooks.
  Hooks can be used for debugging purposes (check certain
  pre- or postconditions on api calls) or to apply patches to protocol
  buffers before/after a call gets submitted.
  """

  def __init__(self):
    """Constructor."""

    self.__content = []

    self.__unique_keys = set()

  def __len__(self):
    """Returns the amount of elements in the collection."""
    return self.__content.__len__()

  def __Insert(self, index, key, function, service=None):
    """Appends a hook at a certain position in the list.

    Args:
      index: the index of where to insert the function
      key: a unique key (within the module) for this particular function.
        If something from the same module with the same key is already
        registered, nothing will be added.
      function: the hook to be added.
      service: optional argument that restricts the hook to a particular api

    Returns:
      True if the collection was modified.
    """
    unique_key = (key, inspect.getmodule(function))
    if unique_key in self.__unique_keys:
      return False
    self.__content.insert(index, (key, function, service))
    self.__unique_keys.add(unique_key)
    return True

  def Append(self, key, function, service=None):
    """Appends a hook at the end of the list.

    Args:
      key: a unique key (within the module) for this particular function.
        If something from the same module with the same key is already
        registered, nothing will be added.
      function: the hook to be added.
      service: optional argument that restricts the hook to a particular api

    Returns:
      True if the collection was modified.
    """
    return self.__Insert(len(self), key, function, service)

  def Push(self, key, function, service=None):
    """Inserts a hook at the beginning of the list.

    Args:
      key: a unique key (within the module) for this particular function.
        If something from the same module with the same key is already
        registered, nothing will be added.
      function: the hook to be added.
      service: optional argument that restricts the hook to a particular api

    Returns:
      True if the collection was modified.
    """
    return self.__Insert(0, key, function, service)

  def Clear(self):
    """Removes all hooks from the list (useful for unit tests)."""
    self.__content = []
    self.__unique_keys = set()

  def Call(self, service, call, request, response):
    """Invokes all hooks in this collection.

    Args:
      service: string representing which service to call
      call: string representing which function to call
      request: protocol buffer for the request
      response: protocol buffer for the response
    """
    for key, function, srv in self.__content:
      if srv is None or srv == service:
        function(service, call, request, response)


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
    self.__precall_hooks = ListOfHooks()
    self.__postcall_hooks = ListOfHooks()

  def GetPreCallHooks(self):
    """Gets a collection for all precall hooks."""
    return self.__precall_hooks

  def GetPostCallHooks(self):
    """Gets a collection for all precall hooks."""
    return self.__postcall_hooks

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

  def MakeSyncCall(self, service, call, request, response):
    """The APIProxy entry point.

    Args:
      service: string representing which service to call
      call: string representing which function to call
      request: protocol buffer for the request
      response: protocol buffer for the response

    Raises:
      apiproxy_errors.Error or a subclass.
    """
    stub = self.GetStub(service)
    assert stub, 'No api proxy found for service "%s"' % service
    self.__precall_hooks.Call(service, call, request, response)
    stub.MakeSyncCall(service, call, request, response)
    self.__postcall_hooks.Call(service, call, request, response)


def GetDefaultAPIProxy():
  try:
    runtime = __import__('google.appengine.runtime', globals(), locals(),
                         ['apiproxy'])
    return APIProxyStubMap(runtime.apiproxy)
  except (AttributeError, ImportError):
    return APIProxyStubMap()

apiproxy = GetDefaultAPIProxy()
