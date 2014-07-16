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
"""Manages a VM Runtime process running inside of a docker container."""

import os

import google

from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import http_proxy
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.docker import containers


_DOCKER_IMAGE_NAME_FORMAT = '{display}.{module}.{version}'


class Error(Exception):
  """Base class for errors in this module."""


class InvalidEnvVariableError(Error):
  """Raised if an environment variable name or value cannot be supported."""


class VMRuntimeProxy(instance.RuntimeProxy):
  """Manages a VM Runtime process running inside of a docker container."""

  def __init__(self, docker_client, runtime_config_getter,
               module_configuration, default_port=8080, port_bindings=None):
    """Initializer for VMRuntimeProxy.

    Args:
      docker_client: docker.Client object to communicate with Docker daemon.
      runtime_config_getter: A function that can be called without arguments
          and returns the runtime_config_pb2.Config containing the configuration
          for the runtime.
      module_configuration: An application_configuration.ModuleConfiguration
          instance respresenting the configuration of the module that owns the
          runtime.
      default_port: int, main port inside of the container that instance is
          listening on.
      port_bindings: dict, additional ports for debugging.
    """
    super(VMRuntimeProxy, self).__init__()

    self._runtime_config_getter = runtime_config_getter
    self._module_configuration = module_configuration
    self._docker_client = docker_client
    self._default_port = default_port
    self._port_bindings = port_bindings
    self._container = None
    self._proxy = None

  def handle(self, environ, start_response, url_map, match, request_id,
             request_type):
    """Serves request by forwarding it to application instance via HttpProxy.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler matching this request.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Returns:
      Generator of sequence of strings containing the body of the HTTP response.

    Raises:
      InvalidEnvVariableError: if user tried to redefine any of the reserved
          environment variables.
    """
    return self._proxy.handle(environ, start_response, url_map, match,
                              request_id, request_type)

  def _get_instance_logs(self):
    # TODO: Handle docker container's logs
    return ''

  def _instance_died_unexpectedly(self):
    # TODO: Check if container is still up and running
    return False

  def start(self, dockerfile_dir=None):
    runtime_config = self._runtime_config_getter()

    if not dockerfile_dir:
      dockerfile_dir = self._module_configuration.application_root

    # api_host set to 'localhost' won't be accessible from a docker container
    # because container will have it's own 'localhost'.
    # 10.0.2.2 is a special network setup by virtualbox to connect from the
    # guest to the host.
    api_host = runtime_config.api_host
    if runtime_config.api_host in ('0.0.0.0', 'localhost'):
      api_host = '10.0.2.2'

    image_name = _DOCKER_IMAGE_NAME_FORMAT.format(
        # Escape domain if it is present.
        display=self._module_configuration.application_external_name.replace(
            ':', '.'),
        module=self._module_configuration.module_name,
        version=self._module_configuration.major_version)

    environment = {
        'API_HOST': api_host,
        'API_PORT': runtime_config.api_port,
        'GAE_LONG_APP_ID': self._module_configuration.application_external_name,
        'GAE_PARTITION': self._module_configuration.partition,
        'GAE_MODULE_NAME': self._module_configuration.module_name,
        'GAE_MODULE_VERSION': self._module_configuration.major_version,
        'GAE_MINOR_VERSION': self._module_configuration.minor_version,
        'GAE_MODULE_INSTANCE': runtime_config.instance_id,
        'GAE_SERVER_PORT': runtime_config.server_port,
        'MODULE_YAML_PATH': os.path.basename(
            self._module_configuration.config_path)
    }

    # Handle user defined environment variables
    if self._module_configuration.env_variables:
      ev = (environment.viewkeys() &
            self._module_configuration.env_variables.viewkeys())
      if ev:
        raise InvalidEnvVariableError(
            'Environment variables [%s] are reserved for App Engine use' %
            ', '.join(ev))
      environment.update(self._module_configuration.env_variables)

    port_bindings = self._port_bindings if self._port_bindings else {}
    port_bindings.setdefault(self._default_port, None)
    self._container = containers.Container(
        self._docker_client,
        containers.ContainerOptions(
            image_opts=containers.ImageOptions(
                dockerfile_dir=dockerfile_dir,
                tag=image_name,
                nocache=False),
            port=self._default_port,
            port_bindings=port_bindings,
            environment=environment,
            volumes={
                '/var/log/app_engine/app': {'bind': '/var/log/app_engine/app'}
            }
        ))

    self._container.Start()

    self._proxy = http_proxy.HttpProxy(
        host=self._container.host, port=self._container.port,
        instance_died_unexpectedly=self._instance_died_unexpectedly,
        instance_logs_getter=self._get_instance_logs,
        error_handler_file=application_configuration.get_app_error_file(
            self._module_configuration))
    self._proxy.wait_for_connection()

  def quit(self):
    """Kills running container and removes it."""
    self._container.Stop()

  def PortBinding(self, port):
    """Get the host binding of a container port.

    Args:
      port: Port inside container.

    Returns:
      Port on the host system mapped to the given port inside of
          the container.
    """
    return self._container.PortBinding(port)
