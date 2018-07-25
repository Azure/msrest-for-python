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
import concurrent.futures

from msrest.pipeline.requests import (
    BasicRequestsHTTPSender,
    RequestsHTTPSender,
    RequestHTTPSenderConfiguration
)


def test_threading_basic_requests():
    # Basic should have the session for all threads, it's why it's not recommended
    sender = BasicRequestsHTTPSender()

    # Build context will give me the session from the main thread
    main_thread_context = sender.build_context()

    def thread_body(local_sender):
        thread_context = local_sender.build_context()
        # Should be the same session
        assert thread_context.session is main_thread_context.session

        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(thread_body, sender)
        assert future.result()

def test_threading_cfg_requests():
    cfg = RequestHTTPSenderConfiguration()

    # The one with conf however, should have one session per thread automatically
    sender = RequestsHTTPSender(cfg)

    # Build context will give me the session from the main thread
    main_thread_context = sender.build_context()
    # Check that this main session is patched
    assert main_thread_context.session.resolve_redirects.is_msrest_patched

    def thread_body(local_sender):
        thread_context = local_sender.build_context()
        # Should have it's own session
        assert thread_context.session is not main_thread_context.session
        # But should be patched as the main thread session
        assert thread_context.session.resolve_redirects.is_msrest_patched
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(thread_body, sender)
        assert future.result()
