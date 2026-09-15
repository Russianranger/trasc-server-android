"""Execute our own 32-bit Windows/DLL/D3D9 probe under ARM64 Box64, then test its display/input."""
import json
from collections import Counter
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

sys.path.insert(0, '/opt/trasc-client')
import client_runner


def wait_for(check, message, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check(): return
        time.sleep(.2)
    raise AssertionError(message)


def recv(stream, size):
    data = b''
    while len(data) < size:
        part = stream.recv(size - len(data))
        if not part: raise EOFError('Display disconnected')
        data += part
    return data


def main():
    for name in ('/session','/prefix','/logs'): Path(name).mkdir(exist_ok=True)
    renderer=os.environ.get('TRASC_TEST_RENDERER','software')
    request={'mode':'client','resolution':'800x600','executable':'eqgame.exe','native_dinput8':True,'native_d3dx':True,'renderer':renderer,'graphics_threading':'single' if renderer=='turnip' else 'opengl_worker','cpu_affinity':'available'}
    if renderer=='turnip': request.update(resolution='1280x720',fullscreen=True)
    Path('/session/request.json').write_text(json.dumps(request))
    runner = subprocess.Popen(['python3','/opt/trasc-client/client_runner.py'])
    try:
        def ready():
            error = Path('/client/probe-error.txt')
            if error.exists(): raise AssertionError(error.read_text())
            if runner.poll() is not None: raise AssertionError('Client supervisor exited: '+Path('/session/status.json').read_text())
            return Path('/client/probe-result.json').exists()
        wait_for(ready, '32-bit Wine / DLL / Direct3D probe did not become ready')
        result=json.loads(Path('/client/probe-result.json').read_text())
        assert all(result.values()),result
        graphics=json.loads(Path('/session/status.json').read_text())
        assert graphics['graphics_backend']==renderer,graphics
        assert graphics['wined3d_patch']=='legacy-specular-fog-v1',graphics
        assert graphics['cpu_profile']=='balanced',graphics
        assert graphics['prefix_update']=='update',graphics
        assert graphics['cpu_settings']['BOX64_DYNAREC_STRONGMEM']=='1',graphics
        if renderer!='turnip':
            wait_for(lambda:json.loads(Path('/session/status.json').read_text()).get('mesa_glthread_observed'),
                     'Requested OpenGL worker was not observed in the real Wine process tree',30)
            print('PASS: real supervisor observes Mesa GL command worker in Wine descendants')
        else:
            wait_for(lambda:json.loads(Path('/session/status.json').read_text()).get('dxvk_loaded')=='2.5.3',
                     'Actual DXVK load not observed',30)
            graphics=json.loads(Path('/session/status.json').read_text())
            assert graphics['native_d3d9_loaded'],graphics
            assert graphics['vulkan']['presentation_frames']==3,graphics
            assert graphics['graphics_acceleration']=='software_test',graphics
            geometry=json.loads(Path('/client/probe-display.json').read_text())
            assert geometry=={'windowed':False,'backbuffer_width':1280,'backbuffer_height':720,'client_width':1280,'client_height':720},geometry
            assert graphics['display_settings']['fullscreen'],graphics
            print('PASS: actual 1280x720 fullscreen D3D9 backbuffer and game client area')
            print('PASS: real DXVK D3D9 and Vulkan X11 presentation; CI device is explicitly software, NOT Turnip hardware')
        def affinity_freed():
            log=Path('/logs/client-threads.log')
            if not log.is_file(): return False
            for line in log.read_text().splitlines():
                sample=json.loads(line)
                for t in sample['threads']:
                    if t['tid']==t['pid'] and t['name']=='eqgame.exe':
                        if len(os.sched_getaffinity(t['tid']))>1:return True
            return False
        wait_for(affinity_freed,'The simulated game CPU restriction was not removed',30)
        print('PASS: real Windows CPU restriction removed from the game Linux thread within app-allowed cores')
        if renderer=='virgl':
            assert 'virgl' in graphics['renderer'].lower(),graphics
            assert graphics['host_gl_renderer'],graphics
        Path('/logs/graphics-verification.json').write_text(json.dumps({key:graphics.get(key) for key in ('renderer','graphics_backend','host_gl_renderer','graphics_acceleration')},indent=2))
        with socket.socket(socket.AF_UNIX) as display:
            display.settimeout(30); display.connect('/session/display.sock')
            assert recv(display,12)==b'RFB 003.008\n';display.sendall(b'RFB 003.008\n')
            types=recv(display,recv(display,1)[0]);assert 1 in types;display.sendall(b'\1')
            assert recv(display,4)==bytes(4);display.sendall(b'\1')
            width,height=struct.unpack('>HH',recv(display,4));recv(display,16)
            if renderer=='turnip': assert (width,height)==(1280,720),(width,height)
            recv(display,struct.unpack('>I',recv(display,4))[0])
            # RGB888, little endian; raw rectangles only, matching the Android client.
            display.sendall(b'\0\0\0\0'+struct.pack('>BBBBHHHBBBxxx',32,24,0,1,255,255,255,16,8,0))
            display.sendall(struct.pack('>BBHi',2,0,1,0))
            deadline=time.monotonic()+20
            colors=Counter()
            while time.monotonic()<deadline:
                display.sendall(struct.pack('>BBHHHH',3,0,0,0,width,height))
                colors.clear()
                while True:
                    message=recv(display,1)[0]
                    if message==2: continue
                    if message==3:
                        recv(display,3);recv(display,struct.unpack('>I',recv(display,4))[0]);continue
                    assert message==0,message
                    recv(display,1);count=struct.unpack('>H',recv(display,2))[0]
                    for _ in range(count):
                        x,y,w,h,encoding=struct.unpack('>HHHHi',recv(display,12));assert encoding==0
                        pixels=recv(display,w*h*4)
                        # Depth 24 leaves the fourth byte unspecified; inspect aligned BGR only.
                        colors.update(pixels[i:i+3] for i in range(0,len(pixels),4))
                    break
                if colors[bytes([96,72,24])]>1000: break
                time.sleep(.2) # Wine Present and X damage delivery are asynchronous.
            summary={color.hex():count for color,count in colors.most_common(16)}
            Path('/logs/display-colors.json').write_text(json.dumps(summary,indent=2))
            assert colors[bytes([96,72,24])]>1000,('Direct3D output not visible in native display protocol',summary)
            if renderer=='turnip': assert colors[bytes([96,72,24])]>width*height*.95,('Fullscreen image does not fill the display',summary)
            # Focus the probe interior, then deliver a keyboard press/release.
            display.sendall(struct.pack('>BBHH',5,1,200,200)+struct.pack('>BBHH',5,0,200,200))
            display.sendall(struct.pack('>BBHI',4,1,0,ord('t'))+struct.pack('>BBHI',4,0,0,ord('t')))
            wait_for(lambda:Path('/client/probe-key.txt').exists() and Path('/client/probe-mouse.txt').exists(),'Display input did not reach the 32-bit Windows program',15)
            display.sendall(struct.pack('>BBHI',4,1,0,ord('w')))
            wait_for(lambda:Path('/client/probe-held-key.txt').exists(),'Held movement key did not reach DirectInput state',15)
            time.sleep(.35)
            display.sendall(struct.pack('>BBHI',4,0,0,ord('w')))
            wait_for(lambda:Path('/client/probe-released-key.txt').exists(),'DirectInput movement key did not release',15)
        wait_for(lambda:json.loads(Path('/session/status.json').read_text()).get('model_libraries_loaded')=={'d3dx9_30.dll':'native','d3dx9_35.dll':'native'}, 'Native model load evidence not recognized',15)
        print('PASS: held W movement key and release reach polled DirectInput keyboard state')
        wait_for(lambda:json.loads(Path('/session/status.json').read_text()).get('native_loaded'), 'Native DLL trace not recognized',15)
        wait_for(lambda:json.loads(Path('/session/status.json').read_text()).get('system_dinput8_loaded'), 'System DirectInput forwarding trace not recognized',15)
        # A negative control must reproduce the old native-only bug. Each check
        # is a separate Windows process while the private X display is alive.
        env=client_runner.Supervisor(request).env
        command=['/usr/local/bin/box64','/opt/wine/bin/wine',r'D:\eqgame.exe','--check-directinput']
        with Path('/logs/client-proxy-regression.log').open('wb') as output:
            for override,expected in [('n',23),('n,b',0)]:
                result=subprocess.run(command,cwd='/client',env=dict(env,WINEDLLOVERRIDES=env['WINEDLLOVERRIDES']+';dinput8='+override),
                                      stdin=subprocess.DEVNULL,stdout=output,stderr=output,timeout=60)
                assert result.returncode==expected,(override,result.returncode,expected)
                print(f'PASS: system DirectInput forwarding with override {override}: exit {result.returncode}')
        timings={}
        for verbose in (False,True):
            label='verbose' if verbose else 'normal'
            path=Path('/logs/client-debug-'+label+'.log')
            started=time.monotonic()
            with path.open('wb') as output:
                result=subprocess.run(command[:-1]+['--check-debug-output'],cwd='/client',
                    env=dict(env,WINEDLLOVERRIDES=env['WINEDLLOVERRIDES']+';dinput8=n,b',WINEDEBUG=client_runner.wine_debug(verbose)),
                    stdin=subprocess.DEVNULL,stdout=output,stderr=output,timeout=60)
            assert result.returncode==0,(label,result.returncode)
            trace=path.read_text(errors='replace')
            assert client_runner.dll_status(trace)['native_loaded'],label
            assert client_runner.dll_status(trace)['system_dinput8_loaded'],label
            assert ('trace:seh:dispatch_exception' in trace)==verbose,label
            timings[label]={'seconds':round(time.monotonic()-started,3),'bytes':path.stat().st_size}
        assert timings['normal']['bytes'] < timings['verbose']['bytes']/5,timings
        Path('/logs/client-debug-comparison.json').write_text(json.dumps({'debug_strings':512,'results':timings},indent=2))
        print('PASS: 512 debug-string calls with normal vs verbose logging (timing informational): '+json.dumps(timings))
        with Path('/logs/texture-shaders.log').open('wb') as out:
            result=subprocess.run(['/usr/local/bin/box64','/opt/wine/bin/wine',r'D:\textures.exe'],cwd='/client',
                env=dict(env,WINEDLLOVERRIDES=env['WINEDLLOVERRIDES']+';d3dx9_35=n,b'),stdout=out,stderr=out,timeout=90)
        assert result.returncode==0,('D3D texture/legacy shader regression', result.returncode,Path('/logs/texture-shaders.log').read_text(errors='replace')[-8000:])
        print('PASS: D3D compressed artwork and SM1/2 specular-fog shader pixels')
        check_models(env)
        if renderer!='turnip': check_graphics_threading(env)
        compatible=client_runner.Supervisor(dict(request,cpu_profile='compatibility')).env
        check_compatibility_exit(compatible)
        print('PASS: ARM64 PE32 native proxy forwards to system DirectInput8, creates keyboard/mouse devices, renders Direct3D9 and receives private-display input')
    finally:
        Path('/session/stop').touch()
        try: runner.wait(timeout=25)
        except subprocess.TimeoutExpired: runner.kill();runner.wait();raise

    # A second real supervisor launch uses the same checked prefix, but boots
    # services without repeating forced file registration. No test-only bypass.
    cold=json.loads(Path('/session/status.json').read_text())
    system=Path('/prefix/drive_c/windows/syswow64/kernel32.dll')
    original_mtime=system.stat().st_mtime_ns
    Path('/session/stop').unlink()
    warm_request=dict(request,mode='desktop',renderer='software' if renderer=='turnip' else renderer)
    Path('/session/request.json').write_text(json.dumps(warm_request))
    runner=subprocess.Popen(['python3','/opt/trasc-client/client_runner.py'])
    try:
        def warm_ready():
            state=json.loads(Path('/session/status.json').read_text())
            if runner.poll() is not None or state.get('phase')=='error':raise AssertionError(state)
            return state.get('phase')=='launch_requested' and state.get('prefix_update')=='reuse'
        wait_for(warm_ready,'Warm Wine startup failed or did not reuse prefix')
        warm=json.loads(Path('/session/status.json').read_text())
        assert warm['wine32_ready'],warm
        assert system.stat().st_mtime_ns==original_mtime,'Warm boot rewrote Wine system files'
        if renderer=='turnip':
            fallback=client_runner.Supervisor(warm_request).env
            with Path('/logs/vulkan-fallback.log').open('wb') as out:
                result=subprocess.run(['/usr/local/bin/box64','/opt/wine/bin/wine',r'D:\textures.exe'],cwd='/client',
                    env=dict(fallback,WINEDLLOVERRIDES=fallback['WINEDLLOVERRIDES']+';d3dx9_35=n,b'),stdout=out,stderr=out,timeout=90)
            assert result.returncode==0,('WineD3D fallback after DXVK',result.returncode)
            assert 'DXVK: v2.5.3' not in Path('/logs/vulkan-fallback.log').read_text(errors='replace')
            print('PASS: WineD3D recovery renders real shader/texture pixels after DXVK without prefix repair')
        Path('/logs/client-startup-comparison.json').write_text(json.dumps({
            'cold':cold['timings_seconds'],'warm':warm['timings_seconds'],
            'warm_prefix_reused':True,'note':'Host startup timings; not Android game FPS.'},indent=2))
        print('PASS: real warm Wine boot preserves system files and passes the PE32 loader check')
    finally:
        Path('/session/stop').touch()
        try:runner.wait(timeout=25)
        except subprocess.TimeoutExpired:runner.kill();runner.wait();raise


def check_compatibility_exit(env):
    # A recurring CI-only SIGKILL follows successful pixels. Retain the strict
    # exit assertion, but collect teardown stages, Wine process/module traces,
    # native wait state and cgroup OOM counters instead of silently retrying.
    def counters():
        report={}
        for name in ('/sys/fs/cgroup/memory.events','/sys/fs/cgroup/memory/memory.failcnt'):
            try:report[name]=Path(name).read_text()[:4096]
            except OSError:pass
        return report
    evidence={'before':counters(),'samples':[]}
    started=time.monotonic()
    with Path('/logs/compatibility-textures.log').open('wb') as out:
        child=subprocess.Popen(['/usr/local/bin/box64','/opt/wine/bin/wine',r'D:\textures.exe'],cwd='/client',
            env=dict(env,WINEDLLOVERRIDES=env['WINEDLLOVERRIDES']+';d3dx9_35=n,b',
                     WINEDEBUG=env.get('WINEDEBUG','')+',trace+process,trace+module'),stdout=out,stderr=out)
        try:
            while child.poll() is None:
                if time.monotonic()-started>90:raise subprocess.TimeoutExpired(child.args,90)
                sample={'seconds':round(time.monotonic()-started,3),'pid':child.pid}
                for name in ('stat','wchan','syscall'):
                    try:sample[name]=Path('/proc',str(child.pid),name).read_text()[:4096]
                    except OSError:pass
                evidence['samples'].append(sample)
                if len(evidence['samples'])>512:del evidence['samples'][0]
                time.sleep(.025)
        finally:
            if child.poll() is None:child.kill();child.wait()
            evidence.update(after=counters(),returncode=child.returncode,seconds=round(time.monotonic()-started,3))
            Path('/logs/compatibility-exit.json').write_text(json.dumps(evidence,indent=2))
    assert child.returncode==0,('Compatibility CPU profile texture/shader check',child.returncode)


def check_graphics_threading(env):
    for mode,setting in [('multi','1'),('single','0'),('opengl_worker','0')]:
        path=Path('/logs/threading-'+mode+'.log')
        selected=dict(env,WINE_D3D_CONFIG='csmt='+setting,
                      mesa_glthread='true' if mode=='opengl_worker' else 'false',
                      WINEDLLOVERRIDES=env['WINEDLLOVERRIDES']+';d3dx9_35=n,b')
        with path.open('wb') as out:
            result=subprocess.run(['/usr/local/bin/box64','/opt/wine/bin/wine',r'D:\textures.exe','--present-telemetry'],
                cwd='/client',env=selected,stdout=out,stderr=out,timeout=90)
        assert result.returncode==0,(mode,result.returncode)
        capture=client_runner.WineLog(Path('/logs/threading-'+mode+'-captured.log'))
        with path.open('rb') as stream:capture.pump(stream)
        fields,error=capture.snapshot()
        assert not error,error
        assert fields.get('graphics_threading_observed')==('multi' if mode=='multi' else 'single'),fields
        assert fields.get('wine_present',{}).get('per_second',0)>0,fields
        assert 'trace:frametime' not in path.read_text(errors='replace')
        Path('/logs/threading-'+mode+'.json').write_text(json.dumps(fields,indent=2))
    check_models(dict(env,WINE_D3D_CONFIG='csmt=0',mesa_glthread='false'),'single-')
    check_models(dict(env,WINE_D3D_CONFIG='csmt=0',mesa_glthread='true'),'opengl-worker-')
    print('PASS: all three graphics threading modes preserve artwork/shader pixels and emit real aggregate Wine presentation rates; single and OpenGL-worker native models animate')


def check_models(env,label=''):
    for marker in ('model-ready.json','model-stop.txt'):Path('/client',marker).unlink(missing_ok=True)
    command=['/usr/local/bin/box64','/opt/wine/bin/wine',r'D:\models.exe']
    with Path('/logs/'+label+'model-builtin.log').open('wb') as out:
        result=subprocess.run(command+['--once'],cwd='/client',
            env=dict(env,WINEDLLOVERRIDES=env['WINEDLLOVERRIDES']+';d3dx9_30=b;d3dx9_35=b'),
            stdin=subprocess.DEVNULL,stdout=out,stderr=out,timeout=60)
    assert result.returncode==31,('Expected built-in animation E_NOTIMPL',result.returncode)
    print('PASS: Wine built-in model negative control reproduces E_NOTIMPL')
    with Path('/logs/'+label+'model-native.log').open('wb') as out:
        model=subprocess.Popen(command,cwd='/client',
            env=dict(env,WINEDLLOVERRIDES=env['WINEDLLOVERRIDES']+';d3dx9_30=n,b;d3dx9_35=n,b'),
            stdin=subprocess.DEVNULL,stdout=out,stderr=out)
        try:
            def ready():
                if model.poll() is not None: raise AssertionError('Native model probe exited: '+str(model.returncode))
                return Path('/client/model-ready.json').exists()
            wait_for(ready,'Native model functions / render did not become ready',45)
            centers=[]
            with socket.socket(socket.AF_UNIX) as display:
                display.settimeout(15);display.connect('/session/display.sock')
                assert recv(display,12)==b'RFB 003.008\n';display.sendall(b'RFB 003.008\n')
                types=recv(display,recv(display,1)[0]);assert 1 in types;display.sendall(b'\1')
                assert recv(display,4)==bytes(4);display.sendall(b'\1')
                width,height=struct.unpack('>HH',recv(display,4));recv(display,16);recv(display,struct.unpack('>I',recv(display,4))[0])
                display.sendall(b'\0\0\0\0'+struct.pack('>BBBBHHHBBBxxx',32,24,0,1,255,255,255,16,8,0))
                display.sendall(struct.pack('>BBHi',2,0,1,0))
                for _ in range(20):
                    display.sendall(struct.pack('>BBHHHH',3,0,0,0,width,height))
                    positions=[]
                    while True:
                        message=recv(display,1)[0]
                        if message==2:continue
                        if message==3:recv(display,3);recv(display,struct.unpack('>I',recv(display,4))[0]);continue
                        assert message==0,message
                        recv(display,1);count=struct.unpack('>H',recv(display,2))[0]
                        for _ in range(count):
                            x,y,w,h,encoding=struct.unpack('>HHHHi',recv(display,12));assert encoding==0
                            pixels=recv(display,w*h*4)
                            positions.extend(x+i//4%w for i in range(0,len(pixels),4) if pixels[i:i+3]==bytes([32,128,224]))
                        break
                    if len(positions)>1000:centers.append(sum(positions)/len(positions))
                    if len(centers)>1 and max(centers)-min(centers)>5:break
                    time.sleep(.17)
            assert len(centers)>1 and max(centers)-min(centers)>5,('Animated skinned mesh not visible/moving',centers)
            trace=Path('/logs/'+label+'model-native.log').read_text(errors='replace')
            assert client_runner.model_dll_status(trace)[0]=={'d3dx9_30.dll':'native','d3dx9_35.dll':'native'}
            Path('/logs/'+label+'model-verification.json').write_text(json.dumps({'visible_model_centers':centers,'native_d3dx':True}))
            print('PASS: native D3DX30/35 registration, sampling, compression, skinning and animated model pixels in private display')
        finally:
            Path('/client/model-stop.txt').touch()
            try:code=model.wait(timeout=10)
            except subprocess.TimeoutExpired:model.kill();model.wait();raise
        assert code==0,code


if __name__=='__main__': main()
