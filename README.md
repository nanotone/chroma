Setup
=====

[GLFW](http://www.glfw.org/) is required. On OSX, install it via [Homebrew](http://brew.sh/):
```
$ brew tap homebrew/versions
$ brew install glfw3
```

Then pip the rest (in a virtualenv, if you like):
```
$ pip install -r requirements.txt
```

Synthesis
=========

Optionally, MIDI streams can be rendered to audio output using [FluidSynth](http://www.fluidsynth.org/), a real-time software synthesizer. On OSX, install FluidSynth via Homebrew:
```
$ brew install fluid-synth
```

FluidSynth requires a [SoundFont](http://en.wikipedia.org/wiki/SoundFont) file which contains instrument-specific waveforms for rendering audio. A helpful `get-sounds.py` script is provided for installing a few popular SoundFonts into `sounds/sf2/`:
```
$ python get-sounds.py
```
