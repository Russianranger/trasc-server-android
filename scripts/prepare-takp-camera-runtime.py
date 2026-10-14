#!/usr/bin/env python3
"""Verify and reuse immutable published camera-runtime inputs for CI only."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

RUNTIME_SHA = '2f130c07683e50bc606af111d5c35c4f503c1427772c1f9b0f45e1e4b75c76c4'
RUNTIME_BYTES = 353710680
APK_SHA = '7bb7a902c5695a430e396ddd035703b4cce278c11896b371a98363090290fa85'
APK_BYTES = 18901782
MANIFEST_SHA = 'f61bf0e4719815ba8b67dff437af8944f0b11173d3b63572bcca51985c3cd0ea'
WINESERVER_SHA = '09933d17ab07fe9c79245b22c9b8f4ff3fbc42d237595bb693271d168c8cb7d3'


def verified(path, size, digest):
    path = Path(path)
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if path.stat().st_size != size or actual != digest:
        raise ValueError('Published input identity mismatch: ' + path.name)
    return actual


def prepare(runtime, manifest, apk, output):
    verified(runtime, RUNTIME_BYTES, RUNTIME_SHA)
    verified(apk, APK_BYTES, APK_SHA)
    verified(manifest, 356, MANIFEST_SHA)
    identity = json.loads(Path(manifest).read_text())
    expected = {'format': 1, 'architecture': 'arm64', 'runtime': 'client-1.0',
                'wine': '10.0-wow64', 'box64': '0.4.4',
                'sha256': RUNTIME_SHA, 'bytes': RUNTIME_BYTES,
                'source_commit': '270b0bbb485e80397148112ebca66a5d98c0f69e'}
    if any(identity.get(key) != value for key, value in expected.items()):
        raise ValueError('Published runtime manifest identity mismatch')
    names = ('x11-frame-bridge', 'presentation-bundle.json',
             'wineserver', 'wineserver-patch.json')
    with zipfile.ZipFile(apk) as archive:
        payload = {name: archive.read('assets/' + name) for name in names}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    presentation = json.loads(payload['presentation-bundle.json'])
    server = json.loads(payload['wineserver-patch.json'])
    if hashes['x11-frame-bridge'] != presentation['sha256']:
        raise ValueError('Published production input bridge disagrees with its receipt')
    if hashes['wineserver'] != WINESERVER_SHA or server['sha256'] != WINESERVER_SHA:
        raise ValueError('Published Wine server differs from the actual Thor session')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in payload.items():
        destination = output / name
        destination.write_bytes(data)
        if name in ('x11-frame-bridge', 'wineserver'):
            destination.chmod(0o755)
    # TrascInputTransport supplies one socket argument. Reuse production's
    # --input entry point, including its original parser and per-packet XFlush.
    bridge = output / 'input-probe'
    bridge.write_text('#!/bin/sh\nexec /qualify/assets/x11-frame-bridge --input "$@"\n')
    bridge.chmod(0o755)
    receipt = {'format': 1, 'runtime_asset_id': 617421976,
               'runtime_manifest_asset_id': 617422429,
               'runtime': identity, 'apk_asset_id': 635995342,
               'apk_sha256': APK_SHA, 'apk_bytes': APK_BYTES,
               'native_payload_sha256': hashes,
               'runtime_rebuilt': False, 'production_input_bridge_rebuilt': False,
               'runtime_overlay': '/opt/wine/bin/wineserver from verified APK'}
    (output / 'published-inputs.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'manifest', 'apk', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.runtime, args.manifest, args.apk, args.output)
