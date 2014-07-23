
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
