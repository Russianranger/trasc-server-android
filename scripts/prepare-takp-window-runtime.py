#!/usr/bin/env python3
"""Reuse independently verified 0.6.28 inputs for read-only window diagnostics."""
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

APK_SHA = '0073d46cc5b58c2a7f27c68d11e5fd3cc58a0b6afb8f208d19c7615bbba02859'
APK_BYTES = 18936371
PINS = {'takp-xinput-focus': '90dda77cb0b0fe1d18d4fa7b39bedda7dad67af6c342d7b23c74d0129f666865',
        'takp-xinput-observe': '5f5cf7e8f8d2d3df475284f72fa0f2944e1cadb9ba334927021799615b35744b'}


def prepare(runtime, manifest, apk, output):
    path = Path(__file__).with_name('prepare-takp-camera-runtime.py')
    spec = importlib.util.spec_from_file_location('published_camera_inputs', path)
    base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
    base.APK_SHA, base.APK_BYTES = APK_SHA, APK_BYTES
    with redirect_stdout(io.StringIO()): base.prepare(runtime, manifest, apk, output)
    output = Path(output)
    with zipfile.ZipFile(apk) as archive:
        for binary_name, manifest_name in (('takp-xinput-focus', 'takp-input-focus.json'),
                                           ('takp-xinput-observe', 'takp-input-observer.json')):
            binary = archive.read('assets/takp-input/' + binary_name)
            build_bytes = archive.read('assets/takp-input/' + manifest_name)
            build = json.loads(build_bytes)
            digest = hashlib.sha256(binary).hexdigest()
            if digest != PINS[binary_name] or digest != build['sha256'] or len(binary) != build['bytes']:
                raise ValueError('Preserved APK companion identity mismatch: ' + binary_name)
            (output / binary_name).write_bytes(binary); (output / binary_name).chmod(0o755)
            (output / manifest_name).write_bytes(build_bytes)
    receipt_path = output / 'published-inputs.json'
    receipt = json.loads(receipt_path.read_text())
    receipt.update(apk_asset_id=638977793, apk_version='0.6.28', apk_version_code=77,
                   preserved_companions_sha256=PINS, focus_helper_rebuilt=False, observer_rebuilt=False)
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'manifest', 'apk', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(); prepare(args.runtime, args.manifest, args.apk, args.output)
