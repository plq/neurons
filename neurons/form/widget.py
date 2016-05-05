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

from __future__ import print_function

import logging
logger = logging.getLogger(__name__)

import re
import locale
import collections

from contextlib import closing
from inspect import isclass, getargspec
from decimal import Decimal as D

from lxml import html
from lxml.builder import E

from spyne import Unicode, Decimal, Boolean, ComplexModelBase, Array, ModelBase, \
    AnyHtml, AnyUri
from spyne.util import six
from spyne.util.tdict import tdict
from spyne.util.oset import oset
from spyne.util.cdict import cdict
from spyne.util.six.moves.urllib.parse import urlencode

from spyne.protocol.html import HtmlBase


def camel_case_to_uscore_gen(string):
    for i, s in enumerate(string):
        if s.isupper():
            if i > 0:
                yield "_"
            yield s.lower()
        else:
            yield s


camel_case_to_uscore = lambda s: ''.join(camel_case_to_uscore_gen(s))


class HtmlWidget(HtmlBase):
    DEFAULT_INPUT_WRAPPER_CLASS = 'label-input-wrapper'
    DEFAULT_ANCHOR_WRAPPER_CLASS = 'label-anchor-wrapper'

    WRAP_FORWARD = type("WRAP_FORWARD", (object,), {})
    WRAP_REVERSED = type("WRAP_REVERSED", (object,), {})

    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                cloth=None, cloth_parser=None, polymorphic=True, hier_delim='.',
                     label=True, doctype=None, asset_paths={}, placeholder=None,
               input_class=None, input_div_class=None, input_wrapper_class=None,
                                                              label_class=None):

        super(HtmlWidget, self).__init__(app=app, doctype=doctype,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                                                          hier_delim=hier_delim)
        self.label = label
        self.placeholder = placeholder
        self.asset_paths = asset_paths
        self._init_input_vars(input_class, input_div_class,
                                               input_wrapper_class, label_class)

        self.use_global_null_handler = False

    def _init_input_vars(self, input_class, input_div_class,
                                              input_wrapper_class, label_class):
        self.input_class = input_class
        self.input_div_class = input_div_class
        self.input_wrapper_class = input_wrapper_class
        if self.input_wrapper_class is None:
            self.input_wrapper_class = self.DEFAULT_INPUT_WRAPPER_CLASS
        self.label_class = label_class

    def to_subprot(self, ctx, cls, inst, parent, name, subprot, **kwargs):
        if isinstance(subprot, HtmlWidget):
            if subprot.input_class is None:
                subprot.input_class = self.input_class

            if subprot.input_wrapper_class == self.DEFAULT_INPUT_WRAPPER_CLASS:
                subprot.input_wrapper_class = self.input_wrapper_class

            if subprot.label_class is None:
                subprot.label_class = self.label_class

        return super(HtmlWidget, self).to_subprot(ctx, cls, inst, parent, name,
                                                              subprot, **kwargs)

    @staticmethod
    def _format_js(lines, **kwargs):
        js = []
        for i, line in enumerate(lines):
            js.append(lines[i] % kwargs)

        return E.script("$(function(){\n\t%s\n});" % '\n\t'.join(js),
                                                        type="text/javascript")

    @staticmethod
    def selsafe(s):
        return s.replace('[', '').replace(']', '').replace('.', '__')

    def _gen_input_hidden(self, cls, inst, parent, name, **kwargs):
        val = self.to_unicode(cls, inst)
        elt = E.input(type="hidden", name=name)
        if val is not None:
            elt.attrib['value'] = val
        parent.write(elt)

    def _gen_label_for(self, ctx, cls, name, input_id=None, **kwargs):
        attrib = {}

        if input_id is not None:
            attrib['for'] = input_id
        if self.label_class is not None:
            attrib['class'] = self.label_class

        return E.label(self.trc(cls, ctx.locale, name), **attrib)

    def _gen_label_wrapper_class(self, ctx, cls, name):
        classes = [self.input_wrapper_class, self.selsafe(name)]
        return {'class': ' '.join(classes)}

    def _wrap_with_label(self, ctx, cls, name, input, no_label=False,
                                             wrap_label=WRAP_FORWARD, **kwargs):
        input_id = input.attrib['id']
        if self.input_div_class is not None:
            input = E.div(input, **{'class': self.input_div_class})

        attrib = self._gen_label_wrapper_class(ctx, cls, name)
        if (no_label or not self.label) and wrap_label is not None:
            retval = E.div(input, **attrib)

        else:
            label_attrib = {'for': input_id}
            if self.label_class is not None:
                label_attrib['class'] = self.label_class

            retval = E.label(self.trc(cls, ctx.locale, name), **label_attrib)
            if wrap_label is HtmlWidget.WRAP_FORWARD:
                retval = E.div(retval, input, **attrib)
            elif wrap_label is HtmlWidget.WRAP_REVERSED:
                retval = E.div(input, retval, **attrib)
            elif wrap_label is None:
                pass
            else:
                raise ValueError(wrap_label)

        return retval

    def _gen_input_elt_id(self, name, array_index=None, **kwargs):
        if array_index is None:
            return "%s_input" % (self.selsafe(name),)
        return "%s_%d_input" % (self.selsafe(name), array_index)

    def _gen_input_name(self, name, array_index=None):
        if array_index is None:
            return name
        return "%s[%d]" % (name, array_index)

    def _gen_input_attrs_novalue(self, ctx, cls, name, cls_attrs, **kwargs):
        elt_class = oset([
            camel_case_to_uscore(cls.get_type_name()),
            name.rsplit(self.hier_delim, 1)[-1],
            re.sub(r'\[[0-9]+\]', '', name).replace(self.hier_delim, '__'),
        ])

        if self.input_class is not None:
            elt_class.add(self.input_class)
        elt_class = ' '.join(elt_class)

        elt_attrs = tdict(six.string_types, six.string_types, {
            'id': self._gen_input_elt_id(name, **kwargs),
            'name': self._gen_input_name(name),
            'type': 'text',
            'class': elt_class,
        })

        if cls_attrs.pattern is not None:
            elt_attrs['pattern'] = cls_attrs.pattern

        if cls_attrs.read_only:
            elt_attrs['readonly'] = ""

        placeholder = cls_attrs.placeholder
        if placeholder is None:
            placeholder = self.placeholder

        if isinstance(placeholder, six.string_types):
            elt_attrs['placeholder'] = placeholder

        elif placeholder:
            elt_attrs['placeholder'] = self.trc(cls, ctx.locale, name)

        # Required bool means, in HTML context, a checkbox that needs to be
        # checked, which is not what we mean here at all.
        if not issubclass(cls, Boolean):
            # We used OR here because html forms send empty values anyway. So a
            # missing value is sent as null as well.
            if cls_attrs.min_occurs >= 1 or cls_attrs.nullable == False:
                elt_attrs['required'] = ''

        return elt_attrs

    def _gen_input_attrs(self, ctx, cls, inst, name, cls_attrs, **kwargs):
        elt_attrs = self._gen_input_attrs_novalue(ctx, cls, name, cls_attrs,
                                                                       **kwargs)

        if (cls_attrs.write_once and inst is not None) or \
                                                       cls_attrs.write is False:
            elt_attrs['readonly'] = ""

        val = self.to_unicode(cls, inst)
        if val is not None:
            elt_attrs['value'] = val

        return elt_attrs

    def _gen_input(self, ctx, cls, inst, name, cls_attrs, **kwargs):
        elt_attrs = self._gen_input_attrs(ctx, cls, inst, name, cls_attrs,
                                                                       **kwargs)

        tag = 'input'
        values = cls_attrs.values
        values_dict = cls_attrs.values_dict
        if values_dict is None:
            values_dict = {}

        if values is not None and len(values) > 0:
            tag = 'select'
            if 'value' in elt_attrs:
                del elt_attrs['value']
            if 'type' in elt_attrs:
                del elt_attrs['type']

        if cls_attrs.min_occurs == 1 and cls_attrs.nullable == False:
            elt = html.fromstring('<%s required>' % tag)
            elt.attrib.update(elt_attrs)
        else:
            elt = E(tag, **elt_attrs)

        if values is None or len(values) == 0:
            return elt

        inststr = self.to_unicode(cls, inst)
        if cls_attrs.write is False and inststr is not None:
            inst_label = values_dict.get(inst, inststr)
            if isinstance(inst_label, dict):
                inst_label = self.trd(inst_label, ctx.locale, inststr)
            logger.debug("\t\tinst %r label %r", inst_label, inst)
            elt.append(E.option(inst_label, value=inststr))

        else:
            selected = False
            we_have_empty = False

            if cls_attrs.nullable or cls_attrs.min_occurs == 0:
                elt.append(E.option("", dict(value='')))
                we_have_empty = True
                # if none are selected, this will be the default anyway, so
                # no need to add selected attribute to the option tag.

            # FIXME: cache this!
            for v in cls_attrs.values:
                valstr = self.to_unicode(cls, v)
                if valstr is None:
                    valstr = ""

                attrib = dict(value=valstr)
                if inst == v:
                    attrib['selected'] = ''
                    selected = True

                val_label = values_dict.get(v, valstr)
                logger.debug("\t\tother values inst %r label %r", v, val_label)
                if isinstance(val_label, dict):
                    val_label = self.trd(val_label, ctx.locale, inststr)

                elt.append(E.option(val_label, **attrib))

            if not (selected or we_have_empty):
                elt.append(E.option("", dict(value='', selected='')))

        return elt

    def _gen_input_textarea(self, ctx, cls, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        elt_attrs = self._gen_input_attrs_novalue(ctx, cls, name, cls_attrs)
        if cls_attrs.min_occurs == 1 and cls_attrs.nullable == False:
            elt = html.fromstring('<textarea required>')
            elt.attrib.update(elt_attrs)
        else:
            elt = E.textarea(**elt_attrs)

        return cls_attrs, elt

    def _gen_input_unicode(self, ctx, cls, inst, name, attr_override={},
                                                                      **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        max_len = attr_override.get('max_len', cls_attrs.max_len)
        min_len = attr_override.get('min_len', cls_attrs.min_len)
        values = attr_override.get('values', cls_attrs.values)

        if len(values) == 0 and max_len >= D('inf'):
            tag = 'textarea'

            elt_attrs = self._gen_input_attrs_novalue(ctx, cls, name, cls_attrs)
            if (cls_attrs.write_once and inst is not None) or \
                                                       cls_attrs.write is False:
                elt_attrs['readonly'] = ""

            if cls_attrs.min_occurs == 1 and cls_attrs.nullable == False:
                elt = html.fromstring('<%s required>' % tag)
                elt.attrib.update(elt_attrs)
            else:
                elt = E(tag, **elt_attrs)

            if not (inst is None and isinstance(inst, type)):
                elt.text = self.to_unicode(cls, inst)

        else:
            elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)
            elt.attrib['type'] = 'text'

            if max_len < Unicode.Attributes.max_len:
                elt.attrib['maxlength'] = str(int(max_len))
            if min_len > Unicode.Attributes.min_len:
                elt.attrib['minlength'] = str(int(min_len))

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


# TODO: Make label optional
class PasswordWidget(HtmlWidget):
    def __init__(self, *args, **kwargs):
        super(PasswordWidget, self).__init__(*args, **kwargs)

        self.serialization_handlers = cdict({
            Unicode: self.unicode_to_parent,
            ComplexModelBase: self.not_supported,
        })

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs, elt = self._gen_input_unicode(ctx, cls, inst, name, **kwargs)
        elt.attrib['type'] = 'password'
        parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))


