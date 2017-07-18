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

import json
import requests
import datetime
from enum import Enum
import unittest
try:
    from unittest import mock
except ImportError:
    import mock

from msrest.pipeline import (
    ClientRequest,
    ClientRawResponse)

from msrest import Configuration



class TestClientRequest(unittest.TestCase):

    def test_request_headers(self):

        request = ClientRequest()
        request.add_header("a", 1)
        request.add_headers({'b':2, 'c':3})

        self.assertEqual(request.headers, {'a':1, 'b':2, 'c':3})

    def test_request_data(self):

        request = ClientRequest()
        data = "Lots of dataaaa"
        request.add_content(data)

        self.assertEqual(request.data, json.dumps(data))
        self.assertEqual(request.headers.get('Content-Length'), '17')

    def test_request_url_with_params(self):

        request = ClientRequest()
        request.url = "a/b/c?t=y"
        request.format_parameters({'g': 'h'})

        self.assertIn(request.url, [
            'a/b/c?g=h&t=y',
            'a/b/c?t=y&g=h'
        ])

class TestClientResponse(unittest.TestCase):

    class Colors(Enum):
        red = 'red'
        blue = 'blue'

    def test_raw_response(self):

        response = mock.create_autospec(requests.Response)
        response.headers = {}
        response.headers["my-test"] = '1999-12-31T23:59:59-23:59'
        response.headers["colour"] = "red"

        raw = ClientRawResponse([], response)

        raw.add_headers({'my-test': 'iso-8601',
                         'another_header': 'str',
                         'colour': TestClientResponse.Colors})
        self.assertIsInstance(raw.headers['my-test'], datetime.datetime)

if __name__ == '__main__':
    unittest.main()
