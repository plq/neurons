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

from collections import namedtuple
from inspect import isgenerator, isclass
from decimal import Decimal as D
from spyne.util.oset import oset

from lxml import html
from lxml.builder import E

from spyne import ComplexModelBase, Unicode, Decimal, Boolean, Date, Time, \
    DateTime, Integer, Duration, PushBase, Array, MethodContext
from spyne.protocol.html import HtmlBase
from spyne.util import coroutine, Break
from spyne.util.cdict import cdict
from spyne.util.six.moves.urllib.parse import urlencode
from spyne.server.http import HttpTransportContext


SOME_COUNTER = 0


class Fieldset(namedtuple('Fieldset', 'legend tag attrib index htmlid')):
    def __new__(cls, legend=None, tag='fieldset', attrib={}, index=None,
                                                                   htmlid=None):
        global SOME_COUNTER
        if htmlid is None:
            htmlid = 'fset' + str(SOME_COUNTER)
            SOME_COUNTER += 1

        return super(Fieldset, cls).__new__(cls, legend, tag, attrib, index,
                                                                         htmlid)

class Tab(namedtuple('Tab', 'legend attrib index htmlid')):
    def __new__(cls, legend=None, attrib={}, index=None, htmlid=None):
        global SOME_COUNTER
        if htmlid is None:
            htmlid = "tab" + str(SOME_COUNTER)
            SOME_COUNTER += 1

        return super(Tab, cls).__new__(cls, legend, attrib, index, htmlid)


def camel_case_to_uscore_gen(string):
    for i, s in enumerate(string):
        if s.isupper():
            if i > 0:
                yield "_"
            yield s.lower()
        else:
            yield s


camel_case_to_uscore = lambda s: ''.join(camel_case_to_uscore_gen(s))


def _gen_array_js(parent, key):
    parent.write(E.script("""
$(function() {
    var field_name = "." + "%(field_name)s";

    var add = function() {
        var f = $($(field_name)[0]).clone();
        f.appendTo($(field_name).parent());
        f.find(".%(field_name)s_btn_add").click(add);
        f.find(".%(field_name)s_btn_del").click(del);
        return false;
    };

    var del = function(event) {
        if($('#%(field_name)s_container').find('.%(field_name)s').length > 1){
            $(this).parent().remove();
        }
        else{
            $(this).parent().children().val("")
        }
       event.preventDefault();
    };

    $(".%(field_name)s_btn_add").click(add);
    $(".%(field_name)s_btn_del").click(del);
});""" % {"field_name": key}, type="text/javascript"))


WRAP_FORWARD = type("WRAP_FORWARD", (object,), {})
WRAP_REVERSED = type("WRAP_REVERSED", (object,), {})


