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

from __future__ import print_function

import logging
logger = logging.getLogger(__name__)

import os
import sys
import getpass

from uuid import uuid1
from os import access
from os.path import isfile, abspath, dirname

from spyne import ComplexModel, Boolean, ByteArray, Uuid, Unicode, \
    UnsignedInteger, UnsignedInteger16, Array

from spyne.util.dictdoc import yaml_loads, get_object_as_yaml

from neurons.daemon.daemonize import daemonize
from neurons.daemon.store import SqlDataStore
from neurons.daemon.cli import spyne_to_argparse


class StorageInfo(ComplexModel):
    name = Unicode
    backend = Unicode


class Relational(StorageInfo):
    conn_str = Unicode
    pool_size = UnsignedInteger
    sync_pool = Boolean
    async_pool = Boolean

    def __init__(self, *args, **kwargs):
        super(Relational, self).__init__(*args, **kwargs)
        self.itself = None

    def apply(self):
        self.itself = SqlDataStore(self.conn_str, self.pool_size)
        if self.async_pool:
            self.itself.add_txpool()
        if not self.sync_pool:
            self.itself.Session = None
            self.itself.metadata = None
            self.itself.engine.close()
            self.itself.engine = None


class Service(ComplexModel):
    name = Unicode


class Listener(Service):
    host = Unicode
    port = UnsignedInteger16
    disabled = Boolean
    unix_socket = Unicode


class HttpApplication(ComplexModel):
    url = Unicode
    name = Unicode


class StaticFileServer(HttpApplication):
    path = Unicode
    list_contents = Boolean(default=False)

    def __init__(self, *args, **kwargs):
        super(StaticFileServer, self).__init__(*args, **kwargs)
        self.name = '{neurons.daemon}StaticFile'

    def gen_resource(self):
        from twisted.web.static import File
        from twisted.web.resource import ForbiddenResource

        if self.list_contents:
            return File(abspath(self.path))

        class StaticFile(File):
            def directoryListing(self):
                return ForbiddenResource()

        return StaticFile(abspath(self.path))


class HttpListener(Listener):
    _type_info = [
        ('static_dir', Unicode),
        ('_subapps', Array(HttpApplication, sub_name='subapps')),
    ]

    def __init__(self, *args, **kwargs):
        super(HttpListener, self).__init__(*args, **kwargs)

        subapps = kwargs.get('subapps', None)
        if subapps is not None:
            self.subapps = subapps
        if not hasattr(self, 'subpaths') or self.subapps is None:
            self.subapps = _wdict()

    def gen_site(self):
        from twisted.web.server import Site
        from twisted.web.resource import Resource

        root_app = self.subapps.get('', None)
        if root_app is None:
            root = Resource()
        else:
            root = root_app.gen_resource()

        for subapp in self.subapps:
            if subapp.uri != '':
                root.putChild(subapp.uri, subapp.gen_resource())
        return Site(root)

    @property
    def _subpaths(self):
        if self.subpaths is not None:
            for k, v in self.subpaths.items():
                v.uri = k

            return self.subpaths.values()

        self.subpaths = _wdict()
        return []

    @_subpaths.setter
    def _subpaths(self, what):
        self.subpaths = what
        if what is not None:
            self.subpaths = _wdict([(s.uri, s) for s in what])


class WsgiListener(HttpListener):
    thread_min = UnsignedInteger
    thread_max = UnsignedInteger


LOGLEVEL_MAP = dict(zip(
    ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR,
                                                               logging.CRITICAL]
))


class Logger(ComplexModel):
    path = Unicode
    level = Unicode(values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])

    def apply(self):
        if self.path == '.':
            _logger = logging.getLogger()
        else:
            _logger = logging.getLogger(self.path)

        _logger.setLevel(LOGLEVEL_MAP[self.level])
        logger.info("Setting logging level for %r to %r.", _logger.name, self.level)


class ServiceDisabled(Exception):
    pass


class _wdict(dict):
    def getwrite(self, key, *args):
        if len(args) > 0:
            if not key in self:
                self[key], = args
            return self[key]
        return self[key]


