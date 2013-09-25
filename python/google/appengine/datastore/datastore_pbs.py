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




"""Utilities for converting between v3 and v4 datastore protocol buffers.

This module is internal and should not be used by client applications.
"""
















from google.appengine.datastore import entity_pb

from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_v4_pb
from google.appengine.datastore import entity_v4_pb



_MEANING_ATOM_CATEGORY = 1
_MEANING_URL = 2
_MEANING_ATOM_TITLE = 3
_MEANING_ATOM_CONTENT = 4
_MEANING_ATOM_SUMMARY = 5
_MEANING_ATOM_AUTHOR = 6
_MEANING_GD_EMAIL = 8
_MEANING_GEORSS_POINT = 9
_MEANING_GD_IM = 10
_MEANING_GD_PHONENUMBER = 11
_MEANING_GD_POSTALADDRESS = 12
_MEANING_PERCENT = 13
_MEANING_TEXT = 15
_MEANING_BYTESTRING = 16
_MEANING_INDEX_ONLY = 18
_MEANING_PREDEFINED_ENTITY_USER = 20
_MEANING_PREDEFINED_ENTITY_POINT = 21
_MEANING_ZLIB = 22


_URI_MEANING_ZLIB = 'ZLIB'


_MAX_INDEXED_BLOB_BYTES = 500


_PROPERTY_NAME_X = 'x'
_PROPERTY_NAME_Y = 'y'


_PROPERTY_NAME_EMAIL = 'email'
_PROPERTY_NAME_AUTH_DOMAIN = 'auth_domain'
_PROPERTY_NAME_USER_ID = 'user_id'
_PROPERTY_NAME_INTERNAL_ID = 'internal_id'
_PROPERTY_NAME_FEDERATED_IDENTITY = 'federated_identity'
_PROPERTY_NAME_FEDERATED_PROVIDER = 'federated_provider'


_PROPERTY_NAME_KEY = '__key__'

_DEFAULT_GAIA_ID = 0


def _is_valid_utf8(s):
  try:
    s.decode('utf-8')
    return True
  except UnicodeDecodeError:
    return False


def _check_conversion(condition, message):
  """Asserts a conversion condition and raises an error if it's not met.

  Args:
    condition: (boolean) condition to enforce
    message: error message

  Raises:
    InvalidConversionError: if condition is not met
  """
  if not condition:
    raise InvalidConversionError(message)



class InvalidConversionError(Exception):
  """Raised when conversion fails."""
  pass


