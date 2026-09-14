#!/usr/bin/env bash
# Build the matching Wine 10 PE32 module; never replace the Wine/Box64 runtime.
set -euo pipefail
cd "$(dirname "$0")/.."
work="$PWD/runtime-work/wined3d"
mkdir -p "$work" backend-assets dist
curl -fL --retry 3 --max-time 180 https://dl.winehq.org/wine/source/10.0/wine-10.0.tar.xz -o "$work/wine-10.0.tar.xz"
echo "c5e0b3f5f7efafb30e9cd4d9c624b85c583171d33549d933cd3402f341ac3601  $work/wine-10.0.tar.xz" | sha256sum -c -
tar -xJf "$work/wine-10.0.tar.xz" -C "$work"
patch -d "$work/wine-10.0" -p1 < native/wine-patches/0001-legacy-specular-fog.patch
mkdir -p "$work/build"
(cd "$work/build" && ../wine-10.0/configure --enable-win64 --enable-archs=i386,x86_64 --without-x --without-wayland --without-vulkan && make -j2 dlls/wined3d/i386-windows/wined3d.dll)
cp "$work/build/dlls/wined3d/i386-windows/wined3d.dll" backend-assets/wined3d.dll
i686-w64-mingw32-strip backend-assets/wined3d.dll
python3 - <<'PY'
import hashlib,json,pathlib,struct
p=pathlib.Path('backend-assets/wined3d.dll');b=p.read_bytes();pe=struct.unpack_from('<I',b,0x3c)[0]
assert b[:2]==b'MZ' and b[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',b,pe+4)[0]==0x14c
pathlib.Path('backend-assets/wined3d-patch.json').write_text(json.dumps({'wine':'10.0','architecture':'i386','patch':'legacy-specular-fog-v1','sha256':hashlib.sha256(b).hexdigest()},indent=2)+'\n')
PY
# LGPL corresponding source, patch and complete build recipe travel together.
tar -czf dist/wined3d-sources.tar.gz scripts/build-wined3d.sh native/wine-patches .github/workflows/wined3d.yml -C runtime-work/wined3d wine-10.0.tar.xz
