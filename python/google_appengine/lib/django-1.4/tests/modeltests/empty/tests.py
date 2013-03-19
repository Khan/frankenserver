from __future__ import with_statement, absolute_import

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models.loading import get_app
from django.test import TestCase
from django.test.utils import override_settings

from .models import Empty


class EmptyModelTests(TestCase):
    def test_empty(self):
        m = Empty()
        self.assertEqual(m.id, None)
        m.save()
        m2 = Empty.objects.create()
        self.assertEqual(len(Empty.objects.all()), 2)
        self.assertTrue(m.id is not None)
        existing = Empty(m.id)
        existing.save()

class NoModelTests(TestCase):
    """
    Test for #7198 to ensure that the proper error message is raised
    when attempting to load an app with no models.py file.

    Because the test runner won't currently load a test module with no
    models.py file, this TestCase instead lives in this module.

    It seemed like an appropriate home for it.
    """
    @override_settings(INSTALLED_APPS=("modeltests.empty.no_models",))
    def test_no_models(self):
        with self.assertRaisesRegexp(ImproperlyConfigured,
                    'App with label no_models is missing a models.py module.'):
            get_app('no_models')