class _EntityConverter(object):
  """Converter for entities and keys."""

  def v4_to_v3_reference(self, v4_key, v3_ref):
    """Converts a v4 Key to a v3 Reference.

    Args:
      v4_key: an entity_v4_pb.Key
      v3_ref: an entity_pb.Reference to populate
    """
    v3_ref.Clear()
    if v4_key.has_partition_id():
      if v4_key.partition_id().has_dataset_id():
        v3_ref.set_app(v4_key.partition_id().dataset_id())
      if v4_key.partition_id().has_namespace():
        v3_ref.set_name_space(v4_key.partition_id().namespace())
    for v4_element in v4_key.path_element_list():
      v3_element = v3_ref.mutable_path().add_element()
      v3_element.set_type(v4_element.kind())
      if v4_element.has_id():
        v3_element.set_id(v4_element.id())
      if v4_element.has_name():
        v3_element.set_name(v4_element.name())

  def v3_to_v4_key(self, v3_ref, v4_key):
    """Converts a v3 Reference to a v4 Key.

    Args:
      v3_ref: an entity_pb.Reference
      v4_key: an entity_v4_pb.Key to populate
    """
    v4_key.Clear()
    if not v3_ref.app():
      return
    v4_key.mutable_partition_id().set_dataset_id(v3_ref.app())
    if v3_ref.name_space():
      v4_key.mutable_partition_id().set_namespace(v3_ref.name_space())
    for v3_element in v3_ref.path().element_list():
      v4_element = v4_key.add_path_element()
      v4_element.set_kind(v3_element.type())
      if v3_element.has_id():
        v4_element.set_id(v3_element.id())
      if v3_element.has_name():
        v4_element.set_name(v3_element.name())

  def v4_to_v3_entity(self, v4_entity, v3_entity):
    """Converts a v4 Entity to a v3 EntityProto.

    Args:
      v4_entity: an entity_v4_pb.Entity
      v3_entity: an entity_pb.EntityProto to populate
    """
    v3_entity.Clear()
    for v4_property in v4_entity.property_list():
      property_name = v4_property.name()
      if v4_property.has_value():
        v4_value = v4_property.value()
        if v4_value.list_value_list():
          for v4_sub_value in v4_value.list_value_list():
            self.__add_v3_property(property_name, True, v4_sub_value, v3_entity)
        else:
          self.__add_v3_property(property_name, False, v4_value, v3_entity)
      else:
        is_multi = v4_property.deprecated_multi()
        for v4_value in v4_property.deprecated_value_list():
          self.__add_v3_property(property_name, is_multi, v4_value, v3_entity)
    if v4_entity.has_key():
      v4_key = v4_entity.key()
      self.v4_to_v3_reference(v4_key, v3_entity.mutable_key())
      v3_ref = v3_entity.key()
      if (self.__v3_reference_has_id_or_name(v3_ref)
          or v3_ref.path().element_size() > 1):
        self._v3_reference_to_group(v3_ref, v3_entity.mutable_entity_group())
    else:


      pass

  def v3_to_v4_entity(self, v3_entity, v4_entity):
    """Converts a v3 EntityProto to a v4 Entity.

    Args:
      v3_entity: an entity_pb.EntityProto
      v4_entity: an entity_v4_pb.Proto to populate
    """
    v4_entity.Clear()
    self.v3_to_v4_key(v3_entity.key(), v4_entity.mutable_key())
    if not v3_entity.key().has_app():

      v4_entity.clear_key()




    v4_properties = {}
    for v3_property in v3_entity.property_list():
      self.__add_v4_property_to_entity(v4_entity, v4_properties, v3_property,
                                       True)
    for v3_property in v3_entity.raw_property_list():
      self.__add_v4_property_to_entity(v4_entity, v4_properties, v3_property,
                                       False)

  def v4_value_to_v3_property_value(self, v4_value, v3_value):
    """Converts a v4 Value to a v3 PropertyValue.

    Args:
      v4_value: an entity_v4_pb.Value
      v3_value: an entity_pb.PropertyValue to populate
    """
    v3_value.Clear()
    if v4_value.has_boolean_value():
      v3_value.set_booleanvalue(v4_value.boolean_value())
    elif v4_value.has_integer_value():
      v3_value.set_int64value(v4_value.integer_value())
    elif v4_value.has_double_value():
      v3_value.set_doublevalue(v4_value.double_value())
    elif v4_value.has_timestamp_microseconds_value():
      v3_value.set_int64value(v4_value.timestamp_microseconds_value())
    elif v4_value.has_key_value():
      v3_ref = entity_pb.Reference()
      self.v4_to_v3_reference(v4_value.key_value(), v3_ref)
      self._v3_reference_to_v3_property_value(v3_ref, v3_value)
    elif v4_value.has_blob_key_value():
      v3_value.set_stringvalue(v4_value.blob_key_value())
    elif v4_value.has_string_value():
      v3_value.set_stringvalue(v4_value.string_value())
    elif v4_value.has_blob_value():
      v3_value.set_stringvalue(v4_value.blob_value())
    elif v4_value.has_entity_value():
      v4_entity_value = v4_value.entity_value()
      v4_meaning = v4_value.meaning()
      if (v4_meaning == _MEANING_GEORSS_POINT
          or v4_meaning == _MEANING_PREDEFINED_ENTITY_POINT):
        self.__v4_to_v3_point_value(v4_entity_value,
                                    v3_value.mutable_pointvalue())
      elif v4_meaning == _MEANING_PREDEFINED_ENTITY_USER:
        self.__v4_to_v3_user_value(v4_entity_value,
                                   v3_value.mutable_uservalue())
      else:
        v3_entity_value = entity_pb.EntityProto()
        self.v4_to_v3_entity(v4_entity_value, v3_entity_value)
        v3_value.set_stringvalue(v3_entity_value.SerializePartialToString())
    else:

      pass

  def v3_property_to_v4_value(self, v3_property, indexed, v4_value):
    """Converts a v3 Property to a v4 Value.

    Args:
      v3_property: an entity_pb.Property
      indexed: whether the v3 property is indexed
      v4_value: an entity_v4_pb.Value to populate
    """
    v4_value.Clear()
    v3_property_value = v3_property.value()
    v3_meaning = v3_property.meaning()
    v3_uri_meaning = None
    if v3_property.meaning_uri():
      v3_uri_meaning = v3_property.meaning_uri()

    if not self.__is_v3_property_value_union_valid(v3_property_value):


      v3_meaning = None
      v3_uri_meaning = None
    elif v3_meaning == entity_pb.Property.NO_MEANING:
      v3_meaning = None
    elif not self.__is_v3_property_value_meaning_valid(v3_property_value,
                                                       v3_meaning):

      v3_meaning = None

    is_zlib_value = False
    if v3_uri_meaning:
      if v3_uri_meaning == _URI_MEANING_ZLIB:
        if v3_property_value.has_stringvalue():
          is_zlib_value = True
          if v3_meaning != entity_pb.Property.BLOB:

            v3_meaning = entity_pb.Property.BLOB
        else:
          pass
      else:
        pass


    if v3_property_value.has_booleanvalue():
      v4_value.set_boolean_value(v3_property_value.booleanvalue())
    elif v3_property_value.has_int64value():
      if v3_meaning == entity_pb.Property.GD_WHEN:
        v4_value.set_timestamp_microseconds_value(
            v3_property_value.int64value())
        v3_meaning = None
      else:
        v4_value.set_integer_value(v3_property_value.int64value())
    elif v3_property_value.has_doublevalue():
      v4_value.set_double_value(v3_property_value.doublevalue())
    elif v3_property_value.has_referencevalue():
      v3_ref = entity_pb.Reference()
      self.__v3_reference_value_to_v3_reference(
          v3_property_value.referencevalue(), v3_ref)
      self.v3_to_v4_key(v3_ref, v4_value.mutable_key_value())
    elif v3_property_value.has_stringvalue():
      if v3_meaning == entity_pb.Property.ENTITY_PROTO:
        serialized_entity_v3 = v3_property_value.stringvalue()
        v3_entity = entity_pb.EntityProto()


        v3_entity.ParsePartialFromString(serialized_entity_v3)
        self.v3_to_v4_entity(v3_entity, v4_value.mutable_entity_value())
        v3_meaning = None
      elif (v3_meaning == entity_pb.Property.BLOB
            or v3_meaning == entity_pb.Property.BYTESTRING):
        v4_value.set_blob_value(v3_property_value.stringvalue())

        if indexed or v3_meaning == entity_pb.Property.BLOB:
          v3_meaning = None
      else:
        string_value = v3_property_value.stringvalue()
        if _is_valid_utf8(string_value):
          if v3_meaning == entity_pb.Property.BLOBKEY:
            v4_value.set_blob_key_value(string_value)
            v3_meaning = None
          else:
            v4_value.set_string_value(string_value)
        else:

          v4_value.set_blob_value(string_value)

          if v3_meaning != entity_pb.Property.INDEX_VALUE:
            v3_meaning = None


    elif v3_property_value.has_pointvalue():
      self.__v3_to_v4_point_entity(v3_property_value.pointvalue(),
                                   v4_value.mutable_entity_value())
      if v3_meaning != entity_pb.Property.GEORSS_POINT:
        v4_value.set_meaning(_MEANING_PREDEFINED_ENTITY_POINT)
        v3_meaning = None
    elif v3_property_value.has_uservalue():
      self.__v3_to_v4_user_entity(v3_property_value.uservalue(),
                                  v4_value.mutable_entity_value())
      v4_value.set_meaning(_MEANING_PREDEFINED_ENTITY_USER)
    else:
      pass

    if is_zlib_value:
      v4_value.set_meaning(_MEANING_ZLIB)
    elif v3_meaning:
      v4_value.set_meaning(v3_meaning)


    if indexed != v4_value.indexed():
      v4_value.set_indexed(indexed)

  def __v4_to_v3_property(self, property_name, is_multi, v4_value, v3_property):
    """Converts info from a v4 Property to a v3 Property.

    v4_value must not have a list_value.

    Args:
      property_name: the name of the property
      is_multi: whether the property contains multiple values
      v4_value: an entity_v4_pb.Value
      v3_property: an entity_pb.Property to populate
    """
    assert not v4_value.list_value_list(), 'v4 list_value not convertable to v3'
    v3_property.Clear()
    v3_property.set_name(property_name)
    v3_property.set_multiple(is_multi)
    self.v4_value_to_v3_property_value(v4_value, v3_property.mutable_value())

    v4_meaning = None
    if v4_value.has_meaning():
      v4_meaning = v4_value.meaning()

    if v4_value.has_timestamp_microseconds_value():
      v3_property.set_meaning(entity_pb.Property.GD_WHEN)
    elif v4_value.has_blob_key_value():
      v3_property.set_meaning(entity_pb.Property.BLOBKEY)
    elif v4_value.has_blob_value():
      if v4_meaning == _MEANING_ZLIB:
        v3_property.set_meaning_uri(_URI_MEANING_ZLIB)
      if v4_meaning == entity_pb.Property.BYTESTRING:
        if v4_value.indexed():
          pass


      else:
        if v4_value.indexed():
          v3_property.set_meaning(entity_pb.Property.BYTESTRING)
        else:
          v3_property.set_meaning(entity_pb.Property.BLOB)
        v4_meaning = None
    elif v4_value.has_entity_value():
      if v4_meaning != _MEANING_GEORSS_POINT:
        if (v4_meaning != _MEANING_PREDEFINED_ENTITY_POINT
            and v4_meaning != _MEANING_PREDEFINED_ENTITY_USER):
          v3_property.set_meaning(entity_pb.Property.ENTITY_PROTO)
        v4_meaning = None
    else:

      pass
    if v4_meaning is not None:
      v3_property.set_meaning(v4_meaning)

  def __add_v3_property(self, property_name, is_multi, v4_value, v3_entity):
    """Adds a v3 Property to an Entity based on information from a v4 Property.

    Args:
      property_name: the name of the property
      is_multi: whether the property contains multiple values
      v4_value: an entity_v4_pb.Value
      v3_entity: an entity_pb.EntityProto
    """
    if v4_value.indexed():
      self.__v4_to_v3_property(property_name, is_multi, v4_value,
                               v3_entity.add_property())
    else:
      self.__v4_to_v3_property(property_name, is_multi, v4_value,
                               v3_entity.add_raw_property())

  def __build_name_to_v4_property_map(self, v4_entity):
    property_map = {}
    for prop in v4_entity.property_list():
      property_map[prop.name()] = prop
    return property_map

  def __add_v4_property_to_entity(self, v4_entity, property_map, v3_property,
                                  indexed):
    """Adds a v4 Property to an entity or modifies an existing one.

    property_map is used to track of properties that have already been added.
    The same dict should be used for all of an entity's properties.

    Args:
      v4_entity: an entity_v4_pb.Entity
      property_map: a dict of name -> v4_property
      v3_property: an entity_pb.Property to convert to v4 and add to the dict
      indexed: whether the property is indexed
    """
    property_name = v3_property.name()
    if property_name in property_map:
      v4_property = property_map[property_name]
    else:
      v4_property = v4_entity.add_property()
      v4_property.set_name(property_name)
      property_map[property_name] = v4_property
    if v3_property.multiple():
      self.v3_property_to_v4_value(v3_property, indexed,
                                   v4_property.mutable_value().add_list_value())
    else:
      self.v3_property_to_v4_value(v3_property, indexed,
                                   v4_property.mutable_value())

  def __get_single_v4_integer_value(self, v4_property):
    """Returns an integer value from a v4 Property.

    Args:
      v4_property: an entity_v4_pb.Property

    Returns:
      an integer

    Throws:
      AssertionError if v4_property doesn't contain exactly one value
    """
    if v4_property.has_value():
      return v4_property.value().integer_value()
    else:
      v4_values = v4_property.deprecated_value_list()
      assert len(v4_values) == 1, 'property had %d values' % len(v4_values)
      return v4_values[0].integer_value()

  def __get_single_v4_double_value(self, v4_property):
    """Returns a double value from a v4 Property.

    Args:
      v4_property: an entity_v4_pb.Property

    Returns:
      a double

    Throws:
      AssertionError if v4_property doesn't contain exactly one value
    """
    if v4_property.has_value():
      return v4_property.value().double_value()
    else:
      v4_values = v4_property.deprecated_value_list()
      assert len(v4_values) == 1, 'property had %d values' % len(v4_values)
      return v4_values[0].double_value()

  def __get_single_v4_string_value(self, v4_property):
    """Returns an string value from a v4 Property.

    Args:
      v4_property: an entity_v4_pb.Property

    Returns:
      a string

    Throws:
      AssertionError if v4_property doesn't contain exactly one value
    """
    if v4_property.has_value():
      return v4_property.value().string_value()
    else:
      v4_values = v4_property.deprecated_value_list()
      assert len(v4_values) == 1, 'property had %d values' % len(v4_values)
      return v4_values[0].string_value()

  def __v4_integer_property(self, name, value, indexed):
    """Creates a single-integer-valued v4 Property.

    Args:
      name: the property name
      value: the integer value of the property
      indexed: whether the value should be indexed

    Returns:
      an entity_v4_pb.Property
    """
    v4_property = entity_v4_pb.Property()
    v4_property.set_name(name)
    v4_value = v4_property.mutable_value()
    v4_value.set_indexed(indexed)
    v4_value.set_integer_value(value)
    return v4_property

  def __v4_double_property(self, name, value, indexed):
    """Creates a single-double-valued v4 Property.

    Args:
      name: the property name
      value: the double value of the property
      indexed: whether the value should be indexed

    Returns:
      an entity_v4_pb.Property
    """
    v4_property = entity_v4_pb.Property()
    v4_property.set_name(name)
    v4_value = v4_property.mutable_value()
    v4_value.set_indexed(indexed)
    v4_value.set_double_value(value)
    return v4_property

  def __v4_string_property(self, name, value, indexed):
    """Creates a single-string-valued v4 Property.

    Args:
      name: the property name
      value: the string value of the property
      indexed: whether the value should be indexed

    Returns:
      an entity_v4_pb.Property
    """
    v4_property = entity_v4_pb.Property()
    v4_property.set_name(name)
    v4_value = v4_property.mutable_value()
    v4_value.set_indexed(indexed)
    v4_value.set_string_value(value)
    return v4_property

  def __v4_to_v3_point_value(self, v4_point_entity, v3_point_value):
    """Converts a v4 point Entity to a v3 PointValue.

    Args:
      v4_point_entity: an entity_v4_pb.Entity representing a point
      v3_point_value: an entity_pb.Property_PointValue to populate
    """
    v3_point_value.Clear()
    name_to_v4_property = self.__build_name_to_v4_property_map(v4_point_entity)
    v3_point_value.set_x(
        self.__get_single_v4_double_value(name_to_v4_property['x']))
    v3_point_value.set_y(
        self.__get_single_v4_double_value(name_to_v4_property['y']))

  def __v3_to_v4_point_entity(self, v3_point_value, v4_entity):
    """Converts a v3 UserValue to a v4 user Entity.

    Args:
      v3_point_value: an entity_pb.Property_PointValue
      v4_entity: an entity_v4_pb.Entity to populate
    """
    v4_entity.Clear()
    v4_entity.property_list().append(
        self.__v4_double_property(_PROPERTY_NAME_X, v3_point_value.x(), False))
    v4_entity.property_list().append(
        self.__v4_double_property(_PROPERTY_NAME_Y, v3_point_value.y(), False))

  def __v4_to_v3_user_value(self, v4_user_entity, v3_user_value):
    """Converts a v4 user Entity to a v3 UserValue.

    Args:
      v4_user_entity: an entity_v4_pb.Entity representing a user
      v3_user_value: an entity_pb.Property_UserValue to populate
    """
    v3_user_value.Clear()
    name_to_v4_property = self.__build_name_to_v4_property_map(v4_user_entity)

    v3_user_value.set_email(self.__get_single_v4_string_value(
        name_to_v4_property[_PROPERTY_NAME_EMAIL]))
    v3_user_value.set_auth_domain(self.__get_single_v4_string_value(
        name_to_v4_property[_PROPERTY_NAME_AUTH_DOMAIN]))
    if _PROPERTY_NAME_USER_ID in name_to_v4_property:
      v3_user_value.set_obfuscated_gaiaid(
          self.__get_single_v4_string_value(
              name_to_v4_property[_PROPERTY_NAME_USER_ID]))
    if _PROPERTY_NAME_INTERNAL_ID in name_to_v4_property:
      v3_user_value.set_gaiaid(self.__get_single_v4_integer_value(
          name_to_v4_property[_PROPERTY_NAME_INTERNAL_ID]))
    else:

      v3_user_value.set_gaiaid(0)
    if _PROPERTY_NAME_FEDERATED_IDENTITY in name_to_v4_property:
      v3_user_value.set_federated_identity(
          self.__get_single_v4_string_value(name_to_v4_property[
              _PROPERTY_NAME_FEDERATED_IDENTITY]))
    if _PROPERTY_NAME_FEDERATED_PROVIDER in name_to_v4_property:
      v3_user_value.set_federated_provider(
          self.__get_single_v4_string_value(name_to_v4_property[
              _PROPERTY_NAME_FEDERATED_PROVIDER]))

  def __v3_to_v4_user_entity(self, v3_user_value, v4_entity):
    """Converts a v3 UserValue to a v4 user Entity.

    Args:
      v3_user_value: an entity_pb.Property_UserValue
      v4_entity: an entity_v4_pb.Entity to populate
    """
    v4_entity.Clear()
    v4_entity.property_list().append(
        self.__v4_string_property(_PROPERTY_NAME_EMAIL, v3_user_value.email(),
                                  False))
    v4_entity.property_list().append(self.__v4_string_property(
        _PROPERTY_NAME_AUTH_DOMAIN,
        v3_user_value.auth_domain(), False))

    if v3_user_value.gaiaid() != 0:
      v4_entity.property_list().append(self.__v4_integer_property(
          _PROPERTY_NAME_INTERNAL_ID,
          v3_user_value.gaiaid(),
          False))
    if v3_user_value.has_obfuscated_gaiaid():
      v4_entity.property_list().append(self.__v4_string_property(
          _PROPERTY_NAME_USER_ID,
          v3_user_value.obfuscated_gaiaid(),
          False))
    if v3_user_value.has_federated_identity():
      v4_entity.property_list().append(self.__v4_string_property(
          _PROPERTY_NAME_FEDERATED_IDENTITY,
          v3_user_value.federated_identity(),
          False))
    if v3_user_value.has_federated_provider():
      v4_entity.property_list().append(self.__v4_string_property(
          _PROPERTY_NAME_FEDERATED_PROVIDER,
          v3_user_value.federated_provider(),
          False))

  def __is_v3_property_value_union_valid(self, v3_property_value):
    """Returns True if the v3 PropertyValue's union is valid."""
    num_sub_values = 0
    if v3_property_value.has_booleanvalue():
      num_sub_values += 1
    if v3_property_value.has_int64value():
      num_sub_values += 1
    if v3_property_value.has_doublevalue():
      num_sub_values += 1
    if v3_property_value.has_referencevalue():
      num_sub_values += 1
    if v3_property_value.has_stringvalue():
      num_sub_values += 1
    if v3_property_value.has_pointvalue():
      num_sub_values += 1
    if v3_property_value.has_uservalue():
      num_sub_values += 1
    return num_sub_values <= 1

  def __is_v3_property_value_meaning_valid(self, v3_property_value, v3_meaning):
    """Returns True if the v3 PropertyValue's type value matches its meaning."""
    def ReturnTrue():
      return True
    def HasStringValue():
      return v3_property_value.has_stringvalue()
    def HasInt64Value():
      return v3_property_value.has_int64value()
    def HasPointValue():
      return v3_property_value.has_pointvalue()
    def ReturnFalse():
      return False
    value_checkers = {
        entity_pb.Property.NO_MEANING: ReturnTrue,
        entity_pb.Property.INDEX_VALUE: ReturnTrue,
        entity_pb.Property.BLOB: HasStringValue,
        entity_pb.Property.TEXT: HasStringValue,
        entity_pb.Property.BYTESTRING: HasStringValue,
        entity_pb.Property.ATOM_CATEGORY: HasStringValue,
        entity_pb.Property.ATOM_LINK: HasStringValue,
        entity_pb.Property.ATOM_TITLE: HasStringValue,
        entity_pb.Property.ATOM_CONTENT: HasStringValue,
        entity_pb.Property.ATOM_SUMMARY: HasStringValue,
        entity_pb.Property.ATOM_AUTHOR: HasStringValue,
        entity_pb.Property.GD_EMAIL: HasStringValue,
        entity_pb.Property.GD_IM: HasStringValue,
        entity_pb.Property.GD_PHONENUMBER: HasStringValue,
        entity_pb.Property.GD_POSTALADDRESS: HasStringValue,
        entity_pb.Property.BLOBKEY: HasStringValue,
        entity_pb.Property.ENTITY_PROTO: HasStringValue,
        entity_pb.Property.GD_WHEN: HasInt64Value,
        entity_pb.Property.GD_RATING: HasInt64Value,
        entity_pb.Property.GEORSS_POINT: HasPointValue,
        }
    default = ReturnFalse
    return value_checkers.get(v3_meaning, default)()

  def __v3_reference_has_id_or_name(self, v3_ref):
    """Determines if a v3 Reference specifies an ID or name.

    Args:
      v3_ref: an entity_pb.Reference

    Returns:
      boolean: True if the last path element specifies an ID or name.
    """
    path = v3_ref.path()
    assert path.element_size() >= 1
    last_element = path.element(path.element_size() - 1)
    return last_element.has_id() or last_element.has_name()

  def _v3_reference_to_group(self, v3_ref, group):
    """Converts a v3 Reference to a v3 Path representing the entity group.

    The entity group is represented as an entity_pb.Path containing only the
    first element in the provided Reference.

    Args:
      v3_ref: an entity_pb.Reference
      group: an entity_pb.Path to populate
    """
    group.Clear()
    path = v3_ref.path()
    assert path.element_size() >= 1
    group.add_element().CopyFrom(path.element(0))

  def _v3_reference_to_v3_property_value(self, v3_ref, v3_property_value):
    """Converts a v3 Reference to a v3 PropertyValue.

    Args:
      v3_ref: an entity_pb.Reference
      v3_property_value: an entity_pb.PropertyValue to populate
    """
    v3_property_value.Clear()
    reference_value = v3_property_value.mutable_referencevalue()
    if v3_ref.has_app():
      reference_value.set_app(v3_ref.app())
    if v3_ref.has_name_space():
      reference_value.set_name_space(v3_ref.name_space())
    for v3_path_element in v3_ref.path().element_list():
      v3_ref_value_path_element = reference_value.add_pathelement()
      if v3_path_element.has_type():
        v3_ref_value_path_element.set_type(v3_path_element.type())
      if v3_path_element.has_id():
        v3_ref_value_path_element.set_id(v3_path_element.id())
      if v3_path_element.has_name():
        v3_ref_value_path_element.set_name(v3_path_element.name())

  def __v3_reference_value_to_v3_reference(self, v3_ref_value, v3_ref):
    """Converts a v3 ReferenceValue to a v3 Reference.

    Args:
      v3_ref_value: an entity_pb.PropertyValue_ReferenceValue
      v3_ref: an entity_pb.Reference to populate
    """
    v3_ref.Clear()
    if v3_ref_value.has_app():
      v3_ref.set_app(v3_ref_value.app())
    if v3_ref_value.has_name_space():
      v3_ref.set_name_space(v3_ref_value.name_space())
    for v3_ref_value_path_element in v3_ref_value.pathelement_list():
      v3_path_element = v3_ref.mutable_path().add_element()
      if v3_ref_value_path_element.has_type():
        v3_path_element.set_type(v3_ref_value_path_element.type())
      if v3_ref_value_path_element.has_id():
        v3_path_element.set_id(v3_ref_value_path_element.id())
      if v3_ref_value_path_element.has_name():
        v3_path_element.set_name(v3_ref_value_path_element.name())



