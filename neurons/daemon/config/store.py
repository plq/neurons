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

from os.path import abspath

from spyne import ComplexModel, Boolean, Unicode, \
    UnsignedInteger16, M, Decimal, UnsignedInteger

from neurons.daemon.store import SqlDataStore, LdapDataStore


class StorageInfo(ComplexModel):
    name = Unicode
    backend = Unicode

    def __init__(self, *args, **kwargs):
        self._parent = None

        super(StorageInfo, self).__init__(*args, **kwargs)

    def set_parent(self, parent):
        assert self._parent is None
        assert parent is not None

        self._parent = parent

    def close(self):
        pass


class PoolConfig(ComplexModel):
    type = Unicode


class AsyncPoolConfig(ComplexModel):
    type = Unicode(values=['txpostgres'])


class SyncPoolConfig(ComplexModel):
    type = Unicode(values=[
            'SingletonThreadPool', 'QueuePool', 'NullPool',
            'StaticPool', 'AssertionPool'
        ])


DistinguishedName = Unicode


class LdapStore(StorageInfo):
    method = M(Unicode(values=['simple', 'gssapi']))
    backend = M(Unicode(values=['python-ldap']))

    host = M(Unicode)
    port = UnsignedInteger16(default=389)
    base_dn = DistinguishedName
    bind_dn = DistinguishedName
    password = Unicode
    timeout = Decimal(gt=0, default=10)
    version = UnsignedInteger(default=3, vaues=[2, 3])
    use_tls = Boolean(default=False)
    referrals = Boolean(default=False)

    def __init__(self, *args, **kwargs):
        super(LdapStore, self).__init__(*args, **kwargs)
        self.itself = None

    def apply(self):
        if self.backend in LdapDataStore.SUPPORTED_BACKENDS:
            self.itself = LdapDataStore(self)
            self.itself.apply()

        else:
            raise ValueError(self.backend)

class FileStore(StorageInfo):
    path = M(Unicode)

    def apply(self):
        self.path = abspath(self.path)
        if not os.path.isdir(self.path):
            os.makedirs(self.path)


class RelationalStore(StorageInfo):
    conn_str = Unicode

    # move these to QueuePool config.
    pool_size = UnsignedInteger(default=10)
    pool_recycle = UnsignedInteger(default=3600)
    pool_timeout = UnsignedInteger(default=30)
    max_overflow = UnsignedInteger(default=3)
    echo_pool = Boolean(default=False)

    sync_pool = Boolean(default=True)
    sync_pool_type = Unicode(
        default='QueuePool',
        values=[
            'SingletonThreadPool', 'QueuePool', 'NullPool',
            'StaticPool', 'AssertionPool'
        ],
    )

    async_pool = Boolean(default=True)

    def __init__(self, *args, **kwargs):
        super(RelationalStore, self).__init__(*args, **kwargs)
        self.itself = None

    def apply(self):
        self.itself = SqlDataStore(self.conn_str, pool_size=self.pool_size,
                                                       echo_pool=self.echo_pool)
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
            self.itself.engine.dispose()
            self.itself.engine = None

        return self

    def close(self):
        if self.async_pool:
            self.itself.txpool.close()

        if self.sync_pool:
            self.itself.Session = None
            self.itself.metadata = None
            self.itself.engine.dispose()
            self.itself.engine = None

        self.itself = None

        return self
