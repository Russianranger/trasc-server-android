#!/usr/bin/env python3
"""Verify the update certificate and exact TAKP helper bytes in a built APK."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile


TAKP_HELPERS = {
    'd3d8.dll': '122928cfe225c25d30decf7184a5d37e490cecf3b58256ba3206c7e1853f8ab8',
    'eqgame.dll': 'f0ca8e4bdcf3875419ecb1067a95bd6dbf8197e564f9d51ff4dec98a30f14b97',
    'eqw.dll': 'dffb97ac1f47d41f450614c8d6d4da30f3f47b7ed5046dbdbd111b3ba1fbe5ba',
}


def verify(apk, signing_report, root):
    expected_certificate = (root / 'docs/preview-signing.sha256').read_text().strip()
    match = re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})',
                      signing_report.read_text())
    if not match or match.group(1) != expected_certificate:
        raise ValueError('APK signing certificate changed; this is not a compatible update')
    with zipfile.ZipFile(apk) as archive:
        for name in ('engine.py', 'takp_build.py', 'takp_runtime.py', 'takp_client.py'):
            if archive.read('assets/' + name) != (root / 'backend' / name).read_bytes():
                raise ValueError('APK is missing the current TAKP backend module: ' + name)
        for name, expected in TAKP_HELPERS.items():
            data = archive.read('assets/takp-client/' + name)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('TAKP helper differs from the verified official release: ' + name)
            if data[:2] != b'MZ' or len(data) < 64:
                raise ValueError('TAKP helper is not a PE binary: ' + name)
            offset = struct.unpack_from('<I', data, 0x3c)[0]
            if data[offset:offset + 4] != b'PE\0\0' or struct.unpack_from('<H', data, offset + 4)[0] != 0x14c:
                raise ValueError('TAKP helper must be a 32-bit x86 PE binary: ' + name)
        # The runtime receipt must ship with the exact DLLs for offline verification.
        archive_manifest = archive.read('assets/takp-client/bundle.json')
        if archive_manifest != (root / 'backend/takp-client/bundle.json').read_bytes():
            raise ValueError('TAKP helper receipt differs from the reviewed source')
        json.loads(archive_manifest)
        for name in ('eqw-LICENSE.txt', 'd3d8to9-LICENSE.txt'):
            data = archive.read('assets/takp-client/' + name)
            if not data or data != (root / 'backend/takp-client' / name).read_bytes():
                raise ValueError('TAKP helper license is missing or changed: ' + name)
        if 'assets/takp-client/eqw.pdb' in archive.namelist():
            raise ValueError('The debug symbol file must not inflate the runtime APK')
    print('PASS: preserved preview certificate and exact 32-bit TAKP helper DLLs/receipt')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--signing-report', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args()
    verify(options.apk, options.signing_report, options.root)
