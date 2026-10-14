#!/usr/bin/env python3
"""Reuse the same published native camera path from independently verified 0.6.29."""
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

APK_SHA = 'e81e6afe2ac639a292d7c048cc7575a9cbd1af6a19f2cfe4a934f2c723e40fcf'
APK_BYTES = 18952880
OBSERVER_SHA = '5f5cf7e8f8d2d3df475284f72fa0f2944e1cadb9ba334927021799615b35744b'


def prepare(runtime, manifest, apk, output):
    path = Path(__file__).with_name('prepare-takp-camera-runtime.py')
    spec = importlib.util.spec_from_file_location('published_camera_inputs', path)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    # Preserve the original verifier/source fingerprints. Only the newer APK
    # identity changes; the embedded input bridge and Wine server are unchanged.
    base.APK_SHA, base.APK_BYTES = APK_SHA, APK_BYTES
    with redirect_stdout(io.StringIO()):
        base.prepare(runtime, manifest, apk, output)
    output=Path(output)
    with zipfile.ZipFile(apk) as archive:
        binary=archive.read('assets/takp-input/takp-xinput-observe')
        build_bytes=archive.read('assets/takp-input/takp-input-observer.json')
        build=json.loads(build_bytes)
        if hashlib.sha256(binary).hexdigest()!=OBSERVER_SHA or build['sha256']!=OBSERVER_SHA or build['bytes']!=len(binary):
            raise ValueError('Published unchanged observer identity mismatch')
        (output/'takp-xinput-observe').write_bytes(binary);(output/'takp-xinput-observe').chmod(0o755)
        (output/'takp-input-observer.json').write_bytes(build_bytes)
    receipt_path = Path(output) / 'published-inputs.json'
    receipt = json.loads(receipt_path.read_text())
    receipt.update(apk_asset_id=639098532, apk_version='0.6.29', apk_version_code=78,
        preserved_observer_sha256=OBSERVER_SHA,observer_rebuilt=False)
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'manifest', 'apk', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.runtime, args.manifest, args.apk, args.output)
