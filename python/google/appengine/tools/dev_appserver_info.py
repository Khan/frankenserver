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

"""CGI for displaying info about the currently running app in dev_appserver.

This serves pages under /_ah/info/ that display information about the app
currently running in the dev_appserver. It currently serves on these URLs:

  /_ah/info/queries:
    A list of datastore queries run so far, grouped by kind. Used to suggest
    composite indices that should be built.

  /_ah/info/index.yaml:
    Produces an index.yaml file that can be uploaded to the real app
    server by appcfg.py.  This information is derived from the query
    history above, by removing queries that don't need any indexes to
    be built and by combining queries that can use the same index.
"""



import cgi
import wsgiref.handlers

from google.appengine.api import apiproxy_stub_map
from google.appengine.datastore import datastore_pb
from google.appengine.ext import webapp
from google.appengine.tools import dev_appserver_index


class QueriesHandler(webapp.RequestHandler):
  """A handler that displays a list of the datastore queries run so far.
  """

  HEADER = """<html>
<head><title>Query History</title></head>

<body>
<h3>Query History</h3>

<p>This is a list of datastore queries your app has run.  You have to
make composite indices for these queries before deploying your app.
This is normally done automatically by running dev_appserver, which
will write the file index.yaml into your app's root directory, and
then deploying your app with appcfg, which will upload that
index.yaml.</p>

<p>You can also view a 'clean' <a href="index.yaml">index.yaml</a>
file and save that to your app's root directory.</p>

<table>
<tr><th>Times run</th><th>Query</th></tr>
"""

  ROW = """<tr><td>%(count)s</td><td>%(query)s</td></tr>"""

  FOOTER = """
</table>
</body>
</html>"""

  def Render(self):
    """Renders and returns the query history page HTML.

    Returns:
      A string, formatted as an HTML page.
    """
    history = apiproxy_stub_map.apiproxy.GetStub('datastore_v3').QueryHistory()
    history_items = [(count, query) for query, count in history.items()]
    history_items.sort(reverse=True)
    rows = [self.ROW % {'query': _FormatQuery(query),
                        'count': count}
            for count, query in history_items]
    return self.HEADER + '\n'.join(rows) + self.FOOTER

  def get(self):
    """Handle a GET.  Just calls Render()."""
    self.response.out.write(self.Render())


class IndexYamlHandler(webapp.RequestHandler):
  """A handler that renders an index.yaml file suitable for upload."""

  def Render(self):
    """Renders and returns the index.yaml file.

    Returns:
      A string, formatted as an index.yaml file.
    """
    datastore_stub = apiproxy_stub_map.apiproxy.GetStub('datastore_v3')
    query_history = datastore_stub.QueryHistory()
    body = dev_appserver_index.GenerateIndexFromHistory(query_history)
    return 'indexes:\n' + body

  def get(self):
    """Handle a GET.  Just calls Render()."""
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(self.Render())


def _FormatQuery(query):
  """Format a Query protobuf as (very simple) HTML.

  Args:
    query: A datastore_pb.Query instance.

  Returns:
    A string containing formatted HTML.  This is mostly the output of
    str(query) with '<' etc. escaped, and '<br>' inserted in front of
    Order and Filter parts.
  """
  res = cgi.escape(str(query))
  res = res.replace('Order', '<br>Order')
  res = res.replace('Filter', '<br>Filter')
  return res


def _DirectionToString(direction):
  """Turn a direction enum into a string.

  Args:
    direction: ASCENDING or DESCENDING

  Returns:
    Either 'asc' or 'descending'.
  """
  if direction == datastore_pb.Query_Order.DESCENDING:
    return 'descending'
  else:
    return 'asc'


URL_MAP = {
  '/_ah/info/queries': QueriesHandler,
  '/_ah/info/index.yaml': IndexYamlHandler,

}


def main():
  application = webapp.WSGIApplication(URL_MAP.items())
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
