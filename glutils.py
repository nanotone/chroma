import contextlib

from OpenGL.GL import *

@contextlib.contextmanager
def translated(x, y, z):
    glPushMatrix()
    glTranslatef(x, y, z)
    yield
    glPopMatrix()

