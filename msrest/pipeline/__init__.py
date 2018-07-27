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
from __future__ import absolute_import  # we have a "requests" module that conflicts with "requests" on Py2.7
import abc
try:
    import configparser
    from configparser import NoOptionError
except ImportError:
    import ConfigParser as configparser  # type: ignore
    from ConfigParser import NoOptionError  # type: ignore
import json
import logging
import os.path
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from typing import TYPE_CHECKING, cast, IO, List, Union, Any, Mapping, Dict, Optional, Tuple, Callable, Iterator  # pylint: disable=unused-import

# This file is NOT using any "requests" HTTP implementation
# However, the CaseInsensitiveDict is handy.
# If one day we reach the point where "requests" can be skip totally,
# might provide our own implementation
from requests.structures import CaseInsensitiveDict

from ..serialization import Deserializer
from ..exceptions import ClientRequestError, raise_with_traceback

if TYPE_CHECKING:
    from ..serialization import Model  # pylint: disable=unused-import


_LOGGER = logging.getLogger(__name__)

try:
    ABC = abc.ABC
except AttributeError: # Python 2.7, abc exists, but not ABC
    ABC = abc.ABCMeta('ABC', (object,), {'__slots__': ()})  # type: ignore

try:
    from contextlib import AbstractContextManager  # type: ignore
except ImportError: # Python <= 3.5
    class AbstractContextManager(object):  # type: ignore
        def __enter__(self):
            """Return `self` upon entering the runtime context."""
            return self

        @abc.abstractmethod
        def __exit__(self, exc_type, exc_value, traceback):
            """Raise any exception triggered within the runtime context."""
            return None

class HTTPPolicy(ABC):
    """An http policy ABC.
    """
    def __init__(self):
        self.next = None

    @abc.abstractmethod
    def send(self, request, **kwargs):
        # type: (ClientRequest, Any) -> ClientResponse
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
    def on_request(self, request, **kwargs):
        # type: (ClientRequest, Any) -> None
        """Is executed before sending the request to next policy.
        """
        pass

    def on_response(self, request, response, **kwargs):
        # type: (ClientRequest, ClientResponse, Any) -> None
        """Is executed after the request comes back from the policy.
        """
        pass

class _SansIOHTTPPolicyRunner(HTTPPolicy):
    """Sync implementation of the SansIO policy.
    """

    def __init__(self, policy):
        # type: (SansIOHTTPPolicy) -> None
        super(_SansIOHTTPPolicyRunner, self).__init__()
        self._policy = policy

    def send(self, request, **kwargs):
        # type: (ClientRequest, Any) -> ClientResponse
        self._policy.on_request(request, **kwargs)
        response = self.next.send(request, **kwargs)
        self._policy.on_response(request, response, **kwargs)
        return response

class Pipeline(AbstractContextManager):
    """A pipeline implementation.

    This is implemented as a context manager, that will activate the context
    of the HTTP sender.
    """

    def __init__(self, policies=None, sender=None):
        # type: (List[Union[HTTPPolicy, SansIOHTTPPolicy]], HTTPSender) -> None
        self._impl_policies = []  # type: List[HTTPPolicy]
        if not sender:
            # Import default only if nothing is provided
            from .requests import BasicRequestsHTTPSender
            self._sender = cast(HTTPSender, BasicRequestsHTTPSender())
        else:
            self._sender = sender
        for policy in (policies or []):
            if isinstance(policy, SansIOHTTPPolicy):
                self._impl_policies.append(_SansIOHTTPPolicyRunner(policy))
            else:
                self._impl_policies.append(policy)
        for index in range(len(self._impl_policies)-1):
            self._impl_policies[index].next = self._impl_policies[index+1]
        if self._impl_policies:
            self._impl_policies[-1].next = self._sender

    def __enter__(self):
        # type: () -> Pipeline
        self._sender.__enter__()
        return self

    def __exit__(self, *exc_details):  # pylint: disable=arguments-differ
        self._sender.__exit__(*exc_details)

    def run(self, request, **kwargs):
        # type: (ClientRequest, Any) -> ClientResponse
        context = self._sender.build_context()
        request.pipeline_context = context
        first_node = self._impl_policies[0] if self._impl_policies else self._sender
        return first_node.send(request, **kwargs)  # type: ignore

