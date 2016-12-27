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

from spyne import ServiceBase, rpc, Unicode, ComplexModel
from spyne.protocol.html import HtmlCloth

from neurons.base.screen import Link
from neurons.jsutil import get_js_parser, set_js_variable

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


POLYMER_PREAMBLE = """
var polymer_init_options = {};

// Setup Polymer options
window.Polymer = {
  dom: 'shadow',
  lazyRegister: true
};

// Load webcomponentsjs polyfill if browser does not support native Web Components
(function () {
  'use strict';

  var onload = function () {
    // For native Imports, manually fire WebComponentsReady so user code
    // can use the same code path for native and polyfill'd imports.
    if (!window.HTMLImports) {
      document.dispatchEvent(
              new CustomEvent('WebComponentsReady', {bubbles: true})
      );
    }
  };

  var webComponentsSupported = (
          'registerElement' in document &&
                           'import' in document.createElement('link') &&
                           'content' in document.createElement('template'));

  if (!webComponentsSupported) {
    var script = document.createElement('script');
    script.async = true;
    script.src = polymer_init_options.url_polyfill;
    script.onload = onload;
    document.head.appendChild(script);
  }
  else {
    onload();
  }
})();

// Load pre-caching Service Worker
if (polymer_init_options.url_service_worker) {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register(polymer_init_options.url_service_worker);
    });
  }
}
"""


POLYMER_DEFN_TEMPLATE = """
Polymer({is: "blabla"
    ,properties: {

    }
    ,listeners: {
      'iron-form-presubmit': '_presubmit',
      'iron-form-element-register': '_register_element',
    }
    ,created: function() {
        this._elements = {};
    }
    ,attached: function() {
        var children = this.getEffectiveChildren();
        var retval = neurons.xml_to_jsobj(children);
        var getter = this.$.ajax_getter;
        getter.params = retval;
        getter.generateRequest();
    }
    ,process_getter_response: function(e) {
        var resp = e.detail.response;
        var form = this.$.form;

        for (var k in resp) {
            var elt = this._elements[k];
            if (! elt) {
                continue;
            }

            elt.value = resp[k];
        }

        if (window.console) console.log(resp);
    }
    ,_register_element: function(e) {
        var elt = Polymer.dom(e).rootTarget;
        this._elements[elt.getAttribute('name')] = elt;
    }
    ,_presubmit: function(e) {
        e.preventDefault();

        var data = this.$.form.serialize();
        if (window.console) console.log(data);

        var putter = this.$.ajax_putter;
        putter.params = retval;
        putter.generateRequest();
    }
})
"""


def gen_polymer_defn(component_name, cls):
    parser = get_js_parser()
    tree = parser.parse(POLYMER_DEFN_TEMPLATE)

    entries = tree.children()[0].children()[0].children()[1].children()

    # set tag name
    e0 = entries[0]
    assert e0.left.value == 'is'
    e0.right.value = '"{}"'.format(component_name)

    return tree.to_ecma()


def gen_component(cls, component_name, DetailScreen, gen_css_imports):
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

        HtmlImport(href='DateComponentScreen.definition'),
    ]

    styles = []
    if gen_css_imports:
        styles.append('@import url("/static/screen/{}.css")'
            .format(component_name))

    # FIXME: stop hardcoding /api
    getter_url = "/api/{}.get".format(cls.get_type_name())

    putter_url = "/api/{}.put".format(cls.get_type_name())

    retval = DetailScreen(
        main=cls(),
        getter=IronAjax(url=getter_url),
        putter=IronAjax(url=putter_url),
        dom_module_id=component_name,
        definition=gen_polymer_defn(component_name, cls),
        dependencies=gen_component_imports(deps),
    )

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
        def _gen_component(ctx, locale):
            if locale is not None:
                ctx.locale = locale
                logger.debug("Locale overridden to %s locally.", locale)
            return gen_component(cls, component_name, DetailScreen,
                                                                gen_css_imports)

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


DEFAULT_URL_POLYFILL = \
            '/static/bower_components/webcomponentsjs/webcomponents-lite.min.js'


def TScreenGeneratorService(cls, prefix=None, url_polyfill=DEFAULT_URL_POLYFILL,
                                                       url_service_worker=None):
    type_name = cls.get_type_name()
    component_name = _to_snake_case(type_name)

    if prefix is not None:
        component_name = "{}-{}".format(prefix, component_name)

    method_name = component_name + ".html"

    getter_in_cls = _get_getter_input(cls)

    class DetailScreen(PolymerScreen):
        main = getter_in_cls.customize(
            protocol=HtmlCloth(),
            sub_name=component_name,
        )

    class ScreenGeneratorService(ServiceBase):
        @rpc(getter_in_cls, ScreenParams, _returns=PolymerScreen,
            _body_style='out_bare', _in_message_name=method_name,
            _internal_key_suffix='_' + component_name)
        def _gen_screen(ctx, query, params):
            if query is None:
                query = getter_in_cls()

            retval = DetailScreen(ctx, title=type_name, main=query) \
                .with_jquery() \
                .with_xml_to_jsobj()

            if params is not None and params.locale is not None:
                retval.links = [
                    Link(
                        rel='import',
                        href="/comp/{}?locale={}".format(method_name,
                                                                  params.locale)
                    )
                ]

            else:
                retval.links = [
                    Link(
                        rel='import',
                        href="/comp/{}".format(method_name)
                    ),
                ]

            data = {'url_polyfill': url_polyfill}
            if url_service_worker is not None:
                data['service_worker_url'] = url_service_worker

            tree = get_js_parser().parse(POLYMER_PREAMBLE)
            preamble = set_js_variable(tree, 'polymer_init_options', data)
            retval.append_script(preamble)

            return retval

    return ScreenGeneratorService
