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

"""Makes API calls to various Google-provided services.

Provides methods for making calls into Google Apphosting services and APIs
from your application code. This code will only work properly from within
the Google Apphosting environment.
"""


import sys
from google.net.proto import ProtocolBuffer
from google.appengine import runtime
from google.appengine.runtime import apiproxy_errors
from google3.apphosting.runtime import _apphosting_runtime___python__apiproxy

OK                =  0
RPC_FAILED        =  1
CALL_NOT_FOUND    =  2
ARGUMENT_ERROR    =  3
DEADLINE_EXCEEDED =  4
CANCELLED         =  5
APPLICATION_ERROR =  6
OTHER_ERROR       =  7
OVER_QUOTA        =  8
REQUEST_TOO_LARGE =  9
CAPABILITY_DISABLED = 10

_ExceptionsMap = {
  RPC_FAILED:
  (apiproxy_errors.RPCFailedError,
   "The remote RPC to the application server failed for the call %s.%s()."),
  CALL_NOT_FOUND:
  (apiproxy_errors.CallNotFoundError,
   "The API package '%s' or call '%s()' was not found."),
  ARGUMENT_ERROR:
  (apiproxy_errors.ArgumentError,
   "An error occurred parsing (locally or remotely) the arguments to %s.%s()."),
  DEADLINE_EXCEEDED:
  (apiproxy_errors.DeadlineExceededError,
   "The API call %s.%s() took too long to respond and was cancelled."),
  CANCELLED:
  (apiproxy_errors.CancelledError,
   "The API call %s.%s() was explicitly cancelled."),
  OTHER_ERROR:
  (apiproxy_errors.Error,
   "An error occurred for the API request %s.%s()."),
  OVER_QUOTA:
  (apiproxy_errors.OverQuotaError,
  "The API call %s.%s() required more quota than is available."),
  REQUEST_TOO_LARGE:
  (apiproxy_errors.RequestTooLargeError,
  "The request to API call %s.%s() was too large."),






}

class RPC(object):
  """A RPC object, suitable for talking to remote services.

  Each instance of this object can be used only once, and should not be reused.

  Stores the data members and methods for making RPC calls via the APIProxy.
  """

  IDLE = 0
  RUNNING = 1
  FINISHING = 2

  def __init__(self, package=None, call=None, request=None, response=None,
               callback=None):
    """Constructor for the RPC object. All arguments are optional, and
    simply set members on the class. These data members will be
    overriden by values passed to MakeCall.

    Args:
      package: string, the package for the call
      call: string, the call within the package
      request: ProtocolMessage instance, appropriate for the arguments
      response: ProtocolMessage instance, appropriate for the response
      callback: callable, called when call is complete
    """
    self.__exception = None
    self.__traceback = None
    self.__result_dict = {}
    self.__state = RPC.IDLE

    self.package = package
    self.call = call
    self.request = request
    self.response = response
    self.callback = callback


  def MakeCall(self, package=None, call=None, request=None, response=None,
               callback=None):
    """Makes an asynchronous (i.e. non-blocking) API call within the
    specified package for the specified call method. request and response must
    be the appropriately typed ProtocolBuffers for the API call.
    callback, if provided, will be called when the request completes
    successfully or when an error occurs.  If an error has ocurred, the
    exception() method on this class will return the error, which can be
    accessed from the callback.

    Args:
      Same as constructor; see __init__.

    Raises:
      TypeError or AssertionError if an argument is of an invalid type.
      AssertionError or RuntimeError is an RPC is already in use.
    """
    self.callback = callback or self.callback
    self.package = package or self.package
    self.call = call or self.call
    self.request = request or self.request
    self.response = response or self.response

    assert self.__state is RPC.IDLE, ("RPC for %s.%s has already been started" %
                                      (self.package, self.call))
    assert self.callback is None or callable(self.callback)
    assert isinstance(self.request, ProtocolBuffer.ProtocolMessage)
    assert isinstance(self.response, ProtocolBuffer.ProtocolMessage)

    e = ProtocolBuffer.Encoder()
    self.request.Output(e)

    self.__state = RPC.RUNNING
    _apphosting_runtime___python__apiproxy.MakeCall(
        self.package, self.call, e.buffer(), self.__result_dict,
        self.__MakeCallDone, self)

  def Wait(self):
    """Waits on the API call associated with this RPC. The callback,
    if provided, will be executed before Wait() returns. If this RPC
    is already complete, or if the RPC was never started, this
    function will return immediately.

    Raises:
      InterruptedError if a callback throws an uncaught exception.
    """
    try:
      rpc_completed = _apphosting_runtime___python__apiproxy.Wait(self)
    except runtime.DeadlineExceededError:
      raise
    except apiproxy_errors.InterruptedError:
      raise
    except:
      exc_class, exc, tb = sys.exc_info()
      if (isinstance(exc, SystemError) and
          exc.args == ('uncaught RPC exception',)):
        raise
      rpc = None
      if hasattr(exc, "_appengine_apiproxy_rpc"):
        rpc = exc._appengine_apiproxy_rpc
      new_exc = apiproxy_errors.InterruptedError(exc, rpc)
      raise new_exc.__class__, new_exc, tb

    assert rpc_completed, ("RPC for %s.%s was not completed, and no other " +
                           "exception was raised " % (self.package, self.call))

  def CheckSuccess(self):
    """If there was an exception, raise it now.

    Raises:
      Exception of the API call or the callback, if any.
    """
    if self.exception and self.__traceback:
      raise self.exception.__class__, self.exception, self.__traceback
    if self.exception:
      raise self.exception

  @property
  def exception(self):
    return self.__exception

  @property
  def state(self):
    return self.__state

  def __MakeCallDone(self):
    self.__state = RPC.FINISHING
    if self.__result_dict['error'] == APPLICATION_ERROR:
      self.__exception = apiproxy_errors.ApplicationError(
          self.__result_dict['application_error'],
          self.__result_dict['error_detail'])
    elif self.__result_dict['error'] == CAPABILITY_DISABLED:
      if self.__result_dict['error_detail']:
        self.__exception = apiproxy_errors.CapabilityDisabledError(
            self.__result_dict['error_detail'])
      else:
        self.__exception = apiproxy_errors.CapabilityDisabledError(
            "The API call %s.%s() is temporarily unavailable." % (
            self.package, self.call))
    elif _ExceptionsMap.has_key(self.__result_dict['error']):
      exception_entry = _ExceptionsMap[self.__result_dict['error']]
      self.__exception = exception_entry[0](
          exception_entry[1] % (self.package, self.call))
    else:
      try:
        self.response.ParseFromString(self.__result_dict['result_string'])
      except Exception, e:
        self.__exception = e
    if self.callback:
      try:
        self.callback()
      except:
        exc_class, self.__exception, self.__traceback = sys.exc_info()
        self.__exception._appengine_apiproxy_rpc = self
        raise


def MakeSyncCall(package, call, request, response):
  """Makes a synchronous (i.e. blocking) API call within the specified
  package for the specified call method. request and response must be the
  appropriately typed ProtocolBuffers for the API call. An exception is
  thrown if an error occurs when communicating with the system.

  Args:
    See MakeCall above.

  Raises:
    See CheckSuccess() above.
  """
  rpc = RPC()
  rpc.MakeCall(package, call, request, response)
  rpc.Wait()
  rpc.CheckSuccess()
