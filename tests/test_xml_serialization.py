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

from msrest.serialization import Serializer, Deserializer, Model, xml_key_extractor

class TestXmlDeserialization:

    def test_basic(self):
        """Test an ultra basic XML."""
        basic_xml = """<?xml version="1.0"?>
            <Data country="france">
                <Age>37</Age>
            </Data>"""

        class XmlModel(Model):
            _attribute_map = {
                'age': {'key': 'age', 'type': 'int', 'xml':{'name': 'Age'}},
                'country': {'key': 'country', 'type': 'str', 'xml':{'name': 'country', 'attr': True}},
            }
            _xml_map = {
                'name': 'Data'
            }

        s = Deserializer({"XmlModel": XmlModel})
        result = s(XmlModel, basic_xml, "application/xml")
            
        assert result.age == 37
        assert result.country == "france"

    def test_list_wrapped(self):
        """Test XML list and wrap."""

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <Apple>granny</Apple>
                  <Apple>fuji</Apple>
                </GoodApples>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples', 'wrapped': True, 'wrappedName': 'Apple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert result.good_apples == ["granny", "fuji"]

    def test_list_not_wrapped(self):
        """Test XML list and wrap."""

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <UnrelatedNode>17</UnrelatedNode>
                <Apple>granny</Apple>
                <Apple>fuji</Apple>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                'apples': {'key': 'Apple', 'type': '[str]', 'xml': {'name': 'Apple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert result.apples == ["granny", "fuji"]

    def test_basic_namespace(self):
        """Test an ultra basic XML."""
        basic_xml = """<?xml version="1.0"?>
            <Data xmlns:fictional="http://characters.example.com">
                <fictional:Age>37</fictional:Age>
            </Data>"""

        class XmlModel(Model):
            _attribute_map = {
                'age': {'key': 'age', 'type': 'int', 'xml':{'name': 'Age', 'prefix':'fictional','ns':'http://characters.example.com'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        s = Deserializer({"XmlModel": XmlModel})
        result = s(XmlModel, basic_xml, "application/xml")
            
        assert result.age == 37
