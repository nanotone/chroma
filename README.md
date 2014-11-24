Setup
=====

GLFW is required. On OSX, install it via Homebrew:
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

Optionally, MIDI streams can be rendered to audio output using FluidSynth, a real-time software synthesizer. On OSX, install FluidSynth via Homebrew:
```
$ brew install fluid-synth
```

FluidSynth requires a SoundFont file which contains instrument-specific waveforms for rendering audio. A helpful `get-sounds.py` script can install several popular SoundFonts in `sounds/sf2/`:
```
$ python get-sounds.py
```
