
import os
import socket
import struct
import psutil

from spyne import rpc, UnsignedInteger16, Unicode
from neurons.base.service import TReaderServiceBase


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


class DaemonServices(TReaderServiceBase()):
    @rpc(Unicode, UnsignedInteger16)
    def unlisten(self, host, port):
        pass