class HtmlWidget(HtmlBase):
    supported_types = None

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

    @classmethod
    def _check_supported_types(cls, t):
        if cls.supported_types is not None and \
                                      not issubclass(t, cls.supported_types):
            logger.warning("%r claims not to support %r. You have been warned.",
                           cls, t)

    def _check_hidden(self, f):
        def _ch(ctx, cls, inst, parent, name, **kwargs):
            cls_attrs = self.get_cls_attrs(cls)
            if cls_attrs.hidden:
                self._gen_input_hidden(cls, inst, parent, name)
            else:
                f(ctx, cls, inst, parent, name, **kwargs)
        return _ch

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

        return E.label(self.trc(cls, ctx.locale, name), **attrib)

    def _wrap_with_label(self, ctx, cls, name, input, no_label=False,
                                             wrap_label=WRAP_FORWARD, **kwargs):
        retval = input

        attrib = {'class': 'label-input-wrapper'}
        if no_label and wrap_label is not None:
            retval = E.div(retval, **attrib)

        else:
            retval = E.label(self.trc(cls, ctx.locale, name),
                                                  **{'for': input.attrib['id']})
            if wrap_label is WRAP_FORWARD:
                retval = E.div(retval, input, **attrib)
            elif wrap_label is WRAP_REVERSED:
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

    def _gen_input_attrs_novalue(self, cls, name, cls_attrs, **kwargs):
        elt_class = ' '.join(oset([
            camel_case_to_uscore(cls.get_type_name()),
            name.rsplit(self.hier_delim, 1)[-1],
            re.sub(r'\[[0-9]+\]', '', name).replace(self.hier_delim, '__'),
        ]))
        elt_attrs = {
            'id': self._gen_input_elt_id(name, **kwargs),
            'name': self._gen_input_name(name),
            'class': elt_class,
            'type': 'text',
        }

        if getattr(cls_attrs, 'pattern', None) is not None:
            elt_attrs['pattern'] = cls_attrs.pattern

        if cls_attrs.write is False or cls_attrs.primary_key:
            elt_attrs['readonly'] = ""

        # Required bool means, in HTML context, a checkbox that needs to be
        # checked, which is not what we mean here at all.
        if not issubclass(cls, Boolean):
            # We used OR here because html forms send empty values anyway. So a
            # missing value is sent as null as well.
            if cls_attrs.min_occurs >= 1 or cls_attrs.nullable == False:
                elt_attrs['required'] = ''

        return elt_attrs

    def _gen_input_attrs(self, cls, inst, name, cls_attrs, **kwargs):
        elt_attrs = self._gen_input_attrs_novalue(cls, name, cls_attrs, **kwargs)

        if inst is None or isinstance(inst, type):
            # FIXME: this must be done the other way around
            if 'readonly' in elt_attrs and cls_attrs.allow_write_for_null:
                del elt_attrs['readonly']

        else:
            val = self.to_unicode(cls, inst)
            if val is not None:
                elt_attrs['value'] = val

        return elt_attrs

    def _gen_input(self, ctx, cls, inst, name, cls_attrs, **kwargs):
        elt_attrs = self._gen_input_attrs(cls, inst, name, cls_attrs, **kwargs)

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

        if values is not None and len(values) > 0:
            inststr = self.to_unicode(cls, inst)
            if cls_attrs.write is False and inststr is not None:
                inst_label = values_dict.get(inst, inststr)
                if isinstance(inst_label, dict):
                    inst_label = self.trd(inst_label, ctx.locale, inststr)
                elt.append(E.option(inst_label, value=inststr))

            else:
                if cls_attrs.nullable or cls_attrs.min_occurs == 0:
                    elt.append(E.option("", {'value':''}))

                # FIXME: cache this!
                for v in cls_attrs.values:
                    valstr = self.to_unicode(cls, v)
                    if valstr is None:
                        valstr = ""

                    attrib = dict(value=valstr)
                    if inst == v:
                        attrib['selected'] = ''

                    val_label = values_dict.get(v, valstr)
                    logger.debug("\tinst %r label %r", inst, val_label)
                    if isinstance(val_label, dict):
                        val_label = self.trd(val_label, ctx.locale, inststr)

                    elt.append(E.option(val_label, **attrib))

        return elt

    def _gen_input_unicode(self, ctx, cls, inst, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)

        if len(cls_attrs.values) == 0 and cls_attrs.max_len >= D('inf'):
            tag = 'textarea'

            elt_attrs = self._gen_input_attrs_novalue(cls, name, cls_attrs)
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


_jstag = lambda src: E.script(src=src, type="text/javascript")
_csstag = lambda src: E.link(href=src, type="text/css", rel="stylesheet")


