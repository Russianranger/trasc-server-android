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
    Path('/session/request.json').write_text(json.dumps({'mode':'client','resolution':'800x600','executable':'eqgame.exe','native_dinput8':True}))
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
        with socket.socket(socket.AF_UNIX) as display:
            display.settimeout(30); display.connect('/session/display.sock')
            assert recv(display,12)==b'RFB 003.008\n';display.sendall(b'RFB 003.008\n')
            types=recv(display,recv(display,1)[0]);assert 1 in types;display.sendall(b'\1')
            assert recv(display,4)==bytes(4);display.sendall(b'\1')
            width,height=struct.unpack('>HH',recv(display,4));recv(display,16)
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
            # Focus the probe interior, then deliver a keyboard press/release.
            display.sendall(struct.pack('>BBHH',5,1,200,200)+struct.pack('>BBHH',5,0,200,200))
            display.sendall(struct.pack('>BBHI',4,1,0,ord('t'))+struct.pack('>BBHI',4,0,0,ord('t')))
            wait_for(lambda:Path('/client/probe-key.txt').exists() and Path('/client/probe-mouse.txt').exists(),'Display input did not reach the 32-bit Windows program',15)
        wait_for(lambda:json.loads(Path('/session/status.json').read_text()).get('native_loaded'), 'Native DLL trace not recognized',15)
        print('PASS: ARM64 Box64 + Wine WoW64 executes PE32, loads our native dinput8 DLL, renders Direct3D9 and receives mouse/keyboard through the private display socket')
    finally:
        Path('/session/stop').touch()
        try: runner.wait(timeout=25)
        except subprocess.TimeoutExpired: runner.kill();runner.wait();raise


if __name__=='__main__': main()
