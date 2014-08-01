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
"""Docker image and docker container classes.

In Docker terminology image is a read-only layer that never changes.
Container is created once you start a process in Docker from an Image. Container
consists of read-write layer, plus information about the parent Image, plus
some additional information like its unique ID, networking configuration,
and resource limits.
For more information refer to http://docs.docker.io/.

Mapping to Docker CLI:
Image is a result of "docker build path/to/Dockerfile" command.
Container is a result of "docker run image_tag" command.
ImageOptions and ContainerOptions allow to pass parameters to these commands.

Versions 1.6 and 1.10 of docker remote API are supported.
"""

from collections import namedtuple

import logging
import re
import threading
import urlparse

import google
import docker
import requests


_SUCCESSFUL_BUILD_PATTERN = re.compile(
    r'{"stream":"Successfully built ([a-zA-Z0-9]{12})\\n"}')


class ImageOptions(namedtuple('ImageOptionsT',
                              ['dockerfile_dir', 'tag', 'nocache', 'rm'])):
  """Options for building Docker Images."""

  def __new__(cls, dockerfile_dir=None, tag=None, nocache=False, rm=False):
    """This method is redefined to provide default values for namedtuple.

    Args:
      dockerfile_dir: str, Path to the directory with the Dockerfile. If it is
          None, no build is needed. We will be looking for the existing image
          with the specified tag and raise an error if it does not exist.
      tag: str, Repository name (and optionally a tag) to be applied to the
          image in case of successful build. If dockerfile_dir is None, tag
          is used for lookup of an image.
      nocache: boolean, True if cache should not be used when building the
          image.
      rm: boolean, True if intermediate images should be removed after a
          successful build.

    Returns:
      ImageOptions object.
    """
    return super(ImageOptions, cls).__new__(
        cls, dockerfile_dir=dockerfile_dir, tag=tag, nocache=nocache, rm=rm)


class ContainerOptions(namedtuple('ContainerOptionsT',
                                  ['image_opts', 'port', 'port_bindings',
                                   'environment', 'volumes', 'volumes_from',
                                   'name'])):
  """Options for creating and running Docker Containers."""

  def __new__(cls, image_opts=None, port=None, port_bindings=None,
              environment=None, volumes=None, volumes_from=None, name=None):
    """This method is redefined to provide default values for namedtuple.

    Args:
      image_opts: ImageOptions, properties of underlying Docker Image.
      port: int, Primary port that the process inside of a container is
          listening on. If this port is not part of the port bindings
          specified, a default binding will be added for this port.
      port_bindings: dict, Port bindings for exposing multiple ports. If the
          only binding needed is the default binding of just one port this
          can be None.
      environment: dict, Environment variables.
      volumes: dict,  Volumes to mount from the host system.
      volumes_from: list, Volumes from the specified container(s).
      name: str, Name of a container. Needed for data containers.

    Returns:
      ContainerOptions object.
    """
    return super(ContainerOptions, cls).__new__(
        cls, image_opts=image_opts, port=port, port_bindings=port_bindings,
        environment=environment, volumes=volumes, volumes_from=volumes_from,
        name=name)


class Error(Exception):
  """Base exception for containers module."""


class ImageError(Error):
  """Image related errors."""


class ContainerError(Error):
  """Container related erorrs."""


class DockerDaemonConnectionError(Error):
  """Raised if the docker client can't connect to the docker daemon."""


class BaseImage(object):
  """Abstract base class for Docker images."""

  def __init__(self, docker_client, image_opts):
    """Initializer for BaseImage.

    Args:
      docker_client: an object of docker.Client class to communicate with a
          Docker daemon.
      image_opts: an instance of ImageOptions class describing the parameters
          passed to docker commands.

    Raises:
      DockerDaemonConnectionError: If the docker daemon isn't responding.
    """
    self._docker_client = docker_client
    self._image_opts = image_opts
    self._id = None

    try:
      self._docker_client.ping()
    except requests.exceptions.ConnectionError:
      raise DockerDaemonConnectionError(
          'Couldn\'t connect to the docker daemon at %s. Please check that '
          'the docker daemon is running and that you have specified the '
          'correct docker host.' % self._docker_client.base_url)

  def Build(self):
    """Calls "docker build" if needed."""
    raise NotImplementedError

  def Remove(self):
    """Calls "docker rmi" if needed."""
    raise NotImplementedError

  @property
  def id(self):
    """Returns 64 hexadecimal digit string identifying the image."""
    # Might also be a first 12-characters shortcut.
    return self._id

  @property
  def tag(self):
    """Returns image tag string."""
    return self._image_opts.tag

  def __enter__(self):
    """Makes BaseImage usable with "with" statement."""
    self.Build()
    return self

  # pylint: disable=redefined-builtin
  def __exit__(self, type, value, traceback):
    """Makes BaseImage usable with "with" statement."""
    self.Remove()

  def __del__(self):
    """Makes sure that build artifacts are cleaned up."""
    self.Remove()


