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
import abc
import functools
import json
import logging
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from typing import Dict, Any, Optional, Union, List, TYPE_CHECKING

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

import requests
from urllib3 import Retry  # Needs requests 2.16 at least to be safe

from ..serialization import Deserializer, Model


_LOGGER = logging.getLogger(__name__)

try:
    ABC = abc.ABC
except ImportError: # Python 2.7
    ABC = abc.ABCMeta('ABC', (object,), {'__slots__': ()})  # type: ignore

class Pipeline:
    """A pipeline implementation.

    This is implemented as a context manager, that will activate the context
    of the HTTP sender.
    """

    def __init__(self, policies):
        # type: List[Union[HTTPPolicy, SansIOHTTPPolicy, HTTPSender]] -> None
        self._impl_policies = []
        for policy in policies:
            if isinstance(policy, SansIOHTTPPolicy):
                self._impl_policies.append(_SansIOHTTPPolicyRunner(policy))
            else:
                self._impl_policies.append(policy)

    def __enter__(self):
        # type: () -> Pipeline
        self._impl_policies[-1].__enter__()
        return self

    def __exit__(self, *exc_details):
        self._impl_policies[-1].__exit__(*exc_details)

    def run(self, request):
        # type: (ClientRequest) -> requests.Response
        context = self._impl_policies[-1].build_context()
        return self._impl_policies[0].send(context, request)

class HTTPSender(ABC):
    """An http sender ABC.
    """

    @abc.abstractmethod
    def send(self, request, **config):
        # type: (ClientRequest, Any) -> requests.Response
        """Send the request using this HTTP sender.
        """
        pass

    def build_context(self):
        # type: () -> Any
        """Allow the sender to build a context that will be passed
        across the pipeline with the request.

        Return type has no constraints. Implementation is not
        required and None by default.
        """
        return None

class HTTPPolicy(ABC):
    """An http policy ABC.
    """

    @abc.abstractmethod
    def send(self, context, request):
        # type: (ClientRequest) -> ClientRawResponse
        """Mutate the request.

        Context content is dependent of the HTTPSender.
        """
        pass

class SansIOHTTPPolicy:
    """Represents a sans I/O policy.

    This policy can act before the I/O, and after the I/O.
    Use this policy if the actual I/O in the middle is an implementation
    detail.

    Context is not available, since it's implementation dependent.
    if a policy needs a context of the Sender, it can't be universal.

    Example: setting a UserAgent does not need to be tight to
    sync or async implementation or specific HTTP lib
    """
    def prepare(self, request):
        """Is executed before sending the request to next policy.
        """
        pass

    def post_send(self, request, response):
        """Is executed after the request comes back from the policy.
        """
        pass

class _SansIOHTTPPolicyRunner(HTTPPolicy):
    """Sync implementation of the SansIO policy.
    """
    def __init__(self, policy):
        # type: (SansIOHTTPPolicy) -> None
        self._policy = policy

    def send(self, context, request):
        self.prepare(request)
        response = self.next.send(context, request)
        self.post_send(request, response)


class ClientRequest(requests.Request):
    """Wrapper for requests.Request object."""

    def format_parameters(self, params):
        # type: (Dict[str, str]) -> None
        """Format parameters into a valid query string.
        It's assumed all parameters have already been quoted as
        valid URL strings.

        :param dict params: A dictionary of parameters.
        """
        query = urlparse(self.url).query
        if query:
            self.url = self.url.partition('?')[0]
            existing_params = {
                p[0]: p[-1]
                for p in [p.partition('=') for p in query.split('&')]
            }
            params.update(existing_params)
        query_params = ["{}={}".format(k, v) for k, v in params.items()]
        query = '?' + '&'.join(query_params)
        self.url = self.url + query

    def add_content(self, data):
        # type: (Optional[Union[Dict[str, Any], ET.Element]]) -> None
        """Add a body to the request.

        :param data: Request body data, can be a json serializable
         object (e.g. dictionary) or a generator (e.g. file data).
        """
        if data is None:
            return

        if isinstance(data, ET.Element):
            self.data = ET.tostring(data, encoding="utf8")
            self.headers['Content-Length'] = str(len(self.data))
            return

        # By default, assume JSON
        try:
            self.data = json.dumps(data)
            self.headers['Content-Length'] = str(len(self.data))
        except TypeError:
            self.data = data


class ClientRawResponse(object):
    """Wrapper for response object.
    This allows for additional data to be gathereded from the response,
    for example deserialized headers.
    It also allows the raw response object to be passed back to the user.

    :param output: Deserialized response object.
    :param response: Raw response object.
    """

    def __init__(self, output, response):
        # type: (Union[Model, List[Model]], Optional[requests.Response]) -> None
        self.response = response
        self.output = output
        self.headers = {}  # type: Dict[str, Optional[Any]]
        self._deserialize = Deserializer()

    def add_headers(self, header_dict):
        # type: (Dict[str, str]) -> None
        """Deserialize a specific header.

        :param dict header_dict: A dictionary containing the name of the
         header and the type to deserialize to.
        """
        if not self.response:
            return
        for name, data_type in header_dict.items():
            value = self.response.headers.get(name)
            value = self._deserialize(data_type, value)
            self.headers[name] = value

# For backward compat, import requests basic policy
from .requests import ClientConnection, ClientProxies, ClientRedirectPolicy, ClientRetryPolicy