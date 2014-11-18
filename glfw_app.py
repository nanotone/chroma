import time

import glfw


class GlfwApp(object):
    def __init__(self, name, width, height, fullscreen=False):
        if not glfw.init():
            raise GlfwError("Could not initialize GLFW")
        monitor = glfw.get_primary_monitor() if fullscreen else None
        self.win = glfw.create_window(width, height, name, monitor, None)
        if not self.win:
            glfw.terminate()
            raise GlfwError("Could not create GLFW window")
        glfw.make_context_current(self.win)
        glfw.set_key_callback(self.win, self.key_cb)
        self.key_callbacks = []

    def key_cb(self, window, key, scancode, action, mods):
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        for cb in self.key_callbacks:
            cb(window, key, scancode, action, mods)

    def run(self, render_frame):
        try:
            frames_rendered = 0
            start = time.time()
            while not glfw.window_should_close(self.win):
                render_frame()
                glfw.swap_buffers(self.win)
                glfw.poll_events()
                frames_rendered += 1
                now = time.time()
                if now - start >= 1.0:
                    print "%.1f fps" % (frames_rendered / (now - start))
                    start = time.time()
                    frames_rendered = 0
        finally:
            glfw.destroy_window(self.win)
            glfw.terminate()


class GlfwError(Exception):
    pass
