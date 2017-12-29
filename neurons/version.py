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

from sqlalchemy import DDL
from sqlalchemy import event

logger = logging.getLogger(__name__)

from contextlib import closing

from spyne import Integer32, M
from neurons import TableModel

entries = []


def TVersion(prefix, migration_dict, current_version, migrate_init=None):
    table_name = '%s_version' % prefix

    class Version(TableModel):
        __tablename__ = table_name
        _type_info = [
            ('id', Integer32(pk=True)),
            ('version', M(Integer32)),
        ]

        @staticmethod
        def migrate(config):
            num_migops = 0
            Version.Attributes.sqla_table.create(checkfirst=True)

            db = config.get_main_store()
            with closing(db.Session()) as session:
                logger.info("Locking table '%s' for schema version checks",
                                                                     table_name)
                session.connection().execute(
                            "lock %s in access exclusive mode;" % (table_name,))

                # Create missing tables
                TableModel.Attributes.sqla_metadata.create_all(checkfirst=True)
                versions = session.query(Version).all()

                if len(versions) == 0:
                    session.add(Version(version=current_version))

                    if migrate_init is not None:
                        num_migops += 1
                        migrate_init(config, session)
                        logger.info("Performed before-init operations")

                    num_migops = -1
                    logger.info("%s schema version management initialized. "
                                 "Current version: %d", prefix, current_version)

                elif len(versions) > 1:
                    session.query(Version).delete()

                    session.add(Version(version=current_version))

                    logger.warning("Multiple rows %r found in schema version "
                                   "for %s. Resetting schema version to %d",
                                              versions, prefix, current_version)

                else:
                    db_version = versions[0]

                    for vernum, migrate in migration_dict.items():
                        if db_version.version < vernum <= current_version:
                            db_version.version = vernum

                            migrate(config, session)

                            session.commit()

                            num_migops += 1
                            logger.info("%s schema migration to version %d was "
                                    "performed successfully.", prefix, vernum)

                session.commit()

            if num_migops == 0:
                logger.info("%s schema version detected as %s. Table unlocked.",
                                                        prefix, current_version)

            elif num_migops > 0:
                logger.info("%s schema version upgraded to %s "
                               "after %d migration operations. Table unlocked.",
                                            prefix, current_version, num_migops)

    event.listen(
        Version.Attributes.sqla_table, "after_create",
        DDL("CREATE UNIQUE INDEX {0}_one_row "
                            "ON {0}((version IS NOT NULL));".format(table_name))
    )

    entries.append(Version)

    return Version
