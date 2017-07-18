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

import requests
from oauthlib import oauth2

from msrest import ServiceClient
from msrest.authentication import OAuthTokenAuthentication

from msrest import Configuration
from msrest.exceptions import ClientRequestError, TokenExpiredError
from msrest.pipeline import ClientRequest


class TestServiceClient(unittest.TestCase):

    def setUp(self):
        self.cfg = Configuration("https://my_endpoint.com")
        self.creds = mock.create_autospec(OAuthTokenAuthentication)
        self.loop = asyncio.get_event_loop()
        return super(TestServiceClient, self).setUp()


    def test_client_send(self):

        mock_client = mock.create_autospec(ServiceClient)
        mock_client.config = self.cfg
        mock_client.creds = self.creds
        mock_client._configure_session.return_value = {}
        session = mock.create_autospec(requests.Session)
        mock_client.creds.signed_session.return_value = session
        mock_client.creds.refresh_session.return_value = session

        request = ClientRequest('GET')
        future = ServiceClient.async_send(mock_client, request)
        self.loop.run_until_complete(future)
        session.request.call_count = 0
        mock_client._configure_session.assert_called_with(session)
        session.request.assert_called_with('GET', None, [], {})
        session.close.assert_called_with()

        future = ServiceClient.async_send(mock_client, request, headers={'id':'1234'}, content={'Test':'Data'})
        self.loop.run_until_complete(future)
        mock_client._configure_session.assert_called_with(session)
        session.request.assert_called_with('GET', None, '{"Test": "Data"}', {'Content-Length': '16', 'id':'1234'})
        self.assertEqual(session.request.call_count, 1)
        session.request.call_count = 0
        session.close.assert_called_with()

        session.request.side_effect = requests.RequestException("test")
        with self.assertRaises(ClientRequestError):
            future = ServiceClient.async_send(mock_client, request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')
            self.loop.run_until_complete(future)
        mock_client._configure_session.assert_called_with(session, test='value')
        session.request.assert_called_with('GET', None, '{"Test": "Data"}', {'Content-Length': '16', 'id':'1234'})
        self.assertEqual(session.request.call_count, 1)
        session.request.call_count = 0
        session.close.assert_called_with()

        session.request.side_effect = oauth2.rfc6749.errors.InvalidGrantError("test")
        with self.assertRaises(TokenExpiredError):
            future = ServiceClient.async_send(mock_client, request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')
            self.loop.run_until_complete(future)
        self.assertEqual(session.request.call_count, 2)
        session.request.call_count = 0
        session.close.assert_called_with()

        session.request.side_effect = ValueError("test")
        with self.assertRaises(ValueError):
            future = ServiceClient.async_send(mock_client, request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')
            self.loop.run_until_complete(future)
        session.close.assert_called_with()

    def test_client_formdata_send(self):
        def make_coroutine(mock):
            async def coroutine(*args, **kwargs):
                return mock(*args, **kwargs)
            return coroutine        
        send_mock = mock.Mock() 
        mock_client = mock.create_autospec(ServiceClient)
        mock_client._format_data.return_value = "formatted"
        mock_client.send = make_coroutine(send_mock)
        request = ClientRequest('GET')
        future = ServiceClient.send_formdata(mock_client, request)
        self.loop.run_until_complete(future)
        send_mock.assert_called_with(request, None, None, files={})

        future = ServiceClient.send_formdata(mock_client, request, {'id':'1234'}, {'Test':'Data'})
        self.loop.run_until_complete(future)
        send_mock.assert_called_with(request, {'id':'1234'}, None, files={'Test':'formatted'})

        future = ServiceClient.send_formdata(mock_client, request, {'Content-Type':'1234'}, {'1':'1', '2':'2'})
        self.loop.run_until_complete(future)
        send_mock.assert_called_with(request, {}, None, files={'1':'formatted', '2':'formatted'})


if __name__ == '__main__':
    unittest.main()