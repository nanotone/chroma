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
        self.damp_start = 0
        self.damp_level = 1.0
        self.accum = 1.0

    def release_with_damper(self, damp_level):
        self.damp_level = damp_level
        self.accum += (now - self.start) * TIME_SCALE
        self.damp_start = now

    def set_damper(self, level):
        if self.damp_start and level < self.damp_level:
            self.accum += (now - self.damp_start) * TIME_SCALE * self.damp_level
            self.damp_level = level
            self.damp_start = now


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

    def get_active_note_pos(self, midipitch):
        note = self.notes[midipitch]
        age = (now - note.start) * TIME_SCALE
        elapsed = (now - note.damp_start) * TIME_SCALE if note.damp_start else age
        weight = math.exp(-age) * (note.accum + note.damp_level * elapsed) * note.volume
        return (note.pitch_coords[0] * weight, note.pitch_coords[1] * weight)

    def get_center(self):
        note_positions = [self.get_active_note_pos(midipitch) for midipitch in self.notes]
        (x, y) = map(sum, zip(*note_positions)) if note_positions else (0, 0)
        self.decay_reverb_center()
        (x, y) = (x + self.reverb_center[0], y + self.reverb_center[1])
        scale = math.log1p(math.hypot(x, y)) * 0.21
        return (scale * x, scale * y)

    def delete_note(self, midipitch):
        # add finished note to reverb
        note_pos = self.get_active_note_pos(midipitch)
        self.decay_reverb_center()
        self.reverb_center[0] += note_pos[0]
        self.reverb_center[1] += note_pos[1]
        del self.notes[midipitch]

    def damper(self, midipitch, state):
        state /= 127.0
        if state < self.damper_level:
            if state:
                for note in self.notes.itervalues():
                    note.set_damper(state)
            else:  # sec
                for (midipitch, note) in self.notes.items():
                    if note.damp_start:
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

    def update_notes(self):
        if now - self.notes_updated < 0.05 and not self.notes_need_update:
            return
        center = self.get_center()
        for (midipitch, note) in self.notes.iteritems():
            note.age = now - note.start
            note.decay = math.exp(-note.age * TIME_SCALE) * note.damp_level
            note.pos = (note.pitch_coords[0] + center[0],
                        note.pitch_coords[1] + center[1])
        self.notes_updated = now
        self.notes_need_update = False

