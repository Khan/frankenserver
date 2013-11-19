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
"""Appcfg logic specific to Java apps."""
from __future__ import with_statement

import os.path
import re
import shutil
import subprocess
import tempfile

from google.appengine.tools import app_engine_web_xml_parser
from google.appengine.tools import backends_xml_parser
from google.appengine.tools import jarfile
from google.appengine.tools import web_xml_parser
from google.appengine.tools import yaml_translator


_LOCAL_JSPC_CLASS = 'com.google.appengine.tools.development.LocalJspC'


class Error(Exception):
  pass


class ConfigurationError(Error):
  """There was a configuration error in the application being uploaded."""
  pass


class CompileError(Error):
  """There was a compilation error in a JSP file or its generated Java code."""
  pass


def IsWarFileWithoutYaml(dir_path):
  if os.path.isfile(os.path.join(dir_path, 'app.yaml')):
    return False
  web_inf = os.path.join(dir_path, 'WEB-INF')
  if not os.path.isdir(web_inf):
    return False
  if not set(['appengine-web.xml', 'web.xml']).issubset(os.listdir(web_inf)):
    return False
  return True


def AddUpdateOptions(parser):
  """Adds options specific to the 'update' command on Java apps to 'parser'.

  Args:
    parser: An instance of OptionsParser.
  """
  parser.add_option('--retain_upload_dir', action='store_true',
                    dest='retain_upload_dir', default=False,
                    help='Do not delete temporary (staging) directory used '
                    'in uploading Java apps')
  parser.add_option('--compile_encoding', action='store',
                    dest='compile_encoding', default='UTF-8',
                    help='Set the encoding to be used when compiling Java '
                    'source files (default "UTF-8").')
  parser.add_option('--disable_jar_jsps', action='store_false',
                    dest='jar_jsps', default=True,
                    help='Do not jar the classes generated from JSPs.')
  parser.add_option('--delete_jsps', action='store_true',
                    dest='delete_jsps', default=False,
                    help='Delete the JSP source files after compilation.')
  parser.add_option('--enable_jar_classes', action='store_true',
                    dest='do_jar_classes', default=False,
                    help='Jar the WEB-INF/classes content.')


