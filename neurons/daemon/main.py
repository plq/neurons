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

from __future__ import print_function

import logging
logger = logging.getLogger(__name__)

import os, gc, sys
import threading
import resource

from os.path import isfile, join, dirname

from spyne.util.six import StringIO
from spyne.store.relational.util import database_exists, create_database

from neurons.daemon.config import ServiceDisabled, ServiceDaemon


def get_package_version(pkg_name):
    try:
        import pkg_resources
        return pkg_resources.get_distribution(pkg_name).version
    except Exception as e:
        sys.stderr.write(repr(e))
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

    return True  # to force exit


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

    return True  # to force exit


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

    return True  # to force exit


def _do_bootstrap(config, init, bootstrap, bootstrapper):
    if bootstrap is None:
        bootstrap = bootstrapper(init)
    else:
        config.apply()

    assert callable(bootstrap), \
                      "'bootstrap' must be a callable. It's %r." % bootstrap

    retval = bootstrap(config)
    if retval is None:
        return True  # we must return *something* to force exit
    return retval


def _do_drop_all_tables(config, init):
    config.log_queries = True
    config.apply()

    import neurons
    meta = neurons.TableModel.Attributes.sqla_metadata
    meta.reflect()

    meta.drop_all()

    return True


def _do_start_shell(config):
    # Import db handle, session and other useful stuff to the shell's scope
    db = None
    if isinstance(config, ServiceDaemon):
        db = config.get_main_store()

    # so that there is a db session handy in the shell
    session = db.Session()

    # these are just useful to have in a dev. shell
    import IPython, traceback, inspect, sys
    from pprint import pprint, pformat

    header = (
        "Database handle is:           db\n"
        "There's also an open session: session\n"
        "Imported packages:  traceback, inspect, sys\n"
        "Imported functions: pprint(), pformat()"
    )

    # start the kind of shell requested by user
    if config.shell:
        return IPython.embed(header=header)

    if config.ikernel:
        return IPython.embed_kernel()


def _inner_main(config, init, bootstrap, bootstrapper):
    # if requested, print version and exit
    if config.version:
        return _print_version(config)

    # if requested, perform bootstrap and exit
    if config.bootstrap:
        return _do_bootstrap(config, init, bootstrap, bootstrapper)

    # if requested, perform bootstrap and exit
    if config.drop_all_tables:
        return _do_drop_all_tables(config, init)

    config.apply()
    logger.info("Initialized '%s' version %s.", config.name,
                                               get_package_version(config.name))

    # initialize main table model
    if isinstance(config, ServiceDaemon):
        if config.main_store is None:
            config.main_store = 'sql_main'

        from neurons import TableModel
        TableModel.Attributes.sqla_metadata.bind = \
                                  config.get_main_store().engine

    # initialize applications
    items = init(config)
    if hasattr(items, 'items'):  # if it's a dict
        items = items.items()

    # apply app-specific config
    handles = config._handles = {}
    for k, v in items:
        disabled = False
        if k in config.services:
            disabled = config.services[k].disabled

        if disabled:
            logger.info("Service '%s' is disabled in the config.", k)
            continue

        try:
            handles[k] = v(config)
        except ServiceDisabled:
            logger.info("Service '%s' is disabled.", k)

    # if requested, write interface documents and exit
    if isinstance(config, ServiceDaemon):
        if config.write_wsdl:
            return _write_wsdl(config)

        if config.write_xsd:
            return _write_xsd(config)

    if config.write_config:
        config.do_write_config()
        return True

    # if requested, drop to shell
    if config.shell or config.ikernel:
        retval = _do_start_shell(config)
        if retval is None:
            return True


class BootStrapper(object):
    def __init__(self, init):
        self.init = init

    def __call__(self, config):
        for store in config.stores.values():
            if database_exists(store.conn_str):
                print(store.conn_str, "already exists.")
                continue

            create_database(store.conn_str)
            print(store.conn_str, "did not exist, created.")

        config.log_results = True
        config.apply()

        # Run init so that all relevant models get imported
        self.init(config)

        from neurons.model import TableModel
        TableModel.Attributes.sqla_metadata.bind = \
                                                  config.get_main_store().engine
        TableModel.Attributes.sqla_metadata.create_all(checkfirst=True)


def _set_reactor_thread():
    import neurons
    neurons.REACTOR_THREAD = threading.current_thread()


def main(daemon_name, argv, init, bootstrap=None,
                                  bootstrapper=BootStrapper, cls=ServiceDaemon):
    """A typical main function for daemons.

    :param daemon_name: Daemon name.
    :param argv: A sequence of command line arguments.
    :param init: A callable that returns the init dict.
    :param bootstrap: A callable that bootstraps daemon's environment.
        It's deprecated in favor of bootstrapper.
    :param bootstrapper: A factory for a callable that bootstraps daemon's
        environment. This is supposed to be run once for every new deployment.
    :param cls: Daemon class
    :return: Exit code of the daemon as int.
    """

    config = cls.parse_config(daemon_name, argv)
    if config.name is None:
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
        retval = _inner_main(config, init, bootstrap, bootstrapper)

        # if _inner_main did something other than initializing daemons
        if retval is not None:
            return retval

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

    # at this point it's safe to import the reactor (or anything else from
    # twisted) because the decision to fork or not to fork is already made.
    from twisted.internet import reactor
    from twisted.internet.task import deferLater

    gc.collect()
    logger.info("Starting reactor... RSS: %f",
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000.0)

    deferLater(reactor, 0, _set_reactor_thread)

    return reactor.run()
