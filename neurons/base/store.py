# encoding: utf8
#
# This file is part of the Neurons project.
# Copyright (c), Burak Arslan <burak.arslan@arskom.com.tr>,
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
# * Neither the name of the {organization} nor the names of its
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


class DataStore(object):
    class SQLALCHEMY: pass

    def __init__(self, type):
        self.type = type


class SqlDataStore(DataStore):
    def __init__(self, connection_string=None, engine=None, metadata=None, **kwargs):
        super(SqlDataStore, self).__init__(type=DataStore.SQLALCHEMY)

        from sqlalchemy import MetaData
        from sqlalchemy.orm import sessionmaker

        self.__kwargs = kwargs
        self.__metadata = None
        self.__engine = None
        self.Session = None

        self.metadata = metadata or MetaData()
        self.engine = engine
        self.Session = sessionmaker()
        self.connection_string = connection_string

        self.txpool = None
        """TxPostgres connection pool.`add_txpool` cagirinca ekleniyor."""

        self.deferred_start = None
        """TxPostgres connection pool'un start()'i cagrilinca donen deferred.
         baglantilar acilinca cagriliyor."""

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
        if self.__engine is not None:
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
