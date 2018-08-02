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
import sys
import unittest
import pytest

from msrest.paging import Paged

class FakePaged(Paged):
    _attribute_map = {
        'next_link': {'key': 'nextLink', 'type': 'str'},
        'current_page': {'key': 'value', 'type': '[str]'}
    }

    def __init__(self, *args, **kwargs):
        super(FakePaged, self).__init__(*args, **kwargs)

class TestPaging(object):

    @pytest.mark.asyncio
    async def test_basic_paging(self):

        async def internal_paging(next_link=None, raw=False):
            if not next_link:
                return {
                    'nextLink': 'page2',
                    'value': ['value1.0', 'value1.1']
                }
            else:
                return {
                    'nextLink': None,
                    'value': ['value2.0', 'value2.1']
                }

        deserialized = FakePaged(None, {}, async_command=internal_paging)

        # 3.6 only : result_iterated = [obj async for obj in deserialized]
        result_iterated = []
        async for obj in deserialized:
            result_iterated.append(obj)

        assert ['value1.0', 'value1.1', 'value2.0', 'value2.1'] == result_iterated

    @pytest.mark.asyncio
    async def test_advance_paging(self):

        async def internal_paging(next_link=None, raw=False):
            if not next_link:
                return {
                    'nextLink': 'page2',
                    'value': ['value1.0', 'value1.1']
                }
            else:
                return {
                    'nextLink': None,
                    'value': ['value2.0', 'value2.1']
                }

        deserialized = FakePaged(None, {}, async_command=internal_paging)
        page1 = await deserialized.async_advance_page()
        assert ['value1.0', 'value1.1'] == page1

        page2 = await deserialized.async_advance_page()
        assert ['value2.0', 'value2.1'] == page2

        with pytest.raises(StopAsyncIteration):
            await deserialized.async_advance_page()

    @pytest.mark.asyncio
    async def test_get_paging(self):

        async def internal_paging(next_link=None, raw=False):
            if not next_link:
                return {
                    'nextLink': 'page2',
                    'value': ['value1.0', 'value1.1']
                }
            elif next_link == 'page2':
                return {
                    'nextLink': 'page3',
                    'value': ['value2.0', 'value2.1']
                }
            else:
                return {
                    'nextLink': None,
                    'value': ['value3.0', 'value3.1']
                }

        deserialized = FakePaged(None, {}, async_command=internal_paging)
        page2 = await deserialized.async_get('page2')
        assert ['value2.0', 'value2.1'] == page2

        page3 = await deserialized.async_get('page3')
        assert ['value3.0', 'value3.1'] == page3

    @pytest.mark.asyncio
    async def test_reset_paging(self):

        async def internal_paging(next_link=None, raw=False):
            if not next_link:
                return {
                    'nextLink': 'page2',
                    'value': ['value1.0', 'value1.1']
                }
            else:
                return {
                    'nextLink': None,
                    'value': ['value2.0', 'value2.1']
                }

        deserialized = FakePaged(None, {}, async_command=internal_paging)
        deserialized.reset()

        # 3.6 only : result_iterated = [obj async for obj in deserialized]
        result_iterated = []
        async for obj in deserialized:
            result_iterated.append(obj)

        assert ['value1.0', 'value1.1', 'value2.0', 'value2.1'] == result_iterated

        deserialized = FakePaged(None, {}, async_command=internal_paging)
        # Push the iterator to the last element
        async for element in deserialized:
            if element == "value2.0":
                break
        deserialized.reset()

        # 3.6 only : result_iterated = [obj async for obj in deserialized]
        result_iterated = []
        async for obj in deserialized:
            result_iterated.append(obj)

        assert ['value1.0', 'value1.1', 'value2.0', 'value2.1'] == result_iterated

    @pytest.mark.asyncio
    async def test_none_value(self):
        async def internal_paging(next_link=None, raw=False):
            return {
                'nextLink': None,
                'value': None
            }

        deserialized = FakePaged(None, {}, async_command=internal_paging)

        # 3.6 only : result_iterated = [obj async for obj in deserialized]
        result_iterated = []
        async for obj in deserialized:
            result_iterated.append(obj)

        assert len(result_iterated) == 0