class _wrdict(_wdict):
    def getwrite(self, key, *args):
        """Raises ServiceDisabled when the service has disabled == True"""

        retval = super(_wrdict, self).getwrite(key, *args)

        if getattr(retval, 'disabled', None):
            raise ServiceDisabled(getattr(retval, 'name', "??"))

        return retval


class Daemon(ComplexModel):
    """A couple of neurons."""

    LOGGING_DEVEL_FORMAT = "%(module)-15s | %(message)s"
    LOGGING_PROD_FORMAT = "%(asctime)s | %(module)-8s | %(message)s"

    _type_info = [
        ('uuid', Uuid(help="Daemon uuid. Regenerated every time a new "
                           "config file is written. It could come in handy.")),
        ('secret', ByteArray(no_cli=True, help="Secret key for signing cookies "
                                               "and other stuff.")),
        ('daemonize', Boolean(default=False,
                              help="Daemonizes before everything else.")),

        ('uid', Unicode(help="The daemon user. You need to start the server as"
                             " a priviledged user for this to work.")),
        ('gid', Unicode(help="The daemon group. You need to start the server as"
                             " a priviledged user for this to work.")),

        ('log_file', Unicode(help="The path to the log file. The server won't "
               "daemonize without this. Converted to an absolute path if not")),
        ('pid_file', Unicode(help="The path to a text file that contains the pid"
                                  "of the daemonized process.")),

        ('log_rpc', Boolean(help="Log raw rpc data.")),
        ('log_queries', Boolean(help="Log sql queries.")),
        ('log_results', Boolean(help="Log query results in addition to queries"
                                     "themselves.")),

        ('_services', Array(Service, sub_name='services')),
        ('_stores', Array(StorageInfo, sub_name='stores')),
        ('_loggers', Array(Logger, sub_name='loggers')),
    ]

    # FIXME: we need this atrocity with custom constructor and properties
    # because spyne doesn't support custom containers
    def __init__(self, *args, **kwargs):
        super(Daemon, self).__init__(*args, **kwargs)

        services = kwargs.get('services', None)
        if services is not None:
            self.services = services
        if not hasattr(self, 'services') or self.services is None:
            self.services = _wdict()

        stores = kwargs.get('stores', None)
        if stores is not None:
            self.stores = stores
        if not hasattr(self, 'stores') or self.stores is None:
            self.stores = _wdict()

        loggers = kwargs.get('loggers', None)
        if loggers is not None:
            self.loggers = loggers
        if not hasattr(self, 'loggers') or self.loggers is None:
            self.loggers = _wdict()

    @property
    def _services(self):
        if self.services is not None:
            for k, v in self.services.items():
                v.name = k

            return self.services.values()

        self.services = _wrdict()
        return []

    @_services.setter
    def _services(self, what):
        self.services = what
        if what is not None:
            self.services = _wrdict([(s.name, s) for s in what])

    @property
    def _stores(self):
        if self.stores is not None:
            for k, v in self.stores.items():
                v.name = k

            return self.stores.values()

        self.stores = _wdict()
        return []

    @_stores.setter
    def _stores(self, what):
        self.stores = what
        if what is not None:
            self.stores = _wdict([(s.name, s) for s in what])

    @property
    def _loggers(self):
        if self.loggers is not None:
            for k, v in self.loggers.items():
                v.name = k

            return self.loggers.values()

        self.loggers = _wdict()
        return []

    @_loggers.setter
    def _loggers(self, what):
        self.loggers = what
        if what is not None:
            self.loggers = _wdict([(s.path, s) for s in what])

    @classmethod
    def get_default(cls, daemon_name):
        return cls(
            uuid=uuid1(),
            secret=os.urandom(64),
            _stores=[
                Relational(
                    name="sql_main",
                    backend="sqlalchemy",
                    pool_size=10,
                    conn_str='postgres://postgres:@localhost:5432/%s_%s' %
                                               (daemon_name, getpass.getuser()),
                    sync_pool=True,
                    async_pool=True,
                ),
            ],
            _loggers=[
                Logger(path='.', level='DEBUG', format=cls.LOGGING_DEVEL_FORMAT),
            ],
        )

    def apply_logging(self):
        # We're using twisted logging only for IO.
        from twisted.python.logger import FileLogObserver
        from twisted.python.logger import Logger, LegacyLogger, LogLevel, globalLogPublisher

        LOGLEVEL_TWISTED_MAP = {
            logging.DEBUG: LogLevel.debug,
            logging.INFO: LogLevel.info,
            logging.WARN: LogLevel.warn,
            logging.ERROR: LogLevel.error,
            logging.CRITICAL: LogLevel.critical,
        }

        class TwistedHandler(logging.Handler):
            def emit(self, record):
                assert isinstance(record, logging.LogRecord)
                Logger(record.name).emit(LOGLEVEL_TWISTED_MAP[record.levelno],
                                         log_text=self.format(record))

        if self.log_file is not None:
            from twisted.python.logfile import DailyLogFile

            self.log_file = abspath(self.log_file)
            if access(dirname(self.log_file), os.R_OK | os.W_OK):
                log_dest = DailyLogFile.fromFullPath(self.log_file)

            else:
                Logger().warn("%r is not accessible. We need rwx on it to "
                               "rotate logs." % dirname(self.log_file))
                log_dest = open(self.log_file, 'wb+')

            formatter = logging.Formatter(self.LOGGING_PROD_FORMAT)

        else:
            formatter = logging.Formatter(self.LOGGING_DEVEL_FORMAT)
            log_dest = open('/dev/stdout', 'wb+')

            try:
                import colorama
                colorama.init()
                logger.debug("colorama loaded.")

            except Exception as e:
                logger.debug("coloarama not loaded: %r" % e)

        observer = FileLogObserver(log_dest, lambda x: x['log_text']+'\n')
        globalLogPublisher.addObserver(observer)

        handler = TwistedHandler()
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

        for l in self._loggers or []:
            l.apply()

        if self.log_rpc or self.log_queries or self.log_results:
            logging.getLogger().setLevel(logging.DEBUG)

        if self.log_rpc:
            logging.getLogger('spyne.protocol').setLevel(logging.DEBUG)
            logging.getLogger('spyne.protocol.xml').setLevel(logging.DEBUG)
            logging.getLogger('spyne.protocol.dictdoc').setLevel(logging.DEBUG)

        if self.log_queries:
            logging.getLogger('sqlalchemy').setLevel(logging.INFO)

        if self.log_results:
            logging.getLogger('sqlalchemy').setLevel(logging.DEBUG)

    def sanitize(self):
        if self.log_file is not None:
            self.log_file = abspath(self.log_file)
        if self.pid_file is not None:
            self.pid_file = abspath(self.pid_file)

    def apply(self):
        """Daemonizes the process if requested, then sets up logging and data
        stores.
        """

        assert not ('twisted' in sys.modules)

        self.sanitize()
        if self.daemonize:
            assert self.log_file
            daemonize()

        if self.pid_file is not None:
            pid = os.getpid()
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))

        self.apply_logging()
        self.apply_storage()

    def apply_storage(self):
        for store in self._stores or []:
            store.apply()

    @classmethod
    def parse_config(cls, daemon_name, argv, parse_cli=True):
        retval = cls.get_default(daemon_name)
        file_name = abspath('%s.yaml' % daemon_name)

        cli = {}
        if parse_cli:
            cli = dict(spyne_to_argparse(cls).parse_args(argv[1:]).__dict__.items())
            if cli['config_file'] is not None:
                file_name = cli['config_file']
                del cli['config_file']

        exists = isfile(file_name) and os.access(file_name, os.R_OK)
        if exists:
            retval = yaml_loads(open(file_name).read(), cls, validator='soft',
                                                               polymorphic=True)
        else:
            if not access(dirname(file_name), os.R_OK | os.W_OK):
                raise Exception("File %r can't be created in %r" %
                                                (file_name, dirname(file_name)))

        for k, v in cli.items():
            if not v in (None, False):
                setattr(retval, k, v)

        retval.config_file = file_name

        return retval

    def write_config(self):
        open(self.config_file, 'wb').write(get_object_as_yaml(self,
                                              self.__class__, polymorphic=True))
