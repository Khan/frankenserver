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
"""Serves content for "script" handlers using the Node runtime."""

import datetime
import os
import sys
import google
from google.appengine.tools.devappserver2 import http_runtime
from google.appengine.tools.devappserver2 import instance


_RUNTIME_PATH = os.path.abspath(



os.path.join(os.path.dirname(sys.argv[0]), '_node_runtime.py')
    )
_RUNTIME_ARGS = [sys.executable, _RUNTIME_PATH]


class NodeRuntimeInstanceFactory(instance.InstanceFactory):
  """A factory that creates new Node runtime Instances."""

  START_URL_MAP = None
  WARMUP_URL_MAP = None
  SUPPORTS_INTERACTIVE_REQUESTS = False
  FILE_CHANGE_INSTANCE_RESTART_POLICY = instance.AFTER_FIRST_REQUEST

  def __init__(self, request_data, runtime_config_getter, module_configuration):
    """Initializer for NodeRuntimeInstanceFactory.

    Args:
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
      runtime_config_getter: A function that can be called without arguments
          and returns the runtime_config_pb2.Config containing the configuration
          for the runtime.
      module_configuration: An application_configuration.ModuleConfiguration
          instance respresenting the configuration of the module that owns the
          runtime.
    """
    super(NodeRuntimeInstanceFactory, self).__init__(
        request_data,
        8 if runtime_config_getter().threadsafe else 1, 10)
    self._runtime_config_getter = runtime_config_getter
    self._module_configuration = module_configuration

  def new_instance(self, instance_id, expect_ready_request=False):
    """Create and return a new Instance.

    Args:
      instance_id: A string or integer representing the unique (per module) id
          of the instance.
      expect_ready_request: If True then the instance will be sent a special
          request (i.e. /_ah/warmup or /_ah/start) before it can handle external
          requests.

    Returns:
      The newly created instance.Instance.
    """

    def instance_config_getter():
      runtime_config = self._runtime_config_getter()
      runtime_config.instance_id = str(instance_id)
      return runtime_config

    # Note, the PORT will be added to the environment when the HttpRuntimeProxy
    # is started.
    prefix_to_strip = 'dev~'
    app_id = self._module_configuration.application
    if app_id.startswith('dev~'):
      app_id = app_id[len(prefix_to_strip):]

    instance_start_time = datetime.datetime.now().strftime('%Y%m%dt%H%M%S')
    node_environ = {
        'GAE_ENV': 'localdev',
        'GAE_INSTANCE': instance_id,
        'GAE_MEMORY_MB': str(self._module_configuration.memory_limit),
        'GAE_RUNTIME': self._module_configuration.runtime,
        'GAE_SERVICE': self._module_configuration.module_name,
        'GAE_VERSION': (
            self._module_configuration.major_version or instance_start_time),
        # TODO: Determine how to pull the gcloud project from the
        # Cloud SDK.
        'GOOGLE_CLOUD_PROJECT': app_id,
    }

    # Set the runtime config environment variables to pass into the subprocess.
    for env_var in self._runtime_config_getter().environ:
      if env_var.key not in node_environ:
        # We don't allow users to override the standard runtime environment
        # variables. In production, no error is raised, and the standard runtime
        # environment variables take precendence over user-defined variables
        # of the same name.
        node_environ[env_var.key] = env_var.value

    proxy = http_runtime.HttpRuntimeProxy(
        _RUNTIME_ARGS,
        instance_config_getter,
        self._module_configuration,
        env=node_environ,
        start_process_flavor=http_runtime.START_PROCESS_REVERSE)
    return instance.Instance(self.request_data,
                             instance_id,
                             proxy,
                             self.max_concurrent_requests,
                             self.max_background_threads,
                             expect_ready_request)
