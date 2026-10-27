<?php
// Router for PHP's development HTTP server; do not use as a production server.
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if ($path !== '/' && is_file('/app/public'.$path)) {
    return false;
}
require '/app/public/index.php';
