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
"""The main entry point for the new development server."""



import logging
import os
import sys
import time

from google.appengine.api import request_info
from google.appengine.tools.devappserver2 import api_server
from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import cli_parser
from google.appengine.tools.devappserver2 import constants
from google.appengine.tools.devappserver2 import dispatcher
from google.appengine.tools.devappserver2 import metrics
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import shutdown
from google.appengine.tools.devappserver2 import update_checker
from google.appengine.tools.devappserver2 import util
from google.appengine.tools.devappserver2 import wsgi_request_info
from google.appengine.tools.devappserver2.admin import admin_server

# Initialize logging early -- otherwise some library packages may
# pre-empt our log formatting.  NOTE: the level is provisional; it may
# be changed in main() based on the --dev_appserver_log_level flag.
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(asctime)s %(filename)s:%(lineno)s] %(message)s')


PARSER = cli_parser.create_command_line_parser(
    cli_parser.DEV_APPSERVER_CONFIGURATION)


class DevelopmentServer(object):
  """Encapsulates the logic for the development server.

  Only a single instance of the class may be created per process. See
  util.setup_environ.
  """

  def __init__(self):
    # A list of servers that are currently running.
    self._running_modules = []
    self._module_to_port = {}
    self._dispatcher = None
    self._options = None

  def module_to_address(self, module_name, instance=None):
    """Returns the address of a module."""



    if module_name is None:
      return self._dispatcher.dispatch_address
    return self._dispatcher.get_hostname(
        module_name,
        self._dispatcher.get_default_version(module_name),
        instance)

  def start(self, options):
    """Start devappserver2 servers based on the provided command line arguments.

    Args:
      options: An argparse.Namespace containing the command line arguments.
    """
    self._options = options

    logging.getLogger().setLevel(
        constants.LOG_LEVEL_TO_PYTHON_CONSTANT[options.dev_appserver_log_level])

    parsed_env_variables = dict(options.env_variables or [])

    if options.dev_appserver_log_setup_script:
      try:
        execfile(options.dev_appserver_log_setup_script, {}, {})
      except Exception as e:
        logging.exception("Error executing log setup script at %r.",
                          options.dev_appserver_log_setup_script)

    configuration = application_configuration.ApplicationConfiguration(
        config_paths=options.config_paths,
        app_id=options.app_id,
        runtime=options.runtime,
        env_variables=parsed_env_variables)

    if options.google_analytics_client_id:
      metrics_logger = metrics.GetMetricsLogger()
      metrics_logger.Start(
          options.google_analytics_client_id,
          options.google_analytics_user_agent,
          {module.runtime for module in configuration.modules},
          {module.env or 'standard' for module in configuration.modules})

    if options.skip_sdk_update_check:
      logging.info('Skipping SDK update check.')
    else:
      update_checker.check_for_updates(configuration)

    # There is no good way to set the default encoding from application code
    # (it needs to be done during interpreter initialization in site.py or
    # sitecustomize.py) so just warn developers if they have a different
    # encoding than production.
    if sys.getdefaultencoding() != constants.PROD_DEFAULT_ENCODING:
      logging.warning(
          'The default encoding of your local Python interpreter is set to %r '
          'while App Engine\'s production environment uses %r; as a result '
          'your code may behave differently when deployed.',
          sys.getdefaultencoding(), constants.PROD_DEFAULT_ENCODING)

    if options.port == 0:
      logging.warn('DEFAULT_VERSION_HOSTNAME will not be set correctly with '
                   '--port=0')

    util.setup_environ(configuration.app_id)

    self._dispatcher = dispatcher.Dispatcher(
        configuration, options.host, options.port, options.auth_domain,
        constants.LOG_LEVEL_TO_RUNTIME_CONSTANT[options.log_level],





        self._create_php_config(options),
        self._create_python_config(options),
        self._create_java_config(options),
        self._create_go_config(options),
        self._create_custom_config(options),
        self._create_cloud_sql_config(options),
        self._create_vm_config(options),
        self._create_module_to_setting(options.max_module_instances,
                                       configuration, '--max_module_instances'),
        options.use_mtime_file_watcher, options.watcher_ignore_re,
        options.automatic_restart, options.allow_skipped_files,
        self._create_module_to_setting(
            options.threadsafe_override,
            configuration,
            '--threadsafe_override'),
        options.external_port,
        options.specified_service_ports,
        options.enable_host_checking)

    wsgi_request_info_ = wsgi_request_info.WSGIRequestInfo(self._dispatcher)
    storage_path = api_server.get_storage_path(
        options.storage_path, configuration.app_id)

    apiserver = api_server.create_api_server(
        wsgi_request_info_, storage_path, options, configuration.app_id,
        configuration.modules[0].application_root)
    apiserver.start()
    self._running_modules.append(apiserver)

    self._dispatcher.start(
        options.api_host, apiserver.port, wsgi_request_info_)

    xsrf_path = os.path.join(storage_path, 'xsrf')
    admin = admin_server.AdminServer(options.admin_host, options.admin_port,
                                     self._dispatcher, configuration, xsrf_path,
                                     options.enable_host_checking,
                                     options.enable_console)
    admin.start()
    self._running_modules.append(admin)
    try:
      default = self._dispatcher.get_module_by_name('default')
      apiserver.set_balanced_address(default.balanced_address)
    except request_info.ModuleDoesNotExistError:
      logging.warning('No default module found. Ignoring.')

  def stop(self):
    """Stops all running devappserver2 modules and report metrics."""
    while self._running_modules:
      self._running_modules.pop().quit()
    if self._dispatcher:
      self._dispatcher.quit()
    if self._options.google_analytics_client_id:
      kwargs = {}
      watcher_results = (self._dispatcher.get_watcher_results()
                         if self._dispatcher else None)
      # get_watcher_results() only returns results for modules that have at
      # least one record of file change. Hence avoiding divide by zero error
      # when computing avg_time.
      if watcher_results:
        zipped = zip(*watcher_results)
        total_time = sum(zipped[0])
        total_changes = sum(zipped[1])

        # Google Analytics Event value cannot be float numbers, so we round the
        # value into integers, and measure in microseconds to ensure accuracy.
        avg_time = int(1000000*total_time/total_changes)

        # watcher_class is same on all modules.
        watcher_class = zipped[2][0]
        kwargs = {
            metrics.GOOGLE_ANALYTICS_DIMENSIONS['FileWatcherType']:
            watcher_class,
            metrics.GOOGLE_ANALYTICS_METRICS['FileChangeDetectionAverageTime']:
            avg_time,
            metrics.GOOGLE_ANALYTICS_METRICS['FileChangeEventCount']:
            total_changes
        }
      metrics.GetMetricsLogger().Stop(**kwargs)

  @staticmethod
  def _create_php_config(options):
    php_config = runtime_config_pb2.PhpConfig()
    if options.php_executable_path:
      php_config.php_executable_path = os.path.abspath(
          options.php_executable_path)
    php_config.enable_debugger = options.php_remote_debugging
    if options.php_gae_extension_path:
      php_config.gae_extension_path = os.path.abspath(
          options.php_gae_extension_path)
    if options.php_xdebug_extension_path:
      php_config.xdebug_extension_path = os.path.abspath(
          options.php_xdebug_extension_path)

    return php_config













  @staticmethod
  def _create_python_config(options):
    python_config = runtime_config_pb2.PythonConfig()
    if options.python_startup_script:
      python_config.startup_script = os.path.abspath(
          options.python_startup_script)
      if options.python_startup_args:
        python_config.startup_args = options.python_startup_args
    return python_config

  @staticmethod
  def _create_java_config(options):
    java_config = runtime_config_pb2.JavaConfig()
    if options.jvm_flag:
      java_config.jvm_args.extend(options.jvm_flag)
    return java_config

  @staticmethod
  def _create_go_config(options):
    go_config = runtime_config_pb2.GoConfig()
    if options.go_work_dir:
      go_config.work_dir = options.go_work_dir
    if options.enable_watching_go_path:
      go_config.enable_watching_go_path = True
    if options.go_debugging:
      go_config.enable_debugging = options.go_debugging
    return go_config

  @staticmethod
  def _create_custom_config(options):
    custom_config = runtime_config_pb2.CustomConfig()
    custom_config.custom_entrypoint = options.custom_entrypoint
    custom_config.runtime = options.runtime
    return custom_config

  @staticmethod
  def _create_cloud_sql_config(options):
    cloud_sql_config = runtime_config_pb2.CloudSQL()
    cloud_sql_config.mysql_host = options.mysql_host
    cloud_sql_config.mysql_port = options.mysql_port
    cloud_sql_config.mysql_user = options.mysql_user
    cloud_sql_config.mysql_password = options.mysql_password
    if options.mysql_socket:
      cloud_sql_config.mysql_socket = options.mysql_socket
    return cloud_sql_config

  @staticmethod
  def _create_vm_config(options):
    vm_config = runtime_config_pb2.VMConfig()
    vm_config.enable_logs = options.enable_mvm_logs
    return vm_config

  @staticmethod
  def _create_module_to_setting(setting, configuration, option):
    """Create a per-module dictionary configuration.

    Creates a dictionary that maps a module name to a configuration
    setting. Used in conjunction with parse_per_module_option.

    Args:
      setting: a value that can be None, a dict of str->type or a single value.
      configuration: an ApplicationConfiguration object.
      option: the option name the setting came from.

    Returns:
      A dict of str->type.
    """
    if setting is None:
      return {}

    module_names = [module_configuration.module_name
                    for module_configuration in configuration.modules]
    if isinstance(setting, dict):
      # Warn and remove a setting if the module name is unknown.
      module_to_setting = {}
      for module_name, value in setting.items():
        if module_name in module_names:
          module_to_setting[module_name] = value
        else:
          logging.warning('Unknown module %r for %r', module_name, option)
      return module_to_setting

    # Create a dict with an entry for every module.
    return {module_name: setting for module_name in module_names}


def main():
  shutdown.install_signal_handlers()
  # The timezone must be set in the devappserver2 process rather than just in
  # the runtime so printed log timestamps are consistent and the taskqueue stub
  # expects the timezone to be UTC. The runtime inherits the environment.
  os.environ['TZ'] = 'UTC'
  if hasattr(time, 'tzset'):
    # time.tzet() should be called on Unix, but doesn't exist on Windows.
    time.tzset()
  options = PARSER.parse_args()
  dev_server = DevelopmentServer()
  try:
    dev_server.start(options)
    shutdown.wait_until_shutdown()
  except:  # pylint: disable=bare-except
    metrics.GetMetricsLogger().LogOnceOnStop(
        metrics.DEVAPPSERVER_CATEGORY, metrics.ERROR_ACTION,
        label=metrics.GetErrorDetails())
    raise
  finally:
    dev_server.stop()


if __name__ == '__main__':
  main()
