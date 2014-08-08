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


from inspect import isgenerator

from decimal import Decimal as D

from lxml import etree, html
from lxml.builder import E

from spyne import ComplexModelBase, Unicode, Decimal, Boolean
from spyne.protocol.html import HtmlBase
from spyne.util import coroutine, Break, memoize_id, DefaultAttrDict
from spyne.util.cdict import cdict


def _form_key(k):
    key, cls = k
    retval = getattr(cls.Attributes, 'order', None)

    if retval is None:
        retval = key

    return retval


def camel_case_to_uscore_gen(string):
    for i, s in enumerate(string):
        if s.isupper():
            if i > 0:
                yield "_"
            yield s.lower()
        else:
            yield s

camel_case_to_uscore = lambda s: ''.join(camel_case_to_uscore_gen(s))

@memoize_id
def _get_cls_attrs(self, cls):
    attr = DefaultAttrDict([(k, getattr(cls.Attributes, k))
                    for k in dir(cls.Attributes) if not k.startswith('__')])
    if cls.Attributes.prot_attrs:
        attr.update(cls.Attributes.prot_attrs.get(self.__class__, {}))
        attr.update(cls.Attributes.prot_attrs.get(self, {}))
    return attr


class HtmlWidget(HtmlBase):
    @staticmethod
    def selsafe(s):
        return s.replace('[', '').replace(']','').replace('.', '__')

    def _gen_input_elt_id(self, name):
        return self.selsafe(name) + '_input'

    def _gen_input_attrs(self, cls, inst, name, cls_attrs):
        elt_attrs = {
            'id': self._gen_input_elt_id(name),
            'name': name,
            'class': camel_case_to_uscore(cls.get_type_name()),
            'type': 'text',
        }

        if getattr(cls_attrs,'pattern', None) is not None:
            elt_attrs['pattern'] = cls_attrs.pattern

        if not cls_attrs.write:
            elt_attrs['readonly'] = 'readonly'

        if cls_attrs.read_only:
            elt_attrs['readonly'] = 'readonly'

        if cls_attrs.hidden:
            elt_attrs['type'] = 'hidden'

        if not (inst is None and isinstance(inst, type)):
            val = self.to_string(cls, inst)
            if val is not None:
                elt_attrs['value'] = val

        if cls_attrs.min_occurs == 1 and cls_attrs.nullable == False:
            elt_attrs['required'] = ''

        return elt_attrs

    def _gen_input(self, cls, inst, name, cls_attrs):
        elt_attrs = self._gen_input_attrs(cls, inst, name, cls_attrs)

        if cls_attrs.min_occurs == 1 and cls_attrs.nullable == False:
            elt = html.fromstring('<input required>')
            del elt_attrs['required']
            elt.attrib.update(elt_attrs)

        else:
            elt = E.input(**elt_attrs)

        return elt

    def _gen_input_unicode(self, cls, inst, name, **_):
        cls_attrs = _get_cls_attrs(self, cls)

        elt = self._gen_input(cls, inst, name, cls_attrs)
        elt.attrib['type'] = 'text'

        if cls_attrs.max_len < Unicode.Attributes.max_len:
            elt.attrib['maxlength'] = str(int(cls_attrs.max_len))
        if cls_attrs.min_len > Unicode.Attributes.min_len:
            elt.attrib['minlength'] = str(int(cls_attrs.min_len))

        return cls_attrs, elt

    @staticmethod
    def _apply_number_constraints(cls_attrs, elt):
        if cls_attrs.max_str_len != Decimal.Attributes.max_str_len:
            elt.attrib['maxlength'] = str(cls_attrs.max_str_len)

        if elt.attrib['type'] == 'range':
            if cls_attrs.ge != Decimal.Attributes.ge:
                elt.attrib['min'] = str(cls_attrs.ge)
            if cls_attrs.gt != Decimal.Attributes.gt:
                elt.attrib['min'] = str(cls_attrs.gt)
            if cls_attrs.le != Decimal.Attributes.le:
                elt.attrib['max'] = str(cls_attrs.le)
            if cls_attrs.lt != Decimal.Attributes.lt:
                elt.attrib['max'] = str(cls_attrs.lt)


class HtmlForm(HtmlWidget):
    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                       cloth=None, attr_name='spyne_id', root_attr_name='spyne',
                                             cloth_parser=None, hier_delim='.'):

        super(HtmlForm, self).__init__(app=app,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, attr_name=attr_name, root_attr_name=root_attr_name,
                                                      cloth_parser=cloth_parser)

        self.serialization_handlers = cdict({
            Unicode: self.unicode_to_parent,
            Decimal: self.decimal_to_parent,
            Boolean: self.boolean_to_parent,
            ComplexModelBase: self.complex_model_to_parent,
        })

        self.hier_delim = hier_delim
        self.assets = [
            E.script(src="/assets/jquery/1.11.1/min.js", type="text/javascript")
        ]

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs, elt = self._gen_input_unicode(cls, inst, name)
        parent.write(elt)

    def decimal_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, inst, name, cls_attrs)
        elt.attrib['type'] = 'number'

        if D(cls.Attributes.fraction_digits).is_infinite():
            elt.attrib['step'] = 'any'
        else:
            elt.attrib['step'] = str(10**(-int(cls.Attributes.fraction_digits)))

        self._apply_number_constraints(cls_attrs, elt)
        parent.write(elt)

    def boolean_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, inst, name, cls_attrs)
        elt.attrib.update({'type': 'checkbox', 'value': 'true'})

        if bool(inst):
            elt.attrib['checked'] = ''

        parent.write(elt)

    @coroutine
    def subserialize(self, ctx, cls, inst, parent, name=None, **kwargs):
        with parent.element("form"):
            ret = super(HtmlForm, self).subserialize(ctx, cls, inst, parent,
                                                                 name, **kwargs)
            if isgenerator(ret):
                try:
                    while True:
                        y = (yield)
                        ret.send(y)

                except Break as b:
                    try:
                        ret.throw(b)
                    except StopIteration:
                        pass

    @coroutine
    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        fti = cls.get_flat_type_info(cls)

        for k, v in sorted(fti.items(), key=_form_key):
            subinst = getattr(inst, k, None)
            ret = self.to_parent(ctx, v, subinst, parent, name, **kwargs)
            if isgenerator(ret):
                try:
                    while True:
                        y = (yield)
                        ret.send(y)

                except Break as b:
                    try:
                        ret.throw(b)
                    except StopIteration:
                        pass


class PasswordWidget(HtmlWidget):
    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs, elt = self._gen_input_unicode(cls, inst, name)
        elt.attrib['type'] = 'password'
        parent.write(elt)
