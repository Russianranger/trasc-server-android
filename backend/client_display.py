"""Selected game display settings, with byte-exact original/previous backups."""
import os
from pathlib import Path
import tempfile

RESOLUTIONS = ('640x480', '800x600', '960x540', '1024x768', '1280x720')
MAX_INI_BYTES = 2 * 1024 * 1024


def update_ini(text, section, values):
    """Update only selected INI values, preserving unrelated settings/comments."""
    result, pending, active, found = [], dict(values), False, False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            if active:
                result.extend(f'{k}={v}' for k, v in pending.items()); pending.clear()
            active = stripped[1:-1].casefold() == section.casefold(); found |= active
        elif active and '=' in line and not stripped.startswith((';', '#')):
            key = line.split('=', 1)[0].strip()
            match = next((k for k in values if k.casefold() == key.casefold()), None)
            if match:
                line = key + '=' + str(values[match]); pending.pop(match, None)
        result.append(line)
    if not found: result += ['', '[' + section + ']']
    result.extend(f'{k}={v}' for k, v in pending.items())
    return '\r\n'.join(result) + '\r\n'



def display_ini(text, resolution, fullscreen):
    if resolution not in RESOLUTIONS: raise ValueError('Unsupported client resolution')
    if not isinstance(fullscreen, bool): raise ValueError('Invalid fullscreen option')
    width, height = resolution.split('x')
    text = update_ini(text, 'Defaults', {'WindowedMode':'FALSE' if fullscreen else 'TRUE'})
    return update_ini(text, 'VideoMode', {'Width':width, 'Height':height,
                                        'WindowedWidth':width, 'WindowedHeight':height})


def atomic_bytes(target, data):
    # Exclusive temporary file; never follow an imported .trasc-new symlink.
    fd, name = tempfile.mkstemp(prefix='.trasc-display-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def apply_display(client, prefix, resolution, fullscreen):
    # Apply only on an explicit client launch, after the old game has stopped.
    display_ini('', resolution, fullscreen)  # Validate before touching any file.
    if client.is_symlink(): raise ValueError('Client directory cannot be a symlink')
    matches = [p for p in client.iterdir() if p.name.casefold() == 'eqclient.ini']
    if len(matches) > 1: raise ValueError('Ambiguous client filename: eqclient.ini')
    target = matches[0] if matches else client/'eqclient.ini'
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError('Display setup requires an ordinary eqclient.ini')
    if target.exists() and target.stat().st_size > MAX_INI_BYTES:
        raise ValueError('eqclient.ini is too large to update safely')
    original = target.read_bytes() if target.exists() else b''
    # Latin-1 roundtrips every byte in the legacy Windows INI. ASCII keys are
    # the only interpreted content; unrelated non-ASCII values stay intact.
    if original.startswith((b'\xff\xfe', b'\xfe\xff')):
        raise ValueError('UTF-16 eqclient.ini is unsupported; display settings were not changed')
    bom = b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b''
    updated = bom + display_ini(original[len(bom):].decode('latin-1'), resolution, fullscreen).encode('latin-1')
    report = {'resolution':resolution, 'fullscreen':fullscreen, 'changed':updated != original}
    if updated == original: return report
    backup = prefix/'trasc-display-originals'
    if backup.is_symlink(): raise ValueError('Display backup directory cannot be a symlink')
    backup.mkdir(parents=True, exist_ok=True)
    first, previous = backup/'eqclient.ini', backup/'eqclient.previous.ini'
    for path in (first, previous):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError('Display backup must be an ordinary file')
    if not first.exists(): atomic_bytes(first, original)
    atomic_bytes(previous, original)
    atomic_bytes(target, updated)
    report['backup'] = 'client/prefix/trasc-display-originals'
    return report
