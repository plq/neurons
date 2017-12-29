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

import json

from lxml.html.builder import E

from slimit import mangler
from slimit.visitors.minvisitor import ECMAMinifier

from spyne import ComplexModel, Array, Unicode, XmlAttribute, AnyUri, \
    XmlData, Integer, UnsignedInteger, ComplexModelBase
from spyne.protocol.html import HtmlCloth
from spyne.store.relational import get_pk_columns
from spyne.util.dictdoc import get_object_as_simple_dict
from spyne.util.six.moves.urllib.parse import urlencode


SETUP_DATATABLES = """
neurons.setup_datatables = function(selector, data, hide) {
    var $table = $(selector);
    if (hide) {
        neurons.hide_empty_columns($table);
    }
    if ($table.length) {
        setTimeout(function () {
            $table.dataTable(data);
        }, 1);
    }
};
"""

HIDE_EMPTY_COLUMNS = """
neurons.hide_empty_columns = function ($table) {
    $($table.find("tr")[1]).find("td").each(function (_, elt) {
        setTimeout(function () {
            var cc = $(elt).attr("class").split(" ")[0];
            if ($table.find("td." + cc).text() == "") {
                $table.find("td." + cc).hide();
                $table.find("th." + cc).hide();
            }
        }, 0);
    });
};
"""

# http://stackoverflow.com/a/17772086
TYPE_CHECKERS = """
['Arguments', 'Function', 'String', 'Number', 'Date', 'RegExp'].forEach(
    function(name) {
        neurons['is' + name] = function(obj) {
              return toString.call(obj) == '[object ' + name + ']';
    };
});
"""

# http://stackoverflow.com/questions/728360#728694
CLONE = """
neurons.clone = function(obj) {
    var copy;

    // Handle the 3 simple types, and null or undefined
    if (null == obj || "object" != typeof obj) return obj;

    // Handle Date
    if (obj instanceof Date) {
        copy = new Date();
        copy.setTime(obj.getTime());
        return copy;
    }

    // Handle Array
    if (obj instanceof Array) {
        copy = [];
        for (var i = 0, len = obj.length; i < len; i++) {
            copy[i] = neurons.clone(obj[i]);
        }
        return copy;
    }

    // Handle Object
    if (obj instanceof Object) {
        copy = {};
        for (var attr in obj) {
            if (obj.hasOwnProperty(attr)) copy[attr] = neurons.clone(obj[attr]);
        }
        return copy;
    }

    throw new Error("Unable to copy obj! Its type isn't supported.");
};
"""

URLENCODE = """
neurons.urlencode_str = function(str) {
    var output = '';
    var x = 0;
    str = str.toString();
    var regex = /(^[a-zA-Z0-9_.]*)/;

    while (x < str.length) {
        var match = regex.exec(str.substr(x));

        if (match != null && match.length > 1 && match[1] != '') {
            output += match[1];
            x += match[1].length;
        }
        else {
            if (str[x] == ' ') {
                output += '+';
            }
            else {
                var charCode = str.charCodeAt(x);
                var hexVal = charCode.toString(16);
                output += '%' + ( hexVal.length < 2 ? '0' : '' ) + hexVal.toUpperCase();
            }
            x++;
        }
    }

    return output;
};

neurons.urlencode = function(obj) {
    var i = 0;
    var retval = "";
    for (var k in obj) if (obj.hasOwnProperty(k) && obj[k]) {
        if (i > 0) {
            retval += "&";
        }
        retval += k + '=' + neurons.urlencode_str(obj[k]);

        ++i;
    }
    return retval;
};

"""

class Link(ComplexModel):
    href = XmlAttribute(AnyUri)
    rel = XmlAttribute(Unicode(values=["stylesheet", 'import']))


class CascadingStyleSheet(ComplexModel):
    id = Unicode
    data = XmlData(Unicode)
    type = XmlAttribute(Unicode(values=["text/css"]))
    media = XmlAttribute(Unicode(values=["text/css"]))
    title = XmlAttribute(Unicode)


class ScriptElement(ComplexModel):
    id = XmlAttribute(Unicode)
    data = XmlData(Unicode)
    type = XmlAttribute(Unicode(values=["text/javascript"]))
    href = XmlAttribute(Unicode)


class ViewRenderer(HtmlCloth):
    def to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        if inst is None:
            return

        in_message = ctx.descriptor.in_message
        if not issubclass(in_message, ComplexModelBase):
            return

        view_names = tuple((k for k, v in in_message._type_info.items()
                                                    if issubclass(v, ViewBase)))
        if len(view_names) == 0:
            return

        view_name, = view_names
        path = ctx.transport.get_path()
        qs_dict = dict(ctx.in_body_doc.items())
        if name == 'prev':
            for k, v in qs_dict.items():
                if k.endswith('.start'):
                    del qs_dict[k]
                    break

        elif name == 'next':
            for k, v in qs_dict.items():
                if k.endswith('.end'):
                    del qs_dict[k]
                    break

        qs_dict.update(get_object_as_simple_dict(inst, prefix=(view_name,)))

        anchor_text = name
        anchor_href = "{}?{}".format(path, urlencode(qs_dict))

        parent.write(E.a(anchor_text, href=anchor_href))


