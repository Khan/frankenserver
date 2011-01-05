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

"""Tests for google.appengine.ext.datastore_admin.utils."""


import google

import datetime
import mox

from google.appengine.api import namespace_manager
from google.appengine.ext import db
from google.appengine.ext.datastore_admin import testutil
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import testutil
from google.appengine.ext.webapp import mock_webapp
from google.testing.pybase import googletest


def foo(key):
  """Test mapper handler."""
  pass


class TestEntity(db.Model):
  """Dummy test entity."""
  pass


class UtilsTest(googletest.TestCase):
  """Tests util module functions."""

  def testFormatThousands(self):
    """Tests the FormatThousands() function."""
    self.assertEqual('0', utils.FormatThousands(0))
    self.assertEqual('0.00', utils.FormatThousands(0.0))
    self.assertEqual('0', utils.FormatThousands('0'))
    self.assertEqual('0.0', utils.FormatThousands('0.0'))
    self.assertEqual('7', utils.FormatThousands(7))
    self.assertEqual('65', utils.FormatThousands('65'))
    self.assertEqual('432', utils.FormatThousands(432))
    self.assertEqual('432.00', utils.FormatThousands(432.0))
    self.assertEqual('1,234', utils.FormatThousands(1234))
    self.assertEqual('1,234.56', utils.FormatThousands(1234.56))
    self.assertEqual('1,234.57', utils.FormatThousands(1234.567))
    self.assertEqual('1,234.567', utils.FormatThousands('1234.567'))
    self.assertEqual('1,234.5678', utils.FormatThousands('1234.5678'))

    self.assertEqual('-7', utils.FormatThousands(-7))
    self.assertEqual('-65', utils.FormatThousands('-65'))
    self.assertEqual('-432', utils.FormatThousands(-432))
    self.assertEqual('-432.00', utils.FormatThousands(-432.0))
    self.assertEqual('-1,234', utils.FormatThousands(-1234))
    self.assertEqual('-1,234.56', utils.FormatThousands(-1234.56))
    self.assertEqual('-1,234.57', utils.FormatThousands(-1234.567))
    self.assertEqual('-1,234.567', utils.FormatThousands('-1234.567'))
    self.assertEqual('-1,234.5678', utils.FormatThousands('-1234.5678'))

  def testGetPrettyBytes(self):
    """Test _GetPrettyBytes method."""
    self.assertEqual('1023 Bytes', utils.GetPrettyBytes(1023))
    self.assertEqual('1 KByte', utils.GetPrettyBytes(1024))
    self.assertEqual('1023 KBytes', utils.GetPrettyBytes(1047575))
    self.assertEqual('1 MByte', utils.GetPrettyBytes(1048576))
    self.assertEqual('1023 MBytes', utils.GetPrettyBytes(1072741823))
    self.assertEqual('1 GByte', utils.GetPrettyBytes(1073741824))
    self.assertEqual('1023 GBytes', utils.GetPrettyBytes(1098511627775))
    self.assertEqual('1 TByte', utils.GetPrettyBytes(1099511627776))
    self.assertEqual('1023 TBytes', utils.GetPrettyBytes(1124899906842623))
    self.assertEqual('1 PByte', utils.GetPrettyBytes(1125899906842624))
    self.assertEqual('1023 PBytes', utils.GetPrettyBytes(1151921504606846175))
    self.assertEqual('1 EByte', utils.GetPrettyBytes(1152921504606846976))

    self.assertEqual('1023 Bytes', utils.GetPrettyBytes(1023, 1))
    self.assertEqual('984.9 KBytes', utils.GetPrettyBytes(1008574, 1))
    self.assertEqual('966.8 MBytes', utils.GetPrettyBytes(1013741823, 1))
    self.assertEqual('940.181 GBytes', utils.GetPrettyBytes(1009511627775, 3))
    self.assertEqual('914.86 TBytes', utils.GetPrettyBytes(1005899906842623, 2))
    self.assertEqual('1.320 PBytes', utils.GetPrettyBytes(1485899906842624, 3))
    self.assertEqual('1.538 EBytes',
                     utils.GetPrettyBytes(1772921504606846976, 3))


