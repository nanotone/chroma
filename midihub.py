#!/usr/bin/env python

import importlib
import traceback

import midihub.simple_logging as logging

def make_midi_dst(arg):
    if arg == '-':
        arg = 'pipe:'
    elif ':' not in arg:
        arg = 'smf://' + arg
    (scheme, arg) = arg.split(':', 1)
    try:
        module = importlib.import_module('midihub.endpoints.' + scheme)
    except ImportError:
        raise ImportError("Unrecognized MIDI sink: module midihub.endpoints.%s not found" % scheme)
    return module.make_dst(arg[2:])


def main(args):
    sinks = map(make_midi_dst, args.dst)
    def emit(*a, **k):
        for s in sinks[:]:
            try:
                s.emit(*a, **k)
            except Exception:
                traceback.print_exc()
                sinks.remove(s)
                if not sinks:
                    logging.warning("No more MIDI sinks!")
    try:
        src = args.src
        if src == '-':
            src = 'pipe:'
        elif ':' not in src:
            src = 'smf://' + src
        (scheme, arg) = src.split(':', 1)
        try:
            module = importlib.import_module('midihub.endpoints.' + scheme)
            module.run_src(arg[2:], emit)
        except ImportError:
            raise ImportError("Unrecognized MIDI source: module midihub.endpoints.%s not found" % scheme)
    finally:
        for s in sinks: s.eof()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('src', help="- (stdin) | .mid file | midi: (realtime)")
    parser.add_argument('dst', nargs='*', help="- (stdout) | .mid file | udp://HOST | fluid:")
    main(parser.parse_args())