# TODO: Make label optional
class HrefWidget(HtmlWidget):
    supported_types = (Unicode, Decimal)

    def __init__(self, href, hidden_input=False, label=True):
        super(HrefWidget, self).__init__(label=label)

        self.href = href
        self.hidden_input = hidden_input

        self.serialization_handlers = cdict({
            ModelBase: self.model_base_to_parent,
            ComplexModelBase: self.not_supported,
        })

    def model_base_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        id_str = self.to_unicode(cls, inst)
        if id_str is None:
            id_str = ''

        try:
            href = self.href.format(inst)
        except:
            href = self.href

        elt = E.a(id_str)
        if href is not None:
            elt.attrib['href'] = href

        if self.label:
            label = self._gen_label_for(ctx, cls, name)
            attrib = self._gen_label_wrapper_class(ctx, cls, name)

            with parent.element('div', attrib=attrib):
                parent.write(label)

                span_attrib = {}
                parent.write(E.span(elt, **span_attrib))

        else:
            parent.write(elt)

        cls_attr = self.get_cls_attrs(cls)
        if self.hidden_input and (inst is not None or cls_attr.min_occurs >= 1):
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)


class SimpleRenderWidget(HtmlWidget):
    def __init__(self, label=True, type=None, hidden=False):
        super(SimpleRenderWidget, self).__init__(label=label)

        self.type = type
        self.hidden = hidden
        self.serialization_handlers = cdict({
            ModelBase: self.model_base_to_parent,
            AnyHtml: self.any_html_to_parent,
            AnyUri: self.any_uri_to_parent,
            ComplexModelBase: self.not_supported,
        })

    def _get_cls(self, cls):
        if self.type is not None:
            cls = self.type
            if len(self.type_attrs) > 0:
                cls = self.type.customize(**self.type_attrs)

        return cls

    def _gen_text_str(self, cls, inst, **kwargs):
        cls = self._get_cls(cls)

        text_str = self.to_unicode(cls, inst, **kwargs)

        if text_str is None:
            text_str = ''

            cls_attr = self.get_cls_attrs(cls)
            if cls_attr.min_occurs == 0:
                return None

        return text_str

    def _wrap_with_label_simple(self, ctx, cls, text_str, parent, name):
        label = self._gen_label_for(ctx, cls, name)
        attrib = self._gen_label_wrapper_class(ctx, cls, name)

        with parent.element('div', attrib=attrib):
            parent.write(label)

            span_attrib = {}
            parent.write(E.span(text_str, **span_attrib))

    def model_base_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        text_str = self._gen_text_str(cls, inst, **kwargs)
        if text_str is None:
            return

        if self.label:
            self._wrap_with_label_simple(ctx, cls, text_str, parent, name)
        else:
            parent.write(text_str)

        if self.hidden:
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)

    def any_uri_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if isinstance(inst, AnyUri.Value):
            href_str = self._gen_text_str(cls, inst.href)
            link_str = inst.text
        else:
            href_str = self._gen_text_str(cls, inst)
            if href_str is None:
                return
            link_str = href_str

        anchor = E.a(link_str, href=href_str)

        if self.label:
            self._wrap_with_label_simple(ctx, cls, anchor, parent, name)
        else:
            parent.write(anchor)

        if self.hidden:
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)

    def any_html_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls = self._get_cls(cls)

        if isinstance(inst, six.string_types):
            inst = html.fromstring(inst)

        if inst is None:
            inst = ''

            cls_attr = self.get_cls_attrs(cls)
            if cls_attr.min_occurs == 0:
                return

        if self.label:
            label = self._gen_label_for(ctx, cls, name)
            attrib = self._gen_label_wrapper_class(ctx, cls, name)

            with parent.element('div', attrib=attrib):
                parent.write(label)
                parent.write(inst)

        else:
            parent.write(inst)

        if self.hidden:
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)


