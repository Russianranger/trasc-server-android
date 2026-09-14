"""The unmodified Wine 10 DLL must reproduce the Thor's exact GLSL failure."""
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,'/opt/trasc-client')
import client_runner

expected=int(sys.argv[1])
for name in ('/session','/prefix','/logs'):Path(name).mkdir(exist_ok=True)
env=client_runner.Supervisor({'mode':'client','renderer':'virgl','resolution':'800x600'}).env
env['WINEDLLOVERRIDES']+=';d3dx9_35=n,b'
x=None
with Path('/logs/shader-regression.log').open('wb') as log:
    try:
        x=subprocess.Popen(['Xtigervnc',':7','-geometry','800x600','-depth','24','-rfbport','-1','-nolisten','tcp'],env=env,stdout=log,stderr=log)
        for _ in range(100):
            if Path('/tmp/.X11-unix/X7').exists():break
            if x.poll() is not None:raise RuntimeError('Private display exited')
            time.sleep(.1)
        wine=['/usr/local/bin/box64','/opt/wine/bin/wine']
        subprocess.run(wine+['wineboot','-u'],env=env,stdout=log,stderr=log,timeout=120,check=True)
        client_runner.prepare_model_libraries()
        # Z maps the fixture without relying on the launcher's D mapping.
        result=subprocess.run(wine+[r'Z:\client\textures.exe','--shader-only'],cwd='/client',env=env,stdout=log,stderr=log,timeout=60)
        assert result.returncode==expected,(result.returncode,expected)
        log.flush();trace=Path('/logs/shader-regression.log').read_text(errors='replace')
        assert ("'ffp_varying_specular' undeclared" in trace)==bool(expected),trace[-5000:]
        print('PASS: '+('unpatched Wine reproduces the exact undeclared specular error' if expected else 'patched Wine renders both legacy shader versions'))
    finally:
        subprocess.run(['/usr/local/bin/box64','/opt/wine/bin/wineserver','-k'],env=env,stdout=log,stderr=log,timeout=15)
        if x is not None:x.terminate();x.wait(timeout=10)
