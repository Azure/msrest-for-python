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

import os
import sys
import json
import isodate
from datetime import datetime
import base64
from base64 import b64decode
import unittest
try:
    from unittest import mock
except ImportError:
    import mock

from msrest.authentication import (
    BasicAuthentication,
    BasicTokenAuthentication,
    OAuthTokenAuthentication,
    ApiKeyCredentials,
    CognitiveServicesCredentials,
    TopicCredentials,
    DomainCredentials
)

from requests import Request, PreparedRequest


class TestAuthentication(unittest.TestCase):

    def setUp(self):

        self.request = mock.create_autospec(Request)
        self.request.headers = {}
        self.request.cookies = {}
        self.request.auth = None
        self.request.url = "http://my_endpoint.com"
        self.request.method = 'GET'
        self.request.files = None
        self.request.data = None
        self.request.json = None
        self.request.params = {}
        self.request.hooks = {}

        return super(TestAuthentication, self).setUp()

    def test_basic_auth(self):

        basic = BasicAuthentication("username", "password")
        session = basic.signed_session()

        req = session.auth(self.request)
        self.assertTrue('Authorization' in req.headers)
        self.assertTrue(req.headers['Authorization'].startswith('Basic '))

    def test_basic_token_auth(self):

        token = {
            'access_token': '123456789'
        }
        basic = BasicTokenAuthentication(token)
        basic.set_token() # Just check that this does not raise
        session = basic.signed_session()

        req = session.prepare_request(self.request)
        assert 'Authorization' in req.headers
        assert req.headers['Authorization'] == 'Bearer 123456789'

    def test_token_auth(self):

        token = {
            'access_token': '123456789'
        }
        auth = OAuthTokenAuthentication("client_id", token)
        session = auth.signed_session()

        request = PreparedRequest()
        request.prepare("GET", "https://example.org")
        session.auth(request)
        assert request.headers == {'Authorization': 'Bearer 123456789'}

    def test_apikey_auth(self):
        auth = ApiKeyCredentials(
            in_headers={
                'testheader' : 'testheadervalue'
            }
        )
        session = auth.signed_session()
        prep_req = session.prepare_request(self.request)
        self.assertDictContainsSubset({'testheader' : 'testheadervalue'}, prep_req.headers)

        auth = ApiKeyCredentials(
            in_query={
                'testquery' : 'testparamvalue'
            }
        )
        session = auth.signed_session()
        prep_req = session.prepare_request(self.request)
        assert "testquery=testparamvalue" in prep_req.path_url

    def test_cs_auth(self):
        auth = CognitiveServicesCredentials("mysubkey")
        session = auth.signed_session()
        prep_req = session.prepare_request(self.request)
        self.assertDictContainsSubset({'Ocp-Apim-Subscription-Key' : 'mysubkey'}, prep_req.headers)

    def test_eventgrid_auth(self):
        auth = TopicCredentials("mytopickey")
        session = auth.signed_session()
        prep_req = session.prepare_request(self.request)
        self.assertDictContainsSubset({'aeg-sas-key' : 'mytopickey'}, prep_req.headers)

    def test_eventgrid_domain_auth(self):
        auth = DomainCredentials("mydomainkey")
        session = auth.signed_session()
        prep_req = session.prepare_request(self.request)
        self.assertDictContainsSubset({'aeg-sas-key' : 'mydomainkey'}, prep_req.headers)

if __name__ == '__main__':
    unittest.main()

