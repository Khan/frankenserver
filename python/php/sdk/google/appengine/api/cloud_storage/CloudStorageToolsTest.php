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
 * PHP Unit tests for the CloudStorageTools.
 *
 */
namespace google\appengine\api\cloud_storage;

use google\appengine\testing\ApiProxyTestBase;
use google\appengine\BlobstoreServiceError;
use google\appengine\ImagesServiceError;

// Provide a mock ini_get as we cannot alter the value of upload_max_filesize
// from a script.
function ini_get($key) {
  if ($key === 'upload_max_filesize') {
    return CloudStorageToolsTest::$mock_upload_max_filesize;
  }
  return \ini_get($key);
}

/**
 * Unit test for CloudStorageTools class.
 *
 * @outputBuffering disabled
 */
class CloudStorageToolsTest extends ApiProxyTestBase {

  public static $mock_upload_max_filesize = 0;

  public function setUp() {
    parent::setUp();
    $this->_SERVER = $_SERVER;
    self::$mock_upload_max_filesize = '0';

    // This is a a hacky workaround to the fact that you cannot use the header()
    // call in PHPUnit because you hit "headers already sent" errors.
    $this->sent_headers = [];
    $mock_send_header = function($key, $value){
      $this->sent_headers[$key] = $value;
    };
    CloudStorageTools::setSendHeaderFunction($mock_send_header);
  }

  public function tearDown() {
    $_SERVER = $this->_SERVER;

    // Reset environmental variables.
    putenv("SERVER_SOFTWARE=");
    putenv("HTTP_HOST=");

    parent::tearDown();
  }

  private function expectFilenameTranslation($filename, $blob_key) {
    $req = new \google\appengine\CreateEncodedGoogleStorageKeyRequest();
    $req->setFilename($filename);

    $resp = new \google\appengine\CreateEncodedGoogleStorageKeyResponse();
    $resp->setBlobKey($blob_key);

    $this->apiProxyMock->expectCall('blobstore',
                                    'CreateEncodedGoogleStorageKey',
                                    $req,
                                    $resp);
  }

  public function testCreateUploadUrl() {
    $req = new \google\appengine\files\GetDefaultGsBucketNameRequest();
    $resp = new \google\appengine\files\GetDefaultGsBucketNameResponse();

    $resp->setDefaultGsBucketName("some_bucket");

    $this->apiProxyMock->expectCall("file",
                                    "GetDefaultGsBucketName",
                                    $req,
                                    $resp);

    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName("some_bucket");

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar');
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidSuccessPath() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl(10);
  }

  public function testSetMaxBytesPerBlob() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setMaxUploadSizePerBlobBytes(37337);
    $req->setGsBucketName("some_bucket");

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['max_bytes_per_blob' => 37337,
         'gs_bucket_name' => 'some_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testSetMaxBytesPerBlobIni() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setMaxUploadSizePerBlobBytes(1 * 1024 * 1024);
    $req->setGsBucketName("some_bucket");

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    self::$mock_upload_max_filesize = '1M';
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'some_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidMaxBytesPerBlob() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['max_bytes_per_blob' => 'not an int',]);
  }

