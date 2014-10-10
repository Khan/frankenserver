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
"""Directly processes text of datastore-indexes.xml.

IndexesXmlParser is called with an XML string to produce an IndexXml object
containing the data from the XML.

IndexesXmlParser: converts XML to Index object.
Index: describes a single index specified in datastore-indexes.xml
"""

from collections import OrderedDict
from xml.etree import ElementTree

from google.appengine.tools.app_engine_config_exception import AppEngineConfigException

MISSING_KIND = '<datastore-index> node has missing attribute "kind".'
BAD_DIRECTION = ('<property> tag attribute "direction" must have value "asc"'
                 ' or "desc", given "%s"')
NAME_MISSING = ('<datastore-index> node with kind "%s" needs to have a name'
                ' attribute specified for its <property> node')


def MakeIndexesListIntoYaml(indexes_list):
  """Converts a list of parsed <datastore-index> clauses into YAML."""
  statements = ['indexes:']
  for index in indexes_list:
    statements += index.ToYaml()
  return '\n'.join(statements) + '\n'


class IndexesXmlParser(object):
  """Provides logic for walking down XML tree and pulling data."""

  def ProcessXml(self, xml_str):
    """Parses XML string and returns object representation of relevant info.

    Args:
      xml_str: The XML string.
    Returns:
      A list of Index objects containing information about datastore indexes
      from the XML.
    Raises:
      AppEngineConfigException: In case of malformed XML or illegal inputs.
    """

    try:
      self.indexes = []
      self.errors = []
      xml_root = ElementTree.fromstring(xml_str)
      if xml_root.tag != 'datastore-indexes':
        raise AppEngineConfigException('Root tag must be <datastore-indexes>')

      for child in xml_root.getchildren():
        self.ProcessIndexNode(child)

      if self.errors:
        raise AppEngineConfigException('\n'.join(self.errors))

      return self.indexes
    except ElementTree.ParseError as e:
      raise AppEngineConfigException('Bad input -- not valid XML: %s' % e)

  def ProcessIndexNode(self, node):
    """Processes XML <datastore-index> nodes into Index objects.

    The following information is parsed out:
    kind: specifies the kind of entities to index.
    ancestor: true if the index supports queries that filter by
      ancestor-key to constraint results to a single entity group.
    property: represents the entity properties to index, with a name
      and direction attribute.

    Args:
      node: <datastore-index> XML node in datastore-indexes.xml.
    """
    if node.tag != 'datastore-index':
      self.errors.append('Unrecognized node: <%s>' % node.tag)
      return

    index = Index()
    index.kind = node.attrib.get('kind', '')
    if not index.kind:
      self.errors.append(MISSING_KIND)
    ancestor = node.attrib.get('ancestor', 'false')
    index.ancestor = self._BooleanAttribute(ancestor)
    if index.ancestor is None:
      self.errors.append(
          'Value for ancestor should be true or false, not "%s"' % ancestor)
    index.properties = OrderedDict()
    property_nodes = [n for n in node.getchildren() if n.tag == 'property']
    for property_node in property_nodes:
      name = property_node.attrib.get('name', '')
      if not name:
        self.errors.append(NAME_MISSING % index.kind)
        continue

      direction = property_node.attrib.get('direction', 'asc')
      if direction not in ('asc', 'desc'):
        self.errors.append(BAD_DIRECTION % direction)
        continue
      index.properties[name] = direction
    self.indexes.append(index)

  @staticmethod
  def _BooleanAttribute(value):
    """Parse the given attribute value as a Boolean value.

    This follows the specification here:
    http://www.w3.org/TR/2012/REC-xmlschema11-2-20120405/datatypes.html#boolean

    Args:
      value: the value to parse.

    Returns:
      True if the value parses as true, False if it parses as false, None if it
      parses as neither.
    """
    if value in ['true', '1']:
      return True
    elif value in ['false', '0']:
      return False
    else:
      return None


class Index(object):

  def ToYaml(self):
    statements = ['- kind: "%s"' % self.kind]
    if self.ancestor:
      statements.append('  ancestor: yes')
    if self.properties:
      statements.append('  properties:')
      for name in self.properties:
        statements += ['  - name: "%s"' % name,
                       '    direction: %s' % self.properties[name]]
    return statements
