#!/usr/bin/env python

import argparse
import json
import math
import random
import re
import subprocess
import sys
import time
import threading

import numpy
from OpenGL.GL import *
#from OpenGL.GL import shaders
from OpenGL.GLU import *
from OpenGL.arrays import vbo

import engine
import glfw_app
from glutils import *


# set up some color stuff

HEXCOLORS = ['#40FF40', '#00FFFF', '#20A0FF', '#4080FF', # G_C_
             '#8060FF', '#C040E0', '#FF0080', '#FF0040', # BvM_
             '#FF4020', '#FF8000', '#FFFF00', '#80FF00'] # RoY_
def rgb_from_hexcolor(hexcolor):
    return (int(hexcolor[1:3], 16) / 255.0, int(hexcolor[3:5], 16) / 255.0, int(hexcolor[5:7], 16) / 255.0)
RGB_COLORS = [rgb_from_hexcolor(c) for c in HEXCOLORS]

def weighted_avg_colors(color1, color2, w1):
    """interp from color1 to color2 as w1 goes from 0 to 1"""
    return [w1*c1 + (1-w1)*c2 for (c1, c2) in zip(color1, color2)]

def apply_whitening_bonus(color, weight):
    """apply linear bonus toward white as weight goes from 1 to 1.4"""
    return [min(1., c + (1-c)*(weight-1)/0.4) for c in color]


def make_array_buffer(array):
    return vbo.VBO(numpy.array(array, dtype=numpy.float32), target=GL_ARRAY_BUFFER)
def make_index_buffer(array):
    return vbo.VBO(numpy.array(array, dtype=numpy.int32), target=GL_ELEMENT_ARRAY_BUFFER)


engine_lock = threading.Lock()


