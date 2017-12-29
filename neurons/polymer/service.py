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

import re

from spyne import Service, rpc, Unicode, ComplexModel, XmlAttribute
from spyne.protocol.cloth import XmlCloth

from slimit.mangler import mangle as slimit_mangler
from slimit.visitors.minvisitor import ECMAMinifier

from neurons.base.screen import Link
from neurons.polymer.jsutil import get_js_parser, set_js_variable
from neurons.polymer.const import POLYMER_PREAMBLE, DEFAULT_URL_POLYFILL
from neurons.polymer.const import POLYMER_DEFN_TEMPLATE

from .model import PolymerComponent, HtmlImport, IronAjax, PolymerScreen


def _to_snake_case(name, delim='-'):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1%s\2' % delim, name)
    return re.sub('([a-z0-9])([A-Z])', r'\1%s\2' % delim, s1).lower()


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


def gen_polymer_defn(component_name, cls, minify=False):
    parser = get_js_parser()
    tree = parser.parse(POLYMER_DEFN_TEMPLATE)

    entries = tree.children()[0].children()[0].children()[1].children()

    # set tag name
    e0 = entries[0]
    assert e0.left.value == 'is'
    e0.right.value = '"{}"'.format(component_name)

    if minify:
        slimit_mangler(tree, toplevel=True)
        retval = ECMAMinifier().visit(tree)
    else:
        retval = tree.to_ecma()

    return retval


def gen_component(cls, component_name, DetailScreen, gen_css_imports, minify_js,
                                     api_read_url_prefix, api_write_url_prefix):
    deps = [
        'polymer',

        'iron-ajax',
        'iron-form',

        'paper-input',
        'paper-input/paper-textarea',
        'paper-checkbox',

        # required for dropdown menu
        'paper-item',
        'paper-listbox',

        'paper-dropdown-menu',
        'paper-dropdown-menu/paper-dropdown-menu-light',

        HtmlImport(href='neurons-array.html'),
        HtmlImport(href='neurons-date-time/neurons-datetime-picker.html'),
        HtmlImport(href='neurons-complex-reference/neurons-complex-dropdown.html'),
        HtmlImport(href='neurons-complex-reference/neurons-complex-href.html'),
    ]

    styles = []
    if gen_css_imports:
        styles.append('@import url("/static/screen/{}.css")'
                                                        .format(component_name))

    getter_url = "{}{}.get".format(api_read_url_prefix, cls.get_type_name())
    putter_url = "{}{}.put".format(api_write_url_prefix, cls.get_type_name())

    retval = DetailScreen(
        main=(cls.__orig__ or cls)(),
        getter=IronAjax(url=getter_url),
        putter=IronAjax(url=putter_url),
        dom_module_id=component_name,
        definition=gen_polymer_defn(component_name, cls, minify=minify_js),
        dependencies=gen_component_imports(deps),
    )

    if len(styles) > 0:
        retval.style = '\n'.join(styles)

    return retval


def TComponentGeneratorService(cls, prefix=None, locale=None,
                     gen_css_imports=False, minify_js=False,
                               api_read_url_prefix='', api_write_url_prefix=''):
    type_name = cls.get_type_name()
    component_name = _to_snake_case(type_name)

    if prefix is not None:
        component_name = "{}-{}".format(prefix, component_name)

    method_name = component_name + ".html"

    class DetailScreen(PolymerComponent):
        __type_name__ = '{}DetailComponent'.format(type_name)
        main = cls

    class ComponentGeneratorService(Service):
        @rpc(Unicode(6), _returns=DetailScreen, _body_style='out_bare',
            _in_message_name=method_name,
            _internal_key_suffix='_' + component_name)
        def _gen_component(ctx, locale):
            if locale is not None:
                ctx.locale = locale
                logger.debug("Locale overridden to %s locally.", locale)
            return gen_component(cls, component_name, DetailScreen,
                             gen_css_imports, minify_js, api_read_url_prefix,
                                                         api_write_url_prefix)

    if locale is not None:
        def _fix_locale(ctx):
            if ctx.locale is None:
                ctx.locale = 'tr_TR'
                logger.debug("Locale overridden to %s.", ctx.locale)

        ComponentGeneratorService.event_manager \
                                       .add_listener('method_call', _fix_locale)

    return ComponentGeneratorService


def _get_getter_input(cls):
    try:
        getter_descriptor = cls.Attributes.methods['get']
    except KeyError:
        raise Exception("%r needs a getter", cls)

    return getter_descriptor.in_message


class ScreenParams(ComplexModel):
    locale = Unicode(6)


def TScreenGeneratorService(cls, prefix=None, url_polyfill=DEFAULT_URL_POLYFILL,
              url_service_worker=None, minify_js=False, comp_prefix=''):
    type_name = cls.get_type_name()
    component_name = _to_snake_case(type_name)

    if prefix is not None:
        component_name = "{}-{}".format(prefix, component_name)

    method_name = component_name + ".html"

    getter_in_cls = _get_getter_input(cls)

    class DetailScreen(PolymerScreen):
        main = getter_in_cls.customize(
            protocol=XmlCloth(),
            sub_name=component_name,
        )

    class ScreenGeneratorService(Service):
        @rpc(getter_in_cls, ScreenParams, _returns=PolymerScreen,
            _body_style='out_bare', _in_message_name=method_name,
            _internal_key_suffix='_' + component_name)
        def _gen_screen(ctx, query, params):
            if query is None:
                query = getter_in_cls()

            retval = DetailScreen(ctx, title=type_name, main=query) \
                .with_jquery() \
                .with_xml_to_jsobj() \
                .with_type_checkers() \
                .with_clone() \
                .with_urlencode()

            if params is not None and params.locale is not None:
                retval.links = [
                    Link(
                        rel='import',
                        href="{}/{}?locale={}".format(comp_prefix, method_name,
                                                                  params.locale)
                    )
                ]

            else:
                retval.links = [
                    Link(
                        rel='import',
                        href="{}/{}".format(comp_prefix, method_name)
                    ),
                ]

            data = {'url_polyfill': url_polyfill}
            if url_service_worker is not None:
                data['service_worker_url'] = url_service_worker

            tree = get_js_parser().parse(POLYMER_PREAMBLE)
            set_js_variable(tree, 'polymer_init_options', data)
            retval.append_script_tree(tree, minify=minify_js)

            return retval

    return ScreenGeneratorService
