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


def run(wine, probe, output):
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
    xtst.XTestFakeButtonEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
    xlib.XQueryPointer.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_uint)]
    display=None;child=None;diagnostics=[]
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
            xtst.XTestFakeRelativeMotionEvent(display,dx,dy,0);xlib.XSync(display,False)
        def button(down):
            xtst.XTestFakeButtonEvent(display,3,down,0);xlib.XSync(display,False)
        subprocess.run([str(wine),'wineboot','-u'],env=env,stdout=wine_log,stderr=subprocess.STDOUT,check=True,timeout=120)
        drives=prefix/'dosdevices';(drives/'d:').unlink(missing_ok=True);(drives/'d:').symlink_to(output)
        (output/'command.txt').unlink(missing_ok=True);(output/'reply.txt').unlink(missing_ok=True)
        shutil.copyfile(probe,output/'cursor-probe.exe')
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
            return wait_file(output/'reply.txt',value,child,prefix=mode=='sample')
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
        motion(80,40);time.sleep(.1);assert point()==(480,340),point()
        # Capture a held-button look, minimize/release, restore and re-enter.
        button(True);time.sleep(.15);assert sample()['clip']==[400,300,401,301]
        command('blur');time.sleep(.15);assert sample()['clip']==original_clip,sample()
        button(False);command('resume');command('focus');time.sleep(.15)
        button(True);time.sleep(.15);assert sample()['clip']==[400,300,401,301],sample()
        button(False);time.sleep(.15);assert sample()['clip']==original_clip,sample()
        command('free');motion(-60,-30);time.sleep(.1);assert point()==(340,270),point()
        command('quit');assert child.wait(timeout=15)==0
        source_root=Path(__file__).resolve().parents[1]
        proof_files=('tests/takp_cursor_probe.cpp','tests/integration_takp_cursor.py','native/takp_camera_recenter.h')
        receipt={'wine':subprocess.check_output([str(wine),'--version'],env=env,text=True).strip(),
                 'github_commit':os.environ.get('GITHUB_SHA'),'github_run_id':os.environ.get('GITHUB_RUN_ID'),
                 'fixture_sha256':{name:hashlib.sha256((source_root/name).read_bytes()).hexdigest() for name in proof_files},
                 'legacy_offsets':old,'v1_relative_comparison':v1,'repaired_relative':repaired,
                 'beyond_desktop':{'injected':[6400,-6400],'polled':[6400,-6400],'buffered':[6400,-6400]},
                 'idle_drift':[0,0],'rmb_release_restores_clip':True,'focus_restore_reenters_look':True,
                 'menu_pointer_free':True,'verification':'real Wine10/Xvnc polled and buffered DirectInput; open fixture, not actual client acceptance'}
        (output/'cursor-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
        print('PASS: real Wine10/Xvnc signed raw camera input, both axes/APIs, edge travel, zero idle drift and look/focus release')
    finally:
        if child and child.poll() is None:child.kill();child.wait()
        if display:xlib.XCloseDisplay(display)
        server.terminate();server.wait(timeout=10);display_log.close();wine_log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wine',type=Path,required=True);parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.wine,args.probe,args.output)