__entity_converter = _EntityConverter()


def get_entity_converter():
  """Returns a converter for v3 and v4 entities and keys."""
  return __entity_converter


class _BaseQueryConverter(object):
  """Base converter for queries."""

  def __init__(self, entity_converter):
    self._entity_converter = entity_converter

  def v4_to_v3_compiled_cursor(self, v4_cursor, v3_compiled_cursor):
    """Converts a v4 cursor string to a v3 CompiledCursor.

    Args:
      v4_cursor: a string representing a v4 query cursor
      v3_compiled_cursor: a datastore_pb.CompiledCursor to populate
    """
    raise NotImplementedError

  def v3_to_v4_compiled_cursor(self, v3_compiled_cursor):
    """Converts a v3 CompiledCursor to a v4 cursor string.

    Args:
      v3_compiled_cursor: a datastore_pb.CompiledCursor

    Returns:
      a string representing a v4 query cursor
    """
    raise NotImplementedError

  def v4_to_v3_query(self, v4_partition_id, v4_query, v3_query):
    """Converts a v4 Query to a v3 Query.

    Args:
      v4_partition_id: a datastore_v4_pb.PartitionId
      v4_query: a datastore_v4_pb.Query
      v3_query: a datastore_pb.Query to populate

    Raises:
      InvalidConversionError if the query cannot be converted
    """
    v3_query.Clear()

    if v4_partition_id.dataset_id():
      v3_query.set_app(v4_partition_id.dataset_id())
    if v4_partition_id.has_namespace():
      v3_query.set_name_space(v4_partition_id.namespace())

    v3_query.set_persist_offset(True)
    v3_query.set_require_perfect_plan(True)
    v3_query.set_compile(True)


    if v4_query.has_limit():
      v3_query.set_limit(v4_query.limit())
    if v4_query.offset():
      v3_query.set_offset(v4_query.offset())
    if v4_query.has_start_cursor():
      self.v4_to_v3_compiled_cursor(v4_query.start_cursor(),
                                    v3_query.mutable_compiled_cursor())
    if v4_query.has_end_cursor():
      self.v4_to_v3_compiled_cursor(v4_query.end_cursor(),
                                    v3_query.mutable_end_compiled_cursor())


    if v4_query.kind_list():
      _check_conversion(len(v4_query.kind_list()) == 1,
                        'multiple kinds not supported')
      v3_query.set_kind(v4_query.kind(0).name())


    has_key_projection = False
    for prop in v4_query.projection_list():
      if prop.property().name() == _PROPERTY_NAME_KEY:
        has_key_projection = True
      else:
        v3_query.add_property_name(prop.property().name())
    if has_key_projection and not v3_query.property_name_list():
      v3_query.set_keys_only(True)


    for prop in v4_query.group_by_list():
      v3_query.add_group_by_property_name(prop.name())


    self.__populate_v3_filters(v4_query.filter(), v3_query)


    for v4_order in v4_query.order_list():
      v3_order = v3_query.add_order()
      v3_order.set_property(v4_order.property().name())
      if v4_order.has_direction():
        v3_order.set_direction(v4_order.direction())

  def v3_to_v4_query(self, v3_query, v4_query):
    """Converts a v3 Query to a v4 Query.

    Args:
      v3_query: a datastore_pb.Query
      v4_query: a datastore_v4_pb.Query to populate

    Raises:
      InvalidConversionError if the query cannot be converted
    """
    v4_query.Clear()

    _check_conversion(not v3_query.has_distinct(),
                      'distinct option not supported')
    _check_conversion(v3_query.require_perfect_plan(),
                      'non-perfect plans not supported')



    if v3_query.has_limit():
      v4_query.set_limit(v3_query.limit())
    if v3_query.offset():
      v4_query.set_offset(v3_query.offset())
    if v3_query.has_compiled_cursor():
      v4_query.set_start_cursor(
          self.v3_to_v4_compiled_cursor(v3_query.compiled_cursor()))
    if v3_query.has_end_compiled_cursor():
      v4_query.set_end_cursor(
          self.v3_to_v4_compiled_cursor(v3_query.end_compiled_cursor()))


    if v3_query.has_kind():
      v4_query.add_kind().set_name(v3_query.kind())


    for name in v3_query.property_name_list():
      v4_query.add_projection().mutable_property().set_name(name)
    if v3_query.keys_only():
      v4_query.add_projection().mutable_property().set_name(_PROPERTY_NAME_KEY)


    for name in v3_query.group_by_property_name_list():
      v4_query.add_group_by().set_name(name)


    num_v4_filters = len(v3_query.filter_list())
    if v3_query.has_ancestor():
      num_v4_filters += 1

    if num_v4_filters == 1:
      get_property_filter = self.__get_property_filter
    elif num_v4_filters >= 1:
      v4_query.mutable_filter().mutable_composite_filter().set_operator(
          datastore_v4_pb.CompositeFilter.AND)
      get_property_filter = self.__add_property_filter

    if v3_query.has_ancestor():
      self.__v3_query_to_v4_ancestor_filter(v3_query,
                                            get_property_filter(v4_query))
    for v3_filter in v3_query.filter_list():
      self.__v3_filter_to_v4_property_filter(v3_filter,
                                             get_property_filter(v4_query))


    for v3_order in v3_query.order_list():
      v4_order = v4_query.add_order()
      v4_order.mutable_property().set_name(v3_order.property())
      if v3_order.has_direction():
        v4_order.set_direction(v3_order.direction())

  def __get_property_filter(self, v4_query):
    """Returns the PropertyFilter from the query's top-level filter."""
    return v4_query.mutable_filter().mutable_property_filter()

  def __add_property_filter(self, v4_query):
    """Adds and returns a PropertyFilter from the query's composite filter."""
    v4_comp_filter = v4_query.mutable_filter().mutable_composite_filter()
    return v4_comp_filter.add_filter().mutable_property_filter()

  def __populate_v3_filters(self, v4_filter, v3_query):
    """Populates a filters for a v3 Query.

    Args:
      v4_filter: a datastore_v4_pb.Filter
      v3_query: a datastore_pb.Query to populate with filters
    """
    if v4_filter.has_property_filter():
      v4_property_filter = v4_filter.property_filter()
      if (v4_property_filter.operator()
          == datastore_v4_pb.PropertyFilter.HAS_ANCESTOR):
        _check_conversion(v4_property_filter.value().has_key_value(),
                          'HAS_ANCESTOR requires a reference value')
        _check_conversion((v4_property_filter.property().name()
                           == _PROPERTY_NAME_KEY),
                          'unsupported property')
        _check_conversion(not v3_query.has_ancestor(),
                          'duplicate ancestor constraint')
        self._entity_converter.v4_to_v3_reference(
            v4_property_filter.value().key_value(),
            v3_query.mutable_ancestor())
      else:
        v3_filter = v3_query.add_filter()
        property_name = v4_property_filter.property().name()
        v3_filter.set_op(v4_property_filter.operator())
        _check_conversion(not v4_property_filter.value().list_value_list(),
                          ('unsupported value type, %s, in property filter'
                           ' on "%s"' % ('list_value', property_name)))
        prop = v3_filter.add_property()
        prop.set_multiple(False)
        prop.set_name(property_name)
        self._entity_converter.v4_value_to_v3_property_value(
            v4_property_filter.value(), prop.mutable_value())
    elif v4_filter.has_composite_filter():
      _check_conversion((v4_filter.composite_filter().operator()
                         == datastore_v4_pb.CompositeFilter.AND),
                        'unsupported composite property operator')
      for v4_sub_filter in v4_filter.composite_filter().filter_list():
        self.__populate_v3_filters(v4_sub_filter, v3_query)

  def __v3_filter_to_v4_property_filter(self, v3_filter, v4_property_filter):
    """Converts a v3 Filter to a v4 PropertyFilter.

    Args:
      v3_filter: a datastore_pb.Filter
      v4_property_filter: a datastore_v4_pb.PropertyFilter to populate

    Raises:
      InvalidConversionError if the filter cannot be converted
    """
    _check_conversion(v3_filter.property_size() == 1, 'invalid filter')
    _check_conversion(v3_filter.op() <= 5,
                      'unsupported filter op: %d' % v3_filter.op())
    v4_property_filter.Clear()
    v4_property_filter.set_operator(v3_filter.op())
    v4_property_filter.mutable_property().set_name(v3_filter.property(0).name())
    self._entity_converter.v3_property_to_v4_value(
        v3_filter.property(0), True, v4_property_filter.mutable_value())

  def __v3_query_to_v4_ancestor_filter(self, v3_query, v4_property_filter):
    """Converts a v3 Query to a v4 ancestor PropertyFilter.

    Args:
      v3_query: a datastore_pb.Query
      v4_property_filter: a datastore_v4_pb.PropertyFilter to populate
    """
    v4_property_filter.Clear()
    v4_property_filter.set_operator(
        datastore_v4_pb.PropertyFilter.HAS_ANCESTOR)
    prop = v4_property_filter.mutable_property()
    prop.set_name(_PROPERTY_NAME_KEY)
    self._entity_converter.v3_to_v4_key(
        v3_query.ancestor(),
        v4_property_filter.mutable_value().mutable_key_value())


