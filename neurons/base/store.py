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


from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import create_engine

from twisted.python.threadpool import ThreadPool
from twisted.internet import reactor


class DBThreadPool(ThreadPool):
    def __init__(self, engine, maxthreads=10, verbose=False):
        if engine.dialect.name == 'sqlite':
            ThreadPool.__init__(self, minthreads=1, maxthreads=1)
        else:
            ThreadPool.__init__(self, maxthreads=maxthreads)

        self.engine = engine
        reactor.callWhenRunning(self.start)

    def start(self):
        reactor.addSystemEventTrigger('during', 'shutdown', self.stop)
        ThreadPool.start(self)


class DataStore(object):
    class SQL: pass

    def __init__(self, type):
        self.type = type


class SqlDataStore(DataStore):
    def __init__(self, name, connstr, async=False, **kwargs):
        super(SqlDataStore, self).__init__(type=DataStore.SQL)

        self.name = name
        self.connstr = connstr
        self.kwargs = kwargs

        self.txpool = None
        self.deferred_start = None
        self.engine = None
        self.Session = None
        self.threadpool = None

        if async:
            if self.connstr.startswith('postgres://'):
                self.use_txpostgres()

            raise NotImplemented(self.connstr.split('/', 1)[0] + "//") # pfft...
        else:
            self.use_sqlalchemy()

    def use_txpostgres(self):
        engine = create_engine(self.connstr, **self.kwargs)
        dsn = engine.raw_connection().connection.dsn
        engine.dispose()

        from txpostgres import txpostgres

        self.txpool = txpostgres.ConnectionPool(self.name, dsn)
        self.deferred_start = self.txpool.start()

        self.engine.close()

    def use_sqlalchemy(self):
        if self.connstr.startswith('sqlite://') or \
                                              self.connstr.endswith(":memory:"):

            self.kwargs['poolclass'] = StaticPool

            if self.connstr.startswith('sqlite'):
                self.kwargs['connect_args'] = {'check_same_thread': False}
            if 'pool_size' in self.kwargs:
                del self.kwargs['pool_size']

        self.engine = create_engine(self.connstr, **self.kwargs)
        self.Session = sessionmaker(bind=self.engine)
