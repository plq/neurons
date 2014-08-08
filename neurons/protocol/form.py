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


from inspect import isgenerator
from lxml.builder import E

from spyne import ComplexModelBase, Unicode
from spyne.protocol.html import HtmlBase
from spyne.util import coroutine, Break
from spyne.util.cdict import cdict


def _form_key(k):
    key, cls = k
    retval = getattr(cls.Attributes, 'order', None)

    if retval is None:
        retval = key

    return retval


class HtmlForm(HtmlBase):
    def __init__(self, app=None, ignore_uncap=False, ignore_wrappers=False,
                       cloth=None, attr_name='spyne_id', root_attr_name='spyne',
                                             cloth_parser=None, hier_delim='.'):

        super(HtmlForm, self).__init__(app=app,
                     ignore_uncap=ignore_uncap, ignore_wrappers=ignore_wrappers,
                cloth=cloth, attr_name=attr_name, root_attr_name=root_attr_name,
                                                      cloth_parser=cloth_parser)

        self.serialization_handlers = cdict({
            Unicode: self.unicode_to_parent,
            ComplexModelBase: self.complex_model_to_parent,
        })

        self.hier_delim = hier_delim

    def unicode_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        parent.write(E.input(
            value=inst,
            name=name,
            type='text',
        ))

    @coroutine
    def subserialize(self, ctx, cls, inst, parent, name=None, **kwargs):
        with parent.element("form"):
            ret = super(HtmlForm, self).subserialize(ctx, cls, inst, parent,
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

    @coroutine
    def complex_model_to_parent(self, ctx, cls, inst, parent, name, **kwargs):
        fti = cls.get_flat_type_info(cls)

        for k, v in sorted(fti.items(), key=_form_key):
            subinst = getattr(inst, k, None)
            ret = self.to_parent(ctx, v, subinst, parent, name, **kwargs)
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
