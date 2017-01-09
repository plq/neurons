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

from spyne import Application
from spyne.protocol.html import HtmlCloth
from spyne.protocol.http import HttpRpc

from neurons.polymer.comp.ref.code import ComplexReferenceComponentScreen
from neurons.polymer.comp.date.code import DateComponentScreen

from .const import T_DOM_MODULE, T_SCREEN


# FIXME: This is a hack to add DateComponentScreen to the interface.
from spyne import ServiceBase, rpc
class _DummyService(ServiceBase):
    @rpc(DateComponentScreen, ComplexReferenceComponentScreen)
    def dummy(self, one, two):
        pass


def gen_component_app(config, prefix, classes, locale=None,
        gen_css_imports=False):
    from neurons.polymer.protocol import PolymerForm
    from neurons.polymer.service import TComponentGeneratorService

    return \
        Application(
            [_DummyService] +
            [
                TComponentGeneratorService(
                        cls.customize(prot=PolymerForm()),
                                        prefix, locale, gen_css_imports)
                                                              for cls in classes
            ],
            tns='%s.comp' % config.name,
            in_protocol=HttpRpc(validator='soft'),
            out_protocol=HtmlCloth(cloth=T_DOM_MODULE, strip_comments=True,
                                                     doctype='<!DOCTYPE html>'),
            config=config,
        )


def gen_screen_app(config, prefix, classes):
    from neurons.polymer.protocol import PolymerForm
    from neurons.polymer.service import TScreenGeneratorService

    return \
        Application(
            [_DummyService] +
            [
                TScreenGeneratorService(
                                      cls.customize(prot=PolymerForm()), prefix)
                for cls in classes
            ],
            tns='%s.scr' % config.name,
            in_protocol=HttpRpc(validator='soft'),
            out_protocol=HtmlCloth(cloth=T_SCREEN, strip_comments=True,
                                                     doctype='<!DOCTYPE html>'),
            config=config,
        )
