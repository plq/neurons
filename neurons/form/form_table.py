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

from inspect import isgenerator

from lxml.builder import E

from spyne import ComplexModelBase, Array
from spyne.util import Break, coroutine
from spyne.protocol.html import HtmlColumnTable

from neurons.form import HtmlForm
from neurons.form import HtmlWidget


SOME_COUNTER = [0]


class HtmlFormTable(HtmlColumnTable, HtmlWidget):
    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=True,
        cloth=None, attr_name='spyne_id', root_attr_name='spyne',
        polymorphic=True, doctype=None, hier_delim='.',
        cloth_parser=None, produce_header=True, table_name_attr='class',
        field_name_attr='class', border=0, row_class=None, cell_class=None,
        header_cell_class=None,
        can_add=True, can_remove=True):

        super(HtmlFormTable, self).__init__(app=app,
            ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
            polymorphic=polymorphic, hier_delim=hier_delim, doctype=doctype,
            cloth=cloth, attr_name=attr_name, root_attr_name=root_attr_name,
            cloth_parser=cloth_parser,

            produce_header=produce_header, table_name_attr=table_name_attr,
            field_name_attr=field_name_attr, border=border,
            row_class=row_class, cell_class=cell_class,
            header_cell_class=header_cell_class)

        self.prot_form = HtmlForm()
        self.can_add = can_add
        self.can_remove = can_remove
        self.use_global_null_handler = False

    def _init_cloth(self, *args, **kwargs):
        super(HtmlFormTable, self)._init_cloth(*args, **kwargs)
        form = E.form(method='POST', enctype="multipart/form-data")
        if self._root_cloth is None:
            self._cloth = self._root_cloth = form
        else:
            self._root_cloth.append(form)
            self._root_cloth = form

    @coroutine
    def model_base_to_parent(self, ctx, cls, inst, parent, name, from_arr=False,
                             remove=None, **kwargs):
        if from_arr:
            td_attrs = {}
            if self.field_name_attr:
                td_attrs[self.field_name_attr] = name

            with parent.element('tr', attrib=td_attrs):
                with parent.element('td', attrib=td_attrs):
                    ret = self.prot_form.to_parent(ctx, cls, inst, parent, name,
                                     from_arr=from_arr, no_label=True, **kwargs)
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

                if remove is None:
                    remove = True
                self.extend_data_row(ctx, cls, inst, parent, name,
                                                        remove=remove, **kwargs)

        else:
            ret = self.prot_form.to_parent(ctx, cls, inst, parent, name,
                                     from_arr=from_arr, no_label=True, **kwargs)

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

    def extend_header_row(self, ctx, cls, parent, name, **kwargs):
        if self.can_add or self.can_remove:
            parent.write(E.th())

    def extend_data_row(self, ctx, cls, inst, parent, name, array_index=None,
                                             add=False, remove=True, **kwargs):
        if array_index is None:
            return

        if not (self.can_remove or self.can_add):
            return

        td = E.td(style='white-space: nowrap;')
        self._gen_buttons(td, name, add, remove)

        parent.write(td)

    def _gen_buttons(self, elt, name, add, remove):
        name = "%s-%d" % (self.selsafe(name), SOME_COUNTER[0])

        if add:
            elt.append(
                E.button('+', **{
                    "class": "%s_btn_add" % name,
                    "type": "button",
                }),
            )

        if remove:
            elt.append(
                E.button('-', **{
                    "class": "%s_btn_remove" % name,
                    "type": "button",
                }),
            )

    def extend_table(self, ctx, cls, parent, name, **kwargs):
        if not self.can_add:
            return

        # FIXME: just fix me.
        if issubclass(cls, Array):
            cls = next(iter(cls._type_info.values()))
            self._gen_row(ctx, cls, [None], parent, name)

        # even though there are calls to coroutines here, as the passed objects
        # are empty, it's not possible to have push data. so there's no need to
        # check the returned generators.
        if issubclass(cls, ComplexModelBase):
            if cls.Attributes.max_occurs > 1:
                self._gen_row(ctx, cls, [None], parent, name,
                                         add=True, remove=False, array_index=-1)
            else:
                self._gen_row(ctx, cls, None, parent, name,
                                         add=True, remove=False, array_index=-1)

        else:
            if cls.Attributes.max_occurs > 1:
                self.model_base_to_parent(ctx, cls, None, parent, name,
                          from_arr=True, add=True, remove=False, array_index=-1)
            else:
                self.model_base_to_parent(ctx, cls, None, parent, name,
                                         add=True, remove=False, array_index=-1)

        rearr = REARRANGE_JS % {'hier_delim': self.prot_form.hier_delim}

        name = '%s-%d' % (self.selsafe(name), SOME_COUNTER[0])

        SOME_COUNTER[0] += 1

        parent.write(self._format_js(ADD_JS, name=name, rearr=rearr))


ADD_JS = ["""
var add = function(event) {
    var td = $(this).parent();
    var tr = td.parent();
    var f = orig_row.clone(true);
    var btn = f.find(".%(name)s_btn_add");

    btn.off("click");
    btn.click(remove);
    btn.text("-");

    f.insertBefore(tr);

    rearrange();

    event.preventDefault();
    return false;
};

var remove = function (e) {
    var own = $(".%(name)s_btn_remove");
    var td = $(this).parent();
    var tr = td.parent();
    tr.remove();

    rearrange();
    e.preventDefault();
    return false;
};

var rearrange = function() {
    table.children('tr').each(function() {
        var idx = $(this).index();
        $(this).children('td[_main]').each(function() {
            var td = $(this);
            var name_str = td.attr('_main') + '[' + zerofill(idx, 9) + '].' + td.attr('_sub');
            $(this).children('[name]').attr('name', name_str);
        });
    });
};

$(".%(name)s_btn_remove").click(remove);
var btn_add = $(".%(name)s_btn_add");
btn_add.off("click");
btn_add.click(add);

var row = btn_add.parent().parent();
var table = row.parent();
var orig_row = row.clone(true);

for (var children = row.children(), i=0, l=children.length-1; i < l; ++i) {
    $(children[i]).children().remove();
}

row.attr('null-widget', true);
var null_widget = row.clone(true);"""]

REARRANGE_JS = """
var rearrange = function() {
    table.children('tr').each(function() {
        var idx = $(this).index();
        $(this).children('td[_main]').each(function() {
            var td = $(this);
            var name_str = td.attr('_main') + '[' + zerofill(idx, 9) + ']%(hier_delim)s' + td.attr('_sub')
            $(this).children('[name]').attr('name', name_str);
        });
    });
}"""
