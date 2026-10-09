#!/usr/bin/env bash
set -euo pipefail
mkdir -p backend-assets runtime-work/traditional-camera
i686-w64-mingw32-g++ -std=c++14 -O2 -Wall -Wextra -Werror -Wno-cast-function-type \
  -static -static-libgcc -static-libstdc++ -shared native/traditional_camera_proxy.cpp \
  native/traditional_camera_proxy.def -o backend-assets/trasc-camera-dinput8.dll \
  -Wl,--no-insert-timestamp -Wl,--kill-at -Wl,--enable-stdcall-fixup -luser32 -ldxguid
i686-w64-mingw32-objdump -p backend-assets/trasc-camera-dinput8.dll > runtime-work/traditional-camera/pe.txt
python3 - <<'PY'
import hashlib,json,pathlib,re,struct
binary=pathlib.Path('backend-assets/trasc-camera-dinput8.dll');raw=binary.read_bytes()
offset=struct.unpack_from('<I',raw,60)[0]
assert raw[:2]==b'MZ' and raw[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',raw,offset+4)[0]==0x14c
assert b'TRASC_TRADITIONAL_CAMERA_ONLY_V1' in raw and b'TRASC_EQ_CAMERA_MOUSE_V2' in raw
text=pathlib.Path('runtime-work/traditional-camera/pe.txt').read_text()
exports={'DirectInput8Create','DllCanUnloadNow','DllGetClassObject','DllRegisterServer','DllUnregisterServer'}
assert all(re.search(r'\]\s+'+name+r'\s*$',text,re.M) for name in exports)
imports=set(re.findall(r'DLL Name:\s+(\S+)',text))
assert imports <= {'KERNEL32.dll','msvcrt.dll','USER32.dll'},imports
receipt={'adapter':'traditional-camera-only-v1','file':binary.name,'sha256':hashlib.sha256(raw).hexdigest(),
 'executable_sha256':'4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3',
 'source_sha256':{name:hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest() for name in
  ('native/traditional_camera_proxy.cpp','native/traditional_camera_proxy.def','backend/eq_camera_mouse.h')},
 'machine':'x86','imports':sorted(imports),'exports':sorted(exports)}
pathlib.Path('backend-assets/traditional-camera-bundle.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('PASS: standalone camera PE32, exports, system-only imports and source receipt')
PY
