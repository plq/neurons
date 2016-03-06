# encoding: utf8
#
# retrieved from http://www.aminus.net/wiki/Dowser at 2015-03-18
# this document were placed in public domain by their author
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

import cgi
import os
import gc
import sys

from types import FrameType, ModuleType
from collections import defaultdict

from neurons.daemon.dowser.const import ASSETS_DIR

from spyne import rpc, Unicode, ServiceBase, ByteArray, AnyHtml
from spyne import Integer
from spyne.protocol.http import HttpPattern, HttpRpc
from spyne.util.six import BytesIO

from neurons.daemon.dowser import reftree


try:
    from PIL import Image
    from PIL import ImageDraw

except ImportError as e:
    class Image:
        @classmethod
        def new(self):
            raise e

    ImageDraw = None


def get_repr(obj, limit=250):
    return cgi.escape(reftree.get_repr(obj, limit))


class _(object): pass


dictproxy = type(_.__dict__)

method_types = [
    type(tuple.__le__),  # 'wrapper_descriptor'
    type([1].__le__),  # 'method-wrapper'
    type(sys.getcheckinterval),  # 'builtin_function_or_method'
    type(cgi.FieldStorage.getfirst),  # 'instancemethod'
]


def template(name, **params):
    p = {
        'maincss': "/assets/main.css",
        'home': "/",
    }
    p.update(params)
    return open(os.path.join(ASSETS_DIR, name)).read() % p


