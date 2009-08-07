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

"""Provides thread-pool-like functionality for workers accessing App Engine.

The pool adapts to slow or timing out requests by reducing the number of
active workers, or increasing the number when requests latency reduces.
"""



import logging
import Queue
import sys
import threading
import time

from google.appengine.tools.requeue import ReQueue


class NullHandler(logging.Handler):
  def emit(self, record):
    pass

logger = logging.getLogger('google.appengine.tools.adaptive_thread_pool')

_THREAD_SHOULD_EXIT = '_THREAD_SHOULD_EXIT'

INITIAL_BACKOFF = 1.0

BACKOFF_FACTOR = 2.0


class Error(Exception):
  """Base-class for exceptions in this module."""


class WorkItemError(Error):
  """Error while processing a WorkItem."""


class RetryException(Exception):
  """A non-fatal exception that indicates that a work item should be retried."""


def InterruptibleSleep(sleep_time):
  """Puts thread to sleep, checking this threads exit_flag four times a second.

  Args:
    sleep_time: Time to sleep.
  """
  slept = 0.0
  epsilon = .0001
  thread = threading.currentThread()
  while slept < sleep_time - epsilon:
    remaining = sleep_time - slept
    this_sleep_time = min(remaining, 0.25)
    time.sleep(this_sleep_time)
    slept += this_sleep_time
    if thread.exit_flag:
      return


class WorkerThread(threading.Thread):
  """A WorkerThread to execute WorkItems."""

  def __init__(self, thread_pool, name=None):
    """Initialize a WorkerThread instance.

    Args:
      thread_pool: A ThreadGate instace.
      name: A name for this WorkerThread.
    """
    threading.Thread.__init__(self)

    self.setDaemon(True)

    self.exit_flag = False
    self.error = None
    self.traceback = None
    self.thread_pool = thread_pool
    self.work_queue = thread_pool.requeue
    self.thread_gate = thread_pool.thread_gate
    if not name:
      self.name = 'Anonymous_' + self.__class__.__name__
    else:
      self.name = name

  def run(self):
    """Perform the work of the thread."""
    logger.info('[%s] %s: started', self.getName(), self.__class__.__name__)

    try:
      self.WorkOnItems()
    except:
      self.SetError()
      logger.exception('[%s] %s:', self.getName(), self.__class__.__name__)

    logger.info('[%s] %s: exiting', self.getName(), self.__class__.__name__)

  def SetError(self):
    """Sets the error and traceback information for this thread.

    This must be called from an exception handler.
    """
    if not self.error:
      exc_info = sys.exc_info()
      self.error = exc_info[1]
      self.traceback = exc_info[2]

  def WorkOnItems(self):
    """Perform the work of a WorkerThread."""
    while not self.exit_flag:
      (status, instruction) = (WorkItem.RETRY, ThreadGate.HOLD)
      item = None
      self.thread_gate.StartWork()
      try:
        if self.exit_flag:
          break

        try:
          item = self.work_queue.get(block=True, timeout=1.0)
        except Queue.Empty:
          continue
        if item == _THREAD_SHOULD_EXIT or self.exit_flag:
          break

        logger.debug('[%s] Got work item %s', self.getName(), item)

        try:
          instruction = ThreadGate.DECREASE
          (status, instruction) = item.PerformWork(self.thread_pool)
        except RetryException:
          status = WorkItem.RETRY
          instruction = ThreadGate.HOLD
        except:
          self.SetError()
          logger.exception('[%s] %s: caught exception %s', self.getName(),
                           self.__class__.__name__, str(sys.exc_info()))
          raise

      finally:
        try:
          if status == WorkItem.SUCCESS:
            self.work_queue.task_done()
          elif status == WorkItem.RETRY and item:
            try:
              self.work_queue.reput(item, block=False)
            except Queue.Full:
              logger.error('[%s] Failed to reput work item.', self.getName())
              raise Error('Failed to reput work item')
          elif item:
            if not self.error:
              if item.error:
                self.error = item.error
                self.traceback = item.traceback
              else:
                self.error = WorkItemError('Fatal error while processing %s' %
                                           item)
              raise self.error

          if not self.error:
            if instruction == ThreadGate.INCREASE:
              self.thread_gate.IncreaseWorkers()
            elif instruction == ThreadGate.DECREASE:
              self.thread_gate.DecreaseWorkers()
        finally:
          self.thread_gate.FinishWork()

  def CheckError(self):
    """If an error is present, then log it."""
    if self.error:
      logger.error('Error in %s: %s', self.getName(), self.error)
      if self.traceback:
        logger.debug(''.join(self.traceback.format_exception(
            self.error.__class__,
            self.error,
            self.traceback)))

  def __str__(self):
    return self.name


