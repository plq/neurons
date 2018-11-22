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

import logging
logger = logging.getLogger(__name__)

import re
import json

from spyne import ComplexModelBase, Boolean, Decimal
from spyne.util import six
from spyne.util.oset import oset
from spyne.util.cdict import cdict
from spyne.protocol.cloth import XmlCloth
from spyne.protocol.html import HtmlCloth

from neurons.form.widget import camel_case_to_uscore
from neurons.polymer.model import PaperInput, PaperDropdownMenu, PaperListbox, \
    PaperItem, NeuronsComplexDropdown, NeuronsComplexHref


class PolymerWidgetBase(HtmlCloth):
    # noinspection PyUnusedLocal
    def __init__(self, app=None, encoding='utf8',
                      mime_type=None, ignore_uncap=False, ignore_wrappers=False,
                                cloth=None, cloth_parser=None, polymorphic=True,
                              strip_comments=True, hier_delim='.', doctype=None,
                                                   placeholder=None, label=True,
               # the rest is not used, required for compat with HtmlFormWidget
               input_class=None, input_div_class=None, input_wrapper_class=None,
                                                              label_class=None):

        super(PolymerWidgetBase, self).__init__(app=app, encoding=encoding,
                                         doctype=doctype, hier_delim=hier_delim,
                                 mime_type=mime_type, ignore_uncap=ignore_uncap,
                                   ignore_wrappers=ignore_wrappers, cloth=cloth,
                             cloth_parser=cloth_parser, polymorphic=polymorphic,
                                                  strip_comments=strip_comments)

        self.label = label
        self.placeholder = placeholder
        self.use_global_null_handler = False

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

        if elt_inst.min is None and cls_attrs.min_bound is not None:
            elt_inst.min = str(cls_attrs.min_bound)

        if elt_inst.max is None and cls_attrs.max_bound is not None:
            elt_inst.max = str(cls_attrs.max_bound)

    def _write_elt_inst(self, ctx, elt_inst, parent):
        elt_cls = elt_inst.__class__
        XmlCloth().to_parent(ctx, elt_cls, elt_inst, parent,
                                      elt_cls.Attributes.sub_name, use_ns=False)
        parent.write("\n")

    def _gen_elt_id(self, name, sugcls, array_index=None, **kwargs):
        wigname = camel_case_to_uscore(sugcls.get_type_name())
        if array_index is None:
            return "%s_%s" % (self.selsafe(name), wigname)
        return "%s_%d_%s" % (self.selsafe(name), array_index, wigname)

    def _add_label(self, ctx, cls, cls_attrs, name, elt_inst,
                                                      no_label=False, **kwargs):
        wants_no_label = cls_attrs.label is False or no_label or not self.label

        if not wants_no_label:
            elt_inst.label = self.trc(cls, ctx.locale, name)
            elt_inst.always_float_label = True

        return elt_inst

    def _gen_input_name(self, name, array_index=None):
        if array_index is None:
            return name
        return "%s[%d]" % (name, array_index)

    def _gen_widget_data(self, ctx, cls, inst, name, cls_attrs, **kwargs):
        wgt_inst_data = dict(
            label=self.trc(cls, ctx.locale, name),
            name=self._gen_input_name(name),
            type='text',
        )

        elt_class = oset([
            camel_case_to_uscore(cls.get_type_name()),
            name.rsplit(self.hier_delim, 1)[-1],
            re.sub(r'\[[0-9]+\]', '', name).replace(self.hier_delim, '__'),
        ])

        wgt_inst_data["class_"] = ' '.join(elt_class)

        if cls_attrs.pattern is not None:
            wgt_inst_data["pattern"] = cls_attrs.pattern

        if cls_attrs.read_only:
            wgt_inst_data["readonly"] = True

        if cls_attrs.error_message is not None:
            wgt_inst_data['error_message'] = \
                             self.trd(cls_attrs.error_message, ctx.locale, name)

        placeholder = cls_attrs.placeholder
        if isinstance(placeholder, six.string_types):
            wgt_inst_data["placeholder"] = placeholder

        elif placeholder:
            wgt_inst_data["placeholder"] = self.trc(cls, ctx.locale, name)

        # Required bool means, in HTML context, a checkbox that needs to be
        # checked, which is not what we mean here at all.
        if not issubclass(cls, Boolean):
            # We used OR here because html forms send empty values anyway. So a
            # missing value is sent as null as well.
            if cls_attrs.min_occurs >= 1 or cls_attrs.nullable == False:
                wgt_inst_data["required"] = True

        if (cls_attrs.write_once and inst is not None) or \
                                                       cls_attrs.write is False:
            wgt_inst_data["readonly"] = True

        if cls_attrs.min_occurs == 1 and cls_attrs.nullable == False:
            wgt_inst_data['required'] = True

        if cls_attrs.read_only:
            wgt_inst_data['readonly'] = True

        # we need to check for an explicit False and not something that walks
        # and quacks like a False.
        if cls_attrs.write is False:
            wgt_inst_data['readonly'] = True

        return wgt_inst_data

    def _gen_widget_inst(self, ctx, cls, inst, name, cls_attrs,
                                                   sugcls=PaperInput, **kwargs):

        wgt_inst_data = self._gen_widget_data(ctx, cls, inst,
                                                      name, cls_attrs, **kwargs)

        values = cls_attrs.values
        if values is None or len(values) == 0:
            wgt_inst_data['id'] = self._gen_elt_id(name, sugcls, **kwargs)
            return sugcls(**wgt_inst_data)

        sugcls = PaperDropdownMenu
        wgt_inst_data['id'] = self._gen_elt_id(name, sugcls, **kwargs)
        elt_inst = sugcls(
            listbox=PaperListbox(items=[], class_='dropdown-content'),
            valueattr="value", **wgt_inst_data)

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
            elt_inst.listbox.selected = 0

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