class HtmlForm(HtmlWidget):
    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                       cloth=None, attr_name='spyne_id', root_attr_name='spyne',
                            cloth_parser=None, polymorphic=True, hier_delim='.',
                                                                asset_paths={}):

        super(HtmlForm, self).__init__(app=app,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, attr_name=attr_name, root_attr_name=root_attr_name,
                             cloth_parser=cloth_parser, polymorphic=polymorphic,
                                                          hier_delim=hier_delim)

        self.serialization_handlers = cdict({
            Date: self._check_hidden(self.date_to_parent),
            Time: self._check_hidden(self.time_to_parent),
            Array: self.array_type_to_parent,
            Integer: self._check_hidden(self.integer_to_parent),
            Unicode: self._check_hidden(self.unicode_to_parent),
            Decimal: self._check_hidden(self.decimal_to_parent),
            Boolean: self._check_hidden(self.boolean_to_parent),
            Duration: self._check_hidden(self.duration_to_parent),
            DateTime: self._check_hidden(self.datetime_to_parent),
            ComplexModelBase: self.complex_model_to_parent,
        })

        self.hier_delim = hier_delim

        self.asset_paths = {
            ('jquery',): [_jstag("/assets/jquery/1.11.1/jquery.min.js")],
            ('jquery-ui',): [_jstag("/assets/jquery-ui/1.11.0/jquery-ui.min.js")],
            ('jquery-timepicker',): [
                _jstag("/assets/jquery-timepicker/jquery-ui-timepicker-addon.js"),
                _csstag("/assets/jquery-timepicker/jquery-ui-timepicker-addon.css"),
            ],
        }
        self.asset_paths.update(asset_paths)
        self.use_global_null_handler = False

    def _form_key(self, sort_key):
        k, v = sort_key
        attrs = self.get_cls_attrs(v)
        return None if attrs.tab is None else \
                                (attrs.tab.index, attrs.tab.htmlid), \
               None if attrs.fieldset is None else \
                                (attrs.fieldset.index, attrs.fieldset.htmlid), \
               attrs.order, k

    @coroutine
    def start_to_parent(self, ctx, cls, inst,parent, name, **kwargs):
        # FIXME: what a HUGE swath of copy/paste! I want yield from!
        if not getattr(ctx.protocol, 'in_form', False):
            ctx.protocol.in_form = True

            if not (len(ctx.protocol.prot_stack) == 1 and \
                              isinstance(ctx.protocol.prot_stack[0], HtmlForm)):
                name = ''

            attrib = dict(method='POST', enctype="multipart/form-data")
            if hasattr(ctx.protocol, 'form_action'):
                attrib['action'] = ctx.protocol.form_action
                logger.debug("Set form action to '%s'", attrib['action'])
            elif isinstance(ctx.transport, HttpTransportContext):
                attrib['action'] = ctx.transport.get_path()

            with parent.element('form', attrib=attrib):
                ret = super(HtmlForm, self).start_to_parent(ctx, cls, inst,
                                                         parent, name, **kwargs)
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

                    finally:
                        parent.write(E.p(
                            E.input(value="Submit", type="submit",
                                            **{'class': "btn btn-default"}),
                                                    **{'class': "text-center"}))
                        ctx.protocol.in_form = False
                else:
                    parent.write(E.p(
                        E.input(value="Submit", type="submit",
                                        **{'class': "btn btn-default"}),
                                                **{'class': "text-center"}))
                    ctx.protocol.in_form = False

        else:
            ret = super(HtmlForm, self).start_to_parent(ctx, cls, inst, parent,
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

                finally:
                    parent.write(E.p(
                        E.input(value="Submit", type="submit",
                                        **{'class': "btn btn-default"}),
                                                    **{'class': "text-center"}))
            else:
                parent.write(E.p(
                    E.input(value="Submit", type="submit",
                                    **{'class': "btn btn-default"}),
                                            **{'class': "text-center"}))

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs, elt = self._gen_input_unicode(ctx, cls, inst, name, **kwargs)
        parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))

    def decimal_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)
        elt.attrib['type'] = 'number'

        if D(cls.Attributes.fraction_digits).is_infinite():
            elt.attrib['step'] = 'any'
        else:
            elt.attrib['step'] = str(10**(-int(cls.Attributes.fraction_digits)))

        self._apply_number_constraints(cls_attrs, elt)

        parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))

    def boolean_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)

        if 'value' in elt.attrib:
            del elt.attrib['value']
        elt.attrib['type'] = 'checkbox'

        if bool(inst):
            elt.attrib['checked'] = ''

        div = self._wrap_with_label(ctx, cls, name, elt,
                                             wrap_label=WRAP_REVERSED, **kwargs)
        parent.write(div)

    def date_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        ctx.protocol.assets.extend([('jquery',), ('jquery-ui', 'datepicker')])

        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)
        elt.attrib['type'] = 'text'

        if cls_attrs.format is None:
            data_format = 'yy-mm-dd'
        else:
            data_format = cls_attrs.format.replace('%Y', 'yy') \
                                          .replace('%m', 'mm') \
                                          .replace('%d', 'dd')

        code = [
            "$('#%(field_name)s').datepicker();",
            "$('#%(field_name)s').datepicker('option', 'dateFormat', '%(format)s');",
        ]

        if inst is None:
            script = self._format_js(code, field_name=elt.attrib['id'],
                                                             format=data_format)
        else:
            value = self.to_string(cls, inst)
            code.append("$('#%(field_name)s').datepicker('setDate', '%(value)s');")
            script = self._format_js(code, field_name=elt.attrib['id'], value=value,
                                                             format=data_format)

        div = self._wrap_with_label(ctx, cls, name, elt, **kwargs)
        div.append(script)
        parent.write(div)

    def time_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        ctx.protocol.assets.extend([('jquery',), ('jquery-ui', 'datepicker'),
                                                        ('jquery-timepicker',)])

        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)
        elt.attrib['type'] = 'text'

        if cls_attrs.format is None:
            data_format = 'HH:MM:SS'
        else:
            data_format = cls_attrs.format.replace('%H', 'HH') \
                                          .replace('%M', 'MM') \
                                          .replace('%S', 'SS')

        code = [
            "$('#%(field_name)s').timepicker();",
            "$('#%(field_name)s').timepicker('option', 'timeFormat', '%(format)s');",
        ]

        if inst is None:
            script = self._format_js(code, field_name=elt.attrib['id'],
                                                             format=data_format)
        else:
            value = self.to_unicode(cls, inst)
            code.append(
                     "$('#%(field_name)s').timepicker('setDate', '%(value)s');")
            script = self._format_js(code, field_name=elt.attrib['id'], value=value,
                                                             format=data_format)

        div = self._wrap_with_label(ctx, cls, name, elt, **kwargs)
        div.append(script)
        parent.write(div)

    def datetime_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        ctx.protocol.assets.extend([('jquery',), ('jquery-ui', 'datepicker'),
                                                        ('jquery-timepicker',)])

        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, None, name, cls_attrs, **kwargs)
        elt.attrib['type'] = 'text'

        if cls_attrs.format is None:
            data_format = 'yy-mm-dd HH:MM:SS'

        else:
            data_format = cls_attrs.format.replace('%Y', 'yy') \
                                          .replace('%m', 'mm') \
                                          .replace('%d', 'dd') \
                                          .replace('%H', 'HH') \
                                          .replace('%M', 'MM') \
                                          .replace('%S', 'SS')

        code = [
            "$('#%(field_name)s').datetimepicker();",
            "$('#%(field_name)s').datetimepicker('option', 'DateTimeFormat', '%(format)s');",
        ]

        if inst is None:
            script = self._format_js(code, field_name=elt.attrib['id'],
                                                             format=data_format)
        else:
            value = self.to_unicode(cls, inst)
            code.append(
                "$('#%(field_name)s').datetimepicker('setDate', '%(value)s');")
            script = self._format_js(code, field_name=elt.attrib['id'],
                                                format=data_format, value=value)

        div = self._wrap_with_label(ctx, cls, name, elt, **kwargs)
        div.append(script)
        parent.write(div)

    def integer_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)
        elt.attrib['type'] = 'number'

        self._apply_number_constraints(cls_attrs, elt)

        parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))

    # TODO: finish this
    def duration_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, inst, name, cls_attrs, **kwargs)

        parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))

    def array_type_to_parent(self, ctx, cls, inst, parent, name=None, **kwargs):
        v = next(iter(cls._type_info.values()))
        return self.to_parent(ctx, v, inst, parent, name, **kwargs)

    def _gen_tab_headers(self, ctx, fti):
        retval = E.ul()

        tabs = {}
        for k, v in fti:
            subattr = self.get_cls_attrs(v)
            tab = subattr.tab
            if tab is not None and not subattr.exc:
                tabs[id(tab)] = tab

        for i, tab in enumerate(sorted(tabs.values(),
                                            key=lambda t: (t.index, t.htmlid))):
            retval.append(E.li(E.a(
                self.trd(tab.legend, ctx.locale, "Tab %d" % i),
                href="#" + tab.htmlid
            )))

        return retval

    @coroutine
    def _render_complex(self, ctx, cls, inst, parent, name, in_fset, **kwargs):
        global SOME_COUNTER

        fti = self.sort_fields(cls)
        fti.sort(key=self._form_key)

        prev_fset = fset_ctx = fset = None
        prev_tab = tab_ctx = tab = tabview_ctx = None
        tabview_id = None

        # FIXME: hack! why do we have top-level object receiving name?
        if name == cls.get_type_name():
            name = ''

        if in_fset:
            parent.write(E.legend(cls.get_type_name()))

        for k, v in fti:
            subattr = self.get_cls_attrs(v)
            if subattr.exc:
                logger.debug("Excluding %s", k)
                continue

            logger.debug("Generating form element for %s", k)
            subinst = getattr(inst, k, None)

            tab = subattr.tab
            if not (tab is prev_tab):
                if fset_ctx is not None:
                    fset_ctx.__exit__(None, None, None)
                    logger.debug("exiting fset tab %r", prev_fset)

                fset_ctx = prev_fset = None

                if tab_ctx is not None:
                    tab_ctx.__exit__(None, None, None)
                    logger.debug("exiting tab %r", prev_tab)

                if prev_tab is None:
                    logger.debug("entering tabview")
                    tabview_id = 'tabview' + str(SOME_COUNTER)
                    SOME_COUNTER += 1

                    tabview_ctx = parent.element('div',
                                                      attrib={'id': tabview_id})
                    tabview_ctx.__enter__()

                    parent.write(self._gen_tab_headers(ctx, fti))

                logger.debug("entering tab %r", tab)

                attrib = {'id': tab.htmlid}
                attrib.update(tab.attrib)
                tab_ctx = parent.element('div', attrib)
                tab_ctx.__enter__()

                prev_tab = tab

            fset = subattr.fieldset
            if not (fset is prev_fset):
                if fset_ctx is not None:
                    fset_ctx.__exit__(None, None, None)
                    logger.debug("exiting fset norm", prev_fset)

                logger.debug("entering fset %r", fset)
                fset_ctx = parent.element(fset.tag, fset.attrib)
                fset_ctx.__enter__()

                parent.write(E.legend(self.trd(fset.legend, ctx.locale, k)))
                prev_fset = fset

            if name is not None and len(name) > 0:
                child_key = self.hier_delim.join((name, k))
            else:
                child_key = k

            ret = self.to_parent(ctx, v, subinst, parent, child_key, **kwargs)
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

        if fset_ctx is not None:
            fset_ctx.__exit__(None, None, None)
            logger.debug("exiting fset close %r", fset)

        if tab_ctx is not None:
            tab_ctx.__exit__(None, None, None)
            logger.debug("exiting tab close %r", tab)

        if tabview_ctx is not None:
            logger.debug("exiting tabview close")
            tabview_ctx.__exit__(None, None, None)
            parent.write(E.script(
                '$(function(){ $( "#%s" ).tabs(); });' % tabview_id,
                type="text/javascript"
            ))

    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attr = self.get_cls_attrs(cls)

        if cls_attr.fieldset is False or cls_attr.no_fieldset:
            return self._render_complex(ctx, cls, inst, parent, name, False,
                                                                       **kwargs)
        if cls_attr.fieldset or cls_attr.no_fieldset is False:
            with parent.element('fieldset'):
                return self._render_complex(ctx, cls, inst, parent, name, False,
                                                                       **kwargs)

        with parent.element('fieldset'):
            return self._render_complex(ctx, cls, inst, parent, name, True,
                                                                       **kwargs)

    @coroutine
    def _push_to_parent(self, ctx, cls, inst, parent, name, parent_inst=None,
                        label_attrs=None, parent_key=None, no_label=False,
                        **kwargs):
        i = -1
        key = self.selsafe(name)
        attr = self.get_cls_attrs(cls)
        while True:
            with parent.element('div', {"class": key}):
                sv = (yield)

                i += 0
                new_key = '%s[%09d]' % (key, i)
                ret = self.to_parent(ctx, cls, sv, parent, new_key,
                                                from_arr=True, **kwargs)

                if isgenerator(ret):
                    try:
                        while True:
                            sv2 = (yield)
                            ret.send(sv2)
                    except Break as e:
                        try:
                            ret.throw(e)
                        except StopIteration:
                            pass

                        if not attr.no_write:
                            parent.write(E.button('+', **{
                                "class": key + "_btn_add",
                                'type': 'button'
                            }))
                            parent.write(E.button('-', **{
                                "class": key + "_btn_del",
                                'type': 'button'
                            }))

        if not attr.no_write:
            _gen_array_js(parent, key)

    @coroutine
    def _pull_to_parent(self, ctx, cls, inst, parent, name, parent_inst=None,
                        label_attrs=None, parent_key=None, no_label=False,
                        **kwargs):
        key = self.selsafe(name)
        attr = self.get_cls_attrs(cls)

        if inst is None:
            inst = []

        for i, subval in enumerate(inst):
            new_key = '%s[%09d]' % (key, i)
            with parent.element('div', {"class": key}):
                kwargs['from_arr'] = True
                ret = self.to_parent(ctx, cls, subval, parent, new_key,
                                         parent_inst=parent_inst, no_label=True,
                                         **kwargs)
                if not attr.no_write:
                    parent.write(E.button('+', **{
                                  "class": key + "_btn_add", 'type': 'button'}))
                    parent.write(E.button('-', **{
                                  "class": key + "_btn_del", 'type': 'button'}))

                if isgenerator(ret):
                    try:
                        while True:
                            sv2 = (yield)
                            ret.send(sv2)
                    except Break as b:
                        try:
                            ret.throw(b)
                        except StopIteration:
                            pass

        if not attr.no_write:
            _gen_array_js(parent, key)

    def array_to_parent(self, ctx, cls, inst, parent, name, parent_inst=None,
                        label_attrs=None, parent_key=None, no_label=False,
                        **kwargs):

        key = self.selsafe(name)

        with parent.element('div', {"id": key + "_container", 'class':'array'}):
            if isinstance(inst, PushBase):
                return self._push_to_parent(ctx, cls, inst, parent, name,
                                     parent_inst=parent_inst, label_attrs=None,
                                     parent_key=None, no_label=False, **kwargs)

            else:
                return self._pull_to_parent(ctx, cls, inst, parent, name,
                                     parent_inst=parent_inst, label_attrs=None,
                                     parent_key=None, no_label=False, **kwargs)


