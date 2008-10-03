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

"""Simple datastore view and interactive console, for use in dev_appserver."""





import cgi
import csv
import cStringIO
import datetime
import logging
import math
import mimetypes
import os
import os.path
import pickle
import pprint
import random
import sys
import time
import traceback
import types
import urllib
import urlparse
import wsgiref.handlers

from google.appengine.api import datastore
from google.appengine.api import datastore_admin
from google.appengine.api import datastore_types
from google.appengine.api import datastore_errors
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

_DEBUG = True


class ImageHandler(webapp.RequestHandler):
  """Serves a static image.

  This exists because we don't want to burden the user with specifying
  a static file handler for the image resources used by the admin tool.
  """

  PATH = '/images/.*'

  def get(self):
    image_name = os.path.basename(self.request.path)
    content_type, encoding = mimetypes.guess_type(image_name)
    if not content_type or not content_type.startswith('image/'):
      logging.debug('image_name=%r, content_type=%r, encoding=%r',
                    image_name, content_type, encoding)
      self.error(404)
      return
    directory = os.path.dirname(__file__)
    path = os.path.join(directory, 'templates', 'images', image_name)
    try:
      image_stream = open(path, 'rb')
    except IOError, e:
      logging.error('Cannot open image %s: %s', image_name, e)
      self.error(404)
      return
    try:
      image_data = image_stream.read()
    finally:
      image_stream.close()
    self.response.headers['Content-Type'] = content_type
    self.response.out.write(image_data)


class BaseRequestHandler(webapp.RequestHandler):
  """Supplies a common template generation function.

  When you call generate(), we augment the template variables supplied with
  the current user in the 'user' variable and the current webapp request
  in the 'request' variable.
  """

  def generate(self, template_name, template_values={}):
    base_path = self.base_path()
    values = {
      'application_name': self.request.environ['APPLICATION_ID'],
      'user': users.get_current_user(),
      'request': self.request,
      'home_path': base_path + DefaultPageHandler.PATH,
      'datastore_path': base_path + DatastoreQueryHandler.PATH,
      'datastore_edit_path': base_path + DatastoreEditHandler.PATH,
      'datastore_batch_edit_path': base_path + DatastoreBatchEditHandler.PATH,
      'interactive_path': base_path + InteractivePageHandler.PATH,
      'interactive_execute_path': base_path + InteractiveExecuteHandler.PATH,
      'memcache_path': base_path + MemcachePageHandler.PATH,
    }
    values.update(template_values)
    directory = os.path.dirname(__file__)
    path = os.path.join(directory, os.path.join('templates', template_name))
    self.response.out.write(template.render(path, values, debug=_DEBUG))

  def base_path(self):
    """Returns the base path of this admin app, which is chosen by the user.

    The user specifies which paths map to this application in their app.cfg.
    You can get that base path with this method. Combine with the constant
    paths specified by the classes to construct URLs.
    """
    path = self.__class__.PATH
    return self.request.path[:-len(path)]

  def filter_url(self, args):
    """Filters the current URL to only have the given list of arguments.

    For example, if your URL is /search?q=foo&num=100&start=10, then

       self.filter_url(['start', 'num']) => /search?num=100&start=10
       self.filter_url(['q']) => /search?q=10
       self.filter_url(['random']) => /search?

    """
    queries = []
    for arg in args:
      value = self.request.get(arg)
      if value:
        queries.append(arg + '=' + urllib.quote_plus(self.request.get(arg)))
    return self.request.path + '?' + '&'.join(queries)


class DefaultPageHandler(BaseRequestHandler):
  """Redirects to the Datastore application by default."""

  PATH = '/'

  def get(self):
    if self.request.path.endswith('/'):
      base = self.request.path[:-1]
    else:
      base = self.request.path
    self.redirect(base + DatastoreQueryHandler.PATH)


class InteractivePageHandler(BaseRequestHandler):
  """Shows our interactive console HTML."""
  PATH = '/interactive'

  def get(self):
    self.generate('interactive.html')


