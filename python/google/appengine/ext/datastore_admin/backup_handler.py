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





"""Handler for data backup operation.

Generic datastore admin console transfers control to ConfirmBackupHandler
after selection of entities. The ConfirmBackupHandler confirms with user
his choice, enters a backup name and transfers control to
DoBackupHandler. DoBackupHandler starts backup mappers and displays confirmation
page.

This module also contains actual mapper code for backing data over.
"""

from __future__ import with_statement



import cStringIO
import datetime
import itertools
import logging
import os
import re
import time
import urllib
import xml.dom.minidom

from google.appengine.datastore import entity_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import app_identity
from google.appengine.api import blobstore as blobstore_api
from google.appengine.api import capabilities
from google.appengine.api import datastore
from google.appengine.api import files
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.api.files import records
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import webapp
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import operation as op
from google.appengine.ext.mapreduce import output_writers


XSRF_ACTION = 'backup'
BUCKET_PATTERN = (r'^([a-zA-Z0-9]+(\-[a-zA-Z0-9]+)*)'
                  r'(\.([a-zA-Z0-9]+(\-[a-zA-Z0-9]+)*))*$')
MAX_BUCKET_LEN = 222
MIN_BUCKET_LEN = 3
MAX_BUCKET_SEGMENT_LEN = 63
NUM_KINDS_DEFERRED_THRESHOLD = 10
MAX_BLOBS_PER_DELETE = 500


class ConfirmBackupHandler(webapp.RequestHandler):
  """Handler to deal with requests from the admin console to backup data."""

  SUFFIX = 'confirm_backup'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    namespace = handler.request.get('namespace', None)
    has_namespace = namespace is not None
    kinds = handler.request.get_all('kind')
    sizes_known, size_total, remainder = utils.ParseKindsAndSizes(kinds)
    notreadonly_warning = capabilities.CapabilitySet(
        'datastore_v3', capabilities=['write']).is_enabled()
    blob_warning = bool(blobstore.BlobInfo.all().count(1))
    template_params = {
        'form_target': DoBackupHandler.SUFFIX,
        'kind_list': kinds,
        'remainder': remainder,
        'sizes_known': sizes_known,
        'size_total': size_total,
        'queues': None,
        'cancel_url': handler.request.get('cancel_url'),
        'has_namespace': has_namespace,
        'namespace': namespace,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
        'notreadonly_warning': notreadonly_warning,
        'blob_warning': blob_warning,
        'backup_name': 'datastore_backup_%s' % time.strftime('%Y_%m_%d')
    }
    utils.RenderToResponse(handler, 'confirm_backup.html', template_params)


class ConfirmDeleteBackupHandler(webapp.RequestHandler):
  """Handler to confirm admin console requests to delete a backup copy."""

  SUFFIX = 'confirm_delete_backup'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    requested_backup_ids = handler.request.get_all('backup_id')
    backups = []
    gs_warning = False
    if requested_backup_ids:
      for backup in db.get(requested_backup_ids):
        if backup:
          backups.append(backup)
          gs_warning |= backup.filesystem == files.GS_FILESYSTEM
    template_params = {
        'form_target': DoBackupDeleteHandler.SUFFIX,
        'cancel_url': handler.request.get('cancel_url'),
        'backups': backups,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
        'gs_warning': gs_warning
    }
    utils.RenderToResponse(handler, 'confirm_delete_backup.html',
                           template_params)


class ConfirmAbortBackupHandler(webapp.RequestHandler):
  """Handler to confirm admin console requests to abort a backup copy."""

  SUFFIX = 'confirm_abort_backup'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    requested_backup_ids = handler.request.get_all('backup_id')
    backups = []
    if requested_backup_ids:
      for backup in db.get(requested_backup_ids):
        if backup:
          backups.append(backup)
    template_params = {
        'form_target': DoBackupAbortHandler.SUFFIX,
        'cancel_url': handler.request.get('cancel_url'),
        'backups': backups,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION)
    }
    utils.RenderToResponse(handler, 'confirm_abort_backup.html',
                           template_params)


