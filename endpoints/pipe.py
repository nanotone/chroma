import json
import sys

class StdoutSerializer(object):
    def emit(self, code, *args):
        sys.stdout.write(json.dumps([code] + list(args)) + '\n')
        sys.stdout.flush()
    def eof(self):
        pass

def run_src(arg, emit):
    while True:
        data = sys.stdin.readline().strip()
        if data:
            args = json.loads(data)
            emit(*args)

def make_dst(arg):
    return StdoutSerializer()
