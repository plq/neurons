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

from collections import defaultdict

from neurons.base.const import ANON_USERNAME


class ReadContext(object):
    def __init__(self, parent):
        self.parent = parent

        self.user = ANON_USERNAME
        self.logged = True
        self.log_entry = None
        self.sqla_sessions = defaultdict(list)

    def is_read_only(self):
        return True

    def sqla_finalize(self, session):
        logger.warning("This is a read-only context!")

    def get_session(self, store, **kwargs):
        if store.backend == 'sqlalchemy':
            sessions = self.sqla_sessions[id(store)]
            if len(sessions) == 0:
                session = store.Session(**kwargs)
                self.sqla_sessions[id(store)].append(session)
            else:
                assert len(kwargs) == 0
                session = sessions[0]

            return session

        raise NotImplementedError(store)

    def close(self, no_error=True):
        for sessions in self.sqla_sessions.values():
            for session in sessions:
                if no_error:
                    self.sqla_finalize(session)
                session.close()


class WriteContext(ReadContext):
    def sqla_finalize(self, session):
        session.commit()
