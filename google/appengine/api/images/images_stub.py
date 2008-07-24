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

"""Stub version of the images API."""



import logging
import StringIO

import PIL
from PIL import _imaging
from PIL import Image

from google.appengine.api import images
from google.appengine.api.images import images_service_pb
from google.appengine.runtime import apiproxy_errors


class ImagesServiceStub(object):
  """Stub version of images API to be used with the dev_appserver."""

  def __init__(self):
    """Preloads PIL to load all modules in the unhardened environment."""
    Image.init()

  def MakeSyncCall(self, service, call, request, response):
    """Main entry point.

    Args:
      service: str, must be 'images'.
      call: str, name of the RPC to make, must be part of ImagesService.
      request: pb object, corresponding args to the 'call' argument.
      response: pb object, return value for the 'call' argument.
    """
    assert service == "images"
    assert request.IsInitialized()

    attr = getattr(self, "_Dynamic_" + call)
    attr(request, response)

  def _Dynamic_Transform(self, request, response):
    """Trivial implementation of ImagesService::Transform.

    Based off documentation of the PIL library at
    http://www.pythonware.com/library/pil/handbook/index.htm

    Args:
      request: ImagesTransformRequest, contains image request info.
      response: ImagesTransformResponse, contains transformed image.
    """
    image = request.image().content()
    if not image:
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.NOT_IMAGE)

    image = StringIO.StringIO(image)
    try:
      original_image = Image.open(image)
    except IOError:
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_IMAGE_DATA)

    img_format = original_image.format
    if img_format not in ("BMP", "GIF", "ICO", "JPEG", "PNG", "TIFF"):
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.NOT_IMAGE)

    new_image = self._ProcessTransforms(original_image,
                                        request.transform_list())

    response_value = self._EncodeImage(new_image, request.output())
    response.mutable_image().set_content(response_value)

  def _EncodeImage(self, image, output_encoding):
    """Encode the given image and return it in string form.

    Args:
      image: PIL Image object, image to encode.
      output_encoding: ImagesTransformRequest.OutputSettings object.

    Returns:
      str with encoded image information in given encoding format.
    """
    image_string = StringIO.StringIO()

    image_encoding = "PNG"

    if (output_encoding.mime_type() == images_service_pb.OutputSettings.JPEG):
      image_encoding = "JPEG"

      image = image.convert("RGB")

    image.save(image_string, image_encoding)

    return image_string.getvalue()

  def _ValidateCropArg(self, arg):
    """Check an argument for the Crop transform.

    Args:
      arg: float, argument to Crop transform to check.

    Raises:
      apiproxy_errors.ApplicationError on problem with argument.
    """
    if not isinstance(arg, float):
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)

    if not (0 <= arg <= 1.0):
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)

  def _CalculateNewDimensions(self,
                              current_width,
                              current_height,
                              req_width,
                              req_height):
    """Get new resize dimensions keeping the current aspect ratio.

    This uses the more restricting of the two requested values to determine
    the new ratio.

    Args:
      current_width: int, current width of the image.
      current_height: int, current height of the image.
      req_width: int, requested new width of the image.
      req_height: int, requested new height of the image.

    Returns:
      tuple (width, height) which are both ints of the new ratio.
    """

    width_ratio = float(req_width) / current_width
    height_ratio = float(req_height) / current_height

    if req_width == 0 or (width_ratio > height_ratio and req_height != 0):
      return int(height_ratio * current_width), req_height
    else:
      return req_width, int(width_ratio * current_height)

  def _Resize(self, image, transform):
    """Use PIL to resize the given image with the given transform.

    Args:
      image: PIL.Image.Image object to resize.
      transform: images_service_pb.Transform to use when resizing.

    Returns:
      PIL.Image.Image with transforms performed on it.

    Raises:
      BadRequestError if the resize data given is bad.
    """
    width = 0
    height = 0

    if transform.has_width():
      width = transform.width()
      if width < 0 or 4000 < width:
        raise apiproxy_errors.ApplicationError(
            images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)

    if transform.has_height():
      height = transform.height()
      if height < 0 or 4000 < height:
        raise apiproxy_errors.ApplicationError(
            images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)

    current_width, current_height = image.size
    new_width, new_height = self._CalculateNewDimensions(current_width,
                                                         current_height,
                                                         width,
                                                         height)

    return image.resize((new_width, new_height), Image.ANTIALIAS)

  def _Rotate(self, image, transform):
    """Use PIL to rotate the given image with the given transform.

    Args:
      image: PIL.Image.Image object to rotate.
      transform: images_service_pb.Transform to use when rotating.

    Returns:
      PIL.Image.Image with transforms performed on it.

    Raises:
      BadRequestError if the rotate data given is bad.
    """
    degrees = transform.rotate()
    if degrees < 0 or degrees % 90 != 0:
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
    degrees %= 360

    degrees = 360 - degrees
    return image.rotate(degrees)

  def _Crop(self, image, transform):
    """Use PIL to crop the given image with the given transform.

    Args:
      image: PIL.Image.Image object to crop.
      transform: images_service_pb.Transform to use when cropping.

    Returns:
      PIL.Image.Image with transforms performed on it.

    Raises:
      BadRequestError if the crop data given is bad.
    """
    left_x = 0.0
    top_y = 0.0
    right_x = 1.0
    bottom_y = 1.0

    if transform.has_crop_left_x():
      left_x = transform.crop_left_x()
      self._ValidateCropArg(left_x)

    if transform.has_crop_top_y():
      top_y = transform.crop_top_y()
      self._ValidateCropArg(top_y)

    if transform.has_crop_right_x():
      right_x = transform.crop_right_x()
      self._ValidateCropArg(right_x)

    if transform.has_crop_bottom_y():
      bottom_y = transform.crop_bottom_y()
      self._ValidateCropArg(bottom_y)

    width, height = image.size

    box = (int(transform.crop_left_x() * width),
           int(transform.crop_top_y() * height),
           int(transform.crop_right_x() * width),
           int(transform.crop_bottom_y() * height))

    return image.crop(box)

  def _CheckTransformCount(self, transform_map, req_transform):
    """Check that the requested transform hasn't already been set in map.

    Args:
      transform_map: {images_service_pb.ImagesServiceTransform: boolean}, map
        to use to determine if the requested transform has been called.
      req_transform: images_service_pb.ImagesServiceTransform, the requested
        transform.

    Raises:
      BadRequestError if we are passed more than one of the same type of
      transform.
    """
    if req_transform in transform_map:
      raise apiproxy_errors.ApplicationError(
          images_service_pb.ImagesServiceError.BAD_TRANSFORM_DATA)
    transform_map[req_transform] = True

  def _ProcessTransforms(self, image, transforms):
    """Execute PIL operations based on transform values.

    Args:
      image: PIL.Image.Image instance, image to manipulate.
      trasnforms: list of ImagesTransformRequest.Transform objects.

    Returns:
      PIL.Image.Image with transforms performed on it.

    Raises:
      BadRequestError if we are passed more than one of the same type of
      transform.
    """
    new_image = image
    transform_map = {}
    for transform in transforms:
      if transform.has_width() or transform.has_height():
        self._CheckTransformCount(
            transform_map,
            images_service_pb.ImagesServiceTransform.RESIZE
        )

        new_image = self._Resize(new_image, transform)

      elif transform.has_rotate():
        self._CheckTransformCount(
            transform_map,
            images_service_pb.ImagesServiceTransform.ROTATE
        )

        new_image = self._Rotate(new_image, transform)

      elif transform.has_horizontal_flip():
        self._CheckTransformCount(
            transform_map,
            images_service_pb.ImagesServiceTransform.HORIZONTAL_FLIP
        )

        new_image = new_image.transpose(Image.FLIP_LEFT_RIGHT)

      elif transform.has_vertical_flip():
        self._CheckTransformCount(
            transform_map,
            images_service_pb.ImagesServiceTransform.VERTICAL_FLIP
        )

        new_image = new_image.transpose(Image.FLIP_TOP_BOTTOM)

      elif (transform.has_crop_left_x() or
          transform.has_crop_top_y() or
          transform.has_crop_right_x() or
          transform.has_crop_bottom_y()):
        self._CheckTransformCount(
            transform_map,
            images_service_pb.ImagesServiceTransform.CROP
        )

        new_image = self._Crop(new_image, transform)

      elif transform.has_autolevels():
        self._CheckTransformCount(
            transform_map,
            images_service_pb.ImagesServiceTransform.IM_FEELING_LUCKY
        )
        logging.info("I'm Feeling Lucky autolevels will be visible once this "
                     "application is deployed.")
      else:
        logging.warn("Found no transformations found to perform.")

    return new_image
