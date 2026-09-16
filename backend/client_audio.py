"""Configure the APK's ALSA endpoint without changing the installed rootfs."""
import hashlib
import json
from pathlib import Path
import struct


def configure_environment(env, session):
    env.update(ALSA_CONFIG_PATH=str(session/'asound.conf'), TRASC_AUDIO_SOCKET=str(session/'audio.sock'))
    # Wine's session override avoids persistent driver edits and stale Pulse defaults.
    env['WINEDLLOVERRIDES'] += ';winepulse.drv=d'


def prepare(folder, session):
    library = folder/'libasound_module_pcm_trasc.so'
    data = library.read_bytes()
    manifest = json.loads((folder/'audio-bundle.json').read_text())
    if (manifest.get('protocol'), manifest.get('architecture')) != (1, 'arm64-glibc'):
        raise RuntimeError('Unsupported audio bridge bundle')
    if library.is_symlink() or hashlib.sha256(data).hexdigest() != manifest.get('sha256'):
        raise RuntimeError('Audio bridge checksum failed')
    if data[:5] != b'\x7fELF\x02' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise RuntimeError('Audio bridge is not ARM64')
    if not (session/'audio.sock').is_socket():
        raise RuntimeError('Android audio bridge is not listening')
    # The built-in ALSA plug handles sample-rate, channel and sample-format conversion.
    # Capture is deliberately absent: the game needs playback, no microphone access.
    (session/'asound.conf').write_text(
        '</usr/share/alsa/alsa.conf>\n'
        f'pcm_type.trasc {{ lib "{library}" }}\n'
        'pcm.trasc { type trasc }\n'
        'pcm.!default { type plug slave { pcm "trasc" format S16_LE rate 48000 channels 2 } }\n')
    return {'backend': 'alsa-audiotrack', 'protocol': 1, 'rate': 48000, 'channels': 2,
            'sha256': manifest['sha256']}
