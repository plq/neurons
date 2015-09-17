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

import getpass
import os, re, sys

from os import access
from uuid import uuid1
from pprint import pformat
from argparse import Action
from os.path import isfile, abspath, dirname

from spyne import ComplexModel, Boolean, ByteArray, Uuid, Unicode, \
    UnsignedInteger, UnsignedInteger16, Array, String, Application, \
    ComplexModelBase, M

from spyne.protocol import ProtocolBase
from spyne.protocol.yaml import YamlDocument

from spyne.util.dictdoc import yaml_loads, get_object_as_yaml

from neurons.daemon.daemonize import daemonize
from neurons.daemon.store import SqlDataStore
from neurons.daemon.cli import spyne_to_argparse, config_overrides


STATIC_DESC_ROOT = "Directory that contains static files for the root url."
STATIC_DESC_URL = "Directory that contains static files for the url '%s'."

_some_prot = ProtocolBase()


_meminfo = None


def update_meminfo():
    global _meminfo

    try:
        import psutil
        process = psutil.Process(os.getpid())
        try: # psutil 2
            _meminfo = process.get_memory_info
        except AttributeError: # psutil 3
            _meminfo = process.memory_info

        del process

    except ImportError:
        pass


update_meminfo()


class _SetStaticPathAction(Action):
    def __init__(self, option_strings, dest, const=None, help=None):
        super(_SetStaticPathAction, self).__init__(nargs=1, const=const,
                            option_strings=option_strings, dest=dest, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        self.const.path = abspath(values[0])


def _apply_custom_attributes(cls):
    fti = cls.get_flat_type_info(cls)
    for k, v in sorted(fti.items(), key=lambda i: i[0]):
        attrs = _some_prot.get_cls_attrs(v)
        if attrs.no_config == True:
            v.Attributes.prot_attrs={YamlDocument: dict(exc=True)}


class AlertDestination(ComplexModel):
    type = Unicode(default='email', values=['email'])


EmailAddress = Unicode(pattern=r"[^@\s]+@[^@\s]+")


class EmailAlert(AlertDestination):
    host = Unicode(default='localhost')
    port = UnsignedInteger16(default=25)
    user = Unicode
    sender = Unicode(default='Random Developer <robot@spyne.io>')
    envelope_from = EmailAddress
    password = Unicode
    recipients = M(Array(M(EmailAddress)))


class StorageInfo(ComplexModel):
    name = Unicode
    backend = Unicode


class Relational(StorageInfo):
    conn_str = Unicode
    pool_size = UnsignedInteger(default=10)
    max_overflow = UnsignedInteger(default=3)
    pool_recycle = UnsignedInteger(default=3600)
    pool_timeout = UnsignedInteger(default=30)
    sync_pool = Boolean(default=True)
    async_pool = Boolean(default=True)

    def __init__(self, *args, **kwargs):
        super(Relational, self).__init__(*args, **kwargs)
        self.itself = None

    def apply(self):
        self.itself = SqlDataStore(self.conn_str, pool_size=self.pool_size)
        if not (self.async_pool or self.sync_pool):
            logger.debug("Store '%s' is disabled.", self.name)

        if self.async_pool:
            if self.conn_str.startswith('postgres'):
                self.itself.add_txpool()
            else:
                self.async_pool = False

        if not self.sync_pool:
            self.itself.Session = None
            self.itself.metadata = None
            self.itself.engine.close()
            self.itself.engine = None

        return self


class Service(ComplexModel):
    name = Unicode


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
            return self.app
        elif isinstance(self.app, Application):
            return TwistedWebResource(self.app)
        elif isinstance(self.app, (WsgiApplication, WsgiMounter)):
            return WSGIResource(reactor, reactor.getThreadPool(), self.app)
        raise ValueError(self.app)


class StaticFileServer(HttpApplication):
    path = String
    list_contents = Boolean(default=False)
    disallowed_exts = Array(Unicode, default_factory=tuple)

    def __init__(self, *args, **kwargs):
        # We need the default ComplexModelBase ctor and not HttpApplication's
        # custom ctor here
        ComplexModelBase.__init__(self, *args, **kwargs)

    def gen_resource(self):
        from twisted.web.static import File
        from twisted.web.resource import ForbiddenResource
        from twisted.python.filepath import InsecurePath

        d_exts = self.disallowed_exts
        class CheckedFile(File):
            def child(self, path):
                retval = File.child(self, path)

                if path.rsplit(".", 1)[-1] in d_exts:
                    raise InsecurePath("%r is disallowed." % (path,))

                return retval

        if self.list_contents:
            return File(abspath(self.path))

        class StaticFile(CheckedFile):
            def directoryListing(self):
                return ForbiddenResource()

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
            self.subapps = _Twrdict('url')()
            for k, v in subapps.items():
                self.subapps[k] = v

        elif isinstance(subapps, (tuple, list)):
            self.subapps = _Twrdict('url')()
            for v in subapps:
                assert v.url is not None, "%r.url is None" % v
                self.subapps[v.url] = v

    def gen_site(self):
        from twisted.web.server import Site
        from twisted.web.resource import Resource

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
            root = Resource()
        else:
            root = root_app.gen_resource()

        for subapp in self._subapps:
            if subapp.url != '':
                root.putChild(subapp.url, subapp.gen_resource())

        return Site(root)

    @property
    def _subapps(self):
        if self.subapps is not None:
            for k, v in self.subapps.items():
                v.url = k

            return self.subapps.values()

        self.subapps = _wrdict()
        return []

    @_subapps.setter
    def _subapps(self, what):
        self.subapps = what
        if what is not None:
            self.subapps = _wdict([(s.url, s) for s in what])


class WsgiListener(HttpListener):
    thread_min = UnsignedInteger
    thread_max = UnsignedInteger


LOGLEVEL_MAP = dict(zip(
    ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'FATAL'],
    [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR,
                                                logging.CRITICAL, logging.FATAL]
))


