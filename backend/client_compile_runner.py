"""Run MSVC in a separate Wine prefix; never alter ROF2 or its shader caches."""
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import time
import client_dll
from log_retention import rotate
from engine import atomic_json

WORK=Path('/work');SESSION=Path('/session');LOG=WORK/'logs/client-compiler.log'
stop_requested=False


def update(phase, **extra):
    atomic_json(SESSION/'status.json', {'phase':phase,'compiler':True,'display_ready':(SESSION/'display.sock').exists(),**extra})


class Compiler:
    work=WORK
    def server_running(self): return False  # Native launcher checked the server/job state.
    def check_cancel(self):
        if stop_requested or (SESSION/'stop').exists(): raise RuntimeError('Client DLL build cancelled; installed DLL unchanged')
    def log(self, message):
        update('compiling',message=message)
        print(message,flush=True)
    def run(self,args,cwd=None,timeout=1800):
        self.check_cancel()
        command=['/usr/local/bin/box64','/opt/wine/bin/wine',str(args[0]),*(str(x) for x in args[1:])]
        with LOG.open('ab') as output:
            process=subprocess.Popen(command,cwd=cwd or WORK,env=ENV,stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True)
            started=time.monotonic()
            try:
                while process.poll() is None:
                    self.check_cancel()
                    if time.monotonic()-started>timeout: raise RuntimeError('Microsoft compiler timed out; see client-compiler.log')
                    time.sleep(.2)
                if process.returncode: raise RuntimeError('Microsoft compiler failed ('+str(process.returncode)+'); see client-compiler.log')
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL);process.wait()


ENV=dict(os.environ,DISPLAY=':8',XAUTHORITY='/session/Xauthority',WINEPREFIX='/prefix',WINEARCH='win64',WINEDEBUG='-all',
         WINESERVER='/opt/wine/bin/wineserver',WINEDLLOVERRIDES='winemenubuilder,mscoree,mshtml,winegstreamer=',
         BOX64_PATH='/opt/wine/bin',BOX64_LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/opt/wine/lib/wine/x86_64-unix',
         BOX64_DYNAREC_STRONGMEM='1',BOX64_DYNAREC_BIGBLOCK='0',BOX64_DYNAREC_SAFEFLAGS='2',BOX64_LOG='0',BOX64_NOBANNER='1',
         LIBGL_ALWAYS_SOFTWARE='1',GALLIUM_DRIVER='llvmpipe')


def main():
    global stop_requested
    def stop(*_):
        global stop_requested
        stop_requested=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    compiler=Compiler();xserver=None
    lease=WORK/'run/client-dll-building.json'
    try:
        atomic_json(lease,{'pid':os.getpid(),'started':time.time()})
        rotate(LOG)
        rotate(WORK/'logs/client-compiler-display.log')
        update('compiler_starting',message='Preparing a separate compiler prefix')
        (SESSION/'Xauthority').touch(mode=0o600)
        subprocess.run(['xauth','-f',ENV['XAUTHORITY'],'add',':8','.',secrets.token_hex(16)],check=True)
        display_log=(WORK/'logs/client-compiler-display.log').open('wb')
        xserver=subprocess.Popen(['Xtigervnc',':8','-geometry','800x600','-depth','24','-rfbport','-1',
            '-rfbunixpath',str(SESSION/'display.sock'),'-rfbunixmode','0600','-SecurityTypes','None','-nolisten','tcp',
            '-auth',ENV['XAUTHORITY'],'-AlwaysShared','-desktop','TRASC compiler'],env=ENV,stdout=display_log,stderr=display_log)
        for _ in range(150):
            compiler.check_cancel()
            if xserver.poll() is not None: raise RuntimeError('Compiler display could not start')
            if (SESSION/'display.sock').exists(): break
            time.sleep(.1)
        else: raise RuntimeError('Compiler display timed out')
        # Microsoft tools use their own Wine environment; game prefix is never mounted here.
        compiler.run(['wineboot','-u'],timeout=300)
        result=client_dll.build_dll(compiler,{})
        atomic_json(WORK/'logs/client-dll-build.json',result)
        update('compiled',message=result['message'],build=result['build'])
    except Exception as error:
        update('error',error=str(error),message=str(error));raise
    finally:
        try: subprocess.run(['/usr/local/bin/box64','/opt/wine/bin/wineserver','-k'],env=ENV,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
        except (OSError,subprocess.TimeoutExpired): pass
        if xserver is not None:
            xserver.terminate()
            try:xserver.wait(timeout=5)
            except subprocess.TimeoutExpired:xserver.kill();xserver.wait()
        (SESSION/'display.sock').unlink(missing_ok=True)
        lease.unlink(missing_ok=True)


if __name__=='__main__': main()
