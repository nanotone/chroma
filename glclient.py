import argparse
import logging
import math
import re
import subprocess
import time
import threading

from OpenGL.GL import *

import engine
import glfw_app
import pipeutil

HEXCOLORS = ['#40FF40', '#00FFFF', '#20A0FF', '#4080FF', # G C
             '#8060FF', '#C040E0', '#FF0080', '#FF0040', # B M
             '#FF4020', '#FF8000', '#FFFF00', '#80FF00'] # ROY
def rgb_from_hexcolor(hexcolor):
    return (int(hexcolor[1:3], 16) / 255.0, int(hexcolor[3:5], 16) / 255.0, int(hexcolor[5:7], 16) / 255.0)
RGB_COLORS = map(rgb_from_hexcolor, HEXCOLORS)

def init_gl(width, height):
    glMatrixMode(GL_PROJECTION)  # set viewing projection
    glLoadIdentity()
    ratio = 1.0  #float(width) / height
    glOrtho(-ratio, ratio, -1.0, 1.0, 1.0, -1.0)
    glMatrixMode(GL_MODELVIEW)  # return to position viewer

engine_lock = threading.Lock()

class Renderer(object):
    def __init__(self):
        self.last_update = 0

    def render_frame(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()
        with engine_lock:
            if midi_engine.notes_need_update or time.time() - self.last_update > 0.05:
                engine.tick()
                (cx, cy) = midi_engine.get_center()
                scale = 1.2 / (math.hypot(cx, cy) + 1)
                (cx, cy) = (scale * cx, scale * cy)
                for note in midi_engine.notes.itervalues():
                    note.render_age = engine.now - note.start
                    note.render_decay = math.exp(-note.render_age * 0.5) * note.damper_level
                    note.render_pos = (note.pitch_coords[0] + cx, note.pitch_coords[1] + cy)
                self.notes_updated = engine.now
                midi_engine.notes_need_update = False
            glBegin(GL_QUADS)
            for (midipitch, note) in midi_engine.notes.items():
                pitch = midipitch - 21
                (minx, maxx) = (pitch / 44. - 1, (pitch + 1) / 44. - 1)
                r = math.hypot(*note.render_pos)
                (f, pc1) = math.modf(math.atan2(note.render_pos[1], note.render_pos[0]) / engine.PC_RADS + 12)
                pc1 = int(pc1)
                color = engine.weighted_avg_colors(RGB_COLORS[ pc1  % 12],
                                                   RGB_COLORS[(pc1+1)%12],
                                                   1 - f)
                if r < 1.0:
                    color = engine.weighted_avg_colors(color, [0.75, 0.75, 0.75], r)
                weight = note.render_decay * note.volume ** 0.3
                color = [min(c * weight, 1) for c in color]
                glColor3f(*color)
                glVertex3f(minx, -1., 0.)
                glVertex3f(maxx, -1., 0.)
                glVertex3f(maxx,  1., 0.)
                glVertex3f(minx,  1., 0.)
            glEnd()

midi_engine = engine.Engine()
def midi_cb(code, *args):
    engine.tick()
    with engine_lock:
        if code == 0x90 and args[1] == 0:  # sometimes note_off arrives as note_on with vel=0
            code = 0x80
        getattr(midi_engine, {0x80: 'note_off', 0x90: 'note_on', 0xB0: 'damper'}[code])(*args)


def main(args):
    if args.src:
        (hostname, port) = pipeutil.parse_addr(args.src, fill_localhost=False)
        if hostname:
            logging.error("Source address cannot specify hostname")
            return
        read_thread = threading.Thread(target=pipeutil.run_udpsock_deserializer, args=(port, midi_cb))
    else:
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
    init_gl(width, height)
    logging.info("Entering render loop")
    app.run(Renderer().render_frame)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', help=":port (omit to use stdin)")
    parser.add_argument('--fullscreen', action='store_true')
    main(parser.parse_args())
