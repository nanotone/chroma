import contextlib
import os
import shutil
import subprocess
import tempfile

SOUNDS_DIR = 'sounds/sf2'

FLUID_R3_GM = ('FluidR3_GM', "Fluid R3 GM", "141M")
TIM_GM = ('TimGM6mb', "Tim Brechbill GM", "5.7M")
ZENPH_YDP = ('acoustic_grand_piano_ydp_20080910', "Zenph Studios YDP", "132M")
UIMIS_STEINWAY = ('acoustic_piano_imis_1', "Iowa MIS (Steinway)", "38M")


filespecs = []
installers = {}

def installs(filespec):
    if filespec not in filespecs:
        filespecs.append(filespec)
        installers[filespec] = []
    def decorator(g):
        def wrapper():
            try:
                os.makedirs(SOUNDS_DIR, 0755)
            except OSError as e:
                if e.args[0] != 17:  # ignore "File exists" error
                    raise
            gen = g()
            src = gen.next()
            os.rename(src, '%s/%s.sf2' % (SOUNDS_DIR, filespec[0]))
            list(gen)  # clean up generator
        installers[filespec].append(wrapper)
    return decorator


@contextlib.contextmanager
def tempdir():
    path = tempfile.mkdtemp()
    print "Created temp dir", path
    try:
        yield path
    finally:
        print "Removing temp dir", path 
        shutil.rmtree(path)


def basic_url_installer(filespec, url):
    @installs(filespec)
    def gen():
        with tempdir() as path:
            abstemppath = '%s/%s.sf2' % (path, filespec[0])
            print "Fetching", url
            subprocess.check_call(['bash', '-c', 'curl -L %s > %s' % (url, abstemppath)])
            yield abstemppath


# FLUID_R3_GM

@installs(FLUID_R3_GM)
def musescore_fluidr3():
    with tempdir() as path:
        subprocess.check_call(['bash', '-c', 'curl -L http://www.musescore.org/download/fluid-soundfont.tar.gz | tar xz -C %s' % path])
        yield '%s/FluidR3 GM2-2.SF2' % path
basic_url_installer(FLUID_R3_GM, 'https://github.com/thinkpad20/synesthesia/raw/master/lib/FluidR3_GM.sf2')

# TIM_GM

basic_url_installer(TIM_GM, 'http://timidity.s3.amazonaws.com/TimGM6mb.sf2')
basic_url_installer(TIM_GM, 'http://sourceforge.net/p/mscore/code/HEAD/tree/trunk/mscore/share/sound/TimGM6mb.sf2?format=raw')

# ZENPH_YDP

@installs(ZENPH_YDP)
def zenvoid_bz2():
    with tempdir() as path:
        subprocess.check_call(['bash', '-c', 'curl -L http://freepats.zenvoid.org/Piano/YamahaDisklavierPro-GrandPiano.tar.bz2 | tar xj -C %s' % path])
        yield '%s/acoustic_grand_piano_ydp_20080910.sf2' % path
basic_url_installer(ZENPH_YDP, 'http://zenvoid.org/audio/acoustic_grand_piano_ydp_20080910.sf2')

# UIMIS_STEINWAY

basic_url_installer(UIMIS_STEINWAY, 'http://freepats.zenvoid.org/sf2/acoustic_piano_imis_1.sf2')


if __name__ == '__main__':
    print "What can I get for you?"
    for (i, filespec) in enumerate(filespecs):
        print "%d. %s (%s)" % (i, filespec[1], filespec[2])
    try:
        num = int(raw_input("? "))
    except KeyboardInterrupt:
        exit()
    filespec = filespecs[num]
    file_installers = installers[filespec]
    for installer in file_installers:
        try:
            installer()
            break
        except Exception:
            pass
    else:
        print "ERROR: Could not retrieve %s from any of %d sources" % (filespec[1], len(file_installers))