class InteractiveExecuteHandler(BaseRequestHandler):
  """Executes the Python code submitted in a POST within this context.

  For obvious reasons, this should only be available to administrators
  of the applications.
  """

  PATH = InteractivePageHandler.PATH + '/execute'

  def post(self):
    save_stdout = sys.stdout
    results_io = cStringIO.StringIO()
    try:
      sys.stdout = results_io

      code = self.request.get('code')
      code = code.replace("\r\n", "\n")

      try:
        compiled_code = compile(code, '<string>', 'exec')
        exec(compiled_code, globals())
      except Exception, e:
        traceback.print_exc(file=results_io)
    finally:
      sys.stdout = save_stdout

    results = results_io.getvalue()
    self.generate('interactive-output.html', {'output': results})


class MemcachePageHandler(BaseRequestHandler):
  """Shows stats about memcache and query form to get values."""
  PATH = '/memcache'

  TYPES = ((str, str, 'String'),
           (unicode, unicode, 'Unicode String'),
           (bool, lambda value: MemcachePageHandler._ToBool(value), 'Boolean'),
           (int, int, 'Integer'),
           (long, long, 'Long Integer'),
           (float, float, 'Float'))
  DEFAULT_TYPESTR_FOR_NEW = 'String'

  @staticmethod
  def _ToBool(string_value):
    """Convert string to boolean value.

    Args:
      string_value: A string.

    Returns:
      Boolean.  True if string_value is "true", False if string_value is
      "false".  This is case-insensitive.

    Raises:
      ValueError: string_value not "true" or "false".
    """
    string_value_low = string_value.lower()
    if string_value_low not in ('false', 'true'):
      raise ValueError('invalid literal for boolean: %s' % string_value)
    return string_value_low == 'true'

  def _GetValueAndType(self, key):
    """Fetch value from memcache and detect its type.

    Args:
      key: String

    Returns:
      (value, type), value is a Python object or None if the key was not set in
      the cache, type is a string describing the type of the value.
    """
    try:
      value = memcache.get(key)
    except (pickle.UnpicklingError, AttributeError, EOFError, ImportError,
            IndexError), e:
      msg = 'Failed to retrieve value from cache: %s' % e
      return msg, 'error'

    if value is None:
      return None, self.DEFAULT_TYPESTR_FOR_NEW

    for typeobj, _, typestr in self.TYPES:
      if isinstance(value, typeobj):
        break
    else:
      typestr = 'pickled'
      value = pprint.pformat(value, indent=2)

    return value, typestr

  def _SetValue(self, key, type_, value):
    """Convert a string value and store the result in memcache.

    Args:
      key: String
      type_: String, describing what type the value should have in the cache.
      value: String, will be converted according to type_.

    Returns:
      Result of memcache.set(ket, converted_value).  True if value was set.

    Raises:
      ValueError: Value can't be converted according to type_.
    """
    for _, converter, typestr in self.TYPES:
      if typestr == type_:
        value = converter(value)
        break
    else:
      raise ValueError('Type %s not supported.' % type_)
    return memcache.set(key, value)

  def get(self):
    """Show template and prepare stats and/or key+value to display/edit."""
    values = {'request': self.request,
              'message': self.request.get('message')}

    edit = self.request.get('edit')
    key = self.request.get('key')
    if edit:
      key = edit
      values['show_stats'] = False
      values['show_value'] = False
      values['show_valueform'] = True
      values['types'] = [typestr for _, _, typestr in self.TYPES]
    elif key:
      values['show_stats'] = True
      values['show_value'] = True
      values['show_valueform'] = False
    else:
      values['show_stats'] = True
      values['show_valueform'] = False
      values['show_value'] = False

    if key:
      values['key'] = key
      values['value'], values['type'] = self._GetValueAndType(key)
      values['key_exists'] = values['value'] is not None

      if values['type'] in ('pickled', 'error'):
        values['writable'] = False
      else:
        values['writable'] = True

    if values['show_stats']:
      memcache_stats = memcache.get_stats()
      values['stats'] = memcache_stats
      try:
        hitratio = memcache_stats['hits'] * 100 / (memcache_stats['hits']
                                                   + memcache_stats['misses'])
      except ZeroDivisionError:
        hitratio = 0
      values['hitratio'] = hitratio
      delta_t = datetime.timedelta(seconds=memcache_stats['oldest_item_age'])
      values['oldest_item_age'] = datetime.datetime.now() - delta_t

    self.generate('memcache.html', values)

  def _urlencode(self, query):
    """Encode a dictionary into a URL query string.

    In contrast to urllib this encodes unicode characters as UTF8.

    Args:
      query: Dictionary of key/value pairs.

    Returns:
      String.
    """
    return '&'.join('%s=%s' % (urllib.quote_plus(k.encode('utf8')),
                               urllib.quote_plus(v.encode('utf8')))
                    for k, v in query.iteritems())

  def post(self):
    """Handle modifying actions and/or redirect to GET page."""
    next_param = {}

    if self.request.get('action:flush'):
      if memcache.flush_all():
        next_param['message'] = 'Cache flushed, all keys dropped.'
      else:
        next_param['message'] = 'Flushing the cache failed.  Please try again.'

    elif self.request.get('action:display'):
      next_param['key'] = self.request.get('key')

    elif self.request.get('action:edit'):
      next_param['edit'] = self.request.get('key')

    elif self.request.get('action:delete'):
      key = self.request.get('key')
      result = memcache.delete(key)
      if result == memcache.DELETE_NETWORK_FAILURE:
        next_param['message'] = ('ERROR: Network failure, key "%s" not deleted.'
                                 % key)
      elif result == memcache.DELETE_ITEM_MISSING:
        next_param['message'] = 'Key "%s" not in cache.' % key
      elif result == memcache.DELETE_SUCCESSFUL:
        next_param['message'] = 'Key "%s" deleted.' % key
      else:
        next_param['message'] = ('Unknown return value.  Key "%s" might still '
                                 'exist.' % key)

    elif self.request.get('action:save'):
      key = self.request.get('key')
      value = self.request.get('value')
      type_ = self.request.get('type')
      next_param['key'] = key
      try:
        if self._SetValue(key, type_, value):
          next_param['message'] = 'Key "%s" saved.' % key
        else:
          next_param['message'] = 'ERROR: Failed to save key "%s".' % key
      except ValueError, e:
        next_param['message'] = 'ERROR: Unable to encode value: %s' % e

    elif self.request.get('action:cancel'):
      next_param['key'] = self.request.get('key')

    else:
      next_param['message'] = 'Unknown action.'

    next = self.request.path_url
    if next_param:
      next = '%s?%s' % (next, self._urlencode(next_param))
    self.redirect(next)


