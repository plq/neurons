
import re, json

from spyne import ServiceBase, rpc

from .model import DomModule, HtmlImport


def _to_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()


def _gen_init_data(cls, method_name):
    return {
        "is": method_name
    }


def TComponentGeneratorService(cls, prefix=None, locale=None):
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
            retval = DetailScreen(dom_module_id=component_name, main=cls())

            init_data = _gen_init_data(cls, component_name)

            retval.definition = "Polymer({})".format(json.dumps(init_data))

            retval.dependencies = [
                HtmlImport(
                    href="/static/bower_components/polymer/polymer.html"
                ),
            ]

            return retval

    if locale is not None:
        def _fix_locale(ctx):
            ctx.locale = 'tr_TR'

        ComponentGeneratorService.event_manager \
                                       .add_listener('method_call', _fix_locale)


    return ComponentGeneratorService
