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

from spyne import TTableModel, Integer32
from spyne.model import TTableModelBase
from spyne.store.relational import get_pk_columns

from sqlalchemy.orm import make_transient


class TableModelBase(TTableModelBase()):
    def __init__(self, *args, **kwargs):
        self._changes = set()

        super(TableModelBase, self).__init__(*args, **kwargs)

    def _safe_set(self, key, value, t, attrs):
        retval = super(TableModelBase, self)._safe_set(key, value, t, attrs)
        if retval:
            self._changes.add(key)
        return retval

    @classmethod
    def __respawn__(cls, ctx=None, filters=None):
        has_db = ctx.app is not None and 'sql_main' in ctx.app.config.stores

        if has_db and ctx is not None and ctx.in_object is not None \
                    and len(ctx.in_object) > 0 and ctx.in_object[0] is not None:
            in_object = ctx.in_object[0]

            if filters is None:
                filters = {}

            for k, v in get_pk_columns(cls):
                filters[k] = getattr(in_object, k)

            session = ctx.udc.get_main_session()
            retval = session.query(cls) \
                .with_polymorphic('*') \
                .filter_by(**filters) \
                .all()

            if len(retval) == 0:
                for k, v in get_pk_columns(cls):
                    setattr(in_object, k, None)
                return in_object

            if len(retval) == 1:
                retval = retval[0]

                make_transient(retval)
                for k in in_object._changes:
                    setattr(retval, k, getattr(in_object, k))
                return retval

        if ctx.descriptor.default_on_null:
            return cls.get_deserialization_instance(ctx)


TableModel = TTableModel(base=TableModelBase)
