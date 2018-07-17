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

import logging
try:
    from urlparse import urljoin, urlparse
except ImportError:
    from urllib.parse import urljoin, urlparse
import warnings

from typing import Any, Dict, Union, IO, Tuple, Optional, Callable, Generator, cast, TYPE_CHECKING  # pylint: disable=unused-import

from .authentication import Authentication
from .pipeline import ClientRequest, Pipeline
from .pipeline.requests import (
    RequestsHTTPSender,
    RequestsCredentialsPolicy,
    RequestsPatchSession
)
from .pipeline.universal import (
    HTTPLogger
)


if TYPE_CHECKING:
    from .configuration import Configuration  # pylint: disable=unused-import
    from .pipeline import ClientResponse  # pylint: disable=unused-import


_LOGGER = logging.getLogger(__name__)

class SDKClient(object):
    """The base class of all generated SDK client.
    """
    def __init__(self, creds, config):
        # type: (Any, Configuration) -> None
        self._client = ServiceClient(creds, config)

    def close(self):
        # type: () -> None
        """Close the client if keep_alive is True.
        """
        self._client.close()

    def __enter__(self):
        # type: () -> SDKClient
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

    def __init__(self, creds, config):
        # type: (Any, Configuration) -> None
        if config is None:
            raise ValueError("Config is a required parameter")
        self.config = config
        self._creds = creds

        self.pipeline = self._create_default_pipeline()

    def _create_default_pipeline(self):
        # type: () -> Pipeline
        policies = [
            self.config._user_agent,  # UserAgent policy
            RequestsPatchSession(),   # Support deprecated operation config at the session level
            HTTPLogger(self.config),  # Log request
        ]
        if self._creds:
            policies.insert(1, RequestsCredentialsPolicy(self._creds))  # Set credentials for requests based session

        return Pipeline(
            policies,
            RequestsHTTPSender(self.config)  # Send HTTP request using requests
        )

    def __enter__(self):
        # type: () -> ServiceClient
        self.config.keep_alive = True
        self.pipeline.__enter__()
        return self

    def __exit__(self, *exc_details):
        self.pipeline.__exit__(*exc_details)
        self.config.keep_alive = False

    def close(self):
        # type: () -> None
        """Close the pipeline if keep_alive is True.
        """
        self.pipeline.__exit__()

    def _request(self, method, url, params, headers, content, form_content):
        # type: (str, str, Optional[Dict[str, str]], Optional[Dict[str, str]], Any, Optional[Dict[str, Any]]) -> ClientRequest
        """Create ClientRequest object.

        :param str url: URL for the request.
        :param dict params: URL query parameters.
        :param dict headers: Headers
        :param dict form_content: Form content
        """
        request = ClientRequest(method, self.format_url(url))

        if params:
            request.format_parameters(params)

        if headers:
            request.headers.update(headers)
        # All requests should contain a Accept.
        # This should be done by Autorest, but wasn't in old Autorest
        # Force it for now, but might deprecate it later.
        if "Accept" not in request.headers:
            _LOGGER.debug("Accept header absent and forced to application/json")
            request.headers['Accept'] = 'application/json'

        if content is not None:
            request.add_content(content)

        if form_content:
            request.add_formdata(form_content)

        return request

    def send_formdata(self, request, headers=None, content=None, **config):
        """Send data as a multipart form-data request.
        We only deal with file-like objects or strings at this point.
        The requests is not yet streamed.

        This method is deprecated, and shouldn't be used anymore.

        :param ClientRequest request: The request object to be sent.
        :param dict headers: Any headers to add to the request.
        :param dict content: Dictionary of the fields of the formdata.
        :param config: Any specific config overrides.
        """
        request.headers = headers
        request.add_formdata(content)
        return self.send(request, **config)

    def send(self, request, headers=None, content=None, **kwargs):
        """Prepare and send request object according to configuration.

        :param ClientRequest request: The request object to be sent.
        :param dict headers: Any headers to add to the request.
        :param content: Any body data to add to the request.
        :param config: Any specific config overrides
        """
        if self.config.keep_alive:
            pipeline = self.pipeline
        else:
            pipeline = self._create_default_pipeline()

        # "content" and "headers" are deprecated, only old SDK
        if headers:
            request.headers.update(headers)
        if not request.files and request.data is None and content is not None:
            request.add_content(content)
        # End of deprecation

        response = None
        kwargs.setdefault('stream', True)
        try:
            response = pipeline.run(request, **kwargs)
            return response
        finally:
            self._close_local_session_if_necessary(response, pipeline, kwargs['stream'])

    def _close_local_session_if_necessary(self, response, pipeline, stream):
        # Do NOT close session if using my own HTTP driver. No exception.
        if self.pipeline is pipeline:
            return
        # Here, it's a local session, I might close it.
        if not response or not stream:
            pipeline._sender.session.close()

    def stream_download(self, data, callback):
        # type: (ClientResponse, Callable) -> Generator[bytes, None, None]
        """Generator for streaming request body data.

        :param data: A response object to be streamed.
        :param callback: Custom callback for monitoring progress.
        """
        block = self.config.connection.data_block_size
        return data.stream_download(callback, block)

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
        # type: (str, Any) -> str
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
        # type: (str, str) -> None
        """Add a persistent header - this header will be applied to all
        requests sent during the current client session.

        .. deprecated:: 0.5.0
           Use config.headers instead

        :param str header: The header name.
        :param str value: The header value.
        """
        warnings.warn("Private attribute _client.add_header is deprecated. Use config.headers instead.",
                      DeprecationWarning)
        self.config.headers[header] = value

    def get(self, url, params=None, headers=None, content=None, form_content=None):
        # type: (str, Optional[Dict[str, str]], Optional[Dict[str, str]], Any, Optional[Dict[str, Any]]) -> ClientRequest
        """Create a GET request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        :param dict headers: Headers
        :param dict form_content: Form content
        """
        request = self._request('GET', url, params, headers, content, form_content)
        request.method = 'GET'
        return request

    def put(self, url, params=None, headers=None, content=None, form_content=None):
        # type: (str, Optional[Dict[str, str]], Optional[Dict[str, str]], Any, Optional[Dict[str, Any]]) -> ClientRequest
        """Create a PUT request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        :param dict headers: Headers
        :param dict form_content: Form content
        """
        request = self._request('PUT', url, params, headers, content, form_content)
        return request

    def post(self, url, params=None, headers=None, content=None, form_content=None):
        # type: (str, Optional[Dict[str, str]], Optional[Dict[str, str]], Any, Optional[Dict[str, Any]]) -> ClientRequest
        """Create a POST request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        :param dict headers: Headers
        :param dict form_content: Form content
        """
        request = self._request('POST', url, params, headers, content, form_content)
        return request

    def head(self, url, params=None, headers=None, content=None, form_content=None):
        # type: (str, Optional[Dict[str, str]], Optional[Dict[str, str]], Any, Optional[Dict[str, Any]]) -> ClientRequest
        """Create a HEAD request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        :param dict headers: Headers
        :param dict form_content: Form content
        """
        request = self._request('HEAD', url, params, headers, content, form_content)
        return request

    def patch(self, url, params=None, headers=None, content=None, form_content=None):
        # type: (str, Optional[Dict[str, str]], Optional[Dict[str, str]], Any, Optional[Dict[str, Any]]) -> ClientRequest
        """Create a PATCH request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        :param dict headers: Headers
        :param dict form_content: Form content
        """
        request = self._request('PATCH', url, params, headers, content, form_content)
        return request

    def delete(self, url, params=None, headers=None, content=None, form_content=None):
        # type: (str, Optional[Dict[str, str]], Optional[Dict[str, str]], Any, Optional[Dict[str, Any]]) -> ClientRequest
        """Create a DELETE request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        :param dict headers: Headers
        :param dict form_content: Form content
        """
        request = self._request('DELETE', url, params, headers, content, form_content)
        return request

    def merge(self, url, params=None, headers=None, content=None, form_content=None):
        # type: (str, Optional[Dict[str, str]], Optional[Dict[str, str]], Any, Optional[Dict[str, Any]]) -> ClientRequest
        """Create a MERGE request object.

        :param str url: The request URL.
        :param dict params: Request URL parameters.
        :param dict headers: Headers
        :param dict form_content: Form content
        """
        request = self._request('MERGE', url, params, headers, content, form_content)
        return request
