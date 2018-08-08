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
import xml.etree.ElementTree as ET
import sys

import pytest

from msrest.universal_http import (
    ClientRequest,
)
from msrest.pipeline import (
    ClientRawResponse,
    SansIOHTTPPolicy,
    Pipeline,
    HTTPSender
)

from msrest import Configuration


def test_sans_io_exception():
    class BrokenSender(HTTPSender):
        def send(self, request, **config):
            raise ValueError("Broken")

        def __exit__(self, exc_type, exc_value, traceback):
            """Raise any exception triggered within the runtime context."""
            return None

    pipeline = Pipeline([SansIOHTTPPolicy()], BrokenSender())

    req = ClientRequest('GET', '/')
    with pytest.raises(ValueError):
        pipeline.run(req)

    class SwapExec(SansIOHTTPPolicy):
        def on_exception(self, requests, **kwargs):
            exc_type, exc_value, exc_traceback = sys.exc_info()
            raise NotImplementedError(exc_value)

    pipeline = Pipeline([SwapExec()], BrokenSender())
    with pytest.raises(NotImplementedError):
        pipeline.run(req)


class TestClientRequest(unittest.TestCase):

    def test_request_data(self):

        request = ClientRequest('GET', '/')
        data = "Lots of dataaaa"
        request.add_content(data)

        self.assertEqual(request.data, json.dumps(data))
        self.assertEqual(request.headers.get('Content-Length'), '17')

    def test_request_xml(self):
        request = ClientRequest('GET', '/')
        data = ET.Element("root")
        request.add_content(data)

        assert request.data == b"<?xml version='1.0' encoding='utf8'?>\n<root />"

    def test_request_url_with_params(self):

        request = ClientRequest('GET', '/')
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