class ConfirmRestoreFromBackupHandler(webapp.RequestHandler):
  """Handler to confirm admin console requests to restore from backup."""

  SUFFIX = 'confirm_restore_from_backup'

  @classmethod
  def Render(cls, handler, default_backup_id=None,
             default_delete_backup_after_restore=False):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
      default_backup_id: default value for handler.request
      default_delete_backup_after_restore: default value for handler.request
    """
    backup_id = handler.request.get('backup_id', default_backup_id)
    backup = db.get(backup_id) if backup_id else None
    notreadonly_warning = capabilities.CapabilitySet(
        'datastore_v3', capabilities=['write']).is_enabled()
    original_app_warning = backup.original_app
    if os.getenv('APPLICATION_ID') == original_app_warning:
      original_app_warning = None
    template_params = {
        'form_target': DoBackupRestoreHandler.SUFFIX,
        'queues': None,
        'cancel_url': handler.request.get('cancel_url'),
        'backup': backup,
        'delete_backup_after_restore': handler.request.get(
            'delete_backup_after_restore', default_delete_backup_after_restore),
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
        'notreadonly_warning': notreadonly_warning,
        'original_app_warning': original_app_warning
    }
    utils.RenderToResponse(handler, 'confirm_restore_from_backup.html',
                           template_params)


class ConfirmBackupImportHandler(webapp.RequestHandler):
  """Handler to import backup information."""

  SUFFIX = 'backup_information'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    gs_handle = handler.request.get('gs_handle')
    error = None if gs_handle else 'Google Cloud Storage path is missing'
    other_backup_info_files = []
    selected_backup_info_file = None
    backup_info_specified = False
    if not error:
      try:
        gs_handle = gs_handle.rstrip()
        bucket_name, prefix = parse_gs_handle(gs_handle)
        validate_gs_bucket_name(bucket_name)
        if not is_accessible_bucket_name(bucket_name):
          raise BackupValidationException(
              'Bucket "%s" is not accessible' % bucket_name)
        if prefix.endswith('.backup_info'):
          prefix = prefix[0:prefix.rfind('/')]
          backup_info_specified = True
        elif prefix and not prefix.endswith('/'):
          prefix += '/'
        for backup_info_file in list_bucket_files(bucket_name, prefix):
          if backup_info_file.endswith('.backup_info'):
            backup_info_file = '/gs/%s/%s' % (bucket_name, backup_info_file)

            if backup_info_specified and backup_info_file == gs_handle:
              selected_backup_info_file = backup_info_file
            else:
              other_backup_info_files.append(backup_info_file)
      except Exception, ex:
        error = 'Failed to read bucket: %s' % ex
    template_params = {
        'error': error,
        'form_target': DoBackupImportHandler.SUFFIX,
        'cancel_url': handler.request.get('cancel_url'),
        'selected_backup_info_file': selected_backup_info_file,
        'other_backup_info_files': other_backup_info_files,
        'backup_info_specified': backup_info_specified,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION)
    }
    utils.RenderToResponse(handler, 'confirm_backup_import.html',
                           template_params)


class BackupInformationHandler(webapp.RequestHandler):
  """Handler to display backup information."""

  SUFFIX = 'backup_information'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    backup_ids = handler.request.get_all('backup_id')
    template_params = {
        'backups': db.get(backup_ids),
        'back_target': handler.request.get('cancel_url'),
    }
    utils.RenderToResponse(handler, 'backup_information.html', template_params)


class BaseDoHandler(webapp.RequestHandler):
  """Base class for all Do*Handlers."""

  MAPREDUCE_DETAIL = utils.config.MAPREDUCE_PATH + '/detail?mapreduce_id='

  def get(self):
    """Handler for get requests to datastore_admin backup operations.

    Status of executed jobs is displayed.
    """
    jobs = self.request.get_all('job')
    tasks = self.request.get_all('task')
    error = self.request.get('error', '')
    xsrf_error = self.request.get('xsrf_error', '')

    template_params = {
        'job_list': jobs,
        'task_list': tasks,
        'mapreduce_detail': self.MAPREDUCE_DETAIL,
        'error': error,
        'xsrf_error': xsrf_error,
        'datastore_admin_home': utils.config.BASE_PATH,
    }
    utils.RenderToResponse(self, self._get_html_page, template_params)

  @property
  def _get_html_page(self):
    """Return the name of the HTML page for HTTP/GET requests."""
    raise NotImplementedError

  @property
  def _get_post_html_page(self):
    """Return the name of the HTML page for HTTP/POST requests."""
    raise NotImplementedError

  def _ProcessPostRequest(self):
    """Process the HTTP/POST request and return the result as parametrs."""
    raise NotImplementedError

  def _GetBasicMapperParams(self):
    return {'namespace': self.request.get('namespace', None)}

  def post(self):
    """Handler for post requests to datastore_admin/backup.do.

    Redirects to the get handler after processing the request.
    """
    token = self.request.get('xsrf_token')

    if not utils.ValidateXsrfToken(token, XSRF_ACTION):
      parameters = [('xsrf_error', '1')]
    else:
      try:
        parameters = self._ProcessPostRequest()


      except Exception, e:
        error = self._HandleException(e)
        parameters = [('error', error)]

    query = urllib.urlencode(parameters)
    self.redirect('%s/%s?%s' % (utils.config.BASE_PATH,
                                self._get_post_html_page,
                                query))

  def _HandleException(self, e):
    """Make exception handling overrideable by tests.

    Args:
      e: The exception to handle.

    Returns:
      The exception error string.
    """
    return '%s: %s' % (type(e), e)


class BackupValidationException(Exception):
  pass


def _perform_backup(kinds,
                    filesystem, gs_bucket_name, backup,
                    queue, mapper_params, max_jobs):
  """Triggers backup mapper jobs.

  Args:
    kinds: a sequence of kind names
    filesystem: files.BLOBSTORE_FILESYSTEM or files.GS_FILESYSTEM
        or None to default to blobstore
    gs_bucket_name: the GS file system bucket in which to store the backup
        when using the GS file system, and otherwise ignored
    backup: the backup name
    queue: the task queue for the backup task
    mapper_params: the mapper parameters
    max_jobs: if backup needs more jobs than this, defer them

  Returns:
    The job or task ids.

  Raises:
    BackupValidationException: On validation error.
    Exception: On other error.
  """
  BACKUP_COMPLETE_HANDLER = __name__ +  '.BackupCompleteHandler'
  BACKUP_HANDLER = __name__ + '.BackupEntity.map'
  INPUT_READER = input_readers.__name__ + '.DatastoreEntityInputReader'
  OUTPUT_WRITER = output_writers.__name__ + '.FileRecordsOutputWriter'

  if not filesystem:
    filesystem = files.BLOBSTORE_FILESYSTEM
  if filesystem == files.GS_FILESYSTEM:

    if not gs_bucket_name:
      raise BackupValidationException('Bucket name missing.')
    bucket_name, path = parse_gs_handle(gs_bucket_name)
    gs_bucket_name = ('%s/%s' % (bucket_name, path)).rstrip('/')
    validate_gs_bucket_name(bucket_name)
    if not is_accessible_bucket_name(bucket_name):
      raise BackupValidationException(
          'Bucket "%s" is not accessible' % bucket_name)
  elif filesystem == files.BLOBSTORE_FILESYSTEM:
    pass
  else:
    raise BackupValidationException('Unknown filesystem "%s".' % filesystem)

  job_name = 'datastore_backup_%s_%%(kind)s' % re.sub(r'[^\w]', '_', backup)
  try:
    job_operation = utils.StartOperation('Backup: %s' % backup)
    backup_info = BackupInformation(parent=job_operation)
    backup_info.filesystem = filesystem
    backup_info.name = backup
    backup_info.kinds = kinds
    backup_info.put(force_writes=True)
    mapreduce_params = {
        'done_callback_handler': BACKUP_COMPLETE_HANDLER,
        'backup_info_pk': str(backup_info.key()),
        'force_ops_writes': True,
    }
    mapper_params = dict(mapper_params)
    mapper_params['filesystem'] = filesystem
    if filesystem == files.GS_FILESYSTEM:
      mapper_params['gs_bucket_name'] = gs_bucket_name
    if len(kinds) <= max_jobs:
      return [('job', job) for job in _run_map_jobs(
          job_operation.key(), backup_info.key(), kinds, job_name,
          BACKUP_HANDLER, INPUT_READER, OUTPUT_WRITER,
          mapper_params, mapreduce_params, queue)]
    else:
      retry_options = taskqueue.TaskRetryOptions(task_retry_limit=1)
      deferred_task = deferred.defer(_run_map_jobs, job_operation.key(),
                                     backup_info.key(), kinds, job_name,
                                      BACKUP_HANDLER, INPUT_READER,
                                      OUTPUT_WRITER,
                                      mapper_params,
                                      mapreduce_params,
                                      queue, _queue=queue,
                                      _url=utils.ConfigDefaults.DEFERRED_PATH,
                                      _retry_options=retry_options)
      return [('task', deferred_task.name)]
  except Exception:
    logging.exception('Failed to start a datastore backup job[s] for "%s".',
                      job_name)
    if backup_info:
      delete_backup_info(backup_info)
    if job_operation:
      job_operation.status = utils.DatastoreAdminOperation.STATUS_FAILED
      job_operation.put(force_writes=True)
    raise


class BackupLinkHandler(webapp.RequestHandler):
  """Handler to deal with requests to the backup link to backup data."""

  SUFFIX = 'backup.create'

  def get(self):
    """Handler for get requests to datastore_admin/backup.create."""
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/backup.create."""
    try:
      backup_prefix = self.request.get('name')
      if not backup_prefix:
        if self.request.headers.get('X-AppEngine-Cron'):
          backup_prefix = 'cron-'
        else:
          backup_prefix = 'link-'
      backup_prefix_with_date = backup_prefix + time.strftime('%Y_%m_%d')
      backup_name = backup_prefix_with_date
      backup_suffix_counter = 1
      while BackupInformation.name_exists(backup_name):
        backup_suffix_counter += 1
        backup_name = backup_prefix_with_date + '-' + str(backup_suffix_counter)
      kinds = self.request.get_all('kind')
      if not kinds:
        self.errorResponse('Backup must include at least one kind.')
        return
      for kind in kinds:
        if not utils.IsKindNameVisible(kind):
          self.errorResponse('Invalid kind %s.' % kind)
          return
      mapper_params = {'namespace': None}
      _perform_backup(kinds,
                      self.request.get('filesystem'),
                      self.request.get('gs_bucket_name'),
                      backup_name,
                      self.request.get('queue'),
                      mapper_params,
                      1000000)
    except Exception, e:
      self.errorResponse(e.message)

  def errorResponse(self, message):
    logging.error('Could not create backup via link: %s', message)
    self.response.set_status(400, message)


