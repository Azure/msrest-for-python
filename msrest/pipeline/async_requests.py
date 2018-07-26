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
import functools
import logging
from typing import Any

from oauthlib import oauth2
import requests

from ..exceptions import (
    TokenExpiredError,
    ClientRequestError,
    raise_with_traceback)
from . import AsyncHTTPSender, AsyncHTTPPolicy, ClientRequest, ClientResponse
from .requests import BasicRequestsHTTPSender, RequestsHTTPSender, RequestsClientResponse


_LOGGER = logging.getLogger(__name__)


class AsyncBasicRequestsHTTPSender(BasicRequestsHTTPSender, AsyncHTTPSender):  # type: ignore

    async def __aenter__(self):
        return super(AsyncBasicRequestsHTTPSender, self).__enter__()

    async def __aexit__(self, *exc_details):  # pylint: disable=arguments-differ
        return super(AsyncBasicRequestsHTTPSender, self).__exit__()

    async def send(self, request: ClientRequest, **kwargs: Any) -> ClientResponse:  # type: ignore
        """Send the request using this HTTP sender.
        """
        if request.pipeline_context is None:  # Should not happen, but make mypy happy and does not hurt
            request.pipeline_context = self.build_context()

        session = request.pipeline_context.session

        loop = kwargs.get("loop", asyncio.get_event_loop())
        future = loop.run_in_executor(
            None,
            functools.partial(
                session.request,
                request.method,
                request.url,
                **kwargs
            )
        )
        try:
            return RequestsClientResponse(
                request,
                await future
            )
        except requests.RequestException as err:
            msg = "Error occurred in request."
            raise_with_traceback(ClientRequestError, msg, err)

class AsyncRequestsHTTPSender(AsyncBasicRequestsHTTPSender, RequestsHTTPSender):  # type: ignore

    async def send(self, request: ClientRequest, **kwargs: Any) -> ClientResponse:  # type: ignore
        """Send the request using this HTTP sender.
        """
        requests_kwargs = self._configure_send(request, **kwargs)
        return await super(AsyncRequestsHTTPSender, self).send(request, **requests_kwargs)

class AsyncRequestsCredentialsPolicy(AsyncHTTPPolicy):
    """Implementation of request-oauthlib except and retry logic.
    """
    def __init__(self, credentials):
        super(AsyncRequestsCredentialsPolicy, self).__init__()
        self._creds = credentials

    async def send(self, request, **kwargs):
        session = request.pipeline_context.session
        try:
            self._creds.signed_session(session)
        except TypeError: # Credentials does not support session injection
            _LOGGER.warning("Your credentials class does not support session injection. Performance will not be at the maximum.")
            request.pipeline_context.session = session = self._creds.signed_session()

        try:
            try:
                return await self.next.send(request, **kwargs)
            except (oauth2.rfc6749.errors.InvalidGrantError,
                    oauth2.rfc6749.errors.TokenExpiredError) as err:
                error = "Token expired or is invalid. Attempting to refresh."
                _LOGGER.warning(error)

            try:
                try:
                    self._creds.refresh_session(session)
                except TypeError: # Credentials does not support session injection
                    _LOGGER.warning("Your credentials class does not support session injection. Performance will not be at the maximum.")
                    request.pipeline_context.session = session = self._creds.refresh_session()

                return await self.next.send(request, **kwargs)
            except (oauth2.rfc6749.errors.InvalidGrantError,
                    oauth2.rfc6749.errors.TokenExpiredError) as err:
                msg = "Token expired or is invalid."
                raise_with_traceback(TokenExpiredError, msg, err)

        except (requests.RequestException,
                oauth2.rfc6749.errors.OAuth2Error) as err:
            msg = "Error occurred in request."
            raise_with_traceback(ClientRequestError, msg, err)
