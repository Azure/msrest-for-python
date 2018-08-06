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
import unittest
try:
    from unittest import mock
except ImportError:
    import mock

import requests

from msrest.serialization import Model, Deserializer
from msrest.exceptions import HttpOperationError


class TestExceptions(unittest.TestCase):

    def test_request_exception(self):
        def raise_for_status():
            raise requests.RequestException()

        deserializer = Deserializer()
        response = mock.create_autospec(requests.Response)
        response.raise_for_status = raise_for_status
        response.reason = "TESTING"

        excep = HttpOperationError(deserializer, response)

        self.assertIn("TESTING", str(excep))
        self.assertIn("Operation returned an invalid status code", str(excep))

    def test_custom_exception(self):

        class ErrorResponse(Model):
            _attribute_map = {
                'error': {'key': 'error', 'type': 'ErrorDetails'},
            }
            def __init__(self, error=None):
                self.error = error


        class ErrorResponseException(HttpOperationError):
            def __init__(self, deserialize, response, *args):
                super(ErrorResponseException, self).__init__(deserialize, response, 'ErrorResponse', *args)

        class ErrorDetails(Model):
            _validation = {
                'code': {'readonly': True},
                'message': {'readonly': True},
                'target': {'readonly': True},
            }

            _attribute_map = {
                'code': {'key': 'code', 'type': 'str'},
                'message': {'key': 'message', 'type': 'str'},
                'target': {'key': 'target', 'type': 'str'},
            }

            def __init__(self):
                self.code = None
                self.message = None
                self.target = None

        deserializer = Deserializer({
            'ErrorResponse': ErrorResponse,
            'ErrorDetails': ErrorDetails
        })

        response = requests.Response()
        response._content_consumed = True
        response._content = json.dumps(
            {
                "error": {
                    "code": "NotOptedIn",
                    "message": "You are not allowed to download invoices. Please contact your account administrator to turn on access in the management portal for allowing to download invoices through the API."
                }
            }
        ).encode('utf-8')
        response.headers = {"content-type": "application/json; charset=utf8"}

        excep = ErrorResponseException(deserializer, response)

        self.assertIn("NotOptedIn", str(excep))
        self.assertIn("You are not allowed to download invoices", str(excep))