class Image(BaseImage):
  """Docker image that requires building and should be removed afterwards."""

  def __init__(self, docker_client, image_opts):
    """Initializer for Image.

    Args:
      docker_client: an object of docker.Client class to communicate with a
          Docker daemon.
      image_opts: an instance of ImageOptions class that must have
          dockerfile_dir set. image_id will be returned by "docker build"
          command.

    Raises:
      ImageError: if dockerfile_dir is not set.
    """
    if not image_opts.dockerfile_dir:
      raise ImageError('dockerfile_dir for images that require building '
                       'must be set.')

    super(Image, self).__init__(docker_client, image_opts)

  def Build(self):
    """Calls "docker build".

    Raises:
      ImageError: if the image could not be built.
    """
    logging.info('Building image %s...', self.tag)

    build_res = self._docker_client.build(
        path=self._image_opts.dockerfile_dir,
        tag=self.tag,
        quiet=False, fileobj=None, nocache=self._image_opts.nocache,
        rm=self._image_opts.rm, stream=False)

    if isinstance(build_res, tuple):
      # Older API returns pair (image_id, warnings)
      self._id, error = build_res
      if not self.id:
        raise ImageError(
            'There was a build error for the image %s. Error: %s' % (self.tag,
                                                                     error))
    else:
      # Newer API returns stream_helper generator. Each message contains output
      # from the build, and the last message contains the status.
      for x in build_res:
        x = x.strip()
        logging.debug(x)
        m = _SUCCESSFUL_BUILD_PATTERN.match(x)
        if m:
          self._id = m.group(1)
          break
      else:
        # There was no line indicating a successful response.
        raise ImageError(
            'There was a build error for the image %s. Error: %s. Run with '
            '\'--verbosity debug\' for more information.' % (self.tag, x))
    if self.id:
      logging.info('Image %s built, id = %s', self.tag, self.id)

  def Remove(self):
    """Calls "docker rmi"."""
    if self._id:
      try:
        self._docker_client.remove_image(self.id)
      except docker.errors.APIError:
        logging.warning('Image %s cannot be removed because it is tagged in '
                        'multiple repositories. Use -f to remove it.', self.id)
      self._id = None


class PrebuiltImage(BaseImage):
  """Prebuilt Docker image. Build and Remove functions are noops."""

  def __init__(self, docker_client, image_opts):
    """Initializer for PrebuiltImage.

    Args:
      docker_client: an object of docker.Client class to communicate with a
          Docker daemon.
      image_opts: an instance of ImageOptions class that must have
          dockerfile_dir not set and tag set.

    Raises:
      ImageError: if image_opts.dockerfile_dir is set or
          image_opts.tag is not set.
    """
    if image_opts.dockerfile_dir:
      raise ImageError('dockerfile_dir for PrebuiltImage must not be set.')

    if not image_opts.tag:
      raise ImageError('PrebuiltImage must have tag specified to find '
                       'image id.')

    super(PrebuiltImage, self).__init__(docker_client, image_opts)

  def Build(self):
    """Searches for pre-built image with specified tag.

    Raises:
      ImageError: if image with this tag was not found.
    """
    logging.info('Looking for image_id for image with tag %s', self.tag)
    images = self._docker_client.images(
        name=self.tag, quiet=True, all=False, viz=False)

    if not images:
      raise ImageError('Image with tag %s was not found' % self.tag)

    # TODO: check if it's possible to have more than one image returned.
    self._id = images[0]

  def Remove(self):
    """Unassigns image_id only, does not remove the image as we don't own it."""
    self._id = None


def CreateImage(docker_client, image_opts):
  """Creates an new object to represent Docker image.

  Args:
    docker_client: an object of docker.Client class to communicate with a
        Docker daemon.
    image_opts: an instance of ImageOptions class.

  Returns:
    New object, subclass of BaseImage class.
  """
  image = Image if image_opts.dockerfile_dir else PrebuiltImage
  return image(docker_client, image_opts)


def GetDockerHost(docker_client):
  parsed_url = urlparse.urlparse(docker_client.base_url)

  # Socket url schemes look like: unix:// or http+unix://.
  # If the user is running docker locally and connecting over a socket, we
  # should just use localhost.
  if 'unix' in parsed_url.scheme:
    return 'localhost'
  return parsed_url.hostname