class KeyboardViz(object):
    def __init__(self, scope):
        self.scope = scope
        self.verts = make_array_buffer([
            [-.4, 0, 0], [.4, 0, 0], [.4, 1, 0], [-.4, 1, 0],
            [-.7, 0, 0], [.7, 0, 0], [.7, 1, 0], [-.7, 1, 0],
        ])
        self.colors = make_array_buffer([[1,1,1,1]] * 4 + [[1,1,1,0]] * 4)
        self.indices = make_index_buffer([[0, 1, 2, 3], [4, 0, 3, 7], [1, 5, 6, 2]])

    def setup(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0.0, 88.0, 0.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        with engine_lock:
            self.scope.request_update()
            for (midipitch, note) in midi_engine.notes.items():
                pitch = midipitch - 21
                (color, norm_weight) = self.scope.get_note_color(note)
                if norm_weight > 1:
                    color = apply_whitening_bonus(color, norm_weight)
                alpha = min(1.0, norm_weight) ** 1.5
                for i in range(3):
                    self.colors.data[:,i].fill(color[i])
                self.colors.data[:4,3].fill(alpha)
                self.colors.set_array(self.colors.data)
                with translated(pitch + 0.5, 0, 0):
                    size = min(1.0, max(1.0, norm_weight) * note.weight ** 0.5)
                    with scaled(size, 1.0, 1.0):
                        with self.verts:
                            glVertexPointer(3, GL_FLOAT, 0, self.verts)
                        with self.colors:
                            glColorPointer(4, GL_FLOAT, 0, self.colors)
                        with self.indices:
                            #glEnableVertexAttribArray(0)
                            #glVertexAttribPointer(0, 3, GL_FLOAT, False, 0, None)
                            glDrawElements(GL_QUADS, 12, GL_UNSIGNED_INT, None)


class SpiralViz(object):
    def __init__(self, scope):
        self.scope = scope
        self.quadric = gluNewQuadric()

    def setup(self):
        ratio = float(self.scope.width) / self.scope.height
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(-ratio, ratio, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_COLOR_ARRAY)

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        glColor3f(0.07, 0.07, 0.07)
        for pitch in range(88):
            self.draw_spiral_pitch(pitch)
        with engine_lock:
            self.scope.request_update()
            for (midipitch, note) in midi_engine.notes.items():
                if not hasattr(note, 'spiral'):
                    note.spiral = {
                        'prev_weight': 1.0,
                        'components': [0, 0, 0],  # dry, mid, wet
                        'inner': 0,
                    }
                dweight = note.spiral['prev_weight'] - note.weight
                if note.pedal < 0.25:
                    pro = (note.pedal / 0.25) * 0.9 + 0.1
                    comp_weights = [1 - pro, pro, 0]
                else:
                    pro = (note.pedal - 0.25) / 0.75 * 0.9
                    comp_weights = [0, 1 - pro, pro]
                if note.spiral['inner']:
                    comp_weights[0] += 1
                else:
                    comp_weights[0] *= note.weight ** 2
                comp_total = sum(comp_weights)
                for (i, comp_weight) in enumerate(comp_weights):
                    note.spiral['components'][i] += dweight * comp_weight / comp_total
                note.spiral['prev_weight'] = note.weight

                comp_sum = sum(note.spiral['components'])
                if comp_sum:
                    log_weight = math.log(note.weight)
                    (dry, mid, wet) = [math.exp(log_weight * comp / comp_sum) for comp in note.spiral['components']]
                else:
                    (dry, mid, wet) = (1, 1, 1)

                (color, norm_weight) = self.scope.get_note_color(note)
                if norm_weight > 1:
                    color = apply_whitening_bonus(color, norm_weight)
                    color.append(1)
                else:
                    color.append(norm_weight * math.exp(norm_weight - 1))
                glColor4f(*color)
                size = mid * (1.0 + (note.weight * note.volume)**3)
                inner = 0 if dry > 0.67 else 1 - dry/3
                note.spiral['inner'] = inner
                self.draw_spiral_pitch(midipitch - 21, inner=size * inner, outer=size, nice_slices=True)

    def draw_spiral_pitch(self, pitch, inner=0.0, outer=1.0, nice_slices=False):
        # use a logarithmic spiral, discretized to circle of fifths
        theta = 2*math.pi * 5.03/12 * pitch  # skewed 5/12, so each pitch class also gets a slight spiral
        r = 1.3 * (0.97 ** pitch)
        r /= (pitch / 88.0 + 1)  # gradually make higher notes 2x closer/smaller
        size = r * 0.24
        slices = int(60 - 10 * math.log(pitch + 10))
        if not nice_slices:
            slices = min(19, slices)
        with translated(r * math.cos(theta), r * math.sin(theta), 0):
            with scaled(size):
                gluDisk(self.quadric, inner, outer, slices, 1)


class FireflyViz(object):
    def __init__(self, scope):
        self.scope = scope
        self.quadric = gluNewQuadric()
        anglestep = 2*math.pi/19
        self.verts = make_array_buffer(
            [[math.cos(i*anglestep)*.5, math.sin(i*anglestep)*.5, 0] for i in range(19)]  # inner ring
          + [[math.cos(i*anglestep)   , math.sin(i*anglestep)   , 0] for i in range(19)]  # outer ring
          + [[0, 0, 0]])
        self.colors = make_array_buffer([[1, 1, 1, 0]] * 39)
        self.indices = make_index_buffer(
            [[38, i, (i+1)%19] for i in range(19)]  # inner layer
          + [[i, i+19, (i+1)%19+19] for i in range(19)]  # outer layer part 1
          + [[i, (i+1)%19+19, (i+1)%19] for i in range(19)]  # outer layer part 2
        )

    def setup(self):
        ratio = float(self.scope.width) / self.scope.height
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        self.height = 88.0 / ratio
        gluOrtho2D(0.0, 88.0, 0.0, self.height)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)

        self.notes = []  # make sure to render this in chronological order
        self.notes_by_midipitch = {n: [] for n in range(21, 109)}
        self.note_density = 0

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        with engine_lock:
            self.scope.request_update()
            for note in midi_engine.notes.values():
                if not hasattr(note, 'firefly'):
                    note.firefly = {
                        'pos': [note.midipitch - 21, 0, 0],
                        'xvel': random.triangular(-1, 1),
                        'yvel': random.triangular(-1, 1),
                        'size': 8 * note.volume**2.5 + 0.5,
                    }
                    self.notes.append(note)
                    prev_notes = self.notes_by_midipitch[note.midipitch]
                    if prev_notes:
                        for n in prev_notes[1:]:
                            n.weight *= prev_notes[0].weight
                    prev_notes.insert(0, note)
                    self.note_density += 1
            for n in reversed(self.notes):
                (color, norm_weight) = self.scope.get_note_color(n)
                pressed_note = self.notes_by_midipitch[n.midipitch][0]
                if n is pressed_note:
                    if norm_weight > 1:
                        color = apply_whitening_bonus(color, norm_weight)
                    alpha = min(norm_weight, 1.0)
                else:
                    alpha = n.weight * pressed_note.weight
                for i in range(3):
                    self.colors.data[:38,i].fill(color[i])
                remaining = max(0.001, 1 - n.firefly['pos'][1] / self.height)
                self.colors.data[:19,3].fill(alpha**0.33/3)#(alpha ** 0.33 + remaining) / 2)
                #self.colors.data[19:38,3].fill(0)#(alpha ** 0.5 * 0.1 + remaining**3) / 5)
                self.colors.data[38,3] = alpha ** 0.33 * 0.25 + 0.75
                self.colors.set_array(self.colors.data)
                with translated(*n.firefly['pos']):
                    with scaled(n.firefly['size'] * (remaining * max(0.05, alpha))**0.1):
                        with self.verts:
                            glVertexPointer(3, GL_FLOAT, 0, self.verts)
                        with self.colors:
                            glColorPointer(4, GL_FLOAT, 0, self.colors)
                        with self.indices:
                            glDrawElements(GL_TRIANGLES, 3*3*19, GL_UNSIGNED_INT, None)
        elapsed = self.scope.frame_elapsed
        self.note_density *= math.exp(-elapsed)  # ranges from 0 to 20
        for n in self.notes:
            n.firefly['xvel'] += random.triangular(-0.5, 0.5) * elapsed
            n.firefly['xvel'] = min(5, max(-5, n.firefly['xvel']))
            n.firefly['yvel'] += random.triangular(-0.5, 0.5) * elapsed
            n.firefly['yvel'] = min(5, max(-5, n.firefly['yvel']))
            n.firefly['pos'][0] += n.firefly['xvel'] * elapsed
            n.firefly['pos'][1] += (4 + 2.5*math.log1p(self.note_density) + n.firefly['yvel']) * elapsed
        remove = [n for n in self.notes if n.firefly['pos'][1] - n.firefly['size'] > self.height]
        for n in remove:
            self.notes.remove(n)
            self.notes_by_midipitch[n.midipitch].remove(n)


