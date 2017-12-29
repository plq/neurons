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

import os
import socket
import struct
import psutil

from spyne import rpc, UnsignedInteger16, Unicode
from neurons.base.service import TReaderService


def _gen_addr(base, num):
    # port numbers should never fall below 1024.
    mgmt_addr = base + num + 1024 * (num // 0xfc00)

    return (
        socket.inet_ntoa(struct.pack('!L', mgmt_addr >> 16)),
        mgmt_addr & 0xffff,
    )


MGMT_ADDR_BASE =   0x7f0100010400 # 127.1.0.1:1024
DOWSER_ADDR_BASE = 0x7f0101010400 # 127.1.1.1:1024


def get_dowser_address_for_pid(pid):
    """Computes dowser service address from process id.

    Returns a tuple containing the computed host as string and the port as int.
    """
    return _gen_addr(DOWSER_ADDR_BASE, pid)


def get_own_dowser_address():
    return get_dowser_address_for_pid(os.getpid())


def get_mgmt_address_for_pid(pid):
    """Computes management service address from process id.

    Returns a tuple containing the computed host as string and the port as int.
    """
    return _gen_addr(MGMT_ADDR_BASE, pid)


def get_mgmt_address_for_tcp_port(port):
    """Gets management service address from a tcp port.

    Returns a tuple containing the computed host as string and the port as int.
    """

    pid = None

    for conn in psutil.net_connections():
        if conn.status != 'LISTEN':
            continue

        h, p = conn.laddr
        if p == port:
            pid = conn.pid
            break

    if pid is not None:
        return get_mgmt_address_for_pid(pid)

    return None, None


def get_own_mgmt_address():
    return get_mgmt_address_for_pid(os.getpid())


class DaemonServices(TReaderService()):
    @rpc(Unicode, UnsignedInteger16)
    def unlisten(self, host, port):
        pass
