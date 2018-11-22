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

from __future__ import print_function

import logging
logger = logging.getLogger(__name__)

import re
import locale
import collections

from spyne import D
from random import choice
from contextlib import closing
from inspect import isclass, getargspec

from lxml import html
from lxml.builder import E

from spyne import Unicode, Decimal, Boolean, ComplexModelBase, Array, File, \
    ModelBase, AnyHtml, AnyUri, Integer
from spyne.util import six
from spyne.util.tdict import tdict
from spyne.util.oset import oset
from spyne.util.cdict import cdict
from spyne.util.six.moves.urllib.parse import urlencode

from spyne.protocol.html import HtmlBase
from spyne.protocol.html.table.column import HtmlColumnTableRowProtocol


def camel_case_to_uscore_gen(string):
    for i, s in enumerate(string):
        if s.isupper():
            if i > 0:
                yield "_"
            yield s.lower()
        else:
            yield s


camel_case_to_uscore = lambda s: ''.join(camel_case_to_uscore_gen(s))


def _gen_html5_epsilon():
    """See paragraph 17 at:

    https://www.w3.org/TR/2012/WD-html5-20121025/common-microsyntaxes.html
                                 #rules-for-parsing-floating-point-number-values
    """
    import math
    return D('1e%s' % int(math.log(2 ** (-1024)) / math.log(10)))


