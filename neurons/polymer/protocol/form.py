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

import re

from neurons.form.widget import camel_case_to_uscore
from neurons.polymer.model import PaperInput, NeuronsDatePicker, PaperCheckbox, \
    PaperDropdownMenu, PaperListbox, PaperItem

from neurons.form import HtmlFormRoot, SimpleRenderWidget

from spyne import ComplexModelBase, Unicode, Decimal, Boolean, Date, Time, \
    DateTime, Integer, Duration, PushBase, Array, Uuid, AnyHtml, AnyXml, \
    AnyUri, Fault, File, D
from spyne.protocol.cloth import XmlCloth
from spyne.util import six
from spyne.util.oset import oset
from spyne.util.cdict import cdict
from spyne.util.tdict import tdict



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
            # Date: self._check_simple(self.date_to_parent),
            # Time: self._check_simple(self.time_to_parent),
            # Uuid: self._check_simple(self.uuid_to_parent),
            # File: self.file_to_parent,
            Fault: self.fault_to_parent,
            # Array: self.array_type_to_parent,
            AnyUri: self._check_simple(self.anyuri_to_parent),
            # AnyXml: self._check_simple(self.anyxml_to_parent),
            Integer: self._check_simple(self.integer_to_parent),
            Unicode: self._check_simple(self.unicode_to_parent),
            # AnyHtml: self._check_simple(self.anyhtml_to_parent),
            Decimal: self._check_simple(self.decimal_to_parent),
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

    def _add_label(self, ctx, cls, cls_attrs, name, elt_inst,
                                                      no_label=False, **kwargs):
        wants_no_label = cls_attrs.label is False or no_label or not self.label

        if not wants_no_label:
            elt_inst.label = self.trc(cls, ctx.locale, name)
            elt_inst.always_float_label = True

        return elt_inst

    def _gen_elt_inst(self, ctx, cls, inst, name, cls_attrs, sugcls=PaperInput, **kwargs):
        elt_inst_data = dict(
            id=self._gen_input_elt_id(name, **kwargs),
            label=self.trc(cls, ctx.locale, name),
            name=self._gen_input_name(name),
            type='text',
        )

        elt_class = oset([
            camel_case_to_uscore(cls.get_type_name()),
            name.rsplit(self.hier_delim, 1)[-1],
            re.sub(r'\[[0-9]+\]', '', name).replace(self.hier_delim, '__'),
        ])

        if self.input_class is not None:
            elt_class.add(self.input_class)

        elt_inst_data["class_"] = ' '.join(elt_class)

        if cls_attrs.pattern is not None:
            elt_inst_data["pattern"] = cls_attrs.pattern

        if cls_attrs.read_only:
            elt_inst_data["readonly"] = True

        placeholder = cls_attrs.placeholder
        if placeholder is None:
            placeholder = self.placeholder

        if cls_attrs.error_message is not None:
            elt_inst_data['error_message'] = \
                             self.trd(cls_attrs.error_message, ctx.locale, name)

        if isinstance(placeholder, six.string_types):
            elt_inst_data["placeholder"] = placeholder

        elif placeholder:
            elt_inst_data["placeholder"] = self.trc(cls, ctx.locale, name)

        # Required bool means, in HTML context, a checkbox that needs to be
        # checked, which is not what we mean here at all.
        if not issubclass(cls, Boolean):
            # We used OR here because html forms send empty values anyway. So a
            # missing value is sent as null as well.
            if cls_attrs.min_occurs >= 1 or cls_attrs.nullable == False:
                elt_inst_data["required"] = True

        if (cls_attrs.write_once and inst is not None) or \
                                                       cls_attrs.write is False:
            elt_inst_data["readonly"] = True

        if cls_attrs.min_occurs == 1 and cls_attrs.nullable == False:
            elt_inst_data['required'] = True

        values = cls_attrs.values
        if values is None or len(values) == 0:
            return  sugcls(**elt_inst_data)

        elt_inst = PaperDropdownMenu(
             listbox=PaperListbox(items=[]), valueattr="value", **elt_inst_data)

        field_name = name.split('.')[-1]

        values_dict = cls_attrs.values_dict
        if values_dict is None:
            values_dict = {}

        inststr = self.to_unicode(cls, inst)
        if cls_attrs.write is False and inststr is not None:
            inst_label = values_dict.get(inst, inststr)
            if isinstance(inst_label, dict):
                inst_label = self.trd(inst_label, ctx.locale, field_name)

            logger.debug("\t\tinst %r label %r", inst_label, inst)
            item = PaperItem(value=inststr, label=inst_label)
            elt_inst.listbox.items.append(item)

        else:
            ever_selected = False
            we_have_empty = False

            if cls_attrs.nullable or cls_attrs.min_occurs == 0:
                elt_inst.listbox.items.append(PaperItem(value="", label=""))
                we_have_empty = True
                # if none are selected, this will be the default anyway, so
                # no need to add selected attribute to the option tag.

            # FIXME: cache this!
            for i, v in enumerate(cls_attrs.values):
                valstr = self.to_unicode(cls, v)
                if valstr is None:
                    valstr = ""

                if inst == v:
                    ever_selected = True
                    elt_inst.listbox.selected = i

                val_label = values_dict.get(v, valstr)
                logger.debug("\t\tother values inst %r label %r", v, val_label)
                if isinstance(val_label, dict):
                    val_label = self.trd(val_label, ctx.locale, valstr)

                item = PaperItem(value=valstr, label=val_label)
                elt_inst.listbox.items.append(item)

            if not (ever_selected or we_have_empty):
                elt_inst.listbox.items.insert(0, PaperItem(value="", label=""))

        return elt_inst

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
            elt_inst.maxlength = cls_attrs.max_str_len

        if cls_attrs.ge != Decimal.Attributes.ge:
            elt_inst.min = cls_attrs.ge

        if cls_attrs.gt != Decimal.Attributes.gt:
            elt_inst.min = cls_attrs.gt + epsilon

        if cls_attrs.le != Decimal.Attributes.le:
            elt_inst.max = cls_attrs.le

        if cls_attrs.lt != Decimal.Attributes.lt:
            elt_inst.max = cls_attrs.lt - epsilon

    def _write_elt_inst(self, ctx, elt_inst, parent):
        elt_cls = elt_inst.__class__
        XmlCloth().to_parent(ctx, elt_cls, elt_inst, parent,
                                      elt_cls.Attributes.sub_name, use_ns=False)

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_inst = self._gen_elt_inst(ctx, cls, inst, name, cls_attrs, **kwargs)

        if cls_attrs.min_len is not None and cls_attrs.min_len > D('-inf'):
            elt_inst.minlength = cls_attrs.min_len

        if cls_attrs.max_len is not None and cls_attrs.max_len < D('inf'):
            elt_inst.maxlength = cls_attrs.max_len

        self._add_label(ctx, cls, cls_attrs, name, elt_inst, **kwargs)
        self._write_elt_inst(ctx, elt_inst, parent)

    def integer_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_inst = self._gen_elt_inst(ctx, cls, inst, name, cls_attrs, **kwargs)
        elt_inst.type = "number"

        self._apply_number_constraints(cls_attrs, elt_inst, epsilon=1)

        self._add_label(ctx, cls, cls_attrs, name, elt_inst, **kwargs)
        self._write_elt_inst(ctx, elt_inst, parent)

    def decimal_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_inst = self._gen_elt_inst(ctx, cls, inst, name, cls_attrs, **kwargs)
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

        elt_inst = self._gen_elt_inst(ctx, cls, inst, name, cls_attrs,
                                                 sugcls=PaperCheckbox, **kwargs)

        self._write_elt_inst(ctx, elt_inst, parent)
