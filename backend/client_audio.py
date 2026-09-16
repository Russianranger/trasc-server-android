"""Configure the APK's ALSA endpoint without changing the installed rootfs."""
import hashlib
import json
from pathlib import Path
import struct
import re
from itertools import islice


def inspect_client(client, logs):
    """Bounded, read-only inventory. Never export INIs, PCM or arbitrary paths.

    Missing loose files may be packed in an archive; report that distinction
    instead of declaring the user's installation broken. Wine resolves case.
    """
    report = {'format': 1, 'settings': {}, 'files': {}, 'loose_wav_count': 0,
              'wav_formats': {}, 'wav_references': 0, 'resolved_loose': 0,
              'unresolved_loose': [], 'unresolved_count': 0, 'unsafe_references': 0,
              'inventory_truncated': False,
              'note': 'Unresolved loose sounds may be packed; this is not proof of missing assets.'}

    def directory(path, limit):
        if path.is_symlink() or not path.is_dir(): return {}
        entries = list(islice(path.iterdir(), limit + 1))
        if len(entries) > limit: report['inventory_truncated'] = True
        found = {}
        for p in entries[:limit]:
            key = p.name.casefold()
            # Reject case collisions and all symlinks rather than selecting one.
            if key in found or p.is_symlink(): found[key] = None
            else: found[key] = p
        return found

    try:
        root = directory(client, 20000)
        sounds = root.get('sounds')
        sound_files = directory(sounds, 20000) if sounds else {}
        for name in ('soundassets.txt', 'sounds.eff', 'mss32.dll', 'msssoft.m3d',
                     'mssds3d.m3d', 'mssdx7.m3d', 'mssmp3.asi', 'spelleffects.eff'):
            path = root.get(name)
            report['files'][name] = {'present': bool(path and path.is_file())}
            if path and path.is_file(): report['files'][name]['bytes'] = path.stat().st_size
        ini = root.get('eqclient.ini')
        allowed = {'sound', 'music', 'soundvolume', 'musicvolume', 'soundrealism',
                   'envsounds', 'combatmusic', 'speakertype', 'sound44k', 'sound16bit',
                   'usethreepointlighting', 'shownameslevel'}
        if ini and ini.is_file() and ini.stat().st_size <= 2*1024*1024:
            active = False
            for line in ini.read_bytes().decode('latin-1').lstrip('\xef\xbb\xbf').splitlines():
                line = line.strip()
                if line.startswith('[') and line.endswith(']'): active = line[1:-1].casefold() == 'defaults'
                elif active and '=' in line and not line.startswith((';', '#')):
                    key, value = (v.strip() for v in line.split('=', 1))
                    if key.casefold() in allowed and re.fullmatch(r'[-+0-9A-Za-z. ]{1,32}', value):
                        report['settings'][key.casefold()] = value
        # Inspect headers only, at most 256 files and 4 KiB each. A format
        # count is enough to separate PCM from compressed WAV codecs.
        wave_paths = [p for mapping in (root, sound_files) for key, p in mapping.items()
                      if key.endswith('.wav') and p and p.is_file()]
        report['loose_wav_count'] = len(wave_paths)
        report['wav_headers_checked'] = min(len(wave_paths), 256)
        for path in sorted(wave_paths)[:256]:
            with path.open('rb') as f: data = f.read(4096)
            fmt = 'unrecognized'
            if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
                offset = 12
                while offset + 8 <= len(data):
                    size = struct.unpack_from('<I', data, offset+4)[0]
                    if data[offset:offset+4] == b'fmt ' and size >= 16 and offset+24 <= len(data):
                        tag, channels, rate = struct.unpack_from('<HHI', data, offset+8)
                        bits = struct.unpack_from('<H', data, offset+22)[0]
                        fmt = f'tag={tag},channels={channels},rate={rate},bits={bits}'
                        break
                    offset += 8 + size + (size & 1)
            report['wav_formats'][fmt] = report['wav_formats'].get(fmt, 0) + 1
        table = root.get('soundassets.txt')
        if table and table.is_file() and table.stat().st_size <= 2*1024*1024:
            references = set()
            for line in table.read_bytes().decode('latin-1').splitlines():
                if line.lstrip().startswith(('#', '//', ';')): continue
                for field in line.split('^'):
                    name = field.strip().strip('"{}').replace('\\', '/').casefold()
                    if not name.endswith('.wav'): continue
                    if not re.fullmatch(r'(?:sounds/)?[a-z0-9_ .-]{1,160}\.wav', name) or '..' in name:
                        report['unsafe_references'] += 1; continue
                    references.add(name)
            report['wav_references'] = len(references)
            for name in sorted(references):
                bare = name.removeprefix('sounds/')
                choices = [sound_files.get(bare)] if name.startswith('sounds/') else [root.get(bare), sound_files.get(bare)]
                if any(p and p.is_file() for p in choices): report['resolved_loose'] += 1
                else:
                    report['unresolved_count'] += 1
                    if len(report['unresolved_loose']) < 24: report['unresolved_loose'].append(name)
        elif table: report['soundassets_unreadable'] = True
    except OSError as error:
        # A diagnostic must not stop a working game launch. Do not export an
        # exception string that may contain unrelated imported filenames.
        report['inspection_error'] = type(error).__name__
    target = logs/'client-sound-assets.json'
    previous = logs/'client-sound-assets.previous.json'
    if target.is_file(): target.replace(previous)
    target.write_text(json.dumps(report, indent=2)+'\n')
    return {k: report[k] for k in ('loose_wav_count', 'wav_references', 'resolved_loose', 'unresolved_count', 'settings')}


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
