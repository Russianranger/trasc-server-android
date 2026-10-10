#!/usr/bin/env python3
"""Prove the legacy cache-equality failure and patched warp in real Wine/Xvnc."""
import argparse
import ctypes
import ctypes.util
import json
import os
from pathlib import Path
import subprocess
import time


def wait_file(path, expected, child, timeout=30):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if path.is_file() and path.read_text()==expected:return
        if child.poll() is not None:raise RuntimeError('Wine cursor fixture exited early')
        time.sleep(.02)
    raise RuntimeError('Wine cursor fixture did not reply: '+expected)


def run(wine, probe, output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    prefix=output/'prefix';prefix.mkdir(exist_ok=True)
    env=dict(os.environ,DISPLAY=':33',WINEPREFIX=str(prefix),WINEARCH='win64',WINEDEBUG='-all',WINEDLLOVERRIDES='winemenubuilder,mscoree,mshtml=')
    display_log=(output/'display.log').open('wb');wine_log=(output/'wine.log').open('wb')
    server=subprocess.Popen(['Xtigervnc',':33','-geometry','800x600','-depth','24','-rfbport','-1','-nolisten','tcp','-nolock','-ac','-SecurityTypes','None'],stdout=display_log,stderr=subprocess.STDOUT)
    xlib=ctypes.CDLL(ctypes.util.find_library('X11'));xtst=ctypes.CDLL(ctypes.util.find_library('Xtst'))
    xlib.XOpenDisplay.argtypes=[ctypes.c_char_p];xlib.XOpenDisplay.restype=ctypes.c_void_p
    xlib.XDefaultRootWindow.argtypes=[ctypes.c_void_p];xlib.XDefaultRootWindow.restype=ctypes.c_ulong
    xlib.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int]
    xlib.XCloseDisplay.argtypes=[ctypes.c_void_p]
    xtst.XTestFakeRelativeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_ulong]
    xlib.XQueryPointer.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_uint)]
    display=None;child=None
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
        subprocess.run([str(wine),'wineboot','-u'],env=env,stdout=wine_log,stderr=subprocess.STDOUT,check=True,timeout=120)
        drives=prefix/'dosdevices';(drives/'d:').unlink(missing_ok=True);(drives/'d:').symlink_to(output)
        (output/'command.txt').unlink(missing_ok=True);(output/'reply.txt').unlink(missing_ok=True)
        child=subprocess.Popen([str(wine),str(Path(probe).resolve())],env=env,stdout=wine_log,stderr=subprocess.STDOUT)
        wait_file(output/'reply.txt','ready',child)
        assert point()==(400,300),point()
        sequence=0
        def center(mode):
            nonlocal sequence
            sequence+=1;command=f'{mode} {sequence}'
            temporary=output/'command.new';temporary.write_text(command);temporary.replace(output/'command.txt')
            wait_file(output/'reply.txt',command,child)
        old=[]
        for dx in (20,20,20,-10):
            xtst.XTestFakeRelativeMotionEvent(display,dx,0,0);xlib.XSync(display,False)
            center('legacy');old.append(point()[0]-400)
        assert old==[20,40,60,50],('cached-center no-op failure not reproduced',old)
        center('fixed');assert point()==(400,300),point()
        after=[]
        for dx,dy in ((20,10),(-10,-5),(20,-10),(-20,10),(10,20),(-10,-20)):
            xtst.XTestFakeRelativeMotionEvent(display,dx,dy,0);xlib.XSync(display,False)
            before=point();assert before==(400+dx,300+dy),before
            center('fixed');after.append({'delta':[dx,dy],'before':list(before),'after':list(point())})
            assert point()==(400,300),point()
        center('quit');assert child.wait(timeout=15)==0
        receipt={'wine':subprocess.check_output([str(wine),'--version'],env=env,text=True).strip(),
                 'legacy_offsets':old,'repaired_motion':after,'verification':'real Wine cursor-cache/Xvnc mechanism; open fixture, not actual client acceptance'}
        (output/'cursor-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
        print('PASS: real Wine/Xvnc cached-center failure and forced recenter on both axes')
    finally:
        if child and child.poll() is None:child.kill();child.wait()
        if display:xlib.XCloseDisplay(display)
        server.terminate();server.wait(timeout=10);display_log.close();wine_log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wine',type=Path,required=True);parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.wine,args.probe,args.output)
