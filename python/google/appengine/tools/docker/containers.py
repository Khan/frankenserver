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
"""

from collections import namedtuple

import logging


ImageOptions = namedtuple(
    'ImageOptions', [
        # If this is None, no build is needed. We will be looking for the
        # existing image with this tag and raise an error if it does not exist.
        'dockerfile_dir',
        'tag',
        'nocache'
    ]
)
# TODO: add rm option


ContainerOptions = namedtuple(
    'ContainerOptions', [
        'image_opts',
        'port',
        'environment',
        # TODO: use another container to forward logs to
        # instead of mounting host directory.
        'volumes',
        'volumes_from'
    ]
)


class Error(Exception):
  """Base exception for containers module."""


class ImageError(Error):
  """Image related errors."""


class ContainerError(Error):
  """Container related erorrs."""


class BaseImage(object):
  """Abstract base class for Docker images."""

  def __init__(self, docker_client, image_opts):
    """Initializer for BaseImage.

    Args:
      docker_client: an object of docker.Client class to communicate with a
          Docker daemon.
      image_opts: an instance of ImageOptions class describing the parameters
          passed to docker commands.
    """
    self._docker_client = docker_client
    self._image_opts = image_opts
    self._image_id = None

  def Build(self):
    """Calls "docker build" if needed."""
    raise NotImplementedError

  def Remove(self):
    """Calls "docker rmi" if needed."""
    raise NotImplementedError

  @property
  def id(self):
    """Returns 64 hexadecimal digit string identifying the image."""
    return self._image_id

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
    """Calls "docker build"."""
    logging.info('Building image %s...', self.tag)
    self._image_id, _ = self._docker_client.build(
        path=self._image_opts.dockerfile_dir,
        tag=self.tag,
        quiet=False, fileobj=None, nocache=self._image_opts.nocache,
        rm=False, stream=False)
    logging.info('Image %s built.', self.tag)

  def Remove(self):
    """Calls "docker rmi"."""
    if self._image_id:
      self._docker_client.remove_image(self.id)
      self._image_id = None


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
                       'image_id.')

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
      raise ImageError('Image with tag %s was not found', self.tag)

    # TODO: check if it's possible to have more than one image returned.
    self._image_id = images[0]

  def Remove(self):
    """Unassigns image_id only, does not remove the image as we don't own it."""
    self._image_id = None


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
    self._container_id = None
    self._port = None

  def Start(self):
    """Builds an image (if necessary) and runs a container.

    Raises:
      ContainerError: if container_id is already set, i.e. container is already
          started.
    """
    if self._container_id:
      raise ContainerError('Trying to start already running container.')

    self._image.Build()

    logging.info('Creating container...')
    self._container_id = self._docker_client.create_container(
        image=self._image.id, hostname=None, user=None, detach=True,
        stdin_open=False,
        tty=False, mem_limit=0,
        ports=[self._container_opts.port],
        volumes=self._container_opts.volumes.keys(),
        environment=self._container_opts.environment,
        dns=None,
        network_disabled=False, name=None,
        volumes_from=self._container_opts.volumes_from)
    logging.info('Container %s created.', self._container_id)

    self._docker_client.start(
        self._container_id,
        # Assigns a random available docker port
        port_bindings={self._container_opts.port: None},
        binds=self._container_opts.volumes)

    container_info = self._docker_client.inspect_container(self._container_id)
    network_settings = container_info['NetworkSettings']
    self._host = network_settings['IPAddress']
    self._port = int(network_settings['Ports']
                     ['%d/tcp' % self._container_opts.port][0]['HostPort'])

  def Stop(self):
    """Stops a running container, removes it and underlying image if needed."""
    if self._container_id:
      self._docker_client.stop(self._container_id)
      self._docker_client.remove_container(self._container_id, v=False,
                                           link=False)
      self._container_id = None
      self._image.Remove()

  @property
  def host(self):
    """Host the container can be reached at by the host (i.e. client) system."""
    # TODO: make this work when Dockerd is running on GCE.
    return 'localhost'

  @property
  def port(self):
    """Port (on the host system) mapped to the port inside of the container."""
    return self._port

  @property
  def addr(self):
    """An address the container can be reached at by the host system."""
    return '%s:%d' % (self.host, self.port)

  @property
  def container_addr(self):
    """An address the container can be reached at by another container."""
    return '%s:%d' % (self._host, self._container_opts.port)

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
