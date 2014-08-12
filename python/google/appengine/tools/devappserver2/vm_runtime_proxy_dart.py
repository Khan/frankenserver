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
"""Manages a Dart VM Runtime process running inside of a docker container.
"""

import logging
import os
import shutil
import subprocess
import tempfile

import google

from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.devappserver2 import vm_runtime_proxy

DEBUG_PORT = 5858
VM_SERVICE_PORT = 8181
DEV_MODE = 'dev'
DEPLOY_MODE = 'deploy'


class DartVMRuntimeProxy(instance.RuntimeProxy):
  """Manages a Dart VM Runtime process running inside of a docker container.
  """

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
      port_bindings: dict, Additional port bindings from the container.
    """
    super(DartVMRuntimeProxy, self).__init__()
    self._runtime_config_getter = runtime_config_getter
    self._module_configuration = module_configuration

    if not port_bindings:
      port_bindings = {
          VM_SERVICE_PORT: None,
      }

    # Get the Dart configuration.
    runtime_config = self._runtime_config_getter()
    dart_config = runtime_config.vm_config.dart_config

    # Find the 'pub' executable to use.
    if dart_config.dart_sdk:
      self._pub = os.path.join(dart_config.dart_sdk, 'bin', 'pub')
    else:
      self._pub = 'pub'

    # Get 'pub serve' and mode configuration.
    self._pub_serve_host = dart_config.dart_pub_serve_host
    self._pub_serve_port = dart_config.dart_pub_serve_port
    self._mode = dart_config.dart_dev_mode or DEV_MODE

    additional_environment = None
    if self._use_pub_serve:
      pub_serve = 'http://%s:%s' % (self._pub_serve_host, self._pub_serve_port)
      additional_environment = {'DART_PUB_SERVE': pub_serve}

    self._vm_runtime_proxy = vm_runtime_proxy.VMRuntimeProxy(
        docker_client=docker_client,
        runtime_config_getter=runtime_config_getter,
        module_configuration=module_configuration,
        default_port=default_port,
        port_bindings=port_bindings,
        additional_environment=additional_environment)

  def handle(self, environ, start_response, url_map, match, request_id,
             request_type):
    """Handle request to Dart runtime.

    Serves this request by first forwarding it to 'pub serve' if
    configured to be used.  If 'pub serve' cannot be contacted or
    does not have the resource (status 404) the request is forwarded
    to the Dart application instance via HttpProxy.

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
    """

    return self._vm_runtime_proxy.handle(environ, start_response, url_map,
                                         match, request_id, request_type)

  def start(self):
    logging.info('Starting Dart VM Deployment process')

    try:
      application_dir = os.path.abspath(
          self._module_configuration.application_root)

      # - copy the application to a new temporary directy (follow symlinks)
      # - copy the dockerfiles/dart/Dockerfile into the directory
      # - build & deploy the docker container
      with TempDir('dart_deployment_dir') as temp_dir:
        dst_application_dir = os.path.join(temp_dir, 'app')
        try:
          shutil.copytree(application_dir, dst_application_dir)
        except Exception as e:
          for src, unused_dst, unused_error in e.args[0]:
            if os.path.islink(src):
              linkto = os.readlink(src)
              if not os.path.exists(linkto):
                logging.error('Dangling symlink in Dart project. Path ' + src +
                              ' links to ' + os.readlink(src))
          raise

        dst_build_dir = os.path.join(dst_application_dir, 'build')

        if self._is_deployment_mode:
          # Run 'pub build' to generate assets from web/ directory if necessary.
          web_dir = os.path.join(application_dir, 'web')
          if os.path.exists(web_dir):
            subprocess.check_call([self._pub, 'build', '--mode=debug',
                                   'web', '-o', dst_build_dir],
                                  cwd=application_dir)

        self._vm_runtime_proxy.start(dockerfile_dir=dst_application_dir)

      logging.info(
          'To access Dart VM observatory for module {module} '
          'open http://{host}:{port}'.format(
              module=self._module_configuration.module_name,
              host=self._vm_runtime_proxy.ContainerHost(),
              port=self._vm_runtime_proxy.PortBinding(VM_SERVICE_PORT)))

    except Exception as e:
      logging.info('Dart VM Deployment process failed: %s', str(e))
      raise

  def quit(self):
    self._vm_runtime_proxy.quit()

  @property
  def _use_pub_serve(self):
    return self._is_development_mode and self._pub_serve_port

  @property
  def _is_development_mode(self):
    return self._mode == DEV_MODE

  @property
  def _is_deployment_mode(self):
    return self._mode == DEPLOY_MODE


class TempDir(object):

  def __init__(self, prefix=''):
    self._temp_dir = None
    self._prefix = prefix

  def __enter__(self):
    self._temp_dir = tempfile.mkdtemp(self._prefix)
    return self._temp_dir

  def __exit__(self, *_):
    shutil.rmtree(self._temp_dir, ignore_errors=True)
