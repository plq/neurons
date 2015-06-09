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

from contextlib import closing

from spyne import TTableModel, Integer32
from spyne.store.relational import get_pk_columns

TableModel = TTableModel()


def TVersion(prefix, default_version):
    class Version(TableModel):
        __tablename__ = '%s_version' % prefix

        id = Integer32(pk=True)
        version = Integer32(default=default_version)

    return Version


def respawn(cls, ctx=None):
    has_db = ctx.app is not None and 'sql_main' in ctx.app.config.stores

    if ctx is not None and ctx.in_object is not None and len(ctx.in_object) > 0 \
                       and ctx.in_object[0] is not None and has_db:
        in_object = ctx.in_object[0]

        filters = {}
        for k, v in get_pk_columns(cls):
            filters[k] = getattr(in_object, k)

        db = ctx.app.config.stores['sql_main'].itself
        with closing(db.Session()) as session:
            return session.query(cls).with_polymorphic('*').filter_by(**filters).one()


TableModel.__respawn__ = classmethod(respawn)
