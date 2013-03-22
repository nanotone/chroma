import glob
import time

import serial

import engine

def get_output():
	usb_ports = glob.glob('/dev/tty.usb*')
	assert usb_ports, "No USB ports for Arduino-serial found"
	if len(usb_ports) == 1:
		idx = 0
		print "Choosing USB port", usb_ports[0], "for Arduino-serial"
	else:
		print "Available USB ports for Arduino-serial:"
		for (idx, usb) in enumerate(usb_ports):
			print "%s. %s" % (idx, usb)
		idx = int(raw_input("Which USB port? "))
	s = serial.Serial(usb_ports[idx], 9600)
	time.sleep(1)
	return USBListener(s)

class USBListener(object):

	HEXCOLORS = ['#30FF20', '#10E0A0', '#0090C0', '#1060E0', # G C
	             '#3030FF', '#7020D0', '#C00080', '#E00040', # B M
	             '#FF2010', '#E06000', '#C0C000', '#70E000'] # ROY
	RGB_COLORS = map(engine.rgb_from_hexcolor, HEXCOLORS)
	GRAY = [0.5] * 3

	def __init__(self, serial_port):
		self._port = serial_port
		self._values = {led: (0, 0, 0) for led in xrange(88)}
		self._skip_history = []

	@staticmethod
	def _led_from_midi(midinote):
		return 87 - (midinote - 21)

	@staticmethod
	def _led_exists_for_midi(midinote):
		return 21 <= midinote < 109

	@staticmethod
	def _noticeable_change(a, b):
		return (min(a, b) + 0.01) / (max(a, b) + 0.01) < 0.8

	def get_attack_multiplier(self, age):
		return 1.0

	def create_note(self, midinote, velocity):
		self.update_note(midinote, (0, 0, 0))

	def update_note(self, midinote, color):
		if self._led_exists_for_midi(midinote):
			led = self._led_from_midi(midinote)
			color = [int(round(32 * c**2)) for c in color]
			if any(self._noticeable_change(a, b) for (a, b) in zip(self._values[led], color)):
				msg = ''.join(map(chr, [led] + color))
				#print "writing", repr(msg)
				self._port.write(msg)
				self._values[led] = color
				self._skip_history.append(0)
			else:
				self._skip_history.append(1)
			if len(self._skip_history) >= 20:
				#print "skips/20:", sum(self._skip_history)
				self._skip_history = []

	def delete_note(self, midinote):
		self.update_note(midinote, (0, 0, 0))
