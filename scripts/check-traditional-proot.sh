#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
archive="$(realpath "${1:?Pass the Traditional runtime archive}")"
qualification_work="$(realpath "${2:?Pass the native Engine qualification workspace}")"
task_dir="$repo_root/runtime-work/traditional-proot"
evidence_dir="$qualification_work/traditional-proot-evidence"
case "$(uname -m)" in aarch64|arm64) ;; *) echo 'This qualification requires a native ARM64 runner' >&2; exit 2 ;; esac
test -f "$qualification_work/server/bin.staged/verification.json"
mkdir -p "$task_dir" "$evidence_dir"
sudo apt-get update
sudo apt-get install -y build-essential libtalloc-dev gawk
if [ ! -d "$task_dir/proot/.git" ]; then
    git clone https://github.com/termux/proot.git "$task_dir/proot"
fi
git -C "$task_dir/proot" checkout 7266fb3e8516535682f5a9c8f3a7e70f6506eddb
for patch_file in proot-acceleration.patch proot-sysvipc.patch; do
    if git -C "$task_dir/proot" apply --check "$repo_root/native/$patch_file"; then
        git -C "$task_dir/proot" apply "$repo_root/native/$patch_file"
    else
        git -C "$task_dir/proot" apply --reverse --check "$repo_root/native/$patch_file"
    fi
done
python3 - "$task_dir/proot/src/extension/ashmem_memfd/ashmem_memfd.c" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
if '#include <string.h>' not in text:
    path.write_text('#include <string.h>\n' + text)
PY
make -C "$task_dir/proot/src" -j2 PROOT_UNBUNDLE_LOADER=/unused HAS_LOADER_32BIT=
rootfs_dir="$(mktemp -d "$task_dir/root.XXXXXX")"
proot_tmp_dir="$(mktemp -d /tmp/trasc-tradproot.XXXXXX)"
hidden_build="$(mktemp -d "$task_dir/hidden-build.XXXXXX")"
restore() {
    if [ -d "$hidden_build/builds" ]; then mv "$hidden_build/builds" "$qualification_work/builds"; fi
    rmdir "$hidden_build" 2>/dev/null || true
    rm -rf "$proot_tmp_dir" "$rootfs_dir"
}
trap restore EXIT
mkdir -p "$task_dir/classes"
javac -d "$task_dir/classes" "$repo_root/tests/java/android/system/Os.java" \
    "$repo_root/app/src/main/java/io/github/russianranger/trasc/TarExtractor.java" \
    "$repo_root/tests/java/io/github/russianranger/trasc/ExtractRuntimeHost.java"
java -cp "$task_dir/classes" io.github.russianranger.trasc.ExtractRuntimeHost "$archive" "$rootfs_dir"
mkdir -p "$rootfs_dir/work" "$rootfs_dir/opt/trasc" "$rootfs_dir/tests" "$rootfs_dir/evidence" "$rootfs_dir/tmp"
printf '127.0.0.1 localhost\n::1 localhost ip6-localhost ip6-loopback\n' > "$rootfs_dir/etc/hosts"
# Staged executables must load after their entire compilation tree is hidden.
if [ -d "$qualification_work/builds" ]; then mv "$qualification_work/builds" "$hidden_build/builds"; fi
export PROOT_NO_SECCOMP=1
export PROOT_LOADER="$task_dir/proot/src/loader/loader" PROOT_TMP_DIR="$proot_tmp_dir"
guest=("$task_dir/proot/src/proot" --kill-on-exit -0 -r "$rootfs_dir" \
    -b /dev -b /proc -b "$qualification_work:/work" \
    -b "$repo_root/backend:/opt/trasc" -b "$repo_root/tests:/tests" \
    -b "$evidence_dir:/evidence" -b "$proot_tmp_dir:/tmp" -w /work \
    /usr/bin/env -i HOME=/root USER=root \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 TMPDIR=/tmp PYTHONUNBUFFERED=1 /usr/bin/python3)
timeout 420 "${guest[@]}" /tests/integration_traditional_toolchain.py \
    --output /evidence/toolchain.json 2>&1 | tee "$evidence_dir/toolchain.log"
timeout 120 "${guest[@]}" /opt/trasc/traditional_verify.py \
    /work/server/bin.staged /evidence/staged 2>&1 | tee "$evidence_dir/staged-verification.log"
python3 - "$qualification_work/server/bin.staged/verification.json" "$evidence_dir/staged/binary-verification.json" <<'PY'
import json
from pathlib import Path
import sys
native, proot = (json.loads(Path(name).read_text()) for name in sys.argv[1:])
assert native['binaries'] == proot['binaries'], 'PRoot binary metadata differs from native qualification'
assert native['abi_libraries'] == proot['abi_libraries'], 'PRoot quest-parser ABI differs from native qualification'
assert proot['providers'] == {'default': True, 'legacy': True, 'des_cbc': True}
print('Packaged Traditional runtime passed PRoot compiler, file mmap/lockf and staged-binary qualification')
PY