class PasswordWidget(HtmlWidget):
    supported_types = (Unicode,)

    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        self._check_supported_types(cls)

        cls_attrs, elt = self._gen_input_unicode(ctx, cls, inst, name, **kwargs)
        elt.attrib['type'] = 'password'
        parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))


class HrefWidget(HtmlWidget):
    supported_types = (Unicode, Decimal)

    def __init__(self, href, hidden_input=True):
        super(HrefWidget, self).__init__()

        self.href = href
        self.hidden_input = hidden_input

    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        self._check_supported_types(cls)

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

        parent.write(elt)
        if self.hidden_input:
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)


class SimpleRenderWidget(HtmlWidget):
    def __init__(self, label=True, type=None, hidden=False):
        super(SimpleRenderWidget, self).__init__()

        self.label = label
        self.type = type
        self.hidden = hidden

    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if self.type is not None:
            cls = self.type

        text_str = self.to_unicode(cls, inst, **kwargs)

        if text_str is None:
            text_str = ''

        cls_attr = self.get_cls_attrs(cls)
        if cls_attr.min_occurs == 0:
            return

        if self.label:
            label = self._gen_label_for(ctx, cls, name)
            # this part should be consistent with what _wrap_with_label does
            with parent.element('div', attrib={'class': 'label-input-wrapper'}):
                parent.write(label)
                parent.write(text_str)

        else:
            parent.write(text_str)

        if self.hidden:
            self._gen_input_hidden(cls, inst, parent, name, **kwargs)