class DatastoreRequestHandler(BaseRequestHandler):
  """The base request handler for our datastore admin pages.

  We provide utility functions for quering the datastore and infering the
  types of entity properties.
  """

  def start(self):
    """Returns the santized "start" argument from the URL."""
    return self.request.get_range('start', min_value=0, default=0)

  def num(self):
    """Returns the sanitized "num" argument from the URL."""
    return self.request.get_range('num', min_value=1, max_value=100,
                                  default=10)

  def execute_query(self, start=0, num=0, no_order=False):
    """Parses the URL arguments and executes the query.

    We return a tuple (list of entities, total entity count).

    If the appropriate URL arguments are not given, we return an empty
    set of results and 0 for the entity count.
    """
    kind = self.request.get('kind')
    if not kind:
      return ([], 0)
    query = datastore.Query(kind)

    order = self.request.get('order')
    order_type = self.request.get('order_type')
    if order and order_type:
      order_type = DataType.get_by_name(order_type).python_type()
      if order.startswith('-'):
        direction = datastore.Query.DESCENDING
        order = order[1:]
      else:
        direction = datastore.Query.ASCENDING
      try:
        query.Order((order, order_type, direction))
      except datastore_errors.BadArgumentError:
        pass

    if not start:
      start = self.start()
    if not num:
      num = self.num()
    total = query.Count()
    entities = query.Get(start + num)[start:]
    return (entities, total)

  def get_key_values(self, entities):
    """Returns the union of key names used by the given list of entities.

    We return the union as a dictionary mapping the key names to a sample
    value from one of the entities for the key name.
    """
    key_dict = {}
    for entity in entities:
      for key, value in entity.iteritems():
        if key_dict.has_key(key):
          key_dict[key].append(value)
        else:
          key_dict[key] = [value]
    return key_dict


