#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
native_dir="$repo_root/runtime-work/native"
out="$repo_root/dist/launcher-source"
mkdir -p "$out"
git -C "$native_dir/proot" archive 7266fb3e8516535682f5a9c8f3a7e70f6506eddb | gzip > "$out/proot-source.tar.gz"
git -C "$native_dir/proot" diff > "$out/proot-android.patch"
cp "$native_dir/talloc.tar.gz" "$out/talloc-2.4.3.tar.gz"
cp "$repo_root/scripts/build-proot.sh" "$out/"
cp "$native_dir/cabextract-1.11.tar.gz" "$out/"
cp "$repo_root/scripts/build-cabextract.sh" "$out/"
cp "$native_dir/virglrenderer-1.3.0.tar.gz" "$native_dir/libepoxy-1.5.10.tar.gz" "$out/"
cp "$repo_root/scripts/build-virgl.sh" "$out/"
cp -r "$repo_root/native" "$out/"
cp "$repo_root/dist/wined3d-sources.tar.gz" "$out/"
cp "$repo_root/THIRD_PARTY_NOTICES.md" "$out/"
tar -czf "$repo_root/dist/launcher-sources.tar.gz" -C "$repo_root/dist" launcher-source