class HTTPSender(AbstractContextManager, ABC):
    """An http sender ABC.
    """

    @abc.abstractmethod
    def send(self, request, **config):
        # type: (ClientRequest, Any) -> ClientResponse
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


class HTTPSenderConfiguration(object):
    """HTTP sender configuration.

    This is composed of generic HTTP configuration, and could be use as a common
    HTTP configuration format.

    :param str filepath: Path to existing config file (optional).
    """

    def __init__(self, filepath=None):
        # Communication configuration
        self.connection = ClientConnection()

        # Headers (sent with every requests)
        self.headers = {}  # type: Dict[str, str]

        # ProxyConfiguration
        self.proxies = ClientProxies()

        # Redirect configuration
        self.redirect_policy = ClientRedirectPolicy()

        self._config = configparser.ConfigParser()
        self._config.optionxform = str

        if filepath:
            self.load(filepath)

    def _clear_config(self):
        # type: () -> None
        """Clearout config object in memory."""
        for section in self._config.sections():
            self._config.remove_section(section)

    def save(self, filepath):
        # type: (str) -> None
        """Save current configuration to file.

        :param str filepath: Path to file where settings will be saved.
        :raises: ValueError if supplied filepath cannot be written to.
        """
        sections = [
            "Connection",
            "Proxies",
            "RedirectPolicy"]
        for section in sections:
            self._config.add_section(section)

        self._config.set("Connection", "timeout", self.connection.timeout)
        self._config.set("Connection", "verify", self.connection.verify)
        self._config.set("Connection", "cert", self.connection.cert)

        self._config.set("Proxies", "proxies", self.proxies.proxies)
        self._config.set("Proxies", "env_settings",
                         self.proxies.use_env_settings)

        self._config.set("RedirectPolicy", "allow", self.redirect_policy.allow)
        self._config.set("RedirectPolicy", "max_redirects",
                         self.redirect_policy.max_redirects)

        try:
            with open(filepath, 'w') as configfile:
                self._config.write(configfile)
        except (KeyError, EnvironmentError):
            error = "Supplied config filepath invalid."
            raise_with_traceback(ValueError, error)
        finally:
            self._clear_config()

    def load(self, filepath):
        # type: (str) -> None
        """Load configuration from existing file.

        :param str filepath: Path to existing config file.
        :raises: ValueError if supplied config file is invalid.
        """
        try:
            self._config.read(filepath)
            import ast
            self.connection.timeout = \
                self._config.getint("Connection", "timeout")
            self.connection.verify = \
                self._config.getboolean("Connection", "verify")
            self.connection.cert = \
                self._config.get("Connection", "cert")

            self.proxies.proxies = \
                ast.literal_eval(self._config.get("Proxies", "proxies"))
            self.proxies.use_env_settings = \
                self._config.getboolean("Proxies", "env_settings")

            self.redirect_policy.allow = \
                self._config.getboolean("RedirectPolicy", "allow")
            self.redirect_policy.max_redirects = \
                self._config.set("RedirectPolicy", "max_redirects")

        except (ValueError, EnvironmentError, NoOptionError):
            error = "Supplied config file incompatible."
            raise_with_traceback(ValueError, error)
        finally:
            self._clear_config()