class MapreduceDoneHandlerTest(testutil.HandlerTestBase):
  """Test utils.MapreduceDoneHandlerTest."""

  def setUp(self):
    """Sets up the test harness."""
    testutil.HandlerTestBase.setUp(self)
    self.mapreduce_id = '123456789'
    self.num_shards = 32
    self.handler = utils.MapreduceDoneHandler()
    self.handler.initialize(mock_webapp.MockRequest(),
                            mock_webapp.MockResponse())

    self.handler.request.path = '/_ah/datastore_admin/%s' % (
        utils.MapreduceDoneHandler.SUFFIX)
    self.handler.request.headers['Mapreduce-Id'] = self.mapreduce_id

  def assertObjectsExist(self):
    """Verify that objects were inserted."""
    self.assertIsNotNone(
        model.MapreduceState.get_by_key_name(self.mapreduce_id))
    self.assertSameElements(
        ['%s-%s' % (self.mapreduce_id, i)
         for i in range(0, self.num_shards)],
        [m.key().name() for m in (
            model.ShardState.find_by_mapreduce_id(self.mapreduce_id))])

  def testSuccessfulJob(self):
    """Verify that with appropriate request parameters form is constructed."""
    TestEntity().put()
    admin_operation = utils.StartOperation("Test Operation")
    self.mapreduce_id = utils.StartMap(
        admin_operation,
        'test_job',
        '__main__.foo',
        ('google.appengine.ext.mapreduce.input_readers.'
         'DatastoreKeyInputReader'),
        {'entity_kind': 'TestEntity'})
    testutil.execute_all_tasks(self.taskqueue)
    self.assertObjectsExist()

    testutil.execute_until_empty(self.taskqueue)

    self.handler.request.headers['Mapreduce-Id'] = self.mapreduce_id
    self.handler.post()

    self.assertIsNone(model.MapreduceState.get_by_key_name(self.mapreduce_id))
    self.assertListEqual(
        [],
        model.ShardState.find_by_mapreduce_id(self.mapreduce_id))
    admin_operation = admin_operation.get(admin_operation.key())
    self.assertEqual(0, admin_operation.active_jobs)
    self.assertEqual(1, admin_operation.completed_jobs)
    self.assertEqual('Completed', admin_operation.status)

  def testFailedJob(self):
    """Verify that with appropriate request parameters form is constructed."""
    model.MapreduceState.create_new(self.mapreduce_id).put()
    for i in range(0, self.num_shards):
      shard_state = model.ShardState.create_new(self.mapreduce_id, i)
      if i != 4:
        shard_state.result_status = 'success'
      shard_state.put()

    self.assertObjectsExist()

    self.handler.post()

    self.assertObjectsExist()


