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

from os.path import isfile

from neurons.daemon.config import Daemon, ServiceDisabled


def _inner_main(config, init, bootstrap):
    config.apply()

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
        if not (k in config.services and config.services[k].disabled):
            try:
                v(config)
            except ServiceDisabled:
                logger.info("Service '%s' is disabled.", k)


def main(daemon_name, argv, init, bootstrap=None, cls=Daemon):
    config = cls.parse_config(daemon_name, argv)
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
    logger.info("Starting reactor...")
    return reactor.run()