  public function testNegativeMaxBytesPerBlob() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['max_bytes_per_blob' => -1,]);
  }

  public function testSetMaxBytesTotal() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setMaxUploadSizeBytes(137337);
    $req->setMaxUploadSizePerBlobBytes(1 * 1024 * 1024 * 1024);
    $req->setGsBucketName("some_bucket");

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    self::$mock_upload_max_filesize = '1G';
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['max_bytes_total' => 137337,
         'gs_bucket_name' => 'some_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidMaxBytes() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::CreateUploadUrl('http://foo/bar',
        ['max_bytes_total' => 'not an int',]);
  }

  public function testNegativeMaxBytes() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['max_bytes_total' => -1,]);
  }

  public function testGsBucketName() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName('my_cool_bucket');

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'my_cool_bucket',]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testInvalidGsBucketName() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => null,]);
  }

  public function testMultipleOptions() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setMaxUploadSizePerBlobBytes(37337);
    $req->setMaxUploadSizeBytes(137337);
    $req->setGsBucketName('my_cool_bucket');

    $resp = new \google\appengine\CreateUploadURLResponse();
    $resp->setUrl('http://upload/to/here');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $resp);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'my_cool_bucket',
         'max_bytes_total' => 137337,
         'max_bytes_per_blob' => 37337]);
    $this->assertEquals($upload_url, 'http://upload/to/here');
    $this->apiProxyMock->verify();
  }

  public function testUrlTooLongException() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName("some_bucket");

    $exception = new \google\appengine\runtime\ApplicationError(
        BlobstoreServiceError\ErrorCode::URL_TOO_LONG, 'message');

    $this->setExpectedException('\InvalidArgumentException', '');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $exception);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'some_bucket',]);
    $this->apiProxyMock->verify();
  }

  public function testPermissionDeniedException() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName("some_bucket");

    $exception = new \google\appengine\runtime\ApplicationError(
        BlobstoreServiceError\ErrorCode::PERMISSION_DENIED, 'message');

    $this->setExpectedException(
        '\google\appengine\api\cloud_storage\CloudStorageException',
        'Permission Denied');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $exception);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'some_bucket',]);
    $this->apiProxyMock->verify();
  }

  public function testInternalErrorException() {
    $req = new \google\appengine\CreateUploadURLRequest();
    $req->setSuccessPath('http://foo/bar');
    $req->setGsBucketName("some_bucket");

    $exception = new \google\appengine\runtime\ApplicationError(
        BlobstoreServiceError\ErrorCode::INTERNAL_ERROR, 'message');

    $this->setExpectedException(
        '\google\appengine\api\cloud_storage\CloudStorageException', '');

    $this->apiProxyMock->expectCall('blobstore', 'CreateUploadURL', $req,
        $exception);

    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'some_bucket',]);
    $this->apiProxyMock->verify();
  }

  public function testNoDefaultBucketException() {
    $req = new \google\appengine\files\GetDefaultGsBucketNameRequest();
    $resp = new \google\appengine\files\GetDefaultGsBucketNameResponse();

    $this->apiProxyMock->expectCall("file",
                                    "GetDefaultGsBucketName",
                                    $req,
                                    $resp);
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar');
    $this->apiProxyMock->verify();
  }

  public function testInvalidOptions() {
    $this->setExpectedException('\InvalidArgumentException');
    $upload_url = CloudStorageTools::createUploadUrl('http://foo/bar',
        ['gs_bucket_name' => 'bucket',
         'foo' => 'bar']);
  }

  public function testServeInvalidGsPrefix() {
    $this->setExpectedException('\InvalidArgumentException');
    CloudStorageTools::serve("/goo/bar.png");
  }

  public function testServeInvalidBucketObjectName() {
    $this->setExpectedException(
        '\InvalidArgumentException',
        'filename not in the format gs://bucket_name/object_name.');
    CloudStorageTools::serve("gs://some_bucket");
  }

  public function testServeInvalidOptionArray() {
    $this->setExpectedException('\InvalidArgumentException');
    CloudStorageTools::serve("gs://foo/bar.png", ["foo" => true]);
  }

  public function testServeEndBadRanges() {
    $ranges = [[null, 1], [null, -1], [2, 1], [-1, 1]];
    foreach($ranges as $range) {
      try {
        CloudStorageTools::serve("gs://foo/bar.png",
                                ["start" => $range[0], "end" => $range[1]]);
      } catch (\InvalidArgumentException $e) {
        continue;
      }
      $this->fail("InvalidArgumentException was not thrown");
    }
  }

  public function testServeRangeIndexDoNotMatchRangeHeader() {
    $this->setExpectedException("\InvalidArgumentException");
    $_SERVER["HTTP_RANGE"] = "bytes=1-2";
    CloudStorageTools::serve("gs://foo/bar.png", ["start" => 1, "end" => 3,
        "use_range" => true]);
  }

  public function testServeSuccess() {
    $this->expectFilenameTranslation("/gs/some_bucket/some_object",
                                     "some_blob_key");
    $filename = "gs://some_bucket/some_object";
    $expected_headers = [
        "X-AppEngine-BlobKey" => "some_blob_key",
        "X-AppEngine-BlobRange" => "bytes=1-2",
        "Content-Disposition" => "attachment; filename=foo.jpg",
    ];
    $options = [
        "start" => 1,
        "end" => 2,
        "save_as" => "foo.jpg",
    ];
    CloudStorageTools::serve($filename, $options);
    $this->assertEquals(ksort($this->sent_headers), ksort($expected_headers));
    $this->apiProxyMock->verify();
  }

  public function testServeSuccessNegativeRange() {
    $this->expectFilenameTranslation("/gs/some_bucket/some_object",
                                     "some_blob_key");
    $filename = "gs://some_bucket/some_object";
    $expected_headers = [
        "X-AppEngine-BlobKey" => "some_blob_key",
        "X-AppEngine-BlobRange" => "bytes=-1001",
        "Content-Disposition" => "attachment; filename=foo.jpg",
    ];
    $options = [
        "start" => -1001,
        "save_as" => "foo.jpg",
    ];
    CloudStorageTools::serve($filename, $options);
    $this->assertEquals(ksort($this->sent_headers), ksort($expected_headers));
    $this->apiProxyMock->verify();
  }

  public function testServeRangeHeaderSuccess() {
    $this->expectFilenameTranslation("/gs/some_bucket/some_object",
                                     "some_blob_key");
    $filename = "gs://some_bucket/some_object";
    $expected_headers = [
        "X-AppEngine-BlobKey" => "some_blob_key",
        "X-AppEngine-BlobRange" => "bytes=100-200",
        "Content-Disposition" => "attachment; filename=foo.jpg",
        "Content-Type" => "image/jpeg",
    ];
    $options = [
        "save_as" => "foo.jpg",
        "use_range" => true,
        "content_type" => "image/jpeg",
    ];
    $_SERVER["HTTP_RANGE"] = "bytes=100-200";
    CloudStorageTools::serve($filename, $options);
    $this->assertEquals(ksort($this->sent_headers), ksort($expected_headers));
    $this->apiProxyMock->verify();
  }

  public function testGetDefaultBucketNameSuccess() {
    $req = new \google\appengine\files\GetDefaultGsBucketNameRequest();
    $resp = new \google\appengine\files\GetDefaultGsBucketNameResponse();

    $resp->setDefaultGsBucketName("some_bucket");

    $this->apiProxyMock->expectCall("file",
                                    "GetDefaultGsBucketName",
                                    $req,
                                    $resp);

    $bucket = CloudStorageTools::getDefaultGoogleStorageBucketName();
    $this->assertEquals($bucket, "some_bucket");
    $this->apiProxyMock->verify();
  }

  public function testGetDefaultBucketNameNotSet() {
    $req = new \google\appengine\files\GetDefaultGsBucketNameRequest();
    $resp = new \google\appengine\files\GetDefaultGsBucketNameResponse();

    $this->apiProxyMock->expectCall("file",
                                    "GetDefaultGsBucketName",
                                    $req,
                                    $resp);

    $bucket = CloudStorageTools::getDefaultGoogleStorageBucketName();
    $this->assertEquals($bucket, "");
    $this->apiProxyMock->verify();
  }

  // getImageServingUrl tests.

  public function testGetImageUrlInvalidFilenameType() {
    $this->setExpectedException('\InvalidArgumentException');
    $url = CloudStorageTools::getImageServingUrl(123);
  }

  public function testGetImageUrlInvalidFilename() {
    $this->setExpectedException('\InvalidArgumentException');
    $url = CloudStorageTools::getImageServingUrl('not-gs://abucket/photo');
  }

  public function testGetImageUrlCropInvalidType() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException('\InvalidArgumentException');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['crop' => 5]);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlCropRequiresSize() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException('\InvalidArgumentException');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['crop' => true]);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlSizeInvalidType() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException(
        '\InvalidArgumentException',
        '$options[\'size\'] must be an integer. Actual type: string');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['size' => 'abc']);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlSizeTooSmall() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException(
        '\InvalidArgumentException',
        '$options[\'size\'] must be >= 0 and <= 1600. Actual value: -1');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['size' => -1]);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlSizeTooBig() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException(
        '\InvalidArgumentException',
        '$options[\'size\'] must be >= 0 and <= 1600. Actual value: 1601');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['size' => 1601]);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlSecureUrlWrongType() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $this->setExpectedException(
        '\InvalidArgumentException',
        '$options[\'secure_url\'] must be a boolean. Actual type: integer');
    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg',
                                                ['secure_url' => 5]);
    $this->apiProxyMock->verify();
  }

  # getImageServingUrl success case.
  public function testGetImageUrlSimpleSuccess() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesGetUrlBaseRequest();
    $resp = new \google\appengine\ImagesGetUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $req->setCreateSecureUrl(false);
    $resp->setUrl('http://magic-url');
    $this->apiProxyMock->expectCall('images',
                                    'GetUrlBase',
                                    $req,
                                    $resp);

    $url = CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg');
    $this->assertEquals('http://magic-url', $url);
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlWithSizeAndCropSuccess() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesGetUrlBaseRequest();
    $resp = new \google\appengine\ImagesGetUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $req->setCreateSecureUrl(false);
    $resp->setUrl('http://magic-url');
    $this->apiProxyMock->expectCall('images',
                                    'GetUrlBase',
                                    $req,
                                    $resp);

    $url = CloudStorageTools::getImageServingUrl(
        'gs://mybucket/photo.jpg', ['size' => 40, 'crop' => true]);
    $this->assertEquals('http://magic-url=s40-c', $url);
    $this->apiProxyMock->verify();
  }

  # getImageServingUrl backend error tests.
  private function executeGetImageUrlErrorTest($error_code, $expected_message) {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesGetUrlBaseRequest();
    $resp = new \google\appengine\ImagesGetUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $req->setCreateSecureUrl(false);
    $exception = new \google\appengine\runtime\ApplicationError(
        $error_code, 'a message');

    $this->setExpectedException(
        '\google\appengine\api\cloud_storage\CloudStorageException',
        $expected_message);
    $this->apiProxyMock->expectCall('images',
                                    'GetUrlBase',
                                    $req,
                                    $exception);
    CloudStorageTools::getImageServingUrl('gs://mybucket/photo.jpg');
    $this->apiProxyMock->verify();
  }

  public function testGetImageUrlUnspecifiedError() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::UNSPECIFIED_ERROR,
        'Unspecified error with image.');
  }

  public function testGetImageUrlBadTransform() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::BAD_TRANSFORM_DATA,
        'Bad image transform data.');
  }

  public function testGetImageUrlNotImage() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::NOT_IMAGE,
        'Not an image.');
  }

  public function testGetImageUrlBadImage() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::BAD_IMAGE_DATA,
        'Bad image data.');
  }

  public function testGetImageUrlImageTooLarge() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::IMAGE_TOO_LARGE,
        'Image too large.');
  }

  public function testGetImageUrlInvalidBlobKey() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::INVALID_BLOB_KEY,
        'Invalid blob key for image.');
  }

  public function testGetImageUrlAccessDenied() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::ACCESS_DENIED,
        'Access denied to image.');
  }

  public function testGetImageUrlObjectNotFound() {
    $this->executeGetImageUrlErrorTest(
        ImagesServiceError\ErrorCode::OBJECT_NOT_FOUND,
        'Image object not found.');
  }

  public function testGetImageUrlUnknownErrorCode() {
    $this->executeGetImageUrlErrorTest(999, 'Images Error Code: 999');
  }

  // deleteImageServingUrl tests.

  public function testDeleteImageUrlInvalidFilenameType() {
    $this->setExpectedException('\InvalidArgumentException',
        'filename must be a string. Actual type: integer');
    $url = CloudStorageTools::deleteImageServingUrl(2468);
  }

  public function testDeleteImageUrlSuccess() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesDeleteUrlBaseRequest();
    $resp = new \google\appengine\ImagesDeleteUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $this->apiProxyMock->expectCall('images',
                                    'DeleteUrlBase',
                                    $req,
                                    $resp);

    CloudStorageTools::deleteImageServingUrl('gs://mybucket/photo.jpg');
    $this->apiProxyMock->verify();
  }

  public function testDeleteImageUrlAccessDenied() {
    $this->expectFilenameTranslation('/gs/mybucket/photo.jpg', 'some_blob_key');
    $req = new \google\appengine\ImagesDeleteUrlBaseRequest();
    $resp = new \google\appengine\ImagesDeleteUrlBaseResponse();
    $req->setBlobKey('some_blob_key');
    $exception = new \google\appengine\runtime\ApplicationError(
        ImagesServiceError\ErrorCode::ACCESS_DENIED, 'a message');

    $this->setExpectedException(
        '\google\appengine\api\cloud_storage\CloudStorageException',
        'Access denied to image.');
    $this->apiProxyMock->expectCall('images',
                                    'DeleteUrlBase',
                                    $req,
                                    $exception);
    CloudStorageTools::deleteImageServingUrl('gs://mybucket/photo.jpg');
    $this->apiProxyMock->verify();
  }

  public function testGetPublicUrlInProduction() {
    putenv("SERVER_SOFTWARE=Google App Engine/1.8.6");

    // Get HTTPS URL for bucket containing "." - should use the path format to
    // avoid SSL certificate validation issue.
    $expected = "https://storage.googleapis.com/bucket.name";
    $actual = CloudStorageTools::getPublicUrl("gs://bucket.name", true);
    $this->assertEquals($expected, $actual);
    $expected = "https://storage.googleapis.com/bucket.name/object";
    $actual = CloudStorageTools::getPublicUrl("gs://bucket.name/object", true);
    $this->assertEquals($expected, $actual);

    // Get HTTP URL for bucket contain "." - should use the subdomain format.
    $expected = "http://bucket.name.storage.googleapis.com/";
    $actual = CloudStorageTools::getPublicUrl("gs://bucket.name/", false);
    $this->assertEquals($expected, $actual);
    $expected = "http://bucket.name.storage.googleapis.com/object";
    $actual = CloudStorageTools::getPublicUrl("gs://bucket.name/object", false);
    $this->assertEquals($expected, $actual);

    // Get HTTPS URL for bucket without "." - should use the subdomain format.
    $expected = "https://bucket.storage.googleapis.com/";
    $actual = CloudStorageTools::getPublicUrl("gs://bucket", true);
    $this->assertEquals($expected, $actual);
    $expected = "https://bucket.storage.googleapis.com/object";
    $actual = CloudStorageTools::getPublicUrl("gs://bucket/object", true);
    $this->assertEquals($expected, $actual);

    // Get HTTP URL for bucket without "." - should use the subdomain format.
    $expected = "http://bucket.storage.googleapis.com/";
    $actual = CloudStorageTools::getPublicUrl("gs://bucket", false);
    $this->assertEquals($expected, $actual);
    $expected = "http://bucket.storage.googleapis.com/object";
    $actual = CloudStorageTools::getPublicUrl("gs://bucket/object", false);
    $this->assertEquals($expected, $actual);
  }

  public function testGetPublicUrlInDevelopment() {
    $bucket = "bucket";
    $object = "object";
    $gs_filename = sprintf("gs://%s/%s", $bucket, $object);
    putenv("SERVER_SOFTWARE=Development/2.0");
    putenv("HTTP_HOST=localhost:8080");

    // Get HTTPS URL
    $expected = "http://localhost:8080/_ah/gcs/bucket/object";
    $actual = CloudStorageTools::getPublicUrl($gs_filename, true);
    $this->assertEquals($expected, $actual);

    // Get HTTP URL
    $expected = "http://localhost:8080/_ah/gcs/bucket/object";
    $actual = CloudStorageTools::getPublicUrl($gs_filename, false);
    $this->assertEquals($expected, $actual);
  }

  public function testGetPublicUrlEncoding() {
    $bucket = "bucket";
    $object = " %#?";
    $gs_filename = sprintf("gs://%s/%s", $bucket, $object);

    $expected = "https://bucket.storage.googleapis.com/%20%25%23%3F";
    $actual = CloudStorageTools::getPublicUrl($gs_filename, true);
    $this->assertEquals($expected, $actual);
  }

  public function testGetFilenameFromValidBucketAndObject() {
    $bucket = "bucket";
    $object = "object";
    $expected = "gs://bucket/object";
    $actual = CloudStorageTools::getFilename($bucket, $object);
    $this->assertEquals($expected, $actual);
  }

  /**
   * DataProvider for
   * - testGetFilenameFromValidBucketNames
   */
  public function validBucketNames() {
    return [
        ['fancy-bucket_name1'],  // Must contain only [a-z0-9\-_].
        ['1_bucket'],  // Must start with a number or letter.
        ['bucket.1'],  // Must end with a number or letter.
        ['foo'],  // Must be longer than 3 characters.
        ['a.b'],  // Must be longer than 3 characters even with dots in name.
        [str_repeat('a', 63)],  // Must not be longer than 63 characters.
        // Must not exceed 222 characters with dots in name.
        [implode('.', [str_repeat('a', 63), str_repeat('b', 63),
                       str_repeat('c', 63), str_repeat('d', 30)])],
        // Each component must not be exceed 63 characters.
        ['a.' . str_repeat('b', 63)],
        ['256.1.1.1'], // Must not be an IP address.
        ['foo.goog'],  // Must not begin with "goog".
    ];
  }

  /**
   * DataProvider for
   * - testGetFilenameFromInvalidBucketNames
   */
  public function invalidBucketNames() {
    return [
        ['BadBucketName'],  // Must contain only [a-z0-9\-_].
        ['.another_bad_bucket'],  // Must start with a number or letter.
        ['another_bad_bucket_'],  // Must end with a number or letter.
        ['a'],  // Must be longer than 3 characters.
        ['a.'],  // Must be longer than 3 characters even with dots in name.
        [str_repeat('a', 64)],  // Must not be longer than 63 characters.
        // Must not exceed 222 characters with dots in name.
        [implode('.', [str_repeat('a', 63), str_repeat('b', 63),
                       str_repeat('c', 63), str_repeat('d', 31)])],
        // Each component must not be exceed 63 characters.
        ['a.' . str_repeat('b', 64)],
        ['192.168.1.1'], // Must not be an IP address.
        ['goog_bucket'],  // Must not begin with "goog".
    ];
  }

  /**
   * DataProvider for
   * - testGetFilenameFromInvalidObjectNames
   */
  public function invalidObjectNames() {
    return [
        ["WithCarriageReturn\r"],
        ["WithLineFeed\n"],
        ["WithFormFeed\f"],
        ["WithverticalTab\v"],
    ];
  }

  /**
   * @dataProvider validBucketNames
   */
  public function testGetFilenameFromValidBucketNames($bucket) {
    CloudStorageTools::getFilename($bucket, 'foo.txt');
  }

  /**
   * @dataProvider invalidBucketNames
   */
  public function testGetFilenameFromInvalidBucketNames($bucket) {
    $this->setExpectedException(
        "\InvalidArgumentException",
        sprintf("Invalid cloud storage bucket name '%s'", $bucket));
     CloudStorageTools::getFilename($bucket, 'foo.txt');
  }

  /**
   * @dataProvider invalidObjectNames
   */
  public function testGetFilenameFromInvalidObjecNames($object) {
    $this->setExpectedException(
        "\InvalidArgumentException",
        sprintf("Invalid cloud storage object name '%s'", $object));
    CloudStorageTools::getFilename('foo', $object);
  }

  public function testParseFilenameWithBucketAndObject() {
    $gs_filename = 'gs://bucket/object';

    $this->assertEquals(true,
        CloudStorageTools::parseFilename($gs_filename, $bucket, $object));
    $this->assertEquals('bucket', $bucket);
    $this->assertEquals('/object', $object);
  }

  public function testParseFilenameWithBucketOnly() {
    $gs_filename = 'gs://bucket';

    $this->assertEquals(true,
        CloudStorageTools::parseFilename($gs_filename, $bucket, $object));
    $this->assertEquals('bucket', $bucket);
    $this->assertEquals(null, $object);
  }
}

