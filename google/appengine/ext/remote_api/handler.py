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

"""A handler that exports various App Engine services over HTTP.

You can export this handler in your app by adding it directly to app.yaml's
list of handlers:

  handlers:
  - url: /remote_api
    script: $PYTHON_LIB/google/appengine/ext/remote_api/handler.py
    login: admin

Then, you can use remote_api_stub to remotely access services exported by this
handler. See the documentation in remote_api_stub.py for details on how to do
this.

Using this handler without specifying "login: admin" would be extremely unwise.
So unwise that the default handler insists on checking for itself.
"""





import google
import pickle
import sha
import wsgiref.handlers
from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import users
from google.appengine.datastore import datastore_pb
from google.appengine.ext import webapp
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.runtime import apiproxy_errors


class RemoteDatastoreStub(apiproxy_stub.APIProxyStub):
  """Provides a stub that permits execution of stateful datastore queries.

  Some operations aren't possible using the standard interface. Notably,
  datastore RunQuery operations internally store a cursor that is referenced in
  later Next calls, and cleaned up at the end of each request. Because every
  call to ApiCallHandler takes place in its own request, this isn't possible.

  To work around this, RemoteDatastoreStub provides its own implementation of
  RunQuery that immediately returns the query results.
  """

  def _Dynamic_RunQuery(self, request, response):
    """Handle a RunQuery request.

    We handle RunQuery by executing a Query and a Next and returning the result
    of the Next request.
    """
    runquery_response = datastore_pb.QueryResult()
    apiproxy_stub_map.MakeSyncCall('datastore_v3', 'RunQuery',
                                   request, runquery_response)
    next_request = datastore_pb.NextRequest()
    next_request.mutable_cursor().CopyFrom(runquery_response.cursor())
    next_request.set_count(request.limit())
    apiproxy_stub_map.MakeSyncCall('datastore_v3', 'Next',
                                   next_request, response)

  def _Dynamic_Transaction(self, request, response):
    """Handle a Transaction request.

    We handle transactions by accumulating Put requests on the client end, as
    well as recording the key and hash of Get requests. When Commit is called,
    Transaction is invoked, which verifies that all the entities in the
    precondition list still exist and their hashes match, then performs a
    transaction of its own to make the updates.
    """
    tx = datastore_pb.Transaction()
    apiproxy_stub_map.MakeSyncCall('datastore_v3', 'BeginTransaction',
                                   api_base_pb.VoidProto(), tx)

    preconditions = request.precondition_list()
    if preconditions:
      get_request = datastore_pb.GetRequest()
      get_request.mutable_transaction().CopyFrom(tx)
      for precondition in preconditions:
        key = get_request.add_key()
        key.CopyFrom(precondition.key())
      get_response = datastore_pb.GetResponse()
      apiproxy_stub_map.MakeSyncCall('datastore_v3', 'Get', get_request,
                                     get_response)
      entities = get_response.entity_list()
      assert len(entities) == request.precondition_size()
      for precondition, entity in zip(preconditions, entities):
        if precondition.has_hash() != entity.has_entity():
          raise apiproxy_errors.ApplicationError(
              datastore_pb.Error.CONCURRENT_TRANSACTION,
              "Transaction precondition failed.")
        elif entity.has_entity():
          entity_hash = sha.new(entity.entity().Encode()).digest()
          if precondition.hash() != entity_hash:
            raise apiproxy_errors.ApplicationError(
                datastore_pb.Error.CONCURRENT_TRANSACTION,
                "Transaction precondition failed.")

    if request.has_puts():
      put_request = request.puts()
      put_request.mutable_transaction().CopyFrom(tx)
      apiproxy_stub_map.MakeSyncCall('datastore_v3', 'Put',
                                     put_request, response)

    if request.has_deletes():
      delete_request = request.deletes()
      delete_request.mutable_transaction().CopyFrom(tx)
      apiproxy_stub_map.MakeSyncCall('datastore_v3', 'Delete',
                                     delete_request, api_base_pb.VoidProto())

    apiproxy_stub_map.MakeSyncCall('datastore_v3', 'Commit', tx,
                                   api_base_pb.VoidProto())

  def _Dynamic_GetIDs(self, request, response):
    """Fetch unique IDs for a set of paths."""
    for entity in request.entity_list():
      assert entity.property_size() == 0
      assert entity.raw_property_size() == 0
      assert entity.entity_group().element_size() == 0
      lastpart = entity.key().path().element_list()[-1]
      assert lastpart.id() == 0 and not lastpart.has_name()

    tx = datastore_pb.Transaction()
    apiproxy_stub_map.MakeSyncCall('datastore_v3', 'BeginTransaction',
                                   api_base_pb.VoidProto(), tx)

    apiproxy_stub_map.MakeSyncCall('datastore_v3', 'Put', request, response)

    apiproxy_stub_map.MakeSyncCall('datastore_v3', 'Rollback', tx,
                                   api_base_pb.VoidProto())