class AdaptiveThreadPool(object):
  """A thread pool which processes WorkItems from a queue."""

  def __init__(self,
               num_threads,
               queue_size=None,
               base_thread_name=None,
               worker_thread_factory=WorkerThread,
               queue_factory=Queue.Queue):
    """Initialize an AdaptiveThreadPool.

    An adaptive thread pool executes WorkItems using a number of
    WorkerThreads.  WorkItems represent items of work that may
    succeed, soft fail, or hard fail. In addition, a completed work
    item can signal this AdaptiveThreadPool to enable more or fewer
    threads.  Initially one thread is active.  Soft failures are
    reqeueud to be retried.  Hard failures cause this
    AdaptiveThreadPool to shut down entirely.  See the WorkItem class
    for more details.

    Args:
      num_threads: The number of threads to use.
      queue_size: The size of the work item queue to use.
      base_thread_name: A string from which worker thread names are derived.
      worker_thread_factory: A factory which procudes WorkerThreads.
      queue_factory: Used for dependency injection.
    """
    if queue_size is None:
      queue_size = num_threads
    self.queue_size = queue_size
    self.requeue = ReQueue(queue_size, queue_factory=queue_factory)
    self.thread_gate = ThreadGate(num_threads)
    self.num_threads = num_threads
    self._threads = []
    for i in xrange(num_threads):
      thread = worker_thread_factory(self)
      if base_thread_name:
        base = base_thread_name
      else:
        base = thread.__class__.__name__
      thread.name = '%s-%d' % (base, i)
      self._threads.append(thread)
      thread.start()

  def Threads(self):
    """Yields the registered threads."""
    for thread in self._threads:
      yield thread

  def SubmitItem(self, item, block=True, timeout=0.0):
    """Submit a WorkItem to the AdaptiveThreadPool.

    Args:
      item: A WorkItem instance.
      block: Whether to block on submitting if the submit queue is full.
      timeout: Time wait for room in the queue if block is True, 0.0 to
        block indefinitely.

    Raises:
      Queue.Full if the submit queue is full.
    """
    self.requeue.put(item, block=block, timeout=timeout)

  def QueuedItemCount(self):
    """Returns the number of items currently in the queue."""
    return self.requeue.qsize()

  def Shutdown(self):
    """Shutdown the thread pool.

    Tasks may remain unexecuted in the submit queue.
    """
    while not self.requeue.empty():
      try:
        unused_item = self.requeue.get_nowait()
        self.requeue.task_done()
      except Queue.Empty:
        pass
    for thread in self._threads:
      thread.exit_flag = True
      self.requeue.put(_THREAD_SHOULD_EXIT)
    self.thread_gate.EnableAllThreads()

  def Wait(self):
    """Wait until all work items have been completed."""
    self.requeue.join()

  def JoinThreads(self):
    """Wait for all threads to exit."""
    for thread in self._threads:
      logger.debug('Waiting for %s to exit' % str(thread))
      thread.join()

  def CheckErrors(self):
    """Output logs for any errors that occurred in the worker threads."""
    for thread in self._threads:
      thread.CheckError()


