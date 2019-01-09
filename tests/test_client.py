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
import json
import unittest
try:
    from unittest import mock
except ImportError:
    import mock
import sys

import requests
from requests.adapters import HTTPAdapter
from oauthlib import oauth2

from msrest import ServiceClient, SDKClient
from msrest.universal_http import (
    ClientRequest,
    ClientResponse
)
from msrest.universal_http.requests import (
    RequestsHTTPSender,
    RequestsClientResponse
)

from msrest.pipeline import (
    HTTPSender,
    Response,
)
from msrest.authentication import OAuthTokenAuthentication, Authentication

from msrest import Configuration
from msrest.exceptions import ClientRequestError, TokenExpiredError


class TestServiceClient(unittest.TestCase):

    def setUp(self):
        self.cfg = Configuration("https://my_endpoint.com")
        self.cfg.headers = {'Test': 'true'}
        self.creds = mock.create_autospec(OAuthTokenAuthentication)
        self.cfg.credentials = self.creds
        return super(TestServiceClient, self).setUp()


    def test_deprecated_creds(self):
        """Test that creds parameters gets populated correctly.

        https://github.com/Azure/msrest-for-python/issues/135
        """

        cfg = Configuration("http://127.0.0.1/")
        assert cfg.credentials is None

        creds = Authentication()

        client = SDKClient(creds, cfg)
        assert cfg.credentials is creds

    def test_sdk_context_manager(self):
        cfg = Configuration("http://127.0.0.1/")

        class Creds(Authentication):
            def __init__(self):
                self.first_session = None
                self.called = 0

            def signed_session(self, session=None):
                self.called += 1
                assert session is not None
                if self.first_session:
                    assert self.first_session is session
                else:
                    self.first_session = session
        cfg.credentials = Creds()

        with SDKClient(None, cfg) as client:
            assert cfg.keep_alive

            req = client._client.get('/')
            try:
                # Will fail, I don't care, that's not the point of the test
                client._client.send(req, timeout=0)
            except Exception:
                pass

            try:
                # Will fail, I don't care, that's not the point of the test
                client._client.send(req, timeout=0)
            except Exception:
                pass

        assert not cfg.keep_alive
        assert cfg.credentials.called == 2

    def test_context_manager(self):

        cfg = Configuration("http://127.0.0.1/")

        class Creds(Authentication):
            def __init__(self):
                self.first_session = None
                self.called = 0

            def signed_session(self, session=None):
                self.called += 1
                assert session is not None
                if self.first_session:
                    assert self.first_session is session
                else:
                    self.first_session = session
        cfg.credentials = Creds()

        with ServiceClient(None, cfg) as client:
            assert cfg.keep_alive

            req = client.get('/')
            try:
                # Will fail, I don't care, that's not the point of the test
                client.send(req, timeout=0)
            except Exception:
                pass

            try:
                # Will fail, I don't care, that's not the point of the test
                client.send(req, timeout=0)
            except Exception:
                pass

        assert not cfg.keep_alive
        assert cfg.credentials.called == 2

    def test_keep_alive(self):

        cfg = Configuration("http://127.0.0.1/")
        cfg.keep_alive = True

        class Creds(Authentication):
            def __init__(self):
                self.first_session = None
                self.called = 0

            def signed_session(self, session=None):
                self.called += 1
                assert session is not None
                if self.first_session:
                    assert self.first_session is session
                else:
                    self.first_session = session
        cfg.credentials = Creds()

        client = ServiceClient(None, cfg)
        req = client.get('/')
        try:
            # Will fail, I don't care, that's not the point of the test
            client.send(req, timeout=0)
        except Exception:
            pass

        try:
            # Will fail, I don't care, that's not the point of the test
            client.send(req, timeout=0)
        except Exception:
            pass

        assert cfg.credentials.called == 2
        # Manually close the client in "keep_alive" mode
        client.close()

    def test_client_request(self):

        cfg = Configuration("http://127.0.0.1/")
        client = ServiceClient(self.creds, cfg)
        obj = client.get('/')
        self.assertEqual(obj.method, 'GET')
        self.assertEqual(obj.url, "http://127.0.0.1/")

        obj = client.get("/service", {'param':"testing"})
        self.assertEqual(obj.method, 'GET')
        self.assertEqual(obj.url, "http://127.0.0.1/service?param=testing")

        obj = client.get("service 2")
        self.assertEqual(obj.method, 'GET')
        self.assertEqual(obj.url, "http://127.0.0.1/service 2")

        cfg.base_url = "https://127.0.0.1/"
        obj = client.get("//service3")
        self.assertEqual(obj.method, 'GET')
        self.assertEqual(obj.url, "https://127.0.0.1/service3")

        obj = client.put('/')
        self.assertEqual(obj.method, 'PUT')

        obj = client.post('/')
        self.assertEqual(obj.method, 'POST')

        obj = client.head('/')
        self.assertEqual(obj.method, 'HEAD')

        obj = client.merge('/')
        self.assertEqual(obj.method, 'MERGE')

        obj = client.patch('/')
        self.assertEqual(obj.method, 'PATCH')

        obj = client.delete('/')
        self.assertEqual(obj.method, 'DELETE')

    def test_format_url(self):

        url = "/bool/test true"

        client = mock.create_autospec(ServiceClient)
        client.config = mock.Mock(base_url="http://localhost:3000")

        formatted = ServiceClient.format_url(client, url)
        self.assertEqual(formatted, "http://localhost:3000/bool/test true")

        client.config = mock.Mock(base_url="http://localhost:3000/")
        formatted = ServiceClient.format_url(client, url, foo=123, bar="value")
        self.assertEqual(formatted, "http://localhost:3000/bool/test true")

        url = "https://absolute_url.com/my/test/path"
        formatted = ServiceClient.format_url(client, url)
        self.assertEqual(formatted, "https://absolute_url.com/my/test/path")
        formatted = ServiceClient.format_url(client, url, foo=123, bar="value")
        self.assertEqual(formatted, "https://absolute_url.com/my/test/path")

        url = "test"
        formatted = ServiceClient.format_url(client, url)
        self.assertEqual(formatted, "http://localhost:3000/test")

        client.config = mock.Mock(base_url="http://{hostname}:{port}/{foo}/{bar}")
        formatted = ServiceClient.format_url(client, url, hostname="localhost", port="3000", foo=123, bar="value")
        self.assertEqual(formatted, "http://localhost:3000/123/value/test")

        client.config = mock.Mock(base_url="https://my_endpoint.com/")
        formatted = ServiceClient.format_url(client, url, foo=123, bar="value")
        self.assertEqual(formatted, "https://my_endpoint.com/test")


    def test_client_send(self):
        current_ua = self.cfg.user_agent

        client = ServiceClient(self.creds, self.cfg)
        client.config.keep_alive = True

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
        client.send(request, stream=False)
        session.request.call_count = 0
        session.request.assert_called_with(
            'GET',
            '/',
            allow_redirects=True,
            cert=None,
            headers={
                'User-Agent': current_ua,
                'Test': 'true'  # From global config
            },
            stream=False,
            timeout=100,
            verify=True
        )
        assert session.resolve_redirects.is_msrest_patched

        client.send(request, headers={'id':'1234'}, content={'Test':'Data'}, stream=False)
        session.request.assert_called_with(
            'GET',
            '/',
            data='{"Test": "Data"}',
            allow_redirects=True,
            cert=None,
            headers={
                'User-Agent': current_ua,
                'Content-Length': '16',
                'id':'1234',
                'Test': 'true'  # From global config
            },
            stream=False,
            timeout=100,
            verify=True
        )
        self.assertEqual(session.request.call_count, 1)
        session.request.call_count = 0
        assert session.resolve_redirects.is_msrest_patched

        session.request.side_effect = requests.RequestException("test")
        with self.assertRaises(ClientRequestError):
            client.send(request, headers={'id':'1234'}, content={'Test':'Data'}, test='value', stream=False)
        session.request.assert_called_with(
            'GET',
            '/',
            data='{"Test": "Data"}',
            allow_redirects=True,
            cert=None,
            headers={
                'User-Agent': current_ua,
                'Content-Length': '16',
                'id':'1234',
                'Test': 'true'  # From global config
            },
            stream=False,
            timeout=100,
            verify=True
        )
        self.assertEqual(session.request.call_count, 1)
        session.request.call_count = 0
        assert session.resolve_redirects.is_msrest_patched

        session.request.side_effect = oauth2.rfc6749.errors.InvalidGrantError("test")
        with self.assertRaises(TokenExpiredError):
            client.send(request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')
        self.assertEqual(session.request.call_count, 2)
        session.request.call_count = 0

        session.request.side_effect = ValueError("test")
        with self.assertRaises(ValueError):
            client.send(request, headers={'id':'1234'}, content={'Test':'Data'}, test='value')

    @mock.patch.object(ClientRequest, "_format_data")
    def test_client_formdata_add(self, format_data):
        format_data.return_value = "formatted"

        request = ClientRequest('GET', '/')
        request.add_formdata()
        assert request.files == {}

        request = ClientRequest('GET', '/')
        request.add_formdata({'Test':'Data'})
        assert request.files == {'Test':'formatted'}

        request = ClientRequest('GET', '/')
        request.headers = {'Content-Type':'1234'}
        request.add_formdata({'1':'1', '2':'2'})
        assert request.files == {'1':'formatted', '2':'formatted'}

        request = ClientRequest('GET', '/')
        request.headers = {'Content-Type':'1234'}
        request.add_formdata({'1':'1', '2':None})
        assert request.files == {'1':'formatted'}

        request = ClientRequest('GET', '/')
        request.headers = {'Content-Type':'application/x-www-form-urlencoded'}
        request.add_formdata({'1':'1', '2':'2'})
        assert request.files is None
        assert request.data == {'1':'1', '2':'2'}

        request = ClientRequest('GET', '/')
        request.headers = {'Content-Type':'application/x-www-form-urlencoded'}
        request.add_formdata({'1':'1', '2':None})
        assert request.files is None
        assert request.data == {'1':'1'}

    def test_format_data(self):

        data = ClientRequest._format_data(None)
        self.assertEqual(data, (None, None))

        data = ClientRequest._format_data("Test")
        self.assertEqual(data, (None, "Test"))

        mock_stream = mock.create_autospec(io.BytesIO)
        data = ClientRequest._format_data(mock_stream)
        self.assertEqual(data, (None, mock_stream, "application/octet-stream"))

        mock_stream.name = "file_name"
        data = ClientRequest._format_data(mock_stream)
        self.assertEqual(data, ("file_name", mock_stream, "application/octet-stream"))

    def test_client_stream_download(self):

        req_response = requests.Response()
        req_response._content = "abc"
        req_response._content_consumed = True
        req_response.status_code = 200

        client_response = RequestsClientResponse(
            None,
            req_response
        )

        def user_callback(chunk, response):
            assert response is req_response
            assert chunk in ["a", "b", "c"]

        sync_iterator = client_response.stream_download(1, user_callback)
        result = ""
        for value in sync_iterator:
            result += value
        assert result == "abc"

    def test_request_builder(self):
        client = ServiceClient(self.creds, self.cfg)

        req = client.get('http://127.0.0.1/')
        assert req.method == 'GET'
        assert req.url == 'http://127.0.0.1/'
        assert req.headers == {'Accept': 'application/json'}
        assert req.data is None
        assert req.files is None

        req = client.put("http://127.0.0.1/", content={'creation': True})
        assert req.method == 'PUT'
        assert req.url == "http://127.0.0.1/"
        assert req.headers == {'Content-Length': '18', 'Accept': 'application/json'}
        assert req.data == '{"creation": true}'
        assert req.files is None


if __name__ == '__main__':
    unittest.main()
