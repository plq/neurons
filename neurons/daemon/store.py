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
logger = logging.getLogger(__name__)

from sqlalchemy import MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine


try:
    import ldap
except ImportError as e:
    class _catchall(object):
        def __getattribute__(self, item):
            raise e

    ldap = _catchall()

    del _catchall


class DataStoreBase(object):
    def __init__(self, type):
        self.type = type


class PythonLdapStore(DataStoreBase):
    def __init__(self, parent):
        DataStoreBase.__init__(self, type='ldap')

        self.conn = None
        self.parent = parent

    def apply_simple(self, bind_dn=None, password=None):
        parent = self.parent

        if bind_dn is None:
            bind_dn = parent.bind_dn

        if password is None:
            password = parent.password

        if parent.use_tls:
            uri = "ldaps://%s:%d" % (parent.host, parent.port)
            retval = ldap.initialize(uri)

            retval.set_option(ldap.OPT_X_TLS, ldap.OPT_X_TLS_DEMAND)
            retval.set_option(ldap.OPT_X_TLS_DEMAND, True)

        else:
            uri = "ldap://%s:%d" % (parent.host, parent.port)
            retval = ldap.initialize(uri)

        retval.set_option(ldap.OPT_NETWORK_TIMEOUT, parent.timeout)

        if not parent.referrals:
            retval.set_option(ldap.OPT_REFERRALS, 0)

        if parent.version == 3:
            retval.protocol_version = ldap.VERSION3

        elif parent.version == 2:
            retval.protocol_version = ldap.VERSION2

        else:
            raise ValueError(parent.version)

        retval.simple_bind_s(bind_dn, password)

        logger.info("Ldap connection to %s successful.",
                                                retval.get_option(ldap.OPT_URI))

        return retval

    def apply(self):
        if self.conn is not None:
            self.conn.close()

        if self.parent.method == 'simple':
            self.conn = self.apply_simple()

        elif self.parent.method == 'sasl':
            raise NotImplementedError(self.parent.method)

        else:
            raise ValueError(self.parent.method)


# FIXME: get rid of the overly complicated property setters.
class SqlDataStore(DataStoreBase):
    def __init__(self, connection_string=None, engine=None, metadata=None, **kwargs):
        DataStoreBase.__init__(self, type='sqlalchemy')

        if engine is not None:
            assert isinstance(engine, Engine)
        if metadata is not None:
            assert isinstance(metadata, MetaData)

        self.__kwargs = kwargs
        self.__metadata = None
        self.__engine = None
        self.Session = None

        self.metadata = metadata or MetaData()
        self.engine = engine
        self.Session = sessionmaker()
        self.connection_string = connection_string

        self.txpool = None
        """TxPostgres connection pool. Added when `add_txpool` is called."""

        self.txpool_start_deferred = None
        """Deferred from TxPostgres pool start()."""

    def add_txpool(self):
        # don't import twisted too soon
        from txpostgres.txpostgres import ConnectionPool
        from txpostgres.reconnection import DeadConnectionDetector

        class LoggingDeadConnectionDetector(DeadConnectionDetector):
            def startReconnecting(self, f):
                logger.warning('TxPool database connection down: %r)', f.value)
                return DeadConnectionDetector.startReconnecting(self, f)

            def reconnect(self):
                logger.warning('TxPool reconnecting...')
                return DeadConnectionDetector.reconnect(self)

            def connectionRecovered(self):
                logger.warning('TxPool connection recovered')
                return DeadConnectionDetector.connectionRecovered(self)

        dsn = self.engine.raw_connection().connection.dsn

        self.txpool = ConnectionPool("heleleley", dsn, min=1)
        self.txpool_start_deferred = self.txpool.start()
        self.txpool_start_deferred.addCallback(
                                 lambda p: logger.info("TxPool %r started.", p))
        return self.txpool_start_deferred

    def connect(self):
        return self.__engine.connect()

    @property
    def meta(self):
        return self.__metadata

    @property
    def metadata(self):
        return self.__metadata

    @metadata.setter
    def metadata(self, metadata):
        self.__metadata = metadata
        if self.__engine is not None and metadata is not None:
            self.__metadata.bind = self.__engine

    @property
    def engine(self):
        return self.__engine

    @engine.setter
    def engine(self, engine):
        self.__engine = engine
        if engine is not None:
            if self.metadata is not None:
                self.metadata.bind = engine
            if self.Session is not None:
                self.Session.configure(bind=engine, expire_on_commit=False)

    @property
    def kwargs(self):
        return self.__kwargs

    @property
    def connection_string(self):
        return self.__connection_string

    @connection_string.setter
    def connection_string(self, what):
        from sqlalchemy.engine import create_engine
        self.__connection_string = what

        if what is None:
            self.engine = None

        else:
            if what.startswith('sqlite://') or what.endswith(":memory:"):
                from sqlalchemy.pool import StaticPool

                self.__kwargs['poolclass'] = StaticPool

                if what.startswith('sqlite'):
                    self.__kwargs['connect_args'] = {'check_same_thread': False}
                if 'pool_size' in self.__kwargs:
                    del self.__kwargs['pool_size']

            self.engine = create_engine(what, **self.__kwargs)
            logger.info("%r started with: %r", self.engine, self.kwargs)


def get_data_store(type, *args, **kwargs):
    if type == 'ldap':
        return LdapDataStore(*args, **kwargs)
    elif type == 'sqlalchemy':
        return SqlDataStore(*args, **kwargs)
    else:
        raise ValueError("Unrecognized data store %r" % type)