class DoBackupHandler(BaseDoHandler):
  """Handler to deal with requests from the admin console to backup data."""

  SUFFIX = 'backup.do'
  _get_html_page = 'do_backup.html'
  _get_post_html_page = SUFFIX

  def _ProcessPostRequest(self):
    """Triggers backup mapper jobs and returns their ids."""
    try:
      backup = self.request.get('backup_name').strip()
      if not backup:
        raise BackupValidationException('Unspecified backup name.')
      if BackupInformation.name_exists(backup):
        raise BackupValidationException('Backup "%s" already exists.' % backup)
      mapper_params = self._GetBasicMapperParams()
      backup_result = _perform_backup(self.request.get_all('kind'),
                                      self.request.get('filesystem'),
                                      self.request.get('gs_bucket_name'),
                                      backup,
                                      self.request.get('queue'),
                                      mapper_params,
                                      10)
      return backup_result
    except BackupValidationException, e:
      return [('error', e.message)]


def _run_map_jobs(job_operation_key,
                  backup_info_key, kinds, job_name, backup_handler,
                  input_reader, output_writer, mapper_params,
                  mapreduce_params, queue):
  """Creates backup/restore MR jobs for the given operation.

  Args:
    job_operation_key: a key of utils.DatastoreAdminOperation entity.
    backup_info_key: a key of BackupInformation entity.
    kinds: a list of kinds to run the M/R for.
    job_name: the M/R job name prefix.
    backup_handler: M/R job completion handler.
    input_reader: M/R input reader.
    output_writer: M/R output writer.
    mapper_params: custom parameters to pass to mapper.
    mapreduce_params: dictionary parameters relevant to the whole job.
    queue: the name of the queue that will be used by the M/R.

  Returns:
    Ids of all started mapper jobs as list of strings.
  """
  backup_info = BackupInformation.get(backup_info_key)
  if not backup_info:
    return []
  jobs = utils.RunMapForKinds(
      job_operation_key,
      kinds,
      job_name,
      backup_handler,
      input_reader,
      output_writer,
      mapper_params,
      mapreduce_params,
      queue_name=queue)
  backup_info.active_jobs = jobs
  backup_info.put(force_writes=True)
  return jobs


