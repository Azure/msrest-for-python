.. _optionsforoperations:

Operation config
================

Methods on operations have extra parameters which can be provided in the kwargs. This is called `operation_config`.

The options for operation configuration are:

=============== ==== ====
Parameter name  Type Role
=============== ==== ====
verify          bool Whether to verify the SSL certificate. Default is True.
cert            str  Path to local certificate for client side verification.
timeout         int  Timeout for establishing a server connection in seconds.
allow_redirects bool Whether to allow redirects.
max_redirects   int  Maimum number of allowed redirects.
proxies         dict Proxy server settings.
use_env_proxies bool Whether to read proxy settings from local environment variables.
retries         int  Total number of retry attempts.
=============== ==== ====