class ComplexRenderWidget(HtmlWidget):
    type_attrs = dict(validate_freq=False)

    def __init__(self, text_field=None, id_field=None, type=None,
                             hidden_fields=None, label=True, null_str='[NULL]'):
        """A widget that renders complex objects as links.

        :param text_field: The name of the field containing a human readable
            string that represents the object.
        :param id_field: The name of the field containing the unique identifier
            of the object.
        :param type: If not `None`, overrides the object type being rendered.
            Useful for e.g. combining multiple fields to one field.
        :param hidden_fields: A sequence of field names that will be rendered as
            hidden <input> tags.
        :param label: If ``True``, a ``<label>`` tag is generated for the
            relevant widget id.
        """

        super(ComplexRenderWidget, self).__init__(label=label)

        self.id_field = id_field
        self.text_field = text_field
        self.hidden_fields = hidden_fields
        self.type = type
        self.null_str = null_str

        self.serialization_handlers = cdict({
            ComplexModelBase: self.complex_model_to_parent,
        })

    def _prep_inst(self, cls, inst, fti):
        id_name = id_type = id_str = None
        if self.id_field is not None:
            id_name = self.id_field
            id_type = fti[id_name]

        text_str = text_type = None
        text_name = self.text_field
        if text_name is not None:
            text_str = self.null_str
            text_type = fti[text_name]

        if inst is not None:
            if id_name is not None:
                id_val = getattr(inst, id_name)
                id_str = self.to_unicode(id_type, id_val)

            if text_name is not None:
                text_val = getattr(inst, text_name)
                text_str = self.to_unicode(text_type, text_val)

        if id_str is None:
            id_str = ""
        if text_str is None:
            text_str = ""

        return id_str, text_str

    def _write_hidden_fields(self, ctx, cls, inst, parent, name, fti, **kwargs):
        if self.hidden_fields is not None:
            for key in self.hidden_fields:
                self._gen_input_hidden(fti[key], getattr(inst, key, None),
                            parent, self.hier_delim.join((name, key)), **kwargs)

    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if self.type is not None:
            logger.debug("ComplexRenderWidget.type cls switch: %r => %r",
                                                                 cls, self.type)
            cls = self.type
            if len(self.type_attrs) > 0:
                cls = self.type.customize(**self.type_attrs)

        fti = cls.get_flat_type_info(cls)
        _, text_str = self._prep_inst(cls, inst, fti)

        if self.label:
            elt_id = self._gen_input_elt_id(name, **kwargs)
            label = self._gen_label_for(ctx, cls, name, elt_id)
            attrib = self._gen_label_wrapper_class(ctx, cls, name)
            with parent.element('div', attrib=attrib):
                parent.write(label)
                parent.write(text_str)

        else:
            parent.write(text_str)

        self._write_hidden_fields(ctx, cls, inst, parent, name, fti, **kwargs)


