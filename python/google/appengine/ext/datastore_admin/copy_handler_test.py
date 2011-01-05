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

"""Unit test for the copy handler."""


import os

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import capabilities
from google.appengine.api import datastore
from google.appengine.api import datastore_file_stub
from google.appengine.api.capabilities import capability_stub
from google.appengine.api.memcache import memcache_stub
from google.appengine.api.taskqueue import taskqueue_stub
from google.appengine.datastore import datastore_rpc
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext.datastore_admin import copy_handler
from google.appengine.ext.datastore_admin import remote_api_put_stub
from google.appengine.ext.datastore_admin import testutil
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.mapreduce import context
from google.appengine.ext.webapp import mock_webapp
from google.testing.pybase import googletest


class TestModel(db.Model):
  prop = db.StringProperty()


def key(*path, **kwargs):
  """Utility function for more concise key creation."""
  return db.Key.from_path(*path, **kwargs)


class TestBase(googletest.TestCase):
  """Test base to set up testing environment."""

  def setUp(self):
    self.stubs = googletest.StubOutForTesting()


    self.app_id = 'test_app'
    os.environ['APPLICATION_ID'] = self.app_id
    os.environ['AUTH_DOMAIN'] = 'gmail.com'
    apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()

    self.datastore = datastore_file_stub.DatastoreFileStub(
        self.app_id, '/dev/null', '/dev/null', trusted=True)
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', self.datastore)

    self.memcache = memcache_stub.MemcacheServiceStub()
    apiproxy_stub_map.apiproxy.RegisterStub('memcache', self.memcache)

    self.capabilities = capability_stub.CapabilityServiceStub()
    apiproxy_stub_map.apiproxy.RegisterStub('capability_service',
                                            self.capabilities)

  def tearDown(self):
    self.stubs.UnsetAll()


class AllocateMaxIdTest(TestBase):
  """Tests for AllocateMaxIdPool and AllocateMaxId classes."""

  def setUp(self):
    super(AllocateMaxIdTest, self).setUp()
    self.pool = copy_handler.AllocateMaxIdPool(self.app_id)
    self.allocated_id_ranges = []
    self.stubs.Set(db, 'allocate_id_range',
                   self.MockAllocateIdRange)

  def MockAllocateIdRange(self, akey, start, end):
    self.allocated_id_ranges.append((akey, start, end))

  def testPoolInit(self):
    """Test pool constructor."""
    self.assertEqual({}, self.pool.key_path_to_max_id)
    self.assertEqual(self.app_id, self.pool.app_id)

  def testRootEntity(self):
    """Test handling of root entities."""
    self.pool.allocate_max_id(key('TestEntity', 30))
    self.pool.allocate_max_id(key('TestEntity', 25))

    self.assertEqual(
        {('TestEntity', 1): 30,
        },
        self.pool.key_path_to_max_id)

    self.pool.allocate_max_id(key('TestEntity', 60))
    self.assertEqual(
        {('TestEntity', 1): 60,
        },
        self.pool.key_path_to_max_id)

    self.pool.allocate_max_id(key('Foo', 3))
    self.assertEqual(
        {('Foo', 1): 3,
         ('TestEntity', 1): 60,
        },
        self.pool.key_path_to_max_id)

  def testChildEntity(self):
    """Test handling of child entities."""
    self.pool.allocate_max_id(key('TestEntity', 20, 'TestChild', 34))
    self.assertEqual(
        {('TestEntity', 20,   'Foo', 1): 34,
        },
        self.pool.key_path_to_max_id)

    self.pool.allocate_max_id(key('TestEntity', 20, 'TestChild', 45))
    self.assertEqual(
        {('TestEntity', 20,   'Foo', 1): 45,
        },
        self.pool.key_path_to_max_id)

    self.pool.allocate_max_id(key('TestEntity', 20, 'TestChild', 56, 'A', 1))
    self.assertEqual(
        {('TestEntity', 20,   'Foo', 1): 56,
        },
        self.pool.key_path_to_max_id)

  def testFlush(self):
    """Test pool flushing."""
    self.pool.allocate_max_id(key('TestEntity', 30))
    self.pool.allocate_max_id(key('TestEntity', 20, 'TestChild', 34))

    self.pool.flush()
    self.assertEqual({}, self.pool.key_path_to_max_id)
    self.assertEqual(
        [(key(u'TestEntity', 20, u'Foo', 1, _app=u'test_app'), 1, 34),
         (key(u'TestEntity', 1, _app=u'test_app'), 1, 30),
        ],
        self.allocated_id_ranges)

  def testOp(self):
    """Test AllocateMaxId operation."""
    ctx = context.Context(None, None)
    copy_handler.AllocateMaxId(key('TestEntity', 30), self.app_id)(ctx)

    self.assertEqual(
        {('TestEntity', 1): 30,
        },
        ctx.get_pool('allocate_max_id_test_app_pool').key_path_to_max_id)

    ctx.flush()
    self.assertEqual(
        [(key(u'TestEntity', 1, _app=u'test_app'), 1, 30),
        ],
        self.allocated_id_ranges)


