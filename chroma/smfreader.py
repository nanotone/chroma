import bisect
import sys
import threading
import time

from midi.MidiInFile import MidiInFile
from midi.MidiOutStream import MidiOutStream

import engine


class SMFReader(MidiOutStream):
	def __init__(self, smf_path):
		MidiOutStream.__init__(self)
		self.quarters_per_tick = 1.0 / 96
		self.events = []
		self.tempi = []
		MidiInFile(self, smf_path).read()

	def header(self, format=0, nTracks=1, division=96):
		self.quarters_per_tick = 1.0 / division

	def note_on(self, channel=0, note=0x40, velocity=0x40):
		self.events.append((self.abs_time(), channel, 'note_on', note, velocity))

	def note_off(self, channel=0, note=0x40, velocity=0x40):
		self.events.append((self.abs_time(), channel, 'note_off', note))

	def continuous_controller(self, channel, controller, value):
		if controller == 0x40:
			self.events.append((self.abs_time(), channel, 'damper', value))

	def tempo(self, value):
		self.tempi.append([self.abs_time(), value * self.quarters_per_tick])

	def sysex_event(self, *args):
		print "wat", args

	def eof(self):
		self.tempi.sort()
		self.events.sort()
		assert self.tempi[0][0] == 0, "No tempo found at tick=0 in MIDI file"
		(prev_tick, prev_time, micros_per_tick) = (0, 0, 0)
		for tempo in self.tempi:
			tick = tempo[0]
			cur_time = prev_time + (tick - prev_tick) * micros_per_tick
			tempo.append(cur_time)
			prev_tick = tick
			micros_per_tick = tempo[1]
			prev_time = cur_time

	def get_time(self, abs_tick):
		idx = bisect.bisect_right(self.tempi, [abs_tick])
		if idx:
			tempo = self.tempi[idx - 1]
			return (tempo[2] + (abs_tick - tempo[0]) * tempo[1]) * 0.000001
		else:
			return 0

	def run(self):
		now = start_time = time.time()
		for event in self.events:
			t = self.get_time(event[0])
			wait = t - (now - start_time)
			if wait > 0:
				time.sleep(wait)
				now = time.time()
			func = getattr(engine, event[2], None)
			if func:
				func(*event[3:])

	def start(self):
		thread = threading.Thread(target=self.run)
		thread.daemon = True
		thread.start()

