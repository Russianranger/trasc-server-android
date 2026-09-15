#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
renderer="${1:-software}"
acceleration="${2:-auto}"
case "$acceleration" in auto|compatibility) ;; *) exit 2 ;; esac
case "$renderer" in
    software) task_dir="$PWD/runtime-work/client-proot" ;;
    virgl) task_dir="$PWD/runtime-work/gpu-proot" ;;
    turnip) task_dir="$PWD/runtime-work/vulkan-proot" ;;
    *) echo 'Expected software, virgl or turnip renderer' >&2; exit 2 ;;
esac
mkdir -p "$task_dir"
sudo apt-get update
sudo apt-get install -y build-essential libtalloc-dev gawk
git clone https://github.com/termux/proot.git "$task_dir/proot"
git -C "$task_dir/proot" checkout 7266fb3e8516535682f5a9c8f3a7e70f6506eddb
git -C "$task_dir/proot" apply "$PWD/native/proot-acceleration.patch"
sed -i '1i#include <string.h>' "$task_dir/proot/src/extension/ashmem_memfd/ashmem_memfd.c"
make -C "$task_dir/proot/src" -j2 PROOT_UNBUNDLE_LOADER=/unused HAS_LOADER_32BIT=
mkdir -p "$task_dir/classes" "$task_dir/root" "$task_dir/client" "$task_dir/prefix" "$task_dir/session" "$task_dir/tmp" "$task_dir/logs"
javac -d "$task_dir/classes" tests/java/android/system/Os.java app/src/main/java/io/github/russianranger/trasc/TarExtractor.java tests/java/io/github/russianranger/trasc/ExtractRuntimeHost.java
java -cp "$task_dir/classes" io.github.russianranger.trasc.ExtractRuntimeHost "${TRASC_TEST_ROOTFS:-dist/client-runtime-arm64.tar.gz}" "$task_dir/root"
mkdir -p "$task_dir/root/directx"
cp runtime-work/client-test/client/eqgame.exe runtime-work/client-test/client/dinput8.dll runtime-work/client-test/client/models.exe runtime-work/client-test/client/textures.exe "$task_dir/client/"
if [ "$renderer" = virgl ]; then
    LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe runtime-work/native/virgl-host/out/vtest/virgl_test_server \
        --use-egl-surfaceless --use-gles --multi-clients --socket-path "$task_dir/tmp/.virgl_test" > "$task_dir/logs/client-gpu.log" 2>&1 &
    graphics_pid=$!
    trap 'kill "$graphics_pid" 2>/dev/null || true; wait "$graphics_pid" 2>/dev/null || true' EXIT
    for i in $(seq 1 100); do test -S "$task_dir/tmp/.virgl_test" && break; sleep .1; done
    test -S "$task_dir/tmp/.virgl_test"
fi
if [ "$acceleration" = compatibility ]; then export PROOT_NO_SECCOMP=1; else unset PROOT_NO_SECCOMP; fi
export TRASC_PROOT_REPORT=1
export PROOT_LOADER="$task_dir/proot/src/loader/loader" PROOT_TMP_DIR="$task_dir/tmp"
vulkan_test_env=()
if [ "$renderer" = turnip ]; then
    vulkan_test_env=(TRASC_TEST_ALLOW_SOFTWARE_VULKAN=1 TRASC_TEST_VULKAN_ICD=/usr/share/vulkan/icd.d/lvp_icd.aarch64.json)
fi
client_command=("$task_dir/proot/src/proot" --kill-on-exit -0 -r "$task_dir/root" \
    -b "$PWD/runtime-work/directx-test/output/directx:/directx" \
    -b "$PWD/backend-assets/wineserver:/opt/wine/bin/wineserver" \
    -b "$PWD/backend-assets/wined3d.dll:/opt/wine/lib/wine/i386-windows/wined3d.dll" \
    -b /dev -b /proc -b /sys -b "$PWD/backend:/opt/trasc-client" -b "$PWD/tests:/tests" \
    -b "$task_dir/client:/client" -b "$task_dir/prefix:/prefix" -b "$task_dir/session:/session" \
    -b "$task_dir/tmp:/tmp" -b "$task_dir/logs:/logs" -w /client \
    /usr/bin/env -i HOME=/root USER=root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 TMPDIR=/tmp PYTHONUNBUFFERED=1 TRASC_TEST_RENDERER="$renderer" "${vulkan_test_env[@]}" /usr/bin/python3)
timeout 20 "${client_command[@]}" /opt/trasc-client/runtime_probe.py 2>&1 | tee "$task_dir/logs/client-runtime-probe.log"
if [ "$acceleration" = auto ]; then
    grep -q "TRASC PRoot: seccomp acceleration observed" "$task_dir/logs/client-runtime-probe.log"
fi
timeout 300 "${client_command[@]}" /tests/integration_client.py 2>&1 | tee "$task_dir/logs/client-proot.log"
if [ "$acceleration" = auto ]; then
    grep -q "TRASC PRoot: seccomp acceleration observed" "$task_dir/logs/client-proot.log"
fi
