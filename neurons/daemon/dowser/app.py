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

from neurons import Application
from neurons.daemon.config import HttpListener, StaticFileServer
from neurons.daemon.dowser.const import ASSETS_DIR
from neurons.daemon.dowser.service import DowserServices

from spyne import Double
from spyne.protocol.html import HtmlBase
from spyne.protocol.http import HttpRpc


class DowserListener(HttpListener):
    tick_period_sec = Double(default=60)


def start_dowser(config):
    from twisted.internet import reactor
    from twisted.internet.task import LoopingCall
    from twisted.internet.threads import deferToThread
    from neurons.daemon.ipc import get_own_dowser_address

    host, port = get_own_dowser_address()

    subconfig = config.services.getwrite('dowser', DowserListener(
        host=None, port=None,
        disabled=False,
        _subapps=[StaticFileServer(url='assets', path=ASSETS_DIR,
                               list_contents=False, disallowed_exts=["py"])],
    ))

    subconfig.subapps[''] = \
        Application(
            [
                DowserServices,
            ],
            tns='neurons.daemon', name='Dowser',
            in_protocol=HttpRpc(validator='soft'),
            out_protocol=HtmlBase(),
            config=config,
        )

    site = subconfig.gen_site()

    task = LoopingCall(deferToThread, DowserServices.tick)
    task.start(subconfig.tick_period_sec)

    logger.info("listening for dowser on %s:%d", host, port)
    return reactor.listenTCP(port, site, interface=host), None
