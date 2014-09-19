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

import logging
from neurons.daemon.daemonize import daemonize

logger = logging.getLogger(__name__)

import os
import sys
import getpass
import argparse

from uuid import uuid1
from decimal import Decimal as D
from os import access
from os.path import isfile, abspath, dirname

from spyne import ComplexModel, Boolean, ByteArray, Uuid, Unicode, \
    UnsignedInteger, UnsignedInteger16, Array, Integer, Decimal, \
    ComplexModelBase

from spyne.util.cdict import cdict
from spyne.util.dictdoc import YamlDocument, yaml_loads, get_object_as_yaml

from spyne.protocol import get_cls_attrs


class StorageInfo(ComplexModel):
    name = Unicode
    backend = Unicode


class Relational(StorageInfo):
    conn_str = Unicode
    pool_size = UnsignedInteger
    sync_pool = Boolean
    async_pool = Boolean


class Listener(ComplexModel):
    name = Unicode
    host = Unicode
    port = UnsignedInteger16
    unix_socket = Unicode
    thread_min = UnsignedInteger
    thread_max = UnsignedInteger


class HttpListener(Listener):
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


class Daemon(ComplexModel):
    """A couple of neurons."""

    LOGGING_DEVEL_FORMAT = "%(module)-15s | %(message)s"
    LOGGING_PROD_FORMAT = "%(asctime)s | %(module)-8s | %(levelname)s: %(message)s"

    uuid = Uuid
    secret = ByteArray
    daemonize = Boolean(default=False)
    gid = Unicode
    uid = Unicode
    log_file = Unicode
    pid_file = Unicode
    listeners = Array(Listener)
    stores = Array(StorageInfo)
    loggers = Array(Logger)
    
    show_rpc = Boolean
    show_queries = Boolean
    show_results = Boolean

    @classmethod
    def get_default(cls, daemon_name):
        return cls(
            uuid=uuid1(),
            secret=os.urandom(64),
            stores=[
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
            listeners=[
                HttpListener(
                    name="http_main",
                    host="localhost",
                    port=2048,
                    thread_min=3,
                    thread_max=10,
                ),
            ],
            loggers=[
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
        logging.getLogger().debug("ALOOOO")

        for l in self.loggers:
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
        assert not ('twisted' in sys.modules)

        if self.daemonize:
            daemonize()

        self.apply_logging()
        print(sys.modules['twisted'])


ARGTYPE_MAP = cdict({
    Integer: int,
    Decimal: D,
})


def is_array_of_primitives(cls):
    if issubclass(cls, Array):
        subcls, = cls._type_info.values()
        return not issubclass(subcls, ComplexModelBase)

    elif cls.Attributes.max_occurs > 1:
        return not issubclass(cls, ComplexModelBase)

    return False


def is_array_of_complexes(cls):
    if issubclass(cls, Array):
        subcls, = cls._type_info.values()
        return issubclass(subcls, ComplexModelBase)

    elif cls.Attributes.max_occurs > 1:
        return issubclass(cls, ComplexModelBase)

    return False


def spyne_to_argparse(cls):
    fti = cls.get_flat_type_info(cls)
    parser = argparse.ArgumentParser(description=Daemon.__doc__)

    for k, v in sorted(fti.items(), key=lambda i: i[0]):
        attrs = get_cls_attrs(None, v)
        args = ['--%s' % k]
        if attrs.short is not None:
            args.append('-%s' % attrs.short)

        kwargs = {}

        if attrs.help is not None:
            kwargs['help'] = attrs.help

        # types
        if is_array_of_primitives(v):
            kwargs['nargs'] = "+"

        elif is_array_of_complexes(v):
            continue

        elif issubclass(v, Boolean):
            kwargs['action'] = "store_true"

        elif issubclass(v, tuple(ARGTYPE_MAP.keys())):
            kwargs['type'] = ARGTYPE_MAP[v]

        parser.add_argument(*args, **kwargs)

    return parser


def parse_config(daemon_name, argv, cls=Daemon):
    retval = cls.get_default(daemon_name)
    file_name = '%s.yaml' % daemon_name

    exists = isfile(file_name) and os.access(file_name, os.R_OK)
    if exists:
        retval = yaml_loads(open(file_name).read(), cls, validator='soft')

    for k,v in spyne_to_argparse(cls).parse_args(argv[1:]).__dict__.items():
        if v is not None:
            setattr(retval, k, v)

    if not exists:
        open(file_name, 'wb').write(get_object_as_yaml(retval, cls, polymorphic=True))

    return retval

