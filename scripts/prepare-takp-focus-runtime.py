#!/usr/bin/env python3
"""Reuse the same published native camera path from independently verified 0.6.27."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path

APK_SHA = '603776458fb2d245262bb36febdec5380557270cc39f5bc476267e21095f5595'
APK_BYTES = 18923551


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
    receipt_path = Path(output) / 'published-inputs.json'
    receipt = json.loads(receipt_path.read_text())
    receipt.update(apk_asset_id=638709306, apk_version='0.6.27', apk_version_code=76)
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'manifest', 'apk', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.runtime, args.manifest, args.apk, args.output)