class Container(object):
  """Docker Container."""

  def __init__(self, docker_client, container_opts):
    """Initializer for Container.

    Args:
      docker_client: an object of docker.Client class to communicate with a
          Docker daemon.
      container_opts: an instance of ContainerOptions class.
    """
    self._docker_client = docker_client
    self._container_opts = container_opts

    self._image = CreateImage(docker_client, container_opts.image_opts)
    self._id = None
    self._host = GetDockerHost(self._docker_client)
    self._container_host = None
    self._port = None
    # Port bindings will be set to a dictionary mapping exposed ports
    # to the interface they are bound to. This will be populated from
    # the container options passed when the container is started.
    self._port_bindings = None

    # Use the daemon flag in case we leak these threads.
    self._logs_listener = threading.Thread(target=self._ListenToLogs)
    self._logs_listener.daemon = True

  def Start(self):
    """Builds an image (if necessary) and runs a container.

    Raises:
      ContainerError: if container_id is already set, i.e. container is already
          started.
    """
    if self.id:
      raise ContainerError('Trying to start already running container.')

    try:
      self._image.Build()
    except ImageError, e:
      logging.error('Error starting container: %s', e)
      raise

    logging.info('Creating container...')
    port_bindings = self._container_opts.port_bindings or {}
    if self._container_opts.port:
      # Add primary port to port bindings if not already specified.
      # Setting its value to None lets docker pick any available port.
      port_bindings[self._container_opts.port] = port_bindings.get(
          self._container_opts.port)

    self._id = self._docker_client.create_container(
        image=self._image.id, hostname=None, user=None, detach=True,
        stdin_open=False,
        tty=False, mem_limit=0,
        ports=port_bindings.keys(),
        volumes=(self._container_opts.volumes.keys()
                 if self._container_opts.volumes else None),
        environment=self._container_opts.environment,
        dns=None,
        network_disabled=False,
        name=self.name)
    # create_container returns a dict sometimes.
    if isinstance(self.id, dict):
      self._id = self.id.get('Id')
    logging.info('Container %s created.', self.id)

    self._docker_client.start(
        self.id,
        port_bindings=port_bindings,
        binds=self._container_opts.volumes,
        # In the newer API version volumes_from got moved from
        # create_container to start. In older version volumes_from option was
        # completely broken therefore we support only passing volumes_from
        # in start.
        volumes_from=self._container_opts.volumes_from)

    self._logs_listener.start()

    if not port_bindings:
      # Nothing to inspect
      return

    container_info = self._docker_client.inspect_container(self._id)
    network_settings = container_info['NetworkSettings']
    self._container_host = network_settings['IPAddress']
    self._port_bindings = {
        port: int(network_settings['Ports']['%d/tcp' % port][0]['HostPort'])
        for port in port_bindings
    }

  def Stop(self):
    """Stops a running container, removes it and underlying image if needed."""
    if self._id:
      self._docker_client.stop(self.id)
      self._docker_client.remove_container(self.id, v=False,
                                           link=False)
      self._id = None
      self._image.Remove()

  def PortBinding(self, port):
    """Get the host binding of a container port.

    Args:
      port: Port inside container.

    Returns:
      Port on the host system mapped to the given port inside of
          the container.
    """
    return self._port_bindings.get(port)

  @property
  def host(self):
    """Host the container can be reached at by the host (i.e. client) system."""
    return self._host

  @property
  def port(self):
    """Port (on the host system) mapped to the port inside of the container."""
    return self._port_bindings[self._container_opts.port]

  @property
  def addr(self):
    """An address the container can be reached at by the host system."""
    return '%s:%d' % (self.host, self.port)

  @property
  def id(self):
    """Returns 64 hexadecimal digit string identifying the container."""
    return self._id

  @property
  def container_addr(self):
    """An address the container can be reached at by another container."""
    return '%s:%d' % (self._container_host, self._container_opts.port)

  @property
  def name(self):
    """String, identifying a container. Required for data containers."""
    return self._container_opts.name

  def _ListenToLogs(self):
    """Logs all output from the docker container.

    The docker.Client.logs method returns a generator that yields log lines.
    This method iterates over that generator and outputs those log lines to
    the devappserver2 logs.
    """
    log_lines = self._docker_client.logs(container=self.id, stream=True)
    for line in log_lines:
      line = line.strip()
      logging.debug('Container: %s: %s', self.id[0:12], line)

  def __enter__(self):
    """Makes Container usable with "with" statement."""
    self.Start()
    return self

  # pylint: disable=redefined-builtin
  def __exit__(self, type, value, traceback):
    """Makes Container usable with "with" statement."""
    self.Stop()

  def __del__(self):
    """Makes sure that all build and run artifacts are cleaned up."""
    self.Stop()
