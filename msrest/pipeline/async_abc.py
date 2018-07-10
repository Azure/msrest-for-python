# --------------------------------------------------------------------------
#
# Copyright (c) Microsoft Corporation. All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the ""Software""), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
# --------------------------------------------------------------------------
import abc

from typing import Any, List, Union

try:
    from contextlib import AbstractAsyncContextManager  # type: ignore
except ImportError: # Python <= 3.7
    class AbstractAsyncContextManager(object):  # type: ignore
        async def __aenter__(self):
            """Return `self` upon entering the runtime context."""
            return self

        @abc.abstractmethod
        async def __aexit__(self, exc_type, exc_value, traceback):
            """Raise any exception triggered within the runtime context."""
            return None

from . import ClientRequest, ClientResponse, Pipeline, SansIOHTTPPolicy


class AsyncHTTPPolicy(abc.ABC):
    """An http policy ABC.
    """
    def __init__(self) -> None:
        # next will be set once in the pipeline
        self.next: Union[AsyncHTTPPolicy, AsyncHTTPSender] = None  # type: ignore

    @abc.abstractmethod
    async def send(self, request: ClientRequest, **kwargs: Any) -> ClientResponse:
        """Mutate the request.

        Context content is dependent of the HTTPSender.
        """
        pass


class _SansIOAsyncHTTPPolicyRunner(AsyncHTTPPolicy):
    """Async implementation of the SansIO policy.
    """

    def __init__(self, policy: SansIOHTTPPolicy) -> None:
        super(_SansIOAsyncHTTPPolicyRunner, self).__init__()
        self._policy = policy

    async def send(self, request: ClientRequest, **kwargs: Any) -> ClientResponse:
        self._policy.prepare(request, **kwargs)
        response = await self.next.send(request, **kwargs)
        self._policy.post_send(request, response, **kwargs)
        return response


class AsyncHTTPSender(AbstractAsyncContextManager, abc.ABC):
    """An http sender ABC.
    """

    @abc.abstractmethod
    async def send(self, request: ClientRequest, **config: Any) -> ClientResponse:
        """Send the request using this HTTP sender.
        """
        pass

    def build_context(self) -> Any:
        """Allow the sender to build a context that will be passed
        across the pipeline with the request.

        Return type has no constraints. Implementation is not
        required and None by default.
        """
        return None


class AsyncPipeline(AbstractAsyncContextManager):
    """A pipeline implementation.

    This is implemented as a context manager, that will activate the context
    of the HTTP sender.
    """

    def __init__(self, policies: List[Union[AsyncHTTPPolicy, SansIOHTTPPolicy]], sender: AsyncHTTPSender) -> None:
        self._impl_policies: List[AsyncHTTPPolicy] = []
        self._sender = sender
        for policy in policies:
            if isinstance(policy, SansIOHTTPPolicy):
                self._impl_policies.append(_SansIOAsyncHTTPPolicyRunner(policy))
            else:
                self._impl_policies.append(policy)
        for index in range(len(self._impl_policies)-1):
            self._impl_policies[index].next = self._impl_policies[index+1]
        if self._impl_policies:
            self._impl_policies[-1].next = self._sender

    async def __aenter__(self) -> 'AsyncPipeline':
        await self._sender.__aenter__()
        return self

    async def __exit__(self, *exc_details):  # pylint: disable=arguments-differ
        await self._sender.__aexit__(*exc_details)

    async def run(self, request: ClientRequest, **kwargs: Any) -> ClientResponse:
        context = self._sender.build_context()
        request.pipeline_context = context
        first_node = self._impl_policies[0] if self._impl_policies else self._sender
        return await first_node.send(request, **kwargs)  # type: ignore

__all__ = [
    'AsyncHTTPPolicy',
    'AsyncHTTPSender',
    'AsyncPipeline'
]