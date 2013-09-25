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
"""Performs XML-to-YAML translation.

  TranslateXmlToYaml(): performs xml-to-yaml translation with
  string inputs and outputs
  AppYamlTranslator: Class that facilitates xml-to-yaml translation
"""

from google.appengine.tools import app_engine_web_xml_parser as aewxp
from google.appengine.tools import backends_xml_parser
from google.appengine.tools import handler_generator
from google.appengine.tools import web_xml_parser
from google.appengine.tools.app_engine_web_xml_parser import AppEngineConfigException


NO_API_VERSION = 'none'


def TranslateXmlToYaml(app_engine_web_xml_str,
                       backends_xml_str,
                       web_xml_str,
                       static_files,
                       api_version):
  """Does xml-string to yaml-string translation, given each separate file text.

  Processes each xml string into an object representing the xml,
  and passes these to the translator.

  Args:
    app_engine_web_xml_str: text from app_engine_web.xml
    backends_xml_str: text from backends.xml
    web_xml_str: text from web.xml
    static_files: List of static files
    api_version: current api version

  Returns:
    The full text of the app.yaml generated from the xml files.

  Raises:
    AppEngineConfigException: raised in processing stage for illegal XML.
  """
  aewx_parser = aewxp.AppEngineWebXmlParser()
  backends_parser = backends_xml_parser.BackendsXmlParser()
  web_parser = web_xml_parser.WebXmlParser()
  app_engine_web_xml = aewx_parser.ProcessXml(app_engine_web_xml_str)
  backends_xml = backends_parser.ProcessXml(backends_xml_str)
  web_xml = web_parser.ProcessXml(web_xml_str)
  translator = AppYamlTranslator(
      app_engine_web_xml, backends_xml, web_xml, static_files, api_version)
  return translator.GetYaml()


def GetRuntime():

  return 'java7'


