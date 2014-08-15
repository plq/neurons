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

from __future__ import print_function

from collections import deque, namedtuple
from inspect import isgenerator
from decimal import Decimal as D

from lxml import etree, html
from lxml.builder import E

from spyne import ComplexModelBase, Unicode, Decimal, Boolean, Date, Time, \
    DateTime, Integer, Duration, PushBase, Array
from spyne.protocol.html import HtmlBase
from spyne.util import coroutine, Break, memoize_id, DefaultAttrDict
from spyne.util.cdict import cdict


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


def _Tform_key(prot):
    def _form_key(sort_key):
        k, v = sort_key
        attrs = _get_cls_attrs(prot, v)
        return None if attrs.tab is None else \
                                (attrs.tab.index, attrs.tab.htmlid), \
               None if attrs.fieldset is None else \
                                (attrs.fieldset.index, attrs.fieldset.htmlid), \
               attrs.order, k

    return _form_key


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
        if($('#%(field_name)s_container').find('.%(field_name)s').length >1){
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

@memoize_id
def _get_cls_attrs(prot, cls):
    attr = DefaultAttrDict([(k, getattr(cls.Attributes, k))
                    for k in dir(cls.Attributes) if not k.startswith('__')])
    if cls.Attributes.prot_attrs:
        attr.update(cls.Attributes.prot_attrs.get(prot.__class__, {}))
        attr.update(cls.Attributes.prot_attrs.get(prot, {}))
    return attr


def _format_js(lines, **kwargs):
    for i, line in enumerate(lines):
        lines[i] = lines[i] % kwargs

    return E.script("""
$(function(){
\t%s
});""" % '\n\t'.join(lines), type="text/javascript")


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

        if getattr(cls_attrs, 'pattern', None) is not None:
            elt_attrs['pattern'] = cls_attrs.pattern

        if not (inst is None and isinstance(inst, type)):
            val = self.to_unicode(cls, inst)
            if val is not None:
                elt_attrs['value'] = val

        # FIXME: handle min_occurs > 1
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


_jstag = lambda src: E.script(src=src, type="text/javascript")
_csstag = lambda src: E.link(href=src, type="text/css", rel="stylesheet")


def _idiv(*args, **kwargs):
    kwargs['class'] = '.label-input-wrapper'
    return E.div(*args, **kwargs)


class HtmlForm(HtmlWidget):
    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                       cloth=None, attr_name='spyne_id', root_attr_name='spyne',
                            cloth_parser=None, polymorphic=True, hier_delim='.',
                                                                asset_paths={}):

        super(HtmlForm, self).__init__(app=app,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, attr_name=attr_name, root_attr_name=root_attr_name,
                             cloth_parser=cloth_parser, polymorphic=polymorphic)

        self.serialization_handlers = cdict({
            Date: self.date_to_parent,
            Time: self.time_to_parent,
            Array: self.array_type_to_parent,
            Integer: self.integer_to_parent,
            Unicode: self.unicode_to_parent,
            Decimal: self.decimal_to_parent,
            Boolean: self.boolean_to_parent,
            Duration: self.duration_to_parent,
            DateTime: self.datetime_to_parent,
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

    def _init_cloth(self, *args, **kwargs):
        super(HtmlForm, self)._init_cloth(*args, **kwargs)
        form = E.form(method='POST', enctype="multipart/form-data")
        if self._root_cloth is None:
            self._cloth = self._root_cloth = form
        else:
            self._root_cloth.append(form)
            self._root_cloth = form

    def _gen_label(self, ctx, cls, name, input):
        return E.label(self.trc(cls, ctx.locale, name),
                                                  **{'for': input.attrib['id']})

    def subserialize(self, ctx, cls, inst, parent, name=None, **kwargs):
        ctx.protocol.assets = []
        return super(HtmlForm, self).subserialize(ctx, cls, inst, parent,
                                                                 name, **kwargs)

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs, elt = self._gen_input_unicode(cls, inst, name)
        parent.write(_idiv(self._gen_label(ctx, cls, name, elt), elt))

    def decimal_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, inst, name, cls_attrs)
        elt.attrib['type'] = 'number'

        if D(cls.Attributes.fraction_digits).is_infinite():
            elt.attrib['step'] = 'any'
        else:
            elt.attrib['step'] = str(10**(-int(cls.Attributes.fraction_digits)))

        self._apply_number_constraints(cls_attrs, elt)

        parent.write(_idiv(self._gen_label(ctx, cls, name, elt), elt))

    def boolean_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, inst, name, cls_attrs)
        elt.attrib.update({'type': 'checkbox', 'value': 'true'})

        if bool(inst):
            elt.attrib['checked'] = ''

        parent.write(_idiv(elt, self._gen_label(ctx, cls, name, elt)))

    def date_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        ctx.protocol.assets.extend([('jquery',), ('jquery-ui', 'datepicker')])

        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, inst, name, cls_attrs)
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
            script = _format_js(code, field_name=elt.attrib['id'],
                                                             format=data_format)
        else:
            value = self.to_string(cls, inst)
            code.append("$('#%(field_name)s').datepicker('setDate', '%(value)s');")
            script = _format_js(code, field_name=elt.attrib['id'], value=value,
                                                             format=data_format)

        parent.write(_idiv(self._gen_label(ctx, cls, name, elt), elt, script))

    def time_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        ctx.protocol.assets.extend([('jquery',), ('jquery-ui', 'datepicker'),
                                                        ('jquery-timepicker',)])

        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, inst, name, cls_attrs)
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
            script = _format_js(code, field_name=elt.attrib['id'],
                                                             format=data_format)
        else:
            value = self.to_string(cls, inst)
            code.append("$('#%(field_name)s').timepicker('setDate', '%(value)s');")
            script = _format_js(code, field_name=elt.attrib['id'], value=value,
                                                             format=data_format)

        parent.write(_idiv(self._gen_label(ctx, cls, name, elt), elt, script))

    def datetime_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        ctx.protocol.assets.extend([('jquery',), ('jquery-ui', 'datepicker'),
                                                        ('jquery-timepicker',)])

        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, None, name, cls_attrs)
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
            script = _format_js(code, field_name=elt.attrib['id'],
                                                             format=data_format)
        else:
            value = self.to_string(cls, inst)
            code.append("$('#%(field_name)s').datetimepicker('setDate', '%(value)s');")
            script = _format_js(code, field_name=elt.attrib['id'],
                                                format=data_format, value=value)

        parent.write(_idiv(self._gen_label(ctx, cls, name, elt), elt, script))

    def integer_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, inst, name, cls_attrs)
        elt.attrib['type'] = 'number'

        self._apply_number_constraints(cls_attrs, elt)

        parent.write(_idiv(self._gen_label(ctx, cls, name, elt), elt))

    # TODO: finish this
    def duration_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs = _get_cls_attrs(self, cls)
        elt = self._gen_input(cls, inst, name, cls_attrs)

        parent.write(_idiv(self._gen_label(ctx, cls, name, elt), elt))

    def array_type_to_parent(self, ctx, cls, inst, parent, name=None, **kwargs):
        v = iter(cls._type_info.values()).next()
        return self.to_parent(ctx, v, inst, parent, name, **kwargs)

    def _gen_tab_headers(self, ctx, fti):
        retval = E.ul()

        tabs = {}
        for k, v in fti.items():
            subattr = _get_cls_attrs(self, v)
            tab = subattr.tab
            if tab is not None:
                tabs[id(tab)] = tab

        for i, tab in enumerate(sorted(tabs.values(),
                                            key=lambda t: (t.index, t.htmlid))):
            retval.append(E.li(E.a(
                self.trd(tab.legend, ctx.locale, "Tab %d" % i),
                href="#" + tab.htmlid
            )))

        return retval

    @coroutine
    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        global SOME_COUNTER

        fti = cls.get_flat_type_info(cls)
        prev_fset = fset_ctx = None
        prev_tab = tab_ctx = tabview_ctx = None
        tabview_id = None

        # FIXME: hack! why do we have top-level object receiving name?
        if name == cls.get_type_name():
            name = ''

        with parent.element('fieldset'):
            parent.write(E.legend(cls.get_type_name()))
            for k, v in sorted(fti.items(), key=_Tform_key(self)):
                subattr = _get_cls_attrs(self, v)
                if subattr.exc:
                    continue

                subinst = getattr(inst, k, None)

                tab = subattr.tab
                print("TAB", k, getattr(v.Attributes, 'tab', None), subattr.tab)
                if not (tab is prev_tab):
                    if fset_ctx is not None:
                        fset_ctx.__exit__(None, None, None)
                        print("exiting fset tab ", prev_fset)

                    fset_ctx = prev_fset = None

                    if tab_ctx is not None:
                        tab_ctx.__exit__(None, None, None)
                        print("exiting tab", prev_tab)

                    if prev_tab is None:
                        print("entering tabview")
                        tabview_id = 'tabview' + str(SOME_COUNTER)
                        SOME_COUNTER += 1

                        tabview_ctx = parent.element('div', attrib={'id': tabview_id})
                        tabview_ctx.__enter__()

                        parent.write(self._gen_tab_headers(ctx, fti))

                    print("entering tab", tab)

                    attrib = {'id': tab.htmlid}
                    attrib.update(tab.attrib)
                    tab_ctx = parent.element('div', attrib)
                    tab_ctx.__enter__()

                    prev_tab = tab

                fset = subattr.fieldset
                if not (fset is prev_fset):
                    if fset_ctx is not None:
                        fset_ctx.__exit__(None, None, None)
                        print("exiting fset norm", prev_fset)

                    print("entering fset", fset)
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
                print("exiting fset close", fset)

            if tab_ctx is not None:
                tab_ctx.__exit__(None, None, None)
                print("exiting tab close", fset)

            if tabview_ctx is not None:
                tabview_ctx.__exit__(None, None, None)
                parent.write(E.script(
                    '$(function() { $( "#%s" ).tabs();});' % tabview_id,
                    type="text/javascript"
                ))

                print("exiting tabview close", fset)

    @coroutine
    def _push_to_parent(self, ctx, cls, inst, parent, name, parent_inst=None,
                        label_attrs=None, parent_key=None, no_label=False,
                        **kwargs):
        i = -1
        key = self.selsafe(name)
        attr = _get_cls_attrs(self, cls)
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
        attr = _get_cls_attrs(self, cls)

        if inst is None:
            inst = []

        for i, subval in enumerate(inst):
            new_key = '%s[%09d]' % (key, i)
            with parent.element('div', {"class": key}):
                ret = self.to_parent(ctx, cls, subval, parent, new_key,
                                parent_inst=parent_inst, no_label=True,
                                from_arr=True, **kwargs)
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
    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs, elt = self._gen_input_unicode(cls, inst, name)
        elt.attrib['type'] = 'password'
        parent.write(elt)
