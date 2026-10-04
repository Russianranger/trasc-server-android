"""Verify Traditional build outputs without starting any server executable."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys


BINARIES = ('world', 'zone', 'shared_memory', 'eqlaunch', 'ucs', 'queryserv',
            'loginserver', 'export_client_files', 'import_client_files')
INTERPRETER = '/lib/ld-linux-aarch64.so.1'
BUILD_PATHS = ('/work/builds', '/work/sources', '/source', '/evidence')
REQUIRED_ABI = {
    'zone': {'luajit': r'libluajit-5\.1\.so\.2', 'perl': r'libperl\.so\.\d+\.\d+'},
    'loginserver': {'crypto': r'libcrypto\.so\.3'},
}


def inspect_elf(path):
    """Check the executable ABI and interpreter before invoking loader tools."""
    path = Path(path)
    size = path.lstat()
    if not stat.S_ISREG(size.st_mode):
        raise ValueError(str(path) + ' must be a regular executable file')
    with path.open('rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:7] != b'\x7fELF\x02\x01\x01':
            raise ValueError(path.name + ' is not a little-endian ELF64 executable')
        fields = struct.unpack('<16sHHIQQQIHHHHHH', header)
        if fields[1] not in (2, 3) or fields[2] != 183 or fields[3] != 1:
            raise ValueError(path.name + ' is not an ARM64 executable')
        offset, entry_size, count = fields[5], fields[9], fields[10]
        if fields[8] != 64 or entry_size != 56 or not 1 <= count <= 4096:
            raise ValueError(path.name + ' has invalid ELF program headers')
        if offset < 64 or offset + entry_size * count > size.st_size:
            raise ValueError(path.name + ' has truncated ELF program headers')
        interpreters = []
        for index in range(count):
            stream.seek(offset + index * entry_size)
            program = struct.unpack('<IIQQQQQQ', stream.read(entry_size))
            if program[0] != 3:
                continue
            begin, length = program[2], program[5]
            if not 1 <= length <= 4096 or begin + length > size.st_size:
                raise ValueError(path.name + ' has invalid interpreter metadata')
            stream.seek(begin)
            interpreter = stream.read(length)
            if not interpreter.endswith(b'\0'):
                raise ValueError(path.name + ' has an unterminated interpreter')
            interpreters.append(interpreter[:-1])
    if interpreters != [INTERPRETER.encode()]:
        raise ValueError(path.name + ' requires an unsupported runtime interpreter')
    return {'architecture': 'arm64', 'interpreter': INTERPRETER, 'bytes': size.st_size}


def _command(args):
    environment = dict(os.environ)
    for name in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT', 'LD_DEBUG',
                 'LD_TRACE_LOADED_OBJECTS', 'OPENSSL_CONF', 'OPENSSL_MODULES'):
        environment.pop(name, None)
    environment['LC_ALL'] = 'C'
    result = subprocess.run(args, capture_output=True, text=True,
                            timeout=20, env=environment)
    output = result.stdout + result.stderr
    if result.returncode:
        raise ValueError(args[0] + ' failed: ' + output.strip()[:2000])
    return output


def _active_providers(output):
    result = set()
    current = None
    for line in output.splitlines():
        match = re.fullmatch(r'  ([a-zA-Z0-9_.-]+)', line)
        if match:
            current = match.group(1)
        elif line.strip() == 'status: active' and current:
            result.add(current)
    return result


def _identity(path):
    value = path.stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def verify(binary_dir, evidence_dir):
    binary_dir, evidence_dir = Path(binary_dir), Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report_file = evidence_dir / 'binary-verification.json'
    report_file.unlink(missing_ok=True)
    report = {'format': 1, 'architecture': 'arm64', 'binaries': {}, 'abi_libraries': {}}
    for name in BINARIES:
        path = binary_dir / name
        identity = _identity(path)
        entry = inspect_elf(path)
        loader = _command(['ldd', str(path)])
        (evidence_dir / (name + '-ldd.txt')).write_text(loader)
        if 'not found' in loader:
            raise ValueError(name + ' has unresolved runtime dependencies')
        if name in REQUIRED_ABI:
            libraries = {}
            for feature, expression in REQUIRED_ABI[name].items():
                match = re.search(r'^\s*(' + expression + r')\s+=>\s+/', loader, re.MULTILINE)
                if not match:
                    raise ValueError(name + ' lacks required ' + feature + ' runtime library')
                libraries[feature] = match.group(1)
            report['abi_libraries'][name] = libraries
        dynamic = _command(['readelf', '--wide', '-d', str(path)])
        (evidence_dir / (name + '-dynamic.txt')).write_text(dynamic)
        for line in dynamic.splitlines():
            if '(RPATH)' in line or '(RUNPATH)' in line:
                if any(prefix in line for prefix in BUILD_PATHS):
                    raise ValueError(name + ' depends on a build-directory library path')
        with path.open('rb') as stream:
            entry['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if _identity(path) != identity:
            raise ValueError(name + ' changed during verification')
        entry['loader_dependencies'] = 'resolved'
        report['binaries'][name] = entry
    version = _command(['openssl', 'version'])
    (evidence_dir / 'openssl-version.txt').write_text(version)
    match = re.match(r'OpenSSL (\d+)\.', version)
    if not match or int(match.group(1)) < 3:
        raise ValueError('Traditional login encryption requires OpenSSL 3 or later')
    providers = _command(['openssl', 'list', '-providers', '-provider', 'default',
                          '-provider', 'legacy'])
    (evidence_dir / 'openssl-providers.txt').write_text(providers)
    if not {'default', 'legacy'} <= _active_providers(providers):
        raise ValueError('OpenSSL default and legacy providers must both be active')
    ciphers = _command(['openssl', 'list', '-cipher-algorithms', '-provider', 'default',
                        '-provider', 'legacy'])
    (evidence_dir / 'openssl-ciphers.txt').write_text(ciphers)
    if not any('DES-CBC' in line and '@ legacy' in line for line in ciphers.splitlines()):
        raise ValueError('OpenSSL legacy DES-CBC is unavailable')
    report['providers'] = {'default': True, 'legacy': True, 'des_cbc': True}
    temporary = report_file.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2) + '\n')
    temporary.replace(report_file)
    return report


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: traditional_verify.py BINARY_DIR EVIDENCE_DIR')
    try:
        verify(sys.argv[1], sys.argv[2])
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('Traditional binary verification failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
    print('Verified nine ARM64 Traditional executables and runtime dependencies', flush=True)
