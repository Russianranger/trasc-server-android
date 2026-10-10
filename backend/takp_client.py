"""TAKP's December 2002 client policy, independent of the RoF2 adapters."""
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import struct

# The server exporter produces spells_us.txt; keep it separate from the
# client's supplied spells_en.txt, whose checksum the pinned server validates.
CLIENT_FILES = ('spells_us.txt', 'SkillCaps.txt')
WINDOWS_FILES = ('eqgame.exe', 'eqmain.dll', 'eqgfx_dx8.dll')
PATCHES = {
    'd3d8.dll': '122928cfe225c25d30decf7184a5d37e490cecf3b58256ba3206c7e1853f8ab8',
    'eqgame.dll': 'f0ca8e4bdcf3875419ecb1067a95bd6dbf8197e564f9d51ff4dec98a30f14b97',
    'eqw.dll': 'c103e024f1cde7829603475e1532d3baabd0764280c63ca2797e7e72569554f4',
}
LEGACY_EQW_SHA = 'dffb97ac1f47d41f450614c8d6d4da30f3f47b7ed5046dbdbd111b3ba1fbe5ba'
PREVIOUS_EQW_SHA = 'b739dfe64b7f69be2ffebf13a1cf794bcfd9e37fe143a75134ca6359e60ef584'
DISABLED = ('native_dinput8', 'native_d3dx', 'mouse_warp', 'reduce_load_pauses', 'fast_spell_parse',
            'name_sky_compatibility')
RUNTIME_LIBRARIES = ('msvcp140.dll', 'vcruntime140.dll', 'ucrtbase.dll')


def file_at(parent, name, required=False):
    from managed_content import client_file
    path = client_file(Path(parent), name)
    if path.exists() and not path.is_file():
        raise ValueError('TAKP needs an ordinary client file: ' + name)
    if required and (not path.is_file() or not path.stat().st_size):
        raise ValueError('Import the complete TAKP 2.1/2.2 client ZIP; missing ' + name)
    return path