class CopyEntityTest(TestBase):
  """Tests CopyEntity map handler."""

  def setUp(self):
    super(CopyEntityTest, self).setUp()
    self.counters = {}
    self.puts = []
    self.configure_remote_puts = []
    self.mapper_params = {}
    self.allocated_ids = []
    self.stubs.Set(copy_handler.operation.counters, 'Increment',
                   self.MockIncrement)
    self.stubs.Set(copy_handler.operation.db, 'Put', self.MockPut)
    self.stubs.Set(copy_handler, 'get_mapper_params',
                   self.MockGetMapperParams)
    self.stubs.Set(copy_handler.remote_api_put_stub, 'configure_remote_put',
                   self.MockConfigureRemotePut)
    self.stubs.Set(copy_handler, 'AllocateMaxId', self.MockAllocateId)

  def MockIncrement(self, value):
    """Mock method for mapreduce.operation.counters.Increment."""
    self.counters[value] = self.counters.get(value, 0) + 1

  def MockPut(self, value):
    """Mock method for mapreduce.operation.counters.Increment."""
    self.puts.append(value)

  def MockGetMapperParams(self):
    """Return dummy mapreduce mapper params."""
    return self.mapper_params

  def MockConfigureRemotePut(self, remote_url, app_id, extra_headers):
    """Mock method to ensure configure remote put is called.

    We're intercepting the operation.db.Put, so no datastore put calls occur.
    """
    self.configure_remote_puts.append((remote_url, app_id, extra_headers))

  def MockAllocateId(self, key, app):
    """Mock method for copy_handler.AllocateMaxId."""
    self.allocated_ids.append((key, app))

  def testCopyEntity(self):
    """Basic test: Copy two entities."""
    model_instance = TestModel(prop='value_one')
    model_instance_two = TestModel(prop='value_two')
    db.put([model_instance, model_instance_two])

    target_app = 's~newapp'
    remote_url = 'http://remote_url/_ah/remote_api'
    self.mapper_params['target_app'] = target_app
    self.mapper_params['remote_url'] = remote_url

    copier = copy_handler.CopyEntity()
    list(copier.map(model_instance.key()))
    self.assertDictEqual({'TestModel': 1}, self.counters)
    expected_puts = [model_instance]
    self.assertEqual(1, len(self.puts))
    self.assertEqual(target_app, self.puts[0].app())
    self.assertDictEqual(model_instance._populate_entity(datastore.Entity),
                         self.puts[0])
    self.assertEqual(
        [(key('TestModel', 1, _app=self.app_id), target_app),
        ],
        self.allocated_ids)

    list(copier.map(model_instance_two.key()))
    self.assertDictEqual({'TestModel': 2}, self.counters)
    self.assertEqual(2, len(self.puts))
    self.assertEqual(target_app, self.puts[1].app())
    self.assertDictEqual(model_instance_two._populate_entity(datastore.Entity),
                         self.puts[1])
    self.assertEqual(
        [(key('TestModel', 1, _app=self.app_id), target_app),
         (key('TestModel', 2, _app=self.app_id), target_app),
        ],
        self.allocated_ids)
    self.assertEqual([(remote_url, target_app, {})],
                     self.configure_remote_puts)

  def testCopyEntityExtraHeader(self):
    """Test that extra header is passed through."""
    model_instance = TestModel(prop='value_one')
    db.put([model_instance])

    target_app = 's~newapp'
    remote_url = 'http://remote_url/_ah/remote_api'
    self.mapper_params['target_app'] = target_app
    self.mapper_params['remote_url'] = remote_url
    self.mapper_params['extra_header'] = 'Cookie:Authorization=Magic'

    copier = copy_handler.CopyEntity()
    list(copier.map(model_instance.key()))
    self.assertEqual([(remote_url, target_app,
                       {'Cookie': 'Authorization=Magic'})],
                     self.configure_remote_puts)
    self.assertDictEqual({'TestModel': 1}, self.counters)


