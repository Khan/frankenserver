import warnings

from django.contrib.auth.models import User
from django.test import TestCase


class SpecialHeadersTest(TestCase):
    fixtures = ['data.xml']
    urls = 'regressiontests.special_headers.urls'

    def setUp(self):
        self.save_warnings_state()
        warnings.filterwarnings('ignore', category=DeprecationWarning,
                                module='django.views.generic.list_detail')

    def tearDown(self):
        self.restore_warnings_state()

    def test_xheaders(self):
        user = User.objects.get(username='super')
        response = self.client.get('/special_headers/article/1/')
        self.assertFalse('X-Object-Type' in response)
        self.client.login(username='super', password='secret')
        response = self.client.get('/special_headers/article/1/')
        self.assertTrue('X-Object-Type' in response)
        user.is_staff = False
        user.save()
        response = self.client.get('/special_headers/article/1/')
        self.assertFalse('X-Object-Type' in response)
        user.is_staff = True
        user.is_active = False
        user.save()
        response = self.client.get('/special_headers/article/1/')
        self.assertFalse('X-Object-Type' in response)

    def test_xview_func(self):
        user = User.objects.get(username='super')
        response = self.client.head('/special_headers/xview/func/')
        self.assertFalse('X-View' in response)
        self.client.login(username='super', password='secret')
        response = self.client.head('/special_headers/xview/func/')
        self.assertTrue('X-View' in response)
        self.assertEqual(response['X-View'], 'regressiontests.special_headers.views.xview')
        user.is_staff = False
        user.save()
        response = self.client.head('/special_headers/xview/func/')
        self.assertFalse('X-View' in response)
        user.is_staff = True
        user.is_active = False
        user.save()
        response = self.client.head('/special_headers/xview/func/')
        self.assertFalse('X-View' in response)

    def test_xview_class(self):
        user = User.objects.get(username='super')
        response = self.client.head('/special_headers/xview/class/')
        self.assertFalse('X-View' in response)
        self.client.login(username='super', password='secret')
        response = self.client.head('/special_headers/xview/class/')
        self.assertTrue('X-View' in response)
        self.assertEqual(response['X-View'], 'regressiontests.special_headers.views.XViewClass')
        user.is_staff = False
        user.save()
        response = self.client.head('/special_headers/xview/class/')
        self.assertFalse('X-View' in response)
        user.is_staff = True
        user.is_active = False
        user.save()
        response = self.client.head('/special_headers/xview/class/')
        self.assertFalse('X-View' in response)
