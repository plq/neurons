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

from spyne import ComplexModelBase
from spyne.protocol.html import HtmlBase

from spyne.util.cdict import cdict


class PolymerWidgetBase(HtmlBase):
    pass


class PolymerDropdownMenu(PolymerWidgetBase):
    """Generates a polymer dropdown menu.

    Example:

        <paper-dropdown-menu id="foo" no-animations="" noink=""
                             label="label" always-float-label="">
            <paper-listbox class="dropdown-content">
                <paper-item></paper-item>
                <paper-item>1</paper-item>
                <paper-item>2</paper-item>
                <paper-item>3</paper-item>
            </paper-listbox>
        </paper-dropdown-menu>
    """

    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                cloth=None, cloth_parser=None, polymorphic=True, hier_delim='.',
                                                    doctype=None, others=False):

        super(PolymerDropdownMenu, self).__init__(app=app, doctype=doctype,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, cloth_parser=cloth_parser, polymorphic=polymorphic,
                                                          hier_delim=hier_delim)

        self.serialization_handlers = cdict({
            ComplexModelBase: self.complex_model_to_parent,
        })

        self.others = others


    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        pass
