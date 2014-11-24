import json
import socket

import simple_logging as logging


def parse_addr(addr):
    try:
        (hostname, port) = addr.split(':')
        return (hostname, int(port))
    except ValueError:
        raise ValueError(addr + " does not look like an address")


class UDPSerializer(object):
    def __init__(self, addr):
        (hostname, port) = addr
        if not hostname:
            hostname = 'localhost'
        self.addr = (hostname, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    def emit(self, code, *args):
        self.sock.sendto(json.dumps([code] + list(args)), self.addr)
    def eof(self):
        pass


def run_src(arg, emit):
    (hostname, port) = parse_addr(arg)
    if hostname:
        logging.warning("UDP source address should probably omit hostname")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((hostname, port))
    while True:
        args = json.loads(sock.recv(1024))
        emit(*args)

def make_dst(arg):
    return UDPSerializer(parse_addr(arg))
