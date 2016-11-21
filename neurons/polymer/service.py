
import re, json

from itertools import chain

from spyne import ServiceBase, rpc

from .model import DomModule, HtmlImport


def _to_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()


def _gen_init_data(cls, method_name):
    return {
        "is": method_name
    }


def TComponentGeneratorService(cls, prefix=None, locale=None,
                                                         gen_css_imports=False):
    type_name = cls.get_type_name()
    component_name = _to_snake_case(type_name)

    if prefix is not None:
        component_name = "{}-{}".format(prefix, component_name)

    method_name = component_name + ".html"

    class DetailScreen(DomModule):
        __type_name__ = '{}DetailScreen'.format(type_name)
        main = cls

    class ComponentGeneratorService(ServiceBase):
        @rpc(_returns=DetailScreen, _body_style='bare',
            _in_message_name=method_name)
        def gen_form(self):
            init_data = _gen_init_data(cls, component_name)
            deps = ['polymer', 'paper-input', 'paper-input/paper-textarea',
                'paper-dropdown-menu']

            styles = []
            if gen_css_imports:
                styles.append('@import url("/static/screen/{}.css")'
                                                        .format(component_name))

            retval = DetailScreen(dom_module_id=component_name, main=cls())
            retval.definition = "Polymer({})".format(json.dumps(init_data))
            retval.dependencies = chain(
                [
                    HtmlImport(
                        href="/static/bower_components/{0}/{0}.html".format(comp)
                    )
                    for comp in deps if not '/' in comp
                ],
                [
                    HtmlImport(
                        href="/static/bower_components/{0}.html".format(comp)
                    )
                    for comp in deps if '/' in comp
                ])

            if len(styles) > 0 :
                retval.style = '\n'.join(styles)

            return retval

    if locale is not None:
        def _fix_locale(ctx):
            ctx.locale = 'tr_TR'

        ComponentGeneratorService.event_manager \
                                       .add_listener('method_call', _fix_locale)


    return ComponentGeneratorService
