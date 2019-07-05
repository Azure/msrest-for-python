# -*- coding: utf-8 -*-
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
try:
    from unittest import mock
except ImportError:
    import mock

import requests

import pytest

from msrest.exceptions import DeserializationError
from msrest.universal_http import (
    ClientRequest,
    ClientResponse,
    HTTPClientResponse,
)
from msrest.universal_http.requests import RequestsClientResponse

from msrest.pipeline import (
    Response,
    Request
)
from msrest.pipeline.universal import (
    HTTPLogger,
    RawDeserializer,
    UserAgentPolicy
)

def test_user_agent():

    with mock.patch.dict('os.environ', {'AZURE_HTTP_USER_AGENT': "mytools"}):
        policy = UserAgentPolicy()
        assert policy.user_agent.endswith("mytools")

        request = ClientRequest('GET', 'http://127.0.0.1/')
        policy.on_request(Request(request))
        assert request.headers["user-agent"].endswith("mytools")

@mock.patch('msrest.http_logger._LOGGER')
def test_no_log(mock_http_logger):
    universal_request = ClientRequest('GET', 'http://127.0.0.1/')
    request = Request(universal_request)
    http_logger = HTTPLogger()
    response = Response(request, ClientResponse(universal_request, None))

    # By default, no log handler for HTTP
    http_logger.on_request(request)
    mock_http_logger.debug.assert_not_called()
    http_logger.on_response(request, response)
    mock_http_logger.debug.assert_not_called()
    mock_http_logger.reset_mock()

    # I can enable it per request
    http_logger.on_request(request, **{"enable_http_logger": True})
    assert mock_http_logger.debug.call_count >= 1
    http_logger.on_response(request, response, **{"enable_http_logger": True})
    assert mock_http_logger.debug.call_count >= 1
    mock_http_logger.reset_mock()

    # I can enable it per request (bool value should be honored)
    http_logger.on_request(request, **{"enable_http_logger": False})
    mock_http_logger.debug.assert_not_called()
    http_logger.on_response(request, response, **{"enable_http_logger": False})
    mock_http_logger.debug.assert_not_called()
    mock_http_logger.reset_mock()

    # I can enable it globally
    http_logger.enable_http_logger = True
    http_logger.on_request(request)
    assert mock_http_logger.debug.call_count >= 1
    http_logger.on_response(request, response)
    assert mock_http_logger.debug.call_count >= 1
    mock_http_logger.reset_mock()

    # I can enable it globally and override it locally
    http_logger.enable_http_logger = True
    http_logger.on_request(request, **{"enable_http_logger": False})
    mock_http_logger.debug.assert_not_called()
    http_logger.on_response(request, response, **{"enable_http_logger": False})
    mock_http_logger.debug.assert_not_called()
    mock_http_logger.reset_mock()


def test_raw_deserializer():
    raw_deserializer = RawDeserializer()

    def build_response(body, content_type=None):
        class MockResponse(HTTPClientResponse):
            def __init__(self, body, content_type):
                super(MockResponse, self).__init__(None, None)
                self._body = body
                if content_type:
                    self.headers['content-type'] = content_type

            def body(self):
                return self._body
        return Response(None, MockResponse(body, content_type))

    # I deserialize XML
    response = build_response(b"<groot/>", content_type="application/xml")
    raw_deserializer.on_response(None, response, stream=False)
    result = response.context["deserialized_data"]
    assert result.tag == "groot"

    # The basic deserializer works with unicode XML
    result = raw_deserializer.deserialize_from_text(u'<groot language="français"/>', content_type="application/xml")
    assert result.attrib["language"] == u"français"

    # Catch some weird situation where content_type is XML, but content is JSON
    response = build_response(b'{"ugly": true}', content_type="application/xml")
    raw_deserializer.on_response(None, response, stream=False)
    result = response.context["deserialized_data"]
    assert result["ugly"] is True

    # Be sure I catch the correct exception if it's neither XML nor JSON
    with pytest.raises(DeserializationError):
        response = build_response(b'gibberish', content_type="application/xml")
        raw_deserializer.on_response(None, response, stream=False)
    with pytest.raises(DeserializationError):
        response = build_response(b'{{gibberish}}', content_type="application/xml")
        raw_deserializer.on_response(None, response, stream=False)

    # Simple JSON
    response = build_response(b'{"success": true}', content_type="application/json")
    raw_deserializer.on_response(None, response, stream=False)
    result = response.context["deserialized_data"]
    assert result["success"] is True

    # Simple JSON with complex content_type
    response = build_response(b'{"success": true}', content_type="application/vnd.microsoft.appconfig.kv+json")
    raw_deserializer.on_response(None, response, stream=False)
    result = response.context["deserialized_data"]
    assert result["success"] is True

    # JSON with UTF-8 BOM
    response = build_response(b'\xef\xbb\xbf{"success": true}', content_type="application/json; charset=utf-8")
    raw_deserializer.on_response(None, response, stream=False)
    result = response.context["deserialized_data"]
    assert result["success"] is True

    # For compat, if no content-type, decode JSON
    response = build_response(b'"data"')
    raw_deserializer.on_response(None, response, stream=False)
    result = response.context["deserialized_data"]
    assert result == "data"

    # Try with a mock of requests

    req_response = requests.Response()
    req_response.headers["content-type"] = "application/json"
    req_response._content = b'{"success": true}'
    req_response._content_consumed = True
    response = Response(None, RequestsClientResponse(None, req_response))

    raw_deserializer.on_response(None, response, stream=False)
    result = response.context["deserialized_data"]
    assert result["success"] is True