class ComplexRenderWidget(HtmlWidget):
    supported_types = (ComplexModelBase,)

    def __init__(self, text_field, id_field=None, type=None, hidden_fields=None,
                                                                    label=True):
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

        self.id_field = id_field
        self.text_field = text_field
        self.hidden_fields = hidden_fields
        self.type = type
        self.label = label
        super(HtmlWidget, self).__init__()

    def _prep_inst(self, cls, inst, fti):
        self._check_supported_types(cls)

        id_name = id_type = id_str = None
        if self.id_field is not None:
            id_name = self.id_field
            id_type = fti[id_name]

        text_name = self.text_field
        text_type = fti[text_name]
        text_str = "[NULL]"

        if inst is not None:
            if id_name is not None:
                id_val = getattr(inst, id_name)
                id_str = self.to_unicode(id_type, id_val)

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

    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        fti = cls.get_flat_type_info(cls)
        _, text_str = self._prep_inst(cls, inst, fti)

        if self.label:
            elt_id = self._gen_input_elt_id(name, **kwargs)
            label = self._gen_label_for(ctx, cls, name, elt_id)
            # this part should be consistent with what _wrap_with_label does
            with parent.element('div', attrib={'class': 'label-input-wrapper'}):
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

            self.empty_widget = empty_widget(self.id_field, self.text_field,
                                   others=True, others_order_by=self.text_field)

    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        fti = cls.get_flat_type_info(cls)
        id_str, text_str = self._prep_inst(cls, inst, fti)

        attrib = {}

        if id_str != "":
            tn_url = self.url
            if tn_url is None:
                tn = cls.get_type_name()
                tn_url = camel_case_to_uscore(tn)
            attrib['href'] = tn_url + "?" + urlencode({self.id_field: id_str})
            parent.write(E.a(text_str, **attrib))

            self._write_hidden_fields(ctx, cls, inst, parent, name, fti, **kwargs)

        elif self.empty_widget is not None:
            self.empty_widget \
                .to_parent(ctx, cls, inst, parent, name, **kwargs)


