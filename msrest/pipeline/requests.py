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
"""
This module is the requests implementation of Pipeline ABC
"""
import logging
from typing import Any, Dict, Union, IO, Tuple, Optional, cast, TYPE_CHECKING
import warnings

if TYPE_CHECKING:
    from ..configuration import Configuration

from oauthlib import oauth2
import requests
from urllib3 import Retry  # Needs requests 2.16 at least to be safe

from ..exceptions import (
    TokenExpiredError,
    ClientRequestError,
    raise_with_traceback)
from . import HTTPSender, HTTPPolicy, ClientRequest, ClientResponse


_LOGGER = logging.getLogger(__name__)


class RequestsCredentialsPolicy(HTTPPolicy):
    """Implementation of request-oauthlib except and retry logic.
    """
    def __init__(self, credentials):
        self._creds = credentials

    def send(self, request, **kwargs):
        session = request.pipeline_context.session
        try:
            self._creds.signed_session(session)
        except TypeError: # Credentials does not support session injection
            _LOGGER.warning("Your credentials class does not support session injection. Performance will not be at the maximum.")
            request.pipeline_context.session = session = self.creds.signed_session()

        try:
            try:
                return self.next.send(request, **kwargs)
            except (oauth2.rfc6749.errors.InvalidGrantError,
                    oauth2.rfc6749.errors.TokenExpiredError) as err:
                error = "Token expired or is invalid. Attempting to refresh."
                _LOGGER.warning(error)

            try:
                try:
                    self._creds.refresh_session(session)
                except TypeError: # Credentials does not support session injection
                    _LOGGER.warning("Your credentials class does not support session injection. Performance will not be at the maximum.")
                    request.pipeline_context.session = session = self.creds.refresh_session()

                return self.next.send(request, **kwargs)
            except (oauth2.rfc6749.errors.InvalidGrantError,
                    oauth2.rfc6749.errors.TokenExpiredError) as err:
                msg = "Token expired or is invalid."
                raise_with_traceback(TokenExpiredError, msg, err)

        except (requests.RequestException,
                oauth2.rfc6749.errors.OAuth2Error) as err:
            msg = "Error occurred in request."
            raise_with_traceback(ClientRequestError, msg, err)

class RequestsPatchSession(HTTPPolicy):
    """Implements request level configuration
    that are actually to be done at the session level.

    This is highly deprecated, and is totally legacy.
    The pipeline structure allows way better design for this.
    """
    _protocols = ['http://', 'https://']

    def send(self, request, **kwargs):
        """Patch the current session with Request level operation config.

        This is deprecated, we shouldn't patch the session with
        arguments at the Request, and "config" should be used.
        """
        session = request.pipeline_context.session

        old_max_redirects = None
        if 'max_redirects' in kwargs:
            warnings.warn("max_redirects in operation kwargs is deprecated, use config.redirect_policy instead",
                          DeprecationWarning)
            old_max_redirects = session.max_redirects
            session.max_redirects = int(kwargs['max_redirects'])

        old_trust_env = None
        if 'use_env_proxies' in kwargs:
            warnings.warn("use_env_proxies in operation kwargs is deprecated, use config.proxies instead",
                          DeprecationWarning)
            old_trust_env = session.trust_env
            session.trust_env = bool(kwargs['use_env_proxies'])

        old_retries = {}
        if 'retries' in kwargs:
            warnings.warn("retries in operation kwargs is deprecated, use config.retry_policy instead",
                          DeprecationWarning)
            max_retries = kwargs['retries']
            for protocol in self._protocols:
                old_retries[protocol] = session.adapters[protocol].max_retries
                session.adapters[protocol].max_retries = max_retries

        try:
            return self.next.send(request, **kwargs)
        finally:
            if old_max_redirects:
                session.max_redirects = old_max_redirects

            if old_trust_env:
                session.trust_env = old_trust_env

            if old_retries:
                for protocol in self._protocols:
                    session.adapters[protocol].max_retries = old_retries[protocol]

class RequestsContext(object):
    def __init__(self, session, kwargs):
        self.session = session
        self.kwargs = kwargs

class RequestsClientResponse(ClientResponse):
    def __init__(self, request, requests_response):
        super(RequestsClientResponse, self).__init__(request)
        self.requests_response = requests_response
        self.status_code = requests_response.status_code
        self.content = requests_response.content
        self.headers = requests_response.headers
        # Optional, should be removed and use delegation to the real response
        # Keep it for rapid tests for now
        self.history = requests_response.history
        self.is_redirect = requests_response.is_redirect
        self.request = requests_response.request

    def json(self):
        # Optional, should be removed and use delegation to the real response
        # Keep it for rapid tests for now
        return self.requests_response.json()

    @property
    def text(self):
        # Optional, should be removed and use delegation to the real response
        # Keep it for rapid tests for now
        return self.requests_response.text

