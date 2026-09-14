"""App-owned Wine/Box64 supervisor. Runs in its own rootfs, never in the server DB runtime."""
import json
import os
from pathlib import Path
import secrets
import re
import signal
import socket
import struct
import subprocess
import time

SESSION = Path('/session')
CLIENT = Path('/client')
PREFIX = Path('/prefix')
LOGS = Path('/logs')
stop_requested = False


class StopRequested(Exception):
    pass


def pe_machine(path):
    with Path(path).open('rb') as f:
        if f.read(2) != b'MZ': raise ValueError(f'{Path(path).name} is not a Windows executable')
        f.seek(0x3c); raw = f.read(4)
        if len(raw) != 4: raise ValueError('Truncated Windows header')
        offset = struct.unpack('<I', raw)[0]
        if offset > 16 * 1024 * 1024: raise ValueError('Invalid Windows header offset')
        f.seek(offset)
        if f.read(4) != b'PE\0\0': raise ValueError('Invalid Windows PE signature')
        raw = f.read(2)
        if len(raw) != 2: raise ValueError('Truncated Windows machine header')
        return struct.unpack('<H', raw)[0]


def validate_request(request):
    if request.get('mode') not in ('desktop', 'client'): raise ValueError('Choose Wine desktop or ROF2 client')
    if request.get('resolution') not in ('640x480', '800x600', '960x540', '1024x768'): raise ValueError('Unsupported client resolution')
    if request['mode'] == 'client':
        name = request.get('executable', '')
        if not name or '/' in name or '\\' in name or name in ('.', '..'): raise ValueError('Invalid client executable name')
        exe = CLIENT / name
        if not exe.is_file() or exe.is_symlink(): raise ValueError('Import the ROF2 client first')
        machine = pe_machine(exe)
        if machine != 0x14c: raise ValueError('This milestone expects the 32-bit x86 ROF2 eqgame.exe')
        if request.get('native_dinput8', True):
            dlls = [p for p in CLIENT.iterdir() if p.name.lower() == 'dinput8.dll' and p.is_file() and not p.is_symlink()]
            if len(dlls) != 1: raise ValueError('dinput8.dll must be beside eqgame.exe; import the modified client or disable the native DLL diagnostic option')
            if pe_machine(dlls[0]) != machine: raise ValueError('dinput8.dll must be 32-bit x86 to match ROF2')


def dll_status(log):
    """Require Wine's native-load trace, not the requested override or file presence."""
    matches = [line for line in log.splitlines() if 'dinput8.dll' in line.lower()]
    loaded = [line for line in matches if 'loaddll' in line.lower() and 'native' in line.lower() and 'loaded' in line.lower()]
    return {'native_loaded': bool(loaded), 'evidence': (loaded or matches)[-8:]}


def fatal_launch_error(log):
    match = re.search(r'wine: could not load kernel32\.dll, status ([0-9a-f]+)', log, re.I)
    if match:
        return 'Wine could not start its Windows loader (kernel32.dll, ' + match[1] + '). See client-prefix.log and client-wine.log; ROF2 did not reach game initialization.'
    missing = re.findall(r'err:module:import_dll Library ([^\r\n]+)', log)
    if missing:
        return 'A required Windows library could not load: ' + missing[-1][:350] + '. Export Logs for the dependency details.'
    if re.search(r'err:module:loader_init .*failed, status', log):
        return 'Windows program initialization failed. Export client-wine.log for the failing module and status.'
    return None


def prefix_diagnostics(prefix=PREFIX, wine=Path('/opt/wine')):
    report = {'files': {}, 'runtime_ready': True, 'prefix_ready': True}
    for scope, parent in (('runtime', wine / 'lib/wine/i386-windows'), ('prefix', prefix / 'drive_c/windows/syswow64')):
        for name in ('ntdll.dll', 'kernel32.dll', 'kernelbase.dll', 'cmd.exe'):
            path = parent / name
            entry = {'path': str(path), 'present': path.is_file()}
            if path.is_file():
                entry['bytes'] = path.stat().st_size
                try: entry['machine'] = hex(pe_machine(path))
                except (OSError, ValueError) as error: entry['error'] = str(error)
            if path.is_symlink(): entry['link'] = os.readlink(path)
            report['files'][scope + '/' + name] = entry
            report[scope + '_ready'] &= entry.get('machine') == '0x14c'
    return report


