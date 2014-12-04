import argparse
import json
import math
import random
import re
import subprocess
import sys
import time
import threading

from OpenGL.GL import *
from OpenGL.GLU import *

import engine
import glfw_app
from glutils import *


# set up some color stuff

HEXCOLORS = ['#40FF40', '#00FFFF', '#20A0FF', '#4080FF', # G_C_
             '#8060FF', '#C040E0', '#FF0080', '#FF0040', # BvM_
             '#FF4020', '#FF8000', '#FFFF00', '#80FF00'] # RoY_
def rgb_from_hexcolor(hexcolor):
    return (int(hexcolor[1:3], 16) / 255.0, int(hexcolor[3:5], 16) / 255.0, int(hexcolor[5:7], 16) / 255.0)
RGB_COLORS = map(rgb_from_hexcolor, HEXCOLORS)

def weighted_avg_colors(color1, color2, w1):
    """interp from color1 to color2 as w1 goes from 0 to 1"""
    return [w1*c1 + (1-w1)*c2 for (c1, c2) in zip(color1, color2)]

def apply_whitening_bonus(color, weight):
    """apply linear bonus toward white as weight goes from 1 to 1.4"""
    return [min(1., c + (1-c)*(weight-1)/0.4) for c in color]


engine_lock = threading.Lock()