class PolymerComplexDropdownWidget(PolymerWidgetBase):
    def __init__(self, text_field=None, id_field=None, data_source=None,
                                  need_parent_params=True, param_whitelist=None,
                  app=None, encoding='utf8', mime_type=None, ignore_uncap=False,
         ignore_wrappers=False, cloth=None, cloth_parser=None, polymorphic=True,
                 strip_comments=True, hier_delim='.', doctype=None, label=True):

        super(PolymerComplexDropdownWidget, self) \
            .__init__(app=app, encoding=encoding, doctype=doctype,
                      hier_delim=hier_delim, mime_type=mime_type,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                                     strip_comments=strip_comments, label=label)

        self.serialization_handlers = cdict({
            ComplexModelBase: self.complex_model_to_parent,
        })

        self.param_whitelist = param_whitelist
        self.data_source = data_source
        self.text_field = text_field
        self.need_parent_params = need_parent_params
        self.id_field = id_field

    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        wgt_inst_data = self._gen_widget_data(ctx, cls, inst, name, cls_attrs,
                                                                       **kwargs)

        wgt_inst = NeuronsComplexDropdown(
            need_parent_params=self.need_parent_params,
            data_source=self.data_source,
            attr_item_label=self.text_field, attr_item_value=self.id_field,
                                                                **wgt_inst_data)

        if self.param_whitelist is not None:
            wgt_inst.param_whitelist = json.dumps(self.param_whitelist)

        self._add_label(ctx, cls, cls_attrs, name, wgt_inst, **kwargs)
        self._write_elt_inst(ctx, wgt_inst, parent)


class PolymerComplexHrefWidget(PolymerWidgetBase):
    def __init__(self, text_field=None, id_field=None,
            need_parent_params=True, param_whitelist=None, base_href=None,
                  app=None, encoding='utf8', mime_type=None, ignore_uncap=False,
         ignore_wrappers=False, cloth=None, cloth_parser=None, polymorphic=True,
                 strip_comments=True, hier_delim='.', doctype=None, label=True):

        super(PolymerComplexHrefWidget, self) \
            .__init__(app=app, encoding=encoding, doctype=doctype,
                                 hier_delim=hier_delim, mime_type=mime_type,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                                     strip_comments=strip_comments, label=label)

        self.serialization_handlers = cdict({
            ComplexModelBase: self.complex_model_to_parent,
        })

        self.param_whitelist = param_whitelist
        self.text_field = text_field
        self.need_parent_params = need_parent_params
        self.id_field = id_field
        self.base_href = base_href

    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        wgt_inst_data = self._gen_widget_data(ctx, cls, inst, name, cls_attrs,
                                                                       **kwargs)
        base_href = self.base_href
        if base_href is None:
            base_href = camel_case_to_uscore(cls.get_type_name())

        wgt_inst = NeuronsComplexHref(
            base_href=base_href,
            need_parent_params=self.need_parent_params,
            attr_item_label=self.text_field, attr_item_value=self.id_field,
                                                                **wgt_inst_data)

        if self.param_whitelist is not None:
            wgt_inst.param_whitelist = json.dumps(self.param_whitelist)

        self._add_label(ctx, cls, cls_attrs, name, wgt_inst, **kwargs)
        self._write_elt_inst(ctx, wgt_inst, parent)
