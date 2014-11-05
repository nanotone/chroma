import threading

import rtmidi_python as rtmidi

import engine


class MidiInput(object):
	def __init__(self):
		self._midiin = rtmidi.MidiIn()
		port_names = self._midiin.ports
		assert port_names, "No MIDI input ports found"
		if len(port_names) == 1:
			idx = 0
			print "Choosing MIDI input port", port_names[0]
		else:
			print "MIDI input ports:"
			for (idx, port_name) in enumerate(port_names):
				print "%s. %s" % (idx, port_name)
			idx = int(raw_input("Which MIDI input port? "))
			assert 0 <= idx < len(port_names)
		self._midiin.open_port(idx)

	def run(self):
		while True:
			(message, delta_time) = self._midiin.get_message()
			if message:
				self._callback((message, delta_time))

	def start(self):
		self.thread = threading.Thread(target=self.run, name="MIDI input")
		self.thread.daemon = True
		self.thread.start()
		#self._midiin.set_callback(self._callback)

	def _callback(self, event, data=None):
		#print "midiserial callback", event
		((func, x, y), delta) = event
		if func & 0x0F == 0:
			if func & 0xF0 == 0x80:  # note off
				note = x
				engine.note_off(note)
			elif func & 0xF0 == 0x90:  # note on
				note = x
				velocity = y
				engine.note_on(note, velocity)
			elif func & 0xF0 == 0xB0:  # pedal
				engine.damper(y)

class MidiOutput(object):
	def __init__(self):
		self._midiout = rtmidi.MidiOut()
		port_names = self._midiout.get_ports()
		assert port_names, "No MIDI input ports found"
		if len(port_names) == 1:
			idx = 0
			print "Choosing MIDI input port", port_names[0]
		else:
			print "MIDI input ports:"
			for (idx, port_name) in enumerate(port_names):
				print "%s. %s" % (idx, port_name)
			idx = int(raw_input("Which MIDI input port? "))
			assert 0 <= idx < len(port_names)
		self._midiout.open_port(idx)

	def note_on(self, note, velocity):
		self._midiout.send_message([0x90, note, velocity])

	def note_off(self, note):
		self._midiout.send_message([0x80, note, 0])

	def damper(self, level):
		self._midiout.send_message([0xB0, 0x40, level])
