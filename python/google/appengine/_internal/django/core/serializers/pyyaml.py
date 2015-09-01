"""
YAML serializer.

Requires PyYaml (http://pyyaml.org/), but that's checked for in __init__.
"""

from StringIO import StringIO
import decimal
import yaml

from google.appengine._internal.django.db import models
from google.appengine._internal.django.core.serializers.python import Serializer as PythonSerializer
from google.appengine._internal.django.core.serializers.python import Deserializer as PythonDeserializer

class DjangoSafeDumper(yaml.SafeDumper):
    def represent_decimal(self, data):
        return self.represent_scalar('tag:yaml.org,2002:str', str(data))

DjangoSafeDumper.add_representer(decimal.Decimal, DjangoSafeDumper.represent_decimal)

class Serializer(PythonSerializer):
    """
    Convert a queryset to YAML.
    """

    internal_use_only = False

    def handle_field(self, obj, field):
        # A nasty special case: base YAML doesn't support serialization of time
        # types (as opposed to dates or datetimes, which it does support). Since
        # we want to use the "safe" serializer for better interoperability, we
        # need to do something with those pesky times. Converting 'em to strings
        # isn't perfect, but it's better than a "!!python/time" type which would
        # halt deserialization under any other language.
        if isinstance(field, models.TimeField) and getattr(obj, field.name) is not None:
            self._current[field.name] = str(getattr(obj, field.name))
        else:
            super(Serializer, self).handle_field(obj, field)

    def end_serialization(self):
        yaml.dump(self.objects, self.stream, Dumper=DjangoSafeDumper, **self.options)

    def getvalue(self):
        return self.stream.getvalue()

def Deserializer(stream_or_string, **options):
    """
    Deserialize a stream or string of YAML data.
    """
    if isinstance(stream_or_string, basestring):
        stream = StringIO(stream_or_string)
    else:
        stream = stream_or_string
    for obj in PythonDeserializer(yaml.safe_load(stream), **options):
        yield obj

