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

from lxml.html.builder import E

from neurons.form import HtmlForm


class PolymerForm(HtmlForm):
    HTML_INPUT = 'paper-input'
    HTML_OPTION = 'paper-item'
    HTML_OPTION_PARENTS = 'paper-listbox', {'class': 'dropdown-content'}
    HTML_SELECT = 'paper-dropdown-menu'
    HTML_TEXTAREA = 'paper-textarea'

    def _gen_options(self, ctx, cls, inst, name, cls_attrs, elt, **kwargs):
        print "!" * 50
        print elt.attrib
        print "!" * 50

        del elt.attrib['name']
        del elt.attrib['class']

        option_parent = E('paper-listbox', **{'class': 'dropdown-content'})
        elt.append(option_parent)

        super(PolymerForm, self)._gen_options(ctx, cls, inst, name, cls_attrs,
                                                        option_parent, **kwargs)
        return elt

    def _append_option(self, parent, label, value, selected=False, index=-1):
        assert (not selected) or index >= 0

        # waiting for https://github.com/lxml/lxml/pull/210
        # if selected:
        #     parent.attrib['selected'] = str(index)

        parent.append(E(self.HTML_OPTION, label))

