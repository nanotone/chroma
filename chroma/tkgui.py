import Tkinter

import engine

HEIGHT = 400

def run():
	Tkinter.mainloop()

class TkListener(object):
	ATTACK_BONUS_DUR = 0.15

	HEXCOLORS = ['#40FF40', '#00FFFF', '#20A0FF', '#4080FF', # G C
	             '#8060FF', '#C040E0', '#FF0080', '#FF0040', # B M
	             '#FF4020', '#FF8000', '#FFFF00', '#80FF00'] # ROY
	RGB_COLORS = map(engine.rgb_from_hexcolor, HEXCOLORS)
	GRAY = [0.75] * 3

	def __init__(self):
		self.master = Tkinter.Tk()
		self.w = Tkinter.Canvas(self.master, width=880, height=HEIGHT)
		self.w.pack()
		self.w.create_rectangle(0, 0, 880, HEIGHT, fill='black')
		self._rects_by_midinote = {}

	def get_attack_multiplier(self, age):
		return max(2.0 - age / self.ATTACK_BONUS_DUR, 1.0)

	def create_note(self, midinote, velocity):
		width_adjust = int(velocity * 8 - 4)
		if midinote in self._rects_by_midinote:
			self.w.delete(self._rects_by_midinote[midinote])
		key = midinote - 21
		self._rects_by_midinote[midinote] = self.w.create_rectangle(10*key - width_adjust, 0,
		                                                            10*(key+1) + width_adjust, HEIGHT,
		                                                            fill='black')

	def update_note(self, midinote, color):
		rect = self._rects_by_midinote.get(midinote)
		if not rect:
			pass
		self.w.itemconfig(rect, fill=engine.hexcolor_from_rgb(color))

	def delete_note(self, midinote):
		rect = self._rects_by_midinote.get(midinote)
		if rect:
			self.w.delete(rect)
			del self._rects_by_midinote[midinote]

