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

import os, gc
import socket
import struct
import resource

from os.path import isfile

from neurons.daemon.config import Daemon, ServiceDisabled

def _get_version(pkg_name):
    try:
        import pkg_resources
        return pkg_resources.get_distribution(pkg_name).version
    except Exception:
        return 'unknown'


MGMT_ADDR_BASE = 0x7f0101010400 # 127.1.1.1:1024


def get_mgmt_address(pid):
    """Computes management service address from process id.

    Returns a tuple containing the computed host as string and the port as int.
    """

    # port numbers should never fall below 1024.
    mgmt_addr = MGMT_ADDR_BASE + pid + 1024 * (pid // 64512)

    return (
        socket.inet_ntoa(struct.pack('!L', mgmt_addr >> 16)),
        mgmt_addr & 0xffff,
    )


def get_own_mgmt_address():
    return get_mgmt_address(os.getpid())


def _print_version(config):
    myver = _get_version(config.name)
    if myver == 'unknown':
        print("Package '%s' version could not be determined. Please make "
              "sure a root package name is passed as daemon_name to the main "
              "function and also the package is correctly installed.")
    else:
        print("This is %s-%s" % (config.name, myver))

    print()
    print("Also:")
    print(" * lxml-%s" % _get_version('lxml'))
    print(" * pytz-%s" % _get_version('pytz'))
    print(" * spyne-%s" % _get_version('spyne'))
    print(" * pyyaml-%s" % _get_version('pyyaml'))
    print(" * neurons-%s" % _get_version('neurons'))
    print(" * twisted-%s" % _get_version('twisted'))
    print(" * msgpack-%s" % _get_version('msgpack-python'))
    print(" * pycrypto-%s" % _get_version('pycrypto'))
    print(" * werkzeug-%s" % _get_version('werkzeug'))
    print(" * txpostgres-%s" % _get_version('txpostgres'))
    print(" * SQLAlchemy-%s" % _get_version('SQLAlchemy'))
    print()

    return 0


def _inner_main(config, init, bootstrap):
    if config.version:
        return _print_version(config)

    config.apply()

    logger.info("Initialized '%s' version %s.", config.name,
                                                      _get_version(config.name))

    if config.bootstrap:
        if not callable(bootstrap):
            raise ValueError("'bootstrap' must be a callable. It's %r." %
                                                                  bootstrap)

        retval = bootstrap(config)
        if retval is None:
            return 0
        return retval

    items = init(config)
    if hasattr(items, 'items'):  # if it's a dict
        items = items.items()

    for k, v in items:
        if not k in config.services or not config.services[k].disabled:
            try:
                v(config)
            except ServiceDisabled:
                logger.info("Service '%s' is disabled.", k)


def main(daemon_name, argv, init, bootstrap=None, cls=Daemon):
    config = cls.parse_config(daemon_name, argv)
    if config.name is None:
        config.name = daemon_name

    services = list(config._services)
    stores = list(config._stores)

    try:
        retval = _inner_main(config, init, bootstrap)
        if retval is not None:
            return retval
    finally:
        if not isfile(config.config_file) or services != config._services \
                                          or stores != config._stores:
            config.write_config()

    from twisted.internet import reactor

    gc.collect()
    logger.info("Starting reactor... RSS: %f",
                   resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000.0)

    return reactor.run()
