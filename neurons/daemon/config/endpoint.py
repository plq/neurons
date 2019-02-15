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

import os
import re

from threading import Lock
from os.path import abspath, join, isfile

from colorama import Fore, Style

from spyne import Application, UnsignedInteger, ComplexModel, Unicode, \
    UnsignedInteger16, Boolean, String, Array, ComplexModelBase, M, \
    ValidationError, Integer32
from spyne.util.resource import get_resource_path

from neurons.daemon import EXIT_ERR_LISTEN_TCP, EXIT_ERR_LISTEN_UDP, \
                                                                EXIT_ERR_UNKNOWN
from neurons.daemon.cli import config_overrides
from neurons.daemon.config._wdict import wdict, Twdict


class Service(ComplexModel):
    name = M(Unicode)
    disabled = Boolean(default=False)

    def __init__(self, *args, **kwargs):
        self._parent = None
        self.color = None

        super(Service, self).__init__(*args, **kwargs)

    def set_parent(self, parent):
        assert self._parent is None
        assert parent is not None

        self._parent = parent

    def _parse_overrides(self):
        pass

    @property
    def colored_name(self):
        if self.color is None:
            return self.name

        return '%s%s[%s]%s' % (self.color, Style.BRIGHT, self.name,
                                                                Style.RESET_ALL)


# noinspection PyPep8Naming
def _TFactoryProxy():
    from twisted.internet.protocol import ServerFactory

    class FactoryProxy(ServerFactory):
        def __init__(self):
            # real_factory is set by neurons.daemon.main
            self.real_factory = None
            self.run_start_factory = False
            self.noisy = False

        @classmethod
        def forProtocol(cls, *args, **kwargs):
            raise NotImplementedError()

        @property
        def real_factory(self):
            return self.__rf

        @real_factory.setter
        def real_factory(self, what):
            self.__rf = what
            if self.run_start_factory:
                what.startFactory()

        def logPrefix(self):
            if self.real_factory is not None:
                return self.real_factory.logPrefix()
            return "EmptyFactoryProxy"

        def startFactory(self):
            if self.real_factory is not None:
                return self.real_factory.startFactory()
            self.run_start_factory = True

        def stopFactory(self):
            if self.real_factory is not None:
                return self.real_factory.stopFactory()

        def buildProtocol(self, addr):
            return self.real_factory.buildProtocol(addr)

    return FactoryProxy


_lock_factory_proxy = Lock()


class Client(Service):
    host = Unicode(nullable=False, default='0.0.0.0')
    port = UnsignedInteger16(nullable=False, default=0)
    type = M(Unicode(values=('tcp4', 'tcp6', 'udp4', 'udp6', 'unix'),
                                                                default='tcp4'))

    def _parse_overrides(self):
        super(Client, self)._parse_overrides()

        for k, v in config_overrides.items():
            if k.startswith('--host-%s' % self.name):
                host = v
                self.host = host
                logger.debug("Overriding host for server service '%s' to '%s'",
                                                           self.name, self.host)

                del config_overrides[k]
                continue

            if k.startswith('--port-%s' % self.name):
                port = v
                self.port = int(port)
                logger.debug("Overriding port for server service '%s' to '%s'",
                                                           self.name, self.port)
                del config_overrides[k]
                continue



class Server(Service):
    backlog = Integer32(default=50)

    host = Unicode(nullable=False, default='0.0.0.0')
    port = UnsignedInteger16(nullable=False, default=0)
    type = M(Unicode(values=('tcp4', 'tcp6', 'udp4', 'udp6', 'unix'),
                                                                default='tcp4'))

    FactoryProxy = None

    def __init__(self, *args, **kwargs):
        super(Server, self).__init__(*args, **kwargs)

        self.d = None
        self.listener = None
        self.failed = False
        self.color = Fore.YELLOW  # set to G by daemon.main._set_real_factory

    def gen_endpoint(self, reactor):
        # FIXME: We might not need endpoints after all..
        if self.type == 'tcp4':
            from twisted.internet.endpoints import TCP4ServerEndpoint
            return TCP4ServerEndpoint(reactor, port=self.port,
                                      backlog=self.backlog, interface=self.host)

        elif self.type == 'tcp6':
            from twisted.internet.endpoints import TCP6ServerEndpoint
            return TCP6ServerEndpoint(reactor, port=self.port,
                                      backlog=self.backlog, interface=self.host)
        elif self.type == 'udp4':
            # TODO
            raise NotImplementedError(self.type)
            #return UDP4ServerEndpoint(reactor, port=self.port,
            #                         backlog=self.backlog, interface=self.host)
        elif self.type == 'udp6':
            # TODO
            raise NotImplementedError(self.type)
            #return UDP6ServerEndpoint(reactor, port=self.port,
            #                         backlog=self.backlog, interface=self.host)

        raise ValidationError(self.type)

    def get_factory_proxy(self):
        # Why thread-safe application of daemon configuration? I say why not :)
        with _lock_factory_proxy:
            if Server.FactoryProxy is None:
                Server.FactoryProxy = _TFactoryProxy()

        return Server.FactoryProxy

    @property
    def lstr(self):
        return "{}:{}:{}".format(self.type.upper(), self.host, self.port)

    def listen(self):
        from twisted.internet import reactor

        FactoryProxy = self.get_factory_proxy()

        retval = self.d = self.gen_endpoint(reactor) \
            .listen(FactoryProxy()) \
                .addCallback(self.set_listening_port) \
                .addCallback(lambda _: logger.info("%s listening on %s",
                                                self.colored_name, self.lstr)) \
                .addErrback(self._eb_listen)

        return retval

    def _eb_listen(self, err):
        self.failed = True

        self.color = Fore.RED
        logging.error("%s Error listening to %s, stopping reactor\n%s",
                               self.colored_name, self.lstr, err.getTraceback())

        if self.type.startswith('udp'):
            raise os._exit(EXIT_ERR_LISTEN_UDP + self.port)

        elif self.type.startswith('tcp'):
            raise os._exit(EXIT_ERR_LISTEN_TCP + self.port)

        raise os._exit(EXIT_ERR_UNKNOWN)

    def set_listening_port(self, listening_port):
        assert not (listening_port is None)
        self.listener = listening_port

    def _parse_overrides(self):
        super(Server, self)._parse_overrides()

        for k, v in config_overrides.items():
            if k.startswith('--host-%s' % self.name):
                host = v
                self.host = host
                logger.debug("Overriding host for server service '%s' to '%s'",
                                                           self.name, self.host)

                del config_overrides[k]
                continue

            if k.startswith('--port-%s' % self.name):
                port = v
                self.port = int(port)
                logger.debug("Overriding port for server service '%s' to '%s'",
                                                           self.name, self.port)
                del config_overrides[k]
                continue


