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
 * Unit tests for GetHostName.php [_gethostname()].
 */

namespace google\appengine\runtime;

require_once 'google/appengine/api/modules/modules_service_pb.php';
require_once 'google/appengine/runtime/ApplicationError.php';
require_once 'google/appengine/runtime/GetHostName.php';
require_once 'google/appengine/testing/ApiProxyTestBase.php';

use google\appengine\GetHostnameRequest;
use google\appengine\GetHostnameResponse;
use google\appengine\ModulesServiceError\ErrorCode;
use google\appengine\runtime\ApplicationError;
use google\appengine\testing\ApiProxyTestBase;

class GetHostNameTest extends ApiProxyTestBase {
  // See api\modules\ModulesServiceTest::testGetHostname().
  public function testGetHostName() {
    $req = new GetHostnameRequest();
    $resp = new GetHostnameResponse();

    $resp->setHostname('hostname');

    $this->apiProxyMock->expectCall('modules', 'GetHostname', $req, $resp);

    $this->assertEquals('hostname', _gethostname());
    $this->apiProxyMock->verify();
  }

  public function testGetHostNameException() {
    $req = new GetHostnameRequest();
    $resp = new ApplicationError(ErrorCode::TRANSIENT_ERROR, 'unkonwn');

    $this->apiProxyMock->expectCall('modules', 'GetHostname', $req, $resp);

    $this->assertEquals(false, _gethostname());
    $this->apiProxyMock->verify();
  }
}