class DatastoreQueryHandler(DatastoreRequestHandler):
  """Our main request handler that executes queries and lists entities.

  We use execute_query() in our base request handler to parse URL arguments
  and execute the datastore query.
  """

  PATH = '/datastore'

  SCHEMA_CACHE_TIMEOUT = 60

  def get_kinds(self, cache={}):
    """Return sorted list of kind names the datastore knows about.

    The list of kinds is cached for a short time.
    """
    server_software = os.environ['SERVER_SOFTWARE']
    in_production = not server_software.startswith('Development')

    if in_production and ('kinds' in cache):
      if cache['kinds_timestamp'] + self.SCHEMA_CACHE_TIMEOUT > time.time():
        return cache['kinds']
      else:
        del cache['kinds']
    schema = datastore_admin.GetSchema()
    kinds = []
    for entity_proto in schema:
      kinds.append(entity_proto.key().path().element_list()[-1].type())
    kinds.sort()
    if in_production:
      cache['kinds'] = kinds
      cache['kinds_timestamp'] = time.time()
    return kinds

  def get(self):
    """Formats the results from execute_query() for datastore.html.

    The only complex part of that process is calculating the pager variables
    to generate the Gooooogle pager at the bottom of the page.
    """
    result_set, total = self.execute_query()
    key_values = self.get_key_values(result_set)
    keys = key_values.keys()
    keys.sort()

    headers = []
    for key in keys:
      sample_value = key_values[key][0]
      headers.append({
        'name': key,
        'type': DataType.get(sample_value).name(),
      })

    entities = []
    edit_path = self.base_path() + DatastoreEditHandler.PATH
    for entity in result_set:
      attributes = []
      for key in keys:
        if entity.has_key(key):
          raw_value = entity[key]
          value = DataType.get(raw_value).format(raw_value)
          short_value = DataType.get(raw_value).short_format(raw_value)
        else:
          value = ''
          short_value = ''
        attributes.append({
          'name': key,
          'value': value,
          'short_value': short_value,
        })
      entities.append({
        'key': str(entity.key()),
        'key_name': entity.key().name(),
        'key_id': entity.key().id(),
        'shortened_key': str(entity.key())[:8] + '...',
        'attributes': attributes,
        'edit_uri': edit_path + '?key=' + str(entity.key()) + '&kind=' + urllib.quote(self.request.get('kind')) + '&next=' + urllib.quote(self.request.uri),
      })

    start = self.start()
    num = self.num()
    max_pager_links = 8
    current_page = start / num
    num_pages = int(math.ceil(total * 1.0 / num))
    page_start = max(math.floor(current_page - max_pager_links / 2), 0)
    page_end = min(page_start + max_pager_links, num_pages)

    pages = []
    for page in range(page_start + 1, page_end + 1):
      pages.append({
        'number': page,
        'start': (page - 1) * num,
      })
    current_page += 1

    values = {
      'request': self.request,
      'kinds': self.get_kinds(),
      'kind': self.request.get('kind'),
      'order': self.request.get('order'),
      'headers': headers,
      'entities': entities,
      'message': self.request.get('msg'),
      'pages': pages,
      'current_page': current_page,
      'num': num,
      'next_start': -1,
      'prev_start': -1,
      'start': start,
      'total': total,
      'start_base_url': self.filter_url(['kind', 'order', 'order_type',
                                         'num']),
      'order_base_url': self.filter_url(['kind', 'num']),
    }
    if current_page > 1:
      values['prev_start'] = int((current_page - 2) * num)
    if current_page < num_pages:
      values['next_start'] = int(current_page * num)

    self.generate('datastore.html', values)


