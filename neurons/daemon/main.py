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

from __future__ import print_function

from time import time
py_start_t = time()
"""Approximate start time of the python code"""

import logging
logger = logging.getLogger(__name__)

import os
import threading
import warnings
import inspect

from os.path import isfile, join, dirname

from colorama import Fore

from spyne.util.six import StringIO
from spyne.util.color import DARK_R
from spyne.store.relational.util import database_exists, create_database

from sqlalchemy import MetaData

from neurons.daemon.config import FileStore, ServiceDaemon, \
    RelationalStore, LdapStore, Server


def get_package_version(pkg_name):
    try:
        import pkg_resources
        return pkg_resources.get_distribution(pkg_name).version
    except Exception:
        return 'unknown'


def _print_version(config):
    myver = get_package_version(config.name)
    if myver == 'unknown':
        print("Package '%s' version could not be determined. Please make "
              "sure a root package name is passed as daemon_name to the main "
              "function and also the package is correctly installed.")
    else:
        print("This is %s-%s" % (config.name, myver))

    print()
    print("Also:")
    print(" * lxml-%s" % get_package_version('lxml'))
    print(" * pytz-%s" % get_package_version('pytz'))
    print(" * spyne-%s" % get_package_version('spyne'))
    print(" * pyyaml-%s" % get_package_version('pyyaml'))
    print(" * neurons-%s" % get_package_version('neurons'))
    print(" * twisted-%s" % get_package_version('twisted'))
    print(" * msgpack-%s" % get_package_version('msgpack-python'))
    print(" * pycrypto-%s" % get_package_version('pycrypto'))
    print(" * werkzeug-%s" % get_package_version('werkzeug'))
    print(" * txpostgres-%s" % get_package_version('txpostgres'))
    print(" * SQLAlchemy-%s" % get_package_version('SQLAlchemy'))
    print()

    return 0  # to force exit


def _write_wsdl(config):
    from lxml import etree

    from spyne.interface.wsdl import Wsdl11
    from spyne.test.sort_wsdl import sort_wsdl
    from spyne.util.appreg import applications

    for (tns, name), appdata in applications.items():
        appdata.app.transport = "no_transport_at_all"
        wsdl = Wsdl11(appdata.app.interface)
        wsdl.build_interface_document('hxxp://invalid_url')
        doc = wsdl.get_interface_document()
        elt = etree.parse(StringIO(doc))
        sort_wsdl(elt)

        file_name = join(config.write_wsdl, 'wsdl.%s.xml' % name)

        try:
            os.makedirs(dirname(file_name))
        except OSError:
            pass

        try:
            with open(file_name, 'w') as f:
                f.write(etree.tostring(elt, pretty_print=True))
        except Exception as e:
            print("Error:", e)
            return -1

        print(file_name, "written.")

    return 0  # to force exit


def _write_xsd(config):
    from lxml import etree

    from spyne.interface.xml_schema import XmlSchema
    from spyne.util.appreg import applications

    for (tns, name), appdata in applications.items():
        xsd = XmlSchema(appdata.app.interface)
        xsd.build_interface_document()
        schemas = xsd.get_interface_document()

        dir_name = join(config.write_xsd, 'schema.%s' % name)

        try:
            os.makedirs(dir_name)
        except OSError:
            pass

        for k, v in schemas.items():
            file_name = os.path.join(dir_name, "%s.xsd" % k)

            try:
                with open(file_name, 'wb') as f:
                    etree.ElementTree(v).write(f, pretty_print=True)

            except Exception as e:
                print("Error:", e)
                return -1

            print("written",file_name, "for ns", appdata.app.interface.nsmap[k])

    return 0  # to force exit


def _do_bootstrap(config, init, bootstrap, bootstrapper):
    if bootstrap is None:
        bootstrap = bootstrapper(init)
    else:
        config.apply()

    assert callable(bootstrap), \
                      "'bootstrap' must be a callable. It's %r." % bootstrap

    # perform bootstrap
    retval = bootstrap(config)

    if retval is None:
        return 0  # to force exit
    return retval