class HtmlFormWidget(HtmlBase):
    DEFAULT_INPUT_WRAPPER_CLASS = 'label-input-wrapper'
    DEFAULT_ANCHOR_WRAPPER_CLASS = 'label-anchor-wrapper'

    WRAP_FORWARD = type("WRAP_FORWARD", (object,), {})
    WRAP_REVERSED = type("WRAP_REVERSED", (object,), {})

    HTML5_EPSILON = _gen_html5_epsilon()
    HTML_FORM = 'form'
    HTML_INPUT = 'input'
    HTML_TEXTAREA = 'textarea'
    HTML_SELECT = 'select'
    HTML_OPTION = 'option'
    HTML_CHECKBOX_TAG = 'input'

    def __init__(self, app=None, encoding='utf8',
            ignore_uncap=False, ignore_wrappers=False,
                cloth=None, cloth_parser=None, polymorphic=True, hier_delim='.',
                     label=True, doctype=None, placeholder=None,
               input_class=None, input_div_class=None, input_wrapper_class=None,
                                                   label_class=None, type=None):

        super(HtmlFormWidget, self).__init__(app=app, encoding=encoding,
            doctype=doctype,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                                                          hier_delim=hier_delim)
        self.label = label
        self.placeholder = placeholder
        self._init_input_vars(input_class, input_div_class,
                                               input_wrapper_class, label_class)

        self.use_global_null_handler = False
        self.type = type

    def _init_input_vars(self, input_class, input_div_class,
                                              input_wrapper_class, label_class):
        self.input_class = input_class
        self.input_div_class = input_div_class
        self.input_wrapper_class = input_wrapper_class
        if self.input_wrapper_class is None:
            self.input_wrapper_class = self.DEFAULT_INPUT_WRAPPER_CLASS
        self.label_class = label_class

    def to_subprot(self, ctx, cls, inst, parent, name, subprot, **kwargs):
        if isinstance(subprot, HtmlFormWidget):
            if subprot.input_class is None:
                subprot.input_class = self.input_class

            if subprot.input_wrapper_class == self.DEFAULT_INPUT_WRAPPER_CLASS:
                subprot.input_wrapper_class = self.input_wrapper_class

            if subprot.label_class is None:
                subprot.label_class = self.label_class

        return super(HtmlFormWidget, self).to_subprot(ctx, cls, inst, parent,
                                                        name, subprot, **kwargs)

    @staticmethod
    def _format_js(lines, **kwargs):
        js = []
        for i, line in enumerate(lines):
            js.append(lines[i] % kwargs)

        return E.script("$(function(){\n\t%s\n});" % '\n\t'.join(js),
                                                        type="text/javascript")

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

    def _wrap_with_label(self, ctx, cls, name, input_elt, no_label=False,
                                             wrap_label=WRAP_FORWARD, **kwargs):
        input_id = input_elt.attrib['id']
        if self.input_div_class is not None:
            input_elt = E.div(input_elt, **{'class': self.input_div_class})

        attrib = self._gen_label_wrapper_class(ctx, cls, name)

        cls_attrs = self.get_cls_attrs(cls)
        wants_no_label = cls_attrs.label is False or no_label or not self.label
        if wants_no_label:
            if wrap_label is None:
                retval = input_elt
            else:
                retval = E.div(input_elt, **attrib)

        else:
            label_attrib = {'for': input_id}
            if self.label_class is not None:
                label_attrib['class'] = self.label_class

            retval = E.label(self.trc(cls, ctx.locale, name), **label_attrib)
            if wrap_label is HtmlFormWidget.WRAP_FORWARD:
                retval = E.div(retval, input_elt, **attrib)

            elif wrap_label is HtmlFormWidget.WRAP_REVERSED:
                retval = E.div(input_elt, retval, **attrib)

            elif wrap_label is None:
                pass

            else:
                raise ValueError(wrap_label)

        return retval

    def _write_elt_with_label(self, ctx, cls, parent, name, elt):
        label = self._gen_label_for(ctx, cls, name)
        attrib = self._gen_label_wrapper_class(ctx, cls, name)
        with parent.element('div', attrib=attrib):
            parent.write(label)
            parent.write(elt)

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

    def _gen_input(self, ctx, cls, inst, name, cls_attrs, tag=None, **kwargs):
        elt_attrs = self._gen_input_attrs(ctx, cls, inst, name, cls_attrs,
                                                                       **kwargs)
        if tag is None:
            tag = self.HTML_INPUT

        values = cls_attrs.values

        if values is not None and len(values) > 0:
            tag = self.HTML_SELECT
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

        return self._gen_options(ctx, cls, inst, name, cls_attrs, elt, **kwargs)

    def _gen_options(self, ctx, cls, inst, name, cls_attrs, elt, **kwargs):
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
            self._append_option(elt, inst_label, inststr)

        else:
            ever_selected = False
            we_have_empty = False

            if cls_attrs.nullable or cls_attrs.min_occurs == 0:
                self._append_option(elt, '', value='')
                we_have_empty = True
                # if none are selected, this will be the default anyway, so
                # no need to add selected attribute to the option tag.

            # FIXME: cache this!
            i = 0
            for i, v in enumerate(cls_attrs.values):
                selected = False
                valstr = self.to_unicode(cls, v)
                if valstr is None:
                    valstr = ""

                if inst == v:
                    ever_selected = True
                    selected = True

                val_label = values_dict.get(v, valstr)
                logger.debug("\t\tother values inst %r label %r", v, val_label)
                if isinstance(val_label, dict):
                    val_label = self.trd(val_label, ctx.locale, valstr)

                self._append_option(elt, val_label, valstr,
                                                     selected=selected, index=i)

            if not (ever_selected or we_have_empty):
                self._append_option(elt, label='', value='', selected=True,
                                                                        index=i)

            return elt

    def _append_option(self, parent, label, value, selected=False, index=-1):
        attrib = dict(value=value)
        if selected:
            attrib['selected'] = ''

        parent.append(E(self.HTML_OPTION, label, **attrib))

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
            tag = self.HTML_TEXTAREA

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
    def _apply_number_constraints(cls_attrs, elt, epsilon):
        if cls_attrs.max_str_len != Decimal.Attributes.max_str_len:
            elt.attrib['maxlength'] = str(cls_attrs.max_str_len)

        if cls_attrs.ge != Decimal.Attributes.ge:
            elt.attrib['min'] = str(cls_attrs.ge)

        if cls_attrs.gt != Decimal.Attributes.gt:
            elt.attrib['min'] = str(cls_attrs.gt + epsilon)

        if cls_attrs.le != Decimal.Attributes.le:
            elt.attrib['max'] = str(cls_attrs.le)

        if cls_attrs.lt != Decimal.Attributes.lt:
            elt.attrib['max'] = str(cls_attrs.lt - epsilon)

        if elt.attrib.get('min', None) is None \
                                            and cls_attrs.min_bound is not None:
            elt.attrib['min'] = str(cls_attrs.min_bound)

        if elt.attrib.get('max', None) is None \
                                            and cls_attrs.max_bound is not None:
            elt.attrib['max'] = str(cls_attrs.max_bound)

    def _switch_to_prot_type(self, cls, inst):
        if self.type is not None and not (cls is self.type):
            cls = self.type
            if len(self.type_attrs) > 0:
                cls = self.type.customize(**self.type_attrs)

        return cls, inst

    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        newcls, newinst = self._switch_to_prot_type(cls, inst)
        if newcls is cls:
            return self.not_supported(ctx, cls)
        return self.to_parent(ctx, newcls, newinst, parent, name, **kwargs)