class AppYamlTranslator(object):
  """Object that contains relevant information for generating app.yaml.

  Attributes:
    app_engine_web_xml: AppEngineWebXml object containing relevant information
      from appengine-web.xml
    backends_xml: BackendsXml object containing relevant info from backends.xml
  """

  def __init__(self,
               app_engine_web_xml,
               backends_xml,
               web_xml,
               static_files,
               api_version):

    self.app_engine_web_xml = app_engine_web_xml
    self.backends_xml = backends_xml
    self.web_xml = web_xml
    self.static_files = static_files
    self.api_version = api_version

  def GetYaml(self):
    """Returns full yaml text."""
    self.VerifyRequiredEntriesPresent()
    stmnt_list = self.TranslateBasicEntries()
    stmnt_list += self.TranslateAutomaticScaling()
    stmnt_list += self.TranslateBasicScaling()
    stmnt_list += self.TranslateManualScaling()
    stmnt_list += self.TranslatePrecompilationEnabled()
    stmnt_list += self.TranslateInboundServices()
    stmnt_list += self.TranslateAdminConsolePages()
    stmnt_list += self.TranslateApiConfig()
    stmnt_list += self.TranslatePagespeed()
    stmnt_list += self.TranslateVmSettings()
    stmnt_list += self.TranslateErrorHandlers()
    stmnt_list += self.TranslateBackendsXml()
    stmnt_list += self.TranslateApiVersion()
    stmnt_list += self.TranslateHandlers()
    return '\n'.join(stmnt_list) + '\n'

  def SanitizeForYaml(self, the_string):
    return "'%s'" % the_string.replace("'", "''")

  def TranslateBasicEntries(self):
    """Produces yaml for entries requiring little formatting."""
    basic_statements = []

    for entry_name, field in [
        ('application', self.app_engine_web_xml.app_id),
        ('source_language', self.app_engine_web_xml.source_language),
        ('module', self.app_engine_web_xml.module),
        ('version', self.app_engine_web_xml.version_id)]:
      if field:
        basic_statements.append(
            '%s: %s' % (entry_name, self.SanitizeForYaml(field)))
    for entry_name, field in [
        ('runtime', GetRuntime()),
        ('vm', self.app_engine_web_xml.use_vm),
        ('threadsafe', self.app_engine_web_xml.threadsafe),
        ('instance_class', self.app_engine_web_xml.instance_class),
        ('auto_id_policy', self.app_engine_web_xml.auto_id_policy),
        ('code_lock', self.app_engine_web_xml.codelock)]:
      if field:
        basic_statements.append('%s: %s' % (entry_name, field))
    return basic_statements

  def TranslateAutomaticScaling(self):
    """Translates automatic scaling settings to yaml."""
    if not self.app_engine_web_xml.automatic_scaling:
      return []
    statements = ['automatic_scaling:']
    for setting in ['min_pending_latency',
                    'max_pending_latency',
                    'min_idle_instances',
                    'max_idle_instances']:
      value = getattr(self.app_engine_web_xml.automatic_scaling, setting)
      if value:
        statements.append('  %s: %s' % (setting, value))
    return statements

  def TranslateBasicScaling(self):
    if not self.app_engine_web_xml.basic_scaling:
      return []
    statements = ['basic_scaling:']
    statements.append('  max_instances: ' +
                      self.app_engine_web_xml.basic_scaling.max_instances)
    if self.app_engine_web_xml.basic_scaling.idle_timeout:
      statements.append('  idle_timeout: ' +
                        self.app_engine_web_xml.basic_scaling.idle_timeout)
    return statements

  def TranslateManualScaling(self):
    if not self.app_engine_web_xml.manual_scaling:
      return []

    statements = ['manual_scaling:']
    statements.append('  instances: ' +
                      self.app_engine_web_xml.manual_scaling.instances)
    return statements

  def TranslatePrecompilationEnabled(self):
    if self.app_engine_web_xml.precompilation_enabled:
      return ['derived_file_type:', '- java_precompiled']
    return []

  def TranslateAdminConsolePages(self):
    if not self.app_engine_web_xml.admin_console_pages:
      return []
    statements = ['admin_console:', '  pages:']
    for admin_console_page in self.app_engine_web_xml.admin_console_pages:
      statements.append('  - name: %s' % admin_console_page.name)
      statements.append('    url: %s' % admin_console_page.url)
    return statements

  def TranslateApiConfig(self):

    if not self.app_engine_web_xml.api_config:
      return []
    return ['api_config:', '  url: %s' % self.app_engine_web_xml.api_config.url,
            '  script: unused']

  def TranslateApiVersion(self):
    return ['api_version: %s' % self.SanitizeForYaml(
        self.api_version or NO_API_VERSION)]

  def TranslatePagespeed(self):
    """Translates pagespeed settings in appengine-web.xml to yaml."""
    pagespeed = self.app_engine_web_xml.pagespeed
    if not pagespeed:
      return []
    statements = ['pagespeed:']
    for title, urls in [('domains_to_rewrite', pagespeed.domains_to_rewrite),
                        ('url_blacklist', pagespeed.url_blacklist),
                        ('enabled_rewriters', pagespeed.enabled_rewriters),
                        ('disabled_rewriters', pagespeed.disabled_rewriters)]:
      if urls:
        statements.append('  %s:' % title)
        statements += ['  - %s' % url for url in urls]
    return statements

  def TranslateVmSettings(self):
    """Translates VM settings in appengine-web.xml to yaml."""
    if (not self.app_engine_web_xml.use_vm or
        not self.app_engine_web_xml.vm_settings):
      return []

    settings = self.app_engine_web_xml.vm_settings
    statements = ['vm_settings:']
    for name in sorted(settings):
      statements.append(
          '  %s: %s' % (
              self.SanitizeForYaml(name), self.SanitizeForYaml(settings[name])))
    return statements

  def TranslateInboundServices(self):
    services = self.app_engine_web_xml.inbound_services
    if not services:
      return []

    statements = ['inbound_services:']
    for service in sorted(services):
      statements.append('- %s' % service)
    return statements

  def TranslateErrorHandlers(self):
    """Translates error handlers specified in appengine-web.xml to yaml."""
    if not self.app_engine_web_xml.static_error_handlers:
      return []
    statements = ['error_handlers:']
    for error_handler in self.app_engine_web_xml.static_error_handlers:
      name = error_handler.name
      if not name.startswith('/'):
        name = '/' + name

      if ('__static__' + name) not in self.static_files:
        raise AppEngineConfigException(
            'No static file found for error handler: %s, out of %s' %
            (name, self.static_files))
      statements.append('- file: __static__%s' % name)
      if error_handler.code:
        statements.append('  error_code: %s' % error_handler.code)
      mime_type = self.web_xml.GetMimeTypeForPath(name)
      if mime_type:
        statements.append('  mime_type: %s' % mime_type)

    return statements

  def TranslateBackendsXml(self):
    """Translates backends.xml backends settings to yaml."""
    if not self.backends_xml:
      return []
    statements = ['backends:']

    for backend in self.backends_xml:
      statements.append('- name: %s' % backend.name)
      for entry, field in [('instances', backend.instances),
                           ('instance_class', backend.instance_class),
                           ('max_concurrent_requests',
                            backend.max_concurrent_requests)]:
        if field is not None:
          statements.append('  %s: %s' % (entry, str(field)))

      if backend.options:
        options_str = ', '.join(sorted(list(backend.options)))
        statements.append('  options: %s' % options_str)
    return statements

  def TranslateHandlers(self):
    return handler_generator.GenerateYamlHandlersList(
        self.app_engine_web_xml,
        self.web_xml,
        self.static_files)

  def VerifyRequiredEntriesPresent(self):
    if not all([self.app_engine_web_xml.app_id,
                self.app_engine_web_xml.version_id,
                GetRuntime(),
                self.app_engine_web_xml.threadsafe_value_provided]):
      raise AppEngineConfigException('Missing required fields')
