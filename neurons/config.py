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

import os
import logging
import getpass
import argparse

from uuid import uuid1
from decimal import Decimal as D
from os.path import isfile

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


class Logger(ComplexModel):
    path = Unicode
    level = Unicode(values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])


class Daemon(ComplexModel):
    """A couple of neurons."""

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
                Logger(path='.', level='DEBUG'),
            ],
        )

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
