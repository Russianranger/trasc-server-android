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
git -C "$task_dir/proot" apply "$PWD/native/proot-sysvipc.patch"
sed -i '1i#include <string.h>' "$task_dir/proot/src/extension/ashmem_memfd/ashmem_memfd.c"
make -C "$task_dir/proot/src" -j2 PROOT_UNBUNDLE_LOADER=/unused HAS_LOADER_32BIT=
mkdir -p "$task_dir/classes" "$task_dir/root" "$task_dir/client" "$task_dir/prefix" "$task_dir/session" "$task_dir/tmp" "$task_dir/logs"
javac -d "$task_dir/classes" tests/java/android/system/Os.java app/src/main/java/io/github/russianranger/trasc/TarExtractor.java tests/java/io/github/russianranger/trasc/ExtractRuntimeHost.java
java -cp "$task_dir/classes" io.github.russianranger.trasc.ExtractRuntimeHost "${TRASC_TEST_ROOTFS:-dist/client-runtime-arm64.tar.gz}" "$task_dir/root"
mkdir -p "$task_dir/root/directx"
cp runtime-work/client-test/client/command-keys.txt runtime-work/client-test/client/audio.exe runtime-work/client-test/client/eqgame.exe runtime-work/client-test/client/dinput8.dll runtime-work/client-test/client/models.exe runtime-work/client-test/client/textures.exe "$task_dir/client/"
# The SysV helper uses a filesystem Unix socket (108-byte path limit).
# Keep its private host directory short even in deeply nested CI checkouts.
proot_tmp_dir=$(mktemp -d /tmp/trasc-proot.XXXXXX)
trap 'if [ -n "${graphics_pid:-}" ]; then kill "$graphics_pid" 2>/dev/null || true; wait "$graphics_pid" 2>/dev/null || true; fi; rm -rf "$proot_tmp_dir"' EXIT
if [ "$renderer" = virgl ]; then
    LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe runtime-work/native/virgl-host/out/vtest/virgl_test_server \
        --use-egl-surfaceless --use-gles --multi-clients --socket-path "$task_dir/tmp/.virgl_test" > "$task_dir/logs/client-gpu.log" 2>&1 &
    graphics_pid=$!
    for i in $(seq 1 100); do test -S "$task_dir/tmp/.virgl_test" && break; sleep .1; done
    test -S "$task_dir/tmp/.virgl_test"
fi
if [ "$acceleration" = compatibility ]; then export PROOT_NO_SECCOMP=1; else unset PROOT_NO_SECCOMP; fi
export TRASC_PROOT_REPORT=1
export PROOT_LOADER="$task_dir/proot/src/loader/loader" PROOT_TMP_DIR="$proot_tmp_dir"
vulkan_test_env=()
if [ "$renderer" = turnip ]; then
    vulkan_test_env=(TRASC_TEST_ALLOW_SOFTWARE_VULKAN=1 TRASC_TEST_VULKAN_ICD=/usr/share/vulkan/icd.d/lvp_icd.aarch64.json)
