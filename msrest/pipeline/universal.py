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
This module represents universal policy that works whatever the HTTPSender implementation
"""
import platform

from typing import Mapping, Any, Optional, TYPE_CHECKING

from ..version import msrest_version as _msrest_version
from . import SansIOHTTPPolicy
from ..http_logger import log_request, log_response

if TYPE_CHECKING:
    from . import ClientRequest, ClientResponse

class HeadersPolicy(SansIOHTTPPolicy):
    """A simple policy that sends the given headers
    with the request.

    This overwrite any headers already defined in the request.
    """
    def __init__(self, headers):
        # type: (Mapping[str, str]) -> None
        self.headers = headers

    def prepare(self, request, **kwargs):
        # type: (ClientRequest, Any) -> None
        request.headers.update(self.headers)

class UserAgentPolicy(SansIOHTTPPolicy):
    _USERAGENT = "User-Agent"

    def __init__(self, user_agent=None, overwrite=False):
        # type: (Optional[str], bool) -> None
        self._overwrite = overwrite
        if user_agent is None:
            self._user_agent = "python/{} ({}) msrest/{}".format(
                platform.python_version(),
                platform.platform(),
                _msrest_version
            )
        else:
            self._user_agent = user_agent

    @property
    def user_agent(self):
        # type: () -> str
        """The current user agent value."""
        return self._user_agent

    def add_user_agent(self, value):
        # type: (str) -> None
        """Add value to current user agent with a space.

        :param str value: value to add to user agent.
        """
        self._user_agent = "{} {}".format(self._user_agent, value)

    def prepare(self, request, **kwargs):
        # type: (ClientRequest, Any) -> None
        if self._overwrite or self._USERAGENT not in request.headers:
            request.headers[self._USERAGENT] = self._user_agent

class HTTPLogger(SansIOHTTPPolicy):
    def __init__(self, config):
        self._config = config

    def prepare(self, request, **kwargs):
        # type: (ClientRequest, Any) -> None
        if kwargs.get("enable_http_logger", self._config.enable_http_logger):
            log_request(None, request)

    def post_send(self, request, response, **kwargs):
        # type: (ClientRequest, ClientResponse, Any) -> None
        if kwargs.get("enable_http_logger", self._config.enable_http_logger):
            log_response(None, request, response, result=response)
