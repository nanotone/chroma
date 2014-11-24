import bisect
import time
import traceback

import rtmidi_python as rtmidi

from midi.MidiInFile import MidiInFile
from midi.MidiOutStream import MidiOutStream

import pipeutil
import rtmidi_listener
import simple_logging as logging

NOTE_OFF = 0x80
NOTE_ON = 0x90
DAMPER = 0xB0


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
        if controller in (0x40, 0x43):
            self.events.append((self.abs_time(), channel, DAMPER, controller, value))

    def tempo(self, value):
        self.tempi.append([self.abs_time(), value * self.quarters_per_tick])

    def sysex_event(self, *args):
        print "wat", args

    def eof(self):
        self.tempi.sort()
        self.events.sort()
        if not (self.tempi and self.tempi[0][0] == 0):
            logging.warning("No tempo found at tick=0 in MIDI file")
            self.tempi.insert(0, [0, 500000 * self.quarters_per_tick])  # 0.5 sec per quarter
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


def make_midi_dst(arg):
    if arg == '-':
        return pipeutil.StdoutSerializer()
    if ':' in arg:
        (scheme, arg) = arg.split(':', 1)
        if scheme == 'udp':
            addr = pipeutil.parse_addr(arg[2:])
            return pipeutil.UDPSerializer(addr)
        if scheme == 'fluid':
            import fluidsynth
            return fluidsynth.FluidSynth()
        if scheme == 'glclient':
            import glclient
            return glclient.GLClient()
        raise Exception("Unrecognized MIDI sink scheme " + scheme)
    return pipeutil.SMFWriter(arg)


def main(args):
    sinks = map(make_midi_dst, args.dst)
    def emit(*a, **k):
        for s in sinks[:]:
            try:
                s.emit(*a, **k)
            except Exception:
                traceback.print_exc()
                sinks.remove(s)
                if not sinks:
                    logging.warning("No more MIDI sinks!")
    try:
        if args.src == '-':
            pipeutil.run_stdin_deserializer(emit)
        elif ':' in args.src:
            (scheme, arg) = args.src.split(':', 1)
            if scheme == 'midi':
                rtmidi_listener.RtMidiListener(emit).run()
            elif scheme == 'udp':
                (hostname, port) = pipeutil.parse_addr(arg[2:])
                if hostname:
                    logging.warning("UDP source address should probably omit hostname")
                pipeutil.run_udpsock_deserializer((hostname, port), emit)
            else:
                raise Exception("Unrecognized MIDI source scheme " + scheme)
        else:
            SMFReader(args.src, emit).run()
    finally:
        for s in sinks: s.eof()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('src', help="- (stdin) | .mid file | midi: (realtime)")
    parser.add_argument('dst', nargs='*', help="- (stdout) | .mid file | udp://HOST | fluid:")
    main(parser.parse_args())
