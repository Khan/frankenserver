# Protos for the Google Cloud Datastore API v1

In this directory we keep the compiled python genproto files for the Google
Cloud  Datastore API.  These describe the structure of the protobuf-over-HTTP
API that the official Google clients use.  They are generated from the protos
available [on GitHub](https://github.com/googleapis/googleapis/).

Generating these so as to fit them into Frankenserver is a bit of a doozy --
they want to be called `google.cloud.datastore.v1.datastore_pb2` and so on, but
getting this import path to play nice with Frankenserver would be require
meddling with namespace packages or other forces beyond our control.  Instead, we just rewrite the files to use a different path inside genproto.

To wit, I ran approximately the following commands:
```
protoc google/api/http.proto google/api/annotations.proto google/rpc/code.proto google/rpc/status.proto google/type/latlng.proto google/datastore/v1/*.proto --python_out=/path/to/frankenserver/python/google/appengine/tools/devappserver2/datastore_translator/genproto
cd /path/to/frankenserver/python/google/appengine/tools/devappserver2/datastore_translator/genproto
mv google/*/*_pb2.py google/*/*/*_pb2.py .
rm -r google
sed -i 's/from google\.\(api\|datastore\.v1\|type\) //' *_pb2.py
```
The list of protos is those which we import, as well as all of their dependencies -- sadly I haven't found a way to get protoc or bazel to resolve those deps but the tree is not very big.

TODO(benkraft): Figure out a more reasonable way to generate these.
