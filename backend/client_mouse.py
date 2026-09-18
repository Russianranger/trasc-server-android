"""Optional, exact-client camera recentering; never enable Wine's global force mode."""
import hashlib
from pathlib import Path

MARKER = 'TRASC_EQ_CAMERA_MOUSE_V1'
EXE_SHA256 = '4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3'


def launch_mode(request, client):
    if request.get('mode') != 'client' or not request.get('mouse_warp', False):
        return 'off'
    if not request.get('native_dinput8', True):
        return 'needs_dll'
    exe = client / request['executable']
    if not exe.is_file() or exe.stat().st_size != 8774656 or hashlib.sha256(exe.read_bytes()).hexdigest() != EXE_SHA256:
        return 'unsupported_executable'
    dlls = [p for p in client.iterdir() if p.name.lower() == 'dinput8.dll' and p.is_file() and not p.is_symlink()]
    if len(dlls) != 1 or dlls[0].stat().st_size > 64*1024**2 or MARKER.encode() not in dlls[0].read_bytes():
        return 'needs_dll'
    return 'enabled'


def prepare_sources(project, build):
    """Overlay only the forwarding methods. Imported sources stay byte-identical."""
    generated = build / 'camera-mouse'; generated.mkdir()
    header = Path(__file__).with_name('eq_camera_mouse.h')
    (generated / header.name).write_bytes(header.read_bytes())
    sources = {}
    for suffix in ('A', 'W'):
        name = f'IDirectInputDevice8{suffix}.cpp'
        source = project.parent / name
        content = source.read_text(encoding='utf-8-sig')
        original = (f'HRESULT m_IDirectInputDevice8{suffix}::GetDeviceState(DWORD cbData, LPVOID lpvData)\n'
                    '{\n\treturn ProxyInterface->GetDeviceState(cbData, lpvData);\n}')
        replacement = (f'HRESULT m_IDirectInputDevice8{suffix}::GetDeviceState(DWORD cbData, LPVOID lpvData)\n'
                       '{\n\tHRESULT result = ProxyInterface->GetDeviceState(cbData, lpvData);\n'
                       '\ttrasc_camera::afterRead(ProxyInterface, result, cbData);\n\treturn result;\n}')
        if content.count(original) != 1 or content.count('#include "dinput8.h"') != 1:
            raise ValueError('Client mouse wrapper changed; review the camera adapter before compiling: ' + name)
        content = content.replace('#include "dinput8.h"', '#include "dinput8.h"\n#include "eq_camera_mouse.h"')
        target = generated / name
        target.write_text('// Altered by TRASC: optional camera-only recentering after input delivery.\n' + content.replace(original, replacement), encoding='utf-8')
        sources[name] = target
    return sources
