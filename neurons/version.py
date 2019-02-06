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

from time import time

from contextlib import closing
from collections import namedtuple

from spyne import Integer32, M, Unicode
from neurons import TableModel


MigrationOperation = namedtuple("MigrationOperation",
                        "submodule migration_dict current_version migrate_init")


class Version(TableModel):
    migopts = []

    __tablename__ = "neurons_version"
    _type_info = [
        ('id', Integer32(pk=True)),
        ('submodule', M(Unicode, unique=True)),
        ('version', M(Integer32)),
    ]

    @classmethod
    def register_submodule(cls, submodule, migration_dict, current_version,
                                                             migrate_init=None):
        cls.migopts.append(
            MigrationOperation(submodule, migration_dict, current_version,
                                                                   migrate_init)
        )

    @staticmethod
    def migrate_all(config):
        for migopt in Version.migopts:
            Version.migrate(config, *migopt)

    @staticmethod
    def migrate(config, submodule, migration_dict, current_version,
                                                                  migrate_init):
        num_migops = 0
        table_name = Version.Attributes.table_name
        Version.Attributes.sqla_table.create(checkfirst=True)

        db = config.get_main_store()
        with closing(db.Session()) as session:
            logger.info("Acquiring pg_advisory_xact_lock(0) "
                                                    "for schema version checks")
            session.connection().execute("select pg_advisory_xact_lock(0)")

            # Create missing tables
            TableModel.Attributes.sqla_metadata.create_all(checkfirst=True)

            db_version = session.query(Version) \
                                         .filter_by(submodule=submodule).first()

            if db_version is None:
                version_entry = \
                           Version(submodule=submodule, version=current_version)

                session.add(version_entry)

                if migrate_init is not None:
                    migrate_init(config, session)
                    logger.info("Submodule '%s' schema version management "
                               "pre-init was executed successfully.", submodule)

                logger.info("Submodule '%s' schema version management "
                                        "was initialized as %d successfully.",
                                                     submodule, current_version)

                session.commit()

                return

            keys = [vernum for vernum in migration_dict.keys()
                              if db_version.version < vernum <= current_version]
            keys.sort()

            if len(keys) > 0:
                logger.info("%s schema version detected as %s. "
                                "Migration operation(s) %r will be performed",
                                            submodule, db_version.version, keys)

            for vernum in keys:
                migrate = migration_dict[vernum]

                with closing(db.Session()) as inner_session:
                    inner_db_version = inner_session.query(Version) \
                                           .filter_by(submodule=submodule).one()
                    inner_db_version.version = vernum

                    try:
                        start_t = time()
                        migrate(config, inner_session)

                    except Exception as e:
                        logger.exception(e)
                        logger.error("Migration operation %d failed, "
                                                     "stopping reactor", vernum)

                        from twisted.internet import reactor
                        from twisted.internet.task import deferLater
                        deferLater(reactor, 0, reactor.stop)
                        raise

                    inner_session.commit()

                num_migops += 1
                logger.info("%s schema migration to version %d took %.1fs.",
                                            submodule, vernum, time() - start_t)

        if num_migops == 0:
            logger.info("%s schema version detected as %s. Table unlocked.",
                                                     submodule, current_version)

        elif num_migops > 0:
            logger.info("%s schema version upgraded to %s "
                           "after %d migration operations. Table unlocked.",
                                         submodule, current_version, num_migops)