class JavaAppUpdate(object):
  """Performs Java-specific update configurations."""
  _JSP_REGEX = re.compile('.*\\.jspx?')




  def __init__(self, basepath, options):
    self.basepath = basepath
    self.options = options

    self.app_engine_web_xml = self._ReadAppEngineWebXml()
    self.app_engine_web_xml.app_root = self.basepath
    self.web_xml = self._ReadWebXml()

  def _ReadAppEngineWebXml(self, basepath=None):
    if not basepath:
      basepath = self.basepath
    return self._ReadAndParseXml(
        basepath=basepath,
        file_name='appengine-web.xml',
        parser=app_engine_web_xml_parser.AppEngineWebXmlParser)

  def _ReadWebXml(self, basepath=None):
    if not basepath:
      basepath = self.basepath
    return self._ReadAndParseXml(
        basepath=basepath,
        file_name='web.xml',
        parser=web_xml_parser.WebXmlParser)

  def _ReadBackendsXml(self, basepath=None):
    if not basepath:
      basepath = self.basepath
    return self._ReadAndParseXml(
        basepath=basepath,
        file_name='backends.xml',
        parser=backends_xml_parser.BackendsXmlParser)

  def _ReadAndParseXml(self, basepath, file_name, parser):
    with open(os.path.join(basepath, 'WEB-INF', file_name)) as file_handle:
      return parser().ProcessXml(file_handle.read())

  def CreateStagingDirectory(self, tools_dir):
    """Creates a staging directory for uploading.

    This is where we perform the necessary actions to create an application
    directory for the update command to work properly - files are organized
    into the static folder, and yaml files are generated where they can be
    found later.

    Args:
      tools_dir: Path to the SDK tools directory
        (typically .../google/appengine/tools)

    Returns:
      The path to a new temporary directory which contains generated yaml files
      and a static file directory. For the most part, the rest of the update and
      upload flow can resume identically to Python/PHP/Go applications.

    Raises:
      CompileError: if compilation of JSPs failed.
      ConfigurationError: if the app to be staged has a configuration error.
      IOError: if there was an I/O problem, for example when scanning jar files.
    """
    full_basepath = os.path.abspath(self.basepath)
    stage_dir = tempfile.mkdtemp(prefix='appcfgpy')
    static_dir = os.path.join(stage_dir, '__static__')
    os.mkdir(static_dir)
    self._CopyOrLink(full_basepath, stage_dir, static_dir, False)
    self.app_engine_web_xml.app_root = stage_dir

    if self.options.compile_jsps:
      self._CompileJspsIfAny(tools_dir, stage_dir)

    web_inf_lib = os.path.join(stage_dir, 'WEB-INF', 'lib')
    api_jar_dict = _FindApiJars(web_inf_lib)
    api_versions = set(api_jar_dict.values())
    if not api_versions:
      api_version = None
    elif len(api_versions) == 1:
      api_version = api_versions.pop()
    else:
      raise ConfigurationError('API jars have inconsistent versions: %s' %
                               api_jar_dict)


    for staged_api_jar in api_jar_dict:
      os.remove(staged_api_jar)

    self._GenerateAppYaml(stage_dir, api_version)

    return stage_dir

  def GenerateAppYamlString(self, basepath, static_file_list, api_version=None):
    """Constructs an app.yaml string equivalent to the XML files under WEB-INF.

    Args:
      basepath: a string that is the path to the WEB-INF directory. This
        might not be self.basepath, because it might be a staging directory.
      static_file_list: a list of strings that are the absolute path names of
        static file resources.
      api_version: a string that is the Java API version number, or None if
        not known or relevant.

    Returns:
      A string that would have the same effect as the XML files under WEB-INF
      if it were the contents of an app.yaml file.
    """
    backends = []
    if os.path.isfile(os.path.join(self.basepath, 'WEB-INF', 'backends.xml')):
      backends = self._ReadBackendsXml(basepath)
    return yaml_translator.AppYamlTranslator(
        self.app_engine_web_xml,
        backends,
        self.web_xml,
        static_file_list,
        api_version).GetYaml()

  def _GenerateAppYaml(self, stage_dir, api_version):
    """Creates the app.yaml file in WEB-INF/appengine-generated/."""
    static_file_list = self._GetStaticFileList(stage_dir)
    yaml_str = self.GenerateAppYamlString(
        stage_dir, static_file_list, api_version)
    appengine_generated = os.path.join(
        stage_dir, 'WEB-INF', 'appengine-generated')
    if not os.path.isdir(appengine_generated):
      os.mkdir(appengine_generated)
    with open(os.path.join(appengine_generated, 'app.yaml'), 'w') as handle:
      handle.write(yaml_str)

  def _CopyOrLink(self, source_dir, stage_dir, static_dir, inside_web_inf):
    for file_name in os.listdir(source_dir):
      file_path = os.path.join(source_dir, file_name)

      if file_name.startswith('.') or file_name == 'appengine-generated':
        continue

      if os.path.isdir(file_path):
        self._CopyOrLink(
            file_path,
            os.path.join(stage_dir, file_name),
            os.path.join(static_dir, file_name),
            inside_web_inf or file_name == 'WEB-INF')
      else:
        if (inside_web_inf
            or self.app_engine_web_xml.IncludesResource(file_path)
            or (self.options.compile_jsps
                and file_path.lower().endswith('.jsp'))):
          self._CopyOrLinkFile(file_path, os.path.join(stage_dir, file_name))
        if (not inside_web_inf
            and self.app_engine_web_xml.IncludesStatic(file_path)):
          self._CopyOrLinkFile(file_path, os.path.join(static_dir, file_name))

  def _CopyOrLinkFile(self, source, dest):

    if not os.path.exists(os.path.dirname(dest)):
      os.makedirs(os.path.dirname(dest))
    if not source.endswith('web.xml'):
      os.symlink(source, dest)
      return
    shutil.copy(source, dest)

  def _CopyOrLinkDirectories(self, source_dir, dest_dir):
    for name in os.listdir(source_dir):
      source_path = os.path.join(source_dir, name)
      dest_path = os.path.join(dest_dir, name)
      if os.path.isdir(source_path):
        self._CopyOrLinkDirectories(source_path, dest_path)
      else:
        self._CopyOrLinkFile(source_path, dest_path)

  @staticmethod
  def _GetStaticFileList(staging_dir):
    return _FilesMatching(os.path.join(staging_dir, '__static__'))

  def _CompileJspsIfAny(self, tools_dir, staging_dir):
    """Performs necessary preparations for JSP Compilation."""
    if self._MatchingFileExists(self._JSP_REGEX, staging_dir):
      staging_web_inf = os.path.join(staging_dir, 'WEB-INF')
      lib_dir = os.path.join(staging_web_inf, 'lib')

      for jar_file in GetUserJspLibFiles(tools_dir):
        self._CopyOrLinkFile(
            jar_file, os.path.join(lib_dir, os.path.basename(jar_file)))
      for jar_file in GetSharedJspLibFiles(tools_dir):
        self._CopyOrLinkFile(
            jar_file, os.path.join(lib_dir, os.path.basename(jar_file)))

      classes_dir = os.path.join(staging_web_inf, 'classes')
      gen_dir = tempfile.mkdtemp()
      generated_web_xml = os.path.join(staging_web_inf, 'generated_web.xml')

      classpath = self._GetJspClasspath(tools_dir, classes_dir, gen_dir)
      java_home, exec_suffix = _JavaHomeAndSuffix()

      java_command = os.path.join(java_home, 'bin', 'java' + exec_suffix)

      command_and_args = [
          java_command,
          '-classpath', classpath,
          _LOCAL_JSPC_CLASS,
          '-uriroot', staging_dir,
          '-p', 'org.apache.jsp',
          '-l',
          '-v',
          '-webinc', generated_web_xml,
          '-d', gen_dir,
          '-javaEncoding', self.options.compile_encoding,
      ]

      status = subprocess.call(command_and_args)
      if status:
        raise CompileError(
            'Compilation of JSPs exited with status %d' % status)

      self._CompileJavaFiles(classpath, staging_web_inf, gen_dir,
                             java_home, exec_suffix)


      self.web_xml = self._ReadWebXml(staging_dir)

  def _CompileJavaFiles(
      self, classpath, web_inf, jsp_class_dir, java_home, exec_suffix):
    """Compile all *.java files found under jsp_class_dir."""
    java_files = _FilesMatching(jsp_class_dir, lambda f: f.endswith('.java'))
    if not java_files:
      return

    javac_command = os.path.join(java_home, 'bin', 'javac' + exec_suffix)

    command_and_args = [
        javac_command,
        '-classpath', classpath,
        '-d', jsp_class_dir,
        '-encoding', self.options.compile_encoding,
    ] + java_files

    status = subprocess.call(command_and_args)
    if status:
      raise CompileError(
          'Compilation of JSP-generated code exited with status %d' % status)

    if self.options.jar_jsps:
      raise RuntimeError('Only --disable_jar_jsps supported for now')
    else:
      web_inf_classes = os.path.join(web_inf, 'classes')
      self._CopyOrLinkDirectories(jsp_class_dir, web_inf_classes)

    if self.options.delete_jsps:
      jsps = _FilesMatching(os.path.dirname(web_inf),
                            lambda f: f.endswith('.jsp'))
      for f in jsps:
        os.remove(f)

    if self.options.do_jar_classes:

      raise RuntimeError('--jar_classes not supported yet')

  @staticmethod
  def _GetJspClasspath(tools_dir, classes_dir, gen_dir):
    """Builds the classpath for the JSP Compilation system call."""
    lib_dir = os.path.join(os.path.dirname(classes_dir), 'lib')
    elements = (
        GetImplLibs(tools_dir) + GetSharedLibFiles(tools_dir) +
        [classes_dir, gen_dir] +
        _FilesMatching(
            lib_dir, lambda f: f.endswith('.jar') or f.endswith('.zip')))

    return (os.pathsep).join(elements)

  @staticmethod
  def _MatchingFileExists(regex, dir_path):
    for _, _, files in os.walk(dir_path):
      for f in files:
        if re.search(regex, f):
          return True
    return False


