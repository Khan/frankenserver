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
   ('birthdate', lambda x: datetime.datetime.fromtimestamp(float(x))),
  ])

if __name__ == '__main__':
  bulkload.main(person)

See the Loader class for more information. Then, add a handler for it in your
app.yaml, e.g.:

  urlmap:
  - regex: /load
    handler:
      type: 1
      path: bulkload.py
      requires_login: true
      admin_only: true

Finally, deploy your app and run bulkload_client.py. For example, to load the
file people.csv into a dev_appserver running on your local machine:

./bulkload_client.py --filename people.csv --kind Person --cookie ... \
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
  """ A base class for creating datastore entities from CSV input data.

  To add a handler for bulk loading a new entity kind into your datastore,
  write a subclass of this class that calls Loader.__init__ from your
  class's __init__.

  If you need to run extra code to convert entities from CSV, create new
  properties, or otherwise modify the entities before they're inserted,
  override HandleEntity.
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


  def CreateEntity(self, values):
    """ Creates an entity from a list of property values.

    Args:
      values: list of str

    Returns:
      list of datastore.Entity

      The returned entities are populated with the property values from the
      argument, converted to native types using the properties map given in
      the constructor, and passed through HandleEntity. They're ready to be
      inserted.

    Raises an AssertionError if the number of values doesn't match the number
    of properties in the properties map.
    """
    Validate(values, list)
    assert len(values) == len(self.__properties), (
      'Expected %d CSV columns, found %d.' %
      (len(self.__properties), len(values)))

    entity = datastore.Entity(self.__kind)
    for (name, converter), val in zip(self.__properties, values):
      entity[name] = converter(val)

    entities = self.HandleEntity(entity)

    if entities is not None:
      if not isinstance(entities, list):
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
  """ A handler for bulk load requests.
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


  def Load(self, kind, data):
    """ Parses CSV data, uses a Loader to convert to entities, and stores them.

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
    entities = []

    line_num = 1
    for columns in reader:
      if columns:
        try:
          output.append('\nLoading from line %d...' % line_num)
          entities.extend(loader.CreateEntity(columns))
          output.append('done.')
        except:
          exc_info = sys.exc_info()
          stacktrace = traceback.format_exception(*exc_info)
          output.append('error:\n%s' % stacktrace)
          return (httplib.BAD_REQUEST, ''.join(output))

      line_num += 1

    for entity in entities:
      datastore.Put(entity)

    return (httplib.OK, ''.join(output))


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
