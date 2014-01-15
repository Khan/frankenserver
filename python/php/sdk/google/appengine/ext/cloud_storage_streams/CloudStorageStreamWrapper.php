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
 * A user space stream wrapper for reading and writing to Google Cloud Storage.
 *
 * See: http://www.php.net/manual/en/class.streamwrapper.php
 *
 */

namespace google\appengine\ext\cloud_storage_streams;

use google\appengine\api\cloud_storage\CloudStorageTools;
use google\appengine\util\ArrayUtil;

/**
 * Allowed stream_context options.
 * "anonymous": Boolean, if set then OAuth tokens will not be generated.
 * "acl": The ACL to apply when creating an object.
 * "Content-Type": The content type of the object being written.
 */
final class CloudStorageStreamWrapper {

  // The client instance that we're using to communicate with GS.
  private $client;

  // Must be public according to PHP documents - We capture the contents when
  // constructing objects.
  public $context;

  const STREAM_OPEN_FOR_INCLUDE = 0x80;

  private static $valid_read_modes = ['r', 'rb', 'rt'];
  private static $valid_write_modes = ['w', 'wb', 'wt'];

  /**
   * Constructs a new stream wrapper.
   */
  public function __construct() {
  }

  /**
   * Destructs an existing stream wrapper.
   */
  public function __destruct() {
  }

  /**
   * Close an open directory handle.
   */
  public function dir_closedir() {
    assert(isset($this->client));
    $this->client->close();
    $this->client = null;
  }

  /**
   * Open a directory handle.
   */
  public function dir_opendir($path, $options) {
    if (!CloudStorageTools::parseFilename($path, $bucket, $object)) {
      trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
                    E_USER_ERROR);
      return false;
    }

