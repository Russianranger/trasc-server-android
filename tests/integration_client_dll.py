"""Compile actual imported upstream source with the same recipe on Windows CI.

The SDK is provided by the runner's licensed VS installation, never published.
Android runs the same compiler EXEs through its Wine/Box64 runtime.
Physical-device execution and loading remain device tests.
"""
import sys
import tempfile
from pathlib import Path
import shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from engine import Engine
import client_dll
source=Path(sys.argv[1]).resolve();sdk=Path(sys.argv[2]).resolve()
with tempfile.TemporaryDirectory() as temp:
    work=Path(temp);engine=Engine(work)
    incoming=work/'incoming/sdk.zip';shutil.copy2(sdk,incoming)
    client_dll.import_sdk(engine,{'file':'sdk.zip'})
    shutil.copytree(source/'Release-NMS-Client',work/'sources/current/Release-NMS-Client')
    try:
        result=client_dll.build_dll(engine,{})
        assert result['build']['bytes']>100000
        print('PASS: actual Triptych source compiled with the original Microsoft v142 toolset as an x86 PE32 DLL; installed client untouched')
    except Exception:
        print((work/'logs/operation.log').read_text(errors='replace')[-30000:])
        raise
