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
    thread_min = UnsignedInteger
    thread_max = UnsignedInteger


class Listener(Service):
    host = Unicode
    port = UnsignedInteger16
    unix_socket = Unicode


class WsgiListener(Listener):
    static_dir = Unicode


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


class _wdict(dict):
    def get(self, key, *args):
        if len(args) > 0:
            if not key in self:
                self[key], = args
            return self[key]
        return self[key]


class Daemon(ComplexModel):
    """A couple of neurons."""

    LOGGING_DEVEL_FORMAT = "%(module)-15s | %(message)s"
    LOGGING_PROD_FORMAT = "%(asctime)s | %(module)-8s | %(levelname)s: %(message)s"

    _type_info = [
        ('uuid', Uuid),
        ('secret', ByteArray),
        ('daemonize', Boolean(default=False)),
        ('gid', Unicode),
        ('uid', Unicode),
        ('log_file', Unicode),
        ('pid_file', Unicode),

        ('show_rpc', Boolean),
        ('show_queries', Boolean),
        ('show_results', Boolean),

        ('_services', Array(Service, sub_name='services')),
        ('_stores', Array(StorageInfo, sub_name='stores')),
        ('_loggers', Array(Logger, sub_name='loggers')),
    ]

    @property
    def _services(self):
        if self.services is not None:
            for k, v in self.services.items():
                v.name = k

            return self.services.values()

    @_services.setter
    def _services(self, what):
        self.services = what
        if what is not None:
            self.services = _wdict([(s.name, s) for s in what])

    @property
    def _stores(self):
        if self.stores is not None:
            for k, v in self.stores.items():
                v.name = k

            return self.stores.values()

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
        from twisted.python import log

        class TwistedHandler(logging.Handler):
            def emit(self, record):
                assert isinstance(record, logging.LogRecord)
                log.msg(self.format(record), logLevel=record.levelno)

        if self.log_file is not None:
            from twisted.python.logfile import DailyLogFile

            self.log_file = abspath(self.log_file)
            assert access(dirname(self.log_file), os.R_OK | os.W_OK | os.X_OK),\
                "%r is not accessible. We need rwx on it." % self.log_file

            log_dest = DailyLogFile.fromFullPath(self.log_file)
            log.startLogging(log_dest, setStdout=False)

            formatter = logging.Formatter(self.LOGGING_PROD_FORMAT)

        else:
            formatter = logging.Formatter(self.LOGGING_DEVEL_FORMAT)
            log.startLogging(sys.stdout, setStdout=False)

            try:
                import colorama
                colorama.init()
                logger.debug("colorama loaded.")
    
            except Exception as e:
                logger.debug("coloarama not loaded: %r" % e)

        handler = TwistedHandler()
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

        for l in self._loggers or []:
            l.apply()

        if self.show_rpc or self.show_queries or self.show_results:
            logging.getLogger().setHandler(logging.DEBUG)

        if self.show_rpc:
            logging.getLogger('spyne.protocol').setLevel(logging.DEBUG)
            logging.getLogger('spyne.protocol.xml').setLevel(logging.DEBUG)
            logging.getLogger('spyne.protocol.dictdoc').setLevel(logging.DEBUG)

        if self.show_queries:
            logging.getLogger('sqlalchemy').setLevel(logging.INFO)

        if self.show_results:
            logging.getLogger('sqlalchemy').setLevel(logging.DEBUG)

    def apply(self):
        """Daemonizes the process if requested, then sets up logging and data
        stores.
        """

        assert not ('twisted' in sys.modules)

        if self.daemonize:
            daemonize()

        self.apply_logging()
        self.apply_storage()

    def apply_storage(self):
        for store in self._stores or []:
            store.apply()


def parse_config(daemon_name, argv, cls=Daemon):
    retval = cls.get_default(daemon_name)
    file_name = '%s.yaml' % daemon_name

    cli = dict(spyne_to_argparse(cls).parse_args(argv[1:]).__dict__.items())
    if cli['config_file'] is not None:
        file_name = cli.config.file
        del cli.config_file

    exists = isfile(file_name) and os.access(file_name, os.R_OK)
    if exists:
        retval = yaml_loads(open(file_name).read(), cls, validator='soft')

    for k,v in cli.items():
        if v is not None:
            setattr(retval, k, v)

    retval.config_file = file_name

    return retval


def write_config(daemon):
    if not isfile(daemon.config_file):
        open(daemon.config_file, 'wb').write(get_object_as_yaml(daemon,
                                            daemon.__class__, polymorphic=True))
