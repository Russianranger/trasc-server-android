#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
verify_dir="$(mktemp -d)"
trap 'rm -rf "$verify_dir"' EXIT
javac -d "$verify_dir/classes" \
    "$repo_root/tests/java/android/system/Os.java" \
    "$repo_root/tests/java/io/github/russianranger/trasc/TarHostTest.java" \
    "$repo_root/app/src/main/java/io/github/russianranger/trasc/TarExtractor.java"
java -cp "$verify_dir/classes" io.github.russianranger.trasc.TarHostTest "${1:?Pass runtime-arm64.tar.gz}" "$verify_dir/rootfs"
