# --------------------------------------------------------------------------
#
# Copyright (c) Microsoft Corporation. All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the ""Software""), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
# --------------------------------------------------------------------------

import asyncio
from collections.abc import AsyncIterator
import functools
import logging

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .configuration import Configuration
    from .pipeline import ClientRequest

from oauthlib import oauth2
import requests

from .exceptions import (
    TokenExpiredError,
    ClientRequestError,
    raise_with_traceback,
)

_LOGGER = logging.getLogger(__name__)

## Refactor this driver to be subclass of _RequestsHTTPDriver ##

from .http_logger import log_request, log_response

class _AsyncRequestsHTTPDriver(object):

    _protocols = ['http://', 'https://']

    def __init__(self, config : 'Configuration') -> None:
        self.config = config
        self.session = requests.Session()

    async def __aenter__(self) -> '_AsyncRequestsHTTPDriver':
        return self

    async def __aexit__(self, *exc_details):
        self.close()

    def close(self):
        self.session.close()

    def configure_session(self, **config) -> Dict[str, Any]:
        """Apply configuration to session.

        :param config: Specific configuration overrides.
        :rtype: dict
        :return: A dict that will be kwarg-send to session.request
        """
        kwargs = self.config.connection()  # type: Dict[str, Any]
        for opt in ['timeout', 'verify', 'cert']:
            kwargs[opt] = config.get(opt, kwargs[opt])
        kwargs.update({k:config[k] for k in ['cookies'] if k in config})
        kwargs['allow_redirects'] = config.get(
            'allow_redirects', bool(self.config.redirect_policy))

        kwargs['headers'] = self.config.headers.copy()
        kwargs['headers']['User-Agent'] = self.config.user_agent
        proxies = config.get('proxies', self.config.proxies())
        if proxies:
            kwargs['proxies'] = proxies

        kwargs['stream'] = config.get('stream', True)

        self.session.max_redirects = int(config.get('max_redirects', self.config.redirect_policy()))
        self.session.trust_env = bool(config.get('use_env_proxies', self.config.proxies.use_env_settings))

        # Patch the redirect method directly *if not done already*
        if not getattr(self.session.resolve_redirects, 'is_mrest_patched', False):
            redirect_logic = self.session.resolve_redirects

            def wrapped_redirect(resp, req, **kwargs):
                attempt = self.config.redirect_policy.check_redirect(resp, req)
                return redirect_logic(resp, req, **kwargs) if attempt else []
            wrapped_redirect.is_mrest_patched = True  # type: ignore

            self.session.resolve_redirects = wrapped_redirect  # type: ignore

        # if "enable_http_logger" is defined at the operation level, take the value.
        # if not, take the one in the client config
        # if not, disable http_logger
        hooks = []
        if config.get("enable_http_logger", self.config.enable_http_logger):
            def log_hook(r, *args, **kwargs):
                log_request(None, r.request)
                log_response(None, r.request, r, result=r)
            hooks.append(log_hook)

        def make_user_hook_cb(user_hook, session):
            def user_hook_cb(r, *args, **kwargs):
                kwargs.setdefault("msrest", {})['session'] = session
                return user_hook(r, *args, **kwargs)
            return user_hook_cb

        for user_hook in self.config.hooks:
            hooks.append(make_user_hook_cb(user_hook, self.session))

        if hooks:
            kwargs['hooks'] = {'response': hooks}

        # Change max_retries in current all installed adapters
        max_retries = config.get('retries', self.config.retry_policy())
        for protocol in self._protocols:
            self.session.adapters[protocol].max_retries=max_retries

        output_kwargs = self.config.session_configuration_callback(
            self.session,
            self.config,
            config,
            **kwargs
        )
        if output_kwargs is not None:
            kwargs = output_kwargs

        return kwargs

    async def send(self, request : 'ClientRequest', **config) -> requests.Response:
        """Send request object according to configuration.

        :param ClientRequest request: The request object to be sent.
        :param config: Any specific config overrides
        """
        kwargs = config.copy()
        if request.files:
            kwargs['files'] = request.files
        elif request.data:
            kwargs['data'] = request.data
        kwargs.setdefault("headers", {}).update(request.headers)

        loop = config.get("loop", asyncio.get_event_loop())
        future = loop.run_in_executor(
            None,
            functools.partial(
                self.session.request,
                request.method,
                request.url,
                **kwargs
            )
        )
        return await future


class AsyncServiceClientMixin:

    def __init__(self, creds : Any, config : 'Configuration') -> None:
        # Don't do super, since I know it will be "object"
        # super(AsyncServiceClientMixin, self).__init__(creds, config)
        self._async_http_driver = _AsyncRequestsHTTPDriver(config)

    async def __aenter__(self):
        await self._async_http_driver.__aenter__()
        return self

    async def __aexit__(self, *exc_details):
        await self._async_http_driver.__aexit__(*exc_details)

    async def async_send(self, request, **config):
        """Prepare and send request object according to configuration.

        :param ClientRequest request: The request object to be sent.
        :param dict headers: Any headers to add to the request.
        :param content: Any body data to add to the request.
        :param config: Any specific config overrides
        """
        http_driver = self._async_http_driver

        try:
            self.creds.signed_session(http_driver.session)
        except TypeError: # Credentials does not support session injection
            _LOGGER.critical("Your credentials class does not support session injection. Required for async.")
            raise

        kwargs = http_driver.configure_session(**config)

        try:

            try:
                return await http_driver.send(request, **kwargs)
            except (oauth2.rfc6749.errors.InvalidGrantError,
                    oauth2.rfc6749.errors.TokenExpiredError) as err:
                error = "Token expired or is invalid. Attempting to refresh."
                _LOGGER.warning(error)

            try:
                self.creds.refresh_session(http_driver.session)
                return await http_driver.send(request, **kwargs)
            except (oauth2.rfc6749.errors.InvalidGrantError,
                    oauth2.rfc6749.errors.TokenExpiredError) as err:
                msg = "Token expired or is invalid."
                raise_with_traceback(TokenExpiredError, msg, err)

        except (requests.RequestException,
                oauth2.rfc6749.errors.OAuth2Error) as err:
            msg = "Error occurred in request."
            raise_with_traceback(ClientRequestError, msg, err)

    def stream_download_async(self, response, user_callback):
        """Async Generator for streaming request body data.

        :param response: The initial response
        :param user_callback: Custom callback for monitoring progress.
        """
        block = self.config.connection.data_block_size
        return StreamDownloadGenerator(response, user_callback, block)

class _MsrestStopIteration(Exception):
    pass

def _msrest_next(iterator):
    """"To avoid:
    TypeError: StopIteration interacts badly with generators and cannot be raised into a Future
    """
    try:
        return next(iterator)
    except StopIteration:
        raise _MsrestStopIteration()

class StreamDownloadGenerator(AsyncIterator):

    def __init__(self, response, user_callback, block):
        self.response = response
        self.block = block
        self.user_callback = user_callback
        self.iter_content_func = self.response.iter_content(self.block)

    async def __anext__(self):
        loop = asyncio.get_event_loop()
        try:
            chunk = await loop.run_in_executor(
                None,
                _msrest_next,
                self.iter_content_func,
            )
            if not chunk:
                raise _MsrestStopIteration()
            if self.user_callback and callable(self.user_callback):
                self.user_callback(chunk, self.response)
            return chunk
        except _MsrestStopIteration:
            self.response.close()
            raise StopAsyncIteration()
        except Exception as err:
            _LOGGER.warning("Unable to stream download: %s", err)
            self.response.close()
            raise