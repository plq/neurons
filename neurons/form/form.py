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

from collections import namedtuple
from inspect import isgenerator
from decimal import Decimal as D

from lxml import etree, html
from lxml.builder import E

from spyne import ComplexModelBase, Unicode, Decimal, Boolean, Date, Time, \
    DateTime, Integer, Duration, PushBase, Array, Uuid, AnyHtml, AnyXml, Fault
from spyne.util import coroutine, Break, six, memoize_id
from spyne.util.cdict import cdict
from spyne.server.http import HttpTransportContext

from neurons.form.widget import HtmlWidget, SimpleRenderWidget

SOME_COUNTER = 0


def _idxof(haystack, needle, default):
    try:
        return haystack.index(needle)
    except ValueError:
        return default


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


_jstag = lambda src: E.script(src=src, type="text/javascript")
_csstag = lambda src: E.link(href=src, type="text/css", rel="stylesheet")


# monkeypatch spyne <2.13
if not hasattr(HtmlWidget, '_get_datetime_format'):
    def _get_datetime_format(self, cls_attrs):
        dt_format = cls_attrs.dt_format
        if dt_format is None:
            dt_format = cls_attrs.date_format
        if dt_format is None:
            dt_format = cls_attrs.out_format
        if dt_format is None:
            dt_format = cls_attrs.format

        return dt_format

    HtmlWidget._get_datetime_format = _get_datetime_format