class DowserServices(ServiceBase):
    period = 5
    maxhistory = 300
    history = {}
    samples = 0
    id_history = []
    max_id_history = 2

    @classmethod
    def tick(cls):
        logger.debug("Dowser tick")
        gc.collect()

        typecounts = {}
        new_ids = defaultdict(set)
        for obj in gc.get_objects():
            objtype = type(obj)
            typename = ".".join((objtype.__module__, objtype.__name__))
            new_ids[typename].add(id(obj))

            if objtype in typecounts:
                typecounts[objtype] += 1
            else:
                typecounts[objtype] = 1

        if len(DowserServices.id_history) > DowserServices.max_id_history:
            DowserServices.id_history.pop(0)
        DowserServices.id_history.append(new_ids)

        for objtype, count in typecounts.items():
            typename = objtype.__module__ + "." + objtype.__name__
            if typename not in cls.history:
                cls.history[typename] = [0] * cls.samples
            cls.history[typename].append(count)

        samples = cls.samples + 1

        # Add dummy entries for any types which no longer exist
        for typename, hist in cls.history.items():
            diff = samples - len(hist)
            if diff > 0:
                hist.extend([0] * diff)

        # Truncate history to self.maxhistory
        if samples > cls.maxhistory:
            for typename, hist in cls.history.items():
                hist.pop(0)
        else:
            cls.samples = samples

    ORDER_MAP = {
        None: None,
        'min': lambda x: min(DowserServices.history[x]),
        'cur': lambda x: DowserServices.history[x][-1],
        'max': lambda x: max(DowserServices.history[x]),
        'diff': lambda x: len(DowserServices.id_history[-1][x]) - \
                          len(DowserServices.id_history[0][x]),
    }

    @rpc(Unicode(values=['max', 'min', 'cur', 'diff']), Integer(default=0),
                     Integer(default=0), Integer(default=0), Integer(default=0),
                     _patterns=[HttpPattern('/', verb='GET')], _returns=AnyHtml)
    def index(ctx, order, cur_floor, min_floor, max_floor, diff_floor):
        rows = []
        typenames = ctx.descriptor.service_class.history.keys()

        key = ctx.descriptor.service_class.ORDER_MAP[order]
        typenames.sort(key=key, reverse=False if order is None else True)

        for typename in typenames:
            hist = ctx.descriptor.service_class.history[typename]

            # get numbers
            maxhist = max(hist)
            minhist = max(hist)
            cur = hist[-1]

            idhist = DowserServices.id_history
            last = idhist[-1][typename]
            first = idhist[0][typename]
            diff = len(last) - len(first)

            # check floors
            show_this = cur >= cur_floor and \
                        minhist >= min_floor and \
                        maxhist >= max_floor and \
                        abs(diff) >= diff_floor

            if not show_this:
                continue

            row = (
                '<div class="typecount">%s<br />'
                '<img class="chart" src="%s" /><br />'
                'Min: %s Cur: %s Max: %s Diff: %s '
                '<a href="%s">TRACE</a> &middot; '
                '<a href="%s">DIFF TRACE</a>'
                '</div>' % (
                    cgi.escape(typename),
                    "/chart?typename=%s" % typename,
                    minhist, cur, maxhist, diff,
                    "/trace?typename=%s" % typename,
                    "/difftrace?typename=%s" % typename,
                )
            )
            rows.append(row)

        return template("graphs.html", output="\n".join(rows))

    @rpc(Unicode, _returns=ByteArray)
    def chart(ctx, typename):
        """Return a sparkline chart of the given type."""

        data = ctx.descriptor.service_class.history[typename]
        height = 20.0
        scale = height / max(data)
        im = Image.new("RGB", (len(data), int(height)), 'white')
        draw = ImageDraw.Draw(im)
        draw.line([(i, int(height - (v * scale))) for i, v in enumerate(data)],
                                                                 fill="#009900")
        del draw

        f = BytesIO()
        im.save(f, "PNG")
        result = f.getvalue()

        ctx.out_protocol = HttpRpc()
        ctx.transport.resp_headers["Content-Type"] = "image/png"
        return [result]

    @rpc(Unicode, Integer, _returns=AnyHtml)
    def trace(ctx, typename, objid):
        gc.collect()

        if objid is None:
            rows = DowserServices.trace_all(typename)
        else:
            rows = DowserServices.trace_one(typename, objid)

        return template("trace.html", output="\n".join(rows),
                        typename=cgi.escape(typename),
                        objid=str(objid or ''))

    @rpc(Unicode, _returns=AnyHtml)
    def difftrace(ctx, typename):
        gc.collect()

        rows = DowserServices.trace_all(typename, difftrace=True)

        return template("trace.html", output="\n".join(rows),
                                        typename=cgi.escape(typename), objid='')

    @classmethod
    def trace_all(cls, typename, difftrace=False):
        rows = []
        for obj in gc.get_objects():
            objtype = type(obj)
            if objtype.__module__ + "." + objtype.__name__ == typename and \
                    ((not difftrace) or (
                             id(obj) in DowserServices.id_history[-1] and
                        (not id(obj) in DowserServices.id_history[0])
                    )):
                rows.append("<p class='obj'>%s</p>"
                            % ReferrerTree(obj).get_repr(obj))

        if not rows:
            rows = ["<h3>The type you requested was not found.</h3>"]

        return rows

    @classmethod
    def trace_one(cls, typename, objid):
        rows = []
        all_objs = gc.get_objects()
        for obj in all_objs:
            if id(obj) == objid:
                objtype = type(obj)
                if objtype.__module__ + "." + objtype.__name__ != typename:
                    rows = ["<h3>The object you requested is no longer "
                            "of the correct type.</h3>"]
                else:
                    # Attributes
                    rows.append('<div class="obj"><h3>Attributes</h3>')
                    for k in dir(obj):
                        v = getattr(obj, k)
                        if type(v) not in method_types:
                            rows.append('<p class="attr"><b>%s:</b> %s</p>' %
                                        (k, get_repr(v)))
                        del v
                    rows.append('</div>')

                    # Referrers
                    rows.append(
                        '<div class="refs"><h3>Referrers (Parents)</h3>')
                    rows.append('<p class="desc"><a href="%s">Show the '
                                'entire tree</a> of reachable objects</p>'
                                % (
                    "/tree?typename=%s&objid=%s" % (typename, objid)))
                    tree = ReferrerTree(obj)
                    tree.ignore(all_objs)
                    for depth, parentid, parentrepr in tree.walk(maxdepth=1):
                        if parentid:
                            rows.append("<p class='obj'>%s</p>" % parentrepr)
                    rows.append('</div>')

                    # Referents
                    rows.append(
                        '<div class="refs"><h3>Referents (Children)</h3>')
                    for child in gc.get_referents(obj):
                        rows.append(
                            "<p class='obj'>%s</p>" % tree.get_repr(child))
                    rows.append('</div>')
                break
        if not rows:
            rows = ["<h3>The object you requested was not found.</h3>"]
        return rows

    @rpc(Unicode, Integer, _returns=AnyHtml)
    def tree(self, typename, objid):
        gc.collect()

        rows = []
        all_objs = gc.get_objects()
        for obj in all_objs:
            if id(obj) == objid:
                objtype = type(obj)
                if objtype.__module__ + "." + objtype.__name__ != typename:
                    rows = ["<h3>The object you requested is no longer "
                            "of the correct type.</h3>"]
                else:
                    rows.append('<div class="obj">')

                    tree = ReferrerTree(obj)
                    tree.ignore(all_objs)
                    for depth, parentid, parentrepr in tree.walk(
                            maxresults=1000):
                        rows.append(parentrepr)

                    rows.append('</div>')
                break

        if not rows:
            rows = ["<h3>The object you requested was not found.</h3>"]

        params = {
            'output': "\n".join(rows),
            'typename': cgi.escape(typename),
            'objid': str(objid),
        }

        return template("tree.html", **params)


