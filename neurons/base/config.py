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

import os

from spyne import Boolean, ComplexModel, Unicode, ByteArray, UnsignedInteger, \
    Array

AbsolutePath = Unicode
SystemUser = Unicode(pattern='[a-z0-9_]+', type_name='SystemUser')
SystemGroup = Unicode(pattern='[a-z0-9_]+', type_name='SystemGroup')


class ListenerConfig(ComplexModel):
    id = Unicode
    """Name of the listener resource."""

    host = Unicode(default='127.0.0.1')
    """The host the server will listen to"""

    port = UnsignedInteger(default=5534)
    """The port the server will listen to"""

    thread_min = UnsignedInteger
    """Min number of threads in the thread pool"""

    thread_max = UnsignedInteger
    """Max number of threads in the thread pool"""


class DaemonConfig(ComplexModel):
    SECTION_NAME = 'basic'

    daemonize = Boolean(default=False)
    """Fork the process to the background."""

    log_file = AbsolutePath
    """Log file."""

    pid_file = AbsolutePath
    """File that will contain the pid of the daemon process."""

    config_file = AbsolutePath
    """Alternative configuration file.."""

    uid = SystemUser
    """Daemon will drop privileges and switch to this uid when specified"""

    gid = SystemGroup
    """Daemon will drop privileges and switch to this gid when specified"""

    log_level = Unicode(values=['DEBUG', 'INFO'], default='DEBUG')
    """Logging level"""

    show_rpc = Boolean(default=False)
    """Log raw request and response data."""

    secret = ByteArray(default_factory=lambda : [os.urandom(64)],
                                                                no_cmdline=True)
    """Cookie encryption key. Keep secret."""

    thread_min = UnsignedInteger(default=3)
    """Min number of threads in the thread pool"""

    thread_max = UnsignedInteger(default=10)
    """Max number of threads in the thread pool"""

    listeners = Array(ListenerConfig)


class DatabaseConfig(ComplexModel):
    name = Unicode
    """Database name. Must be a valid python variable name."""

    type = Unicode(values=['sqlalchemy'])
    """Connection type. Only 'sqlalchemy' is supported."""

    conn_str = Unicode
    """Connection string. See SQLAlchemy docs for more info."""

    pool_size = UnsignedInteger(default=10)
    """Max. number of connections in the the db conn pool."""

    show_queries = Boolean(default=False)
    """Logs sql queries."""

    show_results = Boolean(default=False)
    """Logs sql queries as well as their results."""


class ApplicationConfig(ComplexModel):
    create_schema = Boolean(no_file=True)
    """Create database schema."""

    bootstrap = Boolean(no_file=True)
    """Insert initial data to the database."""

    generate_data = Boolean(no_file=True)
    """Fill the database with test data."""

    write_interface_documents = Boolean(no_file=True)
    """Write the interface documents to the given output directory."""


class Config(ComplexModel):
    daemon = DaemonConfig
    db = Array(DatabaseConfig)
    app = ApplicationConfig