LOGLEVEL_MAP_ABB = {v: k[0] for (k, v) in LOGLEVEL_MAP.items()}


class Logger(ComplexModel):
    path = Unicode
    level = Unicode(values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])

    def apply(self):
        if self.path == '.':
            _logger = logging.getLogger()
        else:
            _logger = logging.getLogger(self.path)

        _logger.setLevel(LOGLEVEL_MAP[self.level])
        logger.info("Setting logging level for %r to %r.",
                                                       _logger.name, self.level)

        return self


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


def _Twrdict(keyattr=None):
    class wrdict(_wrdict):
        if keyattr is not None:
            def __setitem__(self, key, value):
                super(_wrdict, self).__setitem__(key, value)
                setattr(value, keyattr, key)
        else:
            def __setitem__(self, key, value):
                super(_wrdict, self).__setitem__(key, value)
    return wrdict


class Daemon(ComplexModel):
    """This is a custom daemon with only pid files, forking, logging and initial
    setuid/setgid operations.
    """

    LOGGING_DEVEL_FORMAT = "%(l)s | %(module)-15s | %(message)s"
    LOGGING_PROD_FORMAT = "%(l)s %(asctime)s | %(module)-8s | %(message)s"

    _type_info = [
        ('name', Boolean(help="Show version", no_cli=True)),

        ('uuid', Uuid(no_cli=True,
                      help="Daemon uuid. Regenerated every time a new "
                           "config file is written. It could come in handy.")),
        ('secret', ByteArray(no_cli=True, help="Secret key for signing cookies "
                                               "and other stuff.")),
        ('daemonize', Boolean(default=False,
                              help="Daemonizes before everything else.")),

        ('uid', Unicode(help="The daemon user. You need to start the server as "
                             "a priviledged user for this to work.")),
        ('gid', Unicode(help="The daemon group. You need to start the server as"
                             " a priviledged user for this to work.")),

        ('pid_file', String(help="The path to a text file that contains the pid"
                                 " of the daemonized process.")),

        ('logger_dest', String(help="The path to the log file. The server won't"
             " daemonize without this. Converted to an absolute path if not.")),

        ('version', Boolean(help="Show version", no_config=True)),

        ('bootstrap', Boolean(help="Bootstrap the application. Create schema, "
                                  "insert initial data, etc.", no_config=True)),

        ('log_rss', Boolean(help="Prepend current memory usage "
                                 "to all logging messages. Requires psutil")),

        ('log_rpc', Boolean(help="Log raw rpc data.")),

        ('write_wsdl', Unicode(
            help="Write WSDL documents to the given directory. "
                                   "It is created if missing", no_config=True)),

        ('write_xsd', Unicode(
            help="Write Xml Schema documents to given directory. "
                                   "It is created if missing", no_config=True)),

        ('alert_dests', Array(AlertDestination, default=[])),

        ('_services', Array(Service, sub_name='services')),
        ('_loggers', Array(Logger, sub_name='loggers')),
    ]

    # FIXME: We need all this hacky magic with custom constructor and properties
    # because Spyne doesn't support custom containers
    def __init__(self, *args, **kwargs):
        super(Daemon, self).__init__(*args, **kwargs)

        services = kwargs.get('services', None)
        if services is not None:
            self.services = services
        if not hasattr(self, 'services') or self.services is None:
            self.services = _Twrdict('name')()

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

        self.services = _Twrdict('name')()
        return []

    @_services.setter
    def _services(self, what):
        self.services = what
        if what is not None:
            self.services = _Twrdict('name')([(s.name, s) for s in what])

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
            name=daemon_name,
            log_rss=False,
            _loggers=[
                Logger(path='.', level='DEBUG', format=cls.LOGGING_DEVEL_FORMAT),
                # This produces too much output that's not very useful unless
                # you're debugging *Cloth.
                Logger(path='spyne.protocol.cloth.to_cloth.cloth', 
                                  level='INFO', format=cls.LOGGING_DEVEL_FORMAT),
            ],
        )

    def _clear_other_observers(self, publisher, observer):
        from twisted.logger import LimitedHistoryLogObserver, LogPublisher

        # FIXME: Remove Limited History Observer in a supported way.
        logger.debug("Looking for rogue observers in %r", publisher._observers)

        for o in publisher._observers:
            if isinstance(o, LogPublisher):
                self._clear_other_observers(o, observer)

            elif isinstance(o, LimitedHistoryLogObserver):
                publisher.removeObserver(o)
                o.replayTo(observer)
                logger.debug("Removing observer", o)

            else:
                logger.debug("Leaving alone observer", o)

    def sanitize(self):
        if self.logger_dest is not None:
            self.logger_dest = abspath(self.logger_dest)
        if self.pid_file is not None:
            self.pid_file = abspath(self.pid_file)

    def apply_logging(self):
        # We're using twisted logging only for IO.
        from twisted.logger import FileLogObserver
        from twisted.logger import Logger, LogLevel, globalLogPublisher

        LOGLEVEL_TWISTED_MAP = {
            logging.DEBUG: LogLevel.debug,
            logging.INFO: LogLevel.info,
            logging.WARN: LogLevel.warn,
            logging.ERROR: LogLevel.error,
            logging.CRITICAL: LogLevel.critical,
        }

        TWISTED_LOGLEVEL_MAP = {v: k for k,v in LOGLEVEL_TWISTED_MAP.items()}

        loggers = {}

        config = self
        class TwistedHandler(logging.Handler):
            if config.log_rss:
                if _meminfo is None:
                    def _modify_record(self, record):
                        record.msg = '[psutil?] %s' % record.msg
                else:
                    def _modify_record(self, record):
                        rss, vmsize = _meminfo()
                        record.msg = '[%.2f] %s' % (rss / 1024.0 ** 2,
                                                                     record.msg)
            else:
                def _modify_record(self, record):
                    pass

            def emit(self, record):
                assert isinstance(record, logging.LogRecord)

                record.l = LOGLEVEL_MAP_ABB.get(record.levelno, "?")

                self._modify_record(record)

                _logger = loggers.get(record.name, None)
                if _logger is None:
                    _logger = loggers[record.name] = Logger(record.name)

                _logger.emit(LOGLEVEL_TWISTED_MAP[record.levelno],
                                                   log_text=self.format(record))

        if self.logger_dest is not None:
            from twisted.python.logfile import DailyLogFile

            class DailyLogWithLeadingZero(DailyLogFile):
                def suffix(self, tupledate):
                    # this closely imitates the same function from parent class
                    try:
                        return '-'.join(("%02d" % i for i in tupledate))
                    except:
                        # try taking a float unixtime
                        return '-'.join(("%02d" % i for i in
                                                        self.toDate(tupledate)))

            self.logger_dest = abspath(self.logger_dest)
            if access(dirname(self.logger_dest), os.R_OK | os.W_OK):
                log_dest = DailyLogWithLeadingZero \
                                                 .fromFullPath(self.logger_dest)

            else:
                Logger().warn("%r is not accessible. We need rwx on it to "
                               "rotate logs." % dirname(self.logger_dest))
                log_dest = open(self.logger_dest, 'wb+')

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

        def record_as_string(record):
            if 'log_failure' in record:
                failure = record['log_failure']
                try:
                    s = pformat(vars(failure.value))
                except TypeError:
                    # vars() argument must have __dict__ attribute
                    s = repr(failure.value)
                return "%s: %s" % (failure.type, s)

            if 'log_text' in record:
                return record['log_text'] + "\n"

            if 'log_format' in record:
                level = record.get('log_level', LogLevel.debug)
                level = LOGLEVEL_MAP_ABB[TWISTED_LOGLEVEL_MAP[level]]

                text = record['log_format'].format(**record) + "\n"
                ns = record.get('log_namespace', "???")
                lineno = 0
                record = logging.LogRecord(
                                      '?', level, ns, lineno, text, None, None)
                record.l = level
                record.module = ns.split('.')[-2]

                return formatter.format(record)

            if 'log_io' in record:
                return record['log_io'] + "\n"

            if 'message' in record:
                return record['message'] + "\n"

            return pformat(record)

        observer = FileLogObserver(log_dest, record_as_string)
        globalLogPublisher.addObserver(observer)
        self._clear_other_observers(globalLogPublisher, observer)

        handler = TwistedHandler()
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

        self.pre_logging_apply()

        for l in self._loggers or []:
            l.apply()

        return self

    def pre_logging_apply(self):
        pass

    def apply(self, for_testing=False):
        """Daemonizes the process if requested, then sets up logging and pid
        files.
        """

        # Daemonization won't work if twisted is imported before fork().
        # It's best to know this in advance or you'll have to deal with daemons
        # that work perfectly well in development environments but won't boot
        # in production ones, solely because of fork()ingw.
        assert for_testing or not ('twisted' in sys.modules), \
                                                "Twisted is already imported!"

        self.sanitize()
        if self.daemonize:
            assert self.logger_dest, "Refusing to start without any log output."
            daemonize()
            update_meminfo()

        self.apply_logging()

        if self.pid_file is not None:
            pid = os.getpid()
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
                logger.debug("Pid file is at: %r", self.pid_file)

        return self

    @classmethod
    def parse_config(cls, daemon_name, argv=None):
        _apply_custom_attributes(cls)
        retval = cls.get_default(daemon_name)
        file_name = abspath('%s.yaml' % daemon_name)

        argv_parser = spyne_to_argparse(cls)
        cli = {}
        if argv is not None and len(argv) > 1:
            cli = dict(argv_parser.parse_args(argv[1:]).__dict__.items())
            if cli['config_file'] is not None:
                file_name = abspath(cli['config_file'])
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

