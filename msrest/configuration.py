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


try:
    import configparser
    from configparser import NoOptionError
except ImportError:
    import ConfigParser as configparser  # type: ignore
    from ConfigParser import NoOptionError  # type: ignore

from typing import TYPE_CHECKING, Dict, List, Any, Callable  # pylint: disable=unused-import

from .exceptions import raise_with_traceback
from .pipeline import HTTPSenderConfiguration
from .pipeline.requests import (
    ClientRetryPolicy,
)
from .pipeline.universal import (
    UserAgentPolicy,
    HTTPLogger,
)


if TYPE_CHECKING:
    import requests  # pylint: disable=unused-import

def default_session_configuration_callback(session, global_config, local_config, **kwargs):  # pylint: disable=unused-argument
    # type: (requests.Session, Configuration, Dict[str,str], str) -> Dict[str, str]
    """Configuration callback if you need to change default session configuration.

    :param requests.Session session: The session.
    :param Configuration global_config: The global configuration.
    :param dict[str,str] local_config: The on-the-fly configuration passed on the call.
    :param dict[str,str] kwargs: The current computed values for session.request method.
    :return: Must return kwargs, to be passed to session.request. If None is return, initial kwargs will be used.
    :rtype: dict[str,str]
    """
    return kwargs


class Configuration(HTTPSenderConfiguration):
    """Client configuration.

    :param str baseurl: REST API base URL.
    :param str filepath: Path to existing config file (optional).
    """

    def __init__(self, base_url, filepath=None):
        super(Configuration, self).__init__()
        # type: (str, str) -> None
        # Service
        self.base_url = base_url

        # Retry configuration
        self.retry_policy = ClientRetryPolicy()

        # User-Agent as a policy
        self.user_agent_policy = UserAgentPolicy()

        # HTTP logger policy
        self.http_logger_policy = HTTPLogger()

        # Requests hooks. Must respect requests hook callback signature
        # Note that we will inject the following parameters:
        # - kwargs['msrest']['session'] with the current session
        self.hooks = []  # type: List[Callable[[requests.Response, str, str], None]]

        self.session_configuration_callback = default_session_configuration_callback

        # If set to True, ServiceClient will own the sessionn
        self.keep_alive = False

        if filepath:
            self.load(filepath)

    @property
    def user_agent(self):
        # type: () -> str
        """The current user agent value."""
        return self.user_agent_policy.user_agent

    def add_user_agent(self, value):
        # type: (str) -> None
        """Add value to current user agent with a space.

        :param str value: value to add to user agent.
        """
        self.user_agent_policy.add_user_agent(value)

    @property
    def enable_http_logger(self):
        return self.http_logger_policy.enable_http_logger

    @enable_http_logger.setter
    def enable_http_logger(self, value):
        self.http_logger_policy.enable_http_logger = value

    def save(self, filepath):
        """Save current configuration to file.

        :param str filepath: Path to file where settings will be saved.
        :raises: ValueError if supplied filepath cannot be written to.
        """
        self._config.add_section("RetryPolicy")
        self._config.set("RetryPolicy", "retries", self.retry_policy.retries)
        self._config.set("RetryPolicy", "backoff_factor",
                         self.retry_policy.backoff_factor)
        self._config.set("RetryPolicy", "max_backoff",
                         self.retry_policy.max_backoff)
        super(Configuration, self).save(filepath)

    def load(self, filepath):
        try:
            self.retry_policy.retries = \
                self._config.getint("RetryPolicy", "retries")
            self.retry_policy.backoff_factor = \
                self._config.getfloat("RetryPolicy", "backoff_factor")
            self.retry_policy.max_backoff = \
                self._config.getint("RetryPolicy", "max_backoff")
        except (ValueError, EnvironmentError, NoOptionError):
            error = "Supplied config file incompatible."
            raise_with_traceback(ValueError, error)
        finally:
            self._clear_config()
        super(Configuration, self).load(filepath)
