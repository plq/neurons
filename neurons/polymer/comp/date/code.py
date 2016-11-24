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

import json

from neurons.polymer.comp.date import T_DATE
from neurons.polymer.model import PolymerComponent
from neurons.polymer.service import gen_component_imports

from spyne import ComplexModel, Unicode, SelfReference
from spyne import mrpc

__comp_name__ = 'neurons-date-picker'


class DateComponent(ComplexModel):
    label_ok = Unicode
    label_cancel = Unicode


class DateComponentScreen(PolymerComponent):
    class Attributes(ComplexModel.Attributes):
        html_cloth = T_DATE

    main = DateComponent

    @mrpc(_returns=SelfReference, _body_style='bare')
    def definition(self, ctx):
        initial_data = {
            "is": __comp_name__
        }

        deps = [
            'polymer',

            'paper-date-picker',
            'paper-dialog',
            'paper-button',
        ]

        styles = []

        retval = DateComponentScreen(dom_module_id=__comp_name__,
            main=DateComponent(
                label_ok="OK",
                label_cancel="Cancel"
            )
        )
        retval.definition = "Polymer({})".format(json.dumps(initial_data))
        retval.dependencies = gen_component_imports(deps)

        if len(styles) > 0:
            retval.style = '\n'.join(styles)

        return retval
