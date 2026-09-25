"""Verify catalog planning and private msitools in the published ARM64 runtime.

Does not accept Microsoft's license or download compiler/SDK payloads.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, '/opt/trasc')
from engine import Engine
import client_toolchain

with tempfile.TemporaryDirectory(prefix='trasc-toolchain-') as temp:
    engine = Engine(Path(temp) / 'work')
    installed = subprocess.check_output(['dpkg-query', '-W'])
    stage = Path(temp) / 'extractor'
    stage.mkdir()
    wrappers = client_toolchain.prepare_msiextract(engine, stage)
    tool = wrappers / 'msiextract' if wrappers else 'msiextract'
    subprocess.run([str(tool), '--version'], check=True)
    assert subprocess.check_output(['dpkg-query', '-W']) == installed, 'Runtime packages changed'
    info = client_toolchain.download_info(engine)
    assert info['toolset'].startswith('MSVC v142') and info['download_bytes'] > 0
    assert not (engine.work / 'client/toolchain').exists(), 'Catalog planning installed a compiler'
    print(json.dumps({key: info[key] for key in ('license_url', 'toolset', 'sdk', 'download_bytes', 'token')}, indent=2))
    print('PASS: ARM64 extractor runs, installed packages unchanged, catalog verified without accepting SDK license')