def get_backup_files(backup_info, selected_kinds=None):
  """Returns the backup filenames for selected kinds or all if None/Empty."""
  if backup_info.blob_files:

    return backup_info.blob_files
  else:
    kinds_backup_files = backup_info.get_kind_backup_files(selected_kinds)
    return list(itertools.chain(*(
        kind_backup_files.files for kind_backup_files in kinds_backup_files)))


def delete_backup_files(filesystem, backup_files):
  if backup_files:

    if filesystem == files.BLOBSTORE_FILESYSTEM:


      blob_keys = []
      for fname in backup_files:
        blob_key = files.blobstore.get_blob_key(fname)
        if blob_key:
          blob_keys.append(blob_key)
          if len(blob_keys) == MAX_BLOBS_PER_DELETE:
            blobstore_api.delete(blob_keys)
            blob_keys = []
      if blob_keys:
        blobstore_api.delete(blob_keys)


def delete_backup_info(backup_info, delete_files=True):
  """Deletes a backup including its associated files and other metadata."""
  if backup_info.blob_files:
    delete_backup_files(backup_info.filesystem, backup_info.blob_files)
    backup_info.delete(force_writes=True)
  else:
    kinds_backup_files = tuple(backup_info.get_kind_backup_files())
    if delete_files:
      delete_backup_files(backup_info.filesystem, itertools.chain(*(
          kind_backup_files.files for kind_backup_files in kinds_backup_files)))
    db.delete(kinds_backup_files + (backup_info,), force_writes=True)