class Renderer(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.last_update = 0
        self.top_2nd_note_weight = 0.3
        self.visual_modes = "keyboard spiral firefly".split()
        self.visualizers = {
            'keyboard': KeyboardViz(self),
            'spiral': SpiralViz(self),
            'firefly': FireflyViz(self),
        }
        self.quadric = gluNewQuadric()
        self.events = []

    def key_cb(self, window, key, scancode, action, mods):
        #print window, key, scancode, action, mods
        if key == glfw_app.glfw.KEY_SPACE and action == glfw_app.glfw.PRESS:
            self.events.append('switch_viz')

    def set_viz(self, viz):
        if isinstance(viz, int):
            viz = self.visual_modes[viz]
        print("Setting visualizer to '{}'".format(viz))
        self.viz = viz
        self.visualizers[viz].setup()
        self.last_render = time.time()

    def render_frame(self):
        if self.events:
            for event in self.events:
                if event == 'switch_viz':
                    self.set_viz((self.visual_modes.index(self.viz) + 1) % len(self.visual_modes))
            self.events = []
        now = time.time()
        self.frame_elapsed = now - self.last_render
        self.last_render = now
        self.visualizers[self.viz].render()

    def request_update(self):
        engine.tick()
        midi_engine.update()
        (cx, cy) = midi_engine.center
        scale = 1.2 / (math.hypot(cx, cy) + 1)
        (self.cx, self.cy) = (scale * cx, scale * cy)
        for note in midi_engine.notes.values():
            note.render_decay = min(note.weight, 1.0)
        elapsed = engine.now - self.last_update
        self.last_update = engine.now
        midi_engine.notes_need_update = False
        # now find second weightiest note
        note_weights = sorted(n.render_decay * n.volume for n in midi_engine.notes.values())
        top_2nd_note_weight = (note_weights[-2:] + [0])[0]
        self.top_2nd_note_weight = max(self.top_2nd_note_weight * math.exp(-elapsed/5.0),
                                       top_2nd_note_weight, 0.3)

    def get_note_color(self, note):
        render_pos = (note.pitch_coords[0] + self.cx, note.pitch_coords[1] + self.cy)
        r = math.hypot(*render_pos)
        (f, pc1) = math.modf(math.atan2(render_pos[1], render_pos[0]) / engine.PC_RADS + 12)
        pc1 = int(pc1)
        color = weighted_avg_colors(RGB_COLORS[ pc1  % 12], RGB_COLORS[(pc1+1)%12], 1 - f)
        if r < 1.0:
            color = weighted_avg_colors(color, [0.75, 0.75, 0.75], r)
        # normalize weight to 2nd heaviest note, so top note gets voicing bonus
        norm_weight = note.render_decay * note.volume / self.top_2nd_note_weight
        return (color, norm_weight)


midi_engine = engine.Engine()

def run():
    while True:
        data = sys.stdin.readline().strip()
        if data:
            args = json.loads(data)
            engine.tick()
            with engine_lock:
                func = getattr(midi_engine, {0x80: 'note_off', 0x90: 'note_on', 0xB0: 'damper'}[args[0]], None)
                if func:
                    func(*args[1:])
                else:
                    print("Unhandled MIDI event", args)
            if args[0] == 0xB0 and args[1] == 0x42 and args[2] == 0:
                renderer.events.append('switch_viz')



def main(args):
    global renderer
    read_thread = threading.Thread(target=run)
    read_thread.daemon = True
    read_thread.start()
    try:
        match = re.search(r'Resolution:\s*(\d+) [Xx] (\d+)(.*)',
                          subprocess.check_output(['system_profiler', 'SPDisplaysDataType']).decode('ascii'))
        (width, height) = [int(match.group(i)) for i in (1, 2)]
        if 'Retina' in match.group(3):
            width //= 2
            height //= 2
        print("Creating GLFW app")
        app = glfw_app.GlfwApp("Chromatics", width, height, args.fullscreen)
    except glfw_app.GlfwError as e:
        print("Error:", e.message)
        return
    renderer = Renderer(width, height)
    renderer.set_viz('keyboard')
    print("Entering render loop")
    app.key_callbacks.append(renderer.key_cb)
    app.run(renderer.render_frame)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--fullscreen', action='store_true')
    main(parser.parse_args())
