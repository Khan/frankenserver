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
"""Binary for launching the node.js process.

This is launched using the http_runtime.START_PROCESS_REVERSE flavor. See
http_runtime.py for more information. In short, the runtime config is passed as
a file, and the port is passed as environment variable.
"""

import os
import sys
import time

import google

from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import safe_subprocess


def main():
  # Read the runtime configuration from file.
  config = runtime_config_pb2.Config()
  config.ParseFromString(open(sys.argv[1], 'rb').read())

  # Launch the node process. Note, the port is specified in os.environ.
  node_app_process = safe_subprocess.start_process(
      args=[config.node_config.node_executable_path,
            os.path.join(config.application_root, 'server.js')],
      env=os.environ.copy(),
      cwd=config.application_root,
      stdout=sys.stderr,
  )

  # Wait for the devappserver to kill the process.
  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    pass
  finally:
    sys.stdout.close()
    node_app_process.kill()


if __name__ == '__main__':
  main()