def GetImplLibs(tools_dir):
  return _GetLibsShallow(os.path.join(tools_dir, 'java', 'lib', 'impl'))


def GetSharedLibFiles(tools_dir):
  return _GetLibsRecursive(os.path.join(tools_dir, 'java', 'lib', 'shared'))


def GetUserJspLibFiles(tools_dir):
  return _GetLibsRecursive(
      os.path.join(tools_dir, 'java', 'lib', 'tools', 'jsp'))


def GetSharedJspLibFiles(tools_dir):
  return _GetLibsRecursive(
      os.path.join(tools_dir, 'java', 'lib', 'shared', 'jsp'))


def _GetLibsRecursive(dir_path):
  return _FilesMatching(dir_path, lambda f: f.endswith('.jar'))


def _GetLibsShallow(dir_path):
  libs = []
  for f in os.listdir(dir_path):
    if os.path.isfile(os.path.join(dir_path, f)) and f.endswith('.jar'):
      libs.append(os.path.join(dir_path, f))
  return libs


def _FilesMatching(root, predicate=lambda f: True):
  """Finds all files under the given root that match the given predicate.

  Args:
    root: a string that is the absolute or relative path to a directory.
    predicate: a function that takes a file name (without a directory) and
      returns a truth value.

  Returns:
    A list of strings that are the paths of every file under the given root
    that satisfies the given predicate. The paths are absolute if and only if
    the input root is absolute.
  """
  matches = []
  for path, _, files in os.walk(root):
    matches += [os.path.join(path, f) for f in files if predicate(f)]
  return matches


