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

"""Unit test for the App Engine RPC-over-HTTP 'put only' stub."""


import pickle

import google
import mox

from google.testing.pybase import googletest
from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api import urlfetch
from google.appengine.datastore import datastore_pb
from google.appengine.ext import db
from google.appengine.ext.datastore_admin import remote_api_put_stub
from google.appengine.ext.remote_api import remote_api_pb


class MyModel(db.Model):
  prop = db.StringProperty()


class MockUrlfetchResult(object):
  """A mock Urlfetch result object."""

  def __init__(self, status_code, content):
    self.status_code = status_code
    self.content = content


class PutStubTest(googletest.TestCase):
  """Tests the App Engine RPC-over-HTTP interface."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mock_stub = self.mox.CreateMock(apiproxy_stub.APIProxyStub)
    self.mox.StubOutWithMock(remote_api_put_stub.urlfetch, 'fetch')
    self.remote_url = 'http://remoteapp.appspot.com/remote_api'
    self.stub = remote_api_put_stub.DatastorePutStub(
        self.remote_url, 'remoteapp', {'auth': 'good'}, self.mock_stub)

  def tearDown(self):
    try:
      self.mox.VerifyAll()
    finally:
      self.mox.UnsetStubs()

  def CreatePutRequest(self, appid):
    """Create a commonly used datastore Put request."""
    model_instance = MyModel(prop='cat', _app=appid)
    put_request = datastore_pb.PutRequest()
    put_request.add_entity().CopyFrom(db.model_to_protobuf(model_instance))
    return put_request

  def CreateAllocateIdsRequest(self, appid):
    """Create a commonly used datastore AllocateIds request."""
    key = db.Key.from_path('TestEntity', 1, _app=appid)
    request = datastore_pb.AllocateIdsRequest()
    request.mutable_model_key().CopyFrom(key._ToPb())
    return request

  def RemoteApiRequest(self, call, request):
    """Return a filled in remote_api request proto."""
    remote_request_pb = remote_api_pb.Request()
    remote_request_pb.set_service_name('datastore_v3')
    remote_request_pb.set_method(call)
    remote_request_pb.mutable_request().set_contents(request.Encode())
    return remote_request_pb

  def RemoteApiResponse(self, response):
    """Return a filled in remote_api response proto."""
    remote_response = remote_api_pb.Response()
    remote_response.mutable_response().set_contents(response.Encode())
    return remote_response

  def testNonsenseRequest(self):
    """Test that a request for a service other than the datastore fails."""
    request = api_base_pb.Integer32Proto()
    request.set_value(20)
    response = api_base_pb.Integer32Proto()

    self.assertRaises(AssertionError, self.stub.MakeSyncCall,
                      'testservice', 'timestwo', request, response)

  def testLocalGetRequest(self):
    """A request for Get should always pass through."""
    local_key = db.Key.from_path('MyModel', 'Name1', _app='localapp')
    get_request = datastore_pb.GetRequest()
    get_request.add_key().CopyFrom(local_key._ToPb())
    get_response = datastore_pb.GetResponse()
    self.mock_stub.MakeSyncCall('datastore_v3', 'Get', get_request,
                                get_response)
    self.mox.ReplayAll()

    self.stub.MakeSyncCall('datastore_v3', 'Get', get_request, get_response)

  def testRemoteGetRequest(self):
    """A request for Get should always pass through."""
    remote_key = db.Key.from_path('MyModel', 'Name1', _app='remoteapp')
    get_request = datastore_pb.GetRequest()
    get_request.add_key().CopyFrom(remote_key._ToPb())
    get_response = datastore_pb.GetResponse()
    self.mock_stub.MakeSyncCall('datastore_v3', 'Get', get_request,
                                get_response)
    self.mox.ReplayAll()

    self.stub.MakeSyncCall('datastore_v3', 'Get', get_request, get_response)

  def testLocalPutRequest(self):
    """A request for Put should go local or remote depending on the key."""
    put_request = self.CreatePutRequest('localapp')
    put_response = datastore_pb.PutResponse()
    self.mock_stub.MakeSyncCall('datastore_v3', 'Put', put_request,
                                put_response)
    self.mox.ReplayAll()

    self.stub.MakeSyncCall('datastore_v3', 'Put', put_request, put_response)

  def testRemotePutRequest(self):
    """A request for Put should go local or remote depending on the key."""
    put_request = self.CreatePutRequest('remoteapp')
    put_response = datastore_pb.PutResponse()

    key = db.Key.from_path('MyModel', 1, _app='remoteapp')
    expected_put_response = datastore_pb.PutResponse()
    expected_put_response.add_key().CopyFrom(key._ToPb())

    expected_post = self.RemoteApiRequest('Put', put_request).Encode()
    expected_response = self.RemoteApiResponse(
        expected_put_response).Encode()

    remote_api_put_stub.urlfetch.fetch(
        self.remote_url, expected_post, urlfetch.POST,
        {'X-appcfg-api-version': '1', 'auth': 'good'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(200, expected_response))

    self.mox.ReplayAll()

    self.stub.MakeSyncCall('datastore_v3', 'Put', put_request, put_response)
    self.assertEqual(put_response, expected_put_response)

  def testRemotePutTransactionRequest(self):
    """A remote transactional PUT should fail."""
    put_request = self.CreatePutRequest('remoteapp')
    put_request.mutable_transaction().set_app('remoteapp')
    put_request.mutable_transaction().set_handle(123)
    put_response = datastore_pb.PutResponse()

    self.assertRaises(remote_api_put_stub.RemoteTransactionsUnimplemented,
                      self.stub.MakeSyncCall, 'datastore_v3', 'Put',
                      put_request, put_response)

  def testRemoteMultiPutRequest(self):
    """A request for Put should go local or remote depending on the key."""
    put_request = self.CreatePutRequest('remoteapp')
    put_request.add_entity().CopyFrom(put_request.entity(0))
    put_response = datastore_pb.PutResponse()

    key1 = db.Key.from_path('MyModel', 1, _app='localapp')
    key2 = db.Key.from_path('MyModel', 2, _app='localapp')
    expected_put_response = datastore_pb.PutResponse()
    expected_put_response.add_key().CopyFrom(key1._ToPb())
    expected_put_response.add_key().CopyFrom(key2._ToPb())

    expected_post = self.RemoteApiRequest('Put', put_request).Encode()
    expected_response = self.RemoteApiResponse(expected_put_response).Encode()

    remote_api_put_stub.urlfetch.fetch(
        self.remote_url, expected_post, urlfetch.POST,
        {'X-appcfg-api-version': '1', 'auth': 'good'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(200, expected_response))

    self.mox.ReplayAll()

    self.stub.MakeSyncCall('datastore_v3', 'Put', put_request, put_response)
    self.assertEqual(put_response, expected_put_response)

  def testRemotePutRequestUnauthorized(self):
    """A remote put with a 'bad' urlfetch response."""
    put_request = self.CreatePutRequest('remoteapp')
    put_response = datastore_pb.PutResponse()

    expected_post = self.RemoteApiRequest('Put', put_request).Encode()

    remote_api_put_stub.urlfetch.fetch(
        self.remote_url, expected_post, urlfetch.POST,
        {'X-appcfg-api-version': '1', 'auth': 'good'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(403, 'not authorized'))

    self.mox.ReplayAll()

    self.assertRaises(remote_api_put_stub.FetchFailed, self.stub.MakeSyncCall,
                      'datastore_v3', 'Put', put_request, put_response)

  def testRemotePutRemoteException(self):
    """Test that a remote exception is bubbled back up."""
    put_request = self.CreatePutRequest('remoteapp')
    put_response = datastore_pb.PutResponse()

    expected_post = self.RemoteApiRequest('Put', put_request).Encode()
    expected_exception = db.Timeout('too slow')
    remote_response = remote_api_pb.Response()
    remote_response.mutable_exception().set_contents(
        pickle.dumps(expected_exception))
    expected_response = remote_response.Encode()

    remote_api_put_stub.urlfetch.fetch(
        self.remote_url, expected_post, urlfetch.POST,
        {'X-appcfg-api-version': '1', 'auth': 'good'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(200, expected_response))

    self.mox.ReplayAll()

    self.assertRaises(db.Timeout, self.stub.MakeSyncCall,
                      'datastore_v3', 'Put', put_request, put_response)

  def testLocalAllocateIds(self):
    """AllocateIds request should go local or remote depending on the key."""
    request = self.CreateAllocateIdsRequest('localapp')
    response = datastore_pb.AllocateIdsResponse()
    response.set_start(1)
    response.set_end(2)

    self.mock_stub.MakeSyncCall('datastore_v3', 'AllocateIds', request,
                                response)
    self.mox.ReplayAll()
    self.stub.MakeSyncCall('datastore_v3', 'AllocateIds', request, response)

  def testRemoteAllocateIds(self):
    """AllocateIds request should go local or remote depending on the key."""
    request = self.CreateAllocateIdsRequest('remoteapp')
    response = datastore_pb.AllocateIdsResponse()
    response.set_start(1)
    response.set_end(2)

    expected_post = self.RemoteApiRequest('AllocateIds', request).Encode()
    expected_response = self.RemoteApiResponse(response).Encode()

    remote_api_put_stub.urlfetch.fetch(
        self.remote_url, expected_post, urlfetch.POST,
        {'X-appcfg-api-version': '1', 'auth': 'good'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(200, expected_response))

    self.mox.ReplayAll()
    self.stub.MakeSyncCall('datastore_v3', 'AllocateIds', request, response)


class ConfigurationTest(googletest.TestCase):
  """Tests the configuration methods."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(remote_api_put_stub.urlfetch, 'fetch')
    self.mox.StubOutWithMock(remote_api_put_stub.random, 'random')
    self.remote_url = 'http://remoteapp.appspot.com/remote_api'
    self.app_id = 'remoteapp'
    self.rtok = '12345'

  def tearDown(self):
    try:
      self.mox.VerifyAll()
    finally:
      self.mox.UnsetStubs()


  def testGetAppid(self):
    """Sueccessfully get an appid."""
    remote_api_put_stub.random.random().AndReturn(float('0.%s' % self.rtok))
    response = "{app_id: %s, rtok: !!python/unicode '%s'}" % (
        self.app_id, self.rtok)
    remote_api_put_stub.urlfetch.fetch(
        self.remote_url + '?rtok=%s' % self.rtok, None, urlfetch.GET,
        {'X-appcfg-api-version': '1'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(200, response))
    self.mox.ReplayAll()
    self.assertEqual(self.app_id,
                     remote_api_put_stub.get_remote_appid(self.remote_url, {}))

  def testGetAppidAuthDenied(self):
    """Remote server returns denied."""
    remote_api_put_stub.random.random().AndReturn(float('0.%s' % self.rtok))
    remote_api_put_stub.urlfetch.fetch(
        self.remote_url + '?rtok=%s' % self.rtok, None, urlfetch.GET,
        {'X-appcfg-api-version': '1'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(403, 'not authorized'))
    self.mox.ReplayAll()
    self.assertRaises(remote_api_put_stub.FetchFailed,
                      remote_api_put_stub.get_remote_appid,
                      self.remote_url, {})

  def testGetAppidUrlfetchFail(self):
    """Urlfetch fails."""
    remote_api_put_stub.random.random().AndReturn(float('0.%s' % self.rtok))
    remote_api_put_stub.urlfetch.fetch(
        self.remote_url + '?rtok=%s' % self.rtok, None, urlfetch.GET,
        {'X-appcfg-api-version': '1'}, follow_redirects=False
        ).AndRaise(urlfetch.Error)
    self.mox.ReplayAll()
    self.assertRaises(remote_api_put_stub.FetchFailed,
                      remote_api_put_stub.get_remote_appid,
                      self.remote_url, {})


  def testGetAppidBogusResult(self):
    """Remote server returns nonsense."""
    remote_api_put_stub.random.random().AndReturn(float('0.%s' % self.rtok))
    remote_api_put_stub.urlfetch.fetch(
        self.remote_url + '?rtok=%s' % self.rtok, None, urlfetch.GET,
        {'X-appcfg-api-version': '1'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(200, "Hello World"))
    self.mox.ReplayAll()
    self.assertRaises(remote_api_put_stub.ConfigurationError,
                      remote_api_put_stub.get_remote_appid,
                      self.remote_url, {})

  def testGetAppidBogusBadRtok(self):
    """Remote server returns bad token."""
    response = "{app_id: %s, rtok: !!python/unicode '%s'}" % (
        self.app_id, 'badtoken')
    remote_api_put_stub.random.random().AndReturn(float('0.%s' % self.rtok))
    remote_api_put_stub.urlfetch.fetch(
        self.remote_url + '?rtok=%s' % self.rtok, None, urlfetch.GET,
        {'X-appcfg-api-version': '1'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(200, response))
    self.mox.ReplayAll()
    self.assertRaises(remote_api_put_stub.ConfigurationError,
                      remote_api_put_stub.get_remote_appid,
                      self.remote_url, {})

  def testGetAppidNotQuiteYaml(self):
    """Remote server returns other nonsense."""
    response = "{curly braces are curly}"
    remote_api_put_stub.random.random().AndReturn(float('0.%s' % self.rtok))
    remote_api_put_stub.urlfetch.fetch(
        self.remote_url + '?rtok=%s' % self.rtok, None, urlfetch.GET,
        {'X-appcfg-api-version': '1'}, follow_redirects=False
        ).AndReturn(MockUrlfetchResult(200, response))
    self.mox.ReplayAll()
    self.assertRaises(remote_api_put_stub.ConfigurationError,
                      remote_api_put_stub.get_remote_appid,
                      self.remote_url, {})



if __name__ == '__main__':
  googletest.main()
