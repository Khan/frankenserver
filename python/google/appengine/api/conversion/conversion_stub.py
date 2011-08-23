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




"""Stub version of the Conversion API."""










from google.appengine.api import apiproxy_stub
from google.appengine.api import conversion
from google.appengine.api.conversion import conversion_service_pb
from google.appengine.runtime import apiproxy_errors


__all__ = ["ConversionServiceStub",
           "CONVERTED_FILES_STUB"]





CONVERTED_FILES_STUB = {
    "text/html": "<b>Some &nbsp; data!</b>",
    "text/plain": "Some data!",
    }


def _validate_conversion_request(request):
  """Validates ConversionRequest and throws ConversionServiceError if invalid.

  Args:
    request: A conversion request.

  Raises:
    Application error if the conversion request is invalid.
  """
  if not request.IsInitialized():
    raise apiproxy_errors.ApplicationError(
        conversion_service_pb.ConversionServiceError.INVALID_REQUEST,
        "The conversion request is not initialized correctly")

  if not request.conversion_list():
    raise apiproxy_errors.ApplicationError(
        conversion_service_pb.ConversionServiceError.INVALID_REQUEST,
        "At least one conversion is required in the request")

  if request.conversion_size() > conversion.CONVERSION_MAX_NUM_PER_REQUEST:
    raise apiproxy_errors.ApplicationError(
        conversion_service_pb.ConversionServiceError.TOO_MANY_CONVERSIONS,
        "At most ten conversions are allowed in the request")

  for x in range(0, request.conversion_size()):
    if (request.conversion(x).ByteSize() >
        conversion.CONVERSION_MAX_DOC_SIZE_BYTES):
      raise apiproxy_errors.ApplicationError(
          conversion_service_pb.ConversionServiceError.CONVERSION_TOO_LARGE,
          "Each conversion should not be over 10MB")

    if not request.conversion(x).input().asset_list():
      raise apiproxy_errors.ApplicationError(
          conversion_service_pb.ConversionServiceError.INVALID_REQUEST,
          "At least one asset is required in input document")

    for y in range(0, request.conversion(x).input().asset_size()):
      input_asset = request.conversion(x).input().asset(y)
      if not input_asset.has_data():
        raise apiproxy_errors.ApplicationError(
            conversion_service_pb.ConversionServiceError.INVALID_REQUEST,
            "Asset data field must be set in input document")
      if not input_asset.has_mime_type():
        raise apiproxy_errors.ApplicationError(
            conversion_service_pb.ConversionServiceError.INVALID_REQUEST,
            "Asset mime type field must be set in input document")



    output_mime_type = request.conversion(x).output_mime_type()
    if output_mime_type not in CONVERTED_FILES_STUB:
      raise apiproxy_errors.ApplicationError(
          conversion_service_pb.ConversionServiceError.UNSUPPORTED_CONVERSION,
          "Output mime type %s is not supported" % output_mime_type)


class ConversionServiceStub(apiproxy_stub.APIProxyStub):
  """A stub for the ConversionService API for offline development.

  Provides stub functions which allow a developer to test integration before
  deployment.

  Since there's no obvious way to simulate the conversion service, we will
  simply bundle "canonical" files for each target conversion type and return
  them all the time regardless of the input. For each conversion, we only
  return one asset here.
  """

  def __init__(self, service_name="conversion"):
    """Constructor."""
    apiproxy_stub.APIProxyStub.__init__(self, service_name)

  def _Dynamic_Convert(self, request, response):
    _validate_conversion_request(request)

    for x in range(0, request.conversion_size()):
      result = response.add_result()
      result.set_error_code(conversion_service_pb.ConversionServiceError.OK)
      output_mime_type = request.conversion(x).output_mime_type()
      output_asset = result.mutable_output().add_asset()
      output_asset.set_mime_type(output_mime_type)
      output_asset.set_data(CONVERTED_FILES_STUB[output_mime_type])
      first_input_asset = request.conversion(x).input().asset(0)
      if first_input_asset.has_name():
        output_asset.set_name(first_input_asset.name())
