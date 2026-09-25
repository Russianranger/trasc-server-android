"""Exercise real X11 authentication when the host denies link/linkat.

Run with the test-only LD_PRELOAD shim built for the runtime architecture:
  cc -shared -fPIC -Wall -Wextra -Werror tests/xauth_deny_links.c -o /tmp/deny-links.so
  python3 tests/integration_xauthority.py --deny-links /tmp/deny-links.so

No Windows client or Microsoft SDK is needed. The production X11 access control
remains enabled; raw X11 setup requests test valid, absent and incorrect cookies.
"""
import argparse
import errno
import json
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time


DENIED = 'TRASC test: hard-link creation denied'


def backend_directory():
    candidates = (Path(__file__).resolve().parents[1] / 'backend', Path('/opt/trasc-client'))
    for path in candidates:
        if (path / 'client_xauthority.py').is_file():
            return path
    raise RuntimeError('Mount the production backend at /opt/trasc-client')


def command(args, env, timeout=30):
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)
    return result


def receive(stream, length):
    data = b''
    while len(data) < length:
        part = stream.recv(length - len(data))
        if not part:
            raise AssertionError('X11 connection closed before setup reply')
        data += part
    return data


def setup(display, name=b'', cookie=b''):
    pad = lambda data: data + b'\0' * (-len(data) % 4)
    packet = struct.pack('<BBHHHHH', ord('l'), 0, 11, 0, len(name), len(cookie), 0)
    with socket.socket(socket.AF_UNIX) as stream:
        stream.settimeout(5)
        stream.connect('/tmp/.X11-unix/X' + str(display))
        stream.sendall(packet + pad(name) + pad(cookie))
        status, reason_size, major, minor, size = struct.unpack('<BBHHH', receive(stream, 8))
        reply = receive(stream, size * 4)
    reason = reply[:reason_size].decode('utf-8', 'replace') if status == 0 else ''
    return {'status': status, 'protocol': [major, minor], 'reason': reason}


def auth_fields(path):
    data = path.read_bytes()
    offset = 2
    fields = []
    for _ in range(4):
        size, = struct.unpack_from('!H', data, offset)
        offset += 2
        fields.append(data[offset:offset + size])
        offset += size
    assert offset == len(data), 'Invalid credential file size'
    return fields


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def no_tcp_listener(display):
    checked = []
    for family, address in ((socket.AF_INET, '127.0.0.1'), (socket.AF_INET6, '::1')):
        try:
            stream = socket.socket(family)
        except OSError as error:
            if family == socket.AF_INET6 and error.errno == errno.EAFNOSUPPORT:
                continue
            raise
        with stream:
            stream.settimeout(2)
            result = stream.connect_ex((address, 6000 + display))
            assert result in (errno.ECONNREFUSED, errno.EAFNOSUPPORT, errno.ENETUNREACH), (
                'Unexpected X11 TCP listener or unreachable local address', address, result)
            checked.append(address)
    return checked


