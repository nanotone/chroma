import os
import subprocess

import simple_logging as logging


class FluidSynth(object):
    def __init__(self):
        sounds = os.listdir('sounds/sf2')
        for sound in 'acoustic_grand_piano_ydp_20080910 acoustic_piano_imis_1 TimGM6mb FluidR3_GM'.split():
            sound = '%s.sf2' % sound
            if sound in sounds:
                logging.info("Using SoundFont file %s", sound)
                break
        else:
            if not sounds:
                raise IOError("No SoundFont files found in sounds/sf2")
            sound = sounds[0]
        self.proc = subprocess.Popen(['fluidsynth', 'sounds/sf2/%s' % sound], stdin=subprocess.PIPE)

    def emit(self, code, *args):
        if code == 0x90:
            cmd = 'noteon 0 %d %d' % tuple(args)
        elif code == 0x80:
            cmd = 'noteoff 0 %d' % args[0]
        elif code == 0xB0:
            cmd = 'cc 0 %d %d' % tuple(args)
        self.proc.stdin.write(cmd + '\n')

    def eof(self):
        self.proc.stdin.close()


def make_dst(arg):
    return FluidSynth()
