## Google Cloud Datstore

This is a copy of (the python portion of)
[google-cloud-datastore](https://github.com/GoogleCloudPlatform/google-cloud-datastore),
but with import fixes to make it work in frankenserver.  It's needed for the datastore
translator.

To fix the imports, instead of installing `google.cloud.proto.datastore.v1`
(and a few other packages) from `proto-google-cloud-datastore-v1`, we vendor
the relevant protos into the `genproto` subdirectory, and fix up relevant
imports, e.g. with:
```
sed -i 's/google.\(cloud.proto.datastore.v1\|rpc\|type\)/googledatastore.genproto/g' genproto/*.py
```
For more on the vendored protos, see genproto/README.md.
