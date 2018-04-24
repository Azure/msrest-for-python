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
import xml.etree.ElementTree as ET

from msrest.serialization import Serializer, Deserializer, Model, xml_key_extractor

def assert_xml_equals(x1, x2):
    print("--------X1--------")
    ET.dump(x1)
    print("--------X2--------")
    ET.dump(x2)

    assert x1.tag == x2.tag
    assert (x1.text or "").strip() == (x2.text or "").strip()
    # assert x1.tail == x2.tail # Swagger does not change tail
    assert x1.attrib == x2.attrib
    assert len(x1) == len(x2)
    for c1, c2 in zip(x1, x2):
        assert_xml_equals(c1, c2)

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
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples', 'wrapped': True, 'itemsName': 'Apple'}},
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
                'apples': {'key': 'Apple', 'type': '[str]', 'xml': {'name': 'apples', 'itemsName': 'Apple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert result.apples == ["granny", "fuji"]

        class Slideshow(Model):
            _attribute_map = {
                'title': {'key': 'title', 'type': 'str', 'xml': {'name': 'title', 'attr': True}},
                'date_property': {'key': 'date', 'type': 'str', 'xml': {'name': 'date', 'attr': True}},
                'author': {'key': 'author', 'type': 'str', 'xml': {'name': 'author', 'attr': True}},
                'slides': {'key': 'slides', 'type': '[Slide]', 'xml': {'name': 'slide'}},
            }
            _xml_map = {
                'name': 'slideshow'
            }

        class Slide(Model):
            _attribute_map = {
                'type': {'key': 'type', 'type': 'str', 'xml': {'name': 'type', 'attr': True}},
                'title': {'key': 'title', 'type': 'str', 'xml': {'name': 'title'}},
                'items': {'key': 'items', 'type': '[str]', 'xml': {'name': 'items', 'itemsName': 'item'}},
            }
            _xml_map = {
                'name': 'slide'
            }

        slideshow_xml = """<?xml version='1.0' encoding='UTF-8'?>
<slideshow
        title="Sample Slide Show"
        date="Date of publication"
        author="Yours Truly">
    <slide type="all">
        <title>Wake up to WonderWidgets!</title>
    </slide>
    <slide type="all">
        <title>Overview</title>
        <item>Why WonderWidgets are great</item>
        <item></item>
        <item>Who buys WonderWidgets</item>
    </slide>
</slideshow>"""

        s = Deserializer({"Slideshow": Slideshow, "Slide": Slide})
        result = s(Slideshow, slideshow_xml, "application/xml")
        assert len(result.slides) == 2
        assert result.slides[1].items[1] is None

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

class TestXmlSerialization:

    def test_basic(self):
        """Test an ultra basic XML."""
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <Data country="france">
                <Age>37</Age>
            </Data>""")

        class XmlModel(Model):
            _attribute_map = {
                'age': {'key': 'age', 'type': 'int', 'xml':{'name': 'Age'}},
                'country': {'key': 'country', 'type': 'str', 'xml':{'name': 'country', 'attr': True}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            age=37,
            country="france"
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel')

        assert_xml_equals(rawxml, basic_xml)

    def test_list_wrapped(self):
        """Test XML list and wrap."""

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <Apple>granny</Apple>
                  <Apple>fuji</Apple>
                </GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples', 'wrapped': True, 'itemsName': 'Apple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        mymodel = AppleBarrel(
            good_apples=['granny', 'fuji']
        )

        s = Serializer({"AppleBarrel": AppleBarrel})
        rawxml = s.body(mymodel, 'AppleBarrel')

        assert_xml_equals(rawxml, basic_xml)

    def test_list_not_wrapped(self):
        """Test XML list and wrap."""

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <Apple>granny</Apple>
                <Apple>fuji</Apple>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'apples': {'key': 'Apple', 'type': '[str]', 'xml': {'name': 'apples', 'itemsName': 'Apple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        mymodel = AppleBarrel(
            apples=['granny', 'fuji']
        )

        s = Serializer({"AppleBarrel": AppleBarrel})
        rawxml = s.body(mymodel, 'AppleBarrel')

        assert_xml_equals(rawxml, basic_xml)

    def test_basic_namespace(self):
        """Test an ultra basic XML."""
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <Data xmlns:fictional="http://characters.example.com">
                <fictional:Age>37</fictional:Age>
            </Data>""")

        class XmlModel(Model):
            _attribute_map = {
                'age': {'key': 'age', 'type': 'int', 'xml':{'name': 'Age', 'prefix':'fictional','ns':'http://characters.example.com'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            age=37,
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel')

        assert_xml_equals(rawxml, basic_xml)

    def test_slideshow(self):
        class Slideshow(Model):
            _attribute_map = {
                'title': {'key': 'title', 'type': 'str', 'xml': {'name': 'title', 'attr': True}},
                'date_property': {'key': 'date', 'type': 'str', 'xml': {'name': 'date', 'attr': True}},
                'author': {'key': 'author', 'type': 'str', 'xml': {'name': 'author', 'attr': True}},
                'slides': {'key': 'slides', 'type': '[Slide]', 'xml': {'name': 'slide'}},
            }
            _xml_map = {
                'name': 'slideshow'
            }

        class Slide(Model):
            _attribute_map = {
                'type': {'key': 'type', 'type': 'str', 'xml': {'name': 'type', 'attr': True}},
                'title': {'key': 'title', 'type': 'str', 'xml': {'name': 'title'}},
                'items': {'key': 'items', 'type': '[str]', 'xml': {'name': 'items', 'itemsName': 'item'}},
            }
            _xml_map = {
                'name': 'slide'
            }

        slideshow_xml = """<?xml version='1.0' encoding='UTF-8'?>
<slideshow
        title="Sample Slide Show"
        date="Date of publication"
        author="Yours Truly">
    <slide type="all">
        <title>Wake up to WonderWidgets!</title>
    </slide>
    <slide type="all">
        <title>Overview</title>
        <item>Why WonderWidgets are great</item>
        <item></item>
        <item>Who buys WonderWidgets</item>
    </slide>
</slideshow>"""

        input_model = Slideshow(
            title="Sample Slide Show",
            date_property="Date of publication",
            author="Yours Truly",
            slides=[
                Slide(
                    type="all",
                    title="Wake up to WonderWidgets!",
                    items=[]
                ),
                Slide(
                    type="all",
                    title="Overview",
                    items=[
                        "Why WonderWidgets are great",
                        None,
                        "Who buys WonderWidgets"
                    ]
                )
            ]
        )

        s = Serializer({"Slideshow": Slideshow, "Slide": Slide})
        rawxml = s.body(input_model, 'Slideshow')
        assert_xml_equals(rawxml, ET.fromstring(slideshow_xml))
        
