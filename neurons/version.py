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

    @staticmethod
    def register_submodule(submodule, migration_dict, current_version,
                           migrate_init=None):
        Version.migopts.append(
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
        table_name = Version.Attributes.table_name
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
                version_entry = \
                           Version(submodule=submodule, version=current_version)

                session.add(version_entry)

                if migrate_init is not None:
                    num_migops += 1
                    migrate_init(config, session)
                    logger.info("Performed before-init operations")

                num_migops = -1
                logger.info("%s schema version management initialized. "
                              "Current version: %d", submodule, current_version)

            elif len(versions) > 1:
                session.query(Version).delete()

                session.add(Version(version=current_version))

                logger.warning("Multiple rows %r found in schema version "
                               "for %s. Resetting schema version to %d",
                                           versions, submodule, current_version)

            else:
                db_version = versions[0]

                for vernum, migrate in migration_dict.items():
                    if db_version.version < vernum <= current_version:
                        db_version.version = vernum

                        migrate(config, session)

                        session.commit()

                        num_migops += 1
                        logger.info("%s schema migration to version %d was "
                                   "performed successfully.", submodule, vernum)

            session.commit()

        if num_migops == 0:
            logger.info("%s schema version detected as %s. Table unlocked.",
                                                     submodule, current_version)

        elif num_migops > 0:
            logger.info("%s schema version upgraded to %s "
                           "after %d migration operations. Table unlocked.",
                                         submodule, current_version, num_migops)
