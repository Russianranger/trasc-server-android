"""Compile and execute a stateless native fixture in the installed ARM64 runtime."""
import argparse
import fcntl
import json
import mmap
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

sys.path.insert(0, '/opt/trasc')
from runtime_probe import probe
from traditional_verify import inspect_elf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('Traditional toolchain qualification requires native ARM64')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    run = Path('/work/run'); run.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='traditional-toolchain-', dir=run) as directory:
        root = Path(directory)
        runtime = probe(root)
        shared = root / 'shared-memory-probe'
        shared.write_bytes(bytes(4096))
        with shared.open('r+b') as stream:
            fcntl.lockf(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with mmap.mmap(stream.fileno(), 4096, access=mmap.ACCESS_WRITE) as mapping:
                mapping[:16] = b'trasc-shared-map'
                mapping.flush()
            fcntl.lockf(stream, fcntl.LOCK_UN)
        if not shared.read_bytes().startswith(b'trasc-shared-map'):
            raise RuntimeError('Shared file mmap did not persist')
        source = Path(__file__).with_name('traditional_toolchain')
        commands = (
            ['cmake', '-S', str(source), '-B', str(root / 'build'), '-G', 'Ninja',
             '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_COMPILER=/usr/bin/g++',
             '-DCMAKE_TOOLCHAIN_FILE=', '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG -fno-strict-aliasing'],
            ['cmake', '--build', str(root / 'build'), '--parallel', '1'],
        )
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True, timeout=180)
            text = result.stdout + result.stderr
            print(text, flush=True)
            if result.returncode:
                raise RuntimeError('Native toolchain fixture failed: ' + command[0])
        executable = root / 'build/traditional_toolchain_probe'
        elf = inspect_elf(executable)
        result = subprocess.run([str(executable)], capture_output=True, text=True,
                                timeout=30, check=True)
        print(result.stdout + result.stderr, flush=True)
        if 'C++20 native dependencies passed:' not in result.stdout:
            raise RuntimeError('Native fixture did not complete its dependency checks')
        report = {'format': 1, 'architecture': 'arm64', 'ok': True,
                  'runtime': runtime, 'file_mmap_and_lockf': True,
                  'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
                  'cmake': subprocess.check_output(['cmake', '--version'], text=True).splitlines()[0],
                  'fixture_elf': elf, 'fixture_output': result.stdout.strip()}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Traditional native compiler and stateless dependency fixture passed', flush=True)


if __name__ == '__main__': main()
