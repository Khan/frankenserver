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

from google.appengine.tools.devappserver2 import http_proxy
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.devappserver2 import vm_runtime_proxy

DEBUG_PORT = 5858
VM_SERVICE_PORT = 8181
DEV_MODE = 'dev'
DEPLOY_MODE = 'deploy'
DEFAULT_PUB_SERVE_HOST = '127.0.0.1'
DEFAULT_DOCKER_FILE = 'FROM google/appengine-dart'


class DartVMRuntimeProxy(instance.RuntimeProxy):
  """Manages a Dart VM Runtime process running inside of a docker container.

  The Dart VM Runtime can run in two modes:

    Development
    Deployment

  When in development mode this proxy will first try to forward
  requests to 'pub serve' for asset transformation. If 'pub serve'
  does not have the resource the request is forwarded to the Dart
  application instance running in the container.

  When in deployment mode all requests are forwarded to the Dart
  application instance.

  When building the container there is also a difference between
  development mode and depolyment mode. In deployment mode 'pub build'
  is run on the 'web' directory to produce the 'build' directory. In
  development mode this step is skipped and the resources which would
  otherwise be in the 'build' directory are produced by 'pub serve'.
  """

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
    super(DartVMRuntimeProxy, self).__init__()
    self._runtime_config_getter = runtime_config_getter
    self._module_configuration = module_configuration
    port_bindings = {
        DEBUG_PORT: None,
        VM_SERVICE_PORT: None,
    }
    self._vm_runtime_proxy = vm_runtime_proxy.VMRuntimeProxy(
        docker_client=docker_client,
        runtime_config_getter=runtime_config_getter,
        module_configuration=module_configuration,
        port_bindings=port_bindings)

    # Get the Dart configuration.
    runtime_config = self._runtime_config_getter()
    dart_config = runtime_config.vm_config.dart_config

    # Find the 'pub' executable to use.
    if dart_config.dart_sdk:
      self._pub = os.path.join(dart_config.dart_sdk, 'bin', 'pub')
    else:
      self._pub = 'pub'
    self._pub_serve_proxy = None

    # Get 'pub serve' and mode configuration.
    self._pub_serve_host = (dart_config.dart_pub_serve_host
                            or DEFAULT_PUB_SERVE_HOST)
    self._pub_serve_port = dart_config.dart_pub_serve_port
    self._mode = dart_config.dart_dev_mode or DEV_MODE

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

    Yields:
      A sequence of strings containing the body of the HTTP response.
    """

    # Variable which can be mutated in pub_start_response.
    found_in_pub = [False]

    def pub_start_response(status, response_headers, exc_info=None):
      if len(status) >= 3 and status[:3] != '404':
        found_in_pub[0] = True
        start_response(status, response_headers, exc_info)
      else:
        found_in_pub[0] = False

    # Proxy directly to the application instance if 'pub serve' is not
    # used or if this is an internal request.
    if self._pub_serve_proxy is None or environ['PATH_INFO'][:5] == '/_ah/':
      it = self._vm_runtime_proxy.handle(environ, start_response, url_map,
                                         match, request_id, request_type)
      for data in it:
        yield data
    else:
      # If 'pub serve' is used try to proxy to that. The function handle
      # is a generator. Therefore if there is a socket connection error
      # the exception will be throws when next() is called.
      try:
        it = self._pub_serve_proxy.handle(environ, pub_start_response, url_map,
                                          match, request_id, request_type)
        # If the resource was found in 'pub serve' forward the
        # data. Otherwise get the resource from the application
        # instance.
        first = True
        for data in it:
          if found_in_pub[0]:
            yield data
          else:
            if first:
              first = False
              it = self._vm_runtime_proxy.handle(environ, start_response,
                                                 url_map, match,
                                                 request_id, request_type)
              for data in it:
                yield data
      except IOError as e:
        # If there was an exception connecting to 'pub serve' get the
        # resource from the application instance.
        logging.error("Cannot access 'pub serve': %s", str(e))
        it = self._vm_runtime_proxy.handle(environ, start_response, url_map,
                                           match, request_id, request_type)
        for data in it:
          yield data

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

        dst_dockerfile = os.path.join(dst_application_dir, 'Dockerfile')
        dst_build_dir = os.path.join(dst_application_dir, 'build')

        # Write default Dockerfile if none found.
        if not os.path.exists(dst_dockerfile):
          with open(dst_dockerfile, 'w') as fd:
            fd.write(DEFAULT_DOCKER_FILE)

        if self._is_deployment_mode:
          # Run 'pub build' to generate assets from web/ directory if necessary.
          web_dir = os.path.join(application_dir, 'web')
          if os.path.exists(web_dir):
            subprocess.check_call([self._pub, 'build', '--mode=debug',
                                   'web', '-o', dst_build_dir],
                                  cwd=application_dir)

        self._vm_runtime_proxy.start(dockerfile_dir=dst_application_dir)

      logging.info('DartVM debugger available at 127.0.0.1:%s !',
                   self._vm_runtime_proxy.PortBinding(DEBUG_PORT))
      logging.info(
          'DartVM vmservice available at http://127.0.0.1:%s/ !',
          self._vm_runtime_proxy.PortBinding(VM_SERVICE_PORT))

      if self._use_pub_serve:
        self._pub_serve_proxy = http_proxy.HttpProxy(
            host=self._pub_serve_host, port=self._pub_serve_port,
            instance_died_unexpectedly=self._pub_died_unexpectedly,
            instance_logs_getter=self._get_pub_logs,
            error_handler_file=None)

    except Exception as e:
      logging.info('Dart VM Deployment process failed: %s', str(e))
      raise

  def quit(self):
    self._vm_runtime_proxy.quit()

  def _get_pub_logs(self):
    # There is no log available from pub.
    return ''

  def _pub_died_unexpectedly(self):
    # Return false to make the HTTP proxy throw on errors.
    return False

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
