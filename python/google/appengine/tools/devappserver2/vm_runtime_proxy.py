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
"""Manages a VM Runtime process running inside of a docker container.
"""

import logging
import socket

import google
import docker

from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import http_proxy
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.docker import containers


class VMRuntimeProxy(instance.RuntimeProxy):
  """Manages a VM Runtime process running inside of a docker container"""

  def __init__(self, docker_client, runtime_config_getter,
               module_configuration):
    """Initializer for VMRuntimeProxy.

    Args:
      docker_client: docker.Client object to communicate with Docker daemon.
      runtime_config_getter: A function that can be called without arguments
          and returns the runtime_config_pb2.Config containing the configuration
          for the runtime.
      module_configuration: An application_configuration.ModuleConfiguration
          instance respresenting the configuration of the module that owns the
          runtime.
    """
    super(VMRuntimeProxy, self).__init__()

    self._runtime_config_getter = runtime_config_getter
    self._module_configuration = module_configuration
    self._docker_client = docker_client
    self._container = None
    self._proxy = None

  def handle(self, environ, start_response, url_map, match, request_id,
             request_type):
    """Serves this request by forwarding it to application instance
    via HttpProxy.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler matching this request.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Yields:
      A sequence of strings containing the body of the HTTP response.
    """
    return self._proxy.handle(environ, start_response, url_map, match,
                              request_id, request_type)

  def _get_instance_logs(self):
    # TODO: Handle docker container's logs
    return ''

  def _instance_died_unexpectedly(self):
    # TODO: Check if container is still up and running
    return False

  def start(self):
    runtime_config = self._runtime_config_getter()

    # api_host set to 'localhost' won't be accessible from a docker container
    # because container will have it's own 'localhost'.
    # TODO: this works only when /etc/hosts is configured properly.
    api_host = socket.gethostbyname(socket.gethostname()) if (
        runtime_config.api_host == '0.0.0.0') else runtime_config.api_host

    # Must be HTTP_PORT from apphosting/ext/vmruntime/vmservice.py
    # TODO: update apphosting/ext/vmruntime/vmservice.py to use
    # env var set here.
    PORT = 8080

    self._container = containers.Container(
        self._docker_client,
        containers.ContainerOptions(
            image_opts=containers.ImageOptions(
                dockerfile_dir=self._module_configuration.application_root,
                tag='vm.%(RUNTIME)s.%(APP_ID)s.%(MODULE)s.%(VERSION)s' % {
                    'APP_ID': self._module_configuration.application,
                    'MODULE': self._module_configuration.module_name,
                    'RUNTIME': self._module_configuration.effective_runtime,
                    'VERSION': self._module_configuration.major_version},
                nocache=False),
            port=PORT,
            environment={
                'API_HOST': api_host,
                'API_PORT': runtime_config.api_port,
                'GAE_LONG_APP_ID':
                    self._module_configuration.application_external_name,
                'GAE_PARTITION': self._module_configuration.partition,
                'GAE_MODULE_NAME': self._module_configuration.module_name,
                'GAE_MODULE_VERSION': self._module_configuration.major_version,
                'GAE_MINOR_VERSION': self._module_configuration.minor_version,
                'GAE_MODULE_INSTANCE': runtime_config.instance_id},
            volumes={'/var/log/app_engine/app': '/var/log/app_engine/app:rw'},
            volumes_from=None))

    self._container.Start()

    self._proxy = http_proxy.HttpProxy(
        host=self._container.host, port=self._container.port,
        instance_died_unexpectedly=self._instance_died_unexpectedly,
        instance_logs_getter=self._get_instance_logs,
        error_handler_file=application_configuration.get_app_error_file(
            self._module_configuration))

  def quit(self):
    """Kills running container and removes it."""
    self._container.Stop()


class VMRuntimeInstanceFactory(instance.InstanceFactory):
  """A factory that creates new VM runtime Instances."""

  SUPPORTS_INTERACTIVE_REQUESTS = True
  FILE_CHANGE_INSTANCE_RESTART_POLICY = instance.ALWAYS

  # Timeout of HTTP request from docker-py client to docker daemon, in seconds.
  DOCKER_D_REQUEST_TIMEOUT = 60

  def __init__(self, request_data, runtime_config_getter, module_configuration):
    """Initializer for VMRuntimeInstanceFactory.

    Args:
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
      runtime_config_getter: A function that can be called without arguments
          and returns the runtime_config_pb2.Config containing the configuration
          for the runtime.
      module_configuration: An application_configuration.ModuleConfiguration
          instance representing the configuration of the module that owns the
          runtime.
    """
    assert runtime_config_getter().vm_config.HasField('docker_daemon_url'), (
        'VM runtime requires docker_daemon_url to be specified')
    super(VMRuntimeInstanceFactory, self).__init__(
        request_data,
        8 if runtime_config_getter().threadsafe else 1, 10)
    self._runtime_config_getter = runtime_config_getter
    self._module_configuration = module_configuration
    docker_daemon_url = runtime_config_getter().vm_config.docker_daemon_url
    self._docker_client = docker.Client(base_url=docker_daemon_url,
                                        version='1.6',
                                        timeout=self.DOCKER_D_REQUEST_TIMEOUT)
    if not self._docker_client:
      logging.error('Couldn\'t connect to docker daemon on %s' %
                    docker_daemon_url)

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

    def runtime_config_getter():
      runtime_config = self._runtime_config_getter()
      runtime_config.instance_id = str(instance_id)
      return runtime_config

    proxy = VMRuntimeProxy(self._docker_client,
                           runtime_config_getter,
                           self._module_configuration)
    return instance.Instance(self.request_data,
                             instance_id,
                             proxy,
                             self.max_concurrent_requests,
                             self.max_background_threads,
                             expect_ready_request)
