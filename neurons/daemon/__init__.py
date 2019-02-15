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

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERR_UNKNOWN = 1
# EXIT_SIGNAL = 100
EXIT_ERR_MEMORY = 201
EXIT_ERR_LISTEN_TCP = 100000
EXIT_ERR_LISTEN_UDP = 200000


from neurons.daemon import dowser
from neurons.daemon.main import main

from neurons.daemon.config import Service
from neurons.daemon.config import Client
from neurons.daemon.config import Server
from neurons.daemon.config import SslServer
from neurons.daemon.config import HttpServer
from neurons.daemon.config import WsgiServer
from neurons.daemon.config import ServiceDaemon
from neurons.daemon.config import HttpApplication
from neurons.daemon.config import StaticFileServer

from neurons.daemon.config import FileStore
from neurons.daemon.config import LdapStore
from neurons.daemon.config import RelationalStore

from neurons.daemon.config import Daemon
from neurons.daemon.config import ServiceDaemon
from neurons.daemon.config import EmailAlert
from neurons.daemon.config import AlertDestination

from neurons.daemon.config import ServiceDefinition


config_data = None
"""The last parsed ``Daemon`` instance."""