class RequestsHTTPSender(HTTPSender):

    _protocols = ['http://', 'https://']

    # Set of authorized kwargs at the operation level
    _REQUESTS_KWARGS = [
        'cookies',
        'verify',
        'timeout',
        'allow_redirects',
        'proxies',
        'verify',
        'cert'
    ]

    def __init__(self, config):
        # type: (Configuration) -> None
        self.config = config
        self.session = requests.Session()
        self._init_session()

    def __enter__(self):
        # type: () -> RequestsHTTPSender
        return self

    def __exit__(self, *exc_details):
        self.close()

    def close(self):
        self.session.close()

    def build_context(self):
        # type: () -> RequestsContext
        return RequestsContext(
            session=self.session,
            kwargs={}
        )

    def _init_session(self):
        # type: () -> None
        """Init session level configuration of requests.
        """
        self.session.max_redirects = int(self.config.redirect_policy())
        self.session.trust_env = bool(self.config.proxies.use_env_settings)

        # Patch the redirect method directly
        redirect_logic = self.session.resolve_redirects

        def wrapped_redirect(resp, req, **kwargs):
            attempt = self.config.redirect_policy.check_redirect(resp, req)
            return redirect_logic(resp, req, **kwargs) if attempt else []
        wrapped_redirect.is_mrest_patched = True  # type: ignore

        self.session.resolve_redirects = wrapped_redirect  # type: ignore

        # Change max_retries in current all installed adapters
        max_retries = self.config.retry_policy()
        for protocol in self._protocols:
            self.session.adapters[protocol].max_retries=max_retries

    def _configure_send(self, request, **kwargs):
        # type: (ClientRequest, Any) -> Dict[str, str]
        """Configure the kwargs to use with requests.

        :param ClientRequest request: The request object to be sent.
        :returns: The requests.Session.request kwargs
        :rtype: dict[str,str]
        """
        if request.pipeline_context is None:  # Should not happen, but make mypy happy and does not hurt
            request.pipeline_context = self.build_context()

        session = request.pipeline_context.session

        # Initialize requests_kwargs with "config" value
        requests_kwargs = {}  # type: Any
        requests_kwargs.update(self.config.connection())
        requests_kwargs['allow_redirects'] = bool(self.config.redirect_policy)
        requests_kwargs['headers'] = self.config.headers.copy()

        proxies = self.config.proxies()
        if proxies:
            requests_kwargs['proxies'] = proxies

        # Replace by pipeline kwargs
        requests_kwargs.update(request.pipeline_context.kwargs.copy())

        # Replace by operation level kwargs
        # We allow some of them, since some like stream or json are controled by msrest
        for key in kwargs:
            if key in self._REQUESTS_KWARGS:
                requests_kwargs[key] = kwargs[key]

        # Hooks. Deprecated, should be a policy
        def make_user_hook_cb(user_hook, session):
            def user_hook_cb(r, *args, **kwargs):
                kwargs.setdefault("msrest", {})['session'] = session
                return user_hook(r, *args, **kwargs)
            return user_hook_cb

        hooks = []
        for user_hook in self.config.hooks:
            hooks.append(make_user_hook_cb(user_hook, self.session))

        if hooks:
            kwargs['hooks'] = {'response': hooks}

        # Configuration callback. Deprecated, should be a policy
        output_kwargs = self.config.session_configuration_callback(
            session,
            self.config,
            kwargs,
            **requests_kwargs
        )
        if output_kwargs is not None:
            requests_kwargs = output_kwargs

        ### Autorest forced kwargs now ###

        # If Autorest needs this response to be streamable. True for compat.
        requests_kwargs['stream'] = kwargs.get('stream', True)

        if request.files:
            requests_kwargs['files'] = request.files
        elif request.data:
            requests_kwargs['data'] = request.data
        requests_kwargs['headers'].update(request.headers)

        # Tag the request as sent by "requests", to help debugging depending of the driver used.
        current_user_agent = requests_kwargs['headers'].setdefault('User-Agent', "")
        requests_kwargs['headers']['User-Agent'] = " ".join([current_user_agent, "requests/{}".format(requests.__version__)])
        return requests_kwargs

    def send(self, request, **kwargs):
        # type: (ClientRequest, Any) -> RequestsClientResponse
        """Send request object according to configuration.

        :param ClientRequest request: The request object to be sent.
        """
        session = request.pipeline_context.session
        requests_kwargs = self._configure_send(request, **kwargs)
        response = session.request(
            request.method,
            request.url,
            **requests_kwargs)
        return RequestsClientResponse(request, response)