class ReferrerTree(reftree.Tree):
    ignore_modules = True

    def _gen(self, obj, depth=0):
        if self.maxdepth and depth >= self.maxdepth:
            yield depth, 0, "---- Max depth reached ----"
            raise StopIteration()

        if isinstance(obj, ModuleType) and self.ignore_modules:
            raise StopIteration()

        refs = gc.get_referrers(obj)
        refiter = iter(refs)
        self.ignore(refs, refiter)
        thisfile = sys._getframe().f_code.co_filename
        for ref in refiter:
            # Exclude all frames that are from this module or reftree.
            if (isinstance(ref, FrameType)
                       and ref.f_code.co_filename in (thisfile, self.filename)):
                continue

            # Exclude all functions and classes from this module or reftree.
            mod = getattr(ref, "__module__", "")
            if mod is None:
                continue

            if "dowser" in mod or "reftree" in mod or mod == '__main__':
                continue

            # Exclude all parents in our ignore list.
            if id(ref) in self._ignore:
                continue

            # Yield the (depth, id, repr) of our object.
            yield depth, 0, '%s<div class="branch">' % (" " * depth)

            if id(ref) in self.seen:
                yield depth, id(ref), "see %s above" % id(ref)

            else:
                self.seen[id(ref)] = None
                yield depth, id(ref), self.get_repr(ref, obj)

                for parent in self._gen(ref, depth + 1):
                    yield parent

            yield depth, 0, '%s</div>' % (" " * depth)

    def get_repr(self, obj, referent=None):
        """Return an HTML tree block describing the given object."""
        objtype = type(obj)
        typename = objtype.__module__ + "." + objtype.__name__
        prettytype = typename.replace("__builtin__.", "")

        name = getattr(obj, "__name__", "")
        if name:
            prettytype = "%s %r" % (prettytype, name)

        key = ""
        if referent:
            key = self.get_refkey(obj, referent)
        return ('<a class="objectid" href="%s">%s</a> '
                '<span class="typename">%s</span>%s<br />'
                '<span class="repr">%s</span>'
                % (("/trace?typename=%s&objid=%s" % (typename, id(obj))),
                   id(obj), prettytype, key, get_repr(obj, 100))
                )

    def get_refkey(self, obj, referent):
        """Return the dict key or attribute name of obj which refers to
        referent."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if v is referent:
                    return " (via its %r key)" % (k,)

        for k in dir(obj) + ['__dict__']:
            if getattr(obj, k, None) is referent:
                return " (via its %r attribute)" % (k,)
        return ""