class DoCopyHandlerTest(testutil.HandlerTestBase):
  """Test copy_handler.DoCopyHandler."""

  def setUp(self):
    testutil.HandlerTestBase.setUp(self)
    self.handler = copy_handler.DoCopyHandler()
    self.handler.initialize(mock_webapp.MockRequest(),
                            mock_webapp.MockResponse())

    self.handler.request.path = '/_ah/datastore_admin/%s' % (
        copy_handler.ConfirmCopyHandler.SUFFIX)

    self.app_id = 'test_app'
    self.target_app_id = 'test_app_target'
    self.remote_url = 'http://test_app_target.appspot.com/_ah/remote_api'

    os.environ['APPLICATION_ID'] = self.app_id
    ds_stub = datastore_file_stub.DatastoreFileStub(
        'test_app', '/dev/null', '/dev/null', trusted=True)
    self.memcache = memcache_stub.MemcacheServiceStub()
    self.taskqueue = taskqueue_stub.TaskQueueServiceStub()

    self.stubs = googletest.StubOutForTesting()
    self.exceptions = []
    self.stubs.Set(copy_handler.DoCopyHandler, '_HandleException',
                   self.ExceptionTrapper)
    self.expected_extra_headers = None
    self.stubs.Set(copy_handler.remote_api_put_stub, 'get_remote_appid',
                   self.MockGetRemoteAppid)

    apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', ds_stub)
    apiproxy_stub_map.apiproxy.RegisterStub("memcache", self.memcache)
    apiproxy_stub_map.apiproxy.RegisterStub("taskqueue", self.taskqueue)

  def tearDown(self):
    self.stubs.UnsetAll()

  def ExceptionTrapper(self, e):
    """Track exceptions raised through _HandleException."""
    self.exceptions.append(e)
    return str(e)

  def MockGetRemoteAppid(self, remote_url, extra_headers):
    if remote_url != self.remote_url:
      raise remote_api_put_stub.FetchFailed('unexpected url: %s' % remote_url)
    elif extra_headers != self.expected_extra_headers:
      raise remote_api_put_stub.FetchFailed('unexpected headers: %s' %
                                            extra_headers)
    return self.target_app_id

  def testJobCreation(self):
    """Verify that with appropriate request parameters job is kicked off."""
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', self.app_id)
    self.handler.request.set('remote_url', self.remote_url)
    self.handler.request.set('xsrf_token', utils.CreateXsrfToken('copy'))
    TestModel().put()
    self.handler.post()
    self.assertTaskStarted()
    self.assertEqual([], self.exceptions)
    self.assertEqual(302, self.handler.response.status)
    self.assertIn('http://foo.com/_ah/datastore_admin/copy.do?job=',
                  self.handler.response.headers.get('Location'))

  def testJobCreationExtraHeaders(self):
    """Verify that with appropriate request parameters job is kicked off.

    With an extra header (typically used for authentication).
    """
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', self.app_id)
    self.handler.request.set('remote_url', self.remote_url)
    self.handler.request.set('xsrf_token', utils.CreateXsrfToken('copy'))
    self.handler.request.set('extra_header', 'SecretHeader:LetMeIn')
    self.expected_extra_headers = {'SecretHeader': 'LetMeIn'}
    TestModel().put()
    self.handler.post()
    self.assertTaskStarted()
    self.assertEqual([], self.exceptions)
    self.assertEqual(302, self.handler.response.status)
    self.assertIn('http://foo.com/_ah/datastore_admin/copy.do?job=',
                  self.handler.response.headers.get('Location'))


  def testBadRequest(self):
    """Verify that nothing happens on a bad request."""
    self.handler.post()
    self.assertTaskNotStarted()
    self.assertEqual([], self.exceptions)
    self.assertEqual(302, self.handler.response.status)
    self.assertEqual('http://foo.com/_ah/datastore_admin/copy.do?'
                     'error=Unspecified+remote+URL.',
                     self.handler.response.headers.get('Location'))

  def testBadRemoteUrl(self):
    """Verify that nothing happens on a bad request."""
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', self.app_id)
    self.handler.request.set('remote_url', 'bogus remote url')
    self.handler.request.set('xsrf_token', utils.CreateXsrfToken('copy'))
    self.handler.post()
    self.assertTaskNotStarted()
    self.assertEqual(1, len(self.exceptions))
    self.assertEqual(302, self.handler.response.status)
    self.assertEqual('http://foo.com/_ah/datastore_admin/copy.do?'
                     'error=unexpected+url%3A+bogus+remote+url',
                     self.handler.response.headers.get('Location'))

  def testBadTokenValue(self):
    """Verify that nothing happens with a bad token value."""
    utils.CreateXsrfToken('delete')
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', self.app_id)
    self.handler.request.set('remote_url', self.remote_url)
    self.handler.request.set('xsrf_token', 'test-bad-token')
    self.handler.post()
    self.assertTaskNotStarted()
    self.assertEqual([], self.exceptions)
    self.assertEqual(302, self.handler.response.status)
    self.assertEqual('http://foo.com/_ah/datastore_admin/copy.do?'
                     'xsrf_error=1',
                     self.handler.response.headers.get('Location'))

  def testBadTokenType(self):
    """Verify that nothing happens with a bad token name."""
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', self.app_id)
    self.handler.request.set('remote_url', self.remote_url)
    self.handler.request.set('xsrf_token', utils.CreateXsrfToken('foobar'))
    self.handler.post()
    self.assertTaskNotStarted()
    self.assertEqual([], self.exceptions)
    self.assertEqual(302, self.handler.response.status)
    self.assertEqual('http://foo.com/_ah/datastore_admin/copy.do?'
                     'xsrf_error=1',
                     self.handler.response.headers.get('Location'))

  def testNoToken(self):
    """Verify that nothing happens with no token."""
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', self.app_id)
    self.handler.request.set('remote_url', self.remote_url)
    self.handler.post()
    self.assertTaskNotStarted()
    self.assertEqual([], self.exceptions)
    self.assertEqual(302, self.handler.response.status)
    self.assertEqual('http://foo.com/_ah/datastore_admin/copy.do?'
                     'xsrf_error=1',
                     self.handler.response.headers.get('Location'))

  def testPageRendering(self):
    """Verify that page renders on get request."""
    self.handler.request.set('job', ['12345'])
    self.handler.get()
    self.assertEqual(200, self.handler.response.status)
    self.assertIn('The following jobs were launched by MapReduce',
                  self.handler.response.out.getvalue())
    self.assertIn('12345',
                  self.handler.response.out.getvalue())
    self.assertNotIn('Some error.', self.handler.response.out.getvalue())
    self.assertNotIn('The token used to submit this form has expired',
                     self.handler.response.out.getvalue())

  def testPageRenderingWithError(self):
    """Verify that page renders on get request."""
    self.handler.request.set('error', 'Some error.')
    self.handler.get()
    self.assertEqual(200, self.handler.response.status)
    self.assertNotIn('The following jobs were launched by MapReduce',
                     self.handler.response.out.getvalue())
    self.assertIn('Some error.', self.handler.response.out.getvalue())
    self.assertNotIn('The token used to submit this form has expired',
                     self.handler.response.out.getvalue())

  def testPageRenderingWithXsrf(self):
    """Verify that page renders on get request."""
    self.handler.request.set('xsrf_error', '1')
    self.handler.get()
    self.assertEqual(200, self.handler.response.status)
    self.assertNotIn('The following jobs were launched by MapReduce',
                     self.handler.response.out.getvalue())
    self.assertNotIn('Some error.', self.handler.response.out.getvalue())
    self.assertIn('The token used to submit this form has expired',
                  self.handler.response.out.getvalue())


