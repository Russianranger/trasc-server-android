#!/usr/bin/env python3
"""Measure actual Wine/Xvnc polled+buffered relative input during camera look."""
import argparse
import ctypes
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def wait_file(path, expected, child, timeout=30, prefix=False):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if path.is_file():
            value=path.read_text()
            if (value.startswith(expected+' ') if prefix else value==expected):return value
        if child.poll() is not None:raise RuntimeError('Wine cursor fixture exited early: '+str(child.returncode))
        time.sleep(.01)
    raise RuntimeError('Wine cursor fixture did not reply: '+expected)


def run(wine, probe, output, input_probe=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    prefix=output/'prefix';prefix.mkdir(exist_ok=True)
    env=dict(os.environ,DISPLAY=':33',WINEPREFIX=str(prefix),WINEARCH='win64',WINEDEBUG='-all,+cursor,+event,+dinput',WINEDLLOVERRIDES='winemenubuilder,mscoree,mshtml=')
    display_log=(output/'display.log').open('wb');wine_log=(output/'wine.log').open('wb')
    server=subprocess.Popen(['Xtigervnc',':33','-geometry','800x600','-depth','24','-rfbport','-1','-nolisten','tcp','-nolock','-ac','-SecurityTypes','None'],stdout=display_log,stderr=subprocess.STDOUT)
    xlib=ctypes.CDLL(ctypes.util.find_library('X11'));xtst=ctypes.CDLL(ctypes.util.find_library('Xtst'))
    xlib.XOpenDisplay.argtypes=[ctypes.c_char_p];xlib.XOpenDisplay.restype=ctypes.c_void_p
    xlib.XDefaultRootWindow.argtypes=[ctypes.c_void_p];xlib.XDefaultRootWindow.restype=ctypes.c_ulong
    xlib.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int]
    xlib.XCloseDisplay.argtypes=[ctypes.c_void_p]
    xlib.XGetInputFocus.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_int)]
    xlib.XFetchName.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_void_p)]
    xlib.XQueryTree.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_uint)]
    xlib.XFree.argtypes=[ctypes.c_void_p]
    xtst.XTestFakeRelativeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_ulong]
    xtst.XTestFakeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulong]
    xtst.XTestFakeButtonEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
    xlib.XQueryPointer.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_uint)]
    display=None;child=None;transport=None;diagnostics=[]
    try:
        for _ in range(100):
            display=xlib.XOpenDisplay(b':33')
            if display:break
            if server.poll() is not None:raise RuntimeError('Xvnc exited before readiness')
            time.sleep(.05)
        if not display:raise RuntimeError('Xvnc not ready')
        root=xlib.XDefaultRootWindow(display)
        def point():
            r,c=ctypes.c_ulong(),ctypes.c_ulong();x,y,wx,wy=ctypes.c_int(),ctypes.c_int(),ctypes.c_int(),ctypes.c_int();mask=ctypes.c_uint()
            if not xlib.XQueryPointer(display,root,ctypes.byref(r),ctypes.byref(c),ctypes.byref(x),ctypes.byref(y),ctypes.byref(wx),ctypes.byref(wy),ctypes.byref(mask)):raise RuntimeError('X pointer unavailable')
            return x.value,y.value
        def focus():
            window=ctypes.c_ulong();revert=ctypes.c_int()
            xlib.XGetInputFocus(display,ctypes.byref(window),ctypes.byref(revert))
            value=window.value;chain=[]
            while value>1:
                name=ctypes.c_void_p()
                title=None
                if xlib.XFetchName(display,value,ctypes.byref(name)) and name.value:
                    title=ctypes.string_at(name.value).decode('utf-8','replace');xlib.XFree(name)
                chain.append({'window':hex(value),'title':title})
                tree_root,parent=ctypes.c_ulong(),ctypes.c_ulong();children=ctypes.c_void_p();count=ctypes.c_uint()
                if not xlib.XQueryTree(display,value,ctypes.byref(tree_root),ctypes.byref(parent),ctypes.byref(children),ctypes.byref(count)):break
                if children.value:xlib.XFree(children)
                if parent.value==value:break
                value=parent.value
            return {'window':hex(window.value),'revert':revert.value,'ancestors':chain}
        def motion(dx,dy):
            if transport:transport.motion(dx,dy)
            else:xtst.XTestFakeRelativeMotionEvent(display,dx,dy,0);xlib.XSync(display,False)
        def free_motion(x,y,dx,dy):
            # X retains unconstrained coordinates while clipped. Normalize only
            # the free UI phase, prove physical capture has ended, then measure
            # the next signed relative input from that observed free position.
            if transport:transport.absolute(x,y)
            else:xtst.XTestFakeMotionEvent(display,-1,x,y,0);xlib.XSync(display,False)
            time.sleep(.1)
            assert point()==(x,y),('released cursor remains physically trapped',point())
            motion(dx,dy);time.sleep(.1)
            assert point()==(x+dx,y+dy),('free signed movement failed',(x,y),(dx,dy),point())
        def button(down,which=3):
            if transport:transport.button(down,which)
            else:xtst.XTestFakeButtonEvent(display,which,down,0);xlib.XSync(display,False)
        subprocess.run([str(wine),'wineboot','-u'],env=env,stdout=wine_log,stderr=subprocess.STDOUT,check=True,timeout=120)
        drives=prefix/'dosdevices';(drives/'d:').unlink(missing_ok=True);(drives/'d:').symlink_to(output)
        (output/'command.txt').unlink(missing_ok=True);(output/'reply.txt').unlink(missing_ok=True)
        shutil.copyfile(probe,output/'cursor-probe.exe')
        trace_path=output/'eqw-camera-diagnostics.log'
        foreign=b'unrelated user file must remain intact\n';trace_path.write_bytes(foreign)
        subprocess.run([str(wine),r'D:\cursor-probe.exe','trace-smoke'],env=env,stdout=wine_log,stderr=subprocess.STDOUT,check=True,timeout=30)
        assert trace_path.read_bytes()==foreign,'diagnostics overwrote an unrelated file'
        trace_path.unlink()
        subprocess.run([str(wine),r'D:\cursor-probe.exe','trace-cap'],env=env,stdout=wine_log,stderr=subprocess.STDOUT,check=True,timeout=30)
        assert trace_path.read_bytes().startswith(b'TRASC_TAKP_CAMERA_TRACE_V1\n') and 127*1024<trace_path.stat().st_size<=128*1024
        subprocess.run([str(wine),r'D:\cursor-probe.exe','trace-smoke'],env=env,stdout=wine_log,stderr=subprocess.STDOUT,check=True,timeout=30)
        assert trace_path.stat().st_size<1024,'new session did not rotate its owned bounded trace'
        if input_probe:
            from takp_input_transport import TrascInputTransport
            transport=TrascInputTransport(input_probe,output/'input.sock',env,output/'input-transport.log')
        # Match Supervisor.desktop: real launcher input runs in Wine's virtual
        # desktop, which uses unmanaged child windows and establishes X focus.
        # A standalone managed popup without a window manager leaves X focus on
        # PointerRoot even when Wine's foreground/focus caches report success.
        child=subprocess.Popen([str(wine),'explorer','/desktop=TRASC,800x600',r'D:\cursor-probe.exe'],env=env,stdout=wine_log,stderr=subprocess.STDOUT)
        wait_file(output/'reply.txt','ready',child)
        assert point()==(400,300),point()
        sequence=0
        def command(mode):
            nonlocal sequence
            sequence+=1;value=f'{mode} {sequence}'
            temporary=output/'command.new';temporary.write_text(value);temporary.replace(output/'command.txt')
            return wait_file(output/'reply.txt',value,child,prefix=mode.startswith(('sample','readstate','readbuffer','peekbuffer')))
        def sample():
            values=list(map(int,command('sample').split()[2:]))
            assert len(values)==14,values
            return {'state':values[:2],'buffered':values[2:4],'rmb':values[4],
                    'cursor':values[5:7],'clip':values[7:11],
                    'foreground':bool(values[11]),'focused':bool(values[12]),'visible':bool(values[13])}
        def diagnose(stage):
            row={'stage':stage,'native':sample(),'x_pointer':point(),'x_focus':focus()}
            diagnostics.append(row)
            (output/'cursor-diagnostics.log').write_text(json.dumps(diagnostics,indent=2)+'\n')
            print(json.dumps(row),flush=True)
            return row
        def difference(before,after,kind):return [after[kind][i]-before[kind][i] for i in range(2)]
        old=[]
        for dx in (20,20,20,-10):
            motion(dx,0);command('legacy');old.append(point()[0]-400)
        assert old==[20,40,60,50],('cached-center no-op failure not reproduced',old)
        command('fixed');assert point()==(400,300),point()
        command('input');time.sleep(.15)
        # The initial cached-cursor reproduction deliberately paused the window
        # pump. Renew focus after map/input readiness: Wine's clip driver checks
        # actual X focus, independently of GetForegroundWindow's server cache.
        command('focus');time.sleep(.15)
        ready=diagnose('input-focus-ready')
        assert ready['native']['foreground'] and ready['native']['focused'] and ready['native']['visible'],ready
        assert any(row['title']=='TAKP relative camera fixture' for row in ready['x_focus']['ancestors']),ready
        original_clip=sample()['clip'];v1=[]
        button(True);command('warp');time.sleep(.15)
        # Record the prior helper with real DirectInput. Exact loss/drift depends
        # on the two threads' schedule; this is evidence, not a timing assertion.
        for dx,dy in ((20,0),(-10,0),(0,20),(0,-10),(20,10),(-10,-20)):
            before=sample()
            for _ in range(20):motion(dx,dy);time.sleep(.005)
            time.sleep(.15);after=sample()
            v1.append({'injected':[20*dx,20*dy],'polled':difference(before,after,'state'),
                       'buffered':difference(before,after,'buffered')})
        command('raw');time.sleep(.2)
        capture=diagnose('raw-capture-ready')
        assert capture['native']['clip']==[400,300,401,301],capture
        assert capture['x_pointer']==(400,300),('Wine cached clip has not confined the actual X cursor',capture)
        before=sample();time.sleep(.2);after=sample()
        assert difference(before,after,'state')==[0,0],('idle camera drift',before,after)
        assert difference(before,after,'buffered')==[0,0],('idle buffered drift',before,after)
        repaired=[]
        # Cardinal, diagonal and fast reversals: every signed wire delta must
        # arrive once in BOTH native DirectInput APIs, even past desktop edges.
        for dx,dy in ((40,0),(-20,0),(-40,0),(20,0),(0,40),(0,-20),(0,-40),(0,20),
                      (30,-15),(-15,30),(40,40),(-40,-40)):
            before=sample()
            for _ in range(25):motion(dx,dy);time.sleep(.005)
            time.sleep(.15);after=sample();expected=[25*dx,25*dy]
            polled=difference(before,after,'state');buffered=difference(before,after,'buffered')
            assert polled==expected,('polled signed input differs',expected,polled,before,after)
            assert buffered==expected,('buffered signed input differs',expected,buffered,before,after)
            assert point()==(400,300),point()
            repaired.append({'injected':expected,'polled':polled,'buffered':buffered})
        # Repeated 6400px excursion cannot be capped by the 800px desktop.
        before=sample()
        for _ in range(160):motion(40,-40);time.sleep(.002)
        time.sleep(.2);after=sample()
        assert difference(before,after,'state')==[6400,-6400],(before,after)
        assert difference(before,after,'buffered')==[6400,-6400],(before,after)
        button(False);time.sleep(.15)
        assert sample()['clip']==original_clip,('right-button release trapped cursor',sample())
        free_motion(400,300,80,40)
        # Capture a held-button look, minimize/release, restore and re-enter.
        button(True);time.sleep(.15);assert sample()['clip']==[400,300,401,301]
        assert point()==(400,300),diagnose('held-before-blur')
        command('blur');time.sleep(.15);assert sample()['clip']==original_clip,sample()
        free_motion(440,320,20,-10)
        button(False);command('resume');time.sleep(.15);command('focus');time.sleep(.15)
        resumed=diagnose('restored-focus-ready')
        assert resumed['native']['foreground'] and resumed['native']['focused'] and resumed['native']['visible'],resumed
        assert any(row['title']=='TAKP relative camera fixture' for row in resumed['x_focus']['ancestors']),resumed
        button(True);time.sleep(.15);assert sample()['clip']==[400,300,401,301],sample()
        assert point()==(400,300),diagnose('restored-raw-capture')
        before=sample()
        for _ in range(20):motion(-30,15);time.sleep(.005)
        time.sleep(.15);after=sample()
        restored_relative={'injected':[-600,300],'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered')}
        assert restored_relative['polled']==[-600,300] and restored_relative['buffered']==[-600,300],restored_relative
        assert point()==(400,300),point()
        button(False);time.sleep(.15);assert sample()['clip']==original_clip,sample()
        # Mode remains logically active after physical release. It must not
        # reacquire the clip while the game's logical flag is stale/paused.
        time.sleep(.15);assert sample()['clip']==original_clip,sample()
        command('free');free_motion(440,320,-60,-30)
        command('swap');command('raw');button(True,1);time.sleep(.15)
        assert sample()['clip']==[400,300,401,301] and point()==(400,300),diagnose('swapped-look-capture')
        before=sample()
        for _ in range(20):motion(15,-10);time.sleep(.005)
        time.sleep(.15);after=sample()
        swapped_relative={'injected':[300,-200],'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered')}
        assert swapped_relative['polled']==[300,-200] and swapped_relative['buffered']==[300,-200],swapped_relative
        assert point()==(400,300),point()
        button(False,1);time.sleep(.3);assert sample()['clip']==original_clip,sample()
        command('normal');command('free');free_motion(440,320,-20,10)
        # Match controller-scale cadence and production's pipelined XFlush.
        command('raw');button(True);time.sleep(.15)
        cadence=[]
        for events in ([(1,0)]*30+[(0,0)]*5+[(-1,0)]*30,
                       [(0,2)]*20+[(0,0)]*5+[(0,-2)]*20,
                       [(1,-1)]*25+[(-1,1)]*25):
            before=sample()
            for dx,dy in events:motion(dx,dy);time.sleep(.016)
            time.sleep(.2);after=sample();expected=[sum(v[i] for v in events) for i in range(2)]
            assert difference(before,after,'state')==expected and difference(before,after,'buffered')==expected,(events,before,after)
            idle=sample();time.sleep(.2);stopped=sample()
            assert difference(idle,stopped,'state')==[0,0] and difference(idle,stopped,'buffered')==[0,0],(idle,stopped)
            cadence.append({'packets':len(events),'injected':expected,'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered'),'pause_drift':[0,0]})
        bursts=[]
        if transport:
            for events,fragments in (([(1,0)]*200+[(-1,0)]*160,None),
                                     ([(0,-1)]*200+[(0,1)]*160,[1,3,2,7,17]),
                                     ([(1,-1)]*200+[(-1,1)]*160,None)):
                before=sample();transport.burst(events,fragment_sizes=fragments);time.sleep(.3);after=sample()
                expected=[sum(v[i] for v in events) for i in range(2)]
                assert difference(before,after,'state')==expected and difference(before,after,'buffered')==expected,(expected,before,after)
                bursts.append({'packets':len(events),'fragmented':bool(fragments),'injected':expected,'polled':difference(before,after,'state'),'buffered':difference(before,after,'buffered')})
        # The real client can select either mode and consume a bounded queue.
        # Observe both modes, including the reset model, without choosing one for
        # the proprietary consumer. The next Thor trace establishes its contract.
        command('manual');command('absformat');time.sleep(.15)
        def read_state():return list(map(int,command('readstate').split()[2:]))
        def read_buffer(peek=False,limit=256):return list(map(int,command(('peekbuffer' if peek else 'readbuffer')+str(limit)).split()[2:]))
        read_buffer();baseline=read_state()[:2]
        motion(80,40);time.sleep(.15);absolute_out=read_state()[:2]
        motion(-20,-10);time.sleep(.15);absolute_reverse=read_state()[:2]
        assert absolute_out==[baseline[0]+80,baseline[1]+40] and absolute_reverse==[baseline[0]+60,baseline[1]+30],(baseline,absolute_out,absolute_reverse)
        # Resetting only a consumer's saved state to the initial value leaves a
        # positive result after negative input in ABS mode. This is a model,
        # not proof that the actual game requested ABS or computes this delta.
        reset_model=[absolute_reverse[i]-baseline[i] for i in range(2)]
        assert reset_model==[60,30],reset_model
        command('relproperty');time.sleep(.15);read_buffer();read_state()
        for _ in range(10):motion(8,0);time.sleep(.016)
        for _ in range(5):motion(-8,0);time.sleep(.016)
        time.sleep(.15)
        first_peek=read_buffer(True);second_peek=read_buffer(True)
        assert first_peek==second_peek and first_peek[1:3]==[40,0],(first_peek,second_peek)
        first_read=read_buffer(False,1)
        assert first_read[0]==1 and first_read[1:3]==[8,0],first_read
        remaining=read_buffer();assert remaining[1:3]==[32,0] and read_buffer()[0]==0,remaining
        relative_state=read_state()[:2];assert relative_state==[40,0] and read_state()[:2]==[0,0],relative_state
        consumer_modes={'absolute_baseline':baseline,'absolute_out':absolute_out,'absolute_reverse':absolute_reverse,
            'absolute_reset_model_after_negative_input':reset_model,'relative_state':relative_state,
            'peek_repeats_same_events':True,'bounded_first_old_event':first_read,'remaining_consumed':remaining,
            'actual_game_contract':'unknown until device helper diagnostics'}
        command('customformat');time.sleep(.15);read_buffer();read_state()
        motion(9,-5);time.sleep(.15);custom_state=read_state();read_buffer()
        assert custom_state==[-5,0,9],('custom-format memory layout was not respected',custom_state)
        consumer_modes['custom_format_axis_offsets']=[8,0,4]
        consumer_modes['custom_format_raw_memory']=custom_state
        button(False);command('auto');time.sleep(.15);command('free')
        command('quit');assert child.wait(timeout=15)==0
        if transport:
            transport.close()
            counts=transport.summary()
            assert counts['native_decoded']=={key:counts[key] for key in ('relative','absolute','buttons')},counts
        trace=trace_path.read_text()
        assert 'axis_mode=0' in trace and 'axis_mode=1' in trace and 'property id=2' in trace and 'flags=1' in trace,trace[-4000:]
        assert 'axis_offsets=8,0,4' in trace and 'value=9,-5,0' in trace and 'sum_values=9,-5' in trace,trace[-4000:]
        assert trace_path.stat().st_size<=128*1024
        source_root=Path(__file__).resolve().parents[1]
        proof_files=['tests/takp_cursor_probe.cpp','tests/integration_takp_cursor.py','native/takp_camera_recenter.h','native/takp_camera_trace.h','native/takp_dinput_observation.h']
        if transport:proof_files+=['tests/takp_xinput_probe.c','tests/takp_input_transport.py','native/presentation/input.h']
        receipt={'wine':subprocess.check_output([str(wine),'--version'],env=env,text=True).strip(),
                 'github_commit':os.environ.get('GITHUB_SHA'),'github_run_id':os.environ.get('GITHUB_RUN_ID'),
                 'fixture_sha256':{name:hashlib.sha256((source_root/name).read_bytes()).hexdigest() for name in proof_files},
                 'legacy_offsets':old,'v1_relative_comparison':v1,'repaired_relative':repaired,
                 'beyond_desktop':{'injected':[6400,-6400],'polled':[6400,-6400],'buffered':[6400,-6400]},
                 'idle_drift':[0,0],'rmb_release_restores_clip':True,'focus_restore_reenters_look':True,
                 'focus_loss_pointer_free':True,'physical_release_no_reacquire':True,
                 'focus_restored_relative':restored_relative,'swapped_button_relative':swapped_relative,
                 'menu_pointer_free':True,'verification':'real Wine10/Xvnc polled and buffered DirectInput; open fixture, not actual client acceptance'}
        receipt.update(controller_cadence=cadence,pipelined_transport_bursts=bursts,consumer_modes=consumer_modes,
            diagnostic_trace={'marker':'TRASC_TAKP_CAMERA_TRACE_V1','bounded_bytes':trace_path.stat().st_size,'foreign_file_preserved':True,'owned_session_rotated':True},
            transport=transport.summary() if transport else {'type':'direct XTest with per-event XSync'})
        (output/'cursor-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
        print('PASS: real Wine10/Xvnc signed raw camera input, both axes/APIs, edge travel, zero idle drift and look/focus release')
    finally:
        if child and child.poll() is None:child.kill();child.wait()
        if transport:transport.close()
        if display:xlib.XCloseDisplay(display)
        server.terminate();server.wait(timeout=10);display_log.close();wine_log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wine',type=Path,required=True);parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--input-probe',type=Path)
    args=parser.parse_args();run(args.wine,args.probe,args.output,args.input_probe)
