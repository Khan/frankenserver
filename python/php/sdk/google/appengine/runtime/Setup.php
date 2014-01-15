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
 * Performs any required initialization before the user's script is run.
 */

// Ensure that the class autoloader is the first include.
require_once 'google/appengine/runtime/autoloader.php';
require_once 'google/appengine/runtime/Memcache.php';
require_once 'google/appengine/runtime/Memcached.php';
require_once 'google/appengine/ext/session/MemcacheSessionHandler.php';
require_once 'google/appengine/api/mail/MailService.php';

// Setup the Memcache session handler
google\appengine\ext\session\configureMemcacheSessionHandler();

// Setup the GS stream wrapper
$url_flags = STREAM_IS_URL;
if (GAE_INCLUDE_REQUIRE_GS_STREAMS === 1) {
  // By clearing the STREAM_IS_URL flag we allow this stream handler to be used
  // in include & require calls.
  $url_flags = 0;
}

stream_wrapper_register('gs',
    '\google\appengine\ext\cloud_storage_streams\CloudStorageStreamWrapper',
    $url_flags);

// Map core PHP function implementations to proper function names. All function
// implementations should be prefixed with an underscore. The implementations
// should be mapped to the real (un-prefixed) function name and lazy-loaded.
// The underscore prefixed functions may then be used for unit testing on an
// unmodified PHP interpreter which will not allow functions to be redeclared.
//
// Additionally due to e2e tests also running on devappserver with an
// unmodified PHP interpreter the function definitions must be defined
// conditionally and those e2e tests excluded from devappserver.
if (strpos($_SERVER['SERVER_SOFTWARE'], 'Google App Engine') !== false) {
  function gethostname() {
    require_once 'google/appengine/runtime/GetHostName.php';
    return google\appengine\runtime\_gethostname();
  }
}
