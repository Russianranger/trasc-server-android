#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
mkdir -p dist runtime-work
docker build --platform linux/arm64 -t trasc-runtime:1 runtime
container_id="$(docker create --platform linux/arm64 trasc-runtime:1)"
trap 'docker rm -f "$container_id" >/dev/null 2>&1 || true' EXIT
docker export "$container_id" -o runtime-work/rootfs.tar
python3 scripts/pack-runtime.py runtime-work/rootfs.tar dist/runtime-arm64.tar.gz