class ConditionalRendererBase(HtmlFormWidget):
    def __init__(self):
        super(ConditionalRendererBase, self).__init__()

        self.serialization_handlers = cdict({
            ModelBase: self.model_base_to_parent,
        })

    def switch_to_subprot(self, ctx, cls, inst, parent, name, subprot=None,
                                                                      **kwargs):
        if subprot is None:
            subprot = ctx.protocol.prot_stack[-2]

        logger.debug("Subprot switch from %r back to parent prot %r",
                                                                  self, subprot)

        return self.to_subprot(ctx, cls, inst, parent, name, subprot, **kwargs)

    def model_base_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if self.cond(ctx, cls, inst):
            return self.true(ctx, cls, inst, parent, name, **kwargs)
        else:
            return self.false(ctx, cls, inst, parent, name, **kwargs)

    def cond(self, ctx, cls, inst):
        return choice([True, False])

    def true(self, ctx, cls, inst, parent, name, **kwargs):
        return self.switch_to_subprot(ctx, cls, inst, parent, name, **kwargs)

    def false(self, ctx, cls, inst, parent, name, **kwargs):
        return self.switch_to_subprot(ctx, cls, inst, parent, name, **kwargs)


# TODO: Make label optional
class PasswordWidget(HtmlFormWidget):
    def __init__(self, *args, **kwargs):
        super(PasswordWidget, self).__init__(*args, **kwargs)

        self.serialization_handlers = cdict({
            Unicode: self.unicode_to_parent,
            ComplexModelBase: self.complex_model_to_parent,
        })

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs, elt = self._gen_input_unicode(ctx, cls, inst, name, **kwargs)
        elt.attrib['type'] = 'password'
        parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))


class HrefWidget(HtmlFormWidget):
    supported_types = (Unicode, Decimal)

    def __init__(self, href=None, hidden_input=False, label=True, quote=None,
                                                             anchor_class=None):
        """Render current object (inst) as an anchor (the <a> tag)

        :param href: Base HREF for Anchor. Can only be None when
            inst is an instance of AnyUri.Value
        :param hidden_input: If True, generate hidden <input> with inst as value
        :param label: If True, Generate <label> element.
        :param quote: If not None, should be a callable like ``quote_plus``
            to make sure arbitrary strings get properly escaped as query string
            parameters.
        :param anchor_class: If not None, goes into the "class" attribute of
            the <a> tag.
        """

        super(HrefWidget, self).__init__(label=label)

        self.href = href
        self.hidden_input = hidden_input
        self.anchor_class = anchor_class
        self.quote = quote

        self.serialization_handlers = cdict({
            ModelBase: self.model_base_to_parent,
            AnyUri: self.any_uri_to_parent,
            ComplexModelBase: self.not_supported,
        })

    def model_base_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        assert self.href is not None

        anchor_str = self.to_unicode(cls, inst)
        if anchor_str is None:
            anchor_str = ''

        try:
            if self.quote is not None:
                inst = self.quote(inst)

            href = self.href.format(inst)

        except Exception as e:
            logger.warning("Error generating href: %r", e)
            href = self.href

        self.render_anchor(ctx, cls, inst, parent, name, anchor_str, href,
                                                                      **kwargs)

    def render_anchor(self, ctx, cls, inst, parent, name, anchor_str, href,
                                                                      **kwargs):
        elt = E.a(anchor_str)
        if href is not None:
            elt.attrib['href'] = href

        if self.anchor_class is not None:
            elt.attrib['class'] = self.anchor_class

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

    def any_uri_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        retval = self.gen_anchor(cls, inst, name, self.anchor_class)
        parent.write(retval)


