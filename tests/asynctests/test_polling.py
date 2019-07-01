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
import asyncio
try:
    from unittest import mock
except ImportError:
    import mock

import pytest

from msrest.polling.async_poller import *
from msrest.async_client import ServiceClientAsync
from msrest.serialization import Model
from msrest.configuration import Configuration


@pytest.mark.asyncio
async def test_abc_polling():
    abc_polling = AsyncPollingMethod()

    with pytest.raises(NotImplementedError):
        abc_polling.initialize(None, None, None)

    with pytest.raises(NotImplementedError):
        await abc_polling.run()

    with pytest.raises(NotImplementedError):
        abc_polling.status()

    with pytest.raises(NotImplementedError):
        abc_polling.finished()

    with pytest.raises(NotImplementedError):
        abc_polling.resource()


@pytest.mark.asyncio
async def test_no_polling():
    no_polling = AsyncNoPolling()

    initial_response = "initial response"
    def deserialization_cb(response):
        assert response == initial_response
        return "Treated: "+response

    no_polling.initialize(None, initial_response, deserialization_cb)
    await no_polling.run() # Should no raise and do nothing
    assert no_polling.status() == "succeeded"
    assert no_polling.finished()
    assert no_polling.resource() == "Treated: "+initial_response


class PollingTwoSteps(AsyncPollingMethod):
    """An empty poller that returns the deserialized initial response.
    """
    def __init__(self, sleep=0):
        self._initial_response = None
        self._deserialization_callback = None
        self._sleep = sleep

    def initialize(self, _, initial_response, deserialization_callback):
        self._initial_response = initial_response
        self._deserialization_callback = deserialization_callback
        self._finished = False

    async def run(self):
        """Empty run, no polling.
        """
        self._finished = True
        await asyncio.sleep(self._sleep) # Give me time to add callbacks!

    def status(self):
        """Return the current status as a string.
        :rtype: str
        """
        return "succeeded" if self._finished else "running"

    def finished(self):
        """Is this polling finished?
        :rtype: bool
        """
        return self._finished

    def resource(self):
        return self._deserialization_callback(self._initial_response)

@pytest.fixture
def client():
    # We need a ServiceClientAsync instance, but the poller itself don't use it, so we don't need
    # Something functional
    return ServiceClientAsync(Configuration("http://example.org"))

@pytest.mark.asyncio
async def test_poller(client):

    # Same the poller itself doesn't care about the initial_response, and there is no type constraint here
    initial_response = "Initial response"

    # Same for deserialization_callback, just pass to the polling_method
    def deserialization_callback(response):
        assert response == initial_response
        return "Treated: "+response

    method = AsyncNoPolling()

    result = await async_poller(client, initial_response, deserialization_callback, method)
    assert result == "Treated: "+initial_response

    # Test with a basic Model
    class MockedModel(Model):
        called = False
        @classmethod
        def deserialize(cls, data):
            assert data == initial_response
            cls.called = True

    result = await async_poller(client, initial_response, MockedModel, method)
    assert MockedModel.called

    # Test poller that method do a run
    method = PollingTwoSteps(sleep=2)
    result = await async_poller(client, initial_response, deserialization_callback, method)

    assert result == "Treated: "+initial_response

@pytest.mark.asyncio
async def test_broken_poller(client):

    with pytest.raises(ValueError):
        await async_poller(None, None, None, None)

    class NoPollingError(PollingTwoSteps):
        async def run(self):
            raise ValueError("Something bad happened")

    initial_response = "Initial response"
    def deserialization_callback(response):
        return "Treated: "+response

    method = NoPollingError()

    with pytest.raises(ValueError) as excinfo:
        await async_poller(client, initial_response, deserialization_callback, method)
    assert "Something bad happened" in str(excinfo.value)
