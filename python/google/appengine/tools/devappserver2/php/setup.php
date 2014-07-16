<?php

// Ensure that the class autoloader is the first include.
require_once 'google/appengine/runtime/autoloader.php';

function _gae_syslog($priority, $format_string, $message) {
  // TODO(bquinlan): Use the logs service to persist this message.
}

$unsetEnv = function($var_name) {
  putenv($var_name);
  unset($_ENV[$var_name]);
  unset($_SERVER[$var_name]);
};

$setup = function() {
  $setupGaeExtension = function() {
    $allowed_buckets = '';
    $ini_file = getenv('APPLICATION_ROOT') . DIRECTORY_SEPARATOR . 'php.ini';
    $config_values = @parse_ini_file($ini_file);
    if ($config_values &&
        array_key_exists('google_app_engine.allow_include_gs_buckets',
                         $config_values)) {
      $allowed_buckets =
          $config_values['google_app_engine.allow_include_gs_buckets'];
    }
    define('GAE_INCLUDE_REQUIRE_GS_STREAMS',
           // All values are considered true except the empty string.
           $allowed_buckets ? 1 : 0);
    define('GAE_INCLUDE_GS_BUCKETS', $allowed_buckets);
  };

  $configureDefaults = function() {
    if (!ini_get('date.timezone')) {
      date_default_timezone_set('UTC');
    }
  };

  $updateScriptFilename = function() {
    $unixPath = function($path) {
      return str_replace(DIRECTORY_SEPARATOR, "/", $path);
    };

    global $unsetEnv;
    $_SERVER['DOCUMENT_ROOT'] = $unixPath($_SERVER['APPLICATION_ROOT']);
    $unsetEnv('APPLICATION_ROOT');

    putenv('SCRIPT_FILENAME=' . getenv('REAL_SCRIPT_FILENAME'));
    $_ENV['SCRIPT_FILENAME'] = getenv('REAL_SCRIPT_FILENAME');

    $relativePath = dirname(getenv('REAL_SCRIPT_FILENAME'));
    // $actualPath = full path to file, discovered using
    // stream_resolve_include_path checking include paths against
    // $relativePath to see if directory exists.
    $actualPath = stream_resolve_include_path($relativePath);
    chdir($actualPath);

    $_SERVER['SCRIPT_FILENAME'] = $unixPath(getenv('REAL_SCRIPT_FILENAME'));
    $unsetEnv('REAL_SCRIPT_FILENAME');

    // Replicate the SCRIPT_NAME and PHP_SELF setup used in production.
    // Set SCRIPT_NAME to SCRIPT_FILENAME made relative to DOCUMENT_ROOT and
    // PHP_SELF to SCRIPT_NAME except when the script is included in PATH_INFO (
    // REQUEST_URI without the query string) which matches Apache behavior.
    $_SERVER['SCRIPT_NAME'] = substr(
      $_SERVER['SCRIPT_FILENAME'], strlen($_SERVER['DOCUMENT_ROOT']));
    if (strpos($_SERVER['PATH_INFO'], $_SERVER['SCRIPT_NAME']) === 0) {
      $_SERVER['PHP_SELF'] = $_SERVER['PATH_INFO'];
    } else {
      $_SERVER['PHP_SELF'] = $_SERVER['SCRIPT_NAME'];
    }
  };

  $setupApiProxy = function() {
    global $unsetEnv;
    require_once 'google/appengine/runtime/ApiProxy.php';
    require_once 'google/appengine/runtime/RemoteApiProxy.php';
    \google\appengine\runtime\ApiProxy::setApiProxy(
      new \google\appengine\runtime\RemoteApiProxy(
        getenv('REMOTE_API_HOST'), getenv('REMOTE_API_PORT'),
        getenv('REMOTE_REQUEST_ID')));
    $unsetEnv('REMOTE_API_HOST');
    $unsetEnv('REMOTE_API_PORT');
    $unsetEnv('REMOTE_REQUEST_ID');
  };

  $setupBuiltins = function() {
    require_once 'google/appengine/runtime/Setup.php';
  };
  $setupGaeExtension();
  $configureDefaults();
  $updateScriptFilename();
  $setupApiProxy();
  $setupBuiltins();
};
$setup();
unset($setup);

if (isset($_ENV['HTTP_X_APPENGINE_DEV_REQUEST_TYPE']) &&
    $_ENV['HTTP_X_APPENGINE_DEV_REQUEST_TYPE'] == 'interactive') {
  $unsetEnv('HTTP_X_APPENGINE_DEV_REQUEST_TYPE');
  unset($unsetEnv);
  eval(file_get_contents("php://input"));
} else {
  unset($unsetEnv);
  require($_ENV['SCRIPT_FILENAME']);
}
