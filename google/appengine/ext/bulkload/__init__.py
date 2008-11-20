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

"""A mix-in handler for bulk loading data into an application.

For complete documentation, see the Tools and Libraries section of the
documentation.

To use this in your app, first write a script, e.g. bulkload.py, that
instantiates a Loader for each entity kind you want to import and call
bulkload.main(instance). For example:

person = bulkload.Loader(
  'Person',
  [('name', str),
   ('email', datastore_types.Email),
   ('cool', bool), # ('0', 'False', 'No', '')=False, otherwise bool(value)
   ('birthdate', lambda x: datetime.datetime.fromtimestamp(float(x))),
  ])

if __name__ == '__main__':
  bulkload.main(person)

See the Loader class for more information. Then, add a handler for it in your
app.yaml, e.g.:

  handlers:
  - url: /load
    script: bulkload.py
    login: admin

Finally, deploy your app and run bulkloader.py. For example, to load the
file people.csv into a dev_appserver running on your local machine:

./bulkloader.py --filename people.csv --kind Person --cookie ... \
                     --url http://localhost:8080/load

The kind parameter is used to look up the Loader instance that will be used.
The bulkload handler should usually be admin_only, so that non-admins can't use
the shell to modify your app's data. The bulkload client uses the cookie
parameter to piggyback its HTTP requests on your login session. A GET request
to the URL specified for your bulkload script will give you a cookie parameter
you can use (/load in the example above).  If your bulkload handler is not
admin_only, you may omit the cookie parameter.

If you want to do extra processing before the entities are stored, you can
subclass Loader and override HandleEntity. HandleEntity is called once with
each entity that is imported from the CSV data. You can return one or more
entities from HandleEntity to be stored in its place, or None if nothing
should be stored.

For example, this loads calendar events and stores them as
datastore_entities.Event entities. It also populates their author field with a
reference to the corresponding datastore_entites.Contact entity. If no Contact
entity exists yet for the given author, it creates one and stores it first.

class EventLoader(bulkload.Loader):
  def __init__(self):
    EventLoader.__init__(self, 'Event',
                         [('title', str),
                          ('creator', str),
                          ('where', str),
                          ('startTime', lambda x:
                            datetime.datetime.fromtimestamp(float(x))),
                          ])

  def HandleEntity(self, entity):
    event = datastore_entities.Event(entity.title)
    event.update(entity)

    creator = event['creator']
    if creator:
      contact = datastore.Query('Contact', {'title': creator}).Get(1)
      if not contact:
        contact = [datastore_entities.Contact(creator)]
        datastore.Put(contact[0])
      event['author'] = contact[0].key()

    return event

if __name__ == '__main__':
  bulkload.main(EventLoader())
"""





import Cookie
import StringIO
import csv
import httplib
import os
import sys
import traceback
import types
import struct
import zlib

import google
import wsgiref.handlers

from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.ext import webapp
from google.appengine.ext.bulkload import constants


def Validate(value, type):
  """ Checks that value is non-empty and of the right type.

  Raises ValueError if value is None or empty, TypeError if it's not the given
  type.

  Args:
    value: any value
    type: a type or tuple of types
  """
  if not value:
    raise ValueError('Value should not be empty; received %s.' % value)
  elif not isinstance(value, type):
    raise TypeError('Expected a %s, but received %s (a %s).' %
                    (type, value, value.__class__))


