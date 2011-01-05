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

"""Tests for google.appengine.ext.mapreduce.datastore_admin."""


from google.testing.pybase import googletest
from google.appengine.api import datastore
from google.appengine.ext import db
from google.appengine.ext.datastore_admin import delete_handler
from google.appengine.ext.datastore_admin import testutil
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import operation
from google.appengine.ext.webapp import mock_webapp


APP_ID = 'testapp'


class TestModel(db.Model):
  """Test model class."""


class TestEntity(datastore.Entity):
  """Test entity class."""


class ConfirmDeleteHandlerTest(testutil.HandlerTestBase):
  """Test delete_handler.ConfirmDeleteHandler."""

  def setUp(self):
    """Sets up the test harness."""
    testutil.HandlerTestBase.setUp(self)
    self.handler = delete_handler.ConfirmDeleteHandler()
    self.handler.initialize(mock_webapp.MockRequest(),
                            mock_webapp.MockResponse())

    self.handler.request.path = '/_ah/datastore_admin/%s' % (
        delete_handler.ConfirmDeleteHandler.SUFFIX)

  def testFormCreationWithParams(self):
    """Verify that with appropriate request parameters form is constructed."""
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', APP_ID)
    self.handler.get()

  def testFormCreationWithoutParams(self):
    """Verify that with appropriate request parameters form is constructed."""
    self.handler.get()

  def testWithSomeSizesAvailable(self):
    """Verify with sizes available."""
    self.handler.request.set('kind', ['test1', 'test2'])
    utils.CacheStats([{'kind_name': 'test1', 'total_bytes': 2},
                      {'kind_name': 'test3', 'total_bytes': 8},
                     ])
    self.handler.get()

  def testWithNoSizesAvailable(self):
    """Verify with sizes available."""
    self.handler.request.set('kind', ['test1', 'test2'])
    self.handler.get()

  def testWithSizesAvailable(self):
    """Verify with sizes available."""
    self.handler.request.set('kind', ['test1', 'test2'])
    utils.CacheStats([{'kind_name': 'test1', 'total_bytes': 2},
                      {'kind_name': 'test2', 'total_bytes': 4},
                      {'kind_name': 'test3', 'total_bytes': 8},
                     ])
    self.handler.get()


class DoDeleteHandlerTest(testutil.HandlerTestBase):
  """Test delete_handler.DoDeleteHandler."""

  def FailOnException(self, e):
    raise e

  def setUp(self):
    """Sets up the test harness."""
    testutil.HandlerTestBase.setUp(self)
    self.handler = delete_handler.DoDeleteHandler()
    self.handler._handle_exception = self.FailOnException
    self.handler.initialize(mock_webapp.MockRequest(),
                            mock_webapp.MockResponse())

    self.handler.request.path = '/_ah/datastore_admin/%s' % (
        delete_handler.DoDeleteHandler.SUFFIX)

  def testJobCreation(self):
    """Verify that with appropriate request parameters job is kicked off."""
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', APP_ID)
    self.handler.request.set('xsrf_token', utils.CreateXsrfToken('delete'))
    TestModel(_app=APP_ID).put()
    self.handler.post()
    self.assertTaskStarted()

  def testBadRequest(self):
    """Verify that nothing happens on a bad request."""
    self.handler.post()
    self.assertTaskNotStarted()

  def testBadTokenName(self):
    """Verify that nothing happens with a bad token name."""
    utils.CreateXsrfToken('delete')
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', APP_ID)
    self.handler.request.set('xsrf_token', 'test-bad-token')
    self.handler.post()
    self.assertTaskNotStarted()

  def testBadTokenType(self):
    """Verify that nothing happens with a bad token name."""
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', APP_ID)
    self.handler.request.set('xsrf_token', utils.CreateXsrfToken('foobar'))
    self.handler.post()
    self.assertTaskNotStarted()

  def testNoToken(self):
    """Verify that nothing happens with no token."""
    self.handler.request.set('kind', [(__name__ + '.' + TestModel.__name__)])
    self.handler.request.set('namespace', '')
    self.handler.request.set('app_id', APP_ID)
    self.handler.post()
    self.assertTaskNotStarted()

  def testPageRendering(self):
    """Verify that page renders on get request."""
    self.handler.get()

  def testPageRenderingWithError(self):
    """Verify that page renders on get request."""
    self.handler.request.set('error', 'Some error.')
    self.handler.get()


class DeleteFunctionTest(googletest.TestCase):

  def setUp(self):
    class MockDelete(object):
      def __init__(self):
        self.called = False
      def Delete(self, _):
        self.called = True
    self.mock_delete = MockDelete()
    operation.db = self.mock_delete

  def testNormalDeleteWithoutActive(self):
    """Delete anything that is not a Mapreduce object."""
    entity = TestEntity('testentity', _app=APP_ID)
    datastore.Put(entity)
    delete_handler.DeleteEntity(entity.key()).next()
    self.assertTrue(self.mock_delete.called)

  def testNormalDeleteWithActive(self):
    """Delete anything that is not a Mapreduce object."""
    entity = TestEntity('testentity', _app=APP_ID)
    entity['active'] = True
    datastore.Put(entity)
    delete_handler.DeleteEntity(entity.key()).next()
    self.assertTrue(self.mock_delete.called)

  def testMapreduceActiveObject(self):
    """Do not delete active Mapreduce objects."""
    entity = TestEntity(model.MapreduceState.kind(), _app=APP_ID)
    entity['active'] = True
    datastore.Put(entity)
    self.assertRaises(StopIteration,
                      delete_handler.DeleteEntity(entity.key()).next)

  def testMapreduceInactiveObject(self):
    """Delete anything that is not a Mapreduce object."""
    entity = TestEntity(model.MapreduceState.kind(), _app=APP_ID)
    entity['active'] = False
    datastore.Put(entity)
    delete_handler.DeleteEntity(entity.key()).next()
    self.assertTrue(self.mock_delete.called)


if __name__ == '__main__':
  googletest.main()
