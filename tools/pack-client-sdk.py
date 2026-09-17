#!/usr/bin/env python3
"""Prepare the TRASC v142/x86 toolchain ZIP on macOS or Linux, without Windows.

Requires Python 3.9+. --download also needs msiextract (Homebrew: msitools).
Downloads Microsoft packages with a pinned msvc-wine downloader; its interactive
Microsoft license prompt is retained. Never publish the generated toolchain ZIP.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

DOWNLOADER_COMMIT = '514f8ea34842cd6d831804d0e9658d3a32870ae1'
DOWNLOADER_SHA256 = '278429ffd7ec3aa0080ed0438fe241bb73795555949970cc569db68a60cc386b'
DOWNLOADER_URL = ('https://raw.githubusercontent.com/mstorsjo/msvc-wine/'
                  + DOWNLOADER_COMMIT + '/vsdownload.py')
REQUIRED = ('include/msvc/vector', 'include/um/Windows.h',
            'lib/msvc/libcmt.lib', 'lib/ucrt/libucrt.lib', 'lib/um/kernel32.lib',
            'bin/cl.exe', 'bin/link.exe', 'bin/c1xx.dll', 'bin/c2.dll',
            'bin/vcruntime140.dll', 'bin/msvcp140.dll')


def child(root, name):
    """Resolve Windows names on a case-sensitive host; reject ambiguity/links."""
    current = root
    for component in Path(name).parts:
        if component in ('.', '..'):
            raise ValueError('Invalid path: ' + name)
        matches = [p for p in current.iterdir() if p.name.casefold() == component.casefold()]
        if len(matches) != 1 or matches[0].is_symlink():
            raise ValueError('Missing, ambiguous or linked path: ' + str(current / component))
        current = matches[0]
    return current


def newest(root, pattern):
    versions = [p for p in root.iterdir() if re.fullmatch(pattern, p.name)
                and p.is_dir() and not p.is_symlink()]
    if not versions:
        raise ValueError('Required version not found in ' + str(root))
    return max(versions, key=lambda p: tuple(map(int, p.name.split('.'))))


def pe_x64(path):
    with path.open('rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b'MZ':
            raise ValueError('Not a Windows executable: ' + str(path))
        offset = struct.unpack_from('<I', header, 60)[0]
        if offset > 1024 * 1024:
            raise ValueError('Invalid PE header: ' + str(path))
        stream.seek(offset)
        pe = stream.read(26)
    if (len(pe) != 26 or pe[:4] != b'PE\0\0'
            or struct.unpack_from('<H', pe, 4)[0] != 0x8664
            or struct.unpack_from('<H', pe, 24)[0] != 0x20b):
        raise ValueError('Expected x64-host tools for Wine/Box64: ' + str(path))


def copy_tree(source, destination):
    destination.mkdir(parents=True)
    names = set()
    for item in source.iterdir():
        folded = item.name.casefold()
        if folded in names or item.is_symlink():
            raise ValueError('Ambiguous or linked SDK file: ' + str(item))
        names.add(folded)
        if item.is_dir():
            copy_tree(item, destination / item.name)
        elif item.is_file():
            shutil.copyfile(item, destination / item.name)
        else:
            raise ValueError('Unsupported SDK file: ' + str(item))


def package(root, output):
    if output.exists():
        raise ValueError('Output already exists; choose another --output: ' + str(output))
    vc = newest(child(root, 'VC/Tools/MSVC'), r'14\.29\.\d+')
    kits = child(root, 'Windows Kits/10')
    sdk = newest(child(kits, 'Include'), r'10\.0\.19041\.\d+')
    redist = newest(child(root, 'VC/Redist/MSVC'), r'14\.29\.\d+')
    crt = child(redist, 'x64/Microsoft.VC142.CRT')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='trasc-sdk-', dir=output.parent) as temp:
        stage = Path(temp) / 'stage'
        copy_tree(child(vc, 'bin/Hostx64/x86'), stage / 'bin')
        for item in (stage / 'bin').iterdir():
            if item.name.casefold() == 'vctip.exe':
                item.unlink()  # Optional telemetry helper can stay resident.
        for item in crt.iterdir():
            if item.suffix.lower() == '.dll':
                if item.is_symlink():
                    raise ValueError('Linked CRT file: ' + str(item))
                matches = [p for p in (stage / 'bin').iterdir()
                           if p.name.casefold() == item.name.casefold()]
                shutil.copyfile(item, matches[0] if matches else stage / 'bin' / item.name)
        copy_tree(child(vc, 'include'), stage / 'include/msvc')
        copy_tree(child(vc, 'lib/x86'), stage / 'lib/msvc')
        for name in ('ucrt', 'shared', 'um', 'winrt'):
            copy_tree(child(sdk, name), stage / 'include' / name)
        for name in ('ucrt', 'um'):
            copy_tree(child(kits, 'Lib/' + sdk.name + '/' + name + '/x86'), stage / 'lib' / name)
        for name in REQUIRED:
            if not child(stage, name).is_file():
                raise ValueError('Missing SDK file: ' + name)
        for name in ('cl.exe', 'link.exe', 'c1xx.dll', 'c2.dll', 'vcruntime140.dll', 'msvcp140.dll'):
            pe_x64(child(stage, 'bin/' + name))
        metadata = {'format': 'trasc-msvc-sdk-1', 'target': 'x86',
                    'msvc_version': vc.name, 'sdk_version': sdk.name}
        (stage / 'sdk.json').write_text(json.dumps(metadata, indent=2), encoding='ascii')
        archive = Path(temp) / 'toolchain.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for item in sorted(stage.rglob('*')):
                bundle.write(item, item.relative_to(stage).as_posix())
        # Exclusive creation prevents overwriting another completed package.
        with output.open('xb') as dest, archive.open('rb') as source:
            try:
                shutil.copyfileobj(source, dest)
            except BaseException:
                dest.close()
                output.unlink()
                raise
    print('Created ' + str(output))
    print('MSVC ' + vc.name + ' / Windows SDK ' + sdk.name + ' / x86 target')
    print('Transfer this ZIP to Thor, then Client > Build dinput8.dll on this device > Import Microsoft SDK ZIP.')


def download(work):
    if not shutil.which('msiextract'):
        raise ValueError('Install msitools first: brew install python msitools (macOS), or apt install msitools (Linux).')
    work.mkdir(parents=True, exist_ok=True)
    script = work / 'vsdownload.py'
    if not script.is_file() or hashlib.sha256(script.read_bytes()).hexdigest() != DOWNLOADER_SHA256:
        print('Downloading the pinned open-source package downloader...', flush=True)
        with urllib.request.urlopen(DOWNLOADER_URL, timeout=30) as response:
            data = response.read(2 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != DOWNLOADER_SHA256:
            raise ValueError('Downloader checksum mismatch; no script executed.')
        script.write_bytes(data)
    root = work / 'microsoft-v142'
    command = [sys.executable, str(script), '--major', '16', '--msvc-version', '16.11',
               '--sdk-version', '10.0.19041', '--host-arch', 'x64', '--architecture', 'x86',
               '--with-default', 'no', '--with-msvc', 'yes', '--with-sdk', 'yes',
               '--with-asan', 'no', '--with-atl', 'no', '--skip-patch',
               '--cache', str(work / 'downloads'), '--dest', str(root)]
    print('Microsoft packages download to your computer. Review the license at the prompt.', flush=True)
    subprocess.run(command, check=True)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--download', action='store_true', help='Fetch Microsoft packages, then pack them')
    source.add_argument('--vs-root', type=Path, help='Pack an existing unmodified vsdownload.py extraction')
    parser.add_argument('--work-dir', type=Path, default=Path.home() / 'trasc-toolchain-work')
    parser.add_argument('--output', type=Path, default=Path.cwd() / 'trasc-msvc-sdk-x86.zip')
    args = parser.parse_args()
    try:
        output = args.output.expanduser().resolve()
        if output.exists():
            raise ValueError('Output already exists; choose another --output: ' + str(output))
        root = download(args.work_dir.expanduser().resolve()) if args.download else args.vs_root.expanduser().resolve()
        package(root, output)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Toolchain preparation failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
