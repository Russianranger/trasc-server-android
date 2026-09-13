#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist runtime-work/client-sources
docker build --platform linux/arm64 -t trasc-client:1 client-runtime
client_container=$(docker create --platform linux/arm64 trasc-client:1)
trap 'docker rm -f "$client_container" >/dev/null 2>&1 || true' EXIT
docker export "$client_container" -o runtime-work/client-rootfs.tar
# Same strict GNU tar subset as the existing, device-tested runtime installer.
python3 scripts/pack-runtime.py runtime-work/client-rootfs.tar dist/client-runtime-arm64.tar.gz
python3 - <<'PY'
import json,pathlib
p=pathlib.Path('dist/runtime-manifest.json')
m=json.loads(p.read_text());m.update(runtime='client-1.0',wine='10.0-wow64',box64='0.4.4',renderer='wined3d-llvmpipe')
pathlib.Path('dist/client-runtime-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
p.unlink()
PY
# Corresponding upstream sources and exact recipe accompany the binaries.
curl -fL --retry 3 -o runtime-work/client-sources/wine-10.0.tar.xz https://dl.winehq.org/wine/source/10.0/wine-10.0.tar.xz
curl -fL --retry 3 -o runtime-work/client-sources/box64.tar.gz https://codeload.github.com/ptitSeb/box64/tar.gz/2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a
cp client-runtime/Dockerfile runtime-work/client-sources/
cp scripts/build-client-runtime.sh runtime-work/client-sources/
tar -czf dist/client-runtime-sources.tar.gz -C runtime-work/client-sources .