class DatastoreBatchEditHandler(DatastoreRequestHandler):
  """Request handler for a batch operation on entities.

  Supports deleting multiple entities by key, then redirecting to another url.
  """

  PATH = DatastoreQueryHandler.PATH + '/batchedit'

  def post(self):
    kind = self.request.get('kind')

    keys = []
    index = 0
    num_keys = int(self.request.get('numkeys'))
    for i in xrange(1, num_keys+1):
      key = self.request.get('key%d' % i)
      if key:
        keys.append(key)

    if self.request.get('action') == 'Delete':
      num_deleted = 0
      for key in keys:
        datastore.Delete(datastore.Key(key))
        num_deleted = num_deleted + 1
      message = '%d entit%s deleted.' % (
        num_deleted, ('ies', 'y')[num_deleted == 1])
      self.redirect(
        '%s&msg=%s' % (self.request.get('next'), urllib.quote_plus(message)))
      return

    self.error(404)


class DatastoreEditHandler(DatastoreRequestHandler):
  """Request handler for the entity create/edit form.

  We determine how to generate a form to edit an entity by doing a query
  on the entity kind and looking at the set of keys and their types in
  the result set. We use the DataType subclasses for those introspected types
  to generate the form and parse the form results.
  """

  PATH = DatastoreQueryHandler.PATH + '/edit'

  def get(self):
    kind = self.request.get('kind')
    sample_entities = self.execute_query()[0]
    if len(sample_entities) < 1:
      next_uri = self.request.get('next')
      kind_param = 'kind=%s' % kind
      if not kind_param in next_uri:
        if '?' in next_uri:
          next_uri += '&' + kind_param
        else:
          next_uri += '?' + kind_param
      self.redirect(next_uri)
      return

    entity_key = self.request.get('key')
    if entity_key:
      key_instance = datastore.Key(entity_key)
      entity_key_name = key_instance.name()
      entity_key_id = key_instance.id()
      parent_key = key_instance.parent()
      entity = datastore.Get(key_instance)
    else:
      key_instance = None
      entity_key_name = None
      entity_key_id = None
      parent_key = None
      entity = None

    if parent_key:
      parent_kind = parent_key.kind()
    else:
      parent_kind = None

    fields = []
    key_values = self.get_key_values(sample_entities)
    for key, sample_values in key_values.iteritems():
      if entity and entity.has_key(key):
        data_type = DataType.get(entity[key])
      else:
        data_type = DataType.get(sample_values[0])
      name = data_type.name() + "|" + key
      if entity and entity.has_key(key):
        value = entity[key]
      else:
        value = None
      field = data_type.input_field(name, value, sample_values)
      fields.append((key, data_type.name(), field))

    self.generate('datastore_edit.html', {
      'kind': kind,
      'key': entity_key,
      'key_name': entity_key_name,
      'key_id': entity_key_id,
      'fields': fields,
      'focus': self.request.get('focus'),
      'next': self.request.get('next'),
      'parent_key': parent_key,
      'parent_kind': parent_kind,
    })

  def post(self):
    kind = self.request.get('kind')
    entity_key = self.request.get('key')
    if entity_key:
      if self.request.get('action') == 'Delete':
        datastore.Delete(datastore.Key(entity_key))
        self.redirect(self.request.get('next'))
        return
      entity = datastore.Get(datastore.Key(entity_key))
    else:
      entity = datastore.Entity(kind)

    args = self.request.arguments()
    for arg in args:
      bar = arg.find('|')
      if bar > 0:
        data_type_name = arg[:bar]
        field_name = arg[bar + 1:]
        form_value = self.request.get(arg)
        data_type = DataType.get_by_name(data_type_name)
        if entity and entity.has_key(field_name):
          old_formatted_value = data_type.format(entity[field_name])
          if old_formatted_value == form_value:
            continue

        if len(form_value) > 0:
          value = data_type.parse(form_value)
          entity[field_name] = value
        elif entity.has_key(field_name):
          del entity[field_name]

    datastore.Put(entity)

    self.redirect(self.request.get('next'))