class ComboBoxWidget(ComplexRenderWidget):
    def __init__(self, text_field, id_field, hidden_fields=None, label=True,
                                 type=None, others=False, others_order_by=None):
        """Widget that renders complex objects as comboboxes.

        Please see :class:`ComplexRenderWidget` docstring for more info.

        :param others: When `True` fetches all values from the corresponding
            persistence backend entity and adds them as options.

        :param others_order_by: When not `None`, requests an ordered result set
            from the database order by the field name(s) given in this field.
            If given as a string, it's treated as one argument whereas given
            as a list or a tuple of strings, it's treated as multiple field
            names.
        """

        super(ComboBoxWidget, self).__init__(id_field=id_field,
                             text_field=text_field, hidden_fields=hidden_fields,
                                                         label=label, type=type)
        self.others = others
        self.others_order_by = others_order_by

    def _write_select(self, ctx, cls, inst, parent, name, fti, **kwargs):
        attr = self.get_cls_attrs(cls)
        v_id_str, v_text_str = self._prep_inst(cls, inst, fti)

        sub_name = self.hier_delim.join((name, self.id_field))
        attrib = self._gen_input_attrs_novalue(cls, sub_name, attr, **kwargs)

        # FIXME: this must be done the other way around
        if v_id_str == "" and 'readonly' in attrib and attr.allow_write_for_null:
            del attrib['readonly']

        with parent.element("select", attrib=attrib):
            if self.others:
                from contextlib import closing
                if attr.min_occurs == 0:
                    parent.write(E.option())
                if attr.write is False and v_id_str != "":
                    elt = E.option(v_text_str, value=v_id_str, selected="")
                    parent.write(elt)
                else:
                    # FIXME: this blocks the reactor
                    with closing(ctx.app.config.stores['sql_main'].itself.Session()) as session:
                        q = session.query(cls.__orig__ or cls)
                        if self.others_order_by is not None:
                            if isinstance(self.others_order_by, (list, tuple)):
                                q = q.order_by(*self.others_order_by)
                            else:
                                q = q.order_by(self.others_order_by)

                        for o in q:
                            id_str, text_str = self._prep_inst(cls, o, fti)

                            elt = E.option(text_str, value=id_str)
                            if id_str == v_id_str:
                                elt.attrib['selected'] = ""

                            parent.write(elt)
            else:
                parent.write(E.option(v_text_str, value=v_id_str, selected=''))

    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if self.type is not None:
            cls = self.type

        fti = cls.get_flat_type_info(cls)

        if self.label:
            elt_id = self._gen_input_elt_id(name, **kwargs)
            label = self._gen_label_for(ctx, cls, name, elt_id)
            # this part should be consistent with what _wrap_with_label does
            with parent.element('div', attrib={'class': 'label-input-wrapper'}):
                parent.write(label)
                self._write_select(ctx, cls, inst, parent, name, fti, **kwargs)

        else:
            self._write_select(ctx, cls, inst, parent, name, fti, **kwargs)

        self._write_hidden_fields(ctx, cls, inst, parent, name, fti, **kwargs)
