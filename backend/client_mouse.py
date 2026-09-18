"""Optional, exact-client camera recentering; never enable Wine's global force mode."""
import hashlib
from pathlib import Path

MARKER = 'TRASC_EQ_CAMERA_MOUSE_V2'
LOADING_MARKER = 'TRASC_EQ_LOAD_V1'
EXE_SHA256 = '4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3'


def launch_mode(request, client):
    if request.get('mode') != 'client' or not request.get('mouse_warp', False):
        return 'off'
    return adapter_mode(request, client, MARKER)


def loading_mode(request, client):
    if request.get('mode') != 'client': return 'off'
    mode = adapter_mode(request, client, LOADING_MARKER)
    return ('fast' if request.get('fast_spell_parse', False) else 'profile') if mode == 'enabled' else mode


def adapter_mode(request, client, marker):
    if not request.get('native_dinput8', True):
        return 'needs_dll'
    exe = client / request['executable']
    if not exe.is_file() or exe.stat().st_size != 8774656 or hashlib.sha256(exe.read_bytes()).hexdigest() != EXE_SHA256:
        return 'unsupported_executable'
    dlls = [p for p in client.iterdir() if p.name.lower() == 'dinput8.dll' and p.is_file() and not p.is_symlink()]
    if len(dlls) != 1 or dlls[0].stat().st_size > 64*1024**2 or marker.encode() not in dlls[0].read_bytes():
        return 'needs_dll'
    return 'enabled'


def prepare_sources(project, build):
    """Overlay input forwarding/startup only. Imported sources stay byte-identical."""
    generated = build / 'camera-mouse'; generated.mkdir()
    for name in ('eq_camera_mouse.h', 'eq_client_loading.h', 'eq_fast_decimal.h'):
        header = Path(__file__).with_name(name)
        (generated / name).write_bytes(header.read_bytes())
    sources = {}
    for suffix in ('A', 'W'):
        name = f'IDirectInputDevice8{suffix}.cpp'
        source = project.parent / name
        content = source.read_text(encoding='utf-8-sig')
        original = (f'HRESULT m_IDirectInputDevice8{suffix}::GetDeviceState(DWORD cbData, LPVOID lpvData)\n'
                    '{\n\treturn ProxyInterface->GetDeviceState(cbData, lpvData);\n}')
        replacement = (f'HRESULT m_IDirectInputDevice8{suffix}::GetDeviceState(DWORD cbData, LPVOID lpvData)\n'
                       '{\n\tHRESULT result = ProxyInterface->GetDeviceState(cbData, lpvData);\n'
                       '\ttrasc_camera::afterRead(ProxyInterface, result, cbData, lpvData);\n\treturn result;\n}')
        if content.count(original) != 1 or content.count('#include "dinput8.h"') != 1:
            raise ValueError('Client mouse wrapper changed; review the camera adapter before compiling: ' + name)
        content = content.replace('#include "dinput8.h"', '#include "dinput8.h"\n#include "eq_camera_mouse.h"')
        target = generated / name
        target.write_text('// Altered by TRASC: optional camera-only recentering after input delivery.\n' + content.replace(original, replacement), encoding='utf-8')
        sources[name] = target
    name = 'eqgame.cpp'
    content = (project.parent / name).read_text(encoding='utf-8-sig')
    original = ('HRESULT WINAPI DirectInput8Create(HINSTANCE hinst, DWORD dwVersion,\n'
                '                                  REFIID riidltf, LPVOID *ppvOut,\n'
                '                                  LPUNKNOWN punkOuter) {')
    if content.count(original) != 1:
        raise ValueError('Client loading entry changed; review before compiling: ' + name)
    target = generated / name
    # Include after upstream Windows/DirectInput declarations, before the export.
    target.write_text('// Altered by TRASC: optional measured spell loading.\n' + content.replace(
        original, '#include "eq_client_loading.h"\n\n' + original + '\n  trasc_loading::install();'), encoding='utf-8')
    sources[name] = target
    return sources
