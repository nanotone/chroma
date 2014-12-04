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
            prev = start = time.time()
            avg_elapsed = 0
            avg_render_elapsed = 0
            while not glfw.window_should_close(self.win):
                time0 = time.time()
                render_frame()
                avg_render_elapsed = avg_render_elapsed * 0.9 + (time.time() - time0) * 0.1
                glfw.swap_buffers(self.win)
                glfw.poll_events()
                now = time.time()
                avg_elapsed = avg_elapsed * 0.9 + (now - prev) * 0.1
                prev = now
                if now - start >= 1.0:
                    print "%.1f fps, %.1f%% spent in render" % (1/avg_elapsed, 100*avg_render_elapsed/avg_elapsed)
                    start = now
        finally:
            glfw.destroy_window(self.win)
            glfw.terminate()


class GlfwError(Exception):
    pass
