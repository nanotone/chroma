import json
import subprocess


class GLClient(object):
    def __init__(self):
        self.proc = subprocess.Popen(['python', 'run-glclient.py'], stdin=subprocess.PIPE)

    def emit(self, code, *args):
        self.proc.stdin.write(json.dumps([code] + list(args)) + '\n')

    def eof(self):
        self.proc.stdin.close()


def make_dst(arg):
    return GLClient()
