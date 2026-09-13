"""Compile every app-managed server target inside the actual ARM64 runtime image.

Uses the same archive importer, CMake arguments and binary staging as the app.
Run separately from the fast unit tests; no server/database processes are started.
"""
import argparse
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

sys.path.insert(0, '/opt/trasc')
from engine import Engine, BINARIES, atomic_json


def verify(work, repository, revision):
    if platform.machine() not in ('aarch64', 'arm64'):
        raise ValueError('Run this verification in the ARM64 runtime image')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Expected owner/repository')
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Pin the server reference to its full commit SHA')
    engine = Engine(work)
    try:
        subprocess.run(['perl', '-MJSON', '-MDBI', '-MDBD::mysql', '-e', 'print "Quest modules available\\n"'], check=True)
        archive = engine.work / 'incoming' / 'reference-source.zip'
        engine.download(f'https://codeload.github.com/{repository}/zip/{revision}', archive)
        engine.import_source({'file': archive.name})
        source = {'type': 'github', 'repo': f'https://github.com/{repository}', 'ref': revision, 'commit': revision}
        atomic_json(engine.source_root() / 'trasc-source.json', source)
        print(f'Compiling all {len(BINARIES)} server binaries from {repository}@{revision}', flush=True)
        engine.build({'jobs': 2})
        binaries = []
        for name in BINARIES:
            binary = engine.work / 'server/bin.staged' / name
            dependencies = subprocess.run(['ldd', str(binary)], text=True, capture_output=True)
            if dependencies.returncode or 'not found' in dependencies.stdout:
                raise RuntimeError(f'{name}: unresolved runtime libraries\n{dependencies.stdout}\n{dependencies.stderr}')
            binaries.append({'name': name, 'bytes': binary.stat().st_size, 'libraries_resolved': True})
        report = {'result': 'passed', 'server': source, 'architecture': platform.machine(), 'binaries': binaries}
        atomic_json(engine.work / 'server-build-verification.json', report)
        print(json.dumps(report, indent=2), flush=True)
    except Exception:
        log = engine.work / 'logs/operation.log'
        if log.exists():
            with log.open('rb') as f:
                f.seek(max(0, log.stat().st_size - 24000))
                print(f.read().decode(errors='replace'), file=sys.stderr, flush=True)
        raise
    finally:
        engine.shutdown()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', default='/work')
    p.add_argument('--repository', required=True)
    p.add_argument('--revision', required=True)
    args = p.parse_args()
    verify(args.work, args.repository, args.revision)
