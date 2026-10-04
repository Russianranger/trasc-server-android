"""Verify trial executables are ARM64 and all runtime dependencies resolve."""
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
evidence = pathlib.Path(sys.argv[2])
names = ('world', 'zone', 'shared_memory', 'eqlaunch', 'ucs', 'queryserv',
         'loginserver', 'export_client_files', 'import_client_files')
report = {}
for name in names:
    path = root / name
    with path.open('rb') as stream:
        header = stream.read(20)
    assert header[:4] == b'\x7fELF' and header[4] == 2 and header[5] == 1, name
    assert int.from_bytes(header[18:20], 'little') == 183, name
    result = subprocess.run(['ldd', str(path)], check=True, capture_output=True, text=True)
    assert 'not found' not in result.stdout + result.stderr, name
    (evidence / (name + '-ldd.txt')).write_text(result.stdout + result.stderr)
    dynamic = subprocess.run(['readelf', '-d', str(path)], check=True, capture_output=True, text=True).stdout
    (evidence / (name + '-dynamic.txt')).write_text(dynamic)
    assert not any('/source' in line or '/evidence' in line for line in dynamic.splitlines()
                   if '(RPATH)' in line or '(RUNPATH)' in line), name
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report[name] = {'machine': 'AArch64', 'size_bytes': path.stat().st_size,
                    'sha256': digest,
                    'loader_dependencies': 'resolved'}
providers = subprocess.run(['openssl', 'list', '-providers', '-provider', 'default',
                            '-provider', 'legacy'], check=True, capture_output=True, text=True).stdout
ciphers = subprocess.run(['openssl', 'list', '-cipher-algorithms', '-provider', 'default',
                          '-provider', 'legacy'], check=True, capture_output=True, text=True).stdout
(evidence / 'openssl-providers.txt').write_text(providers)
(evidence / 'openssl-ciphers.txt').write_text(ciphers)
assert any('DES-CBC' in line and '@ legacy' in line for line in ciphers.splitlines())
(evidence / 'binary-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print('All nine ARM64 executables, runtime dependencies and legacy DES provider verified')
