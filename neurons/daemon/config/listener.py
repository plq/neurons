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


from __future__ import print_function, absolute_import

import logging
logger = logging.getLogger(__name__)

import re

from os.path import abspath

from spyne import Application, UnsignedInteger, ComplexModel, Unicode, \
    UnsignedInteger16, Boolean, String, Array, ComplexModelBase

from neurons.daemon.cli import config_overrides
from neurons.daemon.config._wdict import wdict, wrdict, Twrdict


class Service(ComplexModel):
    name = Unicode

    def __init__(self, *args, **kwargs):
        self._parent = None

        super(Service, self).__init__(*args, **kwargs)

    def set_parent(self, parent):
        assert self._parent is None
        assert parent is not None

        self._parent = parent


class Listener(Service):
    host = Unicode
    port = UnsignedInteger16
    disabled = Boolean
    unix_socket = Unicode

    def check_overrides(self):
        for a in config_overrides:
            if a.startswith('--host-%s' % self.name):
                _, host = a.split('=', 1)
                self.host = host
                logger.debug("Overriding host for service '%s' to '%s'",
                                                           self.name, self.host)

                continue

            if a.startswith('--port-%s' % self.name):
                _, port = a.split('=', 1)
                self.port = int(port)
                logger.debug("Overriding port for service '%s' to '%s'",
                                                           self.name, self.port)

                continue


class SslListener(Listener):
    cacert = Unicode
    cacert_path = Unicode
    cacert_dir = Unicode

    cert = Unicode
    cert_path = Unicode

    privcert = Unicode
    privcert_path = Unicode

    key = Unicode
    key_path = Unicode


class HttpApplication(ComplexModel):
    url = Unicode

    def __init__(self, app=None, url=None):
        super(HttpApplication, self).__init__(url=url)
        self.app = app

    def gen_resource(self):
        from spyne.server.twisted import TwistedWebResource
        from spyne.server.wsgi import WsgiApplication
        from spyne.util.wsgi_wrapper import WsgiMounter

        from twisted.internet import reactor
        from twisted.web.resource import Resource
        from twisted.web.wsgi import WSGIResource

        if isinstance(self.app, Resource):
            retval = self.app

        elif isinstance(self.app, Application):
            retval = TwistedWebResource(self.app)

        elif isinstance(self.app, (WsgiApplication, WsgiMounter)):
            retval = WSGIResource(reactor, reactor.getThreadPool(), self.app)

        else:
            raise ValueError(self.app)

        retval.prepath = self.url
        return retval


class StaticFileServer(HttpApplication):
    path = String
    list_contents = Boolean(default=False)
    disallowed_exts = Array(Unicode, default_factory=tuple)

    def __init__(self, *args, **kwargs):
        # We need the default ComplexModelBase ctor and not HttpApplication's
        # custom ctor here

        ComplexModelBase.__init__(self, *args, **kwargs)

    def gen_resource(self):
        if self.list_contents:
            from neurons.daemon.config.static_file import TCheckedFile
            CheckedFile = TCheckedFile(self.disallowed_exts, self.url)

            return CheckedFile(abspath(self.path))

        from neurons.daemon.config.static_file import TStaticFile
        StaticFile = TStaticFile(self.disallowed_exts, self.url)

        return StaticFile(abspath(self.path))


class HttpListener(Listener):
    _type_info = [
        ('static_dir', Unicode),
        ('_subapps', Array(HttpApplication, sub_name='subapps')),
    ]

    def _push_asset_dir_overrides(self, obj):
        if obj.url == '':
            key = '--assets-%s=' % self.name
        else:
            suburl = re.sub(r'[\.-/]+', obj.url, '-')
            key = '--assets-%s-%s=' % (self.name, suburl)

        for a in config_overrides:
            if a.startswith(key):
                _, dest = a.split('=', 1)
                obj.path = abspath(dest)

                logger.debug(
                    "Overriding asset path for app '%s', url '%s' to '%s'" % (
                                                  self.name, obj.url, obj.path))

    def __init__(self, *args, **kwargs):
        super(HttpListener, self).__init__(*args, **kwargs)

        subapps = kwargs.get('subapps', None)
        if isinstance(subapps, dict):
            self.subapps = Twrdict(self, 'url')()
            for k, v in subapps.items():
                self.subapps[k] = v

        elif isinstance(subapps, (tuple, list)):
            self.subapps = Twrdict(self, 'url')()
            for v in subapps:
                assert v.url is not None, "%r.url is None" % v
                self.subapps[v.url] = v

    def gen_site(self):
        from twisted.web.server import Site

        self.check_overrides()

        subapps = []
        for url, subapp in self.subapps.items():
            if isinstance(subapp, StaticFileServer):
                self._push_asset_dir_overrides(subapp)

            if isinstance(subapp, HttpApplication):
                assert subapp.url is not None, subapp.app
                if hasattr(subapp, 'app'):
                    if subapp.app is None:
                        logger.warning("No subapp '%s' found in app '%s': "
                                       "Invalid key.", subapp.url, self.name)
                        continue
                subapps.append(subapp)

            else:
                subapps.append(HttpApplication(subapp, url=url))

        self._subapps = subapps

        root_app = self.subapps.get('', None)

        if root_app is None:
            from spyne.server.twisted.http import get_twisted_child_with_default
            from twisted.web.resource import Resource

            class TwistedResource(Resource):
                def getChildWithDefault(self, path, request):
                    return get_twisted_child_with_default(self, path, request)

            root = TwistedResource()
            root.prepath = '/'
        else:
            root = root_app.gen_resource()

        for subapp in self._subapps:
            if subapp.url != '':
                root.putChild(subapp.url, subapp.gen_resource())

        retval = Site(root)

        retval.displayTracebacks = self._parent.debug
        return retval

    @property
    def _subapps(self):
        if self.subapps is not None:
            for k, v in self.subapps.items():
                v.url = k

            return self.subapps.values()

        self.subapps = wrdict()
        return []

    @_subapps.setter
    def _subapps(self, what):
        self.subapps = what
        if what is not None:
            self.subapps = wdict([(s.url, s) for s in what])


class WsgiListener(HttpListener):
    thread_min = UnsignedInteger
    thread_max = UnsignedInteger
