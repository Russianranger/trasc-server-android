#!/usr/bin/env python3
"""Reuse the verified 0.6.10 native payload for the viewport-only APK update."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

BASE_APK_SHA256 = 'ead3312ec676fd10f0940598a1f14eb8b9835f61e5678d933f5abfd6294f2488'
LIBRARIES = ('libcabextract.so', 'libproot-loader.so', 'libproot.so',
             'libtrasc-presentation.so', 'libvirgl-server.so')
ASSETS = ('audio-bundle.json', 'dxvk-d3d9.dll', 'libasound_module_pcm_trasc.so',
          'presentation-bundle.json', 'presentation-notices.txt',
          'turnip-26.0.0.so', 'turnip.so', 'vulkan-bundle.json', 'vulkan-probe',
          'wined3d-patch.json', 'wined3d.dll', 'wineserver-patch.json',
          'wineserver', 'x11-frame-bridge')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def extract(apk, root, expected_sha=BASE_APK_SHA256):
    apk, root = Path(apk), Path(root)
    if digest(apk.read_bytes()) != expected_sha:
        raise ValueError('Published baseline APK does not match the verified 0.6.10 hash')
    mappings = [(f'lib/arm64-v8a/{name}', f'app/src/main/jniLibs/arm64-v8a/{name}')
                for name in LIBRARIES]
    mappings += [('assets/'+name, 'backend-assets/'+name) for name in ASSETS]
    with zipfile.ZipFile(apk) as archive:
        # Read the entire required set before writing any partial payload.
        payload = [(source, target, archive.read(source)) for source, target in mappings]
    records = []
    for source, target, data in payload:
        destination = root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        records.append({'apk_entry': source, 'path': target,
                        'sha256': digest(data), 'bytes': len(data)})
    return {'baseline_version': '0.6.10', 'baseline_apk_sha256': expected_sha,
            'files': records}

def verify(apk, receipt):
    with zipfile.ZipFile(apk) as archive:
        for record in receipt['files']:
            if digest(archive.read(record['apk_entry'])) != record['sha256']:
                raise ValueError('Native payload changed: '+record['apk_entry'])
        actual = {n for n in archive.namelist() if n.startswith('lib/') and not n.endswith('/')}
        expected = {'lib/arm64-v8a/'+n for n in LIBRARIES}
        if actual != expected:
            raise ValueError('Unexpected native library set in new APK')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['extract','verify'])
    parser.add_argument('--apk',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--receipt',type=Path,required=True)
    args = parser.parse_args()
    if args.action == 'extract':
        receipt = extract(args.apk,args.root)
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    else:
        verify(args.apk,json.loads(args.receipt.read_text()))
    print('PASS: verified unchanged native launcher payload')
