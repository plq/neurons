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

from neurons.base.screen import ScreenBase

from spyne import Unicode, ComplexModel, XmlAttribute, Array, AnyUri


class HtmlImport(ComplexModel):
    href = XmlAttribute(Unicode)


class IronAjax(ComplexModel):
    url = XmlAttribute(AnyUri)


class PolymerComponent(ComplexModel):
    style = Unicode
    getter = IronAjax
    putter = IronAjax
    definition = Unicode
    dependencies = Array(HtmlImport, wrapped=False)
    dom_module_id = Unicode(sub_name="id")


XML_TO_JSOBJ = """
window.neurons.xml_to_jsobj = function (children, array_tags) {
    function is_array(o) {
        return Object.prototype.toString.apply(o) === '[object Array]';
    }

    function parse_node(xml_node, result, parnames) {
        if (xml_node.nodeName == "#text") {
            var str = xml_node.nodeValue.trim();
            if (str != "") {
                result[parnames.join('.')] = str;
            }

            return;
        }

        var json_node = {};
        var curname = xml_node.nodeName.toLowerCase();

        if (xml_node.attributes) {
            var length = xml_node.attributes.length;
            for (var i = 0; i < length; i++) {
                var attribute = xml_node.attributes[i];
                var attrname = attribute.nodeName.toLowerCase();
                var names = parnames.concat([attrname]);
                json_node[names.join('.')] = attribute.nodeValue;
            }
        }

        var length = xml_node.childNodes.length;
        for (var i = 0; i < length; i++) {
            parse_node(xml_node.childNodes[i], result,
                                                    parnames.concat([curname]));
        }
    }

    var result = {};
    for (var i = 0, l = children.length; i < l; ++i) {
        parse_node(children[i], result, []);
    }

    return result;
}
"""


class PolymerScreen(ScreenBase):
    JQUERY_URL = "/static/jquery-1.12.4.min.js"

    def __init__(self, ctx, *args, **kwargs):
        super(PolymerScreen, self).__init__(ctx, *args, **kwargs)
        self._have_xml_to_jsobj = False

    def with_xml_to_jsobj(self):
        if not self._have_xml_to_jsobj:
            self.with_namespace()

            self.append_script(XML_TO_JSOBJ)

            self._have_xml_to_jsobj = True

        return self
