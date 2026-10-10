#!/usr/bin/env python3
"""Record the actual compiled PE32, exact source and narrow camera patch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module
recipe = import_module('prepare-takp-eqw')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(source, output, root):
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != recipe.COMMIT:
        raise ValueError('EQW source commit differs from the reviewed build')
    dll = source / 'Release/eqw.dll'
    data = dll.read_bytes()
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    if data[:2] != b'MZ' or data[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', data, offset+4)[0] != 0x14c or struct.unpack_from('<H', data, offset+24)[0] != 0x10b:
        raise ValueError('EQW camera helper must be a Windows x86 PE32 DLL')
    if b'TRASC_TAKP_WINE_RAW_LOOK_V2' not in data:
        raise ValueError('EQW DLL is missing the camera repair identity')
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dll, output/'eqw.dll')
    shutil.copyfile(source/'LICENSE.txt', output/'eqw-LICENSE.txt')
    shutil.copytree(source/'eqw_takp', output/'source/eqw_takp')
    shutil.copyfile(source/'eqw_takp.sln', output/'source/eqw_takp.sln')
    # Build products/debug symbols do not belong in the preserved source.
    for folder in (output/'source/eqw_takp/Release', output/'source/eqw_takp/x64'):
        if folder.exists(): shutil.rmtree(folder)
    patches = {str(path.relative_to(root)):digest(path) for path in (
        root/'native/takp_camera_recenter.h', root/'scripts/prepare-takp-eqw.py', root/'scripts/record-takp-eqw.py')}
    receipt = {'format':1, 'architecture':'x86', 'helper':'eqw.dll', 'sha256':digest(dll),
        'bytes':len(data), 'source_repository':'https://github.com/CoastalRedwood/eqw_takp',
        'source_commit':recipe.COMMIT, 'source_tag':'v1.0.2', 'upstream_game_input_sha256':recipe.INPUT_SHA,
        'patched_game_input_sha256':digest(source/'eqw_takp/game_input.cpp'),
        'upstream_source_sha256':recipe.SOURCE_SHA,
        'patched_source_sha256':{name:digest(source/'eqw_takp'/name) for name in recipe.SOURCE_SHA},
        'patch_files':patches, 'marker':'TRASC_TAKP_WINE_RAW_LOOK_V2',
        'compiler':'Microsoft Visual C++ v143, Release x86', 'build_commit':os.environ.get('GITHUB_SHA'),
        'build_run':int(os.environ.get('GITHUB_RUN_ID','0')), 'license_sha256':digest(source/'LICENSE.txt')}
    (output/'eqw-camera-build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args();record(args.source,args.output,args.root)
