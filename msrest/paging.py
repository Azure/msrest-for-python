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
try:
    from collections.abc import Iterator
    xrange = range
except ImportError:
    from collections import Iterator

from .serialization import Deserializer
from .pipeline import ClientRawResponse


class Paged(Iterator):
    """A container for paged REST responses.

    :param requests.Response response: server response object.
    :param callable command: Function to retrieve the next page of items.
    :param dict classes: A dictionary of class dependencies for
     deserialization.
    """
    _validation = {}
    _attribute_map = {}

    def __init__(self, command, classes, raw_headers=None):
        # Sets next_link, current_page, and _current_page_iter_index.
        self.reset()
        self._derserializer = Deserializer(classes)
        self._get_next = command
        self._response = None
        self._raw_headers = raw_headers

    def __iter__(self):
        """Return 'self'."""
        # Since iteration mutates this object, consider it an iterator in-and-of
        # itself.
        return self

    @classmethod
    def _get_subtype_map(cls):
        """Required for parity to Model object for deserialization."""
        return {}

    @property
    def raw(self):
        raw = ClientRawResponse(self.current_page, self._response)
        if self._raw_headers:
            raw.add_headers(self._raw_headers)
        return raw

    def get(self, url):
        """Get an arbitrary page.

        This resets the iterator and then fully consumes it to return the
        specific page **only**.

        :param str url: URL to arbitrary page results.
        """
        self.reset()
        self.next_link = url
        return self.advance_page()

    def reset(self):
        """Reset iterator to first page."""
        self.next_link = ""
        self.current_page = []
        self._current_page_iter_index = 0

    def advance_page(self):
        if self.next_link is None:
            raise StopIteration("End of paging")
        self._current_page_iter_index = 0
        self._response = self._get_next(self.next_link)
        self._derserializer(self, self._response)
        return self.current_page

    def __next__(self):
        """Iterate through responses."""
        # Storing the list iterator might work out better, but there's no
        # guarantee that some code won't replace the list entirely with a copy,
        # invalidating an list iterator that might be saved between iterations.
        if self.current_page and self._current_page_iter_index < len(self.current_page):
            response = self.current_page[self._current_page_iter_index]
            self._current_page_iter_index += 1
            return response
        else:
            self.advance_page()
            return self.__next__()

    next = __next__  # Python 2 compatibility.
