import math
import time


TIME_SCALE = 1/2.0  # takes 2 seconds for a note to decay e-fold

PC_RADS = 2 * math.pi / 12


def weighted_avg_colors(color1, color2, w1):
    return [w1*c1 + (1-w1)*c2 for (c1, c2) in zip(color1, color2)]

coords_for_pitch_class = {
    pitch_class: [math.cos(pitch_class * PC_RADS),
                  math.sin(pitch_class * PC_RADS)]
    for pitch_class in xrange(12)
}
def coords_for_midipitch(midipitch):
    return coords_for_pitch_class[midipitch * 7 % 12]


now = 0
def tick():
    global now
    newnow = time.time()
    if newnow - now > 0.01:
        now = newnow

class Note(object):
    def __init__(self, midipitch, volume):
        self.pitch_coords = coords_for_midipitch(midipitch)
        self.start = now      # when note_on happened
        self.volume = volume  # original volume. everything eventually gets multiplied by this
        self.damper_start = 0
        self.damper_level = 1.0
        self.accum = 1.0

    def release_with_damper(self, damper_level):
        self.damper_level = damper_level
        self.accum += (now - self.start) * TIME_SCALE
        self.damper_start = now

    def set_damper(self, level):
        if self.damper_start and level < self.damper_level:
            self.accum += (now - self.damper_start) * TIME_SCALE * self.damper_level
            self.damper_level = level
            self.damper_start = now

    def get_decayed_coords(self):
        total_age = (now - self.start) * TIME_SCALE
        if self.damper_start:
            elapsed = (now - self.damper_start) * TIME_SCALE
        else:
            elapsed = total_age
        weight = math.exp(-total_age) * (self.accum + self.damper_level * elapsed) * self.volume
        return (self.pitch_coords[0] * weight, self.pitch_coords[1] * weight)


class Engine(object):
    def __init__(self):
        self.notes = {}
        self.reverb_center = [0, 0]
        self.reverb_center_updated = 0
        self.damper_level = 0
        self.notes_updated = 0
        self.notes_need_update = False

    def decay_reverb_center(self):
        elapsed = now - self.reverb_center_updated
        if elapsed:
            decay_factor = math.exp(-elapsed * TIME_SCALE)
            self.reverb_center[0] *= decay_factor
            self.reverb_center[1] *= decay_factor
            self.reverb_center_updated = now

    def get_center(self):
        self.decay_reverb_center()
        coords = [note.get_decayed_coords() for note in self.notes.itervalues()] + [self.reverb_center]
        return map(sum, zip(*coords))

    def delete_note(self, midipitch):
        # add finished note to reverb
        note = self.notes.get(midipitch)
        if note:
            coords = note.get_decayed_coords()
            self.decay_reverb_center()
            self.reverb_center[0] += coords[0]
            self.reverb_center[1] += coords[1]
            del self.notes[midipitch]

    def damper(self, midipitch, state):
        state /= 127.0
        if state < self.damper_level:
            if state:
                for note in self.notes.itervalues():
                    note.set_damper(state)
            else:  # sec
                for (midipitch, note) in self.notes.items():
                    if note.damper_start:
                        self.delete_note(midipitch)
        self.damper_level = state

    def note_on(self, midipitch, state):
        state /= 127.0
        if midipitch in self.notes:
            self.delete_note(midipitch)
        self.notes[midipitch] = Note(midipitch, state)
        self.notes_need_update = True

    def note_off(self, midipitch, state=0):
        note = self.notes.get(midipitch)
        if note:
            if self.damper_level:
                note.release_with_damper(self.damper_level)
            else:
                self.delete_note(midipitch)