fi
client_command=("$task_dir/proot/src/proot" --kill-on-exit --sysvipc -0 -r "$task_dir/root" \
    -b "$PWD/runtime-work/directx-test/output/directx:/directx" \
    -b "$PWD/backend/wineserver:/opt/wine/bin/wineserver" \
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
grep -q "TRASC PRoot: SysV shared memory uses memfd" "$task_dir/logs/client-proot.log"
if [ "$acceleration" = auto ]; then
    grep -q "TRASC PRoot: seccomp acceleration observed" "$task_dir/logs/client-proot.log"
fi
if [ "$renderer" = software ]; then
    # Existing checks use a short host PROOT_TMP_DIR. Reproduce the Android
    # Traditional layout before requiring the compact, profile-specific fix.
    python3 - "$task_dir" "$PWD" <<'PYPATH'
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

task, repository = map(Path, sys.argv[1:])
logs = task / 'logs'
fixture = Path(tempfile.mkdtemp(prefix='trasc-unix-', dir='/tmp')).resolve()
# Match the canonical preview Android app-data path's 50 bytes without
# depending on this checkout's length or creating a host /data directory.
app = fixture / ('a' * (50 - len(os.fsencode(fixture)) - 1))
assert len(os.fsencode(app)) == 50
old_tmp = app / 'files/profiles/traditional/tmp/client/tmp'
traditional_tmp, custom_tmp = app / 't', app / 'c'
prefix = app / 'files/profiles/traditional/work/client/prefix'
for path in (old_tmp, traditional_tmp / 's', custom_tmp / 's', prefix):
    path.mkdir(parents=True)
prefix_identity = (prefix.stat().st_dev, prefix.stat().st_ino)
evidence = {'old_tmp_bytes': len(os.fsencode(old_tmp)),
            'compact_tmp_bytes': len(os.fsencode(traditional_tmp)), 'checks': {}}
assert evidence['old_tmp_bytes'] == 92 and evidence['compact_tmp_bytes'] == 52

def run(label, tmp, command, timeout=30):
    args = [str(task / 'proot/src/proot'), '--kill-on-exit', '--sysvipc', '-0',
            '-r', str(task / 'root'), '-b', '/dev', '-b', '/proc', '-b', '/sys',
            '-b', str(repository / 'backend/wineserver') + ':/opt/wine/bin/wineserver',
            '-b', str(prefix) + ':/prefix', '-b', str(tmp) + ':/tmp',
            '-b', str(tmp / 's') + ':/session', '-w', '/', '/usr/bin/env', '-i',
            'HOME=/root', 'USER=root', 'PATH=/usr/local/bin:/usr/bin:/bin',
            'LANG=C.UTF-8', 'TMPDIR=/tmp', 'WINEPREFIX=/prefix', 'WINEARCH=win64',
            'WINEDEBUG=-all', 'WINEDLLOVERRIDES=winemenubuilder,mscoree,mshtml=',
            'BOX64_LOG=1', 'BOX64_DYNAREC_STRONGMEM=1', 'BOX64_DYNAREC_BIGBLOCK=0',
            'BOX64_DYNAREC_SAFEFLAGS=2', 'BOX64_PATH=/opt/wine/bin',
            'BOX64_LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/opt/wine/lib/wine/x86_64-unix']
    output = logs / ('client-unix-path-' + label + '.log')
    with output.open('wb') as stream:
        child = subprocess.run(args + command, env=dict(os.environ, PROOT_TMP_DIR=str(tmp)),
                               stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    text = output.read_text(errors='replace')
    evidence['checks'][label] = {'returncode': child.returncode, 'log': output.name}
    return child.returncode, text

shared_memory = r'''
import ctypes
import os
libc = ctypes.CDLL(None, use_errno=True)
libc.shmat.restype = ctypes.c_void_p
libc.shmdt.argtypes = [ctypes.c_void_p]
segment = libc.shmget(0, 4096, 0o1000 | 0o600)
assert segment >= 0, ('shmget', ctypes.get_errno())
address = libc.shmat(segment, None, 0)
assert address != ctypes.c_void_p(-1).value, ('shmat', ctypes.get_errno())
try:
    ctypes.memmove(address, b'compact-proot', 13)
    assert ctypes.string_at(address, 13) == b'compact-proot'
finally:
    assert libc.shmdt(address) == 0
    assert libc.shmctl(segment, 0, None) == 0
print('TRASC_COMPACT_SYSV_OK', flush=True)
'''
socket_alias = r'''
import socket
from pathlib import Path
directory = Path('/tmp') / ('wineserver-' + 'x' * 75)
directory.mkdir()
name = str(directory / 'socket')
assert len(name.encode()) < 108
with socket.socket(socket.AF_UNIX) as server, socket.socket(socket.AF_UNIX) as client:
    server.bind(name)
    server.listen(1)
    client.connect(name)
    peer, _ = server.accept()
    with peer:
        client.sendall(b'compact-socket')
        assert peer.recv(32) == b'compact-socket'
Path(name).unlink()
directory.rmdir()
print('TRASC_COMPACT_SOCKET_ALIAS_OK', flush=True)
'''
wine = r'''
import os
from pathlib import Path
import struct
import subprocess
import time
wine = ['/usr/local/bin/box64', '/opt/wine/bin/wine']
server = ['/usr/local/bin/box64', '/opt/wine/bin/wineserver']
display = subprocess.Popen(['Xtigervnc', ':9', '-geometry', '640x480', '-depth', '24',
                            '-rfbport', '-1', '-nolisten', 'tcp'])
try:
    deadline = time.monotonic() + 15
    while not Path('/tmp/.X11-unix/X9').is_socket():
        assert display.poll() is None and time.monotonic() < deadline
        time.sleep(.1)
    env = dict(os.environ, DISPLAY=':9')
    subprocess.run(wine + ['wineboot', '-u'], env=env, timeout=120, check=True)
    command = Path('/prefix/drive_c/windows/syswow64/cmd.exe').read_bytes()
    header = struct.unpack_from('<I', command, 0x3c)[0]
    assert command[header:header+4] == b'PE\0\0'
    assert struct.unpack_from('<H', command, header+4)[0] == 0x14c
    result = subprocess.run(wine + [r'C:\windows\syswow64\cmd.exe', '/d', '/c',
                            'echo TRASC_COMPACT_WINE_PE32_OK'], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    print(result.stdout.decode(errors='replace'), flush=True)
    assert result.returncode == 0 and b'TRASC_COMPACT_WINE_PE32_OK' in result.stdout
    assert subprocess.run(wine + [r'C:\windows\syswow64\cmd.exe', '/d', '/c', 'exit', '23'],
                          env=env, timeout=30).returncode == 23
finally:
    try:
        for option in ('-k', '-w'):
            subprocess.run(server + [option], timeout=20, check=True)
    finally:
        display.terminate()
        try: display.wait(timeout=10)
        except subprocess.TimeoutExpired:
            display.kill(); display.wait()
'''
try:
    (old_tmp / 's').mkdir()
    code, text = run('old-sysv', old_tmp, ['/usr/bin/python3', '-c', shared_memory])
    assert code != 0 and 'proot-shm-helper: Temporary path too long' in text, (code, text[-4000:])
    code, text = run('old-wineserver', old_tmp,
                     ['/usr/local/bin/box64', '/opt/wine/bin/wineserver', '-f'])
    assert code == 1 and 'wineserver: bind: Invalid argument' in text, (code, text[-4000:])
    for profile, tmp in [('traditional', traditional_tmp), ('custom', custom_tmp)]:
        code, text = run('compact-' + profile, tmp,
                         ['/usr/bin/python3', '-c', shared_memory + socket_alias])
        assert code == 0 and 'TRASC_COMPACT_SYSV_OK' in text, (code, text[-4000:])
        assert 'TRASC PRoot: SysV shared memory uses memfd' in text, text[-4000:]
        assert 'TRASC_COMPACT_SOCKET_ALIAS_OK' in text, text[-4000:]
    code, text = run('compact-wine', traditional_tmp, ['/usr/bin/python3', '-c', wine], timeout=240)
    assert code == 0 and 'TRASC_COMPACT_WINE_PE32_OK' in text, (code, text[-6000:])
    assert prefix_identity == (prefix.stat().st_dev, prefix.stat().st_ino)
    evidence.update(result='passed', same_persistent_prefix=True)
    print('PASS: Android-length temporary paths reproduce real PRoot SHM and bundled wineserver failures; compact Traditional/Custom paths pass memfd, overlong socket remapping and real PE32 Wine startup')
finally:
    (logs / 'client-unix-path-verification.json').write_text(json.dumps(evidence, indent=2))
    shutil.rmtree(fixture)
PYPATH
fi
