#!/usr/bin/env python
# encoding: utf8
#
# This file is part of the Neurons project.
# Copyright (c), Arskom Ltd. (arskom.com.tr),
#                Burak Arslan <burak.arslan@arskom.com.tr>.
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
# * Neither the name of the Arskom Ltd., the neurons project nor the names of
#   its its contributors may be used to endorse or promote products derived from
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

import unittest

from lxml import html, etree

from neurons.polymer import PolymerForm

from spyne import Application, NullServer, Service, rpc, Unicode, Integer, \
    ComplexModel, Decimal
from spyne.util.test import show


def _test_type(cls, inst):
    # silence bogus warnings
    from spyne.util import appreg; appreg.applications.clear()

    class SomeService(Service):
        @rpc(_returns=cls, _body_style='bare')
        def some_call(ctx):
            return inst

    prot = PolymerForm()
    app = Application([SomeService], 'some_ns', out_protocol=prot)

    null = NullServer(app, ostr=True)

    ret = ''.join(null.service.some_call())
    try:
        elt = html.fromstring(ret)
    except:
        print(ret)
        raise

    show(elt, stdout=False)
    print(etree.tostring(elt, pretty_print=True))

    return elt


class TestPolymerForm(object):
    def test_simple_decimal(self):
        v = 42
        elt = _test_type(Decimal(ge=0, le=5), v)

        assert elt.xpath('paper-input/@name') == ['']
        assert elt.xpath('paper-input/@type') == ['number']
        assert elt.xpath('paper-input/@min') == ['0']
        assert elt.xpath('paper-input/@max') == ['5']

    def test_complex(self):
        class SomeObject(ComplexModel):
            _type_info = [
                ('i', Integer),
                ('s', Unicode),
            ]

        v = SomeObject(i=42, s="Arthur")
        elt = _test_type(SomeObject, v)

        assert elt.xpath('fieldset/paper-input/@name') == ['i', 's']


class TestPolymerDropdownMenu(object):
    def test_simple(self):
        elt = _test_type(Integer(values=[0, 3, 2, 1]), None)
        ret = elt.xpath('paper-dropdown-menu/paper-listbox/paper-item/text()')

        # This has to do with the workaround in complex_to_parent in
        # cloth/to_parent.py
        ret = [r.strip() for r in ret]

        assert ret == ['', '0', '3', '2', '1']

    def _test_complex(self):
        class SomeObject(ComplexModel):
            class Attributes(ComplexModel.Attributes):
                prot = PolymerDropdownMenu('s', 'i')

            _type_info = [
                ('i', Integer),
                ('s', Unicode),
            ]

        v = SomeObject(i=42, s="Arthur")
        elt = _test_type(SomeObject, v)

        assert elt.xpath('paper-dropdown-menu/paper-listbox/paper-item/@name') \
                                                                         == ['']


if __name__ == '__main__':
    unittest.main()