class Supervisor:
    def __init__(self, request):
        self.request = request
        self.children = []
        self.status = {'phase': 'starting', 'mode': request['mode'], 'resolution': request['resolution'],
                       'native_dinput8_requested': request['mode']=='client' and request.get('native_dinput8', True), 'native_loaded': False,
                       'renderer': 'WineD3D / llvmpipe (software)', 'started_at': time.time()}
        self.env = dict(os.environ, DISPLAY=':7', XAUTHORITY=str(SESSION / 'Xauthority'),
                        WINEPREFIX=str(PREFIX), WINEARCH='win64', WINEDEBUG='+timestamp,+pid,+loaddll',
                        WINEDLLOVERRIDES='winemenubuilder,mscoree,mshtml,winegstreamer=',
                        BOX64_DYNAREC_STRONGMEM='1', BOX64_DYNAREC_BIGBLOCK='0', BOX64_DYNAREC_SAFEFLAGS='2',
                        BOX64_LOG='1', BOX64_NOBANNER='0', BOX64_PATH='/opt/wine/bin',
                        BOX64_LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/opt/wine/lib/wine/x86_64-unix',
                        LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe', LP_NUM_THREADS='4')

    def update(self, phase=None, **fields):
        if phase: self.status['phase'] = phase
        self.status.update(fields)
        p = SESSION / 'status.json'; tmp = p.with_suffix('.new')
        tmp.write_text(json.dumps(self.status, indent=2)); os.replace(tmp, p)
        report = LOGS / 'client-state.json'; tmp = report.with_suffix('.new')
        tmp.write_text(json.dumps(self.status, indent=2)); os.replace(tmp, report)

    def stopping(self):
        return stop_requested or (SESSION / 'stop').exists()

    def spawn(self, args, log, env=None):
        with (LOGS / log).open('ab') as out:
            process = subprocess.Popen(args, env=env or self.env, stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=out, start_new_session=True, cwd=CLIENT)
        self.children.append(process)
        return process

    def run(self, args, timeout=180, env=None, label='Wine setup'):
        process = self.spawn(args, 'client-prefix.log', env)
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if self.stopping(): raise StopRequested()
            if time.monotonic() > deadline: raise RuntimeError(label + ' timed out; export client-prefix.log')
            time.sleep(.2)
        if process.returncode:
            trace = (LOGS / 'client-prefix.log').read_text(errors='replace')[-128*1024:]
            raise RuntimeError(f'{label} exited with code {process.returncode}. ' + (fatal_launch_error(trace) or 'See client-prefix.log.'))

    def check_prefix(self):
        report = prefix_diagnostics()
        (LOGS / 'client-prefix.json').write_text(json.dumps(report, indent=2))
        if not report['runtime_ready']:
            raise RuntimeError('The client runtime is missing valid 32-bit Windows system files. Download the client runtime again; the game and server are retained.')
        if not report['prefix_ready']:
            raise RuntimeError('The 32-bit Wine prefix is incomplete. Stop the client and use Repair Wine prefix; it preserves the previous prefix and your imported game.')
        self.update('checking_32bit_wine', prefix_files_ready=True)
        diagnostic_env = dict(self.env, WINEDEBUG=self.env['WINEDEBUG']+',+module')
        self.run(['/usr/local/bin/box64', '/opt/wine/bin/wine', r'C:\windows\syswow64\cmd.exe', '/d', '/c', 'exit', '0'],
                 timeout=60, env=diagnostic_env, label='32-bit Wine check')
        self.update(wine32_ready=True)

    def start(self):
        validate_request(self.request)
        for p in (SESSION, PREFIX, LOGS): p.mkdir(parents=True, exist_ok=True)
        for name in ('client-wine.log', 'client-prefix.log', 'client-display.log', 'client-graphics.log'):
            path = LOGS / name
            if path.exists(): os.replace(path, path.with_suffix('.previous.log'))
        # The RFB display has no TCP listener. X11 requires an unpredictable cookie.
        cookie = secrets.token_hex(16)
        (SESSION / 'Xauthority').touch(mode=0o600)
        subprocess.run(['xauth', '-f', self.env['XAUTHORITY'], 'add', ':7', '.', cookie], check=True, stdout=subprocess.DEVNULL)
        xserver = self.spawn(['Xtigervnc', ':7', '-geometry', self.request['resolution'], '-depth', '24',
                             '-rfbport', '-1', '-rfbunixpath', str(SESSION / 'display.sock'), '-rfbunixmode', '0600',
                             '-SecurityTypes', 'None', '-nolisten', 'tcp', '-auth', self.env['XAUTHORITY'],
                             '-AlwaysShared', '-FrameRate', '30', '-desktop', 'TRASC client'], 'client-display.log')
        for _ in range(150):
            if self.stopping(): raise StopRequested()
            if xserver.poll() is not None: raise RuntimeError('Client display failed; see client-display.log')
            if (SESSION / 'display.sock').exists(): break
            time.sleep(.1)
        else: raise RuntimeError('Client display did not become ready')
        self.update('preparing_prefix', display_ready=True)
        self.spawn(['glxinfo', '-B'], 'client-graphics.log')
        self.run(['/usr/local/bin/box64', '/opt/wine/bin/wine', 'wineboot', '-u'])
        self.check_prefix()
        devices = PREFIX / 'dosdevices'; devices.mkdir(exist_ok=True)
        drive = devices / 'd:'
        if drive.is_symlink(): drive.unlink()
        if drive.exists(): raise RuntimeError('Wine D: drive is already occupied')
        drive.symlink_to(CLIENT)
        args = ['/usr/local/bin/box64', '/opt/wine/bin/wine', 'explorer', '/desktop=TRASC,' + self.request['resolution']]
        env = dict(self.env)
        if self.request['mode'] == 'client':
            args += ['D:\\' + self.request['executable'], 'patchme']
            env['WINEDLLOVERRIDES'] += ';dinput8=' + ('n' if self.request.get('native_dinput8', True) else 'b')
            env['WINEDEBUG'] += ',+module'
        launcher = self.spawn(args, 'client-wine.log', env)
        self.update('launch_requested', display_ready=True, launcher_pid=launcher.pid)
        while not self.stopping():
            if xserver.poll() is not None: raise RuntimeError('Display exited; see client-display.log')
            log = LOGS / 'client-wine.log'
            with log.open('rb') as f:
                f.seek(max(0, log.stat().st_size - 512 * 1024)); trace = f.read().decode(errors='replace')
            observed = dll_status(trace)
            if observed['native_loaded']: self.status['native_loaded'] = True
            fatal = fatal_launch_error(trace)
            if fatal: raise RuntimeError(fatal)
            self.update(launcher_exit=launcher.poll(), dll_evidence=observed['evidence'])
            time.sleep(1)

    def stop(self):
        try:
            subprocess.run(['/usr/local/bin/box64', '/opt/wine/bin/wineserver', '-k'], env=self.env,
                           timeout=10, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired): pass
        for child in reversed(self.children):
            if child.poll() is None:
                try: os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError: pass
        deadline = time.monotonic() + 5
        for child in self.children:
            try: child.wait(timeout=max(.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                child.wait()
        (SESSION / 'display.sock').unlink(missing_ok=True)
        self.update(display_ready=False)


def main():
    global stop_requested
    def stop(*_):
        global stop_requested
        stop_requested = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    supervisor = None
    try:
        request = json.loads((SESSION / 'request.json').read_text())
        supervisor = Supervisor(request); supervisor.start()
    except StopRequested:
        if supervisor: supervisor.update('stopped')
    except Exception as error:
        if supervisor: supervisor.update('error', error=str(error))
        print(f'Client runtime failed: {error}', flush=True)
        raise
    finally:
        if supervisor:
            supervisor.stop()
            if supervisor.status.get('phase') != 'error': supervisor.update('stopped', display_ready=False)


if __name__ == '__main__': main()
