
from spyne import Unicode, ComplexModel, XmlAttribute


class HtmlImport(ComplexModel):
    href = XmlAttribute(Unicode)


class DomModule(ComplexModel):
    style = Unicode
    definition = Unicode
    dependencies = HtmlImport.customize(max_occurs='unlimited')
    dom_module_id = Unicode(sub_name="id")
