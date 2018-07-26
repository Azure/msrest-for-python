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
from typing import Any

import requests

from ..exceptions import (
    TokenExpiredError,
    ClientRequestError,
    raise_with_traceback)
from . import AsyncHTTPSender, ClientRequest, ClientResponse
from .requests import BasicRequestsHTTPSender, RequestsHTTPSender, RequestsClientResponse


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
