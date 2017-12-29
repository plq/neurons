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

from collections import defaultdict


class ReadContext(object):
    def __init__(self, parent):
        self.trusted = False

        self.parent = parent

        self.domain = None
        self.username = None

        self.log_entry = None

        self.do_log = True
        self.do_log_inbound = True
        self.do_log_outbound = False
        self.is_read_only = True

        self.short_log_level = logging.INFO

        self.sqla_sessions = defaultdict(list)

        self._initialized = True

    def __repr__(self):
        if self.domain is None and self.username is None:
           return "Context(ro={})".format(self.is_read_only)

        if self.domain is None:
           return "Context(ro={}, user={})".format(self.is_read_only,
                                                                  self.username)

        return "Context(ro={}, user={}@{})".format(self.is_read_only,
                                                     self.username, self.domain)

    def sqla_finalize(self, session):
         pass

    def get_du(self):
        if self.domain is None:
            return self.username
        return "%s@%s" % (self.username, self.domain)

    def get_main_session(self, **kwargs):
        return self.get_session(self.parent.app.config.get_main_store(**kwargs))

    def get_session(self, store, **kwargs):
        if store.type == 'sqlalchemy':
            sessions = self.sqla_sessions[id(store)]

            if len(sessions) == 0:
                session = store.Session(**kwargs)
                self.sqla_sessions[id(store)].append(session)

            else:
                assert len(kwargs) == 0
                session = sessions[0]

            return session

        elif store.type == 'ldap':
            return store.conn

        raise NotImplementedError(store)

    def close(self, no_error=True):
        for sessions in self.sqla_sessions.values():
            for session in sessions:
                if no_error:
                    self.sqla_finalize(session)
                session.close()

        # TODO: Close LDAP sessions?

    def has_role(self, role_cls):
        for role in self.roles:
            if role.role == role_cls.__role_name__:
                return True

        return False


class WriteContext(ReadContext):
    def __init__(self, parent):
        super(WriteContext, self).__init__(parent)

        self.is_read_only = False

    def sqla_finalize(self, session):
        logger.debug("Committing transaction for ctx 0x%012X", id(self.parent))
        session.commit()
