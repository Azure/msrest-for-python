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
from typing import Any, Callable, AsyncIterator as AsyncIteratorType

from oauthlib import oauth2
import requests

from ..exceptions import (
    TokenExpiredError,
    ClientRequestError,
    raise_with_traceback)
from . import AsyncHTTPSender, AsyncHTTPPolicy, ClientRequest, AsyncClientResponse, Response
from .requests import (
    BasicRequestsHTTPSender,
    RequestsHTTPSender,
    HTTPRequestsClientResponse
)


_LOGGER = logging.getLogger(__name__)


class AsyncBasicRequestsHTTPSender(BasicRequestsHTTPSender, AsyncHTTPSender):  # type: ignore

    async def __aenter__(self):
        return super(AsyncBasicRequestsHTTPSender, self).__enter__()

    async def __aexit__(self, *exc_details):  # pylint: disable=arguments-differ
        return super(AsyncBasicRequestsHTTPSender, self).__exit__()

    async def send(self, request: ClientRequest, **kwargs: Any) -> Response[AsyncClientResponse]:  # type: ignore
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
            return Response(AsyncRequestsClientResponse(
                request,
                await future
            ))
        except requests.RequestException as err:
            msg = "Error occurred in request."
            raise_with_traceback(ClientRequestError, msg, err)

class AsyncRequestsHTTPSender(AsyncBasicRequestsHTTPSender, RequestsHTTPSender):  # type: ignore

    async def send(self, request: ClientRequest, **kwargs: Any) -> Response[AsyncClientResponse]:  # type: ignore
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

    def __init__(self, response: requests.Response, user_callback: Callable, block: int) -> None:
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

class AsyncRequestsClientResponse(AsyncClientResponse, HTTPRequestsClientResponse):

    def stream_download(self, callback: Callable, chunk_size: int) -> AsyncIteratorType[bytes]:
        """Generator for streaming request body data.

        :param callback: Custom callback for monitoring progress.
        :param int chunk_size:
        """
        return StreamDownloadGenerator(
            self.internal_response,
            callback,
            chunk_size
        )


# Trio support
try:
    import trio

    class TrioStreamDownloadGenerator(AsyncIterator):

        def __init__(self, response: requests.Response, user_callback: Callable, block: int) -> None:
            self.response = response
            self.block = block
            self.user_callback = user_callback
            self.iter_content_func = self.response.iter_content(self.block)

        async def __anext__(self):
            loop = asyncio.get_event_loop()
            try:
                chunk = await trio.run_sync_in_worker_thread(
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

    class TrioAsyncRequestsClientResponse(AsyncClientResponse, HTTPRequestsClientResponse):

        def stream_download(self, callback: Callable, chunk_size: int) -> AsyncIteratorType[bytes]:
            """Generator for streaming request body data.

            :param callback: Custom callback for monitoring progress.
            :param int chunk_size:
            """
            return TrioStreamDownloadGenerator(
                self.internal_response,
                callback,
                chunk_size
            )


    class AsyncTrioBasicRequestsHTTPSender(BasicRequestsHTTPSender, AsyncHTTPSender):  # type: ignore

        async def __aenter__(self):
            return super(AsyncTrioBasicRequestsHTTPSender, self).__enter__()

        async def __aexit__(self, *exc_details):  # pylint: disable=arguments-differ
            return super(AsyncTrioBasicRequestsHTTPSender, self).__exit__()

        async def send(self, request: ClientRequest, **kwargs: Any) -> Response[AsyncClientResponse]:  # type: ignore
            """Send the request using this HTTP sender.
            """
            if request.pipeline_context is None:  # Should not happen, but make mypy happy and does not hurt
                request.pipeline_context = self.build_context()

            session = request.pipeline_context.session

            trio_limiter = kwargs.get("trio_limiter", None)
            future = trio.run_sync_in_worker_thread(
                functools.partial(
                    session.request,
                    request.method,
                    request.url,
                    **kwargs
                ),
                limiter=trio_limiter
            )
            try:
                return Response(TrioAsyncRequestsClientResponse(
                    request,
                    await future
                ))
            except requests.RequestException as err:
                msg = "Error occurred in request."
                raise_with_traceback(ClientRequestError, msg, err)

    class AsyncTrioRequestsHTTPSender(AsyncTrioBasicRequestsHTTPSender, RequestsHTTPSender):  # type: ignore

        async def send(self, request: ClientRequest, **kwargs: Any) -> Response[AsyncClientResponse]:  # type: ignore
            """Send the request using this HTTP sender.
            """
            requests_kwargs = self._configure_send(request, **kwargs)
            return await super(AsyncTrioRequestsHTTPSender, self).send(request, **requests_kwargs)

except ImportError:
    # trio not installed
    pass