def _do_drop_all_tables(config, init):
    config.log_queries = True
    config.apply()

    import neurons
    meta = neurons.TableModel.Attributes.sqla_metadata
    meta.reflect()

    meta.drop_all()

    return 0


def _do_start_shell(config):
    # Import db handle, session and other useful stuff to the shell's scope
    db = None
    if isinstance(config, ServiceDaemon):
        db = config.get_main_store()

    # so that there is a db session handy in the shell
    session = db.Session()

    # these are just useful to have in a dev. shell
    import IPython

    header = (
        "Database handle is:  db\n"
        "There's also an open session: session\n"
        "Imported packages: traceback, inspect, sys\n"
        "Imported functions: pprint(), pformat()"
    )

    # start the kind of shell requested by user
    if config.shell:
        return IPython.embed(header=header)

    if config.ikernel:
        return IPython.embed_kernel()


def _set_real_factory(lp, subconfig, factory):
    # lp = listening port -- what endpoint.listen()'s return value ends up as
    if hasattr(lp.factory, 'wrappedFactory'):
        import twisted.protocols.tls
        assert isinstance(lp.factory, twisted.protocols.tls.TLSMemoryBIOFactory)
        target_factory = lp.factory.wrappedFactory

    else:
        target_factory = lp.factory

    subconfig.color = Fore.GREEN

    assert isinstance(target_factory, Server.FactoryProxy)
    target_factory.real_factory = factory

    logger.info("%s Service ready with factory %r",
                                                subconfig.colored_name, factory)


def _inner_main(config, init, bootstrap, bootstrapper):
    # if requested, print version and exit
    if config.version:
        return _print_version(config)

    # if requested, perform bootstrap and exit
    if config.bootstrap:
        return _do_bootstrap(config, init, bootstrap, bootstrapper)

    if isinstance(config, ServiceDaemon):
        # if requested, drop all tables and exit
        if config.drop_all_tables:
            return _do_drop_all_tables(config, init)

    config.apply()
    logger.info("%s config valid, initializing services...", config.name)

    # initialize main table model
    if isinstance(config, ServiceDaemon):
        if config.main_store is None:
            config.main_store = 'sql_main'

        if config.debug_reactor:
            config.add_reactor_checks()

        from neurons import TableModel
        TableModel.Attributes.sqla_metadata.bind = \
                                                  config.get_main_store().engine

    # initialize applications
    items = init(config)
    if hasattr(items, 'items'):  # if it's a dict
        items = items.items()

    # apply app-specific config
    for k, v in items:
        disabled = False
        if k in config.services:
            disabled = config.services[k].disabled

        if v.force is not None:
            if k in config.services:
                oldconfig = config.services[k]
                subconfig = config.services[k] = v.force
                if oldconfig.d is not None:
                    subconfig.d = oldconfig.d

                if oldconfig.listener is not None:
                    subconfig.listener = oldconfig.listener

            else:
                subconfig = config.services[k] = v.force

            logger.info("%s Configuration initialized from "
                               "hard-coded object.", subconfig.colored_name)

        else:
            k_was_there = k in config.services
            subconfig = config.services.getwrite(k, v.default)
            disabled = subconfig.disabled

            if k_was_there:
                logger.info("%s Configuration initialized from file.",
                                                     subconfig.colored_name)
            else:
                logger.info("%s Configuration initialized from default.",
                                                     subconfig.colored_name)

        factory = v.init(config)

        if disabled:
            logger.info("%s Service disabled.", DARK_R('[%s]' % (k,)))

        if not isinstance(subconfig, Server):
            continue

        if subconfig.d is not None:
            if subconfig.listener is None:
                subconfig.d.addCallback(_set_real_factory, subconfig, factory)

            else:
                _set_real_factory(subconfig.listener, subconfig, factory)

        elif not subconfig.disabled:
            subconfig.listen() \
                .addCallback(_set_real_factory, subconfig, factory)

    # if requested, write interface documents and exit
    if isinstance(config, ServiceDaemon):
        if config.write_wsdl:
            return _write_wsdl(config)

        if config.write_xsd:
            return _write_xsd(config)

    if config.write_config:
        config.do_write_config()
        return 0

    # Perform schema migrations
    from neurons.version import Version
    Version.migrate_all(config)

    # if requested, drop to shell
    if config.shell or config.ikernel:
        ret = _do_start_shell(config)
        if ret is None:
            return 0