class ClientRequest(object):
    """Represents a HTTP request.

    URL can be given without query parameters, to be added later using "format_parameters".

    Instance can be created without data, to be added later using "add_content"

    Instance can be created without files, to be added later using "add_formdata"

    :param str method: HTTP method (GET, HEAD, etc.)
    :param str url: At least complete scheme/host/path
    :param dict[str,str] headers: HTTP headers
    :param files: Files list.
    :param data: Body to be sent.
    :type data: bytes or str.
    """
    def __init__(self, method, url, headers=None, files=None, data=None):
        # type: (str, str, Mapping[str, str], Any, Any) -> None
        self.method = method
        self.url = url
        self.headers = CaseInsensitiveDict(headers)
        self.files = files
        self.data = data
        self.pipeline_context = None  # type: Any

    def __repr__(self):
        return '<ClientRequest [%s]>' % (self.method)

    @property
    def body(self):
        """Alias to data."""
        return self.data

    @body.setter
    def body(self, value):
        self.data = value

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
            bytes_data = ET.tostring(data, encoding="utf8")
            self.headers['Content-Length'] = str(len(bytes_data))
            self.data = bytes_data
            return

        # By default, assume JSON
        try:
            self.data = json.dumps(data)
            self.headers['Content-Length'] = str(len(self.data))
        except TypeError:
            self.data = data

    @staticmethod
    def _format_data(data):
        # type: (Union[str, IO]) -> Union[Tuple[None, str], Tuple[Optional[str], IO, str]]
        """Format field data according to whether it is a stream or
        a string for a form-data request.

        :param data: The request field data.
        :type data: str or file-like object.
        """
        if hasattr(data, 'read'):
            data = cast(IO, data)
            data_name = None
            try:
                if data.name[0] != '<' and data.name[-1] != '>':
                    data_name = os.path.basename(data.name)
            except (AttributeError, TypeError):
                pass
            return (data_name, data, "application/octet-stream")
        return (None, cast(str, data))

    def add_formdata(self, content=None):
        # type: (Optional[Dict[str, str]]) -> None
        """Add data as a multipart form-data request to the request.

        We only deal with file-like objects or strings at this point.
        The requests is not yet streamed.

        :param dict headers: Any headers to add to the request.
        :param dict content: Dictionary of the fields of the formdata.
        """
        if content is None:
            content = {}
        content_type = self.headers.pop('Content-Type', None) if self.headers else None

        if content_type and content_type.lower() == 'application/x-www-form-urlencoded':
            # Do NOT use "add_content" that assumes input is JSON
            self.data = {f: d for f, d in content.items() if d is not None}
        else: # Assume "multipart/form-data"
            self.files = {f: self._format_data(d) for f, d in content.items() if d is not None}

class HTTPClientResponse(object):
    """Represent a HTTP response.

    No body is defined here on purpose, since async pipeline
    will provide async ways to access the body

    You have two differents types of body:
    - Full in-memory using "body" as bytes
    - Stream body using stream_download
    """
    def __init__(self, request, internal_response):
        # type: (ClientRequest, Any) -> None
        self.request = request
        self.internal_response = internal_response
        self.status_code = None  # type: Optional[int]
        self.headers = {}  # type: Dict[str, str]
        self.reason = None  # type: Optional[str]

    def body(self):
        # type: () -> bytes
        """Return the whole body as bytes in memory.
        """
        pass

    def text(self, encoding=None):
        # type: (str) -> str
        """Return the whole body as a string.

        :param str encoding: The encoding to apply. If None, use "utf-8".
         Implementation can be smarter if they want (using headers).
        """
        return self.body().decode(encoding or "utf-8")

    def raise_for_status(self):
        """Raise for status. Should be overriden, but basic implementation provided.
        """
        if self.status_code >= 400:
            raise ClientRequestError("Received status code {}".format(self.status_code))


class ClientResponse(HTTPClientResponse):

    def stream_download(self, callback, chunk_size):
        # type: (Callable, int) -> Iterator[bytes]
        """Generator for streaming request body data.

        Should be implemented by sub-classes if streaming download
        is supported.

        :param callback: Custom callback for monitoring progress.
        :param int chunk_size:
        """
        pass


# ClientRawResponse is in Pipeline for compat, but technically there is nothing Pipeline here, this is deserialization

class ClientRawResponse(object):
    """Wrapper for response object.
    This allows for additional data to be gathereded from the response,
    for example deserialized headers.
    It also allows the raw response object to be passed back to the user.

    :param output: Deserialized response object.
    :param response: Raw response object.
    """

    def __init__(self, output, response):
        # type: (Union[Model, List[Model]], Optional[ClientResponse]) -> None
        if isinstance(response, ClientResponse):
            # Let's not do too much layers
            self.response = response.internal_response
        else:
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


__all__ = [
    'ClientRequest',
    'ClientResponse',
    'ClientRawResponse',
    'Pipeline',
    'HTTPPolicy',
    'SansIOHTTPPolicy',
    'HTTPSender',
    # Generic HTTP configuration
    'HTTPSenderConfiguration',
    'ClientRedirectPolicy',
    'ClientProxies',
    'ClientConnection'
]

try:
    from .async_abc import AsyncPipeline, AsyncHTTPPolicy, AsyncHTTPSender, AsyncClientResponse  # pylint: disable=unused-import
    from .async_abc import __all__ as _async_all
    __all__ += _async_all
except SyntaxError: # Python 2
    pass