def check_display(root, display, env, backend):
    for path in (Path('/tmp/.X' + str(display) + '-lock'), Path('/tmp/.X11-unix/X' + str(display))):
        assert not path.exists(), 'Test display is already in use: ' + str(path)
    session = root / str(display)
    session.mkdir(mode=0o700)
    auth = session / 'Xauthority'
    make_auth = command([sys.executable, '-c',
        'import sys; sys.path.insert(0,sys.argv[1]); '
        'from client_xauthority import write_xauthority; '
        'write_xauthority(sys.argv[2],int(sys.argv[3]))', str(backend), str(auth), str(display)], env)
    assert make_auth.returncode == 0, make_auth.stderr
    assert DENIED not in make_auth.stderr, 'Production auth writer attempted a hard link'
    assert stat.S_IMODE(auth.stat().st_mode) == 0o600
    _, number, protocol, cookie = auth_fields(auth)
    assert number == str(display).encode() and protocol == b'MIT-MAGIC-COOKIE-1' and len(cookie) == 16
    display_socket = session / 'display.sock'
    args = ['Xtigervnc', ':' + str(display), '-geometry', '800x600', '-depth', '24',
            '-rfbport', '-1', '-rfbunixpath', str(display_socket), '-rfbunixmode', '0600',
            '-SecurityTypes', 'None', '-nolisten', 'tcp', '-auth', str(auth), '-AlwaysShared']

    # Establish why skipping only xauth's own lock is insufficient.
    old = command(args, env, timeout=15)
    assert old.returncode != 0, 'The unpatched display unexpectedly accepted denied links'
    assert DENIED in old.stderr and 'Linking lock file' in old.stderr, old.stderr

    log_path = session / 'display.log'
    with log_path.open('wb') as log:
        server = subprocess.Popen(args + ['-nolock'], env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 10
            while not display_socket.exists():
                assert server.poll() is None, log_path.read_text(errors='replace')
                assert time.monotonic() < deadline, 'Display did not open its private socket'
                time.sleep(.05)
            assert stat.S_IMODE(display_socket.stat().st_mode) == 0o600
            absent = setup(display)
            incorrect = setup(display, protocol, bytes(value ^ 0xff for value in cookie))
            accepted = setup(display, protocol, cookie)
            assert absent['status'] == 0, 'Missing credentials were accepted'
            assert incorrect['status'] == 0, 'Wrong credentials were accepted'
            assert accepted['status'] == 1, accepted
            # Exercise normal libX11 file lookup as well as the raw protocol.
            # This catches a malformed local hostname/family/display record.
            xlib_env = dict(env, DISPLAY=':' + str(display), XAUTHORITY=str(auth))
            xlib = command([sys.executable, '-c',
                'import ctypes; x=ctypes.CDLL("libX11.so.6"); '
                'x.XOpenDisplay.argtypes=[ctypes.c_char_p]; x.XOpenDisplay.restype=ctypes.c_void_p; '
                'x.XCloseDisplay.argtypes=[ctypes.c_void_p]; '
                'd=x.XOpenDisplay(None); assert d,"libX11 could not select the local cookie"; '
                'x.XCloseDisplay(d)'], xlib_env)
            assert xlib.returncode == 0, xlib.stderr
            tcp = no_tcp_listener(display)
            assert DENIED not in log_path.read_text(errors='replace'), 'Repaired display still attempted a hard link'
            assert server.poll() is None, 'Display exited during authorization checks'
            return {'display': display, 'old_display_lock_failed': True,
                    'credential_mode': '0600', 'rfb_socket_mode': '0600',
                    'missing_cookie_rejected': absent['status'] == 0,
                    'wrong_cookie_rejected': incorrect['status'] == 0,
                    'correct_cookie_accepted': accepted['status'] == 1,
                    'libx11_credential_lookup': True, 'tcp_listener_absent': tcp}
        finally:
            stop(server)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deny-links', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    assert os.getuid() == 0, 'Run as root or PRoot -0, matching the app; Xtigervnc -nolock requires root'
    shim = args.deny_links.resolve(strict=True)
    backend = backend_directory()
    env = dict(os.environ, LD_PRELOAD=str(shim))
    with tempfile.TemporaryDirectory(prefix='trasc-xauth-') as temporary:
        root = Path(temporary)
        smoke = command([sys.executable, '-c',
            'import errno,os,sys; from pathlib import Path; '
            'p=Path(sys.argv[1]); p.write_bytes(b"probe"); '
            '\ntry: os.link(p,str(p)+"-link")\n'
            'except OSError as error: assert error.errno==errno.EACCES\n'
            'else: raise AssertionError("Hard-link denial was not active")', str(root / 'smoke')], env)
        assert smoke.returncode == 0 and DENIED in smoke.stderr, smoke.stderr
        old_auth = root / 'old-Xauthority'
        old_auth.touch(mode=0o600)
        old = command(['xauth', '-f', str(old_auth), 'add', ':7', '.', '00' * 16], env)
        assert old.returncode != 0 and DENIED in old.stderr, old.stderr
        result = {'hard_links_denied': True, 'old_xauth_failed': True,
                  'displays': [check_display(root, display, env, backend) for display in (7, 8)]}
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + '\n')
    print(rendered)


if __name__ == '__main__':
    main()