class ParentHrefWidget(HrefWidget):
    """Render current object as a link using information from its parent
    object.

    An example href value:
        "/some_slug?id={0.id}&name={0.name}

    **FIXME:** This needs to be made to use urlencode instead of plain string
    formatting.
    """

    supported_types = (Unicode, Decimal)

    def model_base_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        anchor_str = self.to_unicode(cls, inst)
        if anchor_str is None:
            anchor_str = ''

        inst_stack = ctx.protocol.inst_stack
        if len(inst_stack) < 2:
            logger.warning("No parent instance found.")
            href = self.href

        else:
            _, parent_inst, _ = inst_stack[-2]

            try:
                href = self.href.format(parent_inst)
            except Exception as e:
                logger.warning("Error generating href: %r", e)
                href = self.href

        self.render_anchor(ctx, cls, inst, parent, name, anchor_str, href,
                                                                      **kwargs)


class SimpleRenderWidget(HtmlFormWidget):
    def __init__(self, label=True, type=None, hidden=False, elt=None):
        super(SimpleRenderWidget, self).__init__(label=label)

        self.elt = elt
        self.type = type
        self.hidden = hidden
        self.serialization_handlers = cdict({
            ModelBase: self.model_base_to_parent,
            AnyHtml: self.any_html_to_parent,
            AnyUri: self.any_uri_to_parent,
            ComplexModelBase: self.complex_model_to_parent,
        })

    def _gen_text_str(self, cls, inst, **kwargs):
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
        newcls, newinst = self._switch_to_prot_type(cls, inst)
        if not (newcls is cls):
            return self.to_parent(ctx, newcls, newinst, parent, name, **kwargs)

        text_str = self._gen_text_str(cls, inst, **kwargs)
        if text_str is None:
            return

        if self.label:
            self._wrap_with_label_simple(ctx, cls, text_str, parent, name)
        else:
            if self.elt is not None:
                parent.write(E(self.elt.tag, text_str, **self.elt.attrib))
            else:
                parent.write(text_str)

        if self.hidden:
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)

    def any_uri_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        newcls, newinst = self._switch_to_prot_type(cls, inst)
        if not (newcls is cls):
            return self.to_parent(ctx, newcls, newinst, parent, name, **kwargs)

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
        newcls, newinst = self._switch_to_prot_type(cls, inst)
        if not (newcls is cls):
            return self.to_parent(ctx, newcls, newinst, parent, name, **kwargs)

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