class ComplexHrefWidget(ComplexRenderWidget):
    def __init__(self, text_field, id_field, type=None, hidden_fields=None,
                                       empty_widget=None, label=True, url=None):
        """Widget that renders complex objects as links. Hidden fields are
        skipped then the given instance has the value of `id_field` is `None`.

        Please see :class:`ComplexRenderWidget` docstring for more info.

        :param empty_widget: The widget to be used when the value of the
            instance to be rendered is `None`.
        """
        super(ComplexHrefWidget, self).__init__(text_field, id_field,
                            type=type, hidden_fields=hidden_fields, label=label)

        self.empty_widget = empty_widget
        self.url = url

        if isclass(empty_widget):
            assert issubclass(empty_widget, ComplexRenderWidget), "I don't know" \
                         "how to instantiate a non-ComplexRenderWidget-subclass"

            self.empty_widget = empty_widget(self.text_field, self.id_field,
                      others=True, others_order_by=self.text_field, label=False)

    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        fti = cls.get_flat_type_info(cls)
        id_str, text_str = self._prep_inst(cls, inst, fti)

        attrib = {}
        label_div_attrib = {}

        label = None
        if self.label:
            label = self._gen_label_for(ctx, cls, name, "")
            label_div_attrib = {
                'class': '%s %s' % (
                        self.DEFAULT_ANCHOR_WRAPPER_CLASS, cls.get_type_name())
            }

        if id_str != "":
            tn_url = self.url
            if tn_url is None:
                tn = cls.get_type_name()
                tn_url = camel_case_to_uscore(tn)
            attrib['href'] = tn_url + "?" + urlencode({self.id_field: id_str})

            a_tag = E.a(text_str, **attrib)
            if self.label:
                parent.write(E.div(label, a_tag, **label_div_attrib))
            else:
                parent.write(a_tag)

            self._write_hidden_fields(ctx, cls, inst, parent, name, fti, **kwargs)

        elif self.empty_widget is not None:
            if self.label:
                with parent.element('div', attrib=label_div_attrib):
                    parent.write(label)
                    self.empty_widget \
                        .to_parent(ctx, cls, inst, parent, name, **kwargs)
            else:
                self.empty_widget \
                    .to_parent(ctx, cls, inst, parent, name, **kwargs)


