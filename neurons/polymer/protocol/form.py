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
logger = logging.getLogger(__name__)

from datetime import date

from lxml.html.builder import E

from neurons.form import HtmlForm


class PolymerForm(HtmlForm):
    HTML_INPUT = 'paper-input'
    HTML_OPTION = 'paper-item'
    HTML_OPTION_PARENTS = 'paper-listbox', {'class': 'dropdown-content'}
    HTML_SELECT = 'paper-dropdown-menu'
    HTML_TEXTAREA = 'paper-textarea'
    HTML_CHECKBOX_TAG = 'paper-checkbox'

    def _gen_form_attrib(self, ctx, cls):
        attrib = super(PolymerForm, self)._gen_form_attrib(ctx, cls)

        # attrib['id'] = attrib['action'] \
        #                        .replace('/', '_').replace('.', '_').strip('_')

        attrib['id'] = 'form'
        attrib['is'] = 'iron-form'
        attrib['content-type'] = "application/json"

        return attrib

    def _gen_options(self, ctx, cls, inst, name, cls_attrs, elt, **kwargs):
        del elt.attrib['name']
        del elt.attrib['class']

        option_parent = E('paper-listbox', **{'class': 'dropdown-content'})
        elt.append(option_parent)

        # FIXME: parameterize these
        elt.attrib['no-animations'] = ''
        elt.attrib['noink'] = ''

        super(PolymerForm, self)._gen_options(ctx, cls, inst, name, cls_attrs,
                                                        option_parent, **kwargs)
        return elt

    def _append_option(self, parent, label, value, selected=False, index=-1):
        assert (not selected) or index >= 0

        # waiting for https://github.com/lxml/lxml/pull/210
        # if selected:
        #     parent.attrib['selected'] = str(index)

        parent.append(E(self.HTML_OPTION, label))

    def _wrap_with_label(self, ctx, cls, name, input_elt, no_label=False,
                                             _=HtmlForm.WRAP_FORWARD, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        wants_no_label = cls_attrs.label is False or no_label or not self.label
        if not wants_no_label:
            input_elt.attrib['label'] = self.trc(cls, ctx.locale, name)
            input_elt.attrib['always-float-label'] = ""

        return input_elt

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