class ComplexRenderWidget(HtmlFormWidget):
    type_attrs = dict(validate_freq=False)

    def __init__(self, text_field=None, id_field=None, type=None,
           hidden_fields=None, label=True, null_str='[NULL]', input_class=None):
        """A widget base that renders complex objects as simple html elements.

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

        super(ComplexRenderWidget, self).__init__(label=label,
                                                        input_class=input_class)

        if not six.PY2:
            str_types = (str,)
        else:
            str_types = (str, unicode)

        self.text_field = text_field
        if isinstance(self.text_field, str_types):
            self.text_field = tuple([s for s in self.text_field.split('.')
                                                                 if len(s) > 0])

        self.id_fields = id_field
        if isinstance(self.id_fields, str_types):
            self.id_fields = tuple([s for s in self.id_fields.split('.')
                                                                 if len(s) > 0])

        self.type = type
        self.hidden_fields = hidden_fields
        self.null_str = null_str

        self.serialization_handlers = cdict({
            ComplexModelBase: self.complex_model_to_parent,
        })

    def _get_type(self, cls, field_name):
        assert len(field_name) > 0

        for field_name_fragment in field_name:
            fti = cls.get_flat_type_info(cls)
            cls = fti[field_name_fragment]

        return cls

    def _get_value_str(self, inst_type, inst, field_name):
        assert len(field_name) > 0

        for field_name_fragment in field_name:
            inst = getattr(inst, field_name_fragment)

        return self.to_unicode(inst_type, inst)

    def _prep_inst(self, cls, inst, fti):
        id_name = id_type = id_str = None
        if self.id_fields is not None:
            id_name = self.id_fields
            id_type = self._get_type(cls, id_name)

        text_str = text_type = None
        text_name = self.text_field
        if text_name is not None:
            text_str = self.null_str
            text_type = self._get_type(cls, text_name)

        if inst is not None:
            if id_name is not None:
                id_str = self._get_value_str(id_type, inst, id_name)

            if text_name is not None:
                text_str = self._get_value_str(text_type, inst, text_name)

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
        cls, inst = self._switch_to_prot_type(cls, inst)
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


class ComplexHrefWidget(ComplexRenderWidget, HtmlColumnTableRowProtocol):
    def __init__(self, text_field, id_field, type=None, hidden_fields=None,
                   empty_widget=None, label=True, url=None, id_field_name=None):
        """Widget that renders complex objects as links. Hidden fields are
        skipped then the given instance has the value of `id_field` is `None`.

        Please see :class:`ComplexRenderWidget` docstring for more info.

        :param empty_widget: The widget to be used when the value of the
            instance to be rendered is `None`.
        """
        super(ComplexHrefWidget, self).__init__(text_field, id_field,
                            type=type, hidden_fields=hidden_fields, label=label)

        self.id_field_name = id_field_name
        self.empty_widget = empty_widget
        self.url = url

        if isclass(empty_widget):
            assert issubclass(empty_widget, ComplexRenderWidget), "I don't know" \
                         "how to instantiate a non-ComplexRenderWidget-subclass"

            self.empty_widget = empty_widget(self.text_field, self.id_fields,
                      others=True, others_order_by=self.text_field, label=False)

    def column_table_before_row(self, ctx, cls, inst, parent, name, **kwargs):
        # the ctxstack here is lxml element context, has nothing to do with
        # spyne contexts.

        ctxstack = getattr(ctx.protocol[self], 'array_subprot_ctxstack', [])

        tr_ctx = parent.element('tr')
        tr_ctx.__enter__()
        ctxstack.append(tr_ctx)

        td_ctx = parent.element('td')
        td_ctx.__enter__()
        ctxstack.append(td_ctx)

        ctx.protocol[self].array_subprot_ctxstack = ctxstack

    def column_table_after_row(self, ctx, cls, inst, parent, name, **kwargs):
        ctxstack = ctx.protocol[self].array_subprot_ctxstack

        for elt_ctx in reversed(ctxstack):
            elt_ctx.__exit__(None, None, None)

        del ctxstack[:]

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

            id_field_name = self.id_field_name
            if id_field_name is None:
                id_field_name = '.'.join(self.id_fields)

            attrib['href'] = tn_url + "?" + urlencode({id_field_name: id_str})

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
                     override_parent=False, nonempty_widget=ComplexRenderWidget,
                                                              input_class=None):
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

        :param html_class: When not none, pass as class attribute to the
            ``<input>`` or ``<select>`` element.
        """

        super(SelectWidgetBase, self).__init__(id_field=id_field,
                             text_field=text_field, hidden_fields=hidden_fields,
                                label=label, type=type, input_class=input_class)

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
                    id_field=self.id_fields, label=self.label, type=self.type,
                         hidden_fields=(self.hidden_fields or ()) + (id_field,))

        self.serialization_handlers[ModelBase] = self.model_base_to_parent

    def _write_empty(self, parent):
        parent.write(E(self.HTML_OPTION))

    def _write_select(self, ctx, cls, inst, parent, name, fti, **kwargs):
        raise NotImplementedError()

    def _write_select_impl(self, ctx, cls, tag_attrib, data, fti, parent):
        attr = self.get_cls_attrs(cls)

        with parent.element(self.HTML_SELECT, attrib=tag_attrib):
            if self.others is None:
                for v_id_str, v_text_str in data:
                    elt = E(self.HTML_OPTION, v_text_str, value=v_id_str,
                                                                    selected="")
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
                    # Get class
                    subval_cls = cls.__orig__
                    if subval_cls is None:
                        subval_cls = cls

                    q = session.query(cls.__orig__ or cls)

                    # Apply ordering parameters if possible
                    oob = self.others_order_by
                    oob_id = id(oob)
                    if oob is not None:
                        if not isinstance(oob, (list, tuple)):
                            oob = (oob,)

                        q = q.order_by(*oob)

                    cache_key = (cls.__orig__ or cls, oob_id)
                    selected = self._write_options(ctx, cls, parent, fti, q,
                                                                data, cache_key)

            elif is_iterable or is_callable:
                insts = self.others
                if is_callable:
                    logger.debug("Generating select contents from callable "
                                                                  "for %r", cls)
                    insts = self.others(ctx, self)

                else:
                    logger.debug("Generating select contents from iterable "
                                                                  "for %r", cls)

                selected = self._write_options(ctx, cls, parent, fti, insts,
                                                           data, cache_key=None)

            else:
                raise Exception("This should not be possible")

            if not (we_have_empty or selected):
                self._write_empty(parent)

    def _write_options(self, ctx, cls, parent, fti, insts, data, cache_key):
        selected = False
        data = set((i for (i,t) in data))

        # Generate cache entry
        cache_entry = None
        if cache_key is not None:
            objcache = ctx.protocol.objcache
            cache_entry = objcache.get(cache_key, None)
            if cache_entry is not None:
                logger.debug("Using cache key %r to fill <select> for %r",
                                                                 cache_key, cls)
                for id_str, text_str in cache_entry:
                    elt = E(self.HTML_OPTION, text_str, value=id_str)

                    if id_str in data:
                        elt.attrib['selected'] = ""
                        selected = True

                    parent.write(elt)

                return selected

            logger.debug("Generated cache entry for key %r to fill <select> "
                                                       "for %r", cache_key, cls)

            cache_entry = objcache[cache_key] = []

        # FIXME: this iteration blocks the reactor
        for o in insts:
            id_str, text_str = self._prep_inst(cls, o, fti)

            elt = E(self.HTML_OPTION, text_str, value=id_str)
            if id_str in data:
                elt.attrib['selected'] = ""
                selected = True

            parent.write(elt)
            if cache_entry is not None:
                cache_entry.append( (id_str, text_str) )

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

        sub_name = self.hier_delim.join((name,) + self.id_fields)
        elt_attrs = self._gen_input_attrs_novalue(ctx, cls, sub_name, cls_attrs,
                                                                       **kwargs)
        data = ((v_id_str, v_text_str),)

        self._write_select_impl(ctx, cls, elt_attrs, data, fti, parent)


