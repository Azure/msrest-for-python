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

import contextlib
import logging
import os
try:
    from urlparse import urljoin, urlparse
except ImportError:
    from urllib.parse import urljoin, urlparse

from oauthlib import oauth2
import requests.adapters

from .authentication import Authentication
from .pipeline import ClientRequest
from .http_logger import log_request, log_response
from .exceptions import (
    TokenExpiredError,
    ClientRequestError,
    raise_with_traceback)


_LOGGER = logging.getLogger(__name__)

class SDKClient(object):
    """The base class of all generated SDK client.
    """
    def __init__(self, creds, config):
        self._client = ServiceClient(creds, config)
    
    def close(self):
        """Close the client if keep_alive is True.
        """
        self._client.close()

    def __enter__(self):
        self._client.__enter__()
        return self

    def __exit__(self, *exc_details):
        self._client.__exit__(*exc_details)

class ServiceClient(object):
    """REST Service Client.
    Maintains client pipeline and handles all requests and responses.

    :param Configuration config: Service configuration.
    :param Authentication creds: Authenticated credentials.
    """

    _protocols = ['http://', 'https://']

    def __init__(self, creds, config):
        self.config = config
        self.creds = creds if creds else Authentication()
        self._headers = {}
        self._session = None

    def __enter__(self):
        self.config.keep_alive = True
        return self

    def __exit__(self, *exc_details):
        self.close()
        self.config.keep_alive = False

    def close(self):
        """Close the session if keep_alive is True.
        """
        if self._session:
            self._session.close()
        self._session = None

    def _format_data(self, data):
        """Format field data according to whether it is a stream or
        a string for a form-data request.

        :param data: The request field data.
        :type data: str or file-like object.
        """
        content = [None, data]
        if hasattr(data, 'read'):
            content.append("application/octet-stream")
            try:
                if data.name[0] != '<' and data.name[-1] != '>':
                    content[0] = os.path.basename(data.name)
            except (AttributeError, TypeError):
                pass
        return tuple(content)

    def _request(self, url, params):
        """Create ClientRequest object.

        :param str url: URL for the request.
        :param dict params: URL query parameters.
        """
        request = ClientRequest()

        if url:
            request.url = self.format_url(url)

        if params:
            request.format_parameters(params)

        return request

    def _configure_session(self, session, **config):
        """Apply configuration to session.

        :param requests.Session session: Current request session.
        :param config: Specific configuration overrides.
        :rtype: dict
        :return: A dict that will be kwarg-send to session.request
        """
        kwargs = self.config.connection()
        for opt in ['timeout', 'verify', 'cert']:
            kwargs[opt] = config.get(opt, kwargs[opt])
        kwargs.update({k:config[k] for k in ['cookies', 'files'] if k in config})
        kwargs['allow_redirects'] = config.get(
            'allow_redirects', bool(self.config.redirect_policy))

        kwargs['headers'] = dict(self._headers)
        kwargs['headers']['User-Agent'] = self.config.user_agent
        kwargs['headers']['Accept'] = 'application/json'
        proxies = config.get('proxies', self.config.proxies())
        if proxies:
            kwargs['proxies'] = proxies

        kwargs['stream'] = config.get('stream', True)

        session.max_redirects = config.get('max_redirects', self.config.redirect_policy())
        session.trust_env = config.get('use_env_proxies', self.config.proxies.use_env_settings)

        # Patch the redirect method directly *if not done already*
        if not getattr(session.resolve_redirects, 'is_mrest_patched', False):
            redirect_logic = session.resolve_redirects

            def wrapped_redirect(resp, req, **kwargs):
                attempt = self.config.redirect_policy.check_redirect(resp, req)
                return redirect_logic(resp, req, **kwargs) if attempt else []
            wrapped_redirect.is_mrest_patched = True

            session.resolve_redirects = wrapped_redirect

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
            hooks.append(make_user_hook_cb(user_hook, session))

        if hooks:
            kwargs['hooks'] = {'response': hooks}

        # Change max_retries in current all installed adapters
        max_retries = config.get('retries', self.config.retry_policy())
        for protocol in self._protocols:
            session.adapters[protocol].max_retries=max_retries

        output_kwargs = self.config.session_configuration_callback(session, self.config, config, **kwargs)
        if output_kwargs is not None:
            kwargs = output_kwargs

        return kwargs

    def send_formdata(self, request, headers=None, content=None, **config):
        """Send data as a multipart form-data request.
        We only deal with file-like objects or strings at this point.
        The requests is not yet streamed.

        :param ClientRequest request: The request object to be sent.
        :param dict headers: Any headers to add to the request.
        :param dict content: Dictionary of the fields of the formdata.
        :param config: Any specific config overrides.
        """
        if content is None:
            content = {}
        content_type = headers.pop('Content-Type', None) if headers else None

        if content_type and content_type.lower() == 'application/x-www-form-urlencoded':
            # Do NOT use "add_content" that assumes input is JSON
            request.data = {f: d for f, d in content.items() if d is not None}
            return self.send(request, headers, None, **config)
        else: # Assume "multipart/form-data"
            file_data = {f: self._format_data(d) for f, d in content.items() if d is not None}
            return self.send(request, headers, None, files=file_data, **config)

    def send(self, request, headers=None, content=None, **config):
        """Prepare and send request object according to configuration.

        :param ClientRequest request: The request object to be sent.
        :param dict headers: Any headers to add to the request.
        :param content: Any body data to add to the request.
        :param config: Any specific config overrides
        """
        if self.config.keep_alive and self._session is None:
            self._session = requests.Session()
        try:
            session = self.creds.signed_session(self._session)
        except TypeError: # Credentials does not support session injection
            session = self.creds.signed_session()
            if self._session is not None:
                _LOGGER.warning("Your credentials class does not support session injection. Performance will not be at the maximum.")

        kwargs = self._configure_session(session, **config)
        if headers:
            request.headers.update(headers)

        if not kwargs.get('files'):
            request.add_content(content)
        if request.data:
            kwargs['data']=request.data
        kwargs['headers'].update(request.headers)

        response = None
        try:
            try:
                response = session.request(
                    request.method,
                    request.url,
                    **kwargs)
                return response

            except (oauth2.rfc6749.errors.InvalidGrantError,
                    oauth2.rfc6749.errors.TokenExpiredError) as err:
                error = "Token expired or is invalid. Attempting to refresh."
                _LOGGER.warning(error)

            try:
                try:
                    session = self.creds.refresh_session(self._session)
                except TypeError: # Credentials does not support session injection
                    session = self.creds.refresh_session()
                    if self._session is not None:
                        _LOGGER.warning("Your credentials class does not support session injection. Performance will not be at the maximum.")
                kwargs = self._configure_session(session, **config)
                if request.data:
                    kwargs['data']=request.data
                kwargs['headers'].update(request.headers)

                response = session.request(
                    request.method,
                    request.url,
                    **kwargs)
                return response
            except (oauth2.rfc6749.errors.InvalidGrantError,
                    oauth2.rfc6749.errors.TokenExpiredError) as err:
                msg = "Token expired or is invalid."
                raise_with_traceback(TokenExpiredError, msg, err)

        except (requests.RequestException,
                oauth2.rfc6749.errors.OAuth2Error) as err:
            msg = "Error occurred in request."
            raise_with_traceback(ClientRequestError, msg, err)
        finally:
            self._close_local_session_if_necessary(response, session, kwargs['stream'])

    def _close_local_session_if_necessary(self, response, session, stream):
        # Do NOT close session if session is self._session. No exception.
        if self._session is session:
            return
        # Here, it's a local session, I might close it.
        if not response or not stream:
            session.close()

    def stream_download(self, data, callback):
        """Generator for streaming request body data.

        :param data: A response object to be streamed.
        :param callback: Custom callback for monitoring progress.
        """
        block = self.config.connection.data_block_size
        if not data._content_consumed:
            with contextlib.closing(data) as response:
                for chunk in response.iter_content(block):
                    if not chunk:
                        break
                    if callback and callable(callback):
                        callback(chunk, response=response)
                    yield chunk
        else:
            for chunk in data.iter_content(block):
                if not chunk:
                    break
                if callback and callable(callback):
                    callback(chunk, response=data)
                yield chunk
        data.close()

    def stream_upload(self, data, callback):
        """Generator for streaming request body data.

        :param data: A file-like object to be streamed.
        :param callback: Custom callback for monitoring progress.
        """
        while True:
            chunk = data.read(self.config.connection.data_block_size)
            if not chunk:
                break
            if callback and callable(callback):
                callback(chunk, response=None)
            yield chunk

    def format_url(self, url, **kwargs):
        """Format request URL with the client base URL, unless the
        supplied URL is already absolute.

        :param str url: The request URL to be formatted if necessary.
        """
        url = url.format(**kwargs)
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            url = url.lstrip('/')
            base = self.config.base_url.format(**kwargs).rstrip('/')
            url = urljoin(base + '/', url)
        return url

    def add_header(self, header, value):
        """Add a persistent header - this header will be applied to all
        requests sent during the current client session.

        :param str header: The header name.
        :param str value: The header value.
        """
        self._headers[header] = value

    def get(self, url=None, params=None):
        """Create a GET request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        """
        request = self._request(url, params)
        request.method = 'GET'
        return request

    def put(self, url=None, params=None):
        """Create a PUT request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        """
        request = self._request(url, params)
        request.method = 'PUT'
        return request

    def post(self, url=None, params=None):
        """Create a POST request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        """
        request = self._request(url, params)
        request.method = 'POST'
        return request

    def head(self, url=None, params=None):
        """Create a HEAD request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        """
        request = self._request(url, params)
        request.method = 'HEAD'
        return request

    def patch(self, url=None, params=None):
        """Create a PATCH request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        """
        request = self._request(url, params)
        request.method = 'PATCH'
        return request

    def delete(self, url=None, params=None):
        """Create a DELETE request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        """
        request = self._request(url, params)
        request.method = 'DELETE'
        return request

    def merge(self, url=None, params=None):
        """Create a MERGE request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        """
        request = self._request(url, params)
        request.method = 'MERGE'
        return request
