"""Exercise the actual external ALSA plug (conversion, clock and reconnect)."""
import ctypes as C
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from audio_receiver import Receiver

library = str(Path(sys.argv[1]).resolve())
alsa = C.CDLL('libasound.so.2')
alsa.snd_pcm_open.argtypes = [C.POINTER(C.c_void_p), C.c_char_p, C.c_int, C.c_int]
alsa.snd_pcm_set_params.argtypes = [C.c_void_p, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_int, C.c_uint]
alsa.snd_pcm_writei.argtypes = [C.c_void_p, C.c_void_p, C.c_ulong]; alsa.snd_pcm_writei.restype = C.c_long
for name in ('snd_pcm_drain', 'snd_pcm_close', 'snd_pcm_prepare'):
    getattr(alsa, name).argtypes = [C.c_void_p]
alsa.snd_pcm_delay.argtypes = [C.c_void_p, C.POINTER(C.c_long)]

with tempfile.TemporaryDirectory(prefix='trasc-audio-') as directory:
    path = Path(directory); receiver = Receiver(path/'audio.sock')
    config = path/'asound.conf'
    config.write_text(f'</usr/share/alsa/alsa.conf>\npcm_type.trasc {{ lib "{library}" }}\npcm.trasc {{ type trasc }}\npcm.!default {{ type plug slave {{ pcm "trasc" format S16_LE rate 48000 channels 2 }} }}\n')
    os.environ.update(ALSA_CONFIG_PATH=str(config), TRASC_AUDIO_SOCKET=str(path/'audio.sock'))
    try:
        for rate, channels in ((48000, 2), (22050, 1), (44100, 2)):
            print(f'Checking real ALSA playback: rate={rate} channels={channels}', flush=True)
            pcm = C.c_void_p(); assert alsa.snd_pcm_open(C.byref(pcm), b'default', 0, 1) == 0
            try:
                # S16_LE, RW_INTERLEAVED; software conversion, 80 ms buffer.
                result = alsa.snd_pcm_set_params(pcm, 2, 3, channels, rate, 1, 80000)
                assert result == 0, ('parameters', rate, channels, result, receiver.snapshot())
                count = rate//2; samples = (C.c_int16*(count*channels))()
                for i in range(count):
                    for c in range(channels): samples[i*channels+c] = int(math.sin(i*2*math.pi*(440+c*220)/rate)*12000)
                started = time.monotonic(); offset = 0; paused = False
                while offset < count:
                    assert time.monotonic()-started < 4, 'PCM playback stalled'
                    n = alsa.snd_pcm_writei(pcm, C.byref(samples, offset*channels*2), min(512, count-offset))
                    if n == -11: time.sleep(.002); continue
                    assert n > 0, ('write', n); offset += n
                    if not paused and offset >= rate//10:
                        # Simulate a loading/scheduling pause long enough to empty
                        # the entire ring; the next write must resume normally.
                        time.sleep(.12); paused = True
                # Nonblocking drain can return EAGAIN; our endpoint itself waits boundedly.
                while True:
                    drained=alsa.snd_pcm_drain(pcm)
                    if drained==0: break
                    assert drained==-11 and time.monotonic()-started<4, ('drain',drained)
                    time.sleep(.002)
                elapsed = time.monotonic()-started
                assert .4 < elapsed < 2, ('unpaced or stalled audio', elapsed)
            finally: alsa.snd_pcm_close(pcm)
        report = receiver.snapshot(); assert not report['errors'], report
        assert sum(s['nonzero_samples'] for s in report['streams']) > 100000, report
        assert all(s['left_nonzero'] and s['right_nonzero'] for s in report['streams']), report
        print('PASS: real ALSA stereo, mono/rate conversion, playback clock and repeated stream cleanup', json.dumps(report))
    finally: receiver.close()
