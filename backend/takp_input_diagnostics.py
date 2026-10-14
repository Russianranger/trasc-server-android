"""Read-only TAKP capture settings and an optional bounded native X observer."""
import hashlib
import json
from pathlib import Path
import re
import struct


REGISTRY_LIMIT = 8 * 1024 * 1024
SETTINGS = {
    r'software\wine\x11 driver': ('GrabPointer', 'GrabFullscreen', 'Managed', 'UseXInput2', 'UseTakeFocus'),
    r'software\wine\appdefaults\eqgame.exe\x11 driver': ('GrabPointer', 'GrabFullscreen', 'Managed', 'UseXInput2', 'UseTakeFocus'),
    r'software\wine\directinput': ('MouseWarpOverride',),
    r'software\wine\appdefaults\eqgame.exe\directinput': ('MouseWarpOverride',),
}


def prefix_settings(prefix):
    """Inspect only named input settings; never run reg.exe or write the prefix."""
    path = Path(prefix) / 'user.reg'
    result = {'format': 1, 'source': 'user.reg', 'read_only': True, 'values': {}}
    if path.is_symlink() or not path.is_file():
        return dict(result, state='unavailable')
    if path.stat().st_size > REGISTRY_LIMIT:
        return dict(result, state='oversized')
    section = None
    with path.open('rb') as source:
        content = source.read(REGISTRY_LIMIT + 1)
    if len(content) > REGISTRY_LIMIT:
        return dict(result, state='oversized')
    result['source_sha256'] = hashlib.sha256(content).hexdigest()
    for line in content.decode('utf-8', 'replace').splitlines():
        if len(line) > 4096:
            continue
        match = re.match(r'^\[([^\]]+)\]', line)
        if match:
            section = match[1].replace('\\\\', '\\').casefold()
            continue
        if section not in SETTINGS:
            continue
        match = re.match(r'^"([^"\\]+)"=(.*)$', line)
        if not match:
            continue
        names = {name.casefold(): name for name in SETTINGS[section]}
        name = names.get(match[1].casefold())
        if not name:
            continue
        raw = match[2]
        # Preserve only short REG_SZ or DWORD input values, never unrelated data.
        if re.fullmatch(r'"[^"\\]{0,32}"|dword:[0-9a-fA-F]{8}', raw):
            result['values'].setdefault(section, {})[name] = raw
        else:
            result['values'].setdefault(section, {})[name] = '<unsupported>'
    app = result['values'].get(r'software\wine\appdefaults\eqgame.exe\x11 driver', {})
    global_values = result['values'].get(r'software\wine\x11 driver', {})
    raw = app.get('GrabPointer', global_values.get('GrabPointer'))
    result['grab_pointer_source'] = 'application' if 'GrabPointer' in app else 'global' if raw else 'wine_default'
    result['grab_pointer_raw'] = raw
    # Wine uses the first REG_SZ character, rather than a Python truth value.
    result['grab_pointer_enabled'] = (True if raw is None else
        raw[1].casefold() not in ('n', 'f', '0') if raw.startswith('"') and len(raw) > 2 else None)
    return dict(result, state='read')


def start(supervisor, prefix, logs, root=None):
    """Observer failure is diagnostic only and must not block client launch."""
    if supervisor.request.get('profile') != 'takp' or supervisor.request.get('mode') != 'client':
        return {}
    try:
        settings = prefix_settings(prefix)
    except OSError as error:
        settings = {'state': 'unavailable', 'read_only': True, 'error': str(error)[:160]}
    result = {'takp_input_settings': settings}
    try:
        root = Path(root) if root else Path(__file__).parent
        binary = root / 'takp-xinput-observe'
        receipt = json.loads((root / 'takp-input-observer.json').read_text())
        data = binary.read_bytes() if binary.is_file() and not binary.is_symlink() else b''
        if (receipt.get('format') != 1 or len(data) != receipt.get('bytes')
                or hashlib.sha256(data).hexdigest() != receipt.get('sha256')
                or len(data) < 64 or data[:6] != b'\x7fELF\x02\x01'
                or struct.unpack_from('<H', data, 18)[0] != 183):
            raise ValueError('Input observer differs from qualified ARM64 bytes')
        from log_retention import rotate
        rotate(Path(logs) / 'client-xinput.log')
        process = supervisor.spawn([str(binary), '300'], 'client-xinput.log')
        result['takp_xinput_observer'] = {'state': 'started', 'pid': process.pid,
            'sha256': receipt['sha256'], 'read_only': True, 'max_seconds': 300,
            'max_bytes': 128 * 1024}
    except (OSError, ValueError, KeyError) as error:
        result['takp_xinput_observer'] = {'state': 'unavailable', 'error': str(error)[:240], 'read_only': True}
    return result