class DataType(object):
  """A DataType represents a data type in the datastore.

  Each DataType subtype defines four methods:

     format: returns a formatted string for a datastore value
     input_field: returns a string HTML <input> element for this DataType
     name: the friendly string name of this DataType
     parse: parses the formatted string representation of this DataType
     python_type: the canonical Python type for this datastore type

  We use DataType instances to display formatted values in our result lists,
  and we uses input_field/format/parse to generate forms and parse the results
  from those forms to allow editing of entities.
  """
  @staticmethod
  def get(value):
    return _DATA_TYPES[value.__class__]

  @staticmethod
  def get_by_name(name):
    return _NAMED_DATA_TYPES[name]

  def format(self, value):
    return str(value)

  def short_format(self, value):
    return self.format(value)

  def input_field(self, name, value, sample_values):
    if value is not None:
      string_value = self.format(value)
    else:
      string_value = ''
    return '<input class="%s" name="%s" type="text" size="%d" value="%s"/>' % (cgi.escape(self.name()), cgi.escape(name), self.input_field_size(),
            cgi.escape(string_value, True))

  def input_field_size(self):
    return 30


class StringType(DataType):
  def format(self, value):
    return value

  def input_field(self, name, value, sample_values):
    multiline = False
    if value:
      multiline = len(value) > 255 or value.find('\n') >= 0
    if not multiline:
      for sample_value in sample_values:
        if len(sample_value) > 255 or sample_value.find('\n') >= 0:
          multiline = True
          break
    if multiline:
      if not value:
        value = ''
      return '<textarea name="%s" rows="5" cols="50">%s</textarea>' % (cgi.escape(name), cgi.escape(value))
    else:
      return DataType.input_field(self, name, value, sample_values)

  def name(self):
    return 'string'

  def parse(self, value):
    return value

  def python_type(self):
    return str

  def input_field_size(self):
    return 50


class TextType(StringType):
  def name(self):
    return 'Text'

  def input_field(self, name, value, sample_values):
    return '<textarea name="%s" rows="5" cols="50">%s</textarea>' % (cgi.escape(name), cgi.escape(str(value)))

  def parse(self, value):
    return datastore_types.Text(value)

  def python_type(self):
    return datastore_types.Text


class BlobType(StringType):
  def name(self):
    return 'Blob'

  def input_field(self, name, value, sample_values):
    return '&lt;binary&gt;'

  def format(self, value):
    return '<binary>'

  def python_type(self):
    return datastore_types.Blob


class TimeType(DataType):
  _FORMAT = '%Y-%m-%d %H:%M:%S'

  def format(self, value):
    return value.strftime(TimeType._FORMAT)

  def name(self):
    return 'datetime'

  def parse(self, value):
    return datetime.datetime(*(time.strptime(value, TimeType._FORMAT)[0:6]))

  def python_type(self):
    return datetime.datetime


class ListType(DataType):
  def format(self, value):
    value_file = cStringIO.StringIO()
    try:
      writer = csv.writer(value_file)
      writer.writerow(value)
      return value_file.getvalue()
    finally:
      value_file.close()

  def name(self):
    return 'list'

  def parse(self, value):
    value_file = cStringIO.StringIO(value)
    try:
      reader = csv.reader(value_file)
      return reader.next()
    finally:
      value_file.close()

  def python_type(self):
    return list


class BoolType(DataType):
  def name(self):
    return 'bool'

  def input_field(self, name, value, sample_values):
    selected = { None: '', False: '', True: '' };
    selected[value] = "selected"
    return """<select class="%s" name="%s">
    <option %s value=''></option>
    <option %s value='0'>False</option>
    <option %s value='1'>True</option></select>""" % (cgi.escape(self.name()), cgi.escape(name), selected[None],
            selected[False], selected[True])

  def parse(self, value):
    if value.lower() is 'true':
      return True
    if value.lower() is 'false':
      return False
    return bool(int(value))

  def python_type(self):
    return bool


class NumberType(DataType):
  def input_field_size(self):
    return 10


class IntType(NumberType):
  def name(self):
    return 'int'

  def parse(self, value):
    return int(value)

  def python_type(self):
    return int


class LongType(NumberType):
  def name(self):
    return 'long'

  def parse(self, value):
    return long(value)

  def python_type(self):
    return long


class FloatType(NumberType):
  def name(self):
    return 'float'

  def parse(self, value):
    return float(value)

  def python_type(self):
    return float


class UserType(DataType):
  def name(self):
    return 'User'

  def parse(self, value):
    return users.User(value)

  def python_type(self):
    return users.User

  def input_field_size(self):
    return 15