class MultiSelectWidget(SelectWidgetBase):
    supported_types = (Array,)

    def cm_to_parent_impl(self, ctx, cls, inst, parent, name, **kwargs):
        if issubclass(cls, Array):
            cls = next(iter(cls._type_info.values()))

        super(MultiSelectWidget, self).cm_to_parent_impl(ctx, cls, inst,
                                                         parent, name, **kwargs)

    def _write_select(self, ctx, cls, inst, parent, name, fti, **kwargs):
        cls_attr = self.get_cls_attrs(cls)

        data = []
        for subinst in inst:
            data.add(self._prep_inst(cls, subinst, fti))

        if self.override_parent:
            name = name.rsplit(self.hier_delim)[0]

        sub_name = self.hier_delim.join((name,) + self.id_fields)
        tag_attrib = self._gen_input_attrs_novalue(ctx, cls, sub_name, cls_attr,
                                                                       **kwargs)

        tag_attrib['multiple'] = ""
        self._write_select_impl(ctx, cls, tag_attrib, data, fti, parent)

    def _write_empty(self, parent):
        pass


class SimpleReadableNumberWidget(SimpleRenderWidget):
    def __init__(self, label=True, type=None, hidden=False,
                                                           locale='en_US.utf8'):
        super(SimpleReadableNumberWidget, self).__init__(
                                          label=label, type=type, hidden=hidden)

        self.locale = locale

        self.serialization_handlers = cdict({
            Decimal: self.decimal_to_parent,
            Integer: self.integer_to_parent,
            ComplexModelBase: self.complex_model_to_parent,
        })

    def write_number(self, ctx, cls, inst, parent, name, fstr, **kwargs):
        if inst is None:
            return

        locale.setlocale(locale.LC_ALL, self.locale)
        valstr = locale.format(fstr, inst, grouping=True)

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

    def integer_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls, inst = self._switch_to_prot_type(cls, inst)
        cls_attrs = self.get_cls_attrs(cls)

        fstring = cls_attrs.format
        if fstring is None:
            fstring = "%d"

        self.write_number(ctx, cls, inst, parent, name, fstring, **kwargs)

    def decimal_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls, inst = self._switch_to_prot_type(cls, inst)
        cls_attrs = self.get_cls_attrs(cls)

        fstring = cls_attrs.format
        if fstring is None:
            fstring = "%f"

            if cls_attrs.fraction_digits == D('inf'):
                fd = 2  # FIXME: chosen by fair dice roll
            else:
                fd = int(cls_attrs.fraction_digits)

            if fd is not None:
                fstring = "%%.%df" % fd

        self.write_number(ctx, cls, inst, parent, name, fstring, **kwargs)