class Bootstrapper(object):
    """Creates all databases"""

    def __init__(self, init):
        self.init = init
        self.meta_reflect = MetaData()

    def before_tables(self, config):
        pass

    def after_tables(self, config):
        pass

    def create_relational(self, store):
        if database_exists(store.conn_str):
            print(store.conn_str, "already exists.")
            return

        create_database(store.conn_str)
        print(store.conn_str, "did not exist, created.")

    def __call__(self, config):
        # we are printing stuff here in case the log goes to a log file and the
        # poor ops guy can't see a thing
        for store in config.stores.values():
            if isinstance(store, RelationalStore):
                self.create_relational(store)

            elif isinstance(store, LdapStore):
                warnings.warn("LDAP bootstrap is not implemented.")

            elif isinstance(store, FileStore):
                try:
                    os.makedirs(store.path)
                    print("File store", store.name, "directory", store.path,
                                                            'has been created.')
                except OSError:
                    print("File store", store.name, "directory", store.path,
                                                              'already exists.')

            else:
                raise ValueError(store)

        config.apply(daemonize=False)

        main_engine = config.get_main_store().engine

        # reflect database just in case -- can be useful while bootstrapping
        self.meta_reflect.reflect(bind=main_engine)
        print("Reflection")

        # Run init so that all relevant models get imported
        self.init(config)
        print("Init")

        from neurons.model import TableModel
        TableModel.Attributes.sqla_metadata.bind = main_engine

        # Init schema versions
        from neurons.version import Version
        Version.migrate_all(config)

        self.before_tables(config)

        TableModel.Attributes.sqla_metadata.create_all(checkfirst=True)
        print("All tables created.")

        self.after_tables(config)

        from spyne.util.color import G
        print(G("Bootstrap complete."))


def _set_reactor_thread():
    import neurons
    neurons.REACTOR_THREAD = threading.current_thread()
    neurons.REACTOR_THREAD_ID = neurons.REACTOR_THREAD.ident
    neurons.is_reactor_thread = neurons._base._is_reactor_thread


def _compile_mappers():
    logger.info("Compiling object mappers...")
    from sqlalchemy.orm import compile_mappers
    compile_mappers()


def boot(config_name, argv, init, bootstrap=None,
                bootstrapper=Bootstrapper, cls=ServiceDaemon, daemon_name=None):
    """Boots the daemon. The signature is the same as the ``main()`` function in
    this module.

    :param config_name: Configuration file name. .yaml suffix is appended.
    :param argv: A sequence of command line arguments.
    :param init: A callable that returns the init dict.
    :param bootstrap: A callable that bootstraps daemon's environment.
        It's DEPRECATED in favor of bootstrapper.
    :param bootstrapper: A factory for a callable that bootstraps daemon's
        environment. This is supposed to be run once for every new deployment.
    :param cls: a class:`Daemon` subclass
    :param daemon_name: Daemon name. If ``None``, ``config_name`` is used.
    :return: The return code to be passed to sys.exit() and the daemon config
        object. If the return code is None, it's OK to proceed with running the
        daemon.
    """

    config = cls.parse_config(config_name, argv)
    if config.help:
        from neurons.daemon.cli import spyne_to_argparse

        print(spyne_to_argparse(cls, ignore_defaults=False).format_help())
        return 0, config

    if config.name is None:
        config.name = config_name

    if daemon_name is not None:
        config.name = daemon_name

    # FIXME: Any better ideas?
    has_services = hasattr(config, '_services')
    has_stores = hasattr(config, '_stores')

    services = None
    if has_services:
        services = list(config._services)

    stores = None
    if has_stores:
        stores = list(config._stores)

    try:
        retcode = _inner_main(config, init, bootstrap, bootstrapper)

        # if _inner_main did something other than initializing daemons
        if retcode is not None:
            return retcode, config

    finally:
        if not isfile(config.config_file):
            config.do_write_config()
            logger.info("Writing configuration to: '%s'", config.config_file)

        elif has_services and services != config._services:
            config.do_write_config()
            logger.info("Updating configuration file because new services were "
                                                                     "detected")

        elif has_stores and stores != config._stores:
            config.do_write_config()
            logger.info("Updating configuration file because new stores were "
                                                                     "detected")

        # FIXME: could someone need these during bootstrap above?
        if config.uuid is None:
            config.uuid = config.gen_uuid()
            config.do_write_config()
            logger.info("Updating configuration file because new uuid was "
                                                                    "generated")

        if config.secret is None:
            config.secret = config.gen_secret()
            config.do_write_config()
            logger.info("Updating configuration file because new secret was "
                                                                    "generated")

    return None, config