    $this->client = new CloudStorageDirectoryClient($bucket,
                                                    $object,
                                                    $this->context);
    return $this->client->initialise();
  }

  /**
   * Read entry from the directory handle.
   *
   * @return string representing the next filename, of false if there is no
   * next file.
   */
  public function dir_readdir() {
    assert(isset($this->client));
    return $this->client->dir_readdir();
  }

  /**
   * Reset the output returned from dir_readdir.
   *
   * @return bool true if the stream can be rewound, false otherwise.
   */
  public function dir_rewinddir() {
    assert(isset($this->client));
    return $this->client->dir_rewinddir();
  }

  public function mkdir($path, $mode, $options) {
    if (!CloudStorageTools::parseFilename($path, $bucket, $object) ||
        !isset($object)) {
      if (($options | STREAM_REPORT_ERRORS) != 0) {
        trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
                      E_USER_ERROR);
      }
      return false;
    }
    $client = new CloudStorageDirectoryClient($bucket,
                                              $object,
                                              $this->context);
    return $client->mkdir($options);
  }

  public function rmdir($path, $options) {
    if (!CloudStorageTools::parseFilename($path, $bucket, $object) ||
        !isset($object)) {
      if (($options | STREAM_REPORT_ERRORS) != 0) {
        trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
                      E_USER_ERROR);
      }
      return false;
    }
    $client = new CloudStorageDirectoryClient($bucket,
                                              $object,
                                              $this->context);
    return $client->rmdir($options);
  }

  /**
   * Rename a cloud storage object.
   *
   * @return TRUE if the object was renamed, FALSE otherwise
   */
  public function rename($from, $to) {
    if (!CloudStorageTools::parseFilename($from, $from_bucket, $from_object) ||
        !isset($from_object)) {
      trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $from),
                    E_USER_ERROR);
      return false;
    }
    if (!CloudStorageTools::parseFilename($to, $to_bucket, $to_object) ||
        !isset($to_object)) {
      trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $to),
                    E_USER_ERROR);
      return false;
    }
    $client = new CloudStorageRenameClient($from_bucket,
                                           $from_object,
                                           $to_bucket,
                                           $to_object,
                                           $this->context);
    return $client->rename();
  }

  /**
   * Retrieve the underlaying resource of the stream, called in response to
   * stream_select().
   *
   * As GS streams have no underlying resource, we can only return false
   */
  public function stream_cast() {
    return false;
  }

  /**
   * All resources that were locked, or allocated, by the wrapper should be
   * released.
   *
   * No value is returned.
   */
  public function stream_close() {
    assert(isset($this->client));
    $this->client->close();
    $this->client = null;
  }

  /**
   * Tests for end-of-file on a file pointer.
   *
   * @return TRUE if the read/write position is at the end of the stream and if
   * no more data is available to be read, or FALSE otherwise
   */
  public function stream_eof() {
    assert(isset($this->client));
    return $this->client->eof();
  }

  /**
   * Flushes the output.
   *
   * @return TRUE if the cached data was successfully stored (or if there was
   * no data to store), or FALSE if the data could not be stored.
   */
  public function stream_flush() {
    assert(isset($this->client));
    return $this->client->flush();
  }

  public function stream_metadata($path, $option, $value) {
    return false;
  }

  public function stream_open($path, $mode, $options, &$opened_path) {
    if (!CloudStorageTools::parseFilename($path, $bucket, $object) ||
        !isset($object)) {
      if (($options & STREAM_REPORT_ERRORS) != 0) {
        trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
                E_USER_ERROR);
      }
      return false;
    }

    if (($options & self::STREAM_OPEN_FOR_INCLUDE) != 0) {
      $allowed_buckets = explode(",", GAE_INCLUDE_GS_BUCKETS);
      $include_allowed = false;
      foreach ($allowed_buckets as $bucket_name) {
        $bucket_name = trim($bucket_name);
        if ($bucket_name === $bucket) {
          $include_allowed = true;
          break;
        }
      }
      if (!$include_allowed) {
        if (($options & STREAM_REPORT_ERRORS) != 0) {
          trigger_error(
              sprintf("Not allowed to include/require from bucket '%s'",
                      $bucket),
              E_USER_ERROR);
        }
        return false;
      }
    }

    if (in_array($mode, self::$valid_read_modes)) {
      $this->client = new CloudStorageReadClient($bucket,
                                                 $object,
                                                 $this->context);
    } else if (in_array($mode, self::$valid_write_modes)) {
      $this->client = new CloudStorageWriteClient($bucket,
                                                  $object,
                                                  $this->context);
    } else {
      if (($options & STREAM_REPORT_ERRORS) != 0) {
        trigger_error(sprintf("Invalid mode: %s", $mode), E_USER_ERROR);
      }
      return false;
    }

    return $this->client->initialize();
  }

  /**
   * Read from a stream, return string of bytes.
   */
  public function stream_read($count) {
    assert(isset($this->client));
    return $this->client->read($count);
  }

  public function stream_seek($offset, $whence) {
    assert(isset($this->client));
    return $this->client->seek($offset, $whence);
  }

  public function stream_set_option($option, $arg1, $arg2) {
    assert(isset($this->client));
    return false;
  }

  public function stream_stat() {
    assert(isset($this->client));
    return $this->client->stat();
  }

  public function stream_tell() {
    assert(isset($this->client));
    return $this->client->tell();
  }

  /**
   * Return the number of bytes written.
   */
  public function stream_write($data) {
    assert(isset($this->client));
    return $this->client->write($data);
  }

  /**
   * Deletes a file. Called in response to unlink($filename).
   */
  public function unlink($path) {
    if (!CloudStorageTools::parseFilename($path, $bucket, $object) ||
        !isset($object)) {
      trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
              E_USER_ERROR);
      return false;
    }

    $this->client = new CloudStorageDeleteClient($bucket,
                                                 $object,
                                                 $this->context);
    return $this->client->delete();
  }

  public function url_stat($path, $flags) {
    if (!CloudStorageTools::parseFilename($path, $bucket, $object)) {
      if (($flags & STREAM_URL_STAT_QUIET) != 0) {
        trigger_error(sprintf("Invalid Google Cloud Storage path: %s", $path),
                E_USER_ERROR);
        return false;
      }
    }

    $client = new CloudStorageUrlStatClient($bucket,
                                            $object,
                                            $this->context,
                                            $flags);
    return $client->stat();
  }

}