class Loader(object):
  """A base class for creating datastore entities from input data.

  To add a handler for bulk loading a new entity kind into your datastore,
  write a subclass of this class that calls Loader.__init__ from your
  class's __init__.

  If you need to run extra code to convert entities from the input
  data, create new properties, or otherwise modify the entities before
  they're inserted, override HandleEntity.

  See the CreateEntity method for the creation of entities from the
  (parsed) input data.
  """

  __loaders = {}
  __kind = None
  __properties = None

  def __init__(self, kind, properties):
    """ Constructor.

    Populates this Loader's kind and properties map. Also registers it with
    the bulk loader, so that all you need to do is instantiate your Loader,
    and the bulkload handler will automatically use it.

    Args:
      kind: a string containing the entity kind that this loader handles

      properties: list of (name, converter) tuples.

      This is used to automatically convert the CSV columns into properties.
      The converter should be a function that takes one argument, a string
      value from the CSV file, and returns a correctly typed property value
      that should be inserted. The tuples in this list should match the
      columns in your CSV file, in order.

      For example:
        [('name', str),
         ('id_number', int),
         ('email', datastore_types.Email),
         ('user', users.User),
         ('birthdate', lambda x: datetime.datetime.fromtimestamp(float(x))),
         ('description', datastore_types.Text),
         ]
    """
    Validate(kind, basestring)
    self.__kind = kind

    Validate(properties, list)
    for name, fn in properties:
      Validate(name, basestring)
      assert callable(fn), (
        'Conversion function %s for property %s is not callable.' % (fn, name))

    self.__properties = properties

    Loader.__loaders[kind] = self


  def kind(self):
    """ Return the entity kind that this Loader handes.
    """
    return self.__kind

  def CreateEntity(self, values, key_name=None):
    """ Creates an entity from a list of property values.

    Args:
      values: list/tuple of str
      key_name: if provided, the name for the (single) resulting Entity

    Returns:
      list of datastore.Entity

      The returned entities are populated with the property values from the
      argument, converted to native types using the properties map given in
      the constructor, and passed through HandleEntity. They're ready to be
      inserted.

    Raises:
      AssertionError if the number of values doesn't match the number
        of properties in the properties map.
    """
    Validate(values, (list, tuple))
    assert len(values) == len(self.__properties), (
      'Expected %d CSV columns, found %d.' %
      (len(self.__properties), len(values)))

    entity = datastore.Entity(self.__kind, name=key_name)
    for (name, converter), val in zip(self.__properties, values):
      if converter is bool and val.lower() in ('0', 'false', 'no'):
          val = False
      entity[name] = converter(val)

    entities = self.HandleEntity(entity)

    if entities is not None:
      if not isinstance(entities, (list, tuple)):
        entities = [entities]

      for entity in entities:
        if not isinstance(entity, datastore.Entity):
          raise TypeError('Expected a datastore.Entity, received %s (a %s).' %
                          (entity, entity.__class__))

    return entities


  def HandleEntity(self, entity):
    """ Subclasses can override this to add custom entity conversion code.

    This is called for each entity, after its properties are populated from
    CSV but before it is stored. Subclasses can override this to add custom
    entity handling code.

    The entity to be inserted should be returned. If multiple entities should
    be inserted, return a list of entities. If no entities should be inserted,
    return None or [].

    Args:
      entity: datastore.Entity

    Returns:
      datastore.Entity or list of datastore.Entity
    """
    return entity


  @staticmethod
  def RegisteredLoaders():
    """ Returns a list of the Loader instances that have been created.
    """
    return dict(Loader.__loaders)


class BulkLoad(webapp.RequestHandler):
  """A handler for bulk load requests.

  This class contains handlers for the bulkloading process. One for
  GET to provide cookie information for the upload script, and one
  handler for a POST request to upload the entities.

  In the POST request, the body contains the data representing the
  entities' property values. The original format was a sequences of
  lines of comma-separated values (and is handled by the Load
  method). The current (version 1) format is a binary format described
  in the Tools and Libraries section of the documentation, and is
  handled by the LoadV1 method).
  """

  def get(self):
    """ Handle a GET. Just show an info page.
    """
    page = self.InfoPage(self.request.uri)
    self.response.out.write(page)


  def post(self):
    """ Handle a POST. Reads CSV data, converts to entities, and stores them.
    """
    self.response.headers['Content-Type'] = 'text/plain'
    version = self.request.headers.get('GAE-Uploader-Version', '0')
    if version == '1':
      kind = self.request.headers.get('GAE-Uploader-Kind')
      response, output = self.LoadV1(kind, self.request.body)
    else:
      response, output = self.Load(self.request.get(constants.KIND_PARAM),
                                   self.request.get(constants.CSV_PARAM))
    self.response.set_status(response)
    self.response.out.write(output)


  def InfoPage(self, uri):
    """ Renders an information page with the POST endpoint and cookie flag.

    Args:
      uri: a string containing the request URI
    Returns:
      A string with the contents of the info page to be displayed
    """
    page = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html><head>
