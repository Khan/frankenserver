from __future__ import absolute_import

import contextlib
import os
import unittest

from google.appengine.tools.devappserver2 import stub_util
from google.appengine.tools.devappserver2.datastore_translator import grpc


class DatastoreTranslatorTestBase(unittest.TestCase):
  maxDiff = None

  def setUp(self):
    self.app_id = 'dev~myapp'
    # TODO(benkraft): Clean this environ setting up at end-of-test.
    # (Many of the devappserver tests don't do this, so it can't be that
    # important.)
    os.environ['APPLICATION_ID'] = self.app_id
    stub_util.setup_test_stubs(app_id=self.app_id)

  @contextlib.contextmanager
  def assertRaisesGrpcCode(self, grpc_code):
    with self.assertRaises(grpc.Error) as ctx:
      yield

    self.assertEqual(ctx.exception.grpc_code, grpc_code)