class ClientRetryPolicy(object):
    """Retry configuration settings.
    Container for retry policy object.
    """

    safe_codes = [i for i in range(500) if i != 408] + [501, 505]

    def __init__(self):
        self.policy = Retry()
        self.policy.total = 3
        self.policy.connect = 3
        self.policy.read = 3
        self.policy.backoff_factor = 0.8
        self.policy.BACKOFF_MAX = 90

        retry_codes = [i for i in range(999) if i not in self.safe_codes]
        self.policy.status_forcelist = retry_codes
        self.policy.method_whitelist = ['HEAD', 'TRACE', 'GET', 'PUT',
                                        'OPTIONS', 'DELETE', 'POST', 'PATCH']

    def __call__(self):
        # type: () -> Retry
        """Return configuration to be applied to connection."""
        debug = ("Configuring retry: max_retries=%r, "
                 "backoff_factor=%r, max_backoff=%r")
        _LOGGER.debug(
            debug, self.retries, self.backoff_factor, self.max_backoff)
        return self.policy

    @property
    def retries(self):
        # type: () -> int
        """Total number of allowed retries."""
        return self.policy.total

    @retries.setter
    def retries(self, value):
        # type: (int) -> None
        self.policy.total = value
        self.policy.connect = value
        self.policy.read = value

    @property
    def backoff_factor(self):
        # type: () -> Union[int, float]
        """Factor by which back-off delay is incementally increased."""
        return self.policy.backoff_factor

    @backoff_factor.setter
    def backoff_factor(self, value):
        # type: (Union[int, float]) -> None
        self.policy.backoff_factor = value

    @property
    def max_backoff(self):
        # type: () -> int
        """Max retry back-off delay."""
        return self.policy.BACKOFF_MAX

    @max_backoff.setter
    def max_backoff(self, value):
        # type: (int) -> None
        self.policy.BACKOFF_MAX = value


class ClientRedirectPolicy(object):
    """Redirect configuration settings.
    """

    def __init__(self):
        self.allow = True
        self.max_redirects = 30

    def __bool__(self):
        # type: () -> bool
        """Whether redirects are allowed."""
        return self.allow

    def __call__(self):
        # type: () -> int
        """Return configuration to be applied to connection."""
        debug = "Configuring redirects: allow=%r, max=%r"
        _LOGGER.debug(debug, self.allow, self.max_redirects)
        return self.max_redirects

    def check_redirect(self, resp, request):
        # type: (requests.Response, requests.PreparedRequest) -> bool
        """Whether redirect policy should be applied based on status code."""
        if resp.status_code in (301, 302) and \
                request.method not in ['GET', 'HEAD']:
            return False
        return True


class ClientProxies(object):
    """Proxy configuration settings.
    Proxies can also be configured using HTTP_PROXY and HTTPS_PROXY
    environment variables, in which case set use_env_settings to True.
    """

    def __init__(self):
        self.proxies = {}
        self.use_env_settings = True

    def __call__(self):
        # type: () -> Dict[str, str]
        """Return configuration to be applied to connection."""
        proxy_string = "\n".join(
            ["    {}: {}".format(k, v) for k, v in self.proxies.items()])

        _LOGGER.debug("Configuring proxies: %r", proxy_string)
        debug = "Evaluate proxies against ENV settings: %r"
        _LOGGER.debug(debug, self.use_env_settings)
        return self.proxies

    def add(self, protocol, proxy_url):
        # type: (str, str) -> None
        """Add proxy.

        :param str protocol: Protocol for which proxy is to be applied. Can
         be 'http', 'https', etc. Can also include host.
        :param str proxy_url: The proxy URL. Where basic auth is required,
         use the format: http://user:password@host
        """
        self.proxies[protocol] = proxy_url


class ClientConnection(object):
    """Request connection configuration settings.
    """

    def __init__(self):
        self.timeout = 100
        self.verify = True
        self.cert = None
        self.data_block_size = 4096

    def __call__(self):
        # type: () -> Dict[str, Union[str, int]]
        """Return configuration to be applied to connection."""
        debug = "Configuring request: timeout=%r, verify=%r, cert=%r"
        _LOGGER.debug(debug, self.timeout, self.verify, self.cert)
        return {'timeout': self.timeout,
                'verify': self.verify,
                'cert': self.cert}