# FIXME: We need a better explanation for the very simple thing that
# override_parent does.
class SelectWidgetBase(ComplexRenderWidget):
    def __init__(self, text_field, id_field, hidden_fields=None, label=True,
                   type=None, inst_type=None, others=None, others_order_by=None,
                    override_parent=False, nonempty_widget=ComplexRenderWidget):
        """Widget that renders complex objects as <select> tags.

        Please see :class:`ComplexRenderWidget` docstring for more info.

        :param others: When `True` fetches all values from the corresponding
            persistence backend entity and adds them as options.

        :param others_order_by: When not `None`, requests an ordered result set
            from the database order by the field name(s) given in this field.
            If given as a string, it's treated as one argument whereas given
            as a list or a tuple of strings, it's treated as multiple field
            names.

        :param override_parent: Overrides parent's name with the names from
            ComboBox.

        :param nonempty_widget: The widget to be used for non-null instances of
            classes with ``write_once`` attribute set.

        :param type: Force class type to given type.

        :param inst_type: Also force instance type to given type. Defaults to
            whatever passed in as ``type``.
        """

        super(SelectWidgetBase, self).__init__(id_field=id_field,
                             text_field=text_field, hidden_fields=hidden_fields,
                                                         label=label, type=type)

        self.others = others
        if callable(others):
            argspec = getargspec(others)
            assert argspec.varargs is not None or len(argspec.args) >= 2, \
                "The callable passed to 'others' must accept at least 2 " \
                "arguments: Instances of 'MethodContext' and 'ComboBoxWidget'."

        self.others_order_by = others_order_by
        self.override_parent = override_parent
        self.inst_type = inst_type
        if inst_type is None:
            self.inst_type = type

        self.nonempty_widget = nonempty_widget
        if isclass(nonempty_widget):
            assert issubclass(nonempty_widget, ComplexRenderWidget), \
                         "I don't know" \
                         "how to instantiate a non-ComplexRenderWidget-subclass"

            self.nonempty_widget = nonempty_widget(self.text_field,
                    id_field=self.id_field, label=self.label, type=self.type,
                         hidden_fields=(self.hidden_fields or ()) + (id_field,))

        self.serialization_handlers[ModelBase] = self.model_base_to_parent

    def _write_empty(self, parent):
        parent.write(E.option())

    def _write_select(self, ctx, cls, inst, parent, name, fti, **kwargs):
        raise NotImplementedError()

    def _write_select_impl(self, ctx, cls, tag_attrib, data, fti, parent):
        attr = self.get_cls_attrs(cls)

        with parent.element("select", attrib=tag_attrib):
            if self.others is None:
                for v_id_str, v_text_str in data:
                    elt = E.option(v_text_str, value=v_id_str, selected="")
                    parent.write(elt)
                return

            we_have_empty = False
            if attr.min_occurs == 0:
                self._write_empty(parent)
                we_have_empty = True

            is_callable = callable(self.others)
            is_iterable = isinstance(self.others, collections.Iterable)
            is_autogen = (self.others is True)

            if not any((is_callable, is_iterable, is_autogen)):
                return

            selected = False
            if is_autogen:
                logger.debug("Auto-generating combobox contents for %r", cls)
                db = ctx.app.config.stores['sql_main'].itself
                # FIXME: this blocks the reactor
                with closing(db.Session()) as session:
                    q = session.query(cls.__orig__ or cls)
                    if self.others_order_by is not None:
                        if isinstance(self.others_order_by, (list, tuple)):
                            q = q.order_by(*self.others_order_by)
                        else:
                            q = q.order_by(self.others_order_by)

                    selected = self._write_options(cls, parent, fti, q, data)

            elif is_iterable or is_callable:
                insts = self.others
                if is_callable:
                    insts = self.others(ctx, self)
                    logger.debug("Generating select contents from callable "
                                                                  "for %r", cls)
                else:
                    logger.debug("Generating select contents from iterable "
                                                                  "for %r", cls)

                selected = self._write_options(cls, parent, fti, insts, data)

            else:
                raise Exception("This should not be possible")

            if not (we_have_empty or selected):
                self._write_empty(parent)

    def _write_options(self, cls, parent, fti, insts, data):
        selected = False
        data = set((i for (i,t) in data))
        for o in insts:
            id_str, text_str = self._prep_inst(cls, o, fti)

            elt = E.option(text_str, value=id_str)
            if id_str in data:
                elt.attrib['selected'] = ""
                selected = True

            parent.write(elt)

        return selected

    def model_base_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attr = self.get_cls_attrs(cls)

        parent_cls, parent_inst, parent_fromarr = ctx.protocol.inst_stack[-2]

        if self.override_parent and cls is not parent_cls:
            logger.debug("ComboBoxWidget.override_parent "
                                        "cls switch: %r => %r", cls, parent_cls)

            parent_name = name.rsplit(self.hier_delim, 1)[0]
            kwargs['from_arr'] = parent_fromarr

            if inst is not None and self.nonempty_widget is not None:
                return self.nonempty_widget.to_parent(ctx,
                         parent_cls, parent_inst, parent, parent_name, **kwargs)

            return self.complex_model_to_parent(ctx,
                         parent_cls, parent_inst, parent, parent_name, **kwargs)

        if cls_attr.write_once and inst is not None:
            return self._gen_input_hidden(cls, inst, parent, name, **kwargs)

        return self.not_supported(ctx, cls, inst, parent, name, **kwargs)

    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attr = self.get_cls_attrs(cls)

        if inst is not None and cls_attr.write_once:
            return self.nonempty_widget.to_parent(ctx, cls, inst, parent,
                                                                 name, **kwargs)

        if self.type is not None:
            logger.debug("ComboBoxWidget.type cls switch: %r => %r",
                                                                 cls, self.type)
            cls = self.type

            if len(self.type_attrs) > 0:
                cls = self.type.customize(**self.type_attrs)

        if self.inst_type is not None:
            logger.debug("ComboBoxWidget.type inst switch: %r => %r",
                                                             cls, self.type)

            inst = self.type.init_from(inst)

        self.cm_to_parent_impl(ctx, cls, inst, parent, name, **kwargs)

    def cm_to_parent_impl(self, ctx, cls, inst, parent, name, **kwargs):
        fti = cls.get_flat_type_info(cls)

        if self.label:
            elt_id = self._gen_input_elt_id(name, **kwargs)
            label = self._gen_label_for(ctx, cls, name, elt_id)
            attrib = self._gen_label_wrapper_class(ctx, cls, name)
            with parent.element('div', attrib=attrib):
                parent.write(label)
                self._write_select(ctx, cls, inst, parent, name, fti, **kwargs)

        else:
            self._write_select(ctx, cls, inst, parent, name, fti, **kwargs)

        self._write_hidden_fields(ctx, cls, inst, parent, name, fti, **kwargs)


