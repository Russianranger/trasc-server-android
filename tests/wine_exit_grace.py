"""Reproduce Wine's premature SIGKILL, then require real zero/nonzero exits.

The negative control alone expects SIGKILL. Every patched normal exit must
preserve the Windows code and finish a real two-second native exit delay.
"""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, '/opt/trasc-client')
import client_runner

wine=['/usr/local/bin/box64','/opt/wine/bin/wine']
adjacent=Path('/opt/wine/bin/wineserver')
patched='/opt/trasc-client/wineserver'
logs=Path('/logs');logs.mkdir(exist_ok=True)
results=[]
with tempfile.TemporaryDirectory(prefix='trasc-exit-grace-') as temporary, (logs/'exit-grace.log').open('wb') as output:
    stock=str(Path(temporary)/'stock-wineserver')
    shutil.copy2(adjacent,stock)
    def install_server(source):
        staged=adjacent.with_name('wineserver.exit-test')
        shutil.copy2(source,staged);staged.chmod(0o755);os.replace(staged,adjacent)

    env=client_runner.Supervisor({'mode':'desktop','resolution':'800x600','cpu_profile':'compatibility'}).env
    env.update(WINEPREFIX=temporary,WINESERVER=stock,DISPLAY=':8',WINEDEBUG='-all',BOX64_LOG='1')
    env.pop('XAUTHORITY',None)
    display=subprocess.Popen(['Xtigervnc',':8','-geometry','640x480','-depth','24','-rfbport','-1','-nolisten','tcp'],env=env,stdout=output,stderr=output)

    def stop_server(server):
        selected=dict(env,WINESERVER=server)
        for option in ('-k','-w'):
            subprocess.run(['/usr/local/bin/box64',server,option],env=selected,stdout=output,stderr=output,timeout=20,check=True)

    # Loader-level preload survives Wine exec and bypasses Box64's guest-library
    # finalizer rules. This container is disposable; never alter a device image.
    preload=Path('/etc/ld.so.preload')
    assert not preload.exists(), 'Exit fixture requires an isolated container without a preload'
    preload.write_text('/client/exit-delay.so\n')
    cleanup_needed=True
    try:
        deadline=time.monotonic()+15
        while not Path('/tmp/.X11-unix/X8').exists():
            assert display.poll() is None and time.monotonic()<deadline,'Exit-test display startup failed'
            time.sleep(.1)
        subprocess.run(wine+['wineboot','-u'],env=env,stdout=output,stderr=output,timeout=120,check=True)
        stop_server(stock)
        for label,server,code,expected in [('stock',stock,0,-9),('patched-zero',patched,0,0),('patched-nonzero',patched,23,23)]:
            install_server(server)
            marker=logs/('exit-delay-'+label+'.txt');marker.unlink(missing_ok=True)
            selected=dict(env,WINESERVER=server,TRASC_EXIT_DELAY_REPORT=str(marker))
            started=time.monotonic()
            child=subprocess.run(wine+[r'C:\windows\syswow64\cmd.exe','/d','/c','exit',str(code)],env=selected,stdout=output,stderr=output,timeout=30)
            if marker.exists(): marker.chmod(0o644)
            trace=marker.read_text() if marker.exists() else ''
            result={'case':label,'returncode':child.returncode,'seconds':round(time.monotonic()-started,3),'cleanup':trace}
            results.append(result);(logs/'exit-grace.json').write_text(json.dumps(results,indent=2))
            assert child.returncode==expected,result
            assert 'begin\n' in trace,result
            assert ('done\n' in trace)==(server==patched),result
            stop_server(server)
        # Explicit Stop must still terminate a running Windows process promptly.
        selected=dict(env,WINESERVER=patched)
        child=subprocess.Popen(wine+[r'C:\windows\syswow64\cmd.exe','/d','/c','ping','-n','60','127.0.0.1'],env=selected,stdout=output,stderr=output)
        try:
            time.sleep(1);assert child.poll() is None,'Stop fixture exited before cancellation'
            started=time.monotonic();stop_server(patched);child.wait(timeout=10)
            seconds=round(time.monotonic()-started,3)
            assert seconds<15,seconds
            cleanup_needed=False  # -k/-w and child.wait already proved shutdown.
            results.append({'case':'explicit-stop','seconds':seconds,'returncode':child.returncode})
            (logs/'exit-grace.json').write_text(json.dumps(results,indent=2))
        finally:
            if child.poll() is None:child.kill();child.wait()
        print('PASS: stock Wine timer reproduces SIGKILL; bundled server preserves exit 0/23 through delayed native cleanup and explicit Stop still terminates the process')
    finally:
        preload.unlink()
        try:
            if cleanup_needed: stop_server(str(adjacent))
        finally:
            install_server(stock)
            display.terminate();display.wait(timeout=10)
