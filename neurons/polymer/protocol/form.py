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
# * Neither the name of the Arskom Ltd. nor the names of its
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

import logging

from neurons.polymer.model import PaperInput
from spyne.protocol.cloth import XmlCloth

logger = logging.getLogger(__name__)

from datetime import date

from lxml.html.builder import E

from neurons.form import HtmlFormRoot, SimpleRenderWidget

from spyne import ComplexModelBase, Unicode, Decimal, Boolean, Date, Time, \
    DateTime, Integer, Duration, PushBase, Array, Uuid, AnyHtml, AnyXml, \
    AnyUri, Fault, File, D
from spyne.util.cdict import cdict


class PolymerForm(HtmlFormRoot):
    HTML_INPUT = 'paper-input'
    HTML_OPTION = 'paper-item'
    HTML_SELECT = 'paper-dropdown-menu'
    HTML_TEXTAREA = 'paper-textarea'
    HTML_CHECKBOX_TAG = 'paper-checkbox'

    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                cloth=None, cloth_parser=None, polymorphic=True, hier_delim='.',
                     doctype=None, label=True, asset_paths={}, placeholder=None,
                                         input_class=None, input_div_class=None,
                                     input_wrapper_class=None, label_class=None,
                                  action=None, method='POST', before_form=None):

        super(PolymerForm, self).__init__(app=app, doctype=doctype,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                    hier_delim=hier_delim, label=label, asset_paths=asset_paths,
                    placeholder=placeholder, input_class=input_class,
                    input_div_class=input_div_class,
               input_wrapper_class=input_wrapper_class, label_class=label_class,
                          action=action, method=method, before_form=before_form)

        self.serialization_handlers = cdict({
            Date: self._check_simple(self.date_to_parent),
            Time: self._check_simple(self.time_to_parent),
            # Uuid: self._check_simple(self.uuid_to_parent),
            # File: self.file_to_parent,
            Fault: self.fault_to_parent,
            # Array: self.array_type_to_parent,
            AnyUri: self._check_simple(self.anyuri_to_parent),
            # AnyXml: self._check_simple(self.anyxml_to_parent),
            Integer: self._check_simple(self.integer_to_parent),
            Unicode: self._check_simple(self.unicode_to_parent),
            # AnyHtml: self._check_simple(self.anyhtml_to_parent),
            # Decimal: self._check_simple(self.decimal_to_parent),
            Boolean: self._check_simple(self.boolean_to_parent),
            # Duration: self._check_simple(self.duration_to_parent),
            DateTime: self._check_simple(self.datetime_to_parent),
            ComplexModelBase: self.complex_model_to_parent,
        })

        self.hier_delim = hier_delim

        self.asset_paths.update(asset_paths)
        self.use_global_null_handler = False

        self.simple = SimpleRenderWidget(label=label)

    def _gen_form_attrib(self, ctx, cls):
        attrib = {
            'id': 'form',
            'is': 'iron-form',
            'method': self.method,
            'content-type': "application/json",
        }

        attrib.update(self._get_form_action(ctx, self.get_cls_attrs(cls)))

        return attrib

    def _gen_input(self, ctx, cls, inst, name, cls_attrs, **kwargs):
        retval = super(PolymerForm, self)._gen_input(ctx, cls, inst, name,
                                                            cls_attrs, **kwargs)

        if cls_attrs.error_message is not None:
            retval.attrib['error-message'] = \
                             self.trd(cls_attrs.error_message, ctx.locale, name)

        if cls_attrs.placeholder is not None:
            retval.attrib['placeholder'] = \
                               self.trd(cls_attrs.placeholder, ctx.locale, name)

        return retval

    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attr = self.get_cls_attrs(cls)

        fieldset_attr = {'class': cls.get_type_name()}

        if cls_attr.fieldset is False or cls_attr.no_fieldset:
            return self._render_complex(ctx, cls, inst, parent, name, False,
                                                                       **kwargs)
        if cls_attr.fieldset or cls_attr.no_fieldset is False:
            with parent.element('fieldset', fieldset_attr):
                return self._render_complex(ctx, cls, inst, parent, name, False,
                                                                       **kwargs)

        with parent.element('fieldset', fieldset_attr):
            return self._render_complex(ctx, cls, inst, parent, name, True,
                                                                       **kwargs)

    @staticmethod
    def _apply_number_constraints(cls_attrs, elt_inst, epsilon):
        if cls_attrs.max_str_len != Decimal.Attributes.max_str_len:
            elt_inst.maxlength = str(cls_attrs.max_str_len)

        if cls_attrs.ge != Decimal.Attributes.ge:
            elt_inst.min = str(cls_attrs.ge)

        if cls_attrs.gt != Decimal.Attributes.gt:
            elt_inst.min = str(cls_attrs.gt + epsilon)

        if cls_attrs.le != Decimal.Attributes.le:
            elt_inst.max = str(cls_attrs.le)

        if cls_attrs.lt != Decimal.Attributes.lt:
            elt_inst.max = str(cls_attrs.lt - epsilon)

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_cls = PaperInput
        elt_inst = elt_cls()

        elt_inst.name = name
        elt_inst.type = "text"

        if cls_attrs.min_len is not None and cls_attrs.min_len > D('-inf'):
            elt_inst.minlength = cls_attrs.min_len

        if cls_attrs.max_len is not None and cls_attrs.max_len < D('inf'):
            elt_inst.maxlength = cls_attrs.max_len

        XmlCloth().to_parent(ctx, elt_cls, elt_inst, parent,
                                      elt_cls.Attributes.sub_name, use_ns=False)

    def integer_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_cls = PaperInput
        elt_inst = elt_cls()

        elt_inst.name = name
        elt_inst.type = "number"

        self._apply_number_constraints(cls_attrs, elt_inst, epsilon=1)

        XmlCloth().to_parent(ctx, elt_cls, elt_inst, parent,
                                      elt_cls.Attributes.sub_name, use_ns=False)

    def date_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)

        if elt.tag == self.HTML_INPUT:
            newelt = E('neurons-date-picker')

            for k in ('id', 'name'):
                newelt.attrib[k] = elt.attrib[k]

            if inst is not None:
                assert isinstance(inst, date)
                inststr = self.to_unicode(cls, inst)

                newelt.attrib['date'] = inststr

            elt = newelt

        div = self._wrap_with_label(ctx, cls, name, elt, **kwargs)
        parent.write(div)

    def time_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)
        elt.attrib['type'] = 'text'

        if cls_attrs.format is None:
            time_format = 'HH:MM:SS'

        else:
            time_format = cls_attrs.format.replace('%H', 'HH') \
                .replace('%M', 'MM') \
                .replace('%S', 'SS')

        div = self._wrap_with_label(ctx, cls, name, elt, **kwargs)
        parent.write(div)

    def datetime_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, None, name, cls_attrs, **kwargs)
        elt.attrib['type'] = 'text'

        dt_format = self._get_datetime_format(cls_attrs)
        if dt_format is None:
            date_format, time_format = 'yy-mm-dd', 'HH:mm:ss'
        else:
            date_format, time_format = \
                self._split_datetime_format(cls_attrs.dt_format)

        div = self._wrap_with_label(ctx, cls, name, elt, **kwargs)
        parent.write(div)

    def boolean_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        ret = self._gen_boolean_widget(ctx, cls, inst, name, **kwargs)
        del ret.attrib['type']
        ret.text = ret.attrib['label']
        del ret.attrib['label']
        parent.write(ret)
