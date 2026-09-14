#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
task_dir="$PWD/runtime-work/client-proot"
mkdir -p "$task_dir"
sudo apt-get update
sudo apt-get install -y build-essential libtalloc-dev gawk
git clone https://github.com/termux/proot.git "$task_dir/proot"
git -C "$task_dir/proot" checkout 7266fb3e8516535682f5a9c8f3a7e70f6506eddb
sed -i '1i#include <string.h>' "$task_dir/proot/src/extension/ashmem_memfd/ashmem_memfd.c"
make -C "$task_dir/proot/src" -j2 PROOT_UNBUNDLE_LOADER=/unused HAS_LOADER_32BIT=
mkdir -p "$task_dir/classes" "$task_dir/root" "$task_dir/client" "$task_dir/prefix" "$task_dir/session" "$task_dir/tmp" "$task_dir/logs"
javac -d "$task_dir/classes" tests/java/android/system/Os.java app/src/main/java/io/github/russianranger/trasc/TarExtractor.java tests/java/io/github/russianranger/trasc/ExtractRuntimeHost.java
java -cp "$task_dir/classes" io.github.russianranger.trasc.ExtractRuntimeHost dist/client-runtime-arm64.tar.gz "$task_dir/root"
cp runtime-work/client-test/client/eqgame.exe runtime-work/client-test/client/dinput8.dll "$task_dir/client/"
PROOT_LOADER="$task_dir/proot/src/loader/loader" PROOT_NO_SECCOMP=1 PROOT_TMP_DIR="$task_dir/tmp" \
timeout 300 "$task_dir/proot/src/proot" --kill-on-exit -0 -r "$task_dir/root" \
    -b /dev -b /proc -b "$PWD/backend:/opt/trasc-client" -b "$PWD/tests:/tests" \
    -b "$task_dir/client:/client" -b "$task_dir/prefix:/prefix" -b "$task_dir/session:/session" \
    -b "$task_dir/tmp:/tmp" -b "$task_dir/logs:/logs" -w /client \
    /usr/bin/env -i HOME=/root USER=root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 TMPDIR=/tmp PYTHONUNBUFFERED=1 /usr/bin/python3 /tests/integration_client.py