class Renderer(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.last_update = 0
        self.top_2nd_note_weight = 0.3
        self.visual_modes = "keyboard spiral firefly".split()
        self.quadric = gluNewQuadric()

    def key_cb(self, window, key, scancode, action, mods):
        #print window, key, scancode, action, mods
        if key == glfw_app.glfw.KEY_SPACE and action == glfw_app.glfw.PRESS:
            self.set_viz((self.visual_modes.index(self.viz) + 1) % len(self.visual_modes))

    def set_viz(self, viz):
        if isinstance(viz, int):
            viz = self.visual_modes[viz]
        print "Setting visualizer to '%s'" % viz
        self.viz = viz
        getattr(self, 'setup_' + viz)()
        self.last_render = time.time()

    def render_frame(self):
        now = time.time()
        self.frame_elapsed = now - self.last_render
        self.last_render = now
        render = getattr(self, 'render_' + self.viz)
        if render:
            render()

    def request_update(self):
        engine.tick()
        midi_engine.update()
        (cx, cy) = midi_engine.center
        scale = 1.2 / (math.hypot(cx, cy) + 1)
        (cx, cy) = (scale * cx, scale * cy)
        for note in midi_engine.notes.itervalues():
            note.render_age = engine.now - note.start
            note.render_decay = min(note.weight, 1.0)
            note.render_pos = (note.pitch_coords[0] + cx, note.pitch_coords[1] + cy)
        elapsed = engine.now - self.last_update
        self.last_update = engine.now
        midi_engine.notes_need_update = False
        # now find second weightiest note
        note_weights = sorted(n.render_decay * n.volume for n in midi_engine.notes.itervalues())
        top_2nd_note_weight = (note_weights[-2:] + [0])[0]
        self.top_2nd_note_weight = max(self.top_2nd_note_weight * math.exp(-elapsed/5.0),
                                       top_2nd_note_weight, 0.3)

    def get_note_color(self, note):
        r = math.hypot(*note.render_pos)
        (f, pc1) = math.modf(math.atan2(note.render_pos[1], note.render_pos[0]) / engine.PC_RADS + 12)
        pc1 = int(pc1)
        color = weighted_avg_colors(RGB_COLORS[ pc1  % 12], RGB_COLORS[(pc1+1)%12], 1 - f)
        if r < 1.0:
            color = weighted_avg_colors(color, [0.75, 0.75, 0.75], r)
        # normalize weight to 2nd heaviest note, so top note gets voicing bonus
        norm_weight = note.render_decay * note.volume / self.top_2nd_note_weight
        return (color, norm_weight)

    # keyboard
    def setup_keyboard(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, 88.0, 0.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def render_keyboard(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        with engine_lock:
            self.request_update()
            glBegin(GL_QUADS)
            for (midipitch, note) in midi_engine.notes.items():
                pitch = midipitch - 21
                (color, norm_weight) = self.get_note_color(note)
                if norm_weight > 1:
                    color = apply_whitening_bonus(color, norm_weight)
                    color.append(1)
                else:
                    color.append(norm_weight * math.exp(norm_weight - 1))
                glColor4f(*color)
                glVertex3f(pitch  , 0., 0.)
                glVertex3f(pitch+1, 0., 0.)
                glVertex3f(pitch+1, 1., 0.)
                glVertex3f(pitch  , 1., 0.)
            glEnd()

    # spiral
    def setup_spiral(self):
        ratio = float(self.width) / self.height
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(-ratio, ratio, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def render_spiral(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        glColor3f(.05, .05, .05)
        for pitch in xrange(88):
            self.draw_spiral_pitch(pitch)
        with engine_lock:
            self.request_update()
            for (midipitch, note) in midi_engine.notes.items():
                pitch = midipitch - 21
                (color, norm_weight) = self.get_note_color(note)
                if norm_weight > 1:
                    color = apply_whitening_bonus(color, norm_weight)
                    color.append(1)
                else:
                    color.append(norm_weight * math.exp(norm_weight - 1))
                glColor4f(*color)
                self.draw_spiral_pitch(pitch)

    def draw_spiral_pitch(self, pitch):
        # use a logarithmic spiral, discretized to circle of fifths
        theta = 2*math.pi * 5.03/12 * pitch  # skewed 5/12, so each pitch class also gets a slight spiral
        r = 1.3 * (0.97 ** pitch)
        r /= (pitch / 88.0 + 1)  # gradually make higher notes 2x closer/smaller
        size = r * 0.24
        with translated(r * math.cos(theta), r * math.sin(theta), 0):
            gluDisk(self.quadric, 0, size, 19, 1)

    # firefly
    def setup_firefly(self):
        ratio = float(self.width) / self.height
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, 88.0, 0.0, 88.0/ratio)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.notes = []  # make sure to render this in chronological order
        self.notes_by_midipitch = {n: [] for n in range(21, 109)}

    def render_firefly(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        with engine_lock:
            self.request_update()
            for note in midi_engine.notes.itervalues():
                if not hasattr(note, 'firefly'):
                    note.firefly = {
                        'pos': [note.midipitch - 21, 0, 0],
                        'xvel': random.triangular(-1, 1),
                        'yvel': random.triangular(-1, 1),
                        'color': self.get_note_color(note)[0],  # save initial color
                    }
                    self.notes.append(note)
                    prev_notes = self.notes_by_midipitch[note.midipitch]
                    if prev_notes:
                        for n in prev_notes[1:]:
                            n.weight *= prev_notes[0].weight
                    prev_notes.insert(0, note)
            for n in reversed(self.notes):
                color = n.firefly['color']
                pressed_note = self.notes_by_midipitch[n.midipitch][0]
                if n is pressed_note:
                    (_, norm_weight) = self.get_note_color(n)
                    if norm_weight > 1:
                        color = apply_whitening_bonus(color, norm_weight)
                    alpha = min(norm_weight, 1.0)
                else:
                    alpha = n.weight * pressed_note.weight
                color = color + [alpha ** 0.3]
                glColor4f(*color)
                with translated(*n.firefly['pos']):
                    gluDisk(self.quadric, 0, 4*n.volume**2, 19, 1)
        for n in self.notes:
            n.firefly['xvel'] += random.triangular(-0.5, 0.5) * self.frame_elapsed
            n.firefly['xvel'] = min(5, max(-5, n.firefly['xvel']))
            n.firefly['yvel'] += random.triangular(-0.5, 0.5) * self.frame_elapsed
            n.firefly['yvel'] = min(5, max(-5, n.firefly['yvel']))
            n.firefly['pos'][0] += n.firefly['xvel'] * self.frame_elapsed
            n.firefly['pos'][1] += (8 + n.firefly['yvel']) * self.frame_elapsed
        remove = [n for n in self.notes if n.firefly['pos'][1] > 88]
        for n in remove:
            self.notes.remove(n)
            self.notes_by_midipitch[n.midipitch].remove(n)


midi_engine = engine.Engine()
def midi_cb(code, *args):
    engine.tick()
    with engine_lock:
        if code == 0x90 and args[1] == 0:  # sometimes note_off arrives as note_on with vel=0
            code = 0x80
        func = getattr(midi_engine, {0x80: 'note_off', 0x90: 'note_on', 0xB0: 'damper'}[code], None)
        if func:
            func(*args)
        else:
            print "Unhandled MIDI event", code, args


def run():
    while True:
        data = sys.stdin.readline().strip()
        if data:
            args = json.loads(data)
            midi_cb(*args)


def main(args):
    read_thread = threading.Thread(target=run)
    read_thread.daemon = True
    read_thread.start()
    try:
        match = re.search(r'Resolution:\s*(\d+) [Xx] (\d+)',
                          subprocess.check_output(['system_profiler', 'SPDisplaysDataType']))
        (width, height) = [int(match.group(i)) for i in (1, 2)]
        print "Creating GLFW app"
        app = glfw_app.GlfwApp("Chromatics", width, height, args.fullscreen)
    except glfw_app.GlfwError as e:
        print "Error:", e.message
        return
    renderer = Renderer(width, height)
    renderer.set_viz('firefly')
    print "Entering render loop"
    app.key_callbacks.append(renderer.key_cb)
    app.run(renderer.render_frame)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--fullscreen', action='store_true')
    main(parser.parse_args())
