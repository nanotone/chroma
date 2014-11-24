import argparse
import contextlib
import logging
import math
import re
import subprocess
import time
import threading

from OpenGL.GL import *
from OpenGL.GLU import *

import engine
import glfw_app
import pipeutil

HEXCOLORS = ['#40FF40', '#00FFFF', '#20A0FF', '#4080FF', # G C
             '#8060FF', '#C040E0', '#FF0080', '#FF0040', # B M
             '#FF4020', '#FF8000', '#FFFF00', '#80FF00'] # ROY
def rgb_from_hexcolor(hexcolor):
    return (int(hexcolor[1:3], 16) / 255.0, int(hexcolor[3:5], 16) / 255.0, int(hexcolor[5:7], 16) / 255.0)
RGB_COLORS = map(rgb_from_hexcolor, HEXCOLORS)

engine_lock = threading.Lock()

@contextlib.contextmanager
def translated(x, y, z):
    glPushMatrix()
    glTranslatef(x, y, z)
    yield
    glPopMatrix()

class Renderer(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.last_update = 0
        self.top_2nd_note_weight = 0.3
        self.visual_modes = "keyboard spiral".split()
        self.quadric = gluNewQuadric()

    def key_cb(self, window, key, scancode, action, mods):
        #print window, key, scancode, action, mods
        if key == glfw_app.glfw.KEY_SPACE and action == glfw_app.glfw.PRESS:
            self.set_viz((self.visual_modes.index(self.viz) + 1) % len(self.visual_modes))

    def set_viz(self, viz):
        if isinstance(viz, int):
            viz = self.visual_modes[viz]
        logging.info("Setting visualizer to '%s'", viz)
        self.viz = viz
        getattr(self, 'setup_' + viz)()

    def setup_keyboard(self):
        glMatrixMode(GL_PROJECTION)  # set viewing projection
        glLoadIdentity()
        gluOrtho2D(0.0, 1.0, 0.0, 1.0)
        glMatrixMode(GL_MODELVIEW)  # return to position viewer

    def setup_spiral(self):
        glMatrixMode(GL_PROJECTION)  # set viewing projection
        glLoadIdentity()
        ratio = float(self.width) / self.height
        gluOrtho2D(-ratio, ratio, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)  # return to position viewer

    def render_frame(self):
        render = getattr(self, 'render_' + self.viz)
        if render:
            render()

    def render_keyboard(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        with engine_lock:
            self.request_update()
            glBegin(GL_QUADS)
            for (midipitch, note) in midi_engine.notes.items():
                pitch = midipitch - 21
                color = self.get_note_color(midipitch, note)
                glColor3f(*color)
                (minx, maxx) = (pitch / 88.0, (pitch + 1) / 88.0)
                glVertex3f(minx, 0., 0.)
                glVertex3f(maxx, 0., 0.)
                glVertex3f(maxx, 1., 0.)
                glVertex3f(minx, 1., 0.)
            glEnd()

    def render_spiral(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        with engine_lock:
            self.request_update()
            pitches = set()
            for (midipitch, note) in midi_engine.notes.items():
                pitch = midipitch - 21
                color = self.get_note_color(midipitch, note)
                color = [0.05 + 0.95 * c for c in color]
                glColor3f(*color)
                self.draw_spiral_pitch(pitch)
                pitches.add(pitch)
            glColor3f(.05, .05, .05)
            for pitch in set(xrange(88)) - pitches:
                self.draw_spiral_pitch(pitch)

    def draw_spiral_pitch(self, pitch):
        # use a logarithmic spiral, discretized to circle of fifths
        theta = 2*math.pi * 5.03/12 * pitch  # skewed 5/12, so each pitch class also gets a slight spiral
        r = 1.3 * (0.97 ** pitch)
        r /= pitch / 88.0 + 1  # gradually make higher notes 2x closer/smaller
        size = r * 0.24
        with translated(r * math.cos(theta), r * math.sin(theta), 0):
            gluDisk(self.quadric, 0, size, 19, 1)

    def request_update(self):
        if midi_engine.notes_need_update or time.time() - self.last_update > 0.03:
            engine.tick()
            (cx, cy) = midi_engine.get_center()
            scale = 1.2 / (math.hypot(cx, cy) + 1)
            (cx, cy) = (scale * cx, scale * cy)
            for note in midi_engine.notes.itervalues():
                note.render_age = engine.now - note.start
                note.render_decay = math.exp(-note.render_age * 0.5) * note.damper_level
                note.render_pos = (note.pitch_coords[0] + cx, note.pitch_coords[1] + cy)
            elapsed = engine.now - self.last_update
            self.last_update = engine.now
            midi_engine.notes_need_update = False
            # now find second weightiest note
            note_weights = sorted(n.render_decay * n.volume for n in midi_engine.notes.itervalues())
            top_2nd_note_weight = (note_weights[-2:] + [0])[0]
            self.top_2nd_note_weight = max(self.top_2nd_note_weight * math.exp(-elapsed/5.0),
                                           top_2nd_note_weight, 0.3)

    def get_note_color(self, midipitch, note):
        r = math.hypot(*note.render_pos)
        (f, pc1) = math.modf(math.atan2(note.render_pos[1], note.render_pos[0]) / engine.PC_RADS + 12)
        pc1 = int(pc1)
        color = engine.weighted_avg_colors(RGB_COLORS[ pc1  % 12],
                                           RGB_COLORS[(pc1+1)%12],
                                           1 - f)
        if r < 1.0:
            color = engine.weighted_avg_colors(color, [0.75, 0.75, 0.75], r)
        # normalize weight to 2nd heaviest note, so top note gets voicing bonus
        weight = note.render_decay * note.volume / self.top_2nd_note_weight
        if weight < 1.0:
            # decay non-voiced notes slightly faster at attack-time
            color = [c * weight * math.exp(weight - 1) for c in color]
        else:
            color = [min(c + (1-c)*(weight-1)/0.4, 1) for c in color]
        return color


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
            logging.warning("Unhandled MIDI event", code, args)


def main(args):
    read_thread = threading.Thread(target=pipeutil.run_stdin_deserializer, args=(midi_cb,))
    read_thread.daemon = True
    read_thread.start()

    try:
        match = re.search(r'Resolution:\s*(\d+) [Xx] (\d+)',
                          subprocess.check_output(['system_profiler', 'SPDisplaysDataType']))
        (width, height) = [int(match.group(i)) for i in (1, 2)]
        logging.info("Creating GLFW app")
        app = glfw_app.GlfwApp("Chroma Key", width, height, args.fullscreen)
    except glfw_app.GlfwError as e:
        logging.error(e.message)
        return
    renderer = Renderer(width, height)
    renderer.set_viz('spiral')
    logging.info("Entering render loop")
    app.key_callbacks.append(renderer.key_cb)
    app.run(renderer.render_frame)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', help=":port (omit to use stdin)")
    parser.add_argument('--fullscreen', action='store_true')
    main(parser.parse_args())
