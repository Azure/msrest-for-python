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

from msrest import ServiceClient
from msrest.authentication import OAuthTokenAuthentication
from msrest.configuration import Configuration

from msrest import Configuration
from msrest.exceptions import ClientRequestError, TokenExpiredError
from msrest.pipeline import ClientRequest


@unittest.skipIf(sys.version_info < (3, 5, 2), "Async tests only on 3.5.2 minimal")
class TestServiceClient(object):

    @pytest.mark.asyncio
    async def test_client_send(self):

        cfg = Configuration("/")
        cfg.headers = {'Test': 'true'}
        creds = mock.create_autospec(OAuthTokenAuthentication)

        client = ServiceClient(creds, cfg)

        session = mock.create_autospec(requests.Session)
        session.adapters = {
            "http://": HTTPAdapter(),
            "https://": HTTPAdapter(),
        }
        # Be sure the mock does not trick me
        assert not hasattr(session.resolve_redirects, 'is_msrest_patched')

        client.async_pipeline._sender.session = session

        client._creds.signed_session.return_value = session
        client._creds.refresh_session.return_value = session

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

        # FIXME uncomment once credentials is done in async
        # session.request.side_effect = oauth2.rfc6749.errors.InvalidGrantError("test")
        # with pytest.raises(TokenExpiredError):
        #     await client.async_send(request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')
        # assert session.request.call_count == 2
        # session.request.call_count = 0

        session.request.side_effect = ValueError("test")
        with pytest.raises(ValueError):
            await client.async_send(request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')

    @pytest.mark.asyncio
    async def test_client_stream_download(self):

        mock_client = ServiceClient(None, Configuration(None))
        mock_client.config.connection.data_block_size = 1

        response = requests.Response()
        response._content = "abc"
        response._content_consumed = True
        response.status_code = 200

        def user_callback(chunk, local_response):
            assert local_response is response
            assert chunk in ["a", "b", "c"]

        async_iterator = mock_client.stream_download_async(response, user_callback)
        result = ""
        async for value in async_iterator:
            result += value
        assert result == "abc"


if __name__ == '__main__':
    unittest.main()