<title>Bulk Loader</title>
</head><body>"""

    page += ('The bulk load endpoint is: <a href="%s">%s</a><br />\n' %
            (uri, uri))

    cookies = os.environ.get('HTTP_COOKIE', None)
    if cookies:
      cookie = Cookie.BaseCookie(cookies)
      for param in ['ACSID', 'dev_appserver_login']:
        value = cookie.get(param)
        if value:
          page += ("Pass this flag to the client: --cookie='%s=%s'\n" %
                   (param, value.value))
          break

    else:
      page += 'No cookie found!\n'

    page += '</body></html>'
    return page

  def IterRows(self, reader):
    """ Yields a tuple of a line number and row for each row of the CSV data.

    Args:
      reader: a csv reader for the input data.
    """
    line_num = 1
    for columns in reader:
      yield (line_num, columns)
      line_num += 1

  def LoadEntities(self, iter, loader, key_format=None):
    """Generates entities and loads them into the datastore.  Returns
    a tuple of HTTP code and string reply.

    Args:
      iter: an iterator yielding pairs of a line number and row contents.
      key_format: a format string to convert a line number into an
        entity id. If None, then entity ID's are automatically generated.
      """
    entities = []
    output = []
    for line_num, columns in iter:
      key_name = None
      if key_format is not None:
        key_name = key_format % line_num
      if columns:
        try:
          output.append('\nLoading from line %d...' % line_num)
          new_entities = loader.CreateEntity(columns, key_name=key_name)
          if new_entities:
            entities.extend(new_entities)
          output.append('done.')
        except:
          stacktrace = traceback.format_exc()
          output.append('error:\n%s' % stacktrace)
          return (httplib.BAD_REQUEST, ''.join(output))

    datastore.Put(entities)

    return (httplib.OK, ''.join(output))

  def Load(self, kind, data):
    """Parses CSV data, uses a Loader to convert to entities, and stores them.

    On error, fails fast. Returns a "bad request" HTTP response code and
    includes the traceback in the output.

    Args:
      kind: a string containing the entity kind that this loader handles
      data: a string containing the CSV data to load

    Returns:
      tuple (response code, output) where:
        response code: integer HTTP response code to return
        output: string containing the HTTP response body
    """
    Validate(kind, basestring)
    Validate(data, basestring)
    output = []

    try:
      loader = Loader.RegisteredLoaders()[kind]
    except KeyError:
      output.append('Error: no Loader defined for kind %s.' % kind)
      return (httplib.BAD_REQUEST, ''.join(output))

    buffer = StringIO.StringIO(data)
    reader = csv.reader(buffer, skipinitialspace=True)

    try:
      csv.field_size_limit(800000)
    except AttributeError:
      pass

    return self.LoadEntities(self.IterRows(reader), loader)

  def IterRowsV1(self, data):
    """Yields a tuple of columns for each row in the uploaded data.

    Args:
      data: a string containing the unzipped v1 format data to load.

    """
    column_count, = struct.unpack_from('!i', data)
    offset = 4

    lengths_format = '!%di' % (column_count,)

    while offset < len(data):
      id_num = struct.unpack_from('!i', data, offset=offset)
      offset += 4

      value_lengths = struct.unpack_from(lengths_format, data, offset=offset)
      offset += 4 * column_count

      columns = struct.unpack_from(''.join('%ds' % length
                                           for length in value_lengths), data,
                                   offset=offset)
      offset += sum(value_lengths)

      yield (id_num, columns)


  def LoadV1(self, kind, data):
    """Parses version-1 format data, converts to entities, and stores them.

    On error, fails fast. Returns a "bad request" HTTP response code and
    includes the traceback in the output.

    Args:
      kind: a string containing the entity kind that this loader handles
      data: a string containing the (v1 format) data to load

    Returns:
      tuple (response code, output) where:
        response code: integer HTTP response code to return
        output: string containing the HTTP response body
    """
    Validate(kind, basestring)
    Validate(data, basestring)
    output = []

    try:
      loader = Loader.RegisteredLoaders()[kind]
    except KeyError:
      output.append('Error: no Loader defined for kind %s.' % kind)
      return (httplib.BAD_REQUEST, ''.join(output))

    try:
      data = zlib.decompress(data)
    except:
      stacktrace = traceback.format_exc()
      output.append('Error: Could not decompress data\n%s' % stacktrace)
      return (httplib.BAD_REQUEST, ''.join(output))

    key_format = 'i%010d'
    return self.LoadEntities(self.IterRowsV1(data),
                             loader,
                             key_format=key_format)

def main(*loaders):
  """Starts bulk upload.

  Raises TypeError if not, at least one Loader instance is given.

  Args:
    loaders: One or more Loader instance.
  """
  if not loaders:
    raise TypeError('Expected at least one argument.')

  for loader in loaders:
    if not isinstance(loader, Loader):
      raise TypeError('Expected a Loader instance; received %r' % loader)

  application = webapp.WSGIApplication([('.*', BulkLoad)])
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
