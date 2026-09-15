#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backend-assets runtime-work/vulkan-sources dist
docker build --platform linux/arm64 -t trasc-vulkan:1 vulkan
vulkan_container=$(docker create trasc-vulkan:1)
trap 'docker rm -f "$vulkan_container" >/dev/null 2>&1 || true' EXIT
docker cp "$vulkan_container:/out/." backend-assets/
docker cp "$vulkan_container:/build/mesa.tar.xz" runtime-work/vulkan-sources/mesa-24.3.4.tar.xz
curl -fL --retry 3 https://github.com/doitsujin/dxvk/releases/download/v2.5.3/dxvk-2.5.3.tar.gz -o runtime-work/dxvk-2.5.3.tar.gz
echo 'd8e6ef7d1168095165e1f8a98c7d5a4485b080467bb573d2a9ef3e3d79ea1eb8  runtime-work/dxvk-2.5.3.tar.gz' | sha256sum -c -
tar -xzf runtime-work/dxvk-2.5.3.tar.gz -C runtime-work
cp runtime-work/dxvk-2.5.3/x32/d3d9.dll backend-assets/dxvk-d3d9.dll
curl -fL --retry 3 https://codeload.github.com/doitsujin/dxvk/tar.gz/refs/tags/v2.5.3 -o runtime-work/vulkan-sources/dxvk-2.5.3.tar.gz
echo 'e3d8c320f1cbd134ce176be81a0c156585a1a251fd004c78d78373adff37f1ce  runtime-work/vulkan-sources/dxvk-2.5.3.tar.gz' | sha256sum -c -
cp -R vulkan runtime-work/vulkan-sources/
cp scripts/build-vulkan.sh runtime-work/vulkan-sources/
python3 - <<'PY'
import hashlib,json,pathlib
p=pathlib.Path('backend-assets')
m={'format':1,'mesa':'24.3.4','dxvk':'2.5.3','architecture':'arm64-glibc','kmd':'kgsl',
   'presentation':'x11-cpu-copy','files':{n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ('turnip.so','vulkan-probe','dxvk-d3d9.dll')}}
(p/'vulkan-bundle.json').write_text(json.dumps(m,indent=2)+'\n')
PY
tar -czf dist/vulkan-sources.tar.gz -C runtime-work/vulkan-sources .