class ConfirmCopyHandlerTest(TestBase):
  """ConfirmCopyHandler test."""

  def setUp(self):
    TestBase.setUp(self)

    self.handler = copy_handler.ConfirmCopyHandler()
    self.request = mock_webapp.MockRequest()
    self.response = mock_webapp.MockResponse()
    self.handler.initialize(self.request, self.response)
    self.request.set('kind', 'Foo')

  def MockIsEnabledDisabled(self, request, response):
    """Disable everything in capabilities."""
    response.set_summary_status(capabilities.IsEnabledResponse.DISABLED)

    default_config = response.add_config()
    default_config.set_package('')
    default_config.set_capability('')
    default_config.set_status(capabilities.CapabilityConfig.DISABLED)

  def MockGetDatastoreType(self, app=None):
    """Say datastore is of HIGH_REPLICATION_DATASTORE type."""
    return datastore_rpc.Connection.HIGH_REPLICATION_DATASTORE

  def testPageRendering(self):
    self.handler.Render(self.handler)
    self.assertEqual(200, self.handler.response.status)
    self.assertIn('This application&rsquo;s data is writable. We can only',
                  self.handler.response.out.getvalue())
    self.assertNotIn('Note: Blobs (binary data) will not be copied.',
                     self.handler.response.out.getvalue())
    self.assertNotIn('This application is using a High Replication datastore.',
                     self.handler.response.out.getvalue())

  def testPageRenderingReadonlyApp(self):
    self.stubs.Set(self.capabilities, '_Dynamic_IsEnabled',
                   self.MockIsEnabledDisabled)

    self.handler.Render(self.handler)
    self.assertEqual(200, self.handler.response.status)
    self.assertNotIn(
        'This application&rsquo;s data is writable. We can only',
        self.handler.response.out.getvalue())

  def testPageRenderingBlobWarning(self):
    blob_info_entity = datastore.Entity(blobstore.blobstore.BlobInfo.kind(),
                                        name='blob-key')
    datastore.Put(blob_info_entity)
    self.handler.Render(self.handler)
    self.assertEqual(200, self.handler.response.status)
    self.assertIn('Note: Blobs (binary data) will not be copied.',
                  self.handler.response.out.getvalue())

  def testPageRenderingHRWarning(self):
    self.stubs.Set(datastore_rpc.BaseConnection, 'get_datastore_type',
                   self.MockGetDatastoreType)

    self.handler.Render(self.handler)
    self.assertEqual(200, self.handler.response.status)
    self.assertIn('This application is using a High Replication datastore.',
                  self.handler.response.out.getvalue())

if __name__ == '__main__':
  googletest.main()
