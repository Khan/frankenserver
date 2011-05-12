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




"""Stub version of the Channel API, queues messages and writes them to a log."""








import logging
import random
import time

from google.appengine.api import apiproxy_stub
from google.appengine.api.channel import channel_service_pb
from google.appengine.runtime import apiproxy_errors


class ChannelServiceStub(apiproxy_stub.APIProxyStub):
  """Python only channel service stub.

  This stub does not use a browser channel to push messages to a client.
  Instead it queues messages internally.
  """




  CHANNEL_TIMEOUT_SECONDS = 2

  def __init__(self, log=logging.debug, service_name='channel',
               time_func=time.time):
    """Initializer.

    Args:
      log: A logger, used for dependency injection.
      service_name: Service name expected for all calls.
      time_func: function to get the current time in seconds.
    """
    apiproxy_stub.APIProxyStub.__init__(self, service_name)
    self._log = log
    self._time_func = time_func
    self._channel_messages = {}
    self._connected_channels = []










    self._add_event = None



    self._update_event = None


  def _Dynamic_CreateChannel(self, request, response):
    """Implementation of channel.get_channel.

    Args:
      request: A ChannelServiceRequest.
      response: A ChannelServiceResponse
    """

    client_id = request.application_key()
    if not client_id:
      raise apiproxy_errors.ApplicationError(
          channel_service_pb.ChannelServiceError.INVALID_CHANNEL_KEY)

    token = 'channel-%s-%s' % (random.randint(0, 2 ** 32),
                               client_id)
    self._log('Creating channel token %s with client id %s',
              token, request.application_key())

    if client_id not in self._channel_messages:
      self._channel_messages[client_id] = []


    response.set_client_id(token)


  def _Dynamic_SendChannelMessage(self, request, response):
    """Implementation of channel.send_message.

    Queues a message to be retrieved by the client when it polls.

    Args:
      request: A SendMessageRequest.
      response: A VoidProto.
    """


    client_id = request.application_key()

    if not request.message():
      raise apiproxy_errors.ApplicationError(
          channel_service_pb.ChannelServiceError.BAD_MESSAGE)

    if client_id in self._connected_channels:
      self._log('Sending a message (%s) to channel with key (%s)',
                request.message(), client_id)
      self._channel_messages[client_id].append(request.message())
    else:
      self._log('SKIPPING message (%s) to channel with key (%s): '
                'no clients connected',
                request.message(), client_id)

  def client_id_from_token(self, token):
    """Returns the client id from a given token.

    Args:
       token: String representing an instance of a client connection to a
       client id, returned by CreateChannel.

    Returns:
       String representing the client id used to create this token,
       or None if this token is incorrectly formed and doesn't map to a
       client id.
    """
    pieces = token.split('-', 2)
    if len(pieces) == 3:
      return pieces[2]
    else:
      return None

  def get_channel_messages(self, token):
    """Returns the pending messages for a given channel.

    Args:
      token: String representing the channel. Note that this is the token
        returned by CreateChannel, not the client id.

    Returns:
      List of messages, or None if the channel doesn't exist. The messages are
      strings.
    """
    self._log('Received request for messages for channel: ' + token)
    client_id = self.client_id_from_token(token)
    if client_id in self._channel_messages:
      return self._channel_messages[client_id]

    return None

  def has_channel_messages(self, token):
    """Checks to see if the given channel has any pending messages.

    Args:
      token: String representing the channel. Note that this is the token
        returned by CreateChannel, not the client id.

    Returns:
      True if the channel exists and has pending messages.
    """
    client_id = self.client_id_from_token(token)
    has_messages = (client_id in self._channel_messages and
                    bool(self._channel_messages[client_id]))
    self._log('Checking for messages on channel (%s) (%s)',
              token, has_messages)
    return has_messages

  def pop_first_message(self, token):
    """Returns and clears the first message from the message queue.

    Args:
      token: String representing the channel. Note that this is the token
        returned by CreateChannel, not the client id.

    Returns:
      The first message in the queue, or None if no messages.
    """
    if self.has_channel_messages(token):
      client_id = self.client_id_from_token(token)
      self._log('Popping first message of queue for channel (%s)', token)
      return self._channel_messages[client_id].pop(0)

    return None

  def clear_channel_messages(self, token):
    """Clears all messages from the channel.

    Args:
      token: String representing the channel. Note that this is the token
        returned by CreateChannel, not the client id.
    """
    client_id = self.client_id_from_token(token)
    if client_id:
      self._log('Clearing messages on channel (' + client_id + ')')
      if client_id in self._channel_messages:
        self._channel_messages[client_id] = []
    else:
      self._log('Ignoring clear messages for nonexistent token (' +
                token + ')')

  def disconnect_channel(self, client_id):
    """Removes the channel from the list of connected channels."""
    self._log('Removing channel %s', client_id)
    if client_id in self._channel_messages:
      del self._channel_messages[client_id]
    if client_id in self._connected_channels:
      self._connected_channels.remove(client_id)


    return None

  def connect_channel(self, token):
    """Marks the channel identified by the token (token) as connected."""
    client_id = self.client_id_from_token(token)


    def DefineCallback(client_id):
      return lambda: self.disconnect_channel(client_id)

    timeout = self._time_func() + ChannelServiceStub.CHANNEL_TIMEOUT_SECONDS
    if client_id in self._connected_channels:
      if self._update_event:

        self._update_event('channel', client_id, timeout)
    else:
      self._connected_channels.append(client_id)
      if self._add_event:

        self._add_event(timeout, DefineCallback(client_id), 'channel',
                        client_id)