class RunMapForKindsTest(testutil.HandlerTestBase):
  """Test for RunMapForKinds."""

  def setUp(self):
    super(RunMapForKindsTest, self).setUp()

    self.operation = utils.StartOperation('test operation')
    self.reader_class = input_readers.DatastoreKeyInputReader
    self.reader_class_spec = (self.reader_class.__module__ +
                              "." + self.reader_class.__name__)

  def testNoNamespaces(self):
    """Test default namespace case only."""
    TestEntity().put()

    jobs = utils.RunMapForKinds(
        self.operation,
        [TestEntity.kind()],
        'Test job for %(kind)s%(namespace)s',
        '__main__.foo',
        self.reader_class_spec,
        {'test_param': 1})
    testutil.execute_all_tasks(self.taskqueue)

    self.assertEquals(1, len(jobs))
    job = jobs[0]
    state = model.MapreduceState.get_by_job_id(job)
    self.assertTrue(state)

    spec = state.mapreduce_spec
    self.assertTrue(spec)
    self.assertEquals("Test job for TestEntity", spec.name)
    mapper = spec.mapper
    self.assertTrue(mapper)
    self.assertEquals({'test_param': 1,
                       'entity_kind': TestEntity.kind()},
                      mapper.params)
    self.assertEquals('__main__.foo', mapper.handler_spec)
    self.assertEquals(self.reader_class_spec, mapper.input_reader_spec)


  def testNamespaces(self):
    """Test non-default namespaces present."""
    namespace_manager.set_namespace("1")
    TestEntity().put()
    namespace_manager.set_namespace(None)

    jobs = utils.RunMapForKinds(
        self.operation,
        [TestEntity.kind()],
        'Test job for %(kind)s%(namespace)s',
        '__main__.foo',
        self.reader_class_spec,
        {'test_param': 1})
    testutil.execute_all_tasks(self.taskqueue)

    self.assertEquals(1, len(jobs))
    job = jobs[0]
    state = model.MapreduceState.get_by_job_id(job)
    self.assertTrue(state)

    spec = state.mapreduce_spec
    self.assertTrue(spec)
    self.assertEquals('Test job for TestEntity: discovering namespaces',
                      spec.name)
    mapper = spec.mapper
    self.assertTrue(mapper)
    self.assertEquals({'entity_kind': '__namespace__'},
                      mapper.params)
    self.assertEquals(utils.__name__ + "." + utils.ProcessNamespace.__name__,
                      mapper.handler_spec)
    self.assertEquals(
        'google.appengine.ext.mapreduce.input_readers.NamespaceInputReader',
        mapper.input_reader_spec)
    self.assertEquals({'kinds': [TestEntity.kind()],
                       'reader_spec': self.reader_class_spec,
                       'datastore_admin_operation': str(self.operation.key()),
                       'mapper_params': {'test_param': 1},
                       'handler_spec': '__main__.foo',
                       'done_callback': '/_ah/datastore_admin/mapreduce_done',
                       'job_name': 'Test job for %(kind)s%(namespace)s',
                       },
                      spec.params)

  def testProcessNamespace(self):
    """Test ProcessNamespace function."""
    namespace_manager.set_namespace("1")
    TestEntity().put()
    namespace_manager.set_namespace(None)

    namespaces_jobs = utils.RunMapForKinds(
        self.operation,
        [TestEntity.kind()],
        'Test job for %(kind)s%(namespace)s',
        '__main__.foo',
        self.reader_class_spec,
        {'test_param': 1})
    testutil.execute_all_tasks(self.taskqueue)

    m = mox.Mox()
    m.StubOutWithMock(context, "get", use_mock_anything=True)

    ctx = context.Context(
        model.MapreduceState.get_by_job_id(namespaces_jobs[0]).mapreduce_spec,
        None)
    context.get().AndReturn(ctx)
    context.get().AndReturn(ctx)

    m.ReplayAll()
    try:
      jobs = utils.ProcessNamespace('1')
      jobs.extend(utils.ProcessNamespace('1'))
      m.VerifyAll()
    finally:
      m.UnsetStubs()
    testutil.execute_all_tasks(self.taskqueue)

    self.assertEquals(1, len(jobs))
    job = jobs[0]
    state = model.MapreduceState.get_by_job_id(job)
    self.assertTrue(state)

    spec = state.mapreduce_spec
    self.assertTrue(spec)
    self.assertEquals("Test job for TestEntity in namespace 1", spec.name)
    mapper = spec.mapper
    self.assertTrue(mapper)
    self.assertEquals({'test_param': 1,
                       'entity_kind': TestEntity.kind(),
                       'namespaces': '1'},
                      mapper.params)
    self.assertEquals('__main__.foo', mapper.handler_spec)
    self.assertEquals(self.reader_class_spec, mapper.input_reader_spec)


if __name__ == '__main__':
  googletest.main()
