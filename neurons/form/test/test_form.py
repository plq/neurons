#!/usr/bin/env python
# encoding: utf8
#
# This file is part of the Neurons project.
# Copyright (c), Burak Arslan <burak.arslan@arskom.com.tr>,
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the {organization} nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import absolute_import, print_function

import logging
logging.basicConfig(level=logging.DEBUG)

import re
import unittest

from decimal import Decimal as D
from datetime import date, time, datetime

from lxml import etree, html

from spyne import Application, NullServer, Unicode, ServiceBase, rpc, Decimal, \
    Boolean, Date, Time, DateTime, Integer, ComplexModel, Array, Double, \
    Mandatory as M, AnyHtml, AnyXml
from spyne.util.test import show

from neurons.form import HtmlForm, PasswordWidget, Tab, HrefWidget, \
    ComboBoxWidget, ComplexHrefWidget
from neurons.form.test import strip_ns
from neurons.form.const import T_TEST
from neurons.form.form import Fieldset


def _test_type(cls, inst):
    # silence bogus warnings
    from spyne.util import appreg; appreg.applications.clear()

    class SomeService(ServiceBase):
        @rpc(_returns=cls, _body_style='bare')
        def some_call(ctx):
            return inst

    prot = HtmlForm(cloth=T_TEST)
    app = Application([SomeService], 'some_ns', out_protocol=prot)

    null = NullServer(app, ostr=True)

    ret = ''.join(null.service.some_call())
    try:
        elt = html.fromstring(ret)
    except:
        print(ret)
        raise

    show(elt, stdout=False)
    elt = elt.xpath('//form')[0]  # get the form tag inside the body tag
    elt = strip_ns(elt)  # get rid of namespaces to simplify xpaths in tests

    print(etree.tostring(elt, pretty_print=True))

    return elt


def _test_type_no_root_cloth(cls, inst):
    from spyne.util import appreg; appreg.applications.clear()

    class SomeService(ServiceBase):
        @rpc(_returns=cls, _body_style='bare')
        def some_call(ctx):
            return inst

    prot = HtmlForm()
    app = Application([SomeService], 'some_ns', out_protocol=prot)

    null = NullServer(app, ostr=True)
    elt = etree.fromstring(''.join(null.service.some_call()))
    show(elt)

    return elt


class TestFormPrimitive(unittest.TestCase):
    def test_unicode(self):
        v = 'foo'
        elt = _test_type(Unicode(100, type_name="tn"), v).xpath('div/input')[0]
        assert elt.attrib['type'] == 'text'
        assert elt.attrib['value'] == v

    def test_unicode_boundless(self):
        v = 'foo'
        elt = _test_type(Unicode, v).xpath('div/textarea')[0]
        assert elt.tag == 'textarea'
        assert elt.text == v

    def test_unicode_null(self):
        v = None
        elt = _test_type(Unicode(100, type_name="tn"), v).xpath('div/input')[0]
        assert elt.attrib['type'] == 'text'
        assert not ('value' in elt.attrib)

    def test_unicode_values(self):
        v = 'a'
        cls = Unicode(100, type_name="tn", values=list('abcd'))
        assert not cls.get_type_name() is Unicode.Empty
        elt = _test_type(cls, v).xpath('div/select')[0]
        assert elt.tag == 'select'
        assert elt.xpath("option/@value") == [''] + list('abcd')
        assert elt.xpath("option[@selected]/text()") == [v]

    def test_integer_values(self):
        v = 3
        cls = Integer(type_name="tn", values=list(range(5)))
        assert not cls.get_type_name() is Unicode.Empty
        elt = _test_type(cls, v).xpath('div/select')[0]
        assert elt.tag == 'select'
        assert elt.xpath("option/@value") == ['']+[str(vvv) for vvv in range(5)]
        assert elt.xpath("option[@selected]/text()") == [str(v)]

    def test_integer_values_mandatory_field(self):
        v = 3
        cls = M(Integer(type_name="tn", values=list(range(5))))
        assert not cls.get_type_name() is Unicode.Empty
        elt = _test_type(cls, v).xpath('div/select')[0]
        assert elt.tag == 'select'
        assert elt.xpath("option/@value") == [str(vvv) for vvv in range(5)]
        assert elt.xpath("option[@selected]/text()") == [str(v)]

    def test_unicode_password(self):
        elt = _test_type(Unicode(64, prot=PasswordWidget()), None)
        elt = elt.xpath('div/input')[0]
        assert elt.attrib['type'] == 'password'

    def test_decimal(self):
        elt = _test_type(Decimal, D('0.1')).xpath('div/input')[0]
        assert elt.attrib['type'] == 'number'
        assert elt.attrib['step'] == 'any'

    # FIXME: enable this after fixing the relevant Spyne bug
    def _test_decimal_step(self):
        elt = _test_type(Decimal(fraction_digits=4), D('0.1')).xpath('div/input')[0]
        assert elt.attrib['step'] == '0.0001'

    def test_boolean_true(self):
        elt = _test_type(Boolean, True).xpath('div/input')[0]
        assert 'checked' in elt.attrib

    def test_boolean_false(self):
        elt = _test_type(Boolean, False).xpath('div/input')[0]
        assert not ('checked' in elt.attrib)

    def test_date(self):
        elt = _test_type(Date, date(2013, 12, 11)).xpath('div/input')[0]
        assert elt.attrib['value'] == '2013-12-11'
        # FIXME: Need to find a way to test the generated js

    def test_time(self):
        elt = _test_type(Time, time(10, 9, 8)).xpath('div/input')[0]
        assert elt.attrib['value'] == '10:09:08'
        # FIXME: Need to find a way to test the generated js

    def test_datetime(self):
        v = datetime(2013, 12, 11, 10, 9, 8)
        script = _test_type(DateTime, v).xpath('div/script/text()')[0]
        assert v.isoformat() in script
        # FIXME: Need to find a better way to test the generated js

    def test_datetime_format_split(self):
        ret = HtmlForm._split_datetime_format('%Y-%m-%d %H:%M:%S')
        assert ret == ('yy-mm-dd', 'HH:mm:ss')

        ret = HtmlForm._split_datetime_format('%Y-%m-%d %H:%M')
        assert ret == ('yy-mm-dd', 'HH:mm')

        ret = HtmlForm._split_datetime_format('%Y-%m-%d')
        assert ret == ('yy-mm-dd', '')

        ret = HtmlForm._split_datetime_format('%H:%M:%S')
        assert ret == ('', 'HH:mm:ss')

    def test_integer(self):
        v = 42
        elt = _test_type(Integer, v).xpath('div/input')[0]
        assert elt.attrib['value'] == str(v)

    def test_integer_none(self):
        v = None
        elt = _test_type(Integer, v).xpath('div/input')[0]
        assert not 'value' in elt.attrib

    def test_hidden_input(self):
        v = 5
        elt = _test_type(Integer(hidden=True), v).xpath('input')[0]

        assert elt.attrib['type'] == "hidden"
        assert elt.attrib['value'] == str(v)

    def test_hidden_input_pa(self):
        v = "punk"
        elt = _test_type(Unicode(pa={HtmlForm:dict(hidden=True)}), v) \
                                                              .xpath('input')[0]
        assert elt.attrib['type'] == "hidden"
        assert elt.attrib['value'] == v

    def test_hidden_input_none(self):
        v = None
        elt = _test_type(Integer(hidden=True), v).xpath('input')[0]

        assert elt.attrib['type'] == "hidden"
        assert not 'value' in elt.attrib

    def test_html(self):
        v = "<html><head></head><body><p>test</p></body></html>"
        elt = _test_type(AnyHtml, v).xpath('div/textarea')[0]

        assert elt.text == str(v)

    def test_xml(self):
        v = "<html><head/><body><p>test</p></body></html>"
        elt = _test_type(AnyXml, v).xpath('div/textarea')[0]

        assert elt.text == str(v)


