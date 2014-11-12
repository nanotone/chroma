import json
import socket
import sys


def parse_addr(addr, fill_localhost=True):
    try:
        (hostname, port) = addr.split(':')
        if fill_localhost and not hostname:
            hostname = '127.0.0.1'
        return (hostname, int(port))
    except ValueError:
        raise ValueError(addr + " does not look like an address")


def udpsock_serializer(addr):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    def emit(code, *args):
        sock.sendto(json.dumps([code] + list(args)), addr)
    return emit

def stdout_serializer():
    def emit(code, *args):
        sys.stdout.write(json.dumps([code] + list(args)) + '\n')
        sys.stdout.flush()
    return emit

def run_stdin_deserializer(cb):
    while True:
        data = sys.stdin.readline().strip()
        if data:
            args = json.loads(data)
            cb(*args)

def run_udpsock_deserializer(port, cb):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', port))
    while True:
        args = json.loads(sock.recv(1024))
        cb(*args)