class ReferenceType(DataType):
  def name(self):
    return 'Key'

  def short_format(self, value):
    return str(value)[:8] + '...'

  def parse(self, value):
    return datastore_types.Key(value)

  def python_type(self):
    return datastore_types.Key

  def input_field_size(self):
    return 85


class EmailType(StringType):
  def name(self):
    return 'Email'

  def parse(self, value):
    return datastore_types.Email(value)

  def python_type(self):
    return datastore_types.Email


class CategoryType(StringType):
  def name(self):
    return 'Category'

  def parse(self, value):
    return datastore_types.Category(value)

  def python_type(self):
    return datastore_types.Category


class LinkType(StringType):
  def name(self):
    return 'Link'

  def parse(self, value):
    return datastore_types.Link(value)

  def python_type(self):
    return datastore_types.Link


class GeoPtType(DataType):
  def name(self):
    return 'GeoPt'

  def parse(self, value):
    return datastore_types.GeoPt(value)

  def python_type(self):
    return datastore_types.GeoPt


class ImType(DataType):
  def name(self):
    return 'IM'

  def parse(self, value):
    return datastore_types.IM(value)

  def python_type(self):
    return datastore_types.IM


class PhoneNumberType(StringType):
  def name(self):
    return 'PhoneNumber'

  def parse(self, value):
    return datastore_types.PhoneNumber(value)

  def python_type(self):
    return datastore_types.PhoneNumber


class PostalAddressType(StringType):
  def name(self):
    return 'PostalAddress'

  def parse(self, value):
    return datastore_types.PostalAddress(value)

  def python_type(self):
    return datastore_types.PostalAddress


class RatingType(NumberType):
  def name(self):
    return 'Rating'

  def parse(self, value):
    return datastore_types.Rating(value)

  def python_type(self):
    return datastore_types.Rating


class NoneType(DataType):
  def name(self):
    return 'None'

  def parse(self, value):
    return None

  def format(self, value):
    return 'None'

_DATA_TYPES = {
  types.NoneType: NoneType(),
  types.StringType: StringType(),
  types.UnicodeType: StringType(),
  datastore_types.Text: TextType(),
  datastore_types.Blob: BlobType(),
  types.BooleanType: BoolType(),
  types.IntType: IntType(),
  types.LongType: LongType(),
  types.FloatType: FloatType(),
  datetime.datetime: TimeType(),
  users.User: UserType(),
  datastore_types.Key: ReferenceType(),
  types.ListType: ListType(),
  datastore_types.Email: EmailType(),
  datastore_types.Category: CategoryType(),
  datastore_types.Link: LinkType(),
  datastore_types.GeoPt: GeoPtType(),
  datastore_types.IM: ImType(),
  datastore_types.PhoneNumber: PhoneNumberType(),
  datastore_types.PostalAddress: PostalAddressType(),
  datastore_types.Rating: RatingType(),
}

_NAMED_DATA_TYPES = {}
for data_type in _DATA_TYPES.values():
  _NAMED_DATA_TYPES[data_type.name()] = data_type


def main():
  application = webapp.WSGIApplication([
    ('.*' + DatastoreQueryHandler.PATH, DatastoreQueryHandler),
    ('.*' + DatastoreEditHandler.PATH, DatastoreEditHandler),
    ('.*' + DatastoreBatchEditHandler.PATH, DatastoreBatchEditHandler),
    ('.*' + InteractivePageHandler.PATH, InteractivePageHandler),
    ('.*' + InteractiveExecuteHandler.PATH, InteractiveExecuteHandler),
    ('.*' + MemcachePageHandler.PATH, MemcachePageHandler),
    ('.*' + ImageHandler.PATH, ImageHandler),
    ('.*', DefaultPageHandler),
  ], debug=_DEBUG)
  wsgiref.handlers.CGIHandler().run(application)


import django
if django.VERSION[:2] < (0, 97):
  from django.template import defaultfilters
  def safe(text, dummy=None):
    return text
  defaultfilters.register.filter("safe", safe)


if __name__ == '__main__':
  main()
