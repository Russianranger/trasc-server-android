#!/usr/bin/env python3
"""Qualify bounded read-only window metadata in the published ARM64 runtime."""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from integration_takp_cursor import wait_file
from takp_input_transport import TrascInputTransport
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'backend'))
from client_xauthority import write_xauthority

MARKER='TRASC_TAKP_WINDOW_INSPECT_V1'
TITLE=b'EqW-TAKP'
CLASS=b'eqgame.exe\0eqgame.exe\0'


def run(args):
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    prefix=out/'prefix';prefix.mkdir(exist_ok=True)
    auth=out/'Xauthority';write_xauthority(auth,33)
    (out/'box64.rc').write_text('[wine]\nBOX64_MAXCPU=0\n[wine64]\nBOX64_MAXCPU=0\n'
        '[explorer.exe]\nBOX64_DYNAREC_BIGBLOCK=0\n'
        '[eqgame.exe]\nBOX64_DYNAREC_BIGBLOCK=2\nBOX64_DYNAREC_SAFEFLAGS=1\nBOX64_DYNAREC_STRONGMEM=1\n')
    env=dict(os.environ,DISPLAY=':33',XAUTHORITY=str(auth),WINEPREFIX=str(prefix),WINEARCH='win64',
        WINEDEBUG='-all,+timestamp,+cursor,+event,+dinput',WINEDLLOVERRIDES='winemenubuilder,mscoree,mshtml=',
        WINESERVER='/opt/wine/bin/wineserver',BOX64_DYNAREC_STRONGMEM='1',BOX64_DYNAREC_BIGBLOCK='2',
        BOX64_DYNAREC_SAFEFLAGS='1',BOX64_DYNAREC_X87DOUBLE='1',BOX64_DYNAREC_FASTNAN='0',
        BOX64_DYNAREC_FASTROUND='0',BOX64_SYNC_ROUNDING='1',BOX64_MAXCPU='0',BOX64_LOG='1',BOX64_NOBANNER='0',
        BOX64_PATH='/opt/wine/bin',BOX64_RCFILE=str(out/'box64.rc'),
        BOX64_LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/opt/wine/lib/wine/x86_64-unix',
        TRASC_FIXTURE_CONFIGURATION=str(out/'prefix-configuration.json'))
    env.pop('TRASC_FIXTURE_GLOBAL_GRAB',None);env.pop('TRASC_FIXTURE_APP_GRAB',None)
    os.environ['DISPLAY'],os.environ['XAUTHORITY']=':33',str(auth)
    logs={name:(out/(name+'.log')).open('wb') for name in ('display','wine','observer','focus')}
    server=subprocess.Popen(['Xtigervnc',':33','-geometry','800x600','-depth','24','-rfbport','-1',
        '-rfbunixpath',str(out/'display.sock'),'-rfbunixmode','0600','-SecurityTypes','None','-nolisten','tcp',
        '-nolock','-auth',str(auth),'-AlwaysShared','-FrameRate','60','-desktop','TRASC client'],
        stdout=logs['display'],stderr=subprocess.STDOUT)
    x=C.CDLL(ctypes.util.find_library('X11'));display=None;child=observer=focus_helper=transport=None
    x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
    x.XDefaultRootWindow.argtypes=[C.c_void_p];x.XDefaultRootWindow.restype=C.c_ulong
    x.XGetInputFocus.argtypes=[C.c_void_p,C.POINTER(C.c_ulong),C.POINTER(C.c_int)]
    x.XSetInputFocus.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_ulong]
    x.XQueryPointer.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),
        C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_uint)]
    x.XSync.argtypes=[C.c_void_p,C.c_int];x.XCloseDisplay.argtypes=[C.c_void_p]
    x.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int];x.XInternAtom.restype=C.c_ulong
    x.XChangeProperty.argtypes=[C.c_void_p,C.c_ulong,C.c_ulong,C.c_ulong,C.c_int,C.c_int,C.c_void_p,C.c_int]
    x.XDeleteProperty.argtypes=[C.c_void_p,C.c_ulong,C.c_ulong]
    x.XCreateSimpleWindow.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_uint,C.c_ulong,C.c_ulong]
    x.XCreateSimpleWindow.restype=C.c_ulong
    x.XMapRaised.argtypes=[C.c_void_p,C.c_ulong];x.XDestroyWindow.argtypes=[C.c_void_p,C.c_ulong]
    x.XMoveWindow.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_int]
    cases=[]
    try:
        for _ in range(100):
            display=x.XOpenDisplay(b':33')
            if display:break
            if server.poll() is not None:raise RuntimeError('Published Xvnc failed')
            time.sleep(.05)
        if not display:raise RuntimeError('Published Xvnc unavailable')
        root=x.XDefaultRootWindow(display)
        def state():
            focus,revert=C.c_ulong(),C.c_int();x.XGetInputFocus(display,C.byref(focus),C.byref(revert))
            r,c=C.c_ulong(),C.c_ulong();rx,ry,wx,wy=C.c_int(),C.c_int(),C.c_int(),C.c_int();mask=C.c_uint()
            assert x.XQueryPointer(display,root,C.byref(r),C.byref(c),C.byref(rx),C.byref(ry),C.byref(wx),C.byref(wy),C.byref(mask))
            return {'focus':focus.value,'pointer':[rx.value,ry.value],'buttons_mask':mask.value}
        def set_focus(window):x.XSetInputFocus(display,window,1,0);x.XSync(display,False)
        subprocess.run([str(args.wine),'wineboot','-u'],env=env,stdout=logs['wine'],stderr=subprocess.STDOUT,check=True,timeout=120)
        drive=prefix/'dosdevices/d:';drive.unlink(missing_ok=True);drive.symlink_to(out)
        (out/'cursor-probe.exe').write_bytes(args.probe.read_bytes())
        child=subprocess.Popen([str(args.wine),'explorer','/desktop=TRASC,800x600',r'D:\cursor-probe.exe'],
            env=env,stdout=logs['wine'],stderr=subprocess.STDOUT)
        wait_file(out/'reply.txt','ready',child)
        sequence=0
        def command(mode):
            nonlocal sequence
            sequence+=1;value=f'{mode} {sequence}'
            tmp=out/'command.new';tmp.write_text(value);tmp.replace(out/'command.txt')
            return wait_file(out/'reply.txt',value,child)
        command('input');command('focus');time.sleep(.2)
        game=state()['focus'];assert game not in (0,1),state()
        transport=TrascInputTransport(args.assets/'input-probe',out/'input.sock',env,out/'input-transport.log')
        observer=subprocess.Popen([str(args.assets/'takp-xinput-observe'),'300'],env=env,stdout=logs['observer'],stderr=subprocess.STDOUT)
        focus_helper=subprocess.Popen([str(args.assets/'takp-xinput-focus')],env=env,stdout=logs['focus'],stderr=subprocess.STDOUT)
        transport.button(True);time.sleep(.2)
        name=x.XInternAtom(display,b'WM_NAME',False);klass=x.XInternAtom(display,b'WM_CLASS',False)
        string=x.XInternAtom(display,b'STRING',False);utf8=x.XInternAtom(display,b'UTF8_STRING',False)
        cardinal=x.XInternAtom(display,b'CARDINAL',False)
        def property(atom,value,kind=string,fmt=8):
            if value is None:x.XDeleteProperty(display,game,atom)
            else:
                if fmt==8:data=C.create_string_buffer(value);count=len(value)
                elif fmt==16:data=(C.c_ushort*len(value))(*value);count=len(value)
                else:data=(C.c_ulong*len(value))(*value);count=len(value)
                x.XChangeProperty(display,game,atom,kind,fmt,0,data,count)
            x.XSync(display,False)
        def restore():
            set_focus(game);property(name,TITLE);property(klass,CLASS);time.sleep(.1)
        def inspect(label):
            before=state();path=out/(label+'.log')
            with path.open('wb') as stream:
                subprocess.run([str(args.inspector),'2'],env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=6)
            after=state();assert before==after,(label,before,after)
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            assert rows[0]['marker']==MARKER and rows[0]['read_only'] and not rows[0]['changes_focus_pointer_properties'],rows[0]
            assert rows[-1]['record']=='end' and rows[-1]['reason']=='duration' and not rows[-1]['dropped'],rows[-1]
            assert path.stat().st_size<=131072
            assert all(row.get('nodes_read',0)<=128 and row.get('nodes_enqueued',0)<=128 for row in rows)
            assert all(row.get('returned_bytes',0)<=128 for row in rows)
            case={'case':label,'before':before,'after':after,'inspector_log_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'bytes':path.stat().st_size,'records':len(rows),'completion':rows[-1]}
            cases.append(case);print(json.dumps(case),flush=True)
            return rows
        def prop(rows,key):
            return next(row for row in rows if row['record']=='property' and row['window']==game and row['property']==key)
        def candidate(rows,source='pointer_path'):
            return next(row for row in rows if row['record']=='window' and row['window']==game and row['source']==source)
        rows=inspect('natural-wine-identity');assert candidate(rows)['exact_identity']
        assert prop(rows,'WM_NAME')['hex']==TITLE.hex() and prop(rows,'WM_CLASS')['hex']==CLASS.hex()
        for label,atom,key,value in (
            ('title-optional-nul',name,'WM_NAME',TITLE+b'\0'),
            ('class-optional-nul',klass,'WM_CLASS',CLASS+b'\0')):
            restore();property(atom,value);set_focus(1);time.sleep(.15);rows=inspect(label);p=prop(rows,key)
            assert p['hex']==value.hex() and p['bytes_optional_terminal_nul'] and not p['focus_guard_exact'],p
        for label,atom,key,value in (('title-wrong-type',name,'WM_NAME',TITLE),('class-wrong-type',klass,'WM_CLASS',CLASS)):
            restore();property(atom,value,utf8);set_focus(1);time.sleep(.15);rows=inspect(label);p=prop(rows,key)
            assert p['type_name']=='UTF8_STRING' and p['hex']==value.hex() and not p['focus_guard_exact'],p
        for label,atom,key in (('missing-title',name,'WM_NAME'),('missing-class',klass,'WM_CLASS')):
            restore();property(atom,None);set_focus(1);time.sleep(.15);rows=inspect(label);p=prop(rows,key)
            assert p['type_name']=='None' and p['count']==0 and p['returned_bytes']==0 and not p['focus_guard_exact'],p
        for fmt,values,expected in ((16,[0x45,0xffff],'4500ffff'),(32,[0x45475154,0xfffffffe],'54514745feffffff')):
            restore();property(name,values,cardinal,fmt);set_focus(1);time.sleep(.15);rows=inspect('title-format-'+str(fmt));p=prop(rows,'WM_NAME')
            assert p['format']==fmt and p['hex']==expected and not p['focus_guard_exact'],p
        restore();value=b'EqW-TAKP\xff'+b'x'*300;property(name,value);set_focus(1);time.sleep(.15)
        rows=inspect('oversized-high-byte-title');p=prop(rows,'WM_NAME')
        assert p['returned_bytes']==128 and p['after']==len(value)-128 and p['hex']==value[:128].hex(),p
        restore()
        render=x.XCreateSimpleWindow(display,game,0,0,800,600,0,0,0);x.XMapRaised(display,render);x.XSync(display,False)
        rows=inspect('render-child-path');assert candidate(rows)['exact_identity']
        assert any(row['record']=='window' and row['source']=='pointer_path' and row['window']==render and row['parent']==game for row in rows)
        x.XDestroyWindow(display,render);x.XSync(display,False)
        cover=x.XCreateSimpleWindow(display,root,350,250,100,100,0,0,0);x.XMapRaised(display,cover);x.XSync(display,False)
        set_focus(1);time.sleep(.15);rows=inspect('candidate-outside-covered-pointer-path')
        assert candidate(rows,'bounded_candidate_tree')['exact_identity']
        assert not any(row['record']=='window' and row['source']=='pointer_path' and row['window']==game for row in rows)
        x.XDestroyWindow(display,cover);x.XSync(display,False);restore()
        x.XMoveWindow(display,game,1200,0);x.XSync(display,False);set_focus(1);time.sleep(.2)
        rows=inspect('candidate-outside-screen-layout');g=candidate(rows,'bounded_candidate_tree')
        assert g['x']>=800 and g['focus_guard_viewable'],g
        assert not any(row['record']=='window' and row['source']=='pointer_path' and row['window']==game for row in rows)
        x.XMoveWindow(display,game,0,0);x.XSync(display,False);restore()
        transport.button(False);time.sleep(.1);rows=inspect('idle-no-rmb')
        assert not any(row['record']=='window' for row in rows) and rows[-1]['paths']==0,rows[-1]
        for invalid in ('0','301','NaN'):
            before=state();result=subprocess.run([str(args.inspector),invalid],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=3)
            assert result.returncode==2 and before==state(),invalid
        with (out/'inspector-signal.log').open('wb') as stream:
            process=subprocess.Popen([str(args.inspector),'300'],env=env,stdout=stream,stderr=subprocess.STDOUT)
            time.sleep(.3);process.terminate();assert process.wait(timeout=3)==0
        signal_rows=[json.loads(line) for line in (out/'inspector-signal.log').read_text().splitlines()]
        assert signal_rows[-1]['record']=='end' and signal_rows[-1]['reason']=='signal',signal_rows[-1]
        command('quit');assert child.wait(timeout=15)==0;transport.close()
        for process in (observer,focus_helper):process.terminate();assert process.wait(timeout=3)==0
        counts=transport.summary();assert counts['native_decoded']=={k:counts[k] for k in ('relative','absolute','buttons')},counts
        sources=('tests/integration_takp_window.py','tests/takp_focus_probe.cpp','tests/takp_cursor_probe.cpp',
            'tests/integration_takp_cursor.py','tests/takp_box64_wine.py','tests/takp_input_transport.py',
            'scripts/prepare-takp-window-runtime.py','scripts/prepare-takp-camera-runtime.py','backend/client_xauthority.py',
            'native/presentation/takp-window-inspect.c','native/presentation/observe-log.h','tests/takp_window_tools.Dockerfile')
        source_root=Path(__file__).resolve().parents[1]
        receipt={'format':1,'github_commit':os.environ.get('GITHUB_SHA'),'github_run_id':os.environ.get('GITHUB_RUN_ID'),
            'inspector_sha256':hashlib.sha256(args.inspector.read_bytes()).hexdigest(),'marker':MARKER,
            'published_inputs':json.loads((args.assets/'published-inputs.json').read_text()),
            'fixture_sha256':{p:hashlib.sha256((source_root/p).read_bytes()).hexdigest() for p in sources},
            'cases':cases,'read_only_state_preserved':True,'invalid_cli_rejected':True,'signal_completion':signal_rows[-1],
            'transport':counts,'scope':'Diagnostic-only actual published ARM64 runtime/open PE32 fixture; no new focus repair and physical Thor identity remains unmeasured'}
        (out/'window-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
    finally:
        if transport:transport.close()
        for process in (focus_helper,observer,child):
            if process and process.poll() is None:
                process.terminate()
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        if display:x.XCloseDisplay(display)
        server.terminate();server.wait(timeout=10)
        for stream in logs.values():stream.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('wine','probe','inspector','assets','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    for name in ('wine','probe','inspector','assets','output'):setattr(args,name,getattr(args,name).resolve())
    if platform.machine() not in ('aarch64','arm64'):raise RuntimeError('Native ARM64 runner required')
    run(args)
