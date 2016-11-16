
from lxml import html
from pkg_resources import resource_filename

T_DOM_MODULE = html.fragment_fromstring(
    open(resource_filename(__name__, 'dom_module.html'), 'rb').read(),
                                                     create_parent='spyne-root')

T_DOM_MODULE.attrib['spyne-tagbag'] = ''
