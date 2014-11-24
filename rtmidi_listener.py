import rtmidi_python as rtmidi

import simple_logging as logging


class RtMidiListener(object):
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
