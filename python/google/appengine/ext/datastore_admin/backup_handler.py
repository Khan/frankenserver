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


import datetime
import logging
import re
import time
import urllib

from google.appengine.datastore import entity_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import blobstore as blobstore_api
from google.appengine.api import capabilities
from google.appengine.api import datastore
from google.appengine.api import files
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.datastore import datastore_rpc
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import operation as op
from google.appengine.ext.mapreduce import output_writers


XSRF_ACTION = 'backup'


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
    kinds = handler.request.get('kind', allow_multiple=True)
    sizes_known, size_total, remainder = utils.ParseKindsAndSizes(kinds)
    notreadonly_warning = capabilities.CapabilitySet(
        'datastore_v3', capabilities=['write']).is_enabled()
    blob_warning = bool(blobstore.BlobInfo.all().count(1))
    app_id = handler.request.get('app_id')
    template_params = {
        'form_target': DoBackupHandler.SUFFIX,
        'kind_list': kinds,
        'remainder': remainder,
        'sizes_known': sizes_known,
        'size_total': size_total,
        'app_id': app_id,
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
    backup_ids = handler.request.get_all('backup_id')
    if backup_ids:
      backups = db.get(backup_ids)
      backup_ids = [backup.key() for backup in backups]
      backup_names = [backup.name for backup in backups]
    else:
      backup_names = []
      backup_ids = []
    template_params = {
        'form_target': DoBackupDeleteHandler.SUFFIX,
        'app_id': handler.request.get('app_id'),
        'cancel_url': handler.request.get('cancel_url'),
        'backup_ids': backup_ids,
        'backup_names': backup_names,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
    }
    utils.RenderToResponse(handler, 'confirm_delete_backup.html',
                           template_params)


class ConfirmRestoreFromBackupHandler(webapp.RequestHandler):
  """Handler to confirm admin console requests to restore from backup."""

  SUFFIX = 'confirm_restore_from_backup'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    backup_id = handler.request.get('backup_id')
    backup = db.get(backup_id) if backup_id else None
    notreadonly_warning = capabilities.CapabilitySet(
        'datastore_v3', capabilities=['write']).is_enabled()
    app_id = handler.request.get('app_id')
    template_params = {
        'form_target': DoBackupRestoreHandler.SUFFIX,
        'app_id': app_id,
        'queues': None,
        'cancel_url': handler.request.get('cancel_url'),
        'backup': backup,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
        'notreadonly_warning': notreadonly_warning
    }
    utils.RenderToResponse(handler, 'confirm_restore_from_backup.html',
                           template_params)


class BaseDoHandler(webapp.RequestHandler):
  """Base class for all Do*Handlers."""

  MAPREDUCE_DETAIL = utils.config.MAPREDUCE_PATH + '/detail?mapreduce_id='

  def get(self):
    """Handler for get requests to datastore_admin backup operations.

    Status of executed jobs is displayed.
    """
    jobs = self.request.get('job', allow_multiple=True)
    error = self.request.get('error', '')
    xsrf_error = self.request.get('xsrf_error', '')

    template_params = {
        'job_list': jobs,
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
    return str(type(e)) + ": " + str(e)


class DoBackupHandler(BaseDoHandler):
  """Handler to deal with requests from the admin console to backup data."""

  SUFFIX = 'backup.do'
  BACKUP_HANDLER = __name__ + '.BackupEntity.map'
  BACKUP_COMPLETE_HANDLER = __name__ +  '.BackupCompleteHandler'
  INPUT_READER = input_readers.__name__ + '.DatastoreEntityInputReader'
  OUTPUT_WRITER = output_writers.__name__ + '.BlobstoreRecordsOutputWriter'
  _get_html_page = 'do_backup.html'
  _get_post_html_page = SUFFIX

  def _ProcessPostRequest(self):
    """Triggers backup mapper jobs and returns their ids."""
    backup = self.request.get('backup_name').strip()
    if not backup:
      return [('error', 'Unspecified Backup name.')]

    if BackupInformation.name_exists(backup):
      return [('error', 'Backup "%s" already exists.' % backup)]

    kinds = self.request.get('kind', allow_multiple=True)
    queue = self.request.get('queue')

    job_name = 'datastore_backup_%s' % re.sub(r'[^\w]', '_', backup)
    try:
      job_operation = utils.StartOperation('Backup: %s' % backup)
      backup_info = BackupInformation(parent=job_operation)
      backup_info.name = backup
      backup_info.kinds = kinds
      backup_info.put(config=datastore_rpc.Configuration(force_writes=True))
      mapreduce_params = {
          'done_callback_handler': self.BACKUP_COMPLETE_HANDLER,
          'backup_info_pk': str(backup_info.key()),
          'force_ops_writes': True
      }
      jobs = utils.RunMapForKinds(
          job_operation.key(),
          kinds,
          job_name,
          self.BACKUP_HANDLER,
          self.INPUT_READER,
          self.OUTPUT_WRITER,
          self._GetBasicMapperParams(),
          mapreduce_params,
          queue_name=queue)
      backup_info.active_jobs = jobs
      backup_info.put(config=datastore_rpc.Configuration(force_writes=True))
      return [('job', job) for job in jobs]
    except Exception, e:
      logging.exception('Failed to start a datastore backup job "%s".',
                        job_name)
      raise e


class DoBackupDeleteHandler(BaseDoHandler):
  """Handler to deal with datastore admin requests to delete backup data."""

  SUFFIX = 'backup_delete.do'

  def get(self):
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/backup_delete.do.

    Jobs are executed and user is redirected to the base-path handler.
    """
    backup_ids = self.request.get_all('backup_id')
    token = self.request.get('xsrf_token')
    error = None
    if backup_ids and utils.ValidateXsrfToken(token, XSRF_ACTION):
      try:
        for backup_info in db.get(backup_ids):
          if backup_info:
            blobstore_api.delete([files.blobstore.get_blob_key(filename)
                                  for filename in backup_info.blob_files])
            backup_info.delete()
      except Exception, e:
        logging.exception('Failed to delete datastore backup.')
        error = str(e)

    if error:
      self.redirect(utils.config.BASE_PATH + '?error=%s' % error)
    else:
      self.redirect(utils.config.BASE_PATH)


class DoBackupRestoreHandler(BaseDoHandler):
  """Handler to deal with requests from the admin console to backup data."""

  SUFFIX = 'backup_restore.do'
  BACKUP_RESTORE_HANDLER = __name__ + '.RestoreEntity.map'

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
    job_name = 'datastore_backup_%s' % re.sub(r'[^\w]', '_', backup.name)
    try:
      job_operation = utils.StartOperation('Restore from backup: %s'
                                           % backup.name)
      mapper_params = self._GetBasicMapperParams()
      mapper_params['files'] = backup.blob_files
      mapreduce_params = {
          'backup_name': backup.name,
          'force_ops_writes': True
      }
      return [('job', utils.StartMap(
          job_operation.key(),
          job_name,
          self.BACKUP_RESTORE_HANDLER,
          self.INPUT_READER,
          None,
          mapper_params,
          mapreduce_params,
          queue_name=queue))]
    except Exception, e:
      logging.exception('Failed to start a restore from backup job "%s".',
                        job_name)
      raise e


class BackupInformation(db.Model):
  """An entity to keep information on successful backup operations."""

  name = db.StringProperty()
  kinds = db.StringListProperty()
  start_time = db.DateTimeProperty(auto_now_add=True)
  active_jobs = db.StringListProperty()
  completed_jobs = db.StringListProperty()
  complete_time = db.DateTimeProperty()
  blob_files = db.StringListProperty()

  @classmethod
  def kind(cls):
    return '_AE_Backup_Information'

  @classmethod
  def name_exists(cls, backup_name):
    query = BackupInformation.all(keys_only=True)
    query.filter('name =', backup_name)
    return query.get() is not None


@db.transactional
def BackupCompleteHandler(operation, job_id, mapreduce_state):
  """Updates BackupInformation record for a completed mapper job."""
  mapreduce_spec = mapreduce_state.mapreduce_spec
  backup_info = BackupInformation.get(mapreduce_spec.params['backup_info_pk'])
  if backup_info:
    backup_info.blob_files = list(
        set(backup_info.blob_files + mapreduce_state.writer_state['filenames']))
    if job_id in backup_info.active_jobs:
      backup_info.active_jobs.remove(job_id)
      backup_info.completed_jobs = list(
          set(backup_info.completed_jobs + [job_id]))
    if operation.status == utils.DatastoreAdminOperation.STATUS_COMPLETED:
      backup_info.complete_time = datetime.datetime.now()
    backup_info.put(config=datastore_rpc.Configuration(force_writes=True))


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

  def map(self, record):
    """Restore entity map handler.

    Args:
      record: A serialized entity_pb.EntityProto.

    Yields:
      A operation.db.Put for the mapped entity
    """
    pb = entity_pb.EntityProto(contents=record)
    entity = datastore.Entity._FromPb(pb)
    yield op.db.Put(entity)


def get_queue_names(app_id=None):
  """Returns a list with all non-special queue names for app_id."""
  rpc = apiproxy_stub_map.UserRPC('taskqueue')
  request = taskqueue_service_pb.TaskQueueFetchQueuesRequest()
  response = taskqueue_service_pb.TaskQueueFetchQueuesResponse()
  if app_id:
    request.set_app_id(app_id)
  request.set_max_rows(100)
  queues = ['default']
  try:
    rpc.make_call('FetchQueues', request, response)
    rpc.check_success()

    for queue in response.queue_list():
      if (queue.mode() == taskqueue_service_pb.TaskQueueMode.PUSH and
          not queue.queue_name().startswith('__') and
          queue.queue_name() != 'default'):
        queues.append(queue.queue_name())
  except Exception, e:
    logging.exception('Failed to get queue names: %s', str(e))
  return queues


def handlers_list(base_path):
  return [
      (r'%s/%s' % (base_path, ConfirmBackupHandler.SUFFIX),
       ConfirmBackupHandler),
      (r'%s/%s' % (base_path, DoBackupHandler.SUFFIX), DoBackupHandler),
      (r'%s/%s' % (base_path, DoBackupRestoreHandler.SUFFIX),
       DoBackupRestoreHandler),
      (r'%s/%s' % (base_path, DoBackupDeleteHandler.SUFFIX),
       DoBackupDeleteHandler),
      ]
