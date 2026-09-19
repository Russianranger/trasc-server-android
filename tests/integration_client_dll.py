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
from build_checksum_fixture import generate
source=Path(sys.argv[1]).resolve();sdk=Path(sys.argv[2]).resolve()
with tempfile.TemporaryDirectory() as temp:
    work=Path(temp);engine=Engine(work)
    incoming=work/'incoming/sdk.zip';shutil.copy2(sdk,incoming)
    client_dll.import_sdk(engine,{'file':'sdk.zip'})
    shutil.copytree(source/'Release-NMS-Client',work/'sources/current/Release-NMS-Client')
    try:
        # The same header is compiled by MSVC with production packing and tested
        # against allocated state, including inaccessible pointers and menus.
        compiler=work/'client/toolchain'; obj=work/'camera-state.obj'; test=work/'camera-state.exe'
        engine.run([compiler/'bin/cl.exe','/nologo','/c','/MT','/Zp1','/DWINDOWS_IGNORE_PACKING_MISMATCH','/std:c++14',
                    *('/I'+str(compiler/'include'/n) for n in ('msvc','ucrt','shared','um','winrt')),
                    '/Fo'+str(obj),Path(__file__).with_name('camera_mouse_state.cpp').resolve()])
        engine.run([compiler/'bin/link.exe','/nologo','/machine:x86','/subsystem:console','/out:'+str(test),str(obj),
                    *('/libpath:'+str(compiler/'lib'/n) for n in ('msvc','ucrt','um')),'kernel32.lib','user32.lib'])
        engine.run([test])
        checksum_source=work/'checksum-fixture.cpp'; generate(checksum_source)
        for name in ('fast_decimal', 'loading_patch', 'display_loading', 'first_person_particles', 'boat_diagnostics', 'checksum-fixture'):
            obj=work/(name+'.obj'); test=work/(name+'.exe')
            source_file=checksum_source if name=='checksum-fixture' else Path(__file__).with_name(name+'.cpp').resolve()
            engine.run([compiler/'bin/cl.exe','/nologo','/c','/Od' if name=='checksum-fixture' else '/O2','/MT','/Zp1','/DWINDOWS_IGNORE_PACKING_MISMATCH','/std:c++14',
                        *('/I'+str(compiler/'include'/n) for n in ('msvc','ucrt','shared','um','winrt')),
                        '/I'+str(Path(__file__).resolve().parents[1]/'backend'), '/Fo'+str(obj),source_file])
            engine.run([compiler/'bin/link.exe','/nologo','/machine:x86','/subsystem:console','/out:'+str(test),str(obj),
                        *('/libpath:'+str(compiler/'lib'/n) for n in ('msvc','ucrt','um')),'kernel32.lib','user32.lib'])
            engine.run([test])
        result=client_dll.build_dll(engine,{})
        assert result['build']['bytes']>100000
        print('PASS: actual Triptych source compiled with the original Microsoft v142 toolset as an x86 PE32 DLL; installed client untouched')
    except Exception:
        print((work/'logs/operation.log').read_text(errors='replace')[-30000:])
        raise