def _listfiles(dirpath):
    for f in os.listdir(dirpath):
        fp = join(dirpath, f)
        if isfile(fp):
            yield fp


class SslServer(Server):
    _type_info = [
        ('cacert_path', Unicode),
        ('cacert', Unicode),
        ('cert', Unicode),
        ('key', Unicode),
        ('verify', Boolean(default=False)),
        ('verdepth', Integer32(default=9)),  # taken from twisted default
    ]

    @staticmethod
    def get_path(s):
        if s.startswith("rsc:"):
            package, file_name = s[4:].split("/", 1)
            return get_resource_path(package, file_name)
        return s

    def gen_endpoint(self, reactor):
        from OpenSSL import crypto

        cert = None
        if self.cert is not None:
            fn = self.get_path(self.cert)
            logger.debug("%s Loading cert from: %s", self.colored_name, fn)
            fdata = open(fn, 'rb').read()
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, fdata)
        else:
            logger.warning("%s No cert loaded", self.colored_name)


        key = None
        if self.key is not None:
            fn = self.get_path(self.key)
            logger.debug("%s Loading key from: %s", self.colored_name, fn)
            fdata = open(fn, 'rb').read()
            key = crypto.load_privatekey(crypto.FILETYPE_PEM, fdata)
        else:
            logger.warning("%s No key loaded", self.colored_name)

        cacerts = []
        if self.cacert is not None:
            fn = self.get_path(self.key)
            logger.debug("%s Loading cacert from: %s", self.colored_name, fn)
            fdata = open(fn, 'rb').read()
            cacert = crypto.load_certificate(crypto.FILETYPE_PEM, fdata)
            cacerts.append(cacert)

        if self.cacert_path is not None:
            cacert_path = self.get_path(self.key)
            # TODO: ignore errors
            for fn in _listfiles(cacert_path):
                fdata = open(fn, 'rb').read()
                logger.debug("%s Loading cacert from: %s",
                                                          self.colored_name, fn)
                cacert = crypto.load_certificate(crypto.FILETYPE_PEM, fdata)
                cacerts.append(cacert)

        from twisted.internet.ssl import CertificateOptions
        options = CertificateOptions(
            privateKey=key,
            certificate=cert,
            caCerts=cacerts,
            verify=self.verify,
            verifyDepth=self.verdepth,
        )

        assert options.getContext()

        if self.type == 'tcp4':
            from twisted.internet.endpoints import SSL4ServerEndpoint
            return SSL4ServerEndpoint(reactor, self.port, options,
                                      backlog=self.backlog, interface=self.host)

        elif self.type == 'tcp6':
            from twisted.internet.endpoints import SSL6ServerEndpoint
            return SSL6ServerEndpoint(reactor, self.port, options,
                                      backlog=self.backlog, interface=self.host)

        raise ValidationError(self.type)


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


class HttpServer(Server):
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

                logger.debug("Overriding asset path for app "
                         "'%s', url '%s' to '%s'", self.name, obj.url, obj.path)

    def __init__(self, *args, **kwargs):
        super(HttpServer, self).__init__(*args, **kwargs)

    def gen_site(self):
        from twisted.web.server import Site

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

        self.subapps = wdict()
        return []

    @_subapps.setter
    def _subapps(self, subapps):
        if isinstance(subapps, dict):
            self.subapps = Twdict(self, 'url')()
            for k, v in subapps.items():
                self.subapps[k] = v

        elif isinstance(subapps, (tuple, list)):
            self.subapps = Twdict(self, 'url')()
            for v in subapps:
                assert v.url is not None, "%r.url is None" % v
                self.subapps[v.url] = v

        self.subapps = subapps
        if subapps is not None:
            self.subapps = wdict([(s.url, s) for s in subapps])


class WsgiServer(HttpServer):
    thread_min = UnsignedInteger
    thread_max = UnsignedInteger
