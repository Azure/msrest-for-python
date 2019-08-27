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
import sys
import xml.etree.ElementTree as ET

import pytest

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
                <Long>12</Long>
                <EmptyLong/>
                <Age>37</Age>
                <EmptyAge/>
                <EmptyString/>
            </Data>"""

        class XmlModel(Model):
            _attribute_map = {
                'longnode': {'key': 'longnode', 'type': 'long', 'xml':{'name': 'Long'}},
                'empty_long': {'key': 'empty_long', 'type': 'long', 'xml':{'name': 'EmptyLong'}},
                'age': {'key': 'age', 'type': 'int', 'xml':{'name': 'Age'}},
                'empty_age': {'key': 'empty_age', 'type': 'int', 'xml':{'name': 'EmptyAge'}},
                'empty_string': {'key': 'empty_string', 'type': 'str', 'xml':{'name': 'EmptyString'}},
                'not_set': {'key': 'not_set', 'type': 'str', 'xml':{'name': 'NotSet'}},
                'country': {'key': 'country', 'type': 'str', 'xml':{'name': 'country', 'attr': True}},
            }
            _xml_map = {
                'name': 'Data'
            }

        s = Deserializer({"XmlModel": XmlModel})
        result = s(XmlModel, basic_xml, "application/xml")

        assert result.longnode == 12
        assert result.empty_long is None
        assert result.age == 37
        assert result.empty_age is None
        assert result.country == "france"
        assert result.empty_string == ""
        assert result.not_set is None

    def test_basic_unicode(self):
        """Test a XML with unicode."""
        basic_xml = u"""<?xml version="1.0" encoding="utf-8"?>
            <Data language="français"/>"""

        class XmlModel(Model):
            _attribute_map = {
                'language': {'key': 'language', 'type': 'str', 'xml':{'name': 'language', 'attr': True}},
            }
            _xml_map = {
                'name': 'Data'
            }

        s = Deserializer({"XmlModel": XmlModel})
        result = s(XmlModel, basic_xml, "application/xml")

        assert result.language == u"français"

    def test_add_prop(self):
        """Test addProp as a dict.
        """
        basic_xml = """<?xml version="1.0"?>
            <Data>
                <Metadata>
                  <Key1>value1</Key1>
                  <Key2>value2</Key2>
                </Metadata>
            </Data>"""

        class XmlModel(Model):
            _attribute_map = {
                'metadata': {'key': 'Metadata', 'type': '{str}', 'xml': {'name': 'Metadata'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        s = Deserializer({"XmlModel": XmlModel})
        result = s(XmlModel, basic_xml, "application/xml")

        assert len(result.metadata) == 2
        assert result.metadata['Key1'] == "value1"
        assert result.metadata['Key2'] == "value2"

    def test_object(self):
        basic_xml = """<?xml version="1.0"?>
            <Data country="france">
                <Age>37</Age>
            </Data>"""

        s = Deserializer()
        result = s('object', basic_xml, "application/xml")

        # Should be a XML tree
        assert result.tag == "Data"
        assert result.get("country") == "france"
        for child in result:
            assert child.tag == "Age"
            assert child.text == "37"

    def test_object_no_text(self):
        basic_xml = """<?xml version="1.0"?><Data country="france"><Age>37</Age></Data>"""

        s = Deserializer()
        result = s('object', basic_xml, "application/xml")

        # Should be a XML tree
        assert result.tag == "Data"
        assert result.get("country") == "france"
        for child in result:
            assert child.tag == "Age"
            assert child.text == "37"

    def test_basic_empty(self):
        """Test an basic XML with an empty node."""
        basic_xml = """<?xml version="1.0"?>
            <Data>
                <Age/>
            </Data>"""

        class XmlModel(Model):
            _attribute_map = {
                'age': {'key': 'age', 'type': 'str', 'xml':{'name': 'Age'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        s = Deserializer({"XmlModel": XmlModel})
        result = s(XmlModel, basic_xml, "application/xml")

        assert result.age == ""

    def test_basic_empty_list(self):
        """Test an basic XML with an empty node."""
        basic_xml = """<?xml version="1.0"?>
            <Data/>"""

        class XmlModel(Model):
            _attribute_map = {
                'age': {'key': 'age', 'type': 'str', 'xml':{'name': 'Age'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        s = Deserializer({"XmlModel": XmlModel})
        result = s('[XmlModel]', basic_xml, "application/xml")

        assert result == []

    def test_list_wrapped_items_name_basic_types(self):
        """Test XML list and wrap, items is basic type and there is itemsName.
        """

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

    def test_list_not_wrapped_items_name_basic_types(self):
        """Test XML list and no wrap, items is basic type and there is itemsName.
        """

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <Apple>granny</Apple>
                <Apple>fuji</Apple>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples', 'itemsName': 'Apple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert result.good_apples == ["granny", "fuji"]

    def test_list_wrapped_basic_types(self):
        """Test XML list and wrap, items is basic type and there is no itemsName.
        """

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <GoodApples>granny</GoodApples>
                  <GoodApples>fuji</GoodApples>
                </GoodApples>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples', 'wrapped': True}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert result.good_apples == ["granny", "fuji"]

    def test_list_not_wrapped_basic_types(self):
        """Test XML list and no wrap, items is basic type and there is no itemsName.
        """

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>granny</GoodApples>
                <GoodApples>fuji</GoodApples>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert result.good_apples == ["granny", "fuji"]


    def test_list_wrapped_items_name_complex_types(self):
        """Test XML list and wrap, items is ref and there is itemsName.
        """

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <Apple name="granny"/>
                  <Apple name="fuji"/>
                </GoodApples>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'wrapped': True, 'itemsName': 'Apple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Pomme' # Should be ignored, since "itemsName" is defined
            }

        s = Deserializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        result = s('AppleBarrel', basic_xml, "application/xml")

        assert [apple.name for apple in result.good_apples] == ["granny", "fuji"]

    def test_list_not_wrapped_items_name_complex_types(self):
        """Test XML list and wrap, items is ref and there is itemsName.
        """

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <Apple name="granny"/>
                <Apple name="fuji"/>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                # Pomme should be ignored, since it's invalid to define itemsName for a $ref type
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'itemsName': 'Pomme'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert [apple.name for apple in result.good_apples] == ["granny", "fuji"]

    def test_list_wrapped_complex_types(self):
        """Test XML list and wrap, items is ref and there is no itemsName.
        """

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <Apple name="granny"/>
                  <Apple name="fuji"/>
                </GoodApples>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'wrapped': True}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert [apple.name for apple in result.good_apples] == ["granny", "fuji"]

    def test_list_not_wrapped_complex_types(self):
        """Test XML list and wrap, items is ref and there is no itemsName.
        """

        basic_xml = """<?xml version="1.0"?>
            <AppleBarrel>
                <Apple name="granny"/>
                <Apple name="fuji"/>
            </AppleBarrel>"""

        class AppleBarrel(Model):
            _attribute_map = {
                # Name is ignored if wrapped is False
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        s = Deserializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        result = s(AppleBarrel, basic_xml, "application/xml")

        assert [apple.name for apple in result.good_apples] == ["granny", "fuji"]

    def test_basic_additional_properties(self):
        """Test an ultra basic XML."""
        basic_xml = """<?xml version="1.0"?>
            <Metadata>
              <number>1</number>
              <name>bob</name>
            </Metadata>"""

        class XmlModel(Model):

            _attribute_map = {
                'additional_properties': {'key': '', 'type': '{str}', 'xml': {'name': 'additional_properties'}},
                'encrypted': {'key': 'Encrypted', 'type': 'str', 'xml': {'name': 'Encrypted', 'attr': True}},
            }
            _xml_map = {
                'name': 'Metadata'
            }

            def __init__(self, **kwargs):
                super(XmlModel, self).__init__(**kwargs)
                self.additional_properties = kwargs.get('additional_properties', None)
                self.encrypted = kwargs.get('encrypted', None)

        s = Deserializer({"XmlModel": XmlModel})
        result = s(XmlModel, basic_xml, "application/xml")

        assert result.additional_properties == {'name': 'bob', 'number': '1'}
        assert result.encrypted is None

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

    def test_basic_unicode(self):
        """Test a XML with unicode."""
        basic_xml = ET.fromstring(u"""<?xml version="1.0" encoding="utf-8"?>
            <Data language="français"/>""".encode("utf-8"))

        class XmlModel(Model):
            _attribute_map = {
                'language': {'key': 'language', 'type': 'str', 'xml':{'name': 'language', 'attr': True}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            language=u"français"
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel')

        assert_xml_equals(rawxml, basic_xml)

    def test_nested_unicode(self):

        class XmlModel(Model):
            _attribute_map = {
                'message_text': {'key': 'MessageText', 'type': 'str', 'xml': {'name': 'MessageText'}},
            }

            _xml_map = {
                'name': 'Message'
            }

        mymodel_no_unicode = XmlModel(message_text=u'message1')
        s = Serializer({"XmlModel": XmlModel})
        body = s.body(mymodel_no_unicode, 'XmlModel')
        xml_content = ET.tostring(body, encoding="utf8")
        assert xml_content == b"<?xml version='1.0' encoding='utf8'?>\n<Message><MessageText>message1</MessageText></Message>"

        mymodel_with_unicode = XmlModel(message_text=u'message1㚈')
        s = Serializer({"XmlModel": XmlModel})
        body = s.body(mymodel_with_unicode, 'XmlModel')
        xml_content = ET.tostring(body, encoding="utf8")
        assert xml_content == b"<?xml version='1.0' encoding='utf8'?>\n<Message><MessageText>message1\xe3\x9a\x88</MessageText></Message>"

    @pytest.mark.skipif(sys.version_info < (3,6),
                        reason="Dict ordering not guaranted before 3.6, makes this complicated to test.")
    def test_add_prop(self):
        """Test addProp as a dict.
        """
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <Data>
                <Metadata>
                  <Key1>value1</Key1>
                  <Key2>value2</Key2>
                </Metadata>
            </Data>""")

        class XmlModel(Model):
            _attribute_map = {
                'metadata': {'key': 'Metadata', 'type': '{str}', 'xml': {'name': 'Metadata'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            metadata={
                'Key1': 'value1',
                'Key2': 'value2',
            }
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel')

        assert_xml_equals(rawxml, basic_xml)

    def test_object(self):
        """Test serialize object as is.
        """
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <Data country="france">
                <Age>37</Age>
            </Data>""")

        s = Serializer()
        rawxml = s.body(basic_xml, 'object')

        # It should actually be the same object, should not even try to touch it
        assert rawxml is basic_xml

    @pytest.mark.skipif(sys.version_info < (3,6),
                        reason="Unstable before python3.6 for some reasons")
    def test_type_basic(self):
        """Test some types."""
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <Data>
                <Age>37</Age>
                <Enabled>true</Enabled>
            </Data>""")

        class XmlModel(Model):
            _attribute_map = {
                'age': {'key': 'age', 'type': 'int', 'xml':{'name': 'Age'}},
                'enabled': {'key': 'enabled', 'type': 'bool', 'xml':{'name': 'Enabled'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            age=37,
            enabled=True
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel')

        assert_xml_equals(rawxml, basic_xml)

    def test_direct_array(self):
        """Test an ultra basic XML."""
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <bananas>
               <Data country="france"/>
            </bananas>
            """)

        class XmlModel(Model):
            _attribute_map = {
                'country': {'key': 'country', 'type': 'str', 'xml':{'name': 'country', 'attr': True}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            country="france"
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(
            [mymodel],
            '[XmlModel]',
            serialization_ctxt={'xml': {'name': 'bananas', 'wrapped': True}}
        )

        assert_xml_equals(rawxml, basic_xml)

    def test_list_wrapped_basic_types(self):
        """Test XML list and wrap, items is basic type and there is no itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <GoodApples>granny</GoodApples>
                  <GoodApples>fuji</GoodApples>
                </GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples', 'wrapped': True}},
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

    def test_list_not_wrapped_basic_types(self):
        """Test XML list and no wrap, items is basic type and there is no itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>granny</GoodApples>
                <GoodApples>fuji</GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples'}},
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

    def test_list_wrapped_items_name_complex_types(self):
        """Test XML list and wrap, items is ref and there is itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <Apple name="granny"/>
                  <Apple name="fuji"/>
                </GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                # Pomme should be ignored, since it's invalid to define itemsName for a $ref type
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'wrapped': True, 'itemsName': 'Pomme'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        mymodel = AppleBarrel(
            good_apples=[
                Apple(name='granny'),
                Apple(name='fuji')
            ]
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel')

        assert_xml_equals(rawxml, basic_xml)

    def test_list_not_wrapped_items_name_complex_types(self):
        """Test XML list and wrap, items is ref and there is itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <Apple name="granny"/>
                <Apple name="fuji"/>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                # Pomme should be ignored, since it's invalid to define itemsName for a $ref type
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'itemsName': 'Pomme'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        mymodel = AppleBarrel(
            good_apples=[
                Apple(name='granny'),
                Apple(name='fuji')
            ]
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel')

        assert_xml_equals(rawxml, basic_xml)

    def test_list_wrapped_complex_types(self):
        """Test XML list and wrap, items is ref and there is no itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <Apple name="granny"/>
                  <Apple name="fuji"/>
                </GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'wrapped': True}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        mymodel = AppleBarrel(
            good_apples=[
                Apple(name='granny'),
                Apple(name='fuji')
            ]
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel')

        assert_xml_equals(rawxml, basic_xml)

    def test_list_not_wrapped_complex_types(self):
        """Test XML list and wrap, items is ref and there is no itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <Apple name="granny"/>
                <Apple name="fuji"/>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                # Name is ignored if "wrapped" is False
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        mymodel = AppleBarrel(
            good_apples=[
                Apple(name='granny'),
                Apple(name='fuji')
            ]
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel')

        assert_xml_equals(rawxml, basic_xml)

    @pytest.mark.skipif(sys.version_info < (3,6),
                        reason="Unstable before python3.6 for some reasons")
    def test_two_complex_same_type(self):
        """Two different attribute are same type
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <EuropeanApple name="granny"/>
                <USAApple name="fuji"/>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'eu_apple': {'key': 'EuropeanApple', 'type': 'Apple', 'xml': {'name': 'EuropeanApple'}},
                'us_apple': {'key': 'USAApple', 'type': 'Apple', 'xml': {'name': 'USAApple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
            }

        mymodel = AppleBarrel(
            eu_apple=Apple(name='granny'),
            us_apple=Apple(name='fuji'),
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
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

    def test_basic_is_xml(self):
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
            country="france",
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    def test_basic_unicode_is_xml(self):
        """Test a XML with unicode."""
        basic_xml = ET.fromstring(u"""<?xml version="1.0" encoding="utf-8"?>
            <Data language="français"/>""".encode("utf-8"))

        class XmlModel(Model):
            _attribute_map = {
                'language': {'key': 'language', 'type': 'str', 'xml':{'name': 'language', 'attr': True}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            language=u"français"
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)


    @pytest.mark.skipif(sys.version_info < (3,6),
                        reason="Dict ordering not guaranted before 3.6, makes this complicated to test.")
    def test_add_prop_is_xml(self):
        """Test addProp as a dict.
        """
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <Data>
                <Metadata>
                  <Key1>value1</Key1>
                  <Key2>value2</Key2>
                </Metadata>
            </Data>""")

        class XmlModel(Model):
            _attribute_map = {
                'metadata': {'key': 'Metadata', 'type': '{str}', 'xml': {'name': 'Metadata'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            metadata={
                'Key1': 'value1',
                'Key2': 'value2',
            }
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    def test_object_is_xml(self):
        """Test serialize object as is.
        """
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <Data country="france">
                <Age>37</Age>
            </Data>""")

        s = Serializer()
        rawxml = s.body(basic_xml, 'object', is_xml=True)

        # It should actually be the same object, should not even try to touch it
        assert rawxml is basic_xml

    @pytest.mark.skipif(sys.version_info < (3,6),
                        reason="Unstable before python3.6 for some reasons")
    def test_type_basic_is_xml(self):
        """Test some types."""
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <Data>
                <Age>37</Age>
                <Enabled>true</Enabled>
            </Data>""")

        class XmlModel(Model):
            _attribute_map = {
                'age': {'key': 'age', 'type': 'int', 'xml':{'name': 'Age'}},
                'enabled': {'key': 'enabled', 'type': 'bool', 'xml':{'name': 'Enabled'}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            age=37,
            enabled=True
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(mymodel, 'XmlModel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    def test_direct_array_is_xml(self):
        """Test an ultra basic XML."""
        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <bananas>
               <Data country="france"/>
            </bananas>
            """)

        class XmlModel(Model):
            _attribute_map = {
                'country': {'key': 'country', 'type': 'str', 'xml':{'name': 'country', 'attr': True}},
            }
            _xml_map = {
                'name': 'Data'
            }

        mymodel = XmlModel(
            country="france"
        )

        s = Serializer({"XmlModel": XmlModel})
        rawxml = s.body(
            [mymodel],
            '[XmlModel]',
            serialization_ctxt={'xml': {'name': 'bananas', 'wrapped': True}},
            is_xml=True
        )

        assert_xml_equals(rawxml, basic_xml)

    def test_list_wrapped_basic_types_is_xml(self):
        """Test XML list and wrap, items is basic type and there is no itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <GoodApples>granny</GoodApples>
                  <GoodApples>fuji</GoodApples>
                </GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples', 'wrapped': True}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        mymodel = AppleBarrel(
            good_apples=['granny', 'fuji']
        )

        s = Serializer({"AppleBarrel": AppleBarrel})
        rawxml = s.body(mymodel, 'AppleBarrel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    def test_list_not_wrapped_basic_types_is_xml(self):
        """Test XML list and no wrap, items is basic type and there is no itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>granny</GoodApples>
                <GoodApples>fuji</GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[str]', 'xml': {'name': 'GoodApples'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        mymodel = AppleBarrel(
            good_apples=['granny', 'fuji']
        )

        s = Serializer({"AppleBarrel": AppleBarrel})
        rawxml = s.body(mymodel, 'AppleBarrel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    def test_list_wrapped_items_name_complex_types_is_xml(self):
        """Test XML list and wrap, items is ref and there is itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <Apple name="granny"/>
                  <Apple name="fuji"/>
                </GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                # Pomme should be ignored, since it's invalid to define itemsName for a $ref type
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'wrapped': True, 'itemsName': 'Pomme'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        mymodel = AppleBarrel(
            good_apples=[
                Apple(name='granny'),
                Apple(name='fuji')
            ]
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    def test_list_not_wrapped_items_name_complex_types_is_xml(self):
        """Test XML list and wrap, items is ref and there is itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <Apple name="granny"/>
                <Apple name="fuji"/>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                # Pomme should be ignored, since it's invalid to define itemsName for a $ref type
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'itemsName': 'Pomme'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        mymodel = AppleBarrel(
            good_apples=[
                Apple(name='granny'),
                Apple(name='fuji')
            ]
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    def test_list_wrapped_complex_types_is_xml(self):
        """Test XML list and wrap, items is ref and there is no itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <GoodApples>
                  <Apple name="granny"/>
                  <Apple name="fuji"/>
                </GoodApples>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples', 'wrapped': True}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        mymodel = AppleBarrel(
            good_apples=[
                Apple(name='granny'),
                Apple(name='fuji')
            ]
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    def test_list_not_wrapped_complex_types_is_xml(self):
        """Test XML list and wrap, items is ref and there is no itemsName.
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <Apple name="granny"/>
                <Apple name="fuji"/>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                # Name is ignored if "wrapped" is False
                'good_apples': {'key': 'GoodApples', 'type': '[Apple]', 'xml': {'name': 'GoodApples'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
                'name': 'Apple'
            }

        mymodel = AppleBarrel(
            good_apples=[
                Apple(name='granny'),
                Apple(name='fuji')
            ]
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)

    @pytest.mark.skipif(sys.version_info < (3,6),
                        reason="Unstable before python3.6 for some reasons")
    def test_two_complex_same_type_is_xml(self):
        """Two different attribute are same type
        """

        basic_xml = ET.fromstring("""<?xml version="1.0"?>
            <AppleBarrel>
                <EuropeanApple name="granny"/>
                <USAApple name="fuji"/>
            </AppleBarrel>""")

        class AppleBarrel(Model):
            _attribute_map = {
                'eu_apple': {'key': 'EuropeanApple', 'type': 'Apple', 'xml': {'name': 'EuropeanApple'}},
                'us_apple': {'key': 'USAApple', 'type': 'Apple', 'xml': {'name': 'USAApple'}},
            }
            _xml_map = {
                'name': 'AppleBarrel'
            }

        class Apple(Model):
            _attribute_map = {
                'name': {'key': 'name', 'type': 'str', 'xml':{'name': 'name', 'attr': True}},
            }
            _xml_map = {
            }

        mymodel = AppleBarrel(
            eu_apple=Apple(name='granny'),
            us_apple=Apple(name='fuji'),
        )

        s = Serializer({"AppleBarrel": AppleBarrel, "Apple": Apple})
        rawxml = s.body(mymodel, 'AppleBarrel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)


    def test_basic_namespace_is_xml(self):
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
        rawxml = s.body(mymodel, 'XmlModel', is_xml=True)

        assert_xml_equals(rawxml, basic_xml)