class TestFormComplex(unittest.TestCase):
    # all complex objects serialize to forms with fieldsets. that's why we
    # always run xpaths on elt[0] i.e. inside the fieldset where the data we're
    # after is, instead of running longer xpath queries.

    def test_simple(self):
        class SomeObject(ComplexModel):
            _type_info = [
                ('i', Integer),
                ('s', Unicode(64)),
            ]

        v = SomeObject(i=42, s="Arthur")
        elt = _test_type(SomeObject, v)[0]
        assert elt.xpath('div/input/@value') == ['42', 'Arthur']
        assert elt.xpath('div/input/@name') == ['i', 's']

    def test_no_fieldset(self):
        class SomeObject(ComplexModel):
            _type_info = [
                ('i', Integer),
                ('s', Unicode(64)),
            ]
        SomeObject = SomeObject.customize(no_fieldset=True)
        v = SomeObject(i=42, s="Arthur")
        elt = _test_type(SomeObject, v)
        assert elt.xpath('div/input/@value') == ['42', 'Arthur']
        assert elt.xpath('div/input/@name') == ['i', 's']

    def test_nested(self):
        class InnerObject(ComplexModel):
            _type_info = [
                ('s', Unicode(64)),
            ]
        class OuterObject(ComplexModel):
            _type_info = [
                ('i', InnerObject),
                ('d', Double),
            ]

        v = OuterObject(i=InnerObject(s="Arthur"), d=3.1415)
        elt = _test_type(OuterObject, v)[0]

        # it's a bit risky doing this with doubles
        assert elt.xpath('div/input/@value') == ['3.1415']
        assert elt.xpath('div/input/@name') == ['d']
        assert elt.xpath('fieldset/div/input/@value') == ['Arthur']
        assert elt.xpath('fieldset/div/input/@name') == ['i.s']

    def test_fieldset(self):
        fset_one = Fieldset("One")
        fset_two = Fieldset("Two")
        class SomeObject(ComplexModel):
            _type_info = [
                ('i0', Integer),
                ('s0', Unicode(64)),
                ('i1', Integer(fieldset=fset_one)),
                ('s1', Unicode(64, fieldset=fset_one)),
                ('i2', Integer(fieldset=fset_two)),
                ('s2', Unicode(64, fieldset=fset_two)),
            ]

        v = SomeObject(
            i0=42, s0="Arthur",
            i1=42, s1="Arthur",
            i2=42, s2="Arthur",
        )
        elt = _test_type(SomeObject, v)[0]
        assert elt.xpath('div/input/@value') == ['42', 'Arthur']
        assert elt.xpath('div/input/@name') == ['i0', 's0']
        assert elt.xpath('fieldset/div/input/@value') == ['42', 'Arthur',
                                                          '42', 'Arthur']
        assert elt.xpath('fieldset/div/input/@name') == ['i1', 's1', 'i2', 's2']

    def test_tab(self):
        tab1 = Tab("One")
        tab2 = Tab("Two")
        class SomeObject(ComplexModel):
            _type_info = [
                ('i0', Integer),
                ('i1', Integer(tab=tab1)),
                ('i2', Integer(tab=tab2)),
            ]

        v = SomeObject(i0=14, i1=28, i2=56)
        elt = _test_type(SomeObject, v)[0]
        assert elt.xpath('div/input/@value') == ['14']
        assert elt.xpath('div/input/@name') == ['i0']

        assert elt.xpath('div/ul/li/a/text()') == [tab1.legend, tab2.legend]
        assert elt.xpath('div/ul/li/a/@href') == ["#" + tab1.htmlid, "#" + tab2.htmlid]
        assert elt.xpath('div/div/@id') == [tab1.htmlid, tab2.htmlid]
        assert elt.xpath('div/div[@id]/div/input/@name') == ['i1', 'i2']
        assert elt.xpath('div/div[@id]/div/input/@value') == ['28', '56']

        # FIXME: properly test script tags
        assert elt.xpath('div/@id')[0] in elt.xpath('script/text()')[0]

    def test_simple_array(self):
        class SomeObject(ComplexModel):
            _type_info = [
                ('ints', Array(Integer)),
            ]

        v = SomeObject(ints=range(5))
        elt = _test_type(SomeObject, v)[0]
        assert elt.xpath('div/div/div/input/@value') == ['0', '1', '2', '3', '4']
        assert elt.xpath('div/div/button/text()') == ['+', '-'] * 5
        for i, name in enumerate(elt.xpath('div/div/input/@name')):
            assert re.match(r'ints\[0*%d\]' % i, name)


class TestSimpleHrefWidget(object):
    def test_simple(self):
        v = Integer(prot=HrefWidget(href="/some_href?id={}"))
        elt = _test_type(v, 5)
        assert elt.xpath('div/span/a/text()') == ['5']
        assert elt.xpath('div/span/a/@href') == ['/some_href?id=5']


class TestComplexHrefWidget(object):
    def test_simple(self):
        class SomeObject(ComplexModel):
            class Attributes(ComplexModel.Attributes):
                prot = ComplexHrefWidget('s', 'i')

            _type_info = [
                ('i', Integer),
                ('s', Unicode),
            ]

        v = SomeObject(i=42, s="Arthur")
        elt = _test_type(SomeObject, v)

        assert elt.xpath('div/a/text()') == ['Arthur']
        assert elt.xpath('div/a/@href') == ['some_object?i=42']


class TestComboBoxWidget(object):
    def test_simple_label(self):
        class SomeObject(ComplexModel):
            class Attributes(ComplexModel.Attributes):
                prot = ComboBoxWidget('s', 'i')

            _type_info = [
                ('i', Integer),
                ('s', Unicode),
            ]

        v = SomeObject(i=42, s="Arthur")
        elt = _test_type(SomeObject, v)

        assert elt.xpath('div/label/text()') == ['SomeObject']
        assert elt.xpath('div/select/option/text()') == ['Arthur']
        assert elt.xpath('div/select/option/@value') == ['42']

    def test_simple_nolabel(self):
        class SomeObject(ComplexModel):
            class Attributes(ComplexModel.Attributes):
                prot = ComboBoxWidget('s', 'i', label=False)

            _type_info = [
                ('i', Integer),
                ('s', Unicode),
            ]

        v = SomeObject(i=42, s="Arthur")
        elt = _test_type(SomeObject, v)

        assert elt.xpath('select/option/text()') == ['Arthur']
        assert elt.xpath('select/option/@value') == ['42']


if __name__ == '__main__':
    unittest.main()
