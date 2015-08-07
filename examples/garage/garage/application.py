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

from os.path import abspath

from spyne import Application
from spyne.protocol.html import HtmlMicroFormat
from spyne.protocol.http import HttpRpc

from twisted.internet import reactor

from neurons.daemon.config import HttpListener, StaticFileServer

from garage.const import T_INDEX
from garage.service import GarageService


def start_garage(config):
    subconfig = config.services.getwrite('http', HttpListener(
        host='0.0.0.0',
        port=7111,
        disabled=False,
        _subapps=[StaticFileServer(url='assets', path=abspath('assets'),
                                                          list_contents=False)],
    ))

    subconfig.subapps[''] = \
        Application([GarageService], 'garage.main',
                in_protocol=HttpRpc(validator='soft'),
                out_protocol=HtmlMicroFormat(cloth=T_INDEX)
            )

    logger.info("listening for garage http on %s:%d",
                                                 subconfig.host, subconfig.port)

    return reactor.listenTCP(subconfig.port, subconfig.gen_site(),
                                                 interface=subconfig.host), None
