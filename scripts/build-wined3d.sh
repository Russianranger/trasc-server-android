#!/usr/bin/env bash
# Build matching Wine 10 helpers; the installed runtime image stays intact.
set -euo pipefail
cd "$(dirname "$0")/.."
work="$PWD/runtime-work/wined3d"
mkdir -p "$work" backend-assets dist
curl -fL --retry 3 --max-time 180 https://dl.winehq.org/wine/source/10.0/wine-10.0.tar.xz -o "$work/wine-10.0.tar.xz"
echo "c5e0b3f5f7efafb30e9cd4d9c624b85c583171d33549d933cd3402f341ac3601  $work/wine-10.0.tar.xz" | sha256sum -c -
tar -xJf "$work/wine-10.0.tar.xz" -C "$work"
patch -d "$work/wine-10.0" -p1 < native/wine-patches/0001-legacy-specular-fog.patch
mkdir -p "$work/build"
(cd "$work/build" && ../wine-10.0/configure --enable-win64 --enable-archs=i386,x86_64 --without-freetype --without-x --without-wayland --without-vulkan && make -j2 dlls/wined3d/i386-windows/wined3d.dll)
cp "$work/build/dlls/wined3d/i386-windows/wined3d.dll" backend-assets/wined3d.dll
i686-w64-mingw32-strip backend-assets/wined3d.dll
# Build only the Wine server in Bookworm to preserve glibc compatibility.
mkdir -p "$work/server-context"
cp "$work/wine-10.0.tar.xz" native/wine-patches/0002-translated-exit-grace.patch "$work/server-context/"
docker build -f native/wineserver.Dockerfile -t trasc-wineserver-exit:1 "$work/server-context"
server_container=$(docker create trasc-wineserver-exit:1 /bin/true)
trap 'docker rm -f "$server_container" >/dev/null 2>&1 || true' EXIT
docker cp "$server_container:/src/build/server/wineserver" backend-assets/wineserver
chmod +x backend-assets/wineserver
python3 - <<'PY'
import hashlib,json,pathlib,struct
p=pathlib.Path('backend-assets/wined3d.dll');b=p.read_bytes();pe=struct.unpack_from('<I',b,0x3c)[0]
assert b[:2]==b'MZ' and b[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',b,pe+4)[0]==0x14c
pathlib.Path('backend-assets/wined3d-patch.json').write_text(json.dumps({'wine':'10.0','architecture':'i386','patch':'legacy-specular-fog-v1','sha256':hashlib.sha256(b).hexdigest()},indent=2)+'\n')
p=pathlib.Path('backend-assets/wineserver');b=p.read_bytes()
assert b[:6]==b'\x7fELF\x02\x01' and struct.unpack_from('<H',b,18)[0]==62
pathlib.Path('backend-assets/wineserver-patch.json').write_text(json.dumps({'wine':'10.0','architecture':'x86_64-glibc','patch':'translated-exit-grace-v1','exit_grace_seconds':8,'sha256':hashlib.sha256(b).hexdigest()},indent=2)+'\n')
PY
# LGPL corresponding source, patch and complete build recipe travel together.
tar -czf dist/wined3d-sources.tar.gz scripts/build-wined3d.sh native/wineserver.Dockerfile native/wine-patches .github/workflows/wined3d.yml -C runtime-work/wined3d wine-10.0.tar.xz
