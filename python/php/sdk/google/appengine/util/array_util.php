<?php
/**
 * Copyright 2007 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
/**
 * Various utilities for working with PHP arrays.
 *
 */
namespace google\appengine\util;

/**
 * Various PHP array related utility functions.
 */
final class ArrayUtil {
  /**
   * Find an item in an associative array by a key value, or return null if not
   * found.
   *
   * @param array $array - The array to search
   * @param mixed $key - The key to search for.
   *
   * @return mixed The value of the item in the array with the given key,
   * or null if not found.
   */
  public static function findByKeyOrNull($array, $key) {
    return static::findByKeyOrDefault($array, $key, null);
  }

  /**
   * Find an item in an associative array by a key value, or return default if
   * not found.
   *
   * @param array $array - The array to search
   * @param mixed $key - The key to search for.
   * @param mixed $default - The value to return if key is not found.
   *
   * @return mixed The value of the item in the array with the given key,
   * or the given default if not found.
   */
  public static function findByKeyOrDefault($array, $key, $default) {
    if (array_key_exists($key, $array)) {
      return $array[$key];
    }
    return $default;
  }

  /**
   * Merge a number of arrays using a case insensitive comparison for the array
   * keys.
   *
   * @param mixed array Two or more arrays to merge.
   *
   * @returns array The merged array.
   *
   * @throws InvalidArgumentException If less than two arrays are passed to
   *     the function, or one of the arguments is not an array.
   */
  public static function arrayMergeIgnoreCase() {
    if (func_num_args() < 2) {
      throw new \InvalidArgumentException(
          "At least two arrays must be supplied.");
    }
    $result = [];
    $key_mapping = [];
    $input_args = func_get_args();

    foreach($input_args as $args) {
      if (!is_array($args)) {
        throw new \InvalidArgumentException(
            "Arguments are expected to be arrays, found " . gettype($arg));
      }
      foreach($args as $key => $val) {
        $lower_case_key = strtolower($key);
        if (array_key_exists($lower_case_key, $key_mapping)) {
          $result[$key_mapping[$lower_case_key]] = $val;
        } else {
          $key_mapping[$lower_case_key] = $key;
          $result[$key] = $val;
        }
      }
    }
    return $result;
  }
}