def _log_ready(config_name, orig_stack, py_start_t, func_start_t):
    import resource

    try:
        import psutil
        proc_start_t = psutil.Process(os.getpid()).create_time()
    except ImportError:
        proc_start_t = '?'

    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000.0

    package_name = config_name

    frame, file_name, line_num, func_name, lines, line_id = orig_stack[1]
    module = inspect.getmodule(frame)
    if module is not None:
        package_name = module.__name__.split('.')[0]

    logger.info(
        "%s version %s ready. Max RSS: %.1fmb uptime: %s import: %.2fs "
                                                              "main: %.2fs",
        config_name, get_package_version(package_name),
        max_rss,
        '[?psutil?]' if proc_start_t == '?'
                                    else '%.2fs' % (time() - proc_start_t,),
        time() - py_start_t,
        time() - func_start_t,
    )


def main(config_name, argv, init, bootstrap=None,
                bootstrapper=Bootstrapper, cls=ServiceDaemon, daemon_name=None):
    """Boots and runs the daemon, making it ready to accept requests. This is a
    typical main function for daemons. If you just want to boot the daemon
    and take care of running it yourself, see the ``boot()`` function.

    :param config_name: Configuration file name. .yaml suffix is appended.
    :param argv: A sequence of command line arguments.
    :param init: A callable that returns the init dict.
    :param bootstrap: A callable that bootstraps daemon's environment.
        It's deprecated in favor of bootstrapper.
    :param bootstrapper: A factory for a callable that bootstraps daemon's
        environment. This is supposed to be run once for every new deployment.
    :param cls: a class:`Daemon` subclass
    :param daemon_name: Daemon name. If ``None``, ``config_name`` is used.
    :return: Exit code of the daemon as int.
    """

    func_start_t = time()
    """Start time of post-import initialization code"""

    retcode, config = boot(config_name, argv, init, bootstrap,
                                                 bootstrapper, cls, daemon_name)

    # at this point it's safe to import the reactor (or anything else from
    # twisted) because the decision on whether to fork has already been made.
    from twisted.internet import reactor
    from twisted.internet.task import deferLater

    deferLater(reactor, 0, _compile_mappers) \
        .addErrback(lambda err: logger.error("%s", err.getTraceback()))

    deferLater(reactor, 0, _set_reactor_thread) \
        .addErrback(lambda err: logger.error("%s", err.getTraceback()))

    deferLater(reactor, 0, _log_ready,
                       config_name, inspect.stack(), py_start_t, func_start_t) \
        .addErrback(lambda err: logger.error("%s", err.getTraceback()))

    # this needs to be done as late as possible to capture the highest number of
    # watched (ie imported) modules.
    if config.autoreload:
        from spyne.util.autorel import AutoReloader
        frequency = 0.5
        autorel = AutoReloader(frequency=frequency)
        assert autorel.start() is not None
        num_files = len(autorel.sysfiles() | autorel.files)
        logger.info("Auto reloader init success: Watching %d files "
                                      "every %g seconds.", num_files, frequency)

    if config.dry_run:
        return 0

    return reactor.run()