class ThreadGate(object):
  """Manage the number of active worker threads.

  The ThreadGate limits the number of threads that are simultaneously
  active in order to implement adaptive rate control.

  Initially the ThreadGate allows only one thread to be active.  For
  each successful work item, another thread is activated and for each
  failed item, the number of active threads is reduced by one.  When only
  one thread is active, failures will cause exponential backoff.

  Note that if a thread gate is ever disabled by setting self.enabled to
  False, it must never be enabled again or it will be in an inconsistent
  state.
  """

  INCREASE = 'increase'
  HOLD = 'hold'
  DECREASE = 'decrease'

  def __init__(self,
               num_threads,
               sleep=InterruptibleSleep):
    """Constructor for ThreadGate instances.

    Args:
      num_threads: The total number of threads using this gate.
      sleep: Used for dependency injection.
    """
    self.enabled_count = 1
    self.lock = threading.Lock()
    self.thread_semaphore = threading.Semaphore(self.enabled_count)
    self._threads = []
    self.num_threads = num_threads
    self.backoff_time = 0
    self.sleep = sleep

  def EnableThread(self):
    """Enable one more worker thread."""
    self.lock.acquire()
    try:
      self.enabled_count += 1
    finally:
      self.lock.release()
    self.thread_semaphore.release()

  def EnableAllThreads(self):
    """Enable all worker threads."""
    for unused_idx in xrange(self.num_threads - self.enabled_count):
      self.EnableThread()

  def StartWork(self):
    """Starts a critical section in which the number of workers is limited.

    If thread throttling is enabled then this method starts a critical
    section which allows self.enabled_count simultaneously operating
    threads. The critical section is ended by calling self.FinishWork().
    """
    self.thread_semaphore.acquire()
    if self.backoff_time > 0.0:
      if not threading.currentThread().exit_flag:
        logger.info('Backing off: %.1f seconds',
                    self.backoff_time)
        self.sleep(self.backoff_time)

  def FinishWork(self):
    """Ends a critical section started with self.StartWork()."""
    self.thread_semaphore.release()

  def IncreaseWorkers(self):
    """Increases the number of active threads."""
    if self.backoff_time > 0.0:
      logger.info('Resetting backoff to 0.0')
      self.backoff_time = 0.0
    do_enable = False
    self.lock.acquire()
    try:
      if self.num_threads > self.enabled_count:
        do_enable = True
        self.enabled_count += 1
    finally:
      self.lock.release()
    if do_enable:
      logger.debug('Increasing active thread count to %d',
                   self.enabled_count)
      self.thread_semaphore.release()

  def DecreaseWorkers(self, backoff=True):
    """Informs the thread_gate that an item failed to send.

    If thread throttling is enabled, this method will cause the
    throttler to allow one fewer thread in the critical section. If
    there is only one thread remaining, failures will result in
    exponential backoff until there is a success.

    Args:
      backoff: Whether to increase exponential backoff if there is only
        one thread enabled.
    """
    do_disable = False
    self.lock.acquire()
    try:
      if self.enabled_count > 1:
        do_disable = True
        self.enabled_count -= 1
      elif backoff:
        if self.backoff_time == 0.0:
          self.backoff_time = INITIAL_BACKOFF
        else:
          self.backoff_time *= BACKOFF_FACTOR
    finally:
      self.lock.release()
    if do_disable:
      logger.debug('Decreasing the number of active threads to %d',
                   self.enabled_count)
      self.thread_semaphore.acquire()


class WorkItem(object):
  """Holds a unit of work."""

  SUCCESS = 'success'
  RETRY = 'retry'
  FAILURE = 'failure'

  def __init__(self, name):
    self.name = name

  def PerformWork(self, thread_pool):
    """Perform the work of this work item and report the results.

    Args:
      thread_pool: The AdaptiveThreadPool instance associated with this
        thread.

    Returns:
      A tuple (status, instruction) of the work status and an instruction
      for the ThreadGate.
    """
    return (WorkItem.SUCCESS, ThreadGate.HOLD)

  def __str__(self):
    return self.name
