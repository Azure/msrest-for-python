#--------------------------------------------------------------------------
#
# Copyright (c) Microsoft Corporation. All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the ""Software""), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#--------------------------------------------------------------------------
import sys

from msrest.universal_http import (
    ClientRequest,
    AsyncHTTPSender,
)
from msrest.universal_http.aiohttp import AioHTTPSender
from msrest.universal_http.async_requests import (
    AsyncBasicRequestsHTTPSender,
    AsyncRequestsHTTPSender,
    AsyncTrioRequestsHTTPSender,
)

from msrest.configuration import Configuration

import trio

import pytest


@pytest.mark.asyncio
async def test_basic_aiohttp():

    request = ClientRequest("GET", "http://bing.com")
    async with AioHTTPSender() as sender:
        response = await sender.send(request)
        assert response.body() is not None

    assert sender._session.closed
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_basic_async_requests():

    request = ClientRequest("GET", "http://bing.com")
    async with AsyncBasicRequestsHTTPSender() as sender:
        response = await sender.send(request)
        assert response.body() is not None

    assert response.status_code == 200

@pytest.mark.asyncio
async def test_conf_async_requests():

    conf = Configuration("http://bing.com/")
    request = ClientRequest("GET", "http://bing.com/")
    async with AsyncRequestsHTTPSender(conf) as sender:
        response = await sender.send(request)
        assert response.body() is not None

    assert response.status_code == 200

def test_conf_async_trio_requests():

    async def do():
        conf = Configuration("http://bing.com/")
        request = ClientRequest("GET", "http://bing.com/")
        async with AsyncTrioRequestsHTTPSender(conf) as sender:
            return await sender.send(request)
            assert response.body() is not None

    response = trio.run(do)
    assert response.status_code == 200