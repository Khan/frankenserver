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
 * Provide _gethostname() function that wraps ModulesService::getHostname().
 *
 * In order to allow unit testing on an unmodified PHP runtime the function
 * implementation definition is prefixed with an underscore. The actual function
 * name is mapped in Setup.php which simply calls the implementation.
 *
 * @see http://us2.php.net/manual/en/function.gethostname.php
 */

namespace google\appengine\runtime;

use google\appengine\api\modules\ModulesService;

/**
 * Gets the standard host name for the local machine.
 *
 * @return bool|string
 *   a string with the hostname on success, otherwise FALSE is returned.
 */
function _gethostname() {
  // In order to be consistent with PHP core implementation, wrap any exception
  // and return false.
  try {
    return ModulesService::getHostname();
  }
  catch (\Exception $e) {
    return false;
  }
}
