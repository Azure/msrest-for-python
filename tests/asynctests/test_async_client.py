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

import io
import asyncio
import json
import unittest
try:
    from unittest import mock
except ImportError:
    import mock
import sys

import pytest

import requests
from requests.adapters import HTTPAdapter
from oauthlib import oauth2

from msrest.async_client import ServiceClientAsync
from msrest.authentication import OAuthTokenAuthentication
from msrest.configuration import Configuration

from msrest import Configuration
from msrest.exceptions import ClientRequestError, TokenExpiredError
from msrest.universal_http import ClientRequest
from msrest.universal_http.async_requests import AsyncRequestsClientResponse


@unittest.skipIf(sys.version_info < (3, 5, 2), "Async tests only on 3.5.2 minimal")
class TestServiceClient(object):

    @pytest.mark.asyncio
    async def test_client_send(self):

        cfg = Configuration("/")
        cfg.headers = {'Test': 'true'}
        cfg.credentials = mock.create_autospec(OAuthTokenAuthentication)

        client = ServiceClientAsync(cfg)

        req_response = requests.Response()
        req_response._content = br'{"real": true}'  # Has to be valid bytes JSON
        req_response._content_consumed = True
        req_response.status_code = 200

        def side_effect(*args, **kwargs):
            return req_response

        session = mock.create_autospec(requests.Session)
        session.request.side_effect = side_effect
        session.adapters = {
            "http://": HTTPAdapter(),
            "https://": HTTPAdapter(),
        }
        # Be sure the mock does not trick me
        assert not hasattr(session.resolve_redirects, 'is_msrest_patched')

        client.config.pipeline._sender.driver.session = session
        client.config.credentials.signed_session.return_value = session
        client.config.credentials.refresh_session.return_value = session

        request = ClientRequest('GET', '/')
        await client.async_send(request, stream=False)
        session.request.call_count = 0
        session.request.assert_called_with(
            'GET',
            '/',
            allow_redirects=True,
            cert=None,
            headers={
                'User-Agent': cfg.user_agent,
                'Test': 'true'  # From global config
            },
            stream=False,
            timeout=100,
            verify=True
        )
        assert session.resolve_redirects.is_msrest_patched

        request = client.get('/', headers={'id':'1234'}, content={'Test':'Data'})
        await client.async_send(request, stream=False)
        session.request.assert_called_with(
            'GET',
            '/',
            data='{"Test": "Data"}',
            allow_redirects=True,
            cert=None,
            headers={
                'User-Agent': cfg.user_agent,
                'Content-Length': '16',
                'id':'1234',
                'Accept': 'application/json',
                'Test': 'true'  # From global config
            },
            stream=False,
            timeout=100,
            verify=True
        )
        assert session.request.call_count == 1
        session.request.call_count = 0
        assert session.resolve_redirects.is_msrest_patched

        request = client.get('/', headers={'id':'1234'}, content={'Test':'Data'})
        session.request.side_effect = requests.RequestException("test")
        with pytest.raises(ClientRequestError):
            await client.async_send(request, test='value', stream=False)
        session.request.assert_called_with(
            'GET',
            '/',
            data='{"Test": "Data"}',
            allow_redirects=True,
            cert=None,
            headers={
                'User-Agent': cfg.user_agent,
                'Content-Length': '16',
                'id':'1234',
                'Accept': 'application/json',
                'Test': 'true'  # From global config
            },
            stream=False,
            timeout=100,
            verify=True
        )
        assert session.request.call_count == 1
        session.request.call_count = 0
        assert session.resolve_redirects.is_msrest_patched

        session.request.side_effect = oauth2.rfc6749.errors.InvalidGrantError("test")
        with pytest.raises(TokenExpiredError):
            await client.async_send(request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')
        assert session.request.call_count == 2
        session.request.call_count = 0

        session.request.side_effect = ValueError("test")
        with pytest.raises(ValueError):
            await client.async_send(request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')

    @pytest.mark.asyncio
    async def test_client_stream_download(self):

        req_response = requests.Response()
        req_response._content = "abc"
        req_response._content_consumed = True
        req_response.status_code = 200

        client_response = AsyncRequestsClientResponse(
            None,
            req_response
        )

        def user_callback(chunk, response):
            assert response is req_response
            assert chunk in ["a", "b", "c"]

        async_iterator = client_response.stream_download(1, user_callback)
        result = ""
        async for value in async_iterator:
            result += value
        assert result == "abc"


if __name__ == '__main__':
    unittest.main()