def pe32(path):
    with Path(path).open('rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b'MZ':
            raise ValueError('TAKP needs a Windows PE32 file: ' + Path(path).name)
        offset = struct.unpack_from('<I', header, 0x3c)[0]
        if offset < 64 or offset > min(Path(path).stat().st_size - 26, 16*1024**2):
            raise ValueError('Invalid Windows header: ' + Path(path).name)
        stream.seek(offset)
        pe = stream.read(26)
        if len(pe) != 26 or pe[:4] != b'PE\0\0' or struct.unpack_from('<H', pe, 4)[0] != 0x14c or struct.unpack_from('<H', pe, 24)[0] != 0x10b:
            raise ValueError('TAKP requires 32-bit x86 Windows files: ' + Path(path).name)


def validate_client(client, patched=False):
    """Reject DLL-only uploads and RoF2; the checksum file is never executed."""
    client = Path(client)
    if client.is_symlink() or not client.is_dir():
        raise ValueError('TAKP client must be an ordinary directory')
    files = {}
    for name in WINDOWS_FILES:
        path = file_at(client, name, True)
        pe32(path)
        files[name] = path.name
    # eqgame.dll computes the server checksum from the Intel Mac executable.
    # It must remain beside eqgame.exe, but is never launched under Wine.
    for name in ('eqmac.exe', 'eqstr_en.txt'):
        files[name] = file_at(client, name, True).name
    spell = file_at(client, 'spells_en.txt')
    legacy_spell = file_at(client, 'spells_us.txt')
    if not spell.is_file() or not spell.stat().st_size:
        if not legacy_spell.is_file() or not legacy_spell.stat().st_size:
            raise ValueError('Import the complete TAKP 2.1/2.2 client ZIP; missing spells_en.txt (or legacy spells_us.txt)')
        spell = legacy_spell
    files['spells_en.txt'] = spell.name
    archives = [p for p in client.iterdir() if p.suffix.casefold() == '.s3d' and p.is_file() and not p.is_symlink() and p.stat().st_size]
    if not archives:
        raise ValueError('Import the full TAKP game ZIP, including its .s3d zone/model assets')
    patches = {}
    if patched:
        for name, expected in PATCHES.items():
            path = file_at(client, name, True)
            pe32(path)
            value = hashlib.sha256(path.read_bytes()).hexdigest()
            if value != expected:
                raise ValueError('TAKP client update changed: ' + name + '. Prepare this client again to restore the bundled version')
            patches[name] = value
    return {'client_type': 'takp', 'profile': 'takp', 'executable': files['eqgame.exe'],
            'required_files': files, 's3d_files': len(archives), 'patches': patches,
            'checksum_file': files['eqmac.exe'], 'launch_arguments': [],
            'renderer_path': 'D3D8 to D3D9; DXVK/Turnip or WineD3D'}


def verify_bundle(folder=None):
    folder = Path(folder) if folder else Path(__file__).with_name('takp-client')
    manifest = file_at(folder, 'bundle.json', True)
    if manifest.stat().st_size > 32768:
        raise ValueError('Invalid bundled TAKP client manifest')
    metadata = json.loads(manifest.read_text())
    if metadata.get('format') != 1 or metadata.get('architecture') != 'x86' or metadata.get('files') != PATCHES:
        raise ValueError('Unsupported TAKP client bundle; install the matching APK')
    for name, expected in PATCHES.items():
        path = file_at(folder, name, True)
        pe32(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Bundled TAKP update checksum failed: ' + name)
    return folder


def bundle_changes(client, folder=None):
    folder = verify_bundle(folder)
    return {file_at(client, name): folder / name for name in PATCHES}


def upgrade_camera_helper(client, prefix, folder=None):
    """Upgrade only the known previous managed EQW helper before Wine starts.

    Preserve its exact original once; changed/custom DLLs require an explicit
    Prepare transaction instead of being silently replaced at launch.
    """
    from client_display import atomic_bytes
    client, prefix = Path(client), Path(prefix)
    if client.is_symlink() or not client.is_dir() or prefix.is_symlink():
        raise ValueError('TAKP camera repair requires ordinary client/prefix directories')
    target = file_at(client, 'eqw.dll', True)
    pe32(target)
    original = target.read_bytes()
    current = hashlib.sha256(original).hexdigest()
    expected = PATCHES['eqw.dll']
    if current == expected:
        return {'state':'current', 'sha256':expected, 'changed':False}
    managed_previous = {LEGACY_EQW_SHA, PREVIOUS_EQW_SHA}
    if current not in managed_previous:
        raise ValueError('TAKP EQW helper changed; Prepare the client to install the reviewed camera repair')
    folder = verify_bundle(folder)
    replacement = (folder/'eqw.dll').read_bytes()
    # Complete other-file validation before creating backups or writing a DLL.
    validate_client(client)
    for name, digest in PATCHES.items():
        if name != 'eqw.dll' and hashlib.sha256(file_at(client, name, True).read_bytes()).hexdigest() != digest:
            raise ValueError('TAKP client update changed: ' + name + '. Prepare this client again')
    backup = prefix/'trasc-takp-camera-originals'
    if backup.is_symlink() or (backup.exists() and not backup.is_dir()):
        raise ValueError('TAKP camera backup must be an ordinary directory')
    backup.mkdir(parents=True, exist_ok=True)
    first = backup/'eqw.original.dll'
    if first.is_symlink() or (first.exists() and not first.is_file()):
        raise ValueError('TAKP camera backup must be an ordinary file')
    if first.exists():
        if hashlib.sha256(first.read_bytes()).hexdigest() not in managed_previous:
            raise ValueError('TAKP camera original backup changed; client helper was not replaced')
    # Preserve the exact official 0.6.22 helper separately, while keeping the
    # first pre-repair backup intact if an earlier managed upgrade made it.
    previous = backup/'eqw.0622.dll'
    if previous.is_symlink() or (previous.exists() and not previous.is_file()):
        raise ValueError('TAKP camera previous backup must be an ordinary file')
    if previous.exists() and hashlib.sha256(previous.read_bytes()).hexdigest() != PREVIOUS_EQW_SHA:
        raise ValueError('TAKP camera previous backup changed; client helper was not replaced')
    if not first.exists():
        atomic_bytes(first, original)
    if current == PREVIOUS_EQW_SHA and not previous.exists():
        atomic_bytes(previous, original)
    atomic_bytes(target, replacement)
    return {'state':'upgraded', 'sha256':expected, 'previous_sha256':current,
            'changed':True, 'backup':'client/prefix/trasc-takp-camera-originals/eqw.original.dll'}


def effective_request(request):
    result = dict(request)
    if request.get('profile') != 'takp':
        return result
    if request.get('mode') == 'compiler':
        raise ValueError('The RoF2 client DLL compiler belongs to TRASC Custom')
    for name in DISABLED:
        result[name] = False
    # Accurate legacy math restored NPC models in the Thor device comparison.
    # Explicit saved choices remain available for subsequent comparisons.
    result.setdefault('cpu_profile', 'accurate')
    result.update(boat_mode='off', particle_mode='off', npc_rendering='standard', spell_test={})
    return result


def validate_request(request, client):
    if request.get('mode') != 'client':
        return {'state': 'off', 'client_type': 'takp'}
    report = validate_client(client, patched=True)
    if request.get('executable') != report['executable']:
        raise ValueError('Launch the TAKP Windows eqgame.exe; eqmac.exe is only its checksum resource')
    return {'state': 'off', 'client_type': 'takp', 'client': report}


def login_text(address, port):
    try:
        ipaddress.IPv4Address(address)
        port = int(port)
    except (ValueError, TypeError) as error:
        raise ValueError('TAKP login needs a valid IPv4 address and UDP port') from error
    if not 1 <= port <= 65535:
        raise ValueError('Invalid TAKP login UDP port')
    endpoint = '"' + address + ':' + str(port) + '"\r\n'
    return '[Registration Servers]\r\n{\r\n' + endpoint + '}\r\n[Login Servers]\r\n{\r\n' + endpoint + '}\r\n'


def repair_login_file(client, prefix):
    """Repair the 0.6.16/17 section names without changing the login address."""
    from client_display import atomic_bytes
    client, prefix = Path(client), Path(prefix)
    if client.is_symlink() or prefix.is_symlink():
        raise ValueError('TAKP login repair cannot follow linked directories')
    host = file_at(client, 'eqhost.txt', True)
    if host.stat().st_size > 16384:
        raise ValueError('TAKP eqhost.txt is too large; Prepare this client again')
    original = host.read_bytes()
    if original.startswith((b'\xff\xfe', b'\xfe\xff')):
        raise ValueError('TAKP eqhost.txt must use the legacy text format; Prepare this client again')
    updated = original
    for old, new in ((b'RegistrationServers', b'Registration Servers'),
                     (b'LoginServers', b'Login Servers')):
        updated = re.sub(rb'(?mi)^[ \t]*\[' + old + rb'\][ \t]*(?=\r?$)',
                         b'[' + new + b']', updated)
        if len(re.findall(rb'(?mi)^[ \t]*\[' + new + rb'\][ \t]*\r?$', updated)) != 1:
            raise ValueError('TAKP eqhost.txt needs one [' + new.decode() + '] section; Prepare this client again')
    report = {'format': 'takp_legacy', 'repaired': updated != original}
    if updated == original:
        return report
    backup = prefix / 'trasc-takp-login-originals'
    if backup.is_symlink() or (backup.exists() and not backup.is_dir()):
        raise ValueError('TAKP login backup must be an ordinary directory')
    backup.mkdir(parents=True, exist_ok=True)
    first, previous = backup / 'eqhost.txt', backup / 'eqhost.previous.txt'
    for target in (first, previous):
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError('TAKP login backup must be an ordinary file')
    if not first.exists():
        atomic_bytes(first, original)
    atomic_bytes(previous, original)
    atomic_bytes(host, updated)
    report['backup'] = 'client/prefix/trasc-takp-login-originals'
    return report


def data_changes(engine, client):
    changes = {}
    for name in CLIENT_FILES:
        target = file_at(client, name)
        source = engine.work / 'server/export' / name
        changes[target] = source
    return changes


def install_export(engine, client, result):
    from engine import atomic_json
    changes = data_changes(engine, client)
    for source in changes.values():
        if source.is_symlink() or not source.is_file() or not source.stat().st_size:
            raise ValueError('TAKP client export missing: ' + source.name)
    backup = engine._apply_client_changes(client, changes)
    result.update(local_client_synced=True, copied_files=2, backup=backup,
                  message='TAKP server exports spells_us.txt and SkillCaps.txt copied to this client; any supplied spells_en.txt remains unchanged. Originals saved in ' + backup + '.')
    atomic_json(engine.work / 'logs/client-data-sync.json', result)
    return result


def prepare(engine, args):
    from client_display import RESOLUTIONS, display_ini
    from engine import atomic_json
    client = engine._local_client()
    report = validate_client(client)
    resolution, fullscreen = args.get('resolution', '800x600'), args.get('fullscreen', False)
    if resolution not in RESOLUTIONS or not isinstance(fullscreen, bool):
        raise ValueError('Unsupported TAKP display option')
    changes = data_changes(engine, client)
    changes.update(bundle_changes(client))
    changes[file_at(client, 'eqhost.txt')] = login_text(engine.config['ip'], engine.config['login_port'])
    ini = file_at(client, 'eqclient.ini')
    if ini.exists() and ini.stat().st_size > 2*1024**2:
        raise ValueError('TAKP eqclient.ini is too large')
    raw = ini.read_bytes() if ini.exists() else b''
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        raise ValueError('UTF-16 eqclient.ini is unsupported')
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    changes[ini] = bom + display_ini(raw[len(bom):].decode('latin-1'), resolution, fullscreen, profile='takp').encode('latin-1')
    result = engine._export_client_data()
    for source in data_changes(engine, client).values():
        if source.is_symlink() or not source.is_file() or not source.stat().st_size:
            raise ValueError('TAKP client export missing: ' + source.name)
    backup = engine._apply_client_changes(client, changes)
    report.update(validate_client(client, patched=True), prepared_at=__import__('time').time(), prepared=True)
    marker = file_at(client, 'trasc-client.json', True)
    record = json.loads(marker.read_text())
    record.update(report)
    atomic_json(marker, record)
    result.update(local_client_synced=True, copied_files=2, backup=backup, client=record,
                  message='TAKP client prepared for ' + engine.config['ip'] + ':' + str(engine.config['login_port']) + '. Server exports spells_us.txt and SkillCaps.txt, bundled TAKP DLLs and display settings updated; any supplied spells_en.txt remains unchanged. Originals saved in ' + backup + '.')
    atomic_json(engine.work / 'logs/client-data-sync.json', result)
    return result


def runtime_dependencies(prefix, directx):
    """File/architecture preflight. Actual loader success is reported from Wine."""
    system = Path(prefix) / 'drive_c/windows/syswow64'
    report = {'verification': 'file_architecture_only', 'loaded': False, 'libraries': {}}
    for name in RUNTIME_LIBRARIES:
        path = system / name
        if path.is_symlink() and not (path.resolve().is_relative_to(Path(prefix).resolve()) or path.resolve().is_relative_to(Path('/opt/wine'))):
            raise ValueError('TAKP runtime library link leaves its Wine installation: ' + name)
        if not path.is_file():
            raise ValueError('TAKP needs Wine\'s x86 ' + name + '. Repair the client prefix or reinstall the client runtime')
        pe32(path)
        report['libraries'][name] = 'wine_builtin'
    # The bundled d3d8to9 resolves D3DX functions dynamically, not in PE imports.
    source = file_at(Path(directx), 'd3dx9_43.dll')
    manifest = file_at(Path(directx), 'directx.json')
    if not source.is_file() or not manifest.is_file():
        raise ValueError('Install DirectX helpers in the Client tab: TAKP\'s D3D8 wrapper requires x86 d3dx9_43.dll from the June 2010 package')
    data = json.loads(manifest.read_text())
    expected_source = '053f76dcbb28802e23341b6a787e3b0791c0fa5c8d4d011b1044172dbf89c73b'
    metadata = data.get('files', {}).get(source.name, {})
    if data.get('source_sha256') != expected_source or metadata.get('sha256') != hashlib.sha256(source.read_bytes()).hexdigest() or metadata.get('bytes') != source.stat().st_size:
        raise ValueError('TAKP DirectX helper verification failed; install DirectX helpers again')
    pe32(source)
    from managed_content import replace_client_file
    target = system / 'd3dx9_43.dll'
    if target.exists() and not target.is_file():
        raise ValueError('Wine D3DX helper path is not a file')
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != metadata['sha256']:
        replace_client_file(target, source)
    report['libraries']['d3dx9_43.dll'] = 'microsoft_native'
    return report


def dll_status(text):
    loaded, evidence = {}, []
    wanted = set(PATCHES) | {'d3dx9_43.dll', *RUNTIME_LIBRARIES}
    for line in text.splitlines():
        match = re.search(r'Loaded L".*\\+([^\\"]+\.dll)".*: (native|builtin)\s*$', line, re.I)
        if match and match[1].casefold() in wanted:
            loaded[match[1].casefold()] = match[2].casefold()
            evidence.append(line)
    return loaded, evidence[-12:]


def wine_overrides():
    # The importer may include older dgVoodoo or user input proxies. Explicit
    # builtin input/ddraw avoids activating them alongside the TAKP mod pair.
    return ';d3d8=n;eqw=n;eqgame=n;dinput=b;dinput8=b;ddraw=b;d3dx9_43=n,b;msvcp140=b;vcruntime140=b;ucrtbase=b'
