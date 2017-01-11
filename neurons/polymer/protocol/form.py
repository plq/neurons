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

from lxml.html.builder import E

from neurons.form import THtmlFormRoot, SimpleRenderWidget
from neurons.polymer.model import NeuronsDatePicker, PaperCheckbox, \
    IronDataTable, NeuronsArray, IronAjax, IronDataTableColumn
from neurons.polymer.protocol.widget import PolymerWidgetBase

from spyne import ComplexModelBase, Unicode, Decimal, Boolean, DateTime, \
    Integer, AnyUri, Fault, D, Array
from spyne.util.cdict import cdict


class PolymerForm(THtmlFormRoot(PolymerWidgetBase)):
    HTML_FORM = 'form'

    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                cloth=None, cloth_parser=None, polymorphic=True, hier_delim='.',
                     doctype=None, label=True, placeholder=None,
              action=None, method='POST', before_form=None, mrpc_url_prefix=''):

        super(PolymerForm, self).__init__(app=app, doctype=doctype,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                    hier_delim=hier_delim, label=label, placeholder=placeholder,
                          action=action, method=method, before_form=before_form,
                                                mrpc_url_prefix=mrpc_url_prefix)

        self.serialization_handlers = cdict({
            # Date: self._check_simple(self.date_to_parent),
            # Time: self._check_simple(self.time_to_parent),
            # Uuid: self._check_simple(self.uuid_to_parent),
            # File: self.file_to_parent,
            Fault: self.fault_to_parent,
            AnyUri: self._check_simple(self.any_uri_to_parent),
            # AnyXml: self._check_simple(self.any_xml_to_parent),
            Integer: self._check_simple(self.integer_to_parent),
            Unicode: self._check_simple(self.unicode_to_parent),
            # AnyHtml: self._check_simple(self.any_html_to_parent),
            Decimal: self._check_simple(self.decimal_to_parent),
            Boolean: self._check_simple(self.boolean_to_parent),
            # Duration: self._check_simple(self.duration_to_parent),
            DateTime: self._check_simple(self.datetime_to_parent),
            ComplexModelBase: self.complex_model_to_parent,
        })

        self.hier_delim = hier_delim

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

    def _write_submit_button(self, parent):
        parent.write(
            E.div(
                E.input(
                    value="Submit",
                    type="submit",
                    **{'class': 'submit'}
                ),
                E.div(**{"class$": "[[submitStatus]]"}),
                E.div("[[submitError]]", **{'class': 'submit-error'}),
            ),
        )

    def array_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        if issubclass(cls, Array):
            cls, = cls._type_info.values()

        fti = cls.get_flat_type_info(cls)

        columns = []

        for k, v in fti.items():
            subcls_attrs = self.get_cls_attrs(v)
            if subcls_attrs.exc:
                continue

            subname= self.trc(cls, ctx.locale, k)
            columns.append(IronDataTableColumn(
                name=subname, template="[[item.%s]]" % (k,)
            ))

        methods = cls.Attributes.methods
        if methods is not None and len(methods) > 0:
            mrpc_delim_elt = E.span(" | ")  # TODO: parameterize this
            first = True
            for mn, md in methods.items():
                if first:
                    first = False

                elif mrpc_delim_elt is not None:
                    parent.write(" ")
                    parent.write(mrpc_delim_elt)

                # get first argument name
                cls_arg_name = next(iter(md.in_message._type_info.keys()))

                pd = []
                for k, v in cls.get_identifiers():
                    pd.append("{0}.{1}=[[item.{1}]]".format(cls_arg_name, k))
                pd.append('[[_urlencodeParams()]]')

                mdid2key = ctx.app.interface.method_descriptor_id_to_key
                href = mdid2key[id(md)].rsplit("}", 1)[-1]
                href_with_params = "%s%s?%s" % \
                                      (self.mrpc_url_prefix, href, '&'.join(pd))

                text = md.translate(ctx.locale, md.in_message.get_type_name())

                columns.append(IronDataTableColumn(
                    template=E.a(text, **{'href$': href_with_params}),
                ))

        wgt_inst = NeuronsArray(
            label=self.trc(cls, ctx.locale, name),
            name=self._gen_input_name(name),
            columns=columns,
        )

        self._add_label(ctx, cls, cls_attrs, name, wgt_inst, **kwargs)
        self._write_elt_inst(ctx, wgt_inst, parent)

    def complex_model_to_parent(self, ctx, cls, inst, parent, name,
                                                      from_arr=False, **kwargs):
        cls_attr = self.get_cls_attrs(cls)

        if not from_arr and issubclass(cls, Array) or cls_attr.max_occurs > 1:
            return self.array_to_parent(ctx, cls, inst, parent, name, **kwargs)

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

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_inst = self._gen_widget_inst(ctx, cls, inst, name, cls_attrs,
                                                                       **kwargs)

        if cls_attrs.min_len is not None and cls_attrs.min_len > D('-inf'):
            elt_inst.minlength = cls_attrs.min_len

        if cls_attrs.max_len is not None and cls_attrs.max_len < D('inf'):
            elt_inst.maxlength = cls_attrs.max_len

        self._add_label(ctx, cls, cls_attrs, name, elt_inst, **kwargs)
        self._write_elt_inst(ctx, elt_inst, parent)

    def integer_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_inst = self._gen_widget_inst(ctx, cls, inst, name, cls_attrs,
                                                                       **kwargs)
        elt_inst.type = "number"

        self._apply_number_constraints(cls_attrs, elt_inst, epsilon=1)

        self._add_label(ctx, cls, cls_attrs, name, elt_inst, **kwargs)
        self._write_elt_inst(ctx, elt_inst, parent)

    def decimal_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_inst = self._gen_widget_inst(ctx, cls, inst, name, cls_attrs,
                                                                       **kwargs)
        elt_inst.type = "number"

        if D(cls.Attributes.fraction_digits).is_infinite():
            epsilon = self.HTML5_EPSILON
            elt_inst.step = 'any'

        else:
            epsilon = 10 ** (-int(cls.Attributes.fraction_digits))
            elt_inst.step = str(epsilon)

        self._apply_number_constraints(cls_attrs, elt_inst, epsilon=epsilon)

        self._add_label(ctx, cls, cls_attrs, name, elt_inst)
        self._write_elt_inst(ctx, elt_inst, parent)

    def date_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_inst = NeuronsDatePicker()
        elt_inst.label = self.trd(cls_attrs.translations, ctx.locale, name)

        self._add_label(ctx, cls, cls_attrs, name, elt_inst)
        self._write_elt_inst(ctx, elt_inst, parent)

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

        if inst is not None:
            inst = inst.isoformat(' ')

        self.unicode_to_parent(ctx, cls, inst, parent, name, **kwargs)

    def boolean_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_inst = self._gen_widget_inst(ctx, cls, inst, name, cls_attrs,
                                                 sugcls=PaperCheckbox, **kwargs)

        self._write_elt_inst(ctx, elt_inst, parent)