class DoBackupDeleteHandler(BaseDoHandler):
  """Handler to deal with datastore admin requests to delete backup data."""

  SUFFIX = 'backup_delete.do'

  def get(self):
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/backup_delete.do.

    Deletes are executed and user is redirected to the base-path handler.
    """
    backup_ids = self.request.get_all('backup_id')
    token = self.request.get('xsrf_token')
    error = None
    if backup_ids and utils.ValidateXsrfToken(token, XSRF_ACTION):
      try:
        for backup_info in db.get(backup_ids):
          if backup_info:
            delete_backup_info(backup_info)
      except Exception, e:
        logging.exception('Failed to delete datastore backup.')
        error = str(e)

    if error:
      query = urllib.urlencode([('error', error)])
      self.redirect('%s?%s' % (utils.config.BASE_PATH, query))
    else:
      self.redirect(utils.config.BASE_PATH)


class DoBackupAbortHandler(BaseDoHandler):
  """Handler to deal with datastore admin requests to abort pending backups."""

  SUFFIX = 'backup_abort.do'

  def get(self):
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/backup_abort.do.

    Abort is executed and user is redirected to the base-path handler.
    """
    backup_ids = self.request.get_all('backup_id')
    token = self.request.get('xsrf_token')
    error = None
    if backup_ids and utils.ValidateXsrfToken(token, XSRF_ACTION):
      try:
        for backup_info in db.get(backup_ids):
          if backup_info:
            utils.AbortAdminOperation(backup_info.parent_key())
            delete_backup_info(backup_info)
      except Exception, e:
        logging.exception('Failed to abort pending datastore backup.')
        error = str(e)

    if error:
      self.redirect(utils.config.BASE_PATH + '?error=%s' % error)
    else:
      self.redirect(utils.config.BASE_PATH)


class DoBackupRestoreHandler(BaseDoHandler):
  """Handler to restore backup data.

  Deals with requests from the admin console.
  """
  SUFFIX = 'backup_restore.do'
  BACKUP_RESTORE_HANDLER = __name__ + '.RestoreEntity.map'
  RESTORE_COMPLETE_HANDLER = __name__ + '.RestoreCompleteHandler'

  INPUT_READER = input_readers.__name__ + '.RecordsReader'
  _get_html_page = 'do_restore_from_backup.html'
  _get_post_html_page = SUFFIX

  def _ProcessPostRequest(self):
    """Triggers backup restore mapper jobs and returns their ids."""
    backup_id = self.request.get('backup_id')
    if not backup_id:
      return [('error', 'Unspecified Backup.')]

    backup = db.get(db.Key(backup_id))
    if not backup:
      return [('error', 'Invalid Backup id.')]

    queue = self.request.get('queue')
    job_name = 'datastore_backup_restore_%s' % re.sub(r'[^\w]', '_',
                                                      backup.name)
    job_operation = None
    kinds = set(self.request.get_all('kind'))
    if not (backup.blob_files or kinds):
      return [('error', 'No kinds were selected')]
    backup_kinds = set(backup.kinds)
    difference = kinds.difference(backup_kinds)
    if difference:
      return [('error', 'Backup does not have kind[s] %s' %
               ', '.join(difference))]
    kinds = list(kinds) if len(backup_kinds) != len(kinds) else []
    try:
      operation_name = 'Restoring %s from backup: %s' % (
          ', '.join(kinds) if kinds else 'all', backup.name)
      job_operation = utils.StartOperation(operation_name)
      mapper_params = self._GetBasicMapperParams()
      mapper_params['files'] = get_backup_files(backup, kinds)
      mapper_params['kind_filter'] = kinds
      mapper_params['original_app'] = backup.original_app
      mapreduce_params = {
          'backup_name': backup.name,
          'force_ops_writes': True
      }
      job = utils.StartMap(job_operation.key(), job_name,
                           self.BACKUP_RESTORE_HANDLER, self.INPUT_READER, None,
                           mapper_params, mapreduce_params, queue_name=queue)
      return [('job', job)]
    except Exception:
      logging.exception('Failed to start a restore from backup job "%s".',
                        job_name)
      if job_operation:
        job_operation.status = utils.DatastoreAdminOperation.STATUS_FAILED
        job_operation.put(force_writes=True)
      raise
    finally:



      if self.request.get('delete_backup_after_restore', '').lower() == 'true':
        delete_backup_info(backup, delete_files=False)


