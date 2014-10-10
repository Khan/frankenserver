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
"""Exceptions related to Managed VM deployments."""

import logging


class Error(Exception):
  """Base error class for google.appengine.client.services."""
  pass


class PermanentAppError(Error):
  """Base class for app config related errors we are unable to recover from.

  Handlers should catch this type of errors since retrying is of no use.
  """

  def __init__(self, end_user_message, internal_message=None):
    """Constructor.

    Args:
      end_user_message: The message to forward to appcfg so it can be
        displayed to the end user.
      internal_message: (optional) Error message to log as error.
    """
    # Use the base Exception class message field to store the end_user_message.
    super(PermanentAppError, self).__init__(end_user_message)
    self.internal_message = internal_message

  def LogError(self):
    logging.debug('End user message: %s', self.message)
    if self.internal_message:
      logging.error(self.internal_message)


# TODO: Some of these exceptions specify meaningful error messages, while
# others rely on the caller to do so.  We should be consistent about this.

# TODO: Some exceptions here are specific to particular modules,
# while some are generic and applicable across modules.  On one hand, if
# module-specific Exceptions were defined in their respective modules, there is
# no risk of misapplying them in improper places.  On the other hand, keeping
# all errors in one file is convenient, and allows us to avoid having to disable
# catching-non-exception lint errors (caused because pylint doesn't trace the
# inheritance across files).


class TransientError(Error):
  """Base class for transient errors that should lead to a retry of the task."""


class GlobalConfigLoadError(TransientError):
  """Thrown if there was an error when loading the GlobalConfig for the app."""


class RobotSetupError(PermanentAppError):
  """Thrown if there was an error with the robot setup."""


class InvalidBucketConfigurationError(PermanentAppError):
  """Thrown if there is no GCS bucket configured in AdminConfig."""

  def __init__(self):
    # TODO: Improve this with doc links / next steps the user can take.
    PermanentAppError.__init__(
        self,
        'Severe: This app has no associated Google Cloud Storage bucket.',
        'Configuration error: Neither admin_config.vm_config_bigstore_bucket'
        'nor admin_config.default_bigstore_bucket is set. Deployment aborted.')


class InvalidScopeConfigurationError(PermanentAppError):
  """Thrown if there are incompatible storage scopes in vm_settings."""

  def __init__(self):
    PermanentAppError.__init__(
        self,
        'Severe: Invalid storage scope configuration. '
        'Only one of devstorage.read_only, devstorage.read_write, '
        'devstorage.full_control can be used at a time.')


class InvalidRootSetupCommandError(PermanentAppError):
  """Thrown if the root_setup_command format is invalid."""

  def __init__(self):
    PermanentAppError.__init__(
        self,
        'Severe: Invalid root_setup_command format string.'
        'Invalid root_setup_command format string.')


class StaleGlobalConfigError(TransientError):
  """Thrown if the GlobalConfig is older than the requester's."""

  def __init__(self, msg):
    TransientError.__init__(self, msg)


class AppLockError(PermanentAppError):
  """Thrown if there was an error with the AppLock."""

  def __init__(self):
    PermanentAppError.__init__(
        self,
        'An internal error occurred.  Please retry.',
        'Unable to load the AppLock using the provided applock_key.')


class UnknownAppIdError(PermanentAppError):
  """Thrown if the provided app id does not exist."""


class UnknownVersionIdError(PermanentAppError):
  """Thrown if the provided version id does not exist."""


class AdminConfigLoadError(TransientError):
  """Thrown if there was an error when loading the AdminConfig of the app."""


class AppInfoLoadError(TransientError):
  """Thrown if there was an error when loading the AppInfo for the app."""


class GcsWriteError(TransientError):
  """Thrown if there was an error when writing to cloud storage."""


class InvalidLockdownzResponseError(TransientError):
  """Thrown if a lockdownz request to the agent returns an invalid response."""


class InvalidEnvVariableError(PermanentAppError):
  """Thrown if an environment variable name or value cannot be supported."""


class MachineTypeInfoNotFoundError(PermanentAppError):
  """Thrown when the MachineTypeInfo is not found."""


class MachineTypeInfoLoadError(TransientError):
  """Thrown when the MachineTypeInfo can't be loaded."""


class InvalidImageError(PermanentAppError):
  """Thrown if the user requested image can not be found."""


class InvalidVmSettingsError(PermanentAppError):
  """Thrown if the VM settings dictionary contains an invalid key or Value."""


class InvalidDiskSizeConfiguration(InvalidVmSettingsError):
  """Thrown if the user requsted an invalid disk size."""


class GoManifestError(PermanentAppError):
  """Thrown if there is a problem with the Go manifest."""


class ReplicaPoolTimeoutError(TransientError):
  """Thrown if there was a timeout with a ReplicaPool operation."""


class MigrateDuplicateZoneError(PermanentAppError):
  """Thrown if attempted to migrating a replica pool to its existing zone."""


class ReplicaPoolTransientError(TransientError):
  """Thrown if there was an 5xx HttpError from the ReplicaPool service."""


class InvalidInstanceError(PermanentAppError):
  """Thrown by (un)lock method, if deployment or instance could not be found."""


class LockOperationError(PermanentAppError):
  """Thrown by (un)lock method, in case of a downstream failure."""


class OperationAborted(PermanentAppError):
  """Thrown if operation was aborted (AppLock was revoked). Used internally."""


# Errors thrown by api utility classes
class OperationDidNotCompleteError(TransientError):
  """Thrown if an operation did not go to DONE status in time."""
  pass


class OperationFailedError(PermanentAppError):
  """Thrown if an operation threw an error."""

  def __init__(self, message, errors):
    super(OperationFailedError, self).__init__(
        message, internal_message='Operation errors: %s' % str(errors))
    self.errors = errors


class ResourceAlreadyExistsError(PermanentAppError):
  """Thrown if the resource being inserted already exists."""
  pass


class ResourceDoesNotExistError(PermanentAppError):
  """Thrown if the resource being updated/deleted doesn't exist."""
  pass
