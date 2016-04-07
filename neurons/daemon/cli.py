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

import argparse
import os.path

from gettext import gettext
from decimal import Decimal as D

from spyne import Boolean, Unicode, Integer, Decimal, ComplexModelBase, Array
from spyne.protocol import ProtocolBase
from spyne.util import six
from spyne.util.cdict import cdict


ARGTYPE_MAP = cdict({
    Integer: int,
    Decimal: D,
})


config_overrides = set()


class ArgumentParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        args, argv = self.parse_known_args(args, namespace)

        if len(argv) > 0:
            newargv = []
            for a in argv:
                if a.startswith("--assets-"):
                    opt, val = a.split("=", 2)
                    val = os.path.abspath(val)
                    config_overrides.add('='.join([opt, val]))

                elif a.startswith("--host-") or a.startswith("--port-"):
                    config_overrides.add(a)

                else:
                    newargv.append(a)
            argv = newargv

        if len(argv) > 0:
            msg = gettext('unrecognized arguments: %s')
            self.error(msg % ' '.join(argv))

        return args


def Tmust_exist(test_func):
    """Generic for an argparse type.

    :param test_func: One of :func:`os.path.isdir`, :func:`os.path.isfile` or
            :func:`os.path.ismount`.
    """

    def must_exist(file_name):
        if file_name:
            file_name = os.path.abspath(file_name)
            if not test_func(file_name):
                raise OSError("%r is invalid." % file_name)
            return file_name

    return must_exist


def enum(*values):
    """Enum type for argparse.

    :param values: Values that the option at hand can have. Must all be unicode.
    """

    def enum_(value):
        if value:
            if not (value in values):
                raise ValueError('Argument must be one of %r' % values)
            return value

    return enum_


file_must_exist = Tmust_exist(os.path.isfile)
dir_must_exist = Tmust_exist(os.path.isdir)


def _is_array_of_primitives(cls):
    if issubclass(cls, Array):
        subcls, = cls._type_info.values()
        return not issubclass(subcls, ComplexModelBase)

    elif cls.Attributes.max_occurs > 1:
        return not issubclass(cls, ComplexModelBase)

    return False


def _is_array_of_complexes(cls):
    if issubclass(cls, Array):
        subcls, = cls._type_info.values()
        return issubclass(subcls, ComplexModelBase)

    elif cls.Attributes.max_occurs > 1:
        return issubclass(cls, ComplexModelBase)

    return False


_some_prot = ProtocolBase()

def spyne_to_argparse(cls):
    fti = cls.get_flat_type_info(cls)
    parser = ArgumentParser(description=cls.__doc__)

    parser.add_argument('-c', '--config-file', type=os.path.abspath,
                                             help="An alternative config file.")

    for k, v in sorted(fti.items(), key=lambda i: i[0]):
        attrs = _some_prot.get_cls_attrs(v)
        if attrs.no_cli:
            continue

        args = ['--%s' % k.replace('_', '-')]
        if attrs.short is not None:
            args.append('-%s' % attrs.short)

        assert not ('-c' in args or '--config-file' in args)

        kwargs = {}

        if attrs.help is not None:
            kwargs['help'] = attrs.help

        if attrs.default is not None:
            kwargs['default'] = attrs.default

        # types
        if _is_array_of_primitives(v):
            kwargs['nargs'] = "+"

        elif _is_array_of_complexes(v):
            continue

        elif issubclass(v, Boolean):
            kwargs['action'] = "store_const"
            kwargs['const'] = True

        elif issubclass(v, Unicode):
            if len(v.Attributes.values) > 0:
                kwargs['type'] = enum(*v.Attributes.values)
            else:
                kwargs['type'] = six.text_type

        elif issubclass(v, tuple(ARGTYPE_MAP.keys())):
            kwargs['type'] = ARGTYPE_MAP[v]

        parser.add_argument(*args, **kwargs)
        logger.debug("add_argument %r %r", args, kwargs)

    return parser