class HtmlFormRoot(HtmlWidget):
    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                cloth=None, cloth_parser=None, polymorphic=True, hier_delim='.',
                     label=True, doctype=None, asset_paths={}, placeholder=None,
               input_class=None, input_div_class=None, input_wrapper_class=None,
                                  label_class=None, action=None, method='POST'):

        super(HtmlFormRoot, self).__init__(app=app, doctype=doctype,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                    hier_delim=hier_delim, label=label, asset_paths=asset_paths,
                    placeholder=placeholder, input_class=input_class,
                    input_div_class=input_div_class,
               input_wrapper_class=input_wrapper_class, label_class=label_class)

        self.action = action
        self.method = method

    @coroutine
    def start_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        # FIXME: what a HUGE swath of copy/paste! I want yield from!

        # if we are already in a form, don't open a <form> tag
        if not getattr(ctx.outprot_ctx, 'in_form', False):
            cls_attrs = self.get_cls_attrs(cls)

            ctx.outprot_ctx.in_form = True

            if not (len(ctx.outprot_ctx.prot_stack) == 1 and
                              isinstance(ctx.protocol.prot_stack[0], HtmlForm)):
                name = ''

            attrib = dict(method=self.method)
            if self.method == 'POST':
                attrib['enctype'] = "multipart/form-data"

            if hasattr(ctx.protocol, 'form_action'):
                fa = ctx.protocol.form_action
                attrib['action'] = fa
                logger.debug("Set form action to '%s' from ctx", fa)

            elif cls_attrs.action:
                fa = cls_attrs.action
                attrib['action'] = fa
                logger.debug("Set form action to '%s' from cls_attrs", fa)

            elif self.action is not None:
                fa = self.action
                attrib['action'] = fa
                logger.debug("Set form action to '%s' from protocol", fa)

            elif isinstance(ctx.transport, HttpTransportContext):
                fa = ctx.transport.get_path()
                attrib['action'] = fa
                logger.debug("Set form action to '%s' from request path", fa)

            self.event_manager.fire_event("before_form", ctx, cls, inst, parent,
                                                  name, attrib=attrib, **kwargs)

            with parent.element('form', attrib=attrib):
                ret = super(HtmlFormRoot, self).start_to_parent(ctx, cls, inst,
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
            ret = super(HtmlFormRoot, self).start_to_parent(ctx, cls, inst,
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


class HtmlForm(HtmlFormRoot):
    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                cloth=None, cloth_parser=None, polymorphic=True, hier_delim='.',
                     doctype=None, label=True, asset_paths={}, placeholder=None,
                                         input_class=None, input_div_class=None,
                                     input_wrapper_class=None, label_class=None,
                                                    action=None, method='POST'):

        super(HtmlForm, self).__init__(app=app, doctype=doctype,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                    hier_delim=hier_delim, label=label, asset_paths=asset_paths,
                    placeholder=placeholder, input_class=input_class,
                    input_div_class=input_div_class,
               input_wrapper_class=input_wrapper_class, label_class=label_class,
                                                   action=action, method=method)

        self.serialization_handlers = cdict({
            Date: self._check_simple(self.date_to_parent),
            Time: self._check_simple(self.time_to_parent),
            Uuid: self._check_simple(self.uuid_to_parent),
            Fault: self.fault_to_parent,
            Array: self.array_type_to_parent,
            AnyXml: self._check_simple(self.anyxml_to_parent),
            Integer: self._check_simple(self.integer_to_parent),
            Unicode: self._check_simple(self.unicode_to_parent),
            AnyHtml: self._check_simple(self.anyhtml_to_parent),
            Decimal: self._check_simple(self.decimal_to_parent),
            Boolean: self._check_simple(self.boolean_to_parent),
            Duration: self._check_simple(self.duration_to_parent),
            DateTime: self._check_simple(self.datetime_to_parent),
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

        self.simple = SimpleRenderWidget(label=label)

    def _check_simple(self, f):
        def _ch(ctx, cls, inst, parent, name, **kwargs):
            cls_attrs = self.get_cls_attrs(cls)
            if cls_attrs.hidden:
                self._gen_input_hidden(cls, inst, parent, name)
            elif cls_attrs.read_only:
                self.simple.to_parent(ctx, cls, inst, parent, name, **kwargs)
            else:
                f(ctx, cls, inst, parent, name, **kwargs)

        _ch.__name__ = f.__name__
        return _ch

    def _form_key(self, sort_key):
        k, v = sort_key
        attrs = self.get_cls_attrs(v)
        return None if attrs.tab is None else \
                                (attrs.tab.index, attrs.tab.htmlid), \
               None if attrs.fieldset is None else \
                                (attrs.fieldset.index, attrs.fieldset.htmlid), \

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attrs, elt = self._gen_input_unicode(ctx, cls, inst, name, **kwargs)
        parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))

    @staticmethod
    @memoize_id
    def Tany_ml_to_parent(lxml_package):
        def _ml_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
            cls_attrs, elt = self._gen_input_textarea(ctx, cls, name, **kwargs)
            # TODO: Use something like ACE editor to generate a proper html editor

            if inst is not None:
                if cls_attrs.serialize_as in ('element', 'elt'):
                    if isinstance(inst, six.string_types):
                        inst = lxml_package.fromstring(inst)

                    elt.append(inst)

                else:
                    if not isinstance(inst, six.string_types):
                        inst = lxml_package.tostring(inst)

                    elt.text = inst

            parent.write(self._wrap_with_label(ctx, cls, name, elt, **kwargs))

        return _ml_to_parent

    anyhtml_to_parent = Tany_ml_to_parent.__func__(html)
    anyxml_to_parent = Tany_ml_to_parent.__func__(etree)

    def uuid_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        kwargs.update({'attr_override': {'max_len': 36}})
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
            logger.debug("Removing value=%r from checkbox", elt.attrib['value'])
            del elt.attrib['value']
        elt.attrib['type'] = 'checkbox'

        if bool(inst):
            elt.attrib['checked'] = 'checked'

        wrap_label = HtmlWidget.WRAP_FORWARD \
              if cls_attrs.label_position == 'left' else HtmlWidget.WRAP_FORWARD

        div = self._wrap_with_label(ctx, cls, name, elt,
                                                wrap_label=wrap_label, **kwargs)

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
            value = self.to_unicode(cls, inst)
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

    @staticmethod
    def _split_datetime_format(f):
        """this is actually a pathetic attempt at splitting datetime
        format to date and time formats. assumes date and time fields are
        not mixed"""

        lf = len(f)
        date_start_idx = min(
            _idxof(f, '%Y', lf), _idxof(f, '%m', lf), _idxof(f, '%d', lf)
        )
        date_end_idx = max(
            _idxof(f, '%Y', -1), _idxof(f, '%m', -1), _idxof(f, '%d', -1)
        ) + 2

        time_start_idx = min(
            _idxof(f, '%H', lf), _idxof(f, '%M', lf), _idxof(f, '%S', lf)
        )
        time_end_idx = max(
            _idxof(f, '%H', -1), _idxof(f, '%M', -1), _idxof(f, '%S', -1)
        ) + 2

        if date_end_idx <= time_start_idx:
            date_format = f[:date_end_idx].strip()
            time_format = f[time_start_idx:].strip()
        else:
            date_format = f[date_start_idx:].strip()
            time_format = f[:time_end_idx].strip()

        date_format = date_format.replace('%Y', 'yy') \
                                 .replace('%m', 'mm') \
                                 .replace('%d', 'dd') \

        time_format = time_format.replace('%H', 'HH') \
                                 .replace('%M', 'mm') \
                                 .replace('%S', 'ss')

        return date_format, time_format

    def datetime_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        # see: http://trentrichardson.com/examples/timepicker/
        ctx.protocol.assets.extend([('jquery',), ('jquery-ui', 'datepicker'),
                                                        ('jquery-timepicker',)])

        cls_attrs = self.get_cls_attrs(cls)
        elt = self._gen_input(ctx, cls, None, name, cls_attrs, **kwargs)
        elt.attrib['type'] = 'text'

        dt_format = self._get_datetime_format(cls_attrs)
        if dt_format is None:
            date_format, time_format = 'yy-mm-dd', 'HH:mm:ss'
        else:
            date_format, time_format = \
                                self._split_datetime_format(cls_attrs.dt_format)

        code = [
            "var t=$('#%(field_name)s');",
            "t.datetimepicker({",
            "    dateFormat: '%(date_format)s',",
            "    timeFormat: '%(time_format)s'",
            "});",
        ]

        if inst is None:
            script = self._format_js(code, field_name=elt.attrib['id'],
                               date_format=date_format, time_format=time_format)
        else:
            value = self.to_unicode(cls, inst)

            code.append(
                "t.datetimepicker('setTime', '%(value)s');")

            script = self._format_js(code, field_name=elt.attrib['id'],
                  date_format=date_format, time_format=time_format, value=value)

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
            try:
                subinst = getattr(inst, k, None)
            except (KeyError, AttributeError):
                subinst = None

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

            label_ctxs = []
            if subattr.label:
                if self.input_wrapper_class is not None:
                    div_attrib = {'class': self.input_wrapper_class}

                    div_ctx = parent.element('div', div_attrib)
                    div_ctx.__enter__()
                    label_ctxs.append(div_ctx)
                    logger.debug("entering label wrapper")

                label_attrib = {}
                if self.label_class is not None:
                    label_attrib['class'] = ' '.join((
                                          self.label_class, self.selsafe(name)))
                with parent.element('label', label_attrib):
                    parent.write(self.trc(v, ctx.locale, child_key))

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

            for c in reversed(label_ctxs):
                c.__exit__(None, None, None)
                logger.debug("exiting label_ctxs")

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

    def fault_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        cls_attr = self.get_cls_attrs(cls)

        with parent.element('div', {"class": cls.get_type_name()}):
            parent.write(
                E.div(inst.faultcode, **{"class": "faultcode"}),
                E.div(inst.faultstring, **{"class": "faultstring"}),
                E.div(inst.faultactor, **{"class": "faultactor"}),
            )

            if isinstance(inst.detail, etree._Element):
                parent.write(E.pre(etree.tostring(inst.detail, pretty_print=True)))

            # add other nonstandard fault subelements with get_members_etree
            self._write_members(ctx, cls, inst, parent)
            # no need to track the returned generator because we expect no
            # PushBase instance here.

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
