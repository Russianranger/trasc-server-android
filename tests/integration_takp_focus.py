#!/usr/bin/env python3
"""Qualify exact measured Client1 identity and legacy EqW focus recovery."""
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

MARKER = 'TRASC_TAKP_X_FOCUS_RECOVERY_V2'
TITLE = b'Client1'
LEGACY_TITLE = b'EqW-TAKP'
CLASS = b'eqgame.exe\0eqgame.exe\0'


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
    server = subprocess.Popen(['Xtigervnc', ':33', '-geometry', '1280x720', '-depth', '24',
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
    x.XGetWindowProperty.argtypes = [C.c_void_p,C.c_ulong,C.c_ulong,C.c_long,C.c_long,C.c_int,C.c_ulong,
        C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.c_void_p)]
    x.XDeleteProperty.argtypes = [C.c_void_p,C.c_ulong,C.c_ulong]
    x.XFree.argtypes = [C.c_void_p]
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
        def pointer_path():
            result = [root]
            for _ in range(16):
                r,c = C.c_ulong(),C.c_ulong()
                rx,ry,wx,wy = C.c_int(),C.c_int(),C.c_int(),C.c_int(); mask=C.c_uint()
                assert x.XQueryPointer(display,result[-1],C.byref(r),C.byref(c),C.byref(rx),C.byref(ry),
                    C.byref(wx),C.byref(wy),C.byref(mask)),result
                if not c.value: return result
                assert c.value not in result,result
                result.append(c.value)
            raise RuntimeError('Unexpected fixture pointer path depth')
        def read_property(window,atom):
            kind,count,after=C.c_ulong(),C.c_ulong(),C.c_ulong(); fmt=C.c_int(); data=C.c_void_p()
            assert x.XGetWindowProperty(display,window,atom,0,64,False,0,C.byref(kind),C.byref(fmt),
                C.byref(count),C.byref(after),C.byref(data))==0
            value=C.string_at(data,count.value) if data and fmt.value==8 else b''
            if data:x.XFree(data)
            return {'type':kind.value,'format':fmt.value,'count':count.value,'after':after.value,'hex':value.hex()}
        observer = subprocess.Popen([str(args.observer),'300'],env=env,stdout=logs['observer'],stderr=subprocess.STDOUT)
        subprocess.run([str(args.wine),'wineboot','-u'],env=env,stdout=logs['wine'],stderr=subprocess.STDOUT,check=True,timeout=120)
        drive = prefix / 'dosdevices/d:'
        drive.unlink(missing_ok=True); drive.symlink_to(out)
        (out / 'cursor-probe.exe').write_bytes(args.probe.read_bytes())
        child = subprocess.Popen([str(args.wine),'explorer','/desktop=TRASC,1280x720',r'D:\cursor-probe.exe'],
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
        def release_button():
            transport.button(False)
            until=time.monotonic()+1
            while time.monotonic()<until and point()[1]&1024:time.sleep(.01)
            assert not point()[1]&1024,point()
        def held():
            release_button(); command('focus')
            # Wine's cached foreground can already equal the game while actual
            # X focus is still PointerRoot after a refusal case. Establish a
            # healthy native baseline explicitly during setup, before RMB.
            # Only the later injected loss is allowed to request helper repair.
            set_focus(game_window); command('raw'); time.sleep(.15)
            transport.button(True); time.sleep(.3)
            value=record('healthy-held')
            assert value['native']['foreground'] and value['native']['rmb'] and value['native']['visible'],value
            assert value['native']['clip']==[640,360,641,361] and value['x_pointer']==(640,360),value
            assert value['x_focus'] not in (0,1),value
        command('input'); command('focus'); time.sleep(.2)
        game_window = focus(); assert game_window not in (0,1)
        name=x.XInternAtom(display,b'WM_NAME',False); klass=x.XInternAtom(display,b'WM_CLASS',False)
        string=x.XInternAtom(display,b'STRING',False); utf8=x.XInternAtom(display,b'UTF8_STRING',False)
        cardinal=x.XInternAtom(display,b'CARDINAL',False)
        title_property=read_property(game_window,name); class_property=read_property(game_window,klass)
        assert title_property=={'type':string,'format':8,'count':7,'after':0,'hex':TITLE.hex()},title_property
        assert class_property=={'type':string,'format':8,'count':22,'after':0,'hex':CLASS.hex()},class_property
        # The physical trace's game whole window owns the identifying properties;
        # its actual pointer leaf has neither WM_NAME nor WM_CLASS. Keep identity
        # and focus on the ancestor, with a native propertyless render child.
        render=x.XCreateSimpleWindow(display,game_window,0,0,1280,720,0,0,0)
        x.XMapRaised(display,render); x.XSync(display,False)
        measured_path=pointer_path()
        assert len(measured_path)==4 and measured_path[0]==root and measured_path[-2:]==[game_window,render],measured_path
        assert read_property(render,name)['type']==0 and read_property(render,klass)['type']==0
        original_clip = sample()['clip']
        held()
        # Fault injection changes actual X focus only. No Window focus command,
        # fresh button press, recenter or raw-consumer reset occurs afterward.
        set_focus(1); time.sleep(.35)
        lost = record('pointer-root-before-input')
        assert lost['x_focus']==1 and lost['native']['foreground'] and lost['native']['rmb'],lost
        assert lost['native']['clip']==[640,360,641,361],lost
        transport.motion(3,0); time.sleep(.08)
        before=sample(); transport.motion(-1,0); time.sleep(.08); after=sample()
        broken = {'injected':[-1,0],'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered')}
        escaped = record('pointer-root-wrong-reversal')
        assert escaped['x_focus']==1 and escaped['x_pointer']!=(640,360),escaped
        assert broken['polled'][0]>=0 and broken['buffered'][0]>=0,broken
        companion = subprocess.Popen([str(args.focus_helper)],env=env,stdout=logs['focus'],stderr=subprocess.STDOUT)
        until=time.monotonic()+3
        while time.monotonic()<until and (focus() in (0,1) or point()[0]!=(640,360)):
            if companion.poll() is not None: raise RuntimeError('Focus helper exited early')
            time.sleep(.02)
        fixed=record('scoped-focus-recovered')
        assert fixed['x_focus']==game_window and fixed['x_pointer']==(640,360),fixed
        assert any(row['success'] and row['before']==1 for row in repair_rows()),repair_rows()
        signed=[]
        for dx,dy in ((1,0),(-1,0),(2,0),(-2,0),(0,1),(0,-1),(0,2),(0,-2),(2,-1),(-2,1)):
            before=sample()
            transport.paced(((dx,dy) for _ in range(12)),.016)
            time.sleep(.12); after=sample(); expected=[12*dx,12*dy]
            row={'injected':expected,'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered')}
            assert row['polled']==expected and row['buffered']==expected,row
            assert point()[0]==(640,360),point()
            signed.append(row)
        before=sample(); time.sleep(.3); after=sample()
        assert difference(before,after,'state')==[0,0] and difference(before,after,'buffered')==[0,0],(before,after)
        release_button(); time.sleep(.15); assert sample()['clip']==original_clip
        transport.absolute(640,360); transport.motion(30,-20); time.sleep(.15)
        assert point()[0]==(670,340),point()
        menu_displaced=list(point()[0])
        # End the intentionally free menu phase at its original position while
        # Look is off. Starting each subsequent held guard from the displaced
        # UI pointer made ClipCursor recentering part of the next input segment.
        # Keep the real DirectInput worker running; do not reset or drain it.
        command('free');transport.absolute(640,360);time.sleep(.15)
        menu_before=sample();time.sleep(.3);menu_after=sample()
        menu_normalized={'before_pointer':menu_displaced,'free_menu_motion':[30,-20],
            'normalization_while_look_off':True,'consumer_reset_or_drain':False,
            'pointer':list(point()[0]),'rmb':menu_after['rmb'],
            'clip':menu_after['clip'],'polled':difference(menu_before,menu_after,'state'),
            'buffered':difference(menu_before,menu_after,'buffered'),'quiet_ms':300}
        assert menu_normalized['pointer']==[640,360] and not menu_normalized['rmb'],menu_normalized
        assert menu_normalized['clip']==original_clip,menu_normalized
        assert menu_normalized['polled']==[0,0] and menu_normalized['buffered']==[0,0],menu_normalized
        guards=[]
        def guard(name,expected_focus):
            count=len(repair_rows()); time.sleep(.35)
            value=record(name)
            assert value['x_focus']==expected_focus and len(repair_rows())==count,(value,repair_rows())
            guards.append({'case':name,'focus':expected_focus,'repairs_added':0})
        def property(atom,value,kind=string,fmt=8,window=game_window):
            if value is None:x.XDeleteProperty(display,window,atom)
            else:
                if fmt==8:data=C.create_string_buffer(value);count=len(value)
                elif fmt==16:data=(C.c_ushort*len(value))(*value);count=len(value)
                else:data=(C.c_ulong*len(value))(*value);count=len(value)
                x.XChangeProperty(display,window,atom,kind,fmt,0,data,count)
            x.XSync(display,False)
        def reject_property(label,atom,value,kind=string,fmt=8):
            held();property(atom,value,kind,fmt);set_focus(1);guard(label,1)
            release_button();property(name,TITLE);property(klass,CLASS)
        set_focus(1); guard('released-button-does-not-focus',1)
        held()
        foreign=x.XCreateSimpleWindow(display,root,10,10,40,40,0,0,0)
        x.XStoreName(display,foreign,b'TRASC unrelated dialog'); x.XMapRaised(display,foreign); x.XSync(display,False)
        set_focus(foreign); guard('concrete-foreign-focus-preserved',foreign)
        release_button(); x.XDestroyWindow(display,foreign); x.XSync(display,False)
        for label,value in (
            ('wrong-title-does-not-focus',b'Unrelated game title'),
            ('title-wrong-case-does-not-focus',b'client1'),
            ('title-prefix-does-not-focus',b'Client'),
            ('title-suffix-does-not-focus',b'Client10'),
            ('title-optional-nul-does-not-focus',TITLE+b'\0'),
            ('title-embedded-nul-does-not-focus',b'Client1\0unexpected'),
            ('legacy-title-prefix-does-not-focus',b'EqW'),
            ('legacy-title-suffix-does-not-focus',LEGACY_TITLE+b'-other'),
            ('legacy-title-optional-nul-does-not-focus',LEGACY_TITLE+b'\0'),
            ('missing-title-does-not-focus',None),
            ('empty-title-does-not-focus',b''),
            ('oversized-title-does-not-focus',TITLE+b'x'*300)):
            reject_property(label,name,value)
        reject_property('title-wrong-type-does-not-focus',name,TITLE,utf8)
        reject_property('title-format16-does-not-focus',name,list(TITLE),cardinal,16)
        reject_property('title-format32-does-not-focus',name,list(TITLE),cardinal,32)
        for label,value in (
            ('wrong-class-does-not-focus',b'other.exe\0other.exe\0'),
            ('class-wrong-case-does-not-focus',b'EQGAME.EXE\0EQGAME.EXE\0'),
            ('class-prefix-does-not-focus',b'eqgame\0eqgame\0'),
            ('class-suffix-does-not-focus',b'eqgame.exe2\0eqgame.exe2\0'),
            ('class-optional-nul-does-not-focus',CLASS+b'\0'),
            ('class-single-instance-does-not-focus',b'eqgame.exe\0'),
            ('missing-class-does-not-focus',None),
            ('empty-class-does-not-focus',b''),
            ('oversized-class-does-not-focus',CLASS+b'x'*300)):
            reject_property(label,klass,value)
        reject_property('class-wrong-type-does-not-focus',klass,CLASS,utf8)
        reject_property('class-format16-does-not-focus',klass,list(CLASS),cardinal,16)
        reject_property('class-format32-does-not-focus',klass,list(CLASS),cardinal,32)
        held()
        property(name,TITLE,window=render);property(klass,CLASS,window=render)
        set_focus(1);guard('duplicate-exact-ancestors-does-not-focus',1)
        release_button();property(name,None,window=render);property(klass,None,window=render)
        held()
        cover=x.XCreateSimpleWindow(display,root,590,310,100,100,0,0,0)
        x.XStoreName(display,cover,b'Other app under pointer'); x.XMapRaised(display,cover); x.XSync(display,False)
        set_focus(1); guard('foreign-pointer-window-does-not-focus',1)
        release_button(); x.XDestroyWindow(display,cover); x.XSync(display,False)
        held(); command('blur'); time.sleep(.15); set_focus(1); guard('minimized-game-does-not-focus',1)
        assert sample()['clip']==original_clip
        release_button(); command('resume'); time.sleep(.15)
        # Retain exact legacy EqW support in the same real published runtime.
        held(); property(name,LEGACY_TITLE); set_focus(1)
        until=time.monotonic()+3
        while time.monotonic()<until and (focus()!=game_window or point()[0]!=(640,360)):
            if companion.poll() is not None:raise RuntimeError('Focus helper exited during legacy check')
            time.sleep(.02)
        legacy=record('legacy-eqw-focus-recovered')
        assert legacy['x_focus']==game_window and legacy['x_pointer']==(640,360),legacy
        legacy_before=sample();time.sleep(.3);legacy_after=sample()
        legacy_quiet={'polled':difference(legacy_before,legacy_after,'state'),
            'buffered':difference(legacy_before,legacy_after,'buffered'),'quiet_ms':300,
            'pointer':list(point()[0]),'clip':legacy_after['clip'],'rmb':legacy_after['rmb']}
        assert legacy_quiet['polled']==[0,0] and legacy_quiet['buffered']==[0,0],legacy_quiet
        assert legacy_quiet['pointer']==[640,360] and legacy_quiet['clip']==[640,360,641,361] and legacy_quiet['rmb'],legacy_quiet
        legacy_signed=[]
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            before=sample();transport.paced(((dx,dy) for _ in range(12)),.016)
            time.sleep(.12);after=sample();expected=[12*dx,12*dy]
            row={'injected':expected,'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered')}
            assert row['polled']==expected and row['buffered']==expected,row
            assert point()[0]==(640,360),point()
            legacy_signed.append(row)
        release_button();property(name,TITLE)
        held(); set_focus(0); time.sleep(.4)
        restored=record('none-focus-recovered-after-resume')
        assert restored['x_focus']==game_window and restored['x_pointer']==(640,360),restored
        assert any(row['success'] and row['before']==0 for row in repair_rows()),repair_rows()
        release_button(); time.sleep(.15); assert sample()['clip']==original_clip
        companion.terminate(); assert companion.wait(timeout=3)==0
        command('quit'); assert child.wait(timeout=15)==0
        transport.close()
        counts=transport.summary()
        assert counts['native_decoded']=={key:counts[key] for key in ('relative','absolute','buttons')},counts
        observer.terminate(); assert observer.wait(timeout=3)==0
        for stream in logs.values(): stream.flush()
        focus_rows=[json.loads(line) for line in (out / 'focus.log').read_text().splitlines()]
        assert focus_rows[0]['marker']==MARKER and focus_rows[-1]['record']=='end',focus_rows
        assert focus_rows[0]['window_titles']==['EqW-TAKP','Client1'],focus_rows[0]
        assert focus_rows[-1]['dropped']==0 and focus_rows[-1]['xerrors']==0,focus_rows[-1]
        repairs=repair_rows()
        assert len(repairs)==3 and all(row['success'] and row['candidate']==game_window and
            row['after']==game_window and row['identity']=='EqW-TAKP|Client1/eqgame.exe' and
            row['path_depth']==3 and row['rmb'] and row['xerrors']==0 for row in repairs),repairs
        assert [row['before'] for row in repairs]==[1,1,0],repairs
        assert (out / 'focus.log').stat().st_size<=131072
        source_root=Path(__file__).resolve().parents[1]
        sources=('tests/integration_takp_focus.py','tests/takp_focus_probe_0630.cpp','tests/takp_focus_probe.cpp','tests/takp_cursor_probe.cpp',
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
                'physical_cursor_confined':True,'focus_none_after_resume':True,'rmb_release_restores_clip':True,'menu_pointer_free':True,
                'title':'Client1','viewport':[1280,720],'center':[640,360],
                'pointer_path':measured_path,'propertyless_render_child':render,
                'natural_title_property':title_property,'natural_class_property':class_property,
                'menu_normalization':menu_normalized,'legacy_quiet_baseline':legacy_quiet,
                'legacy_title':'EqW-TAKP','legacy_signed_segments':legacy_signed},
            'negative_guards':guards,'focus_repairs':repairs,'focus_completion':focus_rows[-1],'transport':counts,
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
