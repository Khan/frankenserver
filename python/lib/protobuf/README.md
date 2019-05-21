# Hack to grab just protobuf from grpcio

This directory exists as a hack to allow us to grab just the `google.protobuf`
directory from `grpcio`, without bringing in the rest.  This is useful because
`grpc` may not be compiled for our current system, but `google.protobuf` will
still be usable via the pure-python implementation.  (Well, with some tricks it
will: see `python/wrapper_util.py` for more.)
