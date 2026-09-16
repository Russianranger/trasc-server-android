"""Pinned, APK-owned Turnip/DXVK selection, with explicit device verification."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct

DEFAULT_DRIVER = '24.3.4'
DRIVERS = {'24.3.4': 'turnip.so', '26.0.0': 'turnip-26.0.0.so'}
FILES = (*DRIVERS.values(), 'vulkan-probe', 'dxvk-d3d9.dll')


def driver_file(version):
    if not isinstance(version, str) or version not in DRIVERS:
        raise ValueError('Unsupported Turnip driver; choose 24.3.4 or 26.0.0')
    return DRIVERS[version]


def cache_paths(prefix, version):
    driver_file(version)
    # Preserve the baseline caches; the comparison never overwrites them.
    suffix = '' if version == DEFAULT_DRIVER else '-turnip-' + version
    mesa_suffix = '' if version == DEFAULT_DRIVER else '-' + version
    return prefix/'trasc-cache'/('dxvk'+suffix), prefix/'trasc-cache'/('mesa-turnip'+mesa_suffix)


def npc_configuration(mode):
    # Separate from CPU profile. These are supported by the pinned DXVK 2.5.3.
    # Thor testing rejected the 0.4.3 direct-mapping experiment: names still
    # glitch and NPCs regress. Restore the exact confirmed 0.4.2 baseline.
    # Keep direct mapping explicitly named for reproducing the isolated test.
    if mode == 'standard': return ''
    if mode not in ('compatibility', 'compatibility_042', 'direct_043'): raise ValueError('Invalid NPC rendering option')
    direct = 'True' if mode == 'direct_043' else 'False'
    return 'd3d9.floatEmulation = Strict; d3d9.forceSamplerTypeSpecConstants = True; d3d9.allowDirectBufferMapping = '+direct


def skin_shader_status(client):
    # The uploaded log names this one failing effect. Record presence/hash,
    # never invent a replacement shader or include proprietary bytes in logs.
    current = client
    for part in ('RenderEffects', 'SPL', 'SkinMeshCBS1_VSB.fxo'):
        if not current.is_dir(): return {'present': False}
        matches = [p for p in current.iterdir() if p.name.lower() == part.lower()]
        if len(matches) != 1 or matches[0].is_symlink(): return {'present': False, 'reason': 'missing_or_ambiguous'}
        current = matches[0]
    if not current.is_file(): return {'present': False}
    size = current.stat().st_size
    return {'present': True, 'bytes': size,
            'sha256': hashlib.sha256(current.read_bytes()).hexdigest() if size <= 1024*1024 else 'oversize'}


def verify_bundle(folder):
    manifest = json.loads((folder/'vulkan-bundle.json').read_text())
    if (manifest.get('format'), manifest.get('mesa'), manifest.get('dxvk'), manifest.get('architecture'), manifest.get('kmd')) != (2, DEFAULT_DRIVER, '2.5.3', 'arm64-glibc', 'kgsl') or manifest.get('drivers') != DRIVERS:
        raise RuntimeError('Unsupported bundled Turnip/DXVK version; reinstall the APK')
    if set(manifest.get('files', {})) != set(FILES): raise RuntimeError('Vulkan bundle file list is incomplete')
    for name in FILES:
        p = folder/name
        if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != manifest['files'][name]:
            raise RuntimeError('Vulkan bundle checksum failed: '+name)
        header = p.read_bytes()[:64]
        if name != 'dxvk-d3d9.dll' and (len(header) < 64 or header[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H',header,18)[0] != 183):
            raise RuntimeError('Vulkan native component is not ARM64: '+name)
    return manifest


def configure_environment(env, folder, session, prefix, version=DEFAULT_DRIVER):
    # This flag selects CPU-copy X11 presentation, NOT a software GPU driver.
    # Xtigervnc does not provide the DRM buffers Turnip's usual DRI3 path needs.
    # Rendering remains native Vulkan, proved by the hardware-only preflight.
    dxvk_cache, mesa_cache = cache_paths(prefix, version)
    env.update(VK_ICD_FILENAMES=str(session/'turnip-icd.json'),
               VK_DRIVER_FILES=str(session/'turnip-icd.json'), MESA_VK_WSI_DEBUG='sw',
               DXVK_LOG_LEVEL='info', DXVK_LOG_PATH='/logs', DXVK_HUD='devinfo,fps,compiler',
               DXVK_STATE_CACHE_PATH=str(dxvk_cache),
               MESA_SHADER_CACHE_DIR=str(mesa_cache), mesa_glthread='false')
    env['WINEDLLOVERRIDES'] += ';d3d9=n'
    if os.environ.get('TRASC_TEST_ALLOW_SOFTWARE_VULKAN') == '1':
        icd = os.environ['TRASC_TEST_VULKAN_ICD']
        env.update(VK_ICD_FILENAMES=icd, VK_DRIVER_FILES=icd)


def prepare_probe(folder, session, prefix, env, version=DEFAULT_DRIVER):
    filename = driver_file(version)
    manifest = verify_bundle(folder)
    (session/'turnip-icd.json').write_text(json.dumps({'file_format_version':'1.0.0', 'ICD':{
        'library_path':str(folder/filename), 'api_version':'1.3.0'}}))
    for path in cache_paths(prefix, version): path.mkdir(parents=True, exist_ok=True)
    args = [str(folder/'vulkan-probe')]
    # Only the isolated CI process can set these; Android's env -i never does.
    # No request/GUI field permits accepting a software device as Turnip.
    if os.environ.get('TRASC_TEST_ALLOW_SOFTWARE_VULKAN') == '1':
        icd = os.environ['TRASC_TEST_VULKAN_ICD']
        env.update(VK_ICD_FILENAMES=icd, VK_DRIVER_FILES=icd)
        args.append('--allow-software')
    return manifest, args


def parse_probe(text, allow_software=False, expected_mesa=None):
    reports = []
    for line in text.splitlines():
        try: reports.append(json.loads(line))
        except ValueError: pass
    if not reports: raise RuntimeError('Vulkan probe returned no device/presentation report')
    report = reports[-1]
    if report.get('presentation_frames') != 3: raise RuntimeError('Vulkan presentation was not verified')
    if report.get('api_version', 0) < (1<<22 | 3<<12): raise RuntimeError('DXVK requires Vulkan 1.3')
    if not allow_software and (report.get('driver_id') != 18 or report.get('vendor_id') != 0x5143 or report.get('software') is not False):
        raise RuntimeError('Turnip/Qualcomm hardware was not verified; software fallback rejected')
    if expected_mesa is not None and not allow_software:
        driver_file(expected_mesa)
        major, minor, patch = map(int, expected_mesa.split('.'))
        if report.get('driver_version') != (major<<22 | minor<<12 | patch):
            raise RuntimeError('The loaded Turnip version does not match the selected driver; stop and export Logs')
    return report


def install_d3d9(folder, prefix, client):
    # Keep imported files untouched and reject a DLL that would shadow our copy.
    if any(p.name.lower() == 'd3d9.dll' for p in client.iterdir()):
        raise RuntimeError('The imported client contains d3d9.dll, which would override bundled DXVK. Move that file to a backup with Files before using Turnip.')
    manifest = verify_bundle(folder)
    source = folder/'dxvk-d3d9.dll'
    target = prefix/'drive_c/windows/syswow64/d3d9.dll'
    backup = prefix/'trasc-renderers/wine-d3d9.dll'
    if not target.parent.is_dir(): raise RuntimeError('Prepare the 32-bit Wine prefix before DXVK')
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == manifest['files']['dxvk-d3d9.dll']:
        return manifest['files']['dxvk-d3d9.dll']
    backup.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and not backup.exists(): shutil.copyfile(target, backup)
    temporary = target.with_name('d3d9.trasc-new')
    shutil.copyfile(source, temporary); os.replace(temporary,target)
    return manifest['files']['dxvk-d3d9.dll']
