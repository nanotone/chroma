import os
import subprocess

class FluidSynth(object):
    def __init__(self):
        sounds = os.listdir('sounds/sf2')
        for sound in ('FluidR3_GM',):
            sound = '%s.sf2' % sound
            if sound in sounds:
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
            cmd = 'noteoff 0 %d' % tuple(args)
        elif code == 0xB0:
            cmd = 'cc 0 %d %d' % tuple(args)
        self.proc.stdin.write(cmd + '\n')

    def eof(self):
        self.proc.stdin.close()
