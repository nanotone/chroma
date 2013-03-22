import math
import Queue
import threading
import time


TIME_SCALE = 1/2.0  # takes 2 seconds for a note to decay e-fold

SLICE_RADS = 2 * math.pi / 12

listeners = []

def rgb_from_hexcolor(hexcolor):
	return (int(hexcolor[1:3], 16) / 255.0, int(hexcolor[3:5], 16) / 255.0, int(hexcolor[5:7], 16) / 255.0)


def hexcolor_from_rgb(rgb):
	return '#' + ''.join(map(lambda f: '%02x' % round(255*f), rgb))

def weighted_avg_colors(color1, color2, w1):
	return [w1*c1 + (1-w1)*c2 for (c1, c2) in zip(color1, color2)]

coords_for_pitch_class = {
	pitch_class: [math.cos(pitch_class * SLICE_RADS),
	              math.sin(pitch_class * SLICE_RADS)]
	for pitch_class in xrange(12)
}
def coords_for_midinote(midinote):
	return coords_for_pitch_class[midinote * 7 % 12]


class Note(object):
	def __init__(self, start, volume):
		self.start = start
		self.volume = volume
		self.damp_start = 0
		self.damp_level = 1.0
		self.accum = 1.0


events = Queue.Queue()
notes = {}
reverb_origin = [0, 0]

class DefaultHandler(object):
	@staticmethod
	def note_on(note, velocity):
		events.put((note, velocity))
	@staticmethod
	def note_off(note):
		events.put((note, 0))
	@staticmethod
	def damper(level):
		events.put((-1, level))
handlers = [DefaultHandler()]

def make_event_listener(event_name):
	def event_listener(*args):
		for handler in handlers: getattr(handler, event_name)(*args)
	return event_listener
for event_name in ('note_on', 'note_off', 'damper'):
	globals()[event_name] = make_event_listener(event_name)


def get_reverb_origin(now):
	elapsed = now - getattr(get_reverb_origin, 'last_calculation', 0)
	if elapsed:
		decay_factor = math.exp(-elapsed * TIME_SCALE)
		reverb_origin[0] *= decay_factor
		reverb_origin[1] *= decay_factor
		get_reverb_origin.last_calculation = now
	return reverb_origin

def get_active_note_pos(midinote, now):
	note = notes[midinote]
	(note_x, note_y) = coords_for_midinote(midinote)
	age = (now - note.start) * TIME_SCALE
	elapsed = (now - note.damp_start) * TIME_SCALE if note.damp_start else age
	weight = math.exp(-age) * (note.accum + note.damp_level * elapsed) * note.volume
	return (note_x * weight, note_y * weight)

def get_origin(now):
	note_positions = [get_active_note_pos(midinote, now) for midinote in notes]
	(x, y) = map(sum, zip(*note_positions)) if note_positions else (0, 0)
	(reverb_x, reverb_y) = get_reverb_origin(now)
	(x, y) = (x + reverb_x, y + reverb_y)
	scale = math.log1p(math.hypot(x, y)) * 0.21
	return (scale * x, scale * y)

def nice(coords):
	return "(" + ", ".join("%.3f" % f for f in coords) + ")"

def update_colors(now):
	if now - update_colors.last_update < 0.05:
		return
	origin = get_origin(now)
	for (midinote, note) in notes.iteritems():
		age = now - note.start
		weight = math.exp(-age * TIME_SCALE) * note.damp_level * note.volume**0.3

		pos = coords_for_midinote(midinote)
		pos = (pos[0] + origin[0], pos[1] + origin[1])

		r = math.hypot(*pos)
		(f, pc1) = math.modf(math.atan2(pos[1], pos[0]) / SLICE_RADS + 12)
		pc1 = int(pc1)
		for listener in listeners:
			color = weighted_avg_colors(listener.RGB_COLORS[ pc1      % 12],
			                            listener.RGB_COLORS[(pc1 + 1) % 12],
			                            1-f)
			if r < 1.0:
				color = weighted_avg_colors(color, listener.GRAY, r)

			weight *= listener.get_attack_multiplier(age)
			color = [min(c * weight, 1) for c in color]

			listener.update_note(midinote, color)
	update_colors.last_update = now
update_colors.last_update = 0

def delete_note(midinote, now):
	# add finished note to reverb
	note_pos = get_active_note_pos(midinote, now)
	get_reverb_origin(now)  # also an update
	reverb_origin[0] += note_pos[0]
	reverb_origin[1] += note_pos[1]

	for listener in listeners:
		listener.delete_note(midinote)

def queueproc():
	while True:
		try:
			(midinote, state) = events.get(block=False, timeout=0.05)
			now = time.time()
		except Queue.Empty:
			update_colors(time.time())
			continue
		process_event(midinote, state, now)
		update_colors(now)

damper_level = 0
def process_event(midinote, state, now):
	global damper_level
	state /= 127.0
	if midinote == -1:  # damper
		if state < damper_level:
			if state:
				for (midinote, note) in notes.iteritems():
					if note.damp_start and state < note.damp_level:
						note.accum += (now - note.damp_start) * TIME_SCALE * note.damp_level
						note.damp_level = state
						note.damp_start = now
			else:  # sec
				for (midinote, note) in notes.items():
					if note.damp_start:
						delete_note(midinote, now)
						del notes[midinote]
		damper_level = state
	elif state:  # note on
		note = Note(now, state)
		if midinote in notes:
			delete_note(midinote, now)
		notes[midinote] = note
		for listener in listeners:
			listener.create_note(midinote, state)
		#if w:
			#key = midinote - 21
			#width_adjust = int(state * 8 - 4)
			#note.rect = w.create_rectangle(10*key - width_adjust, 0, 10*(key+1) + width_adjust, 100, fill='#000000')
	else:  # note off
		note = notes.get(midinote)
		if note:
			if damper_level:
				note.damp_level = damper_level
				note.accum += (now - note.start) * TIME_SCALE
				note.damp_start = now
			else:
				delete_note(midinote, now)
				del notes[midinote]

def start_queue_proc():
	queue_thread = threading.Thread(target=queueproc)
	queue_thread.daemon = True
	queue_thread.start()

