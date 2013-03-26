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
"""Configuration manager to store API configurations."""



import json
import logging
import re
import threading

from google.appengine.tools.devappserver2.endpoints import discovery_service


# Internal constants
_API_REST_PATH_FORMAT = '{!name}/{!version}/%s'
_PATH_VARIABLE_PATTERN = r'[a-zA-Z_][a-zA-Z_\d]*'
_RESERVED_PATH_VARIABLE_PATTERN = r'!' + _PATH_VARIABLE_PATTERN
_PATH_VALUE_PATTERN = r'[^:/?#\[\]{}]*'


class ApiConfigManager(object):
  """Manages loading api configs and method lookup."""

  def __init__(self):
    self._rpc_method_dict = {}
    self._rest_methods = []
    self.configs = {}
    self._config_lock = threading.Lock()

  def parse_api_config_response(self, body):
    """Parses a json api config and registers methods for dispatch.

    Side effects:
      Parses method name, etc for all methods and updates the indexing
      datastructures with the information.

    Args:
      body: A string, the JSON body of the getApiConfigs response.
    """

    try:
      response_obj = json.loads(body)
    except ValueError, unused_err:
      logging.error('Can not parse BackendService.getApiConfigs response: %s',
                    body)
    else:
      with self._config_lock:
        self._add_discovery_config()
        for api_config_json in response_obj.get('items', []):
          try:
            config = json.loads(api_config_json)
          except ValueError, unused_err:
            logging.error('Can not parse API config: %s',
                          api_config_json)
          else:
            lookup_key = config.get('name', ''), config.get('version', '')
            self.configs[lookup_key] = config

        for config in self.configs.itervalues():
          version = config.get('version', '')
          for method_name, method in config.get('methods', {}).iteritems():
            self._save_rpc_method(method_name, version, method)
            self._save_rest_method(method_name, version, method)

  def lookup_rpc_method(self, method_name, version):
    """Lookup the JsonRPC method at call time.

    The method is looked up in self._rpc_method_dict, the dictionary that
    it is saved in for SaveRpcMethod().

    Args:
      method_name: A string containing the name of the method.
      version: A string containing the version of the API.

    Returns:
      Method descriptor as specified in the API configuration.
    """
    with self._config_lock:
      method = self._rpc_method_dict.get((method_name, version))
    return method

  def lookup_rest_method(self, path, http_method):
    """Look up the rest method at call time.

    The method is looked up in self._rest_methods, the list it is saved
    in for SaveRestMethod.

    Args:
      path: A string containing the path from the URL of the request.
      http_method: A string containing HTTP method of the request.

    Returns:
      Tuple of (<method name>, <method>, <params>)
      Where:
        <method name> is the string name of the method that was matched.
        <method> is the descriptor as specified in the API configuration. -and-
        <params> is a dict of path parameters matched in the rest request.
    """
    with self._config_lock:
      for compiled_path_pattern, unused_path, methods in self._rest_methods:
        match = compiled_path_pattern.match(path)
        if match:
          params = match.groupdict()
          version = match.group(2)
          method_key = (http_method.lower(), version)
          method_name, method = methods.get(method_key, (None, None))
          if method:
            break
      else:
        logging.warn('No endpoint found for path: %s', path)
        method_name = None
        method = None
        params = None
    return method_name, method, params

  def _add_discovery_config(self):
    lookup_key = (discovery_service.DiscoveryService.API_CONFIG['name'],
                  discovery_service.DiscoveryService.API_CONFIG['version'])
    self.configs[lookup_key] = discovery_service.DiscoveryService.API_CONFIG

  @staticmethod
  def _compile_path_pattern(pattern):
    r"""Generates a compiled regex pattern for a path pattern.

    e.g. '/{!name}/{!version}/notes/{id}'
    returns re.compile(r'/([^:/?#\[\]{}]*)'
                       r'/([^:/?#\[\]{}]*)'
                       r'/notes/(?P<id>[^:/?#\[\]{}]*)')
    Note in this example that !name and !version are reserved variable names
    used to match the API name and version that should not be migrated into the
    method argument namespace.  As such they are not named in the regex, so
    groupdict() excludes them.

    Args:
      pattern: A string, the parameterized path pattern to be checked.

    Returns:
      A compiled regex object to match this path pattern.
    """

    def replace_reserved_variable(match):
      """Replaces a {!variable} with a regex to match it not by name.

      Args:
        match: A regex match object, the matching regex group as sent by
          re.sub().

      Returns:
        A string regex to match the variable by name, if the full pattern was
        matched.
      """
      if match.lastindex > 1:
        return '%s(%s)' % (match.group(1), _PATH_VALUE_PATTERN)
      return match.group(0)

    def replace_variable(match):
      """Replaces a {variable} with a regex to match it by name.

      Args:
        match: A regex match object, the matching regex group as sent by
          re.sub().

      Returns:
        A string regex to match the variable by name, if the full pattern was
        matched.
      """
      if match.lastindex > 1:
        return '%s(?P<%s>%s)' % (match.group(1), match.group(2),
                                 _PATH_VALUE_PATTERN)
      return match.group(0)

    # Replace !name and !version with regexes, but only allow replacement
    # of two reserved variables (re.sub argument 'count') to prevent
    # substituting e.g. {!name}/{!version}/myapi/{id}/{!othervar}
    pattern = re.sub('(/|^){(%s)}(?=/|$)' % _RESERVED_PATH_VARIABLE_PATTERN,
                     replace_reserved_variable, pattern, 2)
    pattern = re.sub('(/|^){(%s)}(?=/|$)' % _PATH_VARIABLE_PATTERN,
                     replace_variable, pattern)
    return re.compile(pattern + '/?$')

  def _save_rpc_method(self, method_name, version, method):
    """Store JsonRpc api methods in a map for lookup at call time.

    (rpcMethodName, apiVersion) => method.

    Args:
      method_name: A string containing the name of the API method.
      version: A string containing the version of the API.
      method: A dict containing the method descriptor (as in the api config
        file).
    """
    self._rpc_method_dict[(method_name, version)] = method

  def _save_rest_method(self, method_name, version, method):
    """Store Rest api methods in a list for lookup at call time.

    The list is self._rest_methods, a list of tuples:
      [(<compiled_path>, <path_pattern>, <method_dict>), ...]
    where:
      <compiled_path> is a compiled regex to match against the incoming URL
      <path_pattern> is a string representing the original path pattern,
        checked on insertion to prevent duplicates.     -and-
      <method_dict> is a dict (httpMethod, apiVersion) => (method_name, method)

    This structure is a bit complex, it supports use in two contexts:
      Creation time:
        - SaveRestMethod is called repeatedly, each method will have a path,
          which we want to be compiled for fast lookup at call time
        - We want to prevent duplicate incoming path patterns, so store the
          un-compiled path, not counting on a compiled regex being a stable
          comparison as it is not documented as being stable for this use.
        - Need to store the method that will be mapped at calltime.
        - Different methods may have the same path but different http method.
          and/or API versions.
      Call time:
        - Quickly scan through the list attempting .match(path) on each
          compiled regex to find the path that matches.
        - When a path is matched, look up the API version and method from the
          request and get the method name and method config for the matching
          API method and method name.

    Args:
      method_name: A string containing the name of the API method.
      version: A string containing the version of the API.
      method: A dict containing the method descriptor (as in the api config
        file).
    """
    path_pattern = _API_REST_PATH_FORMAT % method.get('path', '')
    http_method = method.get('httpMethod', '').lower()
    for _, path, methods in self._rest_methods:
      if path == path_pattern:
        methods[(http_method, version)] = method_name, method
        break
    else:
      self._rest_methods.append(
          (self._compile_path_pattern(path_pattern),
           path_pattern,
           {(http_method, version): (method_name, method)}))
