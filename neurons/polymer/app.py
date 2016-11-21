
from spyne import Application
from spyne.protocol.html import HtmlCloth
from spyne.protocol.http import HttpRpc

from .const import T_DOM_MODULE


def gen_components_app(config, prefix, classes, locale=None):
    from neurons.polymer.service import TComponentGeneratorService

    return \
        Application(
            [
                TComponentGeneratorService(cls, prefix, locale)
                                                              for cls in classes
            ],
            tns='ruzgar.web', name='Components',
            in_protocol=HttpRpc(validator='soft'),
            out_protocol=HtmlCloth(cloth=T_DOM_MODULE,
                                                     doctype='<!DOCTYPE html>'),
            config=config,
        )