class _StubQueryConverter(_BaseQueryConverter):
  """A query converter suitable for use in stubs."""

  def v4_to_v3_compiled_cursor(self, v4_cursor, v3_compiled_cursor):
    v3_compiled_cursor.Clear()
    v3_compiled_cursor.ParseFromString(v4_cursor)

  def v3_to_v4_compiled_cursor(self, v3_compiled_cursor):
    return v3_compiled_cursor.SerializeToString()



__stub_query_converter = _StubQueryConverter(__entity_converter)


def get_stub_query_converter():
  """Returns a converter for v3 and v4 queries (not suitable for production).

  This converter is suitable for use in stubs but not for production.

  Returns:
    a _StubQueryConverter
  """
  return __stub_query_converter


class _BaseServiceConverter(object):
  """Base converter for v3 and v4 request/response protos."""

  def __init__(self, entity_converter, query_converter):
    self._entity_converter = entity_converter
    self._query_converter = query_converter

  def v4_to_v3_cursor(self, v4_query_handle, v3_cursor):
    """Converts a v4 cursor string to a v3 Cursor.

    Args:
      v4_query_handle: a string representing a v4 query handle
      v3_cursor: a datastore_pb.Cursor to populate
    """
    raise NotImplementedError

  def _v3_to_v4_query_handle(self, v3_cursor):
    """Converts a v3 Cursor to a v4 query handle string.

    Args:
      v3_cursor: a datastore_pb.Cursor

    Returns:
      a string representing a v4 cursor
    """
    raise NotImplementedError

  def v4_to_v3_txn(self, v4_txn, v3_txn):
    """Converts a v4 transaction string to a v3 Transaction.

    Args:
      v4_txn: a string representing a v4 transaction
      v3_txn: a datastore_pb.Transaction to populate
    """
    raise NotImplementedError

  def _v3_to_v4_txn(self, v3_txn):
    """Converts a v3 Transaction to a v4 transaction string.

    Args:
      v3_txn: a datastore_pb.Transaction

    Returns:
      a string representing a v4 transaction
    """
    raise NotImplementedError




  def v4_to_v3_begin_transaction_req(self, app_id, v4_req):
    """Converts a v4 BeginTransactionRequest to a v3 BeginTransactionRequest.

    Args:
      app_id: app id
      v4_req: a datastore_v4_pb.BeginTransactionRequest

    Returns:
      a datastore_pb.BeginTransactionRequest
    """
    v3_req = datastore_pb.BeginTransactionRequest()
    v3_req.set_app(app_id)
    v3_req.set_allow_multiple_eg(v4_req.cross_group())
    return v3_req

  def v3_to_v4_begin_transaction_req(self, v3_req):
    """Converts a v3 BeginTransactionRequest to a v4 BeginTransactionRequest.

    Args:
      v3_req: a datastore_pb.BeginTransactionRequest

    Returns:
      a datastore_v4_pb.BeginTransactionRequest
    """
    v4_req = datastore_v4_pb.BeginTransactionRequest()

    if v3_req.has_allow_multiple_eg():
      v4_req.set_cross_group(v3_req.allow_multiple_eg())

    return v4_req

  def v4_begin_transaction_resp_to_v3_txn(self, v4_resp):
    """Converts a v4 BeginTransactionResponse to a v3 Transaction.

    Args:
      v4_resp: datastore_v4_pb.BeginTransactionResponse

    Returns:
      a a datastore_pb.Transaction
    """
    v3_txn = datastore_pb.Transaction()
    self.v4_to_v3_txn(v4_resp.transaction(), v3_txn)
    return v3_txn

  def v3_to_v4_begin_transaction_resp(self, v3_resp):
    """Converts a v3 Transaction to a v4 BeginTransactionResponse.

    Args:
      v3_resp: a datastore_pb.Transaction

    Returns:
      a datastore_v4_pb.BeginTransactionResponse
    """
    v4_resp = datastore_v4_pb.BeginTransactionResponse()
    v4_resp.set_transaction(self._v3_to_v4_txn(v3_resp))
    return v4_resp




  def v4_rollback_req_to_v3_txn(self, v4_req):
    """Converts a v4 RollbackRequest to a v3 Transaction.

    Args:
      v4_req: a datastore_v4_pb.RollbackRequest

    Returns:
      a datastore_pb.Transaction
    """
    v3_txn = datastore_pb.Transaction()
    self.v4_to_v3_txn(v4_req.transaction(), v3_txn)
    return v3_txn

  def v3_to_v4_rollback_req(self, v3_req):
    """Converts a v3 Transaction to a v4 RollbackRequest.

    Args:
      v3_req: datastore_pb.Transaction

    Returns:
      a a datastore_v4_pb.RollbackRequest
    """
    v4_req = datastore_v4_pb.RollbackRequest()
    v4_req.set_transaction(self._v3_to_v4_txn(v3_req))
    return v4_req




  def v4_commit_req_to_v3_txn(self, v4_req):
    """Converts a v4 CommitRequest to a v3 Transaction.

    Args:
      v4_req: a datastore_v4_pb.CommitRequest

    Returns:
      a datastore_pb.Transaction
    """
    v3_txn = datastore_pb.Transaction()
    self.v4_to_v3_txn(v4_req.transaction(), v3_txn)
    return v3_txn




  def v4_run_query_req_to_v3_query(self, v4_req):
    """Converts a v4 RunQueryRequest to a v3 Query.

    GQL is not supported.

    Args:
      v4_req: a datastore_v4_pb.RunQueryRequest

    Returns:
      a datastore_pb.Query
    """

    _check_conversion(not v4_req.has_gql_query(), 'GQL not supported')
    v3_query = datastore_pb.Query()
    self._query_converter.v4_to_v3_query(v4_req.partition_id(), v4_req.query(),
                                         v3_query)


    if v4_req.has_suggested_batch_size():
      v3_query.set_count(v4_req.suggested_batch_size())


    read_options = v4_req.read_options()
    if read_options.has_transaction():
      self.v4_to_v3_txn(read_options.transaction(),
                        v3_query.mutable_transaction())
    elif (read_options.read_consistency()
          == datastore_v4_pb.ReadOptions.EVENTUAL):
      v3_query.set_strong(False)
      v3_query.set_failover_ms(-1)
    elif read_options.read_consistency() == datastore_v4_pb.ReadOptions.STRONG:
      v3_query.set_strong(True)

    if v4_req.has_min_safe_time_seconds():
      v3_query.set_min_safe_time_seconds(v4_req.min_safe_time_seconds())

    return v3_query

  def v3_to_v4_run_query_req(self, v3_req):
    """Converts a v3 Query to a v4 RunQueryRequest.

    Args:
      v3_req: a datastore_pb.Query

    Returns:
      a datastore_v4_pb.RunQueryRequest
    """
    v4_req = datastore_v4_pb.RunQueryRequest()


    v4_partition_id = v4_req.mutable_partition_id()
    v4_partition_id.set_dataset_id(v3_req.app())
    if v3_req.name_space():
      v4_partition_id.set_namespace(v3_req.name_space())


    if v3_req.has_count():
      v4_req.set_suggested_batch_size(v3_req.count())


    if v3_req.has_transaction():
      v4_req.mutable_read_options().set_transaction(
          self._v3_to_v4_txn(v3_req.transaction()))
    elif v3_req.strong():
      v4_req.mutable_read_options().set_read_consistency(
          datastore_v4_pb.ReadOptions.STRONG)
    elif v3_req.has_failover_ms():
      v4_req.mutable_read_options().set_read_consistency(
          datastore_v4_pb.ReadOptions.EVENTUAL)
    if v3_req.has_min_safe_time_seconds():
      v4_req.set_min_safe_time_seconds(v3_req.min_safe_time_seconds())

    self._query_converter.v3_to_v4_query(v3_req, v4_req.mutable_query())

    return v4_req

  def v4_run_query_resp_to_v3_query_result(self, v4_resp):
    """Converts a V4 RunQueryResponse to a v3 QueryResult.

    Args:
      v4_resp: a datastore_v4_pb.QueryResult

    Returns:
      a datastore_pb.QueryResult
    """
    v3_resp = self.v4_to_v3_query_result(v4_resp.batch())


    if v4_resp.has_query_handle():
      self.v4_to_v3_cursor(v4_resp.query_handle(), v3_resp.mutable_cursor())

    return v3_resp

  def v3_to_v4_run_query_resp(self, v3_resp):
    """Converts a v3 QueryResult to a V4 RunQueryResponse.

    Args:
      v3_resp: a datastore_pb.QueryResult

    Returns:
      a datastore_v4_pb.RunQueryResponse
    """
    v4_resp = datastore_v4_pb.RunQueryResponse()
    self.v3_to_v4_query_result_batch(v3_resp, v4_resp.mutable_batch())

    if v3_resp.has_cursor():
      v4_resp.set_query_handle(
          self._query_converter.v3_to_v4_compiled_cursor(v3_resp.cursor()))

    return v4_resp




  def v4_to_v3_next_req(self, v4_req):
    """Converts a v4 ContinueQueryRequest to a v3 NextRequest.

    Args:
      v4_req: a datastore_v4_pb.ContinueQueryRequest

    Returns:
      a datastore_pb.NextRequest
    """
    v3_req = datastore_pb.NextRequest()
    v3_req.set_compile(True)
    self.v4_to_v3_cursor(v4_req.query_handle(), v3_req.mutable_cursor())
    return v3_req

  def v3_to_v4_continue_query_resp(self, v3_resp):
    """Converts a v3 QueryResult to a v4 ContinueQueryResponse.

    Args:
      v3_resp: a datstore_pb.QueryResult

    Returns:
      a datastore_v4_pb.ContinueQueryResponse
    """
    v4_resp = datastore_v4_pb.ContinueQueryResponse()
    self.v3_to_v4_query_result_batch(v3_resp, v4_resp.mutable_batch())
    return v4_resp




  def v4_to_v3_get_req(self, v4_req):
    """Converts a v4 LookupRequest to a v3 GetRequest.

    Args:
      v4_req: a datastore_v4_pb.LookupRequest

    Returns:
      a datastore_pb.GetRequest
    """
    v3_req = datastore_pb.GetRequest()
    v3_req.set_allow_deferred(True)


    if v4_req.read_options().has_transaction():
      self.v4_to_v3_txn(v4_req.read_options().transaction(),
                        v3_req.mutable_transaction())
    elif (v4_req.read_options().read_consistency()
          == datastore_v4_pb.ReadOptions.EVENTUAL):
      v3_req.set_strong(False)
      v3_req.set_failover_ms(-1)
    elif (v4_req.read_options().read_consistency()
          == datastore_v4_pb.ReadOptions.STRONG):
      v3_req.set_strong(True)

    for v4_key in v4_req.key_list():
      self._entity_converter.v4_to_v3_reference(v4_key, v3_req.add_key())

    return v3_req

  def v3_to_v4_lookup_req(self, v3_req):
    """Converts a v3 GetRequest to a v4 LookupRequest.

    Args:
      v3_req: a datastore_pb.GetRequest

    Returns:
      a datastore_v4_pb.LookupRequest
    """
    v4_req = datastore_v4_pb.LookupRequest()
    _check_conversion(v3_req.allow_deferred(), 'allow_deferred must be true')


    if v3_req.has_transaction():
      v4_req.mutable_read_options().set_transaction(
          self._v3_to_v4_txn(v3_req.transaction()))
    elif v3_req.strong():
      v4_req.mutable_read_options().set_read_consistency(
          datastore_v4_pb.ReadOptions.STRONG)
    elif v3_req.has_failover_ms():
      v4_req.mutable_read_options().set_read_consistency(
          datastore_v4_pb.ReadOptions.EVENTUAL)

    for v3_ref in v3_req.key_list():
      self._entity_converter.v3_to_v4_key(v3_ref, v4_req.add_key())

    return v4_req

  def v4_to_v3_get_resp(self, v4_resp):
    """Converts a v4 LookupResponse to a v3 GetResponse.

    Args:
      v4_resp: a datastore_v4_pb.LookupResponse

    Returns:
      a datastore_pb.GetResponse
    """
    v3_resp = datastore_pb.GetResponse()

    for v4_key in v4_resp.deferred_list():
      self._entity_converter.v4_to_v3_reference(v4_key, v3_resp.add_deferred())
    for v4_found in v4_resp.found_list():
      self._entity_converter.v4_to_v3_entity(
          v4_found.entity(), v3_resp.add_entity().mutable_entity())
    for v4_missing in v4_resp.missing_list():
      self._entity_converter.v4_to_v3_reference(
          v4_missing.entity().key(),
          v3_resp.add_entity().mutable_key())

    return v3_resp

  def v3_to_v4_lookup_resp(self, v3_resp):
    """Converts a v3 GetResponse to a v4 LookupResponse.

    Args:
      v3_resp: a datastore_pb.GetResponse

    Returns:
      a datastore_v4_pb.LookupResponse
    """
    v4_resp = datastore_v4_pb.LookupResponse()

    for v3_ref in v3_resp.deferred_list():
      self._entity_converter.v3_to_v4_key(v3_ref, v4_resp.add_deferred())
    for v3_entity in v3_resp.entity_list():
      if v3_entity.has_entity():
        self._entity_converter.v3_to_v4_entity(
            v3_entity.entity(),
            v4_resp.add_found().mutable_entity())
      if v3_entity.has_key():
        self._entity_converter.v3_to_v4_key(
            v3_entity.key(),
            v4_resp.add_missing().mutable_entity().mutable_key())

    return v4_resp

  def v4_to_v3_query_result(self, v4_batch):
    """Converts a v4 QueryResultBatch to a v3 QueryResult.

    Args:
      v4_batch: a datastore_v4_pb.QueryResultBatch

    Returns:
      a datastore_pb.QueryResult
    """
    v3_result = datastore_pb.QueryResult()


    v3_result.set_more_results(
        (v4_batch.more_results()
         == datastore_v4_pb.QueryResultBatch.NOT_FINISHED))
    if v4_batch.has_end_cursor():
      self._query_converter.v4_to_v3_compiled_cursor(
          v4_batch.end_cursor(), v3_result.mutable_compiled_cursor())


    if v4_batch.entity_result_type() == datastore_v4_pb.EntityResult.PROJECTION:
      v3_result.set_index_only(True)
    elif v4_batch.entity_result_type() == datastore_v4_pb.EntityResult.KEY_ONLY:
      v3_result.set_keys_only(True)


    if v4_batch.has_skipped_results():
      v3_result.set_skipped_results(v4_batch.skipped_results())
    for v4_entity in v4_batch.entity_result_list():
      v3_entity = v3_result.add_result()
      self._entity_converter.v4_to_v3_entity(v4_entity.entity(), v3_entity)
      if v4_batch.entity_result_type() != datastore_v4_pb.EntityResult.FULL:


        v3_entity.clear_entity_group()

    return v3_result

  def v3_to_v4_query_result_batch(self, v3_result, v4_batch):
    """Converts a v3 QueryResult to a v4 QueryResultBatch.

    Args:
      v3_result: a datastore_pb.QueryResult
      v4_batch: a datastore_v4_pb.QueryResultBatch to populate
    """
    v4_batch.Clear()


    if v3_result.more_results():
      v4_batch.set_more_results(datastore_v4_pb.QueryResultBatch.NOT_FINISHED)
    else:
      v4_batch.set_more_results(
          datastore_v4_pb.QueryResultBatch.MORE_RESULTS_AFTER_LIMIT)
    if v3_result.has_compiled_cursor():
      v4_batch.set_end_cursor(
          self._query_converter.v3_to_v4_compiled_cursor(
              v3_result.compiled_cursor()))


    if v3_result.keys_only():
      v4_batch.set_entity_result_type(datastore_v4_pb.EntityResult.KEY_ONLY)
    elif v3_result.index_only():
      v4_batch.set_entity_result_type(datastore_v4_pb.EntityResult.PROJECTION)
    else:
      v4_batch.set_entity_result_type(datastore_v4_pb.EntityResult.FULL)


    if v3_result.has_skipped_results():
      v4_batch.set_skipped_results(v3_result.skipped_results())
    for v3_entity in v3_result.result_list():
      v4_entity_result = datastore_v4_pb.EntityResult()
      self._entity_converter.v3_to_v4_entity(v3_entity,
                                             v4_entity_result.mutable_entity())
      v4_batch.entity_result_list().append(v4_entity_result)


class _StubServiceConverter(_BaseServiceConverter):
  """Converter for request/response protos suitable for use in stubs."""

  def v4_to_v3_cursor(self, v4_query_handle, v3_cursor):
    v3_cursor.ParseFromString(v4_query_handle)
    return v3_cursor

  def _v3_to_v4_query_handle(self, v3_cursor):
    return v3_cursor.SerializeToString()

  def v4_to_v3_txn(self, v4_txn, v3_txn):
    v3_txn.ParseFromString(v4_txn)
    return v3_txn

  def _v3_to_v4_txn(self, v3_txn):
    return v3_txn.SerializeToString()



__stub_service_converter = _StubServiceConverter(__entity_converter,
                                                 __stub_query_converter)


def get_stub_service_converter():
  """Returns a converter for v3 and v4 service request/response protos.

  This converter is suitable for use in stubs but not for production.

  Returns:
    a _StubServiceConverter
  """
  return __stub_service_converter