class DoBackupImportHandler(BaseDoHandler):
  """Handler to deal with datastore admin requests to import backup info."""

  SUFFIX = 'import_backup.do'

  def get(self):
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/import_backup.do.

    Import is executed and user is redirected to the base-path handler.
    """
    gs_handle = self.request.get('gs_handle')
    token = self.request.get('xsrf_token')
    error = None
    if gs_handle and utils.ValidateXsrfToken(token, XSRF_ACTION):
      try:
        bucket_name, path = parse_gs_handle(gs_handle)
        file_content = get_gs_object(bucket_name, path)
        entities = parse_backup_info_file(file_content)
        original_backup_info = entities.next()
        entity = datastore.Entity(BackupInformation.kind())
        entity.update(original_backup_info)
        backup_info = BackupInformation.from_entity(entity)
        if original_backup_info.key().app() != os.getenv('APPLICATION_ID'):
          backup_info.original_app = original_backup_info.key().app()

        def tx():
          backup_info.put(force_writes=True)
          kind_files_models = []
          for entity in entities:
            kind_files = backup_info.create_kind_backup_files(
                entity.key().name(), entity['files'])
            kind_files_models.append(kind_files)
          db.put(kind_files_models, force_writes=True)
        db.run_in_transaction(tx)
        backup_id = str(backup_info.key())
      except Exception, e:
        logging.exception('Failed to Import datastore backup information.')
        error = str(e)

    if error:
      query = urllib.urlencode([('error', error)])
      self.redirect('%s?%s' % (utils.config.BASE_PATH, query))
    elif self.request.get('Restore'):
      ConfirmRestoreFromBackupHandler.Render(
          self, default_backup_id=backup_id,
          default_delete_backup_after_restore=True)
    else:
      self.redirect(utils.config.BASE_PATH)


class BackupInformation(db.Model):
  """An entity to keep information on successful backup operations."""

  name = db.StringProperty()
  kinds = db.StringListProperty()
  filesystem = db.StringProperty(default=files.BLOBSTORE_FILESYSTEM)
  start_time = db.DateTimeProperty(auto_now_add=True)
  active_jobs = db.StringListProperty()
  completed_jobs = db.StringListProperty()
  complete_time = db.DateTimeProperty(default=None)
  blob_files = db.StringListProperty()
  original_app = db.StringProperty(default=None)
  gs_handle = db.TextProperty(default=None)

  @classmethod
  def kind(cls):
    return utils.BACKUP_INFORMATION_KIND

  @classmethod
  def name_exists(cls, backup_name):
    query = BackupInformation.all(keys_only=True)
    query.filter('name =', backup_name)
    return query.get() is not None

  def create_kind_backup_files_key(self, kind):
    return db.Key.from_path(KindBackupFiles.kind(), kind, parent=self.key())

  def create_kind_backup_files(self, kind, kind_files):
    return KindBackupFiles(key=self.create_kind_backup_files_key(kind),
                           files=kind_files)

  def get_kind_backup_files(self, kinds=None):
    if kinds:
      return db.get([self.create_kind_backup_files_key(kind) for kind in kinds])
    else:
      return KindBackupFiles.all().ancestor(self).run()


class KindBackupFiles(db.Model):
  """An entity to keep files information per kind for a backup.

  A key for this model should created using kind as a name and the associated
  BackupInformation as a parent.
  """
  files = db.StringListProperty(indexed=False)

  @classmethod
  def kind(cls):
    return utils.BACKUP_INFORMATION_FILES_KIND


@db.transactional
def BackupCompleteHandler(operation, job_id, mapreduce_state):
  """Updates BackupInformation record for a completed mapper job."""
  mapreduce_spec = mapreduce_state.mapreduce_spec
  kind = mapreduce_spec.mapper.params['entity_kind']
  backup_info = BackupInformation.get(mapreduce_spec.params['backup_info_pk'])
  if backup_info:
    if job_id in backup_info.active_jobs:
      backup_info.active_jobs.remove(job_id)
      backup_info.completed_jobs = list(
          set(backup_info.completed_jobs + [job_id]))
    filenames = mapreduce_state.writer_state['filenames']


    if backup_info.filesystem == files.BLOBSTORE_FILESYSTEM:
      filenames = drop_empty_files(filenames)
    if backup_info.blob_files:




      backup_info.blob_files = list(set(backup_info.blob_files + filenames))
      backup_info.put(force_writes=True)
    else:
      kind_backup_files = backup_info.get_kind_backup_files([kind])[0]
      if kind_backup_files:
        kind_backup_files.files = list(set(kind_backup_files.files + filenames))
      else:
        kind_backup_files = backup_info.create_kind_backup_files(kind,
                                                                 filenames)
      db.put((backup_info, kind_backup_files), force_writes=True)
    if operation.status == utils.DatastoreAdminOperation.STATUS_COMPLETED:
      deferred.defer(finalize_backup_info, backup_info.key(),
                     mapreduce_spec.mapper.params,
                     _url=utils.ConfigDefaults.DEFERRED_PATH,
                     _transactional=True)
  else:
    logging.warn('BackupInfo was not found for %s',
                 mapreduce_spec.params['backup_info_pk'])


def finalize_backup_info(
    backup_info_pk, mapper_params):
  """Finalize the state of BackupInformation and creates info file for GS."""


  def tx():
    backup_info = BackupInformation.get(backup_info_pk)
    if backup_info:
      backup_info.complete_time = datetime.datetime.now()
      if backup_info.filesystem == files.GS_FILESYSTEM:

        key_str = str(backup_info.key()).replace('/', '_')
        gs_bucket = mapper_params['gs_bucket_name']
        gs_handle = '/gs/%s/%s.backup_info' % (gs_bucket, key_str)
        backup_info.gs_handle = gs_handle
        create_backup_info_file(gs_handle, backup_info)
      backup_info.put(force_writes=True)
      logging.info('Backup %s completed', backup_info.name)
    else:
      logging.warn('Backup %s could not be found', backup_info_pk)
  db.run_in_transaction(tx)


def create_backup_info_file(filename, backup_info):
  """Creates a backup_info_file for the given BackupInformation model."""
  info_file = files.open(files.gs.create(filename), 'a', exclusive_lock=True)
  try:
    with records.RecordsWriter(info_file) as writer:

      writer.write('1')

      writer.write(db.model_to_protobuf(backup_info).SerializeToString())

      for kind_files in backup_info.get_kind_backup_files():
        writer.write(db.model_to_protobuf(kind_files).SerializeToString())
  finally:
    info_file.close(finalize=True)


def parse_backup_info_file(content):
  """Returns entities iterator from a backup_info file content."""
  reader = records.RecordsReader(cStringIO.StringIO(content))
  version = reader.read()
  if version != '1':
    raise IOError('Unsupported version')
  for record in reader:
    yield datastore.Entity.FromPb(record)


@db.non_transactional
def drop_empty_files(filenames):
  """Deletes empty files and returns filenames minus the deleted ones."""
  non_empty_filenames = []
  empty_file_keys = []
  blobs_info = blobstore.BlobInfo.get(
      [files.blobstore.get_blob_key(fn) for fn in filenames])
  for filename, blob_info in itertools.izip(filenames, blobs_info):
    if blob_info:
      if blob_info.size > 0:
        non_empty_filenames.append(filename)
      else:
        empty_file_keys.append(blob_info.key())
  blobstore_api.delete(empty_file_keys)
  return non_empty_filenames


class BackupEntity(object):
  """A class which dumps the entity to the writer."""

  def map(self, entity):
    """Backup entity map handler.

    Args:
      entity: An instance of datastore.Entity.

    Yields:
      A serialized entity_pb.EntityProto as a string
    """
    yield entity.ToPb().SerializeToString()


class RestoreEntity(object):
  """A class which restore the entity to datastore."""

  def __init__(self):
    self.initialized = False
    self.kind_filter = None
    self.app_id = None

  def initialize(self):
    if self.initialized:
      return
    mapper_params = context.get().mapreduce_spec.mapper.params
    kind_filter = mapper_params.get('kind_filter')
    self.kind_filter = set(kind_filter) if kind_filter else None
    original_app = mapper_params.get('original_app')
    if original_app and os.getenv('APPLICATION_ID') != original_app:
      self.app_id = os.getenv('APPLICATION_ID')
    self.initialized = True

  def map(self, record):
    """Restore entity map handler.

    Args:
      record: A serialized entity_pb.EntityProto.

    Yields:
      A operation.db.Put for the mapped entity
    """
    self.initialize()
    pb = entity_pb.EntityProto(contents=record)
    if self.app_id:
      utils.FixKeys(pb, self.app_id)
    entity = datastore.Entity.FromPb(pb)
    if not self.kind_filter or entity.kind() in self.kind_filter:
      yield op.db.Put(entity)
      if self.app_id:
        yield utils.AllocateMaxId(entity.key(), self.app_id)


def validate_gs_bucket_name(bucket_name):
  """Validate the format of the given bucket_name.

  Validation rules are based:
  https://developers.google.com/storage/docs/bucketnaming#requirements

  Args:
    bucket_name: The bucket name to validate.

  Raises:
    BackupValidationException: If the bucket name is invalid.
  """
  if len(bucket_name) > MAX_BUCKET_LEN:
    raise BackupValidationException(
        'Bucket name length should not be longer than %d' % MAX_BUCKET_LEN)
  if len(bucket_name) < MIN_BUCKET_LEN:
    raise BackupValidationException(
        'Bucket name length should be longer than %d' % MIN_BUCKET_LEN)
  if bucket_name.lower().startswith('goog'):
    raise BackupValidationException(
        'Bucket name should not start with a "goog" prefix')
  bucket_elements = bucket_name.split('.')
  for bucket_element in bucket_elements:
    if len(bucket_element) > MAX_BUCKET_SEGMENT_LEN:
      raise BackupValidationException(
          'Segment length of bucket name should not be longer than %d' %
          MAX_BUCKET_SEGMENT_LEN)
  if not re.match(BUCKET_PATTERN, bucket_name):
    raise BackupValidationException('Invalid bucket name "%s"' % bucket_name)


def is_accessible_bucket_name(bucket_name):
  """Returns True if the application has access to the specified bucket."""
  scope = 'https://www.googleapis.com/auth/devstorage.read_write'
  url = 'https://%s.commondatastorage.googleapis.com/' % bucket_name
  auth_token, _ = app_identity.get_access_token(scope)
  result = urlfetch.fetch(url, method=urlfetch.HEAD, headers={
      'Authorization': 'OAuth %s' % auth_token,
      'x-goog-api-version': '2'})
  return result and result.status_code == 200



def parse_gs_handle(gs_handle):
  """Splits [/gs/]?bucket_name[/folder]*[/file]? to (bucket_name, path | '')."""
  if gs_handle.startswith('/'):
    filesystem = gs_handle[1:].split('/', 1)[0]
    if filesystem == 'gs':
      gs_handle = gs_handle[4:]
    else:
      raise BackupValidationException('Unsupported filesystem: %s' % filesystem)
  tokens = gs_handle.split('/', 1)
  return (tokens[0], '') if len(tokens) == 1 else tuple(tokens)


def list_bucket_files(
    bucket_name, prefix, max_keys=1000):
  """Returns a listing of of a bucket that matches the given prefix."""
  scope = 'https://www.googleapis.com/auth/devstorage.read_only'
  url = 'https://%s.commondatastorage.googleapis.com/?' % bucket_name
  query = [('max-keys', max_keys)]
  if prefix:
    query.append(('prefix', prefix))
  url += urllib.urlencode(query)
  auth_token, _ = app_identity.get_access_token(scope)
  result = urlfetch.fetch(url, method=urlfetch.GET, headers={
      'Authorization': 'OAuth %s' % auth_token,
      'x-goog-api-version': '2'})
  if result and result.status_code == 200:
    doc = xml.dom.minidom.parseString(result.content)
    return [node.childNodes[0].data for node in doc.getElementsByTagName('Key')]
  raise BackupValidationException('Request to Google Cloud Storage failed')


def get_gs_object(bucket_name, path):
  """Returns a listing of of a bucket that matches the given prefix."""
  scope = 'https://www.googleapis.com/auth/devstorage.read_only'
  url = 'https://%s.commondatastorage.googleapis.com/%s' % (bucket_name, path)
  auth_token, _ = app_identity.get_access_token(scope)
  result = urlfetch.fetch(url, method=urlfetch.GET, headers={
      'Authorization': 'OAuth %s' % auth_token,
      'x-goog-api-version': '2'})
  if result and result.status_code == 200:
    return result.content
  raise BackupValidationException('Requested path was not found')



def get_queue_names(app_id=None, max_rows=100):
  """Returns a list with all non-special queue names for app_id."""
  rpc = apiproxy_stub_map.UserRPC('taskqueue')
  request = taskqueue_service_pb.TaskQueueFetchQueuesRequest()
  response = taskqueue_service_pb.TaskQueueFetchQueuesResponse()
  if app_id:
    request.set_app_id(app_id)
  request.set_max_rows(max_rows)
  queues = ['default']
  try:
    rpc.make_call('FetchQueues', request, response)
    rpc.check_success()

    for queue in response.queue_list():
      if (queue.mode() == taskqueue_service_pb.TaskQueueMode.PUSH and
          not queue.queue_name().startswith('__') and
          queue.queue_name() != 'default'):
        queues.append(queue.queue_name())
  except Exception:
    logging.exception('Failed to get queue names.')
  return queues


def handlers_list(base_path):
  return [
      (r'%s/%s' % (base_path, BackupLinkHandler.SUFFIX),
       BackupLinkHandler),
      (r'%s/%s' % (base_path, ConfirmBackupHandler.SUFFIX),
       ConfirmBackupHandler),
      (r'%s/%s' % (base_path, DoBackupHandler.SUFFIX), DoBackupHandler),
      (r'%s/%s' % (base_path, DoBackupRestoreHandler.SUFFIX),
       DoBackupRestoreHandler),
      (r'%s/%s' % (base_path, DoBackupDeleteHandler.SUFFIX),
       DoBackupDeleteHandler),
      (r'%s/%s' % (base_path, DoBackupAbortHandler.SUFFIX),
       DoBackupAbortHandler),
      (r'%s/%s' % (base_path, DoBackupImportHandler.SUFFIX),
       DoBackupImportHandler),
      ]
