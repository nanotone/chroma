import json
import socket
import sys
import time

from midi.MidiOutFile import MidiOutFile


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

class StdoutSerializer(object):
    def emit(self, code, *args):
        sys.stdout.write(json.dumps([code] + list(args)) + '\n')
        sys.stdout.flush()
    def eof(self):
        pass

class SMFWriter(object):
    def __init__(self, path, division=96):
        self.path = path
        self.events = []
        self.starttime = time.time()
        self.division = division
        with open(self.path, 'w') as f:  # complain early if path isn't writable
            pass

    def emit(self, code, *args):
        self.events.append({'code': code, 'args': args, 'time': time.time()})

    def eof(self):
        mof = MidiOutFile(self.path)
        mof.header(division=self.division)
        mof.start_of_track()
        tick = 0
        for e in self.events:
            tstamp = e['time'] - self.starttime
            next_tick = int(tstamp * 2 * self.division)
            mof.update_time(next_tick - tick)
            tick = next_tick
            if e['code'] == 0x90:
                #e['args'][1] /= 2  # garageband
                mof.note_on(note=e['args'][0], velocity=e['args'][1])
            elif e['code'] == 0x80:
                mof.note_off(note=e['args'][0])
            elif e['code'] == 0xB0:
                #e['args'][0] /= 4  # garageband
                mof.continuous_controller(channel=0, controller=e['args'][0], value=e['args'][1])
        mof.update_time(self.division)
        mof.end_of_track()
        mof.eof()


def run_stdin_deserializer(cb):
    while True:
        data = sys.stdin.readline().strip()
        if data:
            args = json.loads(data)
            cb(*args)

def run_udpsock_deserializer(addr, cb):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(addr)
    while True:
        args = json.loads(sock.recv(1024))
        cb(*args)