class JQFileUploadWidget(SimpleRenderWidget):
    def __init__(self, label=True):
        super(JQFileUploadWidget, self).__init__(label=label)

        self.serialization_handlers = cdict({
            File: self.file_to_parent,
        })

    def file_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        pass


class TrueFalseWidget(SimpleRenderWidget):
    SYM_TRUE = u"✔"
    SYM_FALSE = u"✘"
    SYM_NONE = u"●"

    def __init__(self, label=True, type=None, hidden=False, center=False,
                        color=True, color_true='green', color_false='red',
                        color_none='gray', display='inline-block', width="100%",
                                            addtl_css="text-decoration: none;"):
        super(TrueFalseWidget, self).__init__(label=label, type=type,
                                                                  hidden=hidden)

        self.center = center
        self.color = color

        self.color_true = color_true
        self.color_false = color_false
        self.color_none = color_none

        self.display = display
        self.width = width
        self.addtl_css = addtl_css

    def get_none(self):
        if self.color:
            return E.span(self.SYM_NONE,
                style="{}color:{}".format(self.addtl_css, self.color_none),
                **{"class": "widget-none widget-none-color"}
            )

        else:
            return E.span(self.SYM_NONE,
                style=self.addtl_css,
                **{"class": "widget-none widget-none-dull"}
            )

    def get_true(self):
        if self.color:
            return E.span(self.SYM_TRUE,
                style="{}color:{}".format(self.addtl_css, self.color_true),
                **{"class": "widget-true widget-true-color"}
            )

        else:
            return E.span(self.SYM_TRUE,
                style=self.addtl_css,
                **{"class": "widget-true widget-true-dull"}
            )

    def get_false(self):
        if self.color:
            return E.span(self.SYM_FALSE,
                style="{}color:{}".format(self.addtl_css, self.color_false),
                **{"class": "widget-false widget-false-color"}
            )

        else:
            elt = E.span(self.SYM_FALSE,
                style=self.addtl_css,
                **{"class": "widget-false widget-false-dull"}
            )

    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if self.type is not None:
            cls = self.type

        if inst is None:
            elt = self.get_none()

        elif inst:
            elt = self.get_true()

        else:
            elt = self.get_false()

        styles = ["background: transparent"]
        if self.width:
            styles.append("width: 100%")
        if self.display:
            styles.append("display: %s" % (self.display,))
        if self.center:
            styles.append("text-align:center;")

        elt = E.div(elt, style=';'.join(styles))

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
