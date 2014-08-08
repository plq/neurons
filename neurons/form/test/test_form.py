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


import unittest
import logging

from decimal import Decimal as D

from neurons.form import HtmlForm, PasswordWidget
from spyne import Application, NullServer, Unicode, ServiceBase, rpc, Decimal, \
    Boolean
from lxml import etree

logging.basicConfig(level=logging.DEBUG)


def _test_type(cls, inst):
    from spyne.util import appreg; appreg._applications.clear()

    class SomeService(ServiceBase):
        @rpc(_returns=cls, _body_style='bare')
        def some_call(ctx):
            return inst

    app = Application([SomeService], 'some_ns', out_protocol=HtmlForm())

    null = NullServer(app, ostr=True)
    elt = etree.fromstring(''.join(null.service.some_call()))
    print(etree.tostring(elt, pretty_print=True))

    return elt


class TestForm(unittest.TestCase):
    def test_unicode(self):
        v = 'foo'
        elt = _test_type(Unicode, v).xpath('input')[0]
        assert elt.attrib['type'] == 'text'
        assert elt.attrib['name'] == 'string'
        assert elt.attrib['value'] == v

    def test_unicode_password(self):
        elt = _test_type(Unicode(prot=PasswordWidget()), None).xpath('input')[0]
        assert elt.attrib['type'] == 'password'

    def test_decimal(self):
        elt = _test_type(Decimal, D('0.1')).xpath('input')[0]
        assert elt.attrib['type'] == 'number'
        assert elt.attrib['step'] == 'any'

    def test_decimal_step(self):
        elt = _test_type(Decimal(fraction_digits=4), D('0.1')).xpath('input')[0]
        assert elt.attrib['step'] == '0.0001'

    def test_boolean_true(self):
        elt = _test_type(Boolean, True).xpath('input')[0]
        assert 'checked' in elt.attrib

    def test_boolean_false(self):
        elt = _test_type(Boolean, False).xpath('input')[0]
        assert not ('checked' in elt.attrib)

    def test_date(self):
        pass


if __name__ == '__main__':
    unittest.main()
