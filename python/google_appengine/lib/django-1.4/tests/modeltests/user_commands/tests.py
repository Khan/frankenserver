from __future__ import with_statement

from StringIO import StringIO

from django.core import management
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import translation


class CommandTests(TestCase):
    def test_command(self):
        out = StringIO()
        management.call_command('dance', stdout=out)
        self.assertEqual(out.getvalue(),
            "I don't feel like dancing Rock'n'Roll.")

    def test_command_style(self):
        out = StringIO()
        management.call_command('dance', style='Jive', stdout=out)
        self.assertEqual(out.getvalue(),
            "I don't feel like dancing Jive.")

    def test_language_preserved(self):
        out = StringIO()
        with translation.override('fr'):
            management.call_command('dance', stdout=out)
            self.assertEqual(translation.get_language(), 'fr')

    def test_explode(self):
        self.assertRaises(CommandError, management.call_command, ('explode',))