class ComboBoxWidget(SelectWidgetBase):
    def _write_select(self, ctx, cls, inst, parent, name, fti, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        v_id_str, v_text_str = self._prep_inst(cls, inst, fti)

        sub_name = self.hier_delim.join((name, self.id_field))
        elt_attrs = self._gen_input_attrs_novalue(ctx, cls, sub_name, cls_attrs,
                                                                       **kwargs)
        data = ((v_id_str, v_text_str),)

        self._write_select_impl(ctx, cls, elt_attrs, data, fti, parent)


class MultiSelectWidget(SelectWidgetBase):
    supported_types = (Array,)

    def cm_to_parent_impl(self, ctx, cls, inst, parent, name, **kwargs):
        if issubclass(cls, Array):
            cls = next(iter(cls._type_info.values()))

        super(MultiSelectWidget, self).to_parent_impl(ctx, cls, inst,
                                                         parent, name, **kwargs)

    def _write_select(self, ctx, cls, inst, parent, name, fti, **kwargs):
        cls_attr = self.get_cls_attrs(cls)

        data = []
        for subinst in inst:
            data.add(self._prep_inst(cls, subinst, fti))

        if self.override_parent:
            name = name.rsplit(self.hier_delim)[0]

        sub_name = self.hier_delim.join((name, self.id_field))
        tag_attrib = self._gen_input_attrs_novalue(ctx, cls, sub_name, cls_attr,
                                                                       **kwargs)

        tag_attrib['multiple'] = ""
        self._write_select_impl(ctx, cls, tag_attrib, data, fti, parent)

    def _write_empty(self, parent):
        pass


class SimpleReadableNumberWidget(SimpleRenderWidget):
    def __init__(self, label=True, type=None, hidden=False):
        super(SimpleReadableNumberWidget, self).__init__(label=label,
                                                         type=type, hidden=hidden)

        self.serialization_handlers = cdict({
            Decimal: self.number_to_parent,
        })

    def number_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if inst is None:
            return

        locale.setlocale(locale.LC_ALL, 'en_US')
        valstr = locale.format("%d", inst, grouping=True)

        if self.label:
            label = self._gen_label_for(ctx, cls, name)
            attrib = self._gen_label_wrapper_class(ctx, cls, name)
            with parent.element('div', attrib=attrib):
                parent.write(label)
                parent.write(valstr)

        else:
            parent.write(valstr)

        if self.hidden:
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)


