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

import unittest

from msrest.paging import Paged

class FakePaged(Paged):
    _attribute_map = {
        'next_link': {'key': 'nextLink', 'type': 'str'},
        'current_page': {'key': 'value', 'type': '[str]'}
    }

    def __init__(self, *args, **kwargs):
        super(FakePaged, self).__init__(*args, **kwargs)

class TestPaging(unittest.TestCase):

    def test_basic_paging(self):

        def internal_paging(next_link=None, raw=False):
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

        deserialized = FakePaged(internal_paging, {})
        result_iterated = list(deserialized)
        self.assertListEqual(
            ['value1.0', 'value1.1', 'value2.0', 'value2.1'],
            result_iterated
        )

    def test_advance_paging(self):

        def internal_paging(next_link=None, raw=False):
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

        deserialized = FakePaged(internal_paging, {})
        page1 = deserialized.advance_page()
        self.assertListEqual(
            ['value1.0', 'value1.1'],
            page1
        )
        page2 = deserialized.advance_page()
        self.assertListEqual(
            ['value2.0', 'value2.1'],
            page2
        )
        with self.assertRaises(StopIteration):
            deserialized.advance_page()

    def test_get_paging(self):

        def internal_paging(next_link=None, raw=False):
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

        deserialized = FakePaged(internal_paging, {})
        page2 = deserialized.get('page2')
        self.assertListEqual(
            ['value2.0', 'value2.1'],
            page2
        )
        page3 = deserialized.get('page3')
        self.assertListEqual(
            ['value3.0', 'value3.1'],
            page3
        )

    def test_reset_paging(self):

        def internal_paging(next_link=None, raw=False):
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

        deserialized = FakePaged(internal_paging, {})
        deserialized.reset()
        result_iterated = list(deserialized)
        self.assertListEqual(
            ['value1.0', 'value1.1', 'value2.0', 'value2.1'],
            result_iterated
        )

        deserialized = FakePaged(internal_paging, {})
        # Push the iterator to the last element
        for element in deserialized:
            if element == "value2.0":
                break
        deserialized.reset()
        result_iterated = list(deserialized)
        self.assertListEqual(
            ['value1.0', 'value1.1', 'value2.0', 'value2.1'],
            result_iterated
        )

    def test_none_value(self):
        def internal_paging(next_link=None, raw=False):
            return {
                'nextLink': None,
                'value': None
            }

        deserialized = FakePaged(internal_paging, {})
        result_iterated = list(deserialized)
        self.assertEqual(len(result_iterated), 0)
