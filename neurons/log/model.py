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

import logging
logger = logging.getLogger(__name__)

from spyne import M, Integer32, Integer64, Integer, ByteArray, Unicode, \
    DateTime, Boolean, IpAddress, AnyXml, AnyDict, ComplexModel, Uuid

from neurons import TableModel
from neurons.version import Version

from sqlalchemy import sql


class LogEntryMixin(ComplexModel):
    __mixin__ = True
    __table_args__ = {"sqlite_autoincrement": True}

    _type_info = [
        ('id', Integer64(primary_key=True)),
        ('id_session', Uuid),
        ('id_message', Uuid),

        ('time', M(DateTime(timezone=False, server_default=sql.func.now()))),
        ('domain', Unicode(255)),
        ('username', Unicode(255)),

        ('method_name', M(Unicode(255))),
        ('duration_ms', Integer32),
        ('read_only', M(Boolean)),

        ('daemon_version', Integer64),
        ('daemon_name', Unicode(32)),

        ('is_request', M(Boolean(default=True, server_default='true'))),
        ('err_code_in', Unicode),
        ('err_code_out', Unicode),

        ('host', IpAddress),

        # TODO: figure out how these will work
        # ('id_session', Uuid),
        # ('id_message', Uuid),

        ('data_in_xml', AnyXml),
        ('data_in_json', AnyDict(store_as='json')),
        ('data_out_int', Integer64),
        ('data_out_xml', AnyXml),
        ('data_out_json', Integer64),
    ]


def migrate_2(config, session):
    session.connection().execute("""
      alter table neurons_log add column id_session uuid;
      alter table neurons_log add column id_message uuid;
    """)


migdict = {
    2: migrate_2,
}


DB_SCHEMA_VERSION = max(migdict.keys())


def TLogEntry(table_model=TableModel):
    # Register version table for migration
    Version.register_submodule("neurons_log", migdict, DB_SCHEMA_VERSION)

    class LogEntry(table_model, LogEntryMixin):
        __namespace__ = 'http://spyne.io/neurons/log'
        __tablename__ = 'neurons_log'

    return LogEntry