class TrueFalseWidget(SimpleRenderWidget):
    SYM_TRUE = u"✔"
    SYM_FALSE = u"✘"
    SYM_NONE = u"●"

    def __init__(self, label=True, type=None, hidden=False, center=False,
                        color=True, color_true='green', color_false='red',
                         color_none='gray', addtl_css="text-decoration: none;"):
        super(TrueFalseWidget, self).__init__(label=label, type=type, hidden=hidden)

        self.center = center
        self.color = color

        self.color_true = color_true
        self.color_false = color_false
        self.color_none = color_none

        self.addtl_css = addtl_css

    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if self.type is not None:
            cls = self.type

        if self.color:
            if inst is None:
                elt = E.span(self.SYM_NONE,
                    style="{}color:{}".format(self.addtl_css, self.color_none),
                    **{"class": "widget-none widget-none-color"}
                )
            elif inst:
                elt = E.span(self.SYM_TRUE,
                    style="{}color:{}".format(self.addtl_css, self.color_true),
                    **{"class": "widget-true widget-true-color"}
                )

            else:
                elt = E.span(self.SYM_FALSE,
                    style="{}color:{}".format(self.addtl_css, self.color_false),
                    **{"class": "widget-false widget-false-color"}
                )
        else:
            if inst is None:
                elt = E.span(self.SYM_NONE,
                    style=self.addtl_css,
                    **{"class": "widget-none widget-none-dull"})

            elif inst:
                elt = E.span(self.SYM_TRUE,
                    style=self.addtl_css,
                    **{"class": "widget-true widget-true-dull"})
            else:
                elt = E.span(self.SYM_FALSE,
                    style=self.addtl_css,
                    **{"class": "widget-false widget-false-dull"})

        style = "display:inline-block; width: 100%; background: transparent"
        if self.center:
            style += "text-align:center"

        elt = E.div(elt, style=style)

        if self.label:
            label = self._gen_label_for(ctx, cls, name)
            attrib = self._gen_label_wrapper_class(ctx, cls, name)
            with parent.element('div', attrib=attrib):
                parent.write(label)
                parent.write(elt)

        else:
            parent.write(elt)

        if self.hidden:
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)
