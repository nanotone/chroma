import math
import time


TIME_SCALE = 1/2.0  # takes 2 seconds for a note to decay e-fold

PC_RADS = 2 * math.pi / 12

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
        self.midipitch = midipitch
        self.volume = volume  # original volume. everything eventually gets multiplied by this
        self.pitch_coords = coords_for_midipitch(midipitch)
        self.start = now      # when note_on happened
        self.released = False
        self.audible = True
        self.pedal = 1.0
        self.weight = 1.0
        self.max_sustain = 25 * 0.8 ** ((midipitch - 12) / 12.0)
        self.min_sustain = 0.75
        self.decayed_weight = volume  # integral of Dirac delta over [0, eps]
        self.last_decay = now

    def release_with_pedal(self, pedal):
        self.released = True
        self.pedal = pedal

    def set_pedal(self, pedal):
        if self.released:
            self.pedal = pedal

    def get_decayed_coords(self):
        elapsed = now - self.last_decay
        if elapsed:
            if self.audible:
                sustain = self.min_sustain + (self.max_sustain - self.min_sustain) * self.pedal
                self.weight *= 0.002 ** (elapsed / sustain)
                amplitude = self.weight * self.volume
                self.decayed_weight += elapsed * amplitude
                if amplitude < 0.001:
                    self.audible = False
            self.decayed_weight *= math.exp(-elapsed * TIME_SCALE)
            self.last_decay = now
        return (self.pitch_coords[0] * self.decayed_weight, self.pitch_coords[1] * self.decayed_weight)


class Engine(object):
    def __init__(self):
        self.notes = {}
        self.reverb_center = [0, 0]
        self.reverb_center_updated = 0
        self.pedal = 0
        self.notes_updated = 0
        self.notes_need_update = False

    def decay_reverb_center(self):
        elapsed = now - self.reverb_center_updated
        if elapsed:
            decay_factor = math.exp(-elapsed * TIME_SCALE)
            self.reverb_center[0] *= decay_factor
            self.reverb_center[1] *= decay_factor
            self.reverb_center_updated = now

    def update(self):
        self.decay_reverb_center()
        coords = [self.reverb_center]
        inaudible_notes = []
        for note in self.notes.itervalues():
            coords.append(note.get_decayed_coords())
            if not note.audible:
                inaudible_notes.append(note)
        self.center = map(sum, zip(*coords))
        for note in inaudible_notes:
            self.delete_note(note)

    def delete_note(self, note):
        # add finished note to reverb
        coords = note.get_decayed_coords()
        self.decay_reverb_center()
        self.reverb_center[0] += coords[0]
        self.reverb_center[1] += coords[1]
        del self.notes[note.midipitch]

    def damper(self, controller, state):
        if controller != 0x40:
            return  # only handle sustain pedal for now
        state /= 127.0
        for note in self.notes.itervalues():
            note.set_pedal(state)
        self.pedal = state

    def note_on(self, midipitch, state):
        state /= 127.0
        note = self.notes.get(midipitch)
        if note:
            self.delete_note(note)
        self.notes[midipitch] = Note(midipitch, state)
        self.notes_need_update = True

    def note_off(self, midipitch, state=0):
        note = self.notes.get(midipitch)
        if note:
            note.release_with_pedal(self.pedal)

