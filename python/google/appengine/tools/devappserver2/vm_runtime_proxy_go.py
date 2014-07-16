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
"""Manages a Go VM Runtime process running inside of a docker container.
"""

import logging
import os
import shutil
import tempfile

import google

from google.appengine.tools.devappserver2 import go_application
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.devappserver2 import vm_runtime_proxy

DEBUG_PORT = 5858
VM_SERVICE_PORT = 8181
DEFAULT_DOCKER_FILE = """FROM google/golang
ADD . /app
RUN /app/_ah/build.sh

EXPOSE 8080
CMD []
WORKDIR /app
ENTRYPOINT ["/app/_ah/exe"]
"""

# Where to look for go-app-builder, which is needed for copying
# into the Docker image for building the Go App Engine app.
# There is no need to add '.exe' here because it is always a Linux executable.
_GO_APP_BUILDER = os.path.join(
    go_application.GOROOT, 'pkg', 'tool', 'linux_amd64', 'go-app-builder')


class GoVMRuntimeProxy(instance.RuntimeProxy):
  """Manages a Go VM Runtime process running inside of a docker container.

  The Go VM Runtime forwards all requests to the Go application instance.
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
    super(GoVMRuntimeProxy, self).__init__()
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

  def handle(self, environ, start_response, url_map, match, request_id,
             request_type):
    """Handle request to Go runtime.

    Serves this request by forwarding to the Go application instance via
    HttpProxy.

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

    it = self._vm_runtime_proxy.handle(environ, start_response, url_map,
                                       match, request_id, request_type)
    for data in it:
      yield data

  def start(self):
    logging.info('Starting Go VM Deployment process')

    try:
      application_dir = os.path.abspath(
          self._module_configuration.application_root)

      # - copy the application to a new temporary directory (follow symlinks)
      # - copy used parts of $GOPATH to the temporary directory
      # - copy or create a Dockerfile in the temporary directory
      # - build & deploy the docker container
      with TempDir('go_deployment_dir') as temp_dir:
        dst_deployment_dir = temp_dir
        dst_application_dir = temp_dir
        try:
          _copytree(application_dir, dst_application_dir,
                    self._module_configuration.skip_files)
        except shutil.Error as e:
          logging.error('Error copying tree: %s', e)
          for src, unused_dst, unused_error in e.args[0]:
            if os.path.islink(src):
              linkto = os.readlink(src)
              if not os.path.exists(linkto):
                logging.error('Dangling symlink in Go project. '
                              'Path %s links to %s', src, os.readlink(src))
          raise
        except OSError as e:
          logging.error('Failed to copy dir: %s', e.strerror)
          raise

        extras = go_application.get_app_extras_for_vm(
            self._module_configuration)
        for dest, src in extras:
          try:
            dest = os.path.join(dst_deployment_dir, dest)
            dirname = os.path.dirname(dest)
            if not os.path.exists(dirname):
              os.makedirs(dirname)
            shutil.copy(src, dest)
          except OSError as e:
            logging.error('Failed to copy %s to %s', src, dest)
            raise

        # Make the _ah subdirectory for the app engine tools.
        ah_dir = os.path.join(dst_deployment_dir, '_ah')
        try:
          os.mkdir(ah_dir)
        except OSError as e:
          logging.error('Failed to create %s: %s', ah_dir, e.strerror)
          raise

        # Copy gab.
        try:
          gab_dest = os.path.join(ah_dir, 'gab')
          shutil.copy(_GO_APP_BUILDER, gab_dest)
        except OSError as e:
          logging.error('Failed to copy %s to %s', _GO_APP_BUILDER, gab_dest)
          raise

        # Write build script.
        nobuild_files = '^' + str(self._module_configuration.nobuild_files)
        gab_args = [
            '/app/_ah/gab',
            '-app_base', '/app',
            '-arch', '6',
            '-dynamic',
            '-goroot', '/goroot',
            '-nobuild_files', nobuild_files,
            '-unsafe',
            '-binary_name', '_ah_exe',
            '-work_dir', '/tmp/work',
            '-vm',
        ]
        gab_args.extend(
            go_application.list_go_files(self._module_configuration))
        gab_args.extend([x[0] for x in extras])
        dst_build = os.path.join(ah_dir, 'build.sh')
        with open(dst_build, 'w') as fd:
          fd.write('#!/bin/bash\n')
          fd.write('set -e\n')
          fd.write('mkdir -p /tmp/work\n')
          fd.write(' '.join(gab_args) + '\n')
          fd.write('mv /tmp/work/_ah_exe /app/_ah/exe\n')
          fd.write('rm -rf /tmp/work\n')
          fd.write('echo Done.\n')
        os.chmod(dst_build, 0777)

        # Write default Dockerfile if none found.
        dst_dockerfile = os.path.join(dst_application_dir, 'Dockerfile')
        if not os.path.exists(dst_dockerfile):
          with open(dst_dockerfile, 'w') as fd:
            fd.write(DEFAULT_DOCKER_FILE)

        self._vm_runtime_proxy.start(dockerfile_dir=dst_deployment_dir)

      logging.info(
          'GoVM vmservice available at http://127.0.0.1:%s/ !',
          self._vm_runtime_proxy.PortBinding(VM_SERVICE_PORT))

    except Exception as e:
      logging.info('Go VM Deployment process failed: %s', str(e))
      raise

  def quit(self):
    self._vm_runtime_proxy.quit()


class TempDir(object):
  """Creates a temporary directory."""

  def __init__(self, prefix=''):
    self._temp_dir = None
    self._prefix = prefix

  def __enter__(self):
    self._temp_dir = tempfile.mkdtemp(self._prefix)
    return self._temp_dir

  def __exit__(self, *_):
    shutil.rmtree(self._temp_dir, ignore_errors=True)


def _copytree(src, dst, skip_files, symlinks=False):
  """Copies src tree to dst (except those matching skip_files).

  Args:
    src: string name of source directory to copy from.
    dst: string name of destination directory to copy to.
    skip_files: RegexStr of files to skip from appinfo.py.
    symlinks: optional bool determines if symbolic links are followed.
  """
  # Ignore files that match the skip_files RegexStr.
  # TODO: skip_files expects the full path relative to the app root, so
  # this may need fixing.
  def ignored_files(unused_dir, filenames):
    return [filename for filename in filenames if skip_files.match(filename)]

  for item in os.listdir(src):
    s = os.path.join(src, item)
    if skip_files.match(item):
      logging.info('skipping file %s', s)
      continue
    d = os.path.join(dst, item)
    if os.path.isdir(s):
      shutil.copytree(s, d, symlinks, ignore=ignored_files)
    else:
      shutil.copy2(s, d)
