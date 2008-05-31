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

"""Stub version of the memcache API, keeping all data in process memory."""



import logging
import time

from google.appengine.api import memcache
from google.appengine.api.memcache import memcache_service_pb

MemcacheSetResponse = memcache_service_pb.MemcacheSetResponse
MemcacheSetRequest = memcache_service_pb.MemcacheSetRequest
MemcacheIncrementRequest = memcache_service_pb.MemcacheIncrementRequest
MemcacheDeleteResponse = memcache_service_pb.MemcacheDeleteResponse


class CacheEntry(object):
  """An entry in the cache."""

  def __init__(self, value, expiration, flags, gettime):
    """Initializer.

    Args:
      value: String containing the data for this entry.
      expiration: Number containing the expiration time or offset in seconds
        for this entry.
      flags: Opaque flags used by the memcache implementation.
      gettime: Used for testing. Function that works like time.time().
    """
    assert isinstance(value, basestring)
    assert len(value) <= memcache.MAX_VALUE_SIZE
    assert isinstance(expiration, (int, long))

    self._gettime = gettime
    self.value = value
    self.flags = flags
    self.created_time = self._gettime()
    self.will_expire = expiration != 0
    self.locked = False
    self._SetExpiration(expiration)

  def _SetExpiration(self, expiration):
    """Sets the expiration for this entry.

    Args:
      expiration: Number containing the expiration time or offset in seconds
        for this entry. If expiration is above one month, then it's considered
        an absolute time since the UNIX epoch.
    """
    if expiration > (86400 * 30):
      self.expiration_time = expiration
    else:
      self.expiration_time = self._gettime() + expiration

  def CheckExpired(self):
    """Returns True if this entry has expired; False otherwise."""
    return self.will_expire and self._gettime() >= self.expiration_time

  def ExpireAndLock(self, timeout):
    """Marks this entry as deleted and locks it for the expiration time.

    Used to implement memcache's delete timeout behavior.

    Args:
      timeout: Parameter originally passed to memcache.delete or
        memcache.delete_multi to control deletion timeout.
    """
    self.will_expire = True
    self.locked = True
    self._SetExpiration(timeout)

  def CheckLocked(self):
    """Returns True if this entry was deleted but has not yet timed out."""
    return self.locked and not self.CheckExpired()


class MemcacheServiceStub(object):
  """Python only memcache service stub.

  This stub keeps all data in the local process' memory, not in any
  external servers.
  """

  def __init__(self, gettime=time.time):
    """Initializer.

    Args:
      gettime: time.time()-like function used for testing.
    """
    self._gettime = gettime
    self._ResetStats()

    self._the_cache = {}

  def _ResetStats(self):
    """Resets statistics information."""
    self._hits = 0
    self._misses = 0
    self._byte_hits = 0

  def MakeSyncCall(self, service, call, request, response):
    """The main RPC entry point.

    Args:
      service: Must be name as defined by sub class variable SERVICE.
      call: A string representing the rpc to make.  Must be part of
        MemcacheService.
      request: A protocol buffer of the type corresponding to 'call'.
      response: A protocol buffer of the type corresponding to 'call'.
    """
    assert service == 'memcache'
    assert request.IsInitialized()

    attr = getattr(self, '_Dynamic_' + call)
    attr(request, response)

  def _GetKey(self, key):
    """Retrieves a CacheEntry from the cache if it hasn't expired.

    Does not take deletion timeout into account.

    Args:
      key: The key to retrieve from the cache.

    Returns:
      The corresponding CacheEntry instance, or None if it was not found or
      has already expired.
    """
    entry = self._the_cache.get(key, None)
    if entry is None:
      return None
    elif entry.CheckExpired():
      del self._the_cache[key]
      return None
    else:
      return entry

  def _Dynamic_Get(self, request, response):
    """Implementation of MemcacheService::Get().

    Args:
      request: A MemcacheGetRequest.
      response: A MemcacheGetResponse.
    """
    keys = set(request.key_list())
    for key in keys:
      entry = self._GetKey(key)
      if entry is None or entry.CheckLocked():
        self._misses += 1
        continue
      self._hits += 1
      self._byte_hits += len(entry.value)
      item = response.add_item()
      item.set_key(key)
      item.set_value(entry.value)
      item.set_flags(entry.flags)

  def _Dynamic_Set(self, request, response):
    """Implementation of MemcacheService::Set().

    Args:
      request: A MemcacheSetRequest.
      response: A MemcacheSetResponse.
    """
    for item in request.item_list():
      key = item.key()
      set_policy = item.set_policy()
      old_entry = self._GetKey(key)

      set_status = MemcacheSetResponse.NOT_STORED
      if ((set_policy == MemcacheSetRequest.SET) or
          (set_policy == MemcacheSetRequest.ADD and old_entry is None) or
          (set_policy == MemcacheSetRequest.REPLACE and old_entry is not None)):

        if (old_entry is None or
            set_policy == MemcacheSetRequest.SET
            or not old_entry.CheckLocked()):
          self._the_cache[key] = CacheEntry(item.value(),
                                            item.expiration_time(),
                                            item.flags(),
                                            gettime=self._gettime)
          set_status = MemcacheSetResponse.STORED

      response.add_set_status(set_status)

  def _Dynamic_Delete(self, request, response):
    """Implementation of MemcacheService::Delete().

    Args:
      request: A MemcacheDeleteRequest.
      response: A MemcacheDeleteResponse.
    """
    for item in request.item_list():
      key = item.key()
      entry = self._GetKey(key)

      delete_status = MemcacheDeleteResponse.DELETED
      if entry is None:
        delete_status = MemcacheDeleteResponse.NOT_FOUND
      elif item.delete_time == 0:
        del self._the_cache[key]
      else:
        entry.ExpireAndLock(item.delete_time())

      response.add_delete_status(delete_status)

  def _Dynamic_Increment(self, request, response):
    """Implementation of MemcacheService::Increment().

    Args:
      request: A MemcacheIncrementRequest.
      response: A MemcacheIncrementResponse.
    """
    key = request.key()
    entry = self._GetKey(key)
    if entry is None:
      return

    try:
      old_value = long(entry.value)
    except ValueError, e:
      logging.error('Increment/decrement failed: Could not interpret '
                    'value for key = "%s" as an integer.', key)
      return

    delta = request.delta()
    if request.direction() == MemcacheIncrementRequest.DECREMENT:
      delta = -delta

    new_value = old_value + delta
    if not (0 <= new_value < 2**64):
      new_value = 0

    entry.value = str(new_value)
    response.set_new_value(new_value)

  def _Dynamic_FlushAll(self, request, response):
    """Implementation of MemcacheService::FlushAll().

    Args:
      request: A MemcacheFlushRequest.
      response: A MemcacheFlushResponse.
    """
    self._the_cache.clear()
    self._ResetStats()

  def _Dynamic_Stats(self, request, response):
    """Implementation of MemcacheService::Stats().

    Args:
      request: A MemcacheStatsRequest.
      response: A MemcacheStatsResponse.
    """
    stats = response.mutable_stats()
    stats.set_hits(self._hits)
    stats.set_misses(self._misses)
    stats.set_byte_hits(self._byte_hits)
    stats.set_items(len(self._the_cache))

    total_bytes = 0
    for key, entry in self._the_cache.iteritems():
      total_bytes += len(entry.value)
    stats.set_bytes(total_bytes)

    stats.set_oldest_item_age(1800)