SERVICE_PB_MAP = {
    'datastore_v3': {
        'Get': (datastore_pb.GetRequest, datastore_pb.GetResponse),
        'Put': (datastore_pb.PutRequest, datastore_pb.PutResponse),
        'Delete': (datastore_pb.DeleteRequest, datastore_pb.DeleteResponse),
        'Count': (datastore_pb.Query, api_base_pb.Integer64Proto),
        'GetIndices': (api_base_pb.StringProto, datastore_pb.CompositeIndices),
    },
    'remote_datastore': {
        'RunQuery': (datastore_pb.Query, datastore_pb.QueryResult),
        'Transaction': (remote_api_pb.TransactionRequest,
                             datastore_pb.PutResponse),
        'GetIDs': (remote_api_pb.PutRequest, datastore_pb.PutResponse),
    },
}


class ApiCallHandler(webapp.RequestHandler):
  """A webapp handler that accepts API calls over HTTP and executes them."""

  LOCAL_STUBS = {
      'remote_datastore': RemoteDatastoreStub('remote_datastore'),
  }

  def CheckIsAdmin(self):
    if not users.is_current_user_admin():
      self.response.set_status(401)
      self.response.out.write(
          "You must be logged in as an administrator to access this.")
      self.response.headers['Content-Type'] = 'text/plain'
      return False
    elif 'X-appcfg-api-version' not in self.request.headers:
      self.response.set_status(403)
      self.response.out.write("This request did not contain a necessary header")
      return False
    return True


  def get(self):
    """Handle a GET. Just show an info page."""
    if not self.CheckIsAdmin():
      return

    page = self.InfoPage()
    self.response.out.write(page)

  def post(self):
    """Handle POST requests by executing the API call."""
    if not self.CheckIsAdmin():
      return

    self.response.headers['Content-Type'] = 'application/octet-stream'
    response = remote_api_pb.Response()
    try:
      request = remote_api_pb.Request()
      request.ParseFromString(self.request.body)
      response_data = self.ExecuteRequest(request)
      response.mutable_response().set_contents(response_data.Encode())
      self.response.set_status(200)
    except Exception, e:
      self.response.set_status(500)
      response.mutable_exception().set_contents(pickle.dumps(e))
    self.response.out.write(response.Encode())

  def ExecuteRequest(self, request):
    """Executes an API invocation and returns the response object."""
    service = request.service_name()
    method = request.method()
    service_methods = SERVICE_PB_MAP.get(service, {})
    request_class, response_class = service_methods.get(method, (None, None))
    if not request_class:
      raise apiproxy_errors.CallNotFoundError()

    request_data = request_class()
    request_data.ParseFromString(request.request().contents())
    response_data = response_class()

    if service in self.LOCAL_STUBS:
      self.LOCAL_STUBS[service].MakeSyncCall(service, method, request_data,
                                             response_data)
    else:
      apiproxy_stub_map.MakeSyncCall(service, method, request_data,
                                     response_data)

    return response_data

  def InfoPage(self):
    """Renders an information page."""
    return """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html><head>
<title>App Engine API endpoint.</title>
</head><body>
<h1>App Engine API endpoint.</h1>
<p>This is an endpoint for the App Engine remote API interface.
Point your stubs (google.appengine.ext.remote_api.remote_api_stub) here.</p>
</body>
</html>"""


def main():
  application = webapp.WSGIApplication([('.*', ApiCallHandler)])
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
