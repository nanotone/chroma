import bisect
import json
import socket
import sys
import time

import rtmidi_python as rtmidi

from midi.MidiInFile import MidiInFile
from midi.MidiOutStream import MidiOutStream

import pipeutil

NOTE_OFF = 0x80
NOTE_ON = 0x90
DAMPER = 0xB0

class RtMidiListener(object):
    def __init__(self, emit):
        self.emit = emit
        self.mi = rtmidi.MidiIn()
        ports = self.mi.ports
        if not ports:
            print "No MIDI input ports found"
            sys.exit()
        if len(ports) == 1:
            idx = 0
            print "Choosing MIDI input port", ports[0]
        else:
            print "MIDI input ports:"
            for (idx, name) in enumerate(ports):
                print "%s. %s" % (idx, name)
            idx = int(raw_input("Which MIDI input port? "))
            assert 0 <= idx < len(ports)
        self.mi.open_port(idx)

    def run(self):
        while True:
            (message, delta_time) = self.mi.get_message()
            if message:
                self.emit(*message)


class SMFReader(MidiOutStream):
    def __init__(self, smf_path, emit):
        MidiOutStream.__init__(self)
        self.quarters_per_tick = 1.0 / 96
        self.events = []
        self.tempi = []
        MidiInFile(self, smf_path).read()
        self.emit = emit

    def header(self, format=0, nTracks=1, division=96):
        self.quarters_per_tick = 1.0 / division

    def note_on(self, channel=0, note=0x40, velocity=0x40):
        if velocity:
            self.events.append((self.abs_time(), channel, NOTE_ON, note, velocity))
        else:
            self.events.append((self.abs_time(), channel, NOTE_OFF, note))

    def note_off(self, channel=0, note=0x40, velocity=0x40):
        self.events.append((self.abs_time(), channel, NOTE_OFF, note))

    def continuous_controller(self, channel, controller, value):
        if controller == 0x40:
            self.events.append((self.abs_time(), channel, DAMPER, value))

    def tempo(self, value):
        self.tempi.append([self.abs_time(), value * self.quarters_per_tick])

    def sysex_event(self, *args):
        print "wat", args

    def eof(self):
        self.tempi.sort()
        self.events.sort()
        assert self.tempi[0][0] == 0, "No tempo found at tick=0 in MIDI file"
        (prev_tick, prev_time, micros_per_tick) = (0, 0, 0)
        for tempo in self.tempi:
            tick = tempo[0]
            cur_time = prev_time + (tick - prev_tick) * micros_per_tick
            tempo.append(cur_time)
            prev_tick = tick
            micros_per_tick = tempo[1]
            prev_time = cur_time

    def get_time(self, abs_tick):
        idx = bisect.bisect_right(self.tempi, [abs_tick])
        if idx:
            tempo = self.tempi[idx - 1]
            return (tempo[2] + (abs_tick - tempo[0]) * tempo[1]) * 0.000001
        else:
            return 0

    def run(self):
        now = start_time = time.time()
        for event in self.events:
            t = self.get_time(event[0])
            wait = t - (now - start_time)
            if wait > 0:
                time.sleep(wait)
                now = time.time()
            self.emit(event[2], *event[3:])


def main(args):
    sinks = []
    for dst in args.dst:
        if dst == '-':
            sinks.append(pipeutil.StdoutSerializer())
        elif ':' in dst:
            addr = pipeutil.parse_addr(dst)
            sinks.append(pipeutil.UDPSerializer(addr))
        else:
            sinks.append(pipeutil.SMFWriter(dst))
    def emit(*a, **k):
        for s in sinks: s.emit(*a, **k)
    if args.src == '-':
        runner = RtMidiListener(emit)
    else:
        runner = SMFReader(args.src, emit)
    try:
        runner.run()
    finally:
        for s in sinks: s.eof()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('src', help=".mid path OR - (for realtime MIDI)")
    parser.add_argument('dst', nargs='*', help="[hostname]:port OR .mid path OR - (for stdout)")
    main(parser.parse_args())