class ViewBase(ComplexModel):
    LIMIT_MAX = 100
    START_MIN = 0

    _type_info = [
        ('end', Integer),
        ('start', Integer),
        ('limit', UnsignedInteger),
        ('offset', UnsignedInteger),
    ]

    def __init__(self, *args, **kwargs):
        self._limit = None

        super(ViewBase, self).__init__(*args, **kwargs)

    @property
    def limit(self):
        if self._limit is None:
            return None

        return min(self._limit, self.LIMIT_MAX)

    @limit.setter
    def limit(self, limit):
        self._limit = limit

    def apply(self, ctx, cls, q):
        if self is None:
            return q

        # FIXME: Support compound columns
        # FIXME: Actually we don't need the primary key. Just a unique column
        #        should be enough
        (pk_field_name, pk_field_type), = get_pk_columns(cls)
        pk_field = getattr(cls, pk_field_name)

        start = self.start
        if start is not None:
            q = q.filter(pk_field > start)

        end = self.end
        if end is not None:
            q = q.filter(pk_field < end)

        if self.sort_params is not None and len(self.sort_params) > 0:
            order_by = []

            for param in self.sort_params:
                field = getattr(cls, param.column)
                if param.is_descending():
                    field = field.desc()

                order_by.append(field)
                logger.debug("Order by %s", param.column)

            q = q.order_by(*order_by)

        else:
            logger.debug("Order by pk")
            if end is not None:
                q = q.order_by(pk_field.desc())
            else:
                q = q.order_by(pk_field)

        limit = self.limit
        if limit is not None:
            if limit > self.LIMIT_MAX:
                limit = self.LIMIT_MAX

            logger.debug("Limit %d", limit)
            q = q.limit(limit)

        offset = self.offset
        if offset is not None:
            logger.debug("Offset %d", offset)
            q = q.offset(offset)

        return q


class ScreenBase(ComplexModel):
    JQUERY_URL = "https://code.jquery.com/jquery-1.12.4.min.js"

    class Attributes(ComplexModel.Attributes):
        logged = False

    datatables = None

    title = Unicode(default='Neurons Screen')

    # meta properties
    description = Unicode(sub_name='content', default='Neurons Application')
    application_name = Unicode(sub_name='content',
                                                  default='Neurons Application')
    apple_mobile_webapp_title = Unicode(sub_name='content',
                                                          default='Neurons App')

    links = Array(Link, wrapped=False)
    styles = Array(CascadingStyleSheet, wrapped=False)
    scripts = Array(ScriptElement, wrapped=False)

    def __init__(self, ctx, *args, **kwargs):
        ComplexModel.__init__(self, *args, **kwargs)

        self._link_hrefs = set()
        self._have_clone = False
        self._have_jquery = False
        self._have_namespace = False
        self._have_urlencode = False
        self._have_type_checkers = False
        self._have_setup_datatables = False
        self._have_hide_empty_columns = False

        assert ctx.outprot_ctx.screen is None, \
                          "We are supposed to have only one screen per context."
        ctx.outprot_ctx.screen = self

    def append_script_href(self, what, type='text/javascript'):
        if self.scripts is None:
            self.scripts = []
        self.scripts.append(ScriptElement(href=what, type=type))

    def append_script(self, what, type='text/javascript', id=None):
        if self.scripts is None:
            self.scripts = []
        self.scripts.append(ScriptElement(what, type=type, id=id))

    def append_script_tree(self, tree, id=None, minify=False):
        if minify:
            mangler.mangle(tree, toplevel=True)
            ret = ECMAMinifier().visit(tree)
        else:
            ret = tree.to_ecma()

        self.append_script(ret, type='text/javascript', id=id)

    def append_style(self, what, media=None):
        if self.styles is None:
            self.styles = []
        self.styles.append(CascadingStyleSheet(what, media=media))

    def with_namespace(self):
        if not self._have_namespace:
            self.append_script("window.neurons = {}")

            self._have_namespace = True

        return self

    def with_jquery(self):
        if not self._have_jquery:
            self.append_script_href(self.JQUERY_URL)

            self._have_jquery = True

        return self

    def with_own_stylesheet(self, base='/assets/css/screen'):
        if self.links is None:
            self.links = []

        class_name = self.__class__.get_type_name()
        href = "%s/%s.css" % (base, class_name)

        if not (href in self._link_hrefs):
            self._link_hrefs.add(href)
            self.links.append(Link(rel="stylesheet", href=href))

        return self

    def with_setup_datatables(self):
        self.with_namespace()
        if not self._have_setup_datatables:
            self.append_script(SETUP_DATATABLES)

            self._have_setup_datatables = True
        return self

    def with_hide_empty_columns(self):
        self.with_namespace()
        if not self._have_hide_empty_columns:
            self.append_script(HIDE_EMPTY_COLUMNS)

            self._have_hide_empty_columns = True
        return self

    def with_datatables(self, data=None, hide_empty_columns=False):
        if data is None:
            data = self.datatables

        if data is None:
            data = {}

        self.with_jquery()

        if hide_empty_columns:
            self.with_hide_empty_columns()

        self.with_setup_datatables()

        for selector, data in data.items():
            retval = [
                "$(document).ready(function() {",
                    "neurons.setup_datatables(",
                        json.dumps(selector), ",",
                        json.dumps(data), ",",
                        json.dumps(hide_empty_columns),
                    ");",
                "});",
            ]

            self.append_script(''.join(retval))

        return self

    def with_type_checkers(self):
        if not self._have_type_checkers:
            self.with_namespace()

            self.append_script(TYPE_CHECKERS)

            self._have_type_checkers = True

        return self

    def with_clone(self):
        if not self._have_clone:
            self.with_namespace()

            self.append_script(CLONE)

            self._have_clone = True

        return self

    def with_urlencode(self):
        if not self._have_urlencode:
            self.with_namespace()

            self.append_script(URLENCODE)

            self._have_urlencode = True

        return self
