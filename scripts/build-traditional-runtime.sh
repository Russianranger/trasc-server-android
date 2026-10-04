#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
mkdir -p dist/traditional runtime-work/traditional
docker build --platform linux/arm64 -t trasc-traditional-runtime:1 runtime/traditional
container_id="$(docker create --platform linux/arm64 trasc-traditional-runtime:1)"
trap 'docker rm -f "$container_id" >/dev/null 2>&1 || true' EXIT
docker export "$container_id" -o runtime-work/traditional/rootfs.tar
python3 scripts/pack-runtime.py runtime-work/traditional/rootfs.tar dist/traditional/runtime-arm64.tar.gz \
    --runtime traditional-1.0 --profile traditional --build-adapter 1
