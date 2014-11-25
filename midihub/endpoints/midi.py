import rtmidi_python as rtmidi

import simple_logging as logging


class RtMidiIn(object):
    def __init__(self, emit):
        self.emit = emit
        self.mi = rtmidi.MidiIn()
        ports = self.mi.ports
        if not ports:
            raise IndexError("No MIDI input ports found")
        if len(ports) == 1:
            idx = 0
            logging.info("Choosing MIDI input port %s", ports[0])
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

class RtMidiOut(object):
    def __init__(self): #, emit):
        #self.emit = emit
        self.mo = rtmidi.MidiOut()
        ports = self.mo.ports
        if not ports:
            raise IndexError("No MIDI output ports found")
        if len(ports) == 1:
            idx = 0
            logging.info("Choosing MIDI output port %s", ports[0])
        else:
            print "MIDI output ports:"
            for (idx, name) in enumerate(ports):
                print "%s. %s" % (idx, name)
            idx = int(raw_input("Which MIDI output port? "))
            assert 0 <= idx < len(ports)
        self.mo.open_port(idx)

    def emit(self, code, *args):
        self.mo.send_message([code] + list(args))

    def eof(self):
        pass


def run_src(arg, emit):
    RtMidiIn(emit).run()

def make_dst(arg):
    return RtMidiOut()
