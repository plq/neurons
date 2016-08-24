
import json

from spyne import ComplexModel, Array, Unicode, XmlAttribute, AnyUri, XmlData

SETUP_DATATABLES = """neurons.setup_datatables = function(data, hide) {
    var $table = $(data.selector);
    if (hide) {
        neurons.hide_empty_columns($table);
    }
    if ($table.length) {
        setTimeout(function () {
            $table.dataTable(data.dt_dict);
        }, 1);
    }
};
"""

HIDE_EMPTY_COLUMNS = """neurons.hide_empty_columns = function ($table) {
    $($table.find("tr")[1]).find("td").each(function (_, elt) {
        setTimeout(function () {
            var cc = $(elt).attr("class");
            if ($table.find("td." + cc).text() == "") {
                $table.find("td." + cc).hide();
                $table.find("th." + cc).hide();
            }
        }, 0);
    });
};
"""


class Link(ComplexModel):
    href = XmlAttribute(AnyUri)
    rel = XmlAttribute(Unicode(values=["stylesheet"]))


class CascadingStyleSheet(ComplexModel):
    data = XmlData(Unicode)
    type = XmlAttribute(Unicode(values=["text/css"]))
    title = XmlAttribute(Unicode)


class ScriptElement(ComplexModel):
    data = XmlData(Unicode)
    type = XmlAttribute(Unicode(values=["text/javascript"]))
    href = XmlAttribute(Unicode)


class ScreenBase(ComplexModel):
    class Attributes(ComplexModel.Attributes):
        logged = False

    datatables = None

    links = Array(Link, wrapped=False)
    styles = Array(CascadingStyleSheet, wrapped=False)
    scripts = Array(ScriptElement, wrapped=False)

    def __init__(self, ctx, *args, **kwargs):
        ComplexModel.__init__(self, *args, **kwargs)

        self._link_hrefs = set()
        self._have_jquery = False
        self._have_namespace = False
        self._have_hide_empty_columns = False
        self._have_setup_datatables = False

    def append_script_href(self, what, lang='text/javascript'):
        if self.scripts is None:
            self.scripts = []
        self.scripts.append(ScriptElement(href=what, lang=lang))

    def append_script(self, what):
        if self.scripts is None:
            self.scripts = []
        self.scripts.append(ScriptElement(what))

    def append_style(self, what):
        if self.styles is None:
            self.styles = []
        self.styles.append(what)

    def with_namespace(self):
        if not self._have_namespace:
            self.append_script("window.neurons = {}")

            self._have_namespace = True

    def with_jquery(self):
        if not self._have_jquery:
            self.append_script_href(
                                 "https://code.jquery.com/jquery-1.12.4.min.js")

            self._have_jquery = True

    def with_own_stylesheet(self, base='/assets/css/screen'):
        if self.links is None:
            self.links = []

        class_name = self.__class__.get_type_name()
        href = "%s/%s.css" % (base, class_name)

        if not (href in self._link_hrefs):
            self._link_hrefs.add(href)
            self.links.append(Link(rel="stylesheet", href=href))

        return self

    def with_setup_datatables(self):
        self.with_namespace()
        if not self._have_setup_datatables:
            self.append_script(SETUP_DATATABLES)

            self._have_setup_datatables = True
        return self

    def with_hide_empty_columns(self):
        self.with_namespace()
        if not self._have_hide_empty_columns:
            self.append_script(HIDE_EMPTY_COLUMNS)

            self._have_hide_empty_columns = True
        return self

    def with_datatables(self, data=None, hide_empty_columns=False):
        if data is None:
            data = self.datatables

        if hide_empty_columns:
            self.with_hide_empty_columns()

        self.with_setup_datatables()
        self.with_jquery()

        retval = [
            "$(document).ready(function() {",
                "neurons.setup_datatables(",
                    json.dumps(data), ",", json.dumps(hide_empty_columns),
                ");",
            "});",
        ]

        self.append_script(''.join(retval))

        return self
