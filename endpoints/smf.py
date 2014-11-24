import bisect
import time

from pythonmidi.MidiInFile import MidiInFile
from pythonmidi.MidiOutFile import MidiOutFile
from pythonmidi.MidiOutStream import MidiOutStream

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


def run_src(arg, emit):
    SMFReader(arg, emit).run()

def make_dst(arg):
    return SMFWriter(arg)
