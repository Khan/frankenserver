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

"""Stub version of the Task Queue API.

This stub only stores tasks; it doesn't actually run them. It also validates
the tasks by checking their queue name against the queue.yaml.

As well as implementing Task Queue API functions, the stub exposes various other
functions that are used by the dev_appserver's admin console to display the
application's queues and tasks.
"""



import base64
import datetime
import os

import taskqueue_service_pb

from google.appengine.api import apiproxy_stub
from google.appengine.api import queueinfo
from google.appengine.api import urlfetch
from google.appengine.runtime import apiproxy_errors


DEFAULT_RATE = '5.00/s'

DEFAULT_BUCKET_SIZE = 5


def _ParseQueueYaml(unused_self, root_path):
  """Load the queue.yaml file and parse it."""
  if root_path is None:
    return None
  for queueyaml in ('queue.yaml', 'queue.yml'):
    try:
      fh = open(os.path.join(root_path, queueyaml), 'r')
    except IOError:
      continue
    try:
      queue_info = queueinfo.LoadSingleQueue(fh)
      return queue_info
    finally:
      fh.close()
  return None


def _CompareEta(a, b):
  """Python sort comparator for task ETAs."""
  if a.eta_usec() > b.eta_usec():
    return 1
  if a.eta_usec() < b.eta_usec():
    return -1
  return 0


def _FormatEta(eta_usec):
  """Formats a task ETA as a date string in UTC."""
  eta = datetime.datetime.fromtimestamp(eta_usec/1000000)
  return eta.strftime('%Y/%m/%d %H:%M:%S')


def _EtaDelta(eta_usec):
  """Formats a task ETA as a relative time string."""
  eta = datetime.datetime.fromtimestamp(eta_usec/1000000)
  now = datetime.datetime.utcnow()
  if eta > now:
    return str(eta - now) + ' from now'
  else:
    return str(now - eta) + ' ago'


class TaskQueueServiceStub(apiproxy_stub.APIProxyStub):
  """Python only task queue service stub.

  This stub does not attempt to automatically execute tasks.  Instead, it
  stores them for display on a console.  The user may manually execute the
  tasks from the console.
  """

  queue_yaml_parser = _ParseQueueYaml

  def __init__(self, service_name='taskqueue', root_path=None):
    """Constructor.

    Args:
      service_name: Service name expected for all calls.
      root_path: Root path to the directory of the application which may contain
        a queue.yaml file. If None, then it's assumed no queue.yaml file is
        available.
    """
    super(TaskQueueServiceStub, self).__init__(service_name)
    self.taskqueues = {}
    self.next_task_id = 1
    self.root_path = root_path

  def _Dynamic_Add(self, request, unused_response):
    if not self._ValidQueue(request.queue_name()):
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
      return

    if not request.task_name():
      request.set_task_name('task%d' % self.next_task_id)
      self.next_task_id += 1

    tasks = self.taskqueues.setdefault(request.queue_name(), [])
    tasks.append(request)
    tasks.sort(_CompareEta)
    return

  def _ValidQueue(self, queue_name):
    if queue_name == 'default':
      return True
    queue_info = self.queue_yaml_parser(self.root_path)
    if queue_info and queue_info.queue:
      for entry in queue_info.queue:
        if entry.name == queue_name:
          return True
    return False

  def GetQueues(self):
    """Gets all the applications's queues.

    Returns:
      A list of dictionaries, where each dictionary contains one queue's
      attributes.
    """
    queues = []
    queue_info = self.queue_yaml_parser(self.root_path)
    has_default = False
    if queue_info and queue_info.queue:
      for entry in queue_info.queue:
        if entry.name == 'default':
          has_default = True
        queue = {}
        queues.append(queue)
        queue['name'] = entry.name
        queue['max_rate'] = entry.rate
        if entry.bucket_size:
          queue['bucket_size'] = entry.bucket_size
        else:
          queue['bucket_size'] = DEFAULT_BUCKET_SIZE

        tasks = self.taskqueues.setdefault(entry.name, [])
        if tasks:
          queue['oldest_task'] = _FormatEta(tasks[0].eta_usec())
          queue['eta_delta'] = _EtaDelta(tasks[0].eta_usec())
        else:
          queue['oldest_task'] = ''
        queue['tasks_in_queue'] = len(tasks)

    if not has_default:
      queue = {}
      queues.append(queue)
      queue['name'] = 'default'
      queue['max_rate'] = DEFAULT_RATE
      queue['bucket_size'] = DEFAULT_BUCKET_SIZE

      tasks = self.taskqueues.get('default', [])
      if tasks:
        queue['oldest_task'] = _FormatEta(tasks[0].eta_usec())
        queue['eta_delta'] = _EtaDelta(tasks[0].eta_usec())
      else:
        queue['oldest_task'] = ''
      queue['tasks_in_queue'] = len(tasks)
    return queues

  def GetTasks(self, queue_name):
    """Gets a queue's tasks.

    Args:
      queue_name: Queue's name to return tasks for.

    Returns:
      A list of dictionaries, where each dictionary contains one task's
      attributes.
    """
    tasks = self.taskqueues.get(queue_name, [])
    result_tasks = []
    for task_request in tasks:
      task = {}
      result_tasks.append(task)
      task['name'] = task_request.task_name()
      task['url'] = task_request.url()
      method = task_request.method()
      if (method == taskqueue_service_pb.TaskQueueAddRequest.GET):
        task['method'] = 'GET'
      elif (method == taskqueue_service_pb.TaskQueueAddRequest.POST):
        task['method'] = 'POST'
      elif (method == taskqueue_service_pb.TaskQueueAddRequest.HEAD):
        task['method'] = 'HEAD'
      elif (method == taskqueue_service_pb.TaskQueueAddRequest.PUT):
        task['method'] = 'PUT'
      elif (method == taskqueue_service_pb.TaskQueueAddRequest.DELETE):
        task['method'] = 'DELETE'

      task['eta'] = _FormatEta(task_request.eta_usec())
      task['eta_delta'] = _EtaDelta(task_request.eta_usec())
      task['body'] = base64.b64encode(task_request.body())
      headers = urlfetch._CaselessDict()
      task['headers'] = headers
      for req_header in task_request.header_list():
        headers[req_header.key()] = req_header.value()

      headers['X-AppEngine-QueueName'] = queue_name
      headers['X-AppEngine-TaskName'] = task['name']
      headers['X-AppEngine-TaskRetryCount'] = '0'
      headers['X-AppEngine-Development-Payload'] = '1'
      headers['Content-Length'] = len(task['body'])
      headers['Content-Type'] = headers.get(
          'Content-Type', 'application/octet-stream')

    return result_tasks

  def DeleteTask(self, queue_name, task_name):
    """Deletes a task from a queue.

    Args:
      queue_name: the name of the queue to delete the task from.
      task_name: the name of the task to delete.
    """
    tasks = self.taskqueues.get(queue_name, [])
    for task in tasks:
      if task.task_name() == task_name:
        tasks.remove(task)
        return

  def FlushQueue(self, queue_name):
    """Removes all tasks from a queue.

    Args:
      queue_name: the name of the queue to remove tasks from.
    """
    self.taskqueues[queue_name] = []
