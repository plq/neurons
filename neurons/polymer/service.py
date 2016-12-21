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

import logging
logger = logging.getLogger(__name__)

import re
import json

from lxml.builder import E

from spyne import ServiceBase, rpc, Unicode

from .model import PolymerComponent, PolymerScreen, HtmlImport


def _to_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()


def gen_component_imports(deps):
    for comp in deps:
        if isinstance(comp, HtmlImport):
            yield comp
            continue

        if '/' in comp:
            yield HtmlImport(
                href="/static/bower_components/{0}.html".format(comp)
            )

        else:
            yield HtmlImport(
                href="/static/bower_components/{0}/{0}.html".format(comp)
            )


def gen_component(cls, method_name, component_name, DetailScreen,
                                                               gen_css_imports):
    initial_data = {
        "is": component_name
    }

    deps = [
        'polymer',

        'iron-ajax',
        'iron-form',

        'paper-input',
        'paper-input/paper-textarea',

        # required for dropdown menu
        'paper-listbox',

        'paper-dropdown-menu',
        'paper-dropdown-menu/paper-dropdown-menu-light',

        HtmlImport(href='DateComponentScreen.definition'),
    ]

    styles = []
    if gen_css_imports:
        styles.append('@import url("/static/screen/{}.css")'
            .format(component_name))

    retval = DetailScreen(dom_module_id=component_name, main=cls())
    retval.definition = "Polymer({})".format(json.dumps(initial_data))
    retval.dependencies = gen_component_imports(deps)

    if len(styles) > 0:
        retval.style = '\n'.join(styles)

    return retval


def TComponentGeneratorService(cls, prefix=None, locale=None,
                                                         gen_css_imports=False):
    type_name = cls.get_type_name()
    component_name = _to_snake_case(type_name)

    if prefix is not None:
        component_name = "{}-{}".format(prefix, component_name)

    method_name = component_name + ".html"

    class DetailScreen(PolymerComponent):
        __type_name__ = '{}DetailComponent'.format(type_name)
        main = cls

    class ComponentGeneratorService(ServiceBase):
        @rpc(Unicode(6), _returns=DetailScreen, _body_style='out_bare',
            _in_message_name=method_name,
            _internal_key_suffix='_' + component_name)
        def _gen_component(self, locale):
            if locale is not None:
                ctx.locale = locale
                logger.debug("Locale override local.")
            return gen_component(cls, method_name, component_name, DetailScreen,
                                                                gen_css_imports)

    if locale is not None:
        def _fix_locale(ctx):
            if ctx.locale is None:
                ctx.locale = 'tr_TR'
                logger.debug("Locale override generic.")

        ComponentGeneratorService.event_manager \
                                       .add_listener('method_call', _fix_locale)

    return ComponentGeneratorService


def TScreenGeneratorService(cls, prefix=None):
    type_name = cls.get_type_name()
    component_name = _to_snake_case(type_name)

    if prefix is not None:
        component_name = "{}-{}".format(prefix, component_name)

    method_name = component_name + ".html"

    class ScreenGeneratorService(ServiceBase):
        @rpc(Unicode(6), _returns=PolymerScreen, _body_style='out_bare',
            _in_message_name=method_name,
            _internal_key_suffix='_' + component_name)
        def _gen_screen(self, locale):
            retval = PolymerScreen(
                title=type_name,
                element=E(component_name),
            )

            if locale is None:
                retval.dependencies = [
                    HtmlImport(
                        href="/comp/{}".format(method_name)
                    ),
                ]

            else:
                retval.dependencies = [
                    HtmlImport(
                        href="/comp/{}?locale={}".format(method_name, locale)
                    )
                ]

            return retval

    return ScreenGeneratorService
