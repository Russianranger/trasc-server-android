#!/usr/bin/env python3
"""Reproduce PointerRoot/Wine foreground divergence and qualify scoped repair."""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

from integration_takp_cursor import wait_file
from takp_input_transport import TrascInputTransport

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from client_xauthority import write_xauthority

MARKER = 'TRASC_TAKP_X_FOCUS_RECOVERY_V1'


def run(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    prefix = out / 'prefix'
    prefix.mkdir(exist_ok=True)
    authority = out / 'Xauthority'
    write_xauthority(authority, 33)
    (out / 'box64.rc').write_text('[wine]\nBOX64_MAXCPU=0\n[wine64]\nBOX64_MAXCPU=0\n'
        '[explorer.exe]\nBOX64_DYNAREC_BIGBLOCK=0\n'
        '[eqgame.exe]\nBOX64_DYNAREC_BIGBLOCK=2\nBOX64_DYNAREC_SAFEFLAGS=1\nBOX64_DYNAREC_STRONGMEM=1\n')
    env = dict(os.environ, DISPLAY=':33', XAUTHORITY=str(authority), WINEPREFIX=str(prefix),
        WINEARCH='win64', WINEDEBUG='-all,+timestamp,+cursor,+event,+dinput',
        WINEDLLOVERRIDES='winemenubuilder,mscoree,mshtml=', WINESERVER='/opt/wine/bin/wineserver',
        BOX64_DYNAREC_STRONGMEM='1', BOX64_DYNAREC_BIGBLOCK='2', BOX64_DYNAREC_SAFEFLAGS='1',
        BOX64_DYNAREC_X87DOUBLE='1', BOX64_DYNAREC_FASTNAN='0', BOX64_DYNAREC_FASTROUND='0',
        BOX64_SYNC_ROUNDING='1', BOX64_MAXCPU='0', BOX64_LOG='1', BOX64_NOBANNER='0',
        BOX64_PATH='/opt/wine/bin', BOX64_RCFILE=str(out / 'box64.rc'),
        BOX64_LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/opt/wine/lib/wine/x86_64-unix',
        TRASC_FIXTURE_CONFIGURATION=str(out / 'prefix-configuration.json'))
    env.pop('TRASC_FIXTURE_GLOBAL_GRAB', None)
    env.pop('TRASC_FIXTURE_APP_GRAB', None)
    os.environ['DISPLAY'], os.environ['XAUTHORITY'] = ':33', str(authority)
    logs = {name: (out / (name + '.log')).open('wb') for name in ('display', 'wine', 'observer', 'focus')}
    server = subprocess.Popen(['Xtigervnc', ':33', '-geometry', '800x600', '-depth', '24',
        '-rfbport', '-1', '-rfbunixpath', str(out / 'display.sock'), '-rfbunixmode', '0600',
        '-SecurityTypes', 'None', '-nolisten', 'tcp', '-nolock', '-auth', str(authority),
        '-AlwaysShared', '-FrameRate', '60', '-desktop', 'TRASC client'], stdout=logs['display'], stderr=subprocess.STDOUT)
    x = C.CDLL(ctypes.util.find_library('X11'))
    display = None
    child = observer = companion = transport = None
    evidence = []
    x.XOpenDisplay.argtypes = [C.c_char_p]; x.XOpenDisplay.restype = C.c_void_p
    x.XDefaultRootWindow.argtypes = [C.c_void_p]; x.XDefaultRootWindow.restype = C.c_ulong
    x.XGetInputFocus.argtypes = [C.c_void_p,C.POINTER(C.c_ulong),C.POINTER(C.c_int)]
    x.XSetInputFocus.argtypes = [C.c_void_p,C.c_ulong,C.c_int,C.c_ulong]
    x.XQueryPointer.argtypes = [C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),
        C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_uint)]
    x.XSync.argtypes = [C.c_void_p,C.c_int]
    x.XCloseDisplay.argtypes = [C.c_void_p]
    x.XStoreName.argtypes = [C.c_void_p,C.c_ulong,C.c_char_p]
    x.XInternAtom.argtypes = [C.c_void_p,C.c_char_p,C.c_int]; x.XInternAtom.restype = C.c_ulong
    x.XChangeProperty.argtypes = [C.c_void_p,C.c_ulong,C.c_ulong,C.c_ulong,C.c_int,C.c_int,C.c_void_p,C.c_int]
    x.XCreateSimpleWindow.argtypes = [C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_uint,C.c_ulong,C.c_ulong]
    x.XCreateSimpleWindow.restype = C.c_ulong
    x.XMapRaised.argtypes = [C.c_void_p,C.c_ulong]
    x.XUnmapWindow.argtypes = [C.c_void_p,C.c_ulong]
    x.XDestroyWindow.argtypes = [C.c_void_p,C.c_ulong]
    try:
        for _ in range(100):
            display = x.XOpenDisplay(b':33')
            if display: break
            if server.poll() is not None: raise RuntimeError('Published Xvnc failed')
            time.sleep(.05)
        if not display: raise RuntimeError('Published Xvnc did not become ready')
        root = x.XDefaultRootWindow(display)
        def focus():
            value, revert = C.c_ulong(), C.c_int()
            x.XGetInputFocus(display,C.byref(value),C.byref(revert))
            return value.value
        def set_focus(value):
            x.XSetInputFocus(display,value,1,0); x.XSync(display,False)
        def point():
            r,c = C.c_ulong(),C.c_ulong()
            rx,ry,wx,wy = C.c_int(),C.c_int(),C.c_int(),C.c_int(); mask = C.c_uint()
            assert x.XQueryPointer(display,root,C.byref(r),C.byref(c),C.byref(rx),C.byref(ry),C.byref(wx),C.byref(wy),C.byref(mask))
            return (rx.value,ry.value),mask.value
        observer = subprocess.Popen([str(args.observer),'300'],env=env,stdout=logs['observer'],stderr=subprocess.STDOUT)
        subprocess.run([str(args.wine),'wineboot','-u'],env=env,stdout=logs['wine'],stderr=subprocess.STDOUT,check=True,timeout=120)
        drive = prefix / 'dosdevices/d:'
        drive.unlink(missing_ok=True); drive.symlink_to(out)
        (out / 'cursor-probe.exe').write_bytes(args.probe.read_bytes())
        child = subprocess.Popen([str(args.wine),'explorer','/desktop=TRASC,800x600',r'D:\cursor-probe.exe'],
            env=env,stdout=logs['wine'],stderr=subprocess.STDOUT)
        wait_file(out / 'reply.txt','ready',child)
        transport = TrascInputTransport(args.assets / 'input-probe',out / 'input.sock',env,out / 'input-transport.log')
        sequence = 0
        def command(mode):
            nonlocal sequence
            sequence += 1; value = f'{mode} {sequence}'
            temporary = out / 'command.new'; temporary.write_text(value); temporary.replace(out / 'command.txt')
            return wait_file(out / 'reply.txt',value,child,prefix=mode in ('sample','clipmetrics'))
        def sample():
            v = list(map(int,command('sample').split()[2:])); assert len(v)==14,v
            return {'state':v[:2],'buffered':v[2:4],'rmb':bool(v[4]),'cursor':v[5:7],
                'clip':v[7:11],'foreground':bool(v[11]),'focused':bool(v[12]),'visible':bool(v[13])}
        def record(stage):
            value = {'stage':stage,'native':sample(),'x_focus':focus(),'x_pointer':point()[0],'buttons_mask':point()[1]}
            evidence.append(value); (out / 'focus-diagnostics.json').write_text(json.dumps(evidence,indent=2)+'\n')
            print(json.dumps(value),flush=True); return value
        def difference(before,after,kind): return [after[kind][i]-before[kind][i] for i in range(2)]
        def repair_rows():
            return [json.loads(line) for line in (out / 'focus.log').read_text().splitlines()
                    if line.startswith('{') and json.loads(line).get('record')=='focus_repair']
        def held():
            transport.button(False); command('focus'); command('raw'); time.sleep(.15)
            transport.button(True); time.sleep(.3)
            value=record('healthy-held')
            assert value['native']['foreground'] and value['native']['rmb'] and value['native']['visible'],value
            assert value['native']['clip']==[400,300,401,301] and value['x_pointer']==(400,300),value
            assert value['x_focus'] not in (0,1),value
        command('input'); command('focus'); time.sleep(.2)
        game_window = focus(); assert game_window not in (0,1)
        original_clip = sample()['clip']
        held()
        # Fault injection changes actual X focus only. No Window focus command,
        # fresh button press, recenter or raw-consumer reset occurs afterward.
        set_focus(1); time.sleep(.35)
        lost = record('pointer-root-before-input')
        assert lost['x_focus']==1 and lost['native']['foreground'] and lost['native']['rmb'],lost
        assert lost['native']['clip']==[400,300,401,301],lost
        transport.motion(3,0); time.sleep(.08)
        before=sample(); transport.motion(-1,0); time.sleep(.08); after=sample()
        broken = {'injected':[-1,0],'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered')}
        escaped = record('pointer-root-wrong-reversal')
        assert escaped['x_focus']==1 and escaped['x_pointer']!=(400,300),escaped
        assert broken['polled'][0]>=0 and broken['buffered'][0]>=0,broken
        companion = subprocess.Popen([str(args.focus_helper)],env=env,stdout=logs['focus'],stderr=subprocess.STDOUT)
        until=time.monotonic()+3
        while time.monotonic()<until and (focus() in (0,1) or point()[0]!=(400,300)):
            if companion.poll() is not None: raise RuntimeError('Focus helper exited early')
            time.sleep(.02)
        fixed=record('scoped-focus-recovered')
        assert fixed['x_focus']==game_window and fixed['x_pointer']==(400,300),fixed
        assert any(row['success'] and row['before']==1 for row in repair_rows()),repair_rows()
        signed=[]
        for dx,dy in ((1,0),(-1,0),(2,0),(-2,0),(0,1),(0,-1),(0,2),(0,-2),(2,-1),(-2,1)):
            before=sample()
            transport.paced(((dx,dy) for _ in range(12)),.016)
            time.sleep(.12); after=sample(); expected=[12*dx,12*dy]
            row={'injected':expected,'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered')}
            assert row['polled']==expected and row['buffered']==expected,row
            assert point()[0]==(400,300),point()
            signed.append(row)
        before=sample(); time.sleep(.3); after=sample()
        assert difference(before,after,'state')==[0,0] and difference(before,after,'buffered')==[0,0],(before,after)
        transport.button(False); time.sleep(.15); assert sample()['clip']==original_clip
        transport.absolute(400,300); transport.motion(30,-20); time.sleep(.15)
        assert point()[0]==(430,280),point()
        guards=[]
        def guard(name,expected_focus):
            count=len(repair_rows()); time.sleep(.35)
            value=record(name)
            assert value['x_focus']==expected_focus and len(repair_rows())==count,(value,repair_rows())
            guards.append({'case':name,'focus':expected_focus,'repairs_added':0})
        set_focus(1); guard('released-button-does-not-focus',1)
        held()
        foreign=x.XCreateSimpleWindow(display,root,10,10,40,40,0,0,0)
        x.XStoreName(display,foreign,b'TRASC unrelated dialog'); x.XMapRaised(display,foreign); x.XSync(display,False)
        set_focus(foreign); guard('concrete-foreign-focus-preserved',foreign)
        transport.button(False); x.XDestroyWindow(display,foreign); x.XSync(display,False)
        held(); x.XStoreName(display,game_window,b'Unrelated game title'); x.XSync(display,False)
        set_focus(1); guard('wrong-title-does-not-focus',1)
        transport.button(False); x.XStoreName(display,game_window,b'EqW-TAKP'); x.XSync(display,False)
        held()
        klass=x.XInternAtom(display,b'WM_CLASS',False); string=x.XInternAtom(display,b'STRING',False)
        def set_class(value):
            data=C.create_string_buffer(value); x.XChangeProperty(display,game_window,klass,string,8,0,data,len(value)); x.XSync(display,False)
        set_class(b'other.exe\0other.exe\0'); set_focus(1); guard('wrong-class-does-not-focus',1)
        transport.button(False); set_class(b'eqgame.exe\0eqgame.exe\0')
        held()
        cover=x.XCreateSimpleWindow(display,root,350,250,100,100,0,0,0)
        x.XStoreName(display,cover,b'Other app under pointer'); x.XMapRaised(display,cover); x.XSync(display,False)
        set_focus(1); guard('foreign-pointer-window-does-not-focus',1)
        transport.button(False); x.XDestroyWindow(display,cover); x.XSync(display,False)
        held(); command('blur'); time.sleep(.15); set_focus(1); guard('minimized-game-does-not-focus',1)
        assert sample()['clip']==original_clip
        transport.button(False); command('resume'); time.sleep(.15)
        held(); set_focus(0); time.sleep(.4)
        restored=record('none-focus-recovered-after-resume')
        assert restored['x_focus']==game_window and restored['x_pointer']==(400,300),restored
        assert any(row['success'] and row['before']==0 for row in repair_rows()),repair_rows()
        transport.button(False); time.sleep(.15); assert sample()['clip']==original_clip
        command('quit'); assert child.wait(timeout=15)==0
        transport.close()
        counts=transport.summary()
        assert counts['native_decoded']=={key:counts[key] for key in ('relative','absolute','buttons')},counts
        companion.terminate(); assert companion.wait(timeout=3)==0
        observer.terminate(); assert observer.wait(timeout=3)==0
        for stream in logs.values(): stream.flush()
        focus_rows=[json.loads(line) for line in (out / 'focus.log').read_text().splitlines()]
        assert focus_rows[0]['marker']==MARKER and focus_rows[-1]['record']=='end',focus_rows
        assert (out / 'focus.log').stat().st_size<=131072
        source_root=Path(__file__).resolve().parents[1]
        sources=('tests/integration_takp_focus.py','tests/takp_focus_probe.cpp','tests/takp_cursor_probe.cpp',
            'tests/takp_box64_wine.py','tests/takp_input_transport.py','scripts/prepare-takp-focus-runtime.py',
            'scripts/prepare-takp-camera-runtime.py','native/takp_camera_recenter.h','native/takp_camera_trace.h',
            'native/takp_dinput_observation.h','native/presentation/input.h','native/presentation/takp-xinput-focus.c',
            'native/presentation/takp-xinput-observe.c','native/presentation/observe-log.h','tests/takp_focus_tools.Dockerfile')
        receipt={'format':1,'github_commit':os.environ.get('GITHUB_SHA'),'github_run_id':os.environ.get('GITHUB_RUN_ID'),
            'published_inputs':json.loads((args.assets / 'published-inputs.json').read_text()),
            'fixture_sha256':{name:hashlib.sha256((source_root / name).read_bytes()).hexdigest() for name in sources},
            'focus_helper_sha256':hashlib.sha256(args.focus_helper.read_bytes()).hexdigest(),
            'observer_sha256':hashlib.sha256(args.observer.read_bytes()).hexdigest(),
            'pointer_root_reproduction':{'native_foreground_preserved':True,'cached_clip_preserved':True,
                'pointer_escaped':escaped['x_pointer'],'negative_reversal':broken},
            'recovery':{'candidate':game_window,'signed_segments':signed,'idle_drift':[0,0],
                'physical_cursor_confined':True,'focus_none_after_resume':True,'rmb_release_restores_clip':True,'menu_pointer_free':True},
            'negative_guards':guards,'focus_repairs':repair_rows(),'transport':counts,
            'scope':'Published ARM64 runtime/open PE32 consumer with exact game identity; physical Thor acceptance pending'}
        (out / 'focus-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
    finally:
        if transport: transport.close()
        for process in (companion,observer,child):
            if process and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
        if display: x.XCloseDisplay(display)
        server.terminate(); server.wait(timeout=10)
        for stream in logs.values(): stream.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('wine','probe','observer','focus-helper','assets','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    for name in ('wine','probe','observer','focus_helper','assets','output'):
        setattr(args,name,getattr(args,name).resolve())
    if platform.machine() not in ('aarch64','arm64'): raise RuntimeError('Native ARM64 runner required')
    run(args)
