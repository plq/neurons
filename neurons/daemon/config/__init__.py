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


FILE_VERSION_KEY = 'file_version'
STATIC_DESC_ROOT = "Directory that contains static files for the root url."
STATIC_DESC_URL = "Directory that contains static files for the url '%s'."


class ServiceDisabled(Exception):
    pass


from neurons.daemon.config._base import LOGLEVEL_MAP
from neurons.daemon.config._base import LOGLEVEL_MAP_ABB
from neurons.daemon.config._base import LOGLEVEL_STR_MAP
from neurons.daemon.config._base import ServiceDefinition

from neurons.daemon.config.endpoint import Service
from neurons.daemon.config.endpoint import Client
from neurons.daemon.config.endpoint import Server
from neurons.daemon.config.endpoint import SslServer
from neurons.daemon.config.endpoint import HttpServer
from neurons.daemon.config.endpoint import WsgiServer
from neurons.daemon.config.endpoint import HttpApplication
from neurons.daemon.config.endpoint import StaticFileServer

from neurons.daemon.config.store import FileStore
from neurons.daemon.config.store import LdapStore
from neurons.daemon.config.store import RelationalStore

from neurons.daemon.config.daemon import Daemon
from neurons.daemon.config.daemon import ServiceDaemon
from neurons.daemon.config.daemon import EmailAlert
from neurons.daemon.config.daemon import AlertDestination
