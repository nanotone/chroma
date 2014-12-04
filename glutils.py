import contextlib

from OpenGL.GL import *

@contextlib.contextmanager
def translated(x=0, y=0, z=0):
    glPushMatrix()
    glTranslatef(x, y, z)
    yield
    glPopMatrix()

@contextlib.contextmanager
def scaled(x, y=None, z=None):
    if y is None: y = x
    if z is None: z = y
    glPushMatrix()
    glScalef(x, y, z)
    yield
    glPopMatrix()