class ServiceDaemon(Daemon):
    """This daemon needs access to one or more data stores to work."""

    _type_info = [
        ('log_queries', Boolean(help="Log sql queries.")),
        ('log_results', Boolean(help="Log query results in addition to queries "
                                     "themselves.")),

        ('main_store', Unicode(help="The name of the store for binding "
                                    "neurons.TableModel's metadata to.")),

        ('_stores', Array(StorageInfo, sub_name='stores')),
    ]

    # FIXME: We need all this hacky magic with custom constructor and properties
    # because Spyne doesn't support custom containers
    def __init__(self, *args, **kwargs):
        super(Daemon, self).__init__(*args, **kwargs)

        stores = kwargs.get('stores', None)
        if stores is not None:
            self.stores = stores
        if not hasattr(self, 'stores') or self.stores is None:
            self.stores = _wdict()

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

    @classmethod
    def get_default(cls, daemon_name):
        return cls(
            uuid=uuid1(),
            secret=os.urandom(64),
            name=daemon_name,
            _stores=[
                Relational(
                    name="sql_main",
                    backend="sqlalchemy",
                    pool_size=10,
                    pool_recycle=3600,
                    pool_timeout=30,
                    max_overflow=3,
                    conn_str='postgres://postgres:@localhost:5432/%s_%s' %
                                               (daemon_name, getpass.getuser()),
                    sync_pool=True,
                    async_pool=True,
                ),
            ],
            main_store='sql_main',
            _loggers=[
                Logger(path='.', level='DEBUG', format=cls.LOGGING_DEVEL_FORMAT),
            ],
        )

    def apply_storage(self):
        for store in self._stores or []:
            try:
                store.apply()
            except Exception as e:
                logger.exception(e)
                raise

            if self.main_store == store.name:
                engine = store.itself.engine

                import neurons
                neurons.TableModel.Attributes.sqla_metadata.bind = engine

        return self

    def apply(self, for_testing=False):
        """Daemonizes the process if requested, then sets up logging and pid
        files plus data stores.
        """

        # FIXME: apply_storage could return a deferred due to txpool init.

        super(ServiceDaemon, self).apply(for_testing=for_testing)

        self.apply_storage()

        return self

    def pre_logging_apply(self):
        if self.log_rpc or self.log_queries or self.log_results:
            logging.getLogger().setLevel(logging.DEBUG)

        if self.log_rpc:
            logging.getLogger('spyne.protocol').setLevel(logging.DEBUG)
            logging.getLogger('spyne.protocol.xml').setLevel(logging.DEBUG)
            logging.getLogger('spyne.protocol.dictdoc').setLevel(logging.DEBUG)

        if self.log_queries:
            logging.getLogger('sqlalchemy').setLevel(logging.INFO)
            logging.getLogger('sqlalchemy.orm.mapper').setLevel(logging.WARNING)

        if self.log_results:
            logging.getLogger('sqlalchemy').setLevel(logging.DEBUG)
            logging.getLogger('sqlalchemy.orm.mapper').setLevel(logging.WARNING)