def _JavaHomeAndSuffix():
  """Find the directory that the JDK is installed in.

  The JDK install directory is expected to have a bin directory that contains
  at a minimum the java and javac executables. If the environment variable
  JAVA_HOME is set then it must point to such a directory. Otherwise, we look
  for javac on the PATH and check that it is inside a JDK install directory.

  Returns:
    A tuple where the first element is the JDK install directory and the second
    element is a suffix that must be appended to executables in that directory
    ('' on Unix-like systems, '.exe' on Windows).

  Raises:
    RuntimeError: If JAVA_HOME is set but is not a JDK install directory, or
    otherwise if a JDK install directory cannot be found based on the PATH.
  """
  def ResultForJdkAt(path):
    """Return (path, suffix) if path is a JDK install directory, else None."""
    def IsExecutable(binary):
      return os.path.isfile(binary) and os.access(binary, os.X_OK)

    for suffix in ['', '.exe']:
      if all(IsExecutable(os.path.join(path, 'bin', binary + suffix))
             for binary in ['java', 'javac', 'jar']):
        return (path, suffix)
    return None

  java_home = os.getenv('JAVA_HOME')
  if java_home:
    result = ResultForJdkAt(java_home)
    if result:
      return result
    else:
      raise RuntimeError(
          'JAVA_HOME is set but does not reference a valid JDK: %s' % java_home)
  for path_dir in os.environ['PATH'].split(os.pathsep):
    maybe_root, last = os.path.split(path_dir)
    if last == 'bin':
      result = ResultForJdkAt(maybe_root)
      if result:
        return result
  raise RuntimeError('Did not find JDK in PATH and JAVA_HOME is not set')


def _FindApiJars(lib_dir):
  """Find the appengine-api-*.jar and its version.

  The version of an appengine-api-*.jar is the Specification-Version attribute
  in the jar's manifest section whose Name is 'com/google/appengine/api/'.

  Args:
    lib_dir: the base directory under which jars are to be found.

  Returns:
    A dict from string to string, mapping all found API jars to their
    corresponding versions.

  Raises:
    IOError: if there was a problem reading the jars.
  """
  result = {}
  for jar_file in _FilesMatching(lib_dir, lambda f: f.endswith('.jar')):
    manifest = jarfile.ReadManifest(jar_file)
    section = manifest.sections.get('com/google/appengine/api/')
    if section and 'Specification-Version' in section:
      result[jar_file] = section['Specification-Version']
  return result
