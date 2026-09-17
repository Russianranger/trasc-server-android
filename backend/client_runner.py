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
import threading
import hashlib
import shutil
import tempfile
import time
from contextlib import contextmanager
from client_metrics import process_threads, allow_game_cpus
import client_vulkan
import client_audio
import client_spells
from client_display import RESOLUTIONS, apply_display

SESSION = Path('/session')
CLIENT = Path('/client')
PREFIX = Path('/prefix')
LOGS = Path('/logs')
stop_requested = False
stop_reason = None
WINE_LOG_LIMIT = 8 * 1024 * 1024


def wine_debug(verbose=False, sound=False):
    # +seh expands each routine OutputDebugString exception into dozens of
    # lines. ROF2 generated 1.06 GB of this in one session through PRoot.
    # Wine's fps channel emits one aggregate per swapchain every 1.5 seconds,
    # unlike per-frame frametime / d3d traces. Keep the latter disabled.
    normal = '-all,+timestamp,+pid,err+all,trace+loaddll,trace+fps'
    return normal + ',warn+dsound,warn+wave,warn+mmdevapi' + (',warn+all,fixme+all,trace+module,trace+seh' if verbose else '') + (',trace+dsound,trace+mmdevapi' if sound else '')


def archive_log(path, limit=WINE_LOG_LIMIT):
    from log_retention import rotate
    rotate(path, limit)


def preserve_game_log(client=CLIENT, logs=LOGS, limit=WINE_LOG_LIMIT):
    """Copy only the known startup diagnostic before ROF2 overwrites it.

    No INI/chat files, symlink traversal or modifications to imported game logs.
    An oversized log retains bounded startup/final excerpts.
    """
    target = logs/'client-game.previous.log'
    from log_retention import shift
    shift(logs/'client-game.log')
    for relative in ('Logs/dbg.txt', 'logs/dbg.txt', 'dbg.txt'):
        source = client/relative
        if source.is_symlink() or source.parent.is_symlink() or not source.is_file(): continue
        temporary = target.with_suffix('.new')
        with source.open('rb') as inp, temporary.open('wb') as out:
            size = source.stat().st_size
            if size <= limit: out.write(inp.read(limit))
            else:
                marker = b'\n[TRASC: previous game log shortened; startup and final output retained]\n'
                head = limit//2
                out.write(inp.read(head)); out.write(marker)
                inp.seek(-(limit-head-len(marker)), os.SEEK_END)
                out.write(inp.read(limit-head-len(marker)))
        os.replace(temporary,target)
        return


class WineLog:
    """Drain Wine independently of status polling; retain two bounded segments.

    Parse before rotation so an early DLL load or fatal error cannot disappear
    between polls. A pipe reader owns rotation: renaming a direct subprocess
    output file would leave Wine writing to the old file descriptor.
    """
    def __init__(self, path, limit=WINE_LOG_LIMIT):
        self.path, self.limit = path, limit
        self.lock = threading.Lock()
        self.fields = {'wine_log_bytes': 0, 'wine_log_rotations': 0,
                       'native_loaded': False, 'system_dinput8_loaded': False, 'dll_evidence': [],
                       'model_libraries_loaded': {}, 'model_dll_evidence': []}
        self.error = None
        self.pending = b''
        self.trace = ''
        self.fps_streams = set()
        self.sound_trace = client_audio.SoundTrace()
        self.sound_saved_at = 0.0

    def observe(self, chunk):
        self.pending += chunk
        end = self.pending.rfind(b'\n') + 1
        text = self.pending[:end].decode(errors='replace')
        self.pending = self.pending[end:][-128*1024:]
        self.trace = (self.trace + text)[-128*1024:]
        observed = dll_status(text)
        models, model_evidence = model_dll_status(text)
        with self.lock:
            for line in text.splitlines():
                self.sound_trace.observe(line)
                if re.search(r'Loaded L".*\\+d3d9\.dll".*: native\s*$', line, re.I):
                    self.fields['native_d3d9_loaded'] = True
                if re.search(r'DXVK: v?2\.5\.3\b', line): self.fields['dxvk_loaded'] = '2.5.3'
                fps = re.search(r':([0-9a-f]+):[0-9a-f]+:trace:fps:wined3d_cs_exec_present ((?:0x)?[0-9a-f]+) @ approx ([0-9]+\.[0-9]+)fps', line, re.I)
                if fps:
                    stream = fps[1].lower() + ':' + fps[2].lower()
                    # Wine's first interval starts at tick zero, not first Present.
                    if stream in self.fps_streams and 0 <= float(fps[3]) <= 10000:
                        self.fields['wine_present'] = {'per_second': float(fps[3]), 'sampled_at': time.time(), 'stream': stream}
                    if len(self.fps_streams) < 64: self.fps_streams.add(stream)
                threading = re.search(r'Setting multithreaded command stream to (0x1|0x0|1|0)\.', line)
                if threading: self.fields['graphics_threading_observed'] = 'multi' if int(threading[1], 0) else 'single'
            self.fields['wine_log_bytes'] += len(chunk)
            self.fields['model_libraries_loaded'] = {**self.fields['model_libraries_loaded'], **models}
            self.fields['model_dll_evidence'] = list(dict.fromkeys(self.fields['model_dll_evidence'] + model_evidence))[-8:]
            for key in ('native_loaded', 'system_dinput8_loaded'):
                self.fields[key] |= observed[key]
            # Keep actual load evidence, not repeating MODULE thread events.
            if observed['native_loaded'] or observed['system_dinput8_loaded']:
                self.fields['dll_evidence'] = list(dict.fromkeys(self.fields['dll_evidence'] + observed['evidence']))[-8:]
            self.error = self.error or fatal_launch_error(self.trace)

    def save_sound_trace(self, final=False):
        if not final and time.monotonic()-self.sound_saved_at < 5: return
        self.sound_saved_at = time.monotonic()
        target = self.path.with_suffix('.sound.json')
        temporary = target.with_suffix('.new')
        try:
            with self.lock: report = json.dumps(self.sound_trace.report(), indent=2)
            temporary.write_text(report+'\n'); os.replace(temporary, target)
        except OSError:
            # Optional diagnostics must not turn a working client into a failure.
            with self.lock: self.fields['sound_trace_write_failed'] = True

    def snapshot(self):
        with self.lock: return dict(self.fields), self.error

    def pump(self, stream):
        output = None
        try:
            output = self.path.open('wb'); written = 0
            while chunk := stream.read1(min(64*1024, self.limit)):
                self.observe(chunk)
                self.save_sound_trace()
                if written + len(chunk) > self.limit:
                    output.close()
                    os.replace(self.path, self.path.with_suffix('.overflow.log'))
                    output = self.path.open('wb'); written = 0
                    with self.lock: self.fields['wine_log_rotations'] += 1
                output.write(chunk); output.flush(); written += len(chunk)
            if self.pending:
                # Check a final non-newline-terminated diagnostic, without
                # counting the synthetic delimiter as output from Wine.
                self.observe(b'\n')
                with self.lock: self.fields['wine_log_bytes'] -= 1
        except OSError as error:
            with self.lock: self.error = 'Could not capture Wine output: ' + str(error)
        finally:
            self.save_sound_trace(final=True)
            if output: output.close()
            stream.close()


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
    spell_test = client_spells.verify_installed_test(CLIENT, request.get('spell_test', {}))
    if request.get('npc_rendering', 'compatibility') not in ('standard', 'compatibility', 'compatibility_042', 'direct_043'): raise ValueError('Invalid NPC rendering option')
    if not isinstance(request.get('audio', False), bool): raise ValueError('Invalid audio option')
    if not isinstance(request.get('sound_diagnostics', False), bool): raise ValueError('Invalid sound diagnostic option')
    if request.get('mode') not in ('desktop', 'client'): raise ValueError('Choose Wine desktop or ROF2 client')
    if request.get('resolution') not in RESOLUTIONS: raise ValueError('Unsupported client resolution')
    if request.get('renderer', 'software') not in ('software', 'virgl', 'turnip'): raise ValueError('Unsupported graphics option')
    client_vulkan.driver_file(request.get('turnip_driver', client_vulkan.DEFAULT_DRIVER))
    if request.get('cpu_affinity', 'available') not in ('available', 'game'): raise ValueError('Unsupported CPU affinity')
    if request.get('cpu_profile', 'balanced') not in ('balanced', 'compatibility', 'accurate'): raise ValueError('Unsupported CPU profile')
    if request.get('runtime_mode', 'auto') not in ('auto', 'compatibility'): raise ValueError('Unsupported runtime mode')
    if request.get('graphics_threading', 'multi') not in ('multi', 'single', 'opengl_worker'): raise ValueError('Unsupported graphics threading')
    if not isinstance(request.get('fullscreen', False), bool): raise ValueError('Invalid fullscreen option')
    if not isinstance(request.get('native_d3dx', False), bool): raise ValueError('Invalid model-library option')
    if not isinstance(request.get('diagnostic_logging', False), bool): raise ValueError('Invalid Wine diagnostic option')
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
    return spell_test


def dll_status(log):
    """Require Wine's native-load trace, not the requested override or file presence."""
    matches = [line for line in log.splitlines() if 'dinput8.dll' in line.lower()]
    loaded = [line for line in matches if 'loaddll' in line.lower()
              and re.search(r'Loaded L"D:\\+dinput8\.dll".*: native\s*$', line, re.I)]
    system = [line for line in matches if 'loaddll' in line.lower()
              and re.search(r'Loaded L"C:\\+windows\\+(?:system32|syswow64)\\+dinput8\.dll".*: builtin\s*$', line, re.I)]
    return {'native_loaded': bool(loaded), 'system_dinput8_loaded': bool(system), 'evidence': (loaded + system or matches)[-8:]}


def fatal_launch_error(log):
    match = re.search(r'wine: could not load kernel32\.dll, status ([0-9a-f]+)', log, re.I)
    if match:
        return 'Wine could not start its Windows loader (kernel32.dll, ' + match[1] + '). See client-prefix.log and client-wine.log; ROF2 did not reach game initialization.'
    # An optional LoadLibrary can report a missing dependency and recover. Require
    # the loader's process-termination message before stopping the whole display.
    if re.search(r'err:module:\w+ (?:Importing|Initializing).*failed, status', log):
        missing = re.findall(r'err:module:import_dll Library ([^\r\n]+)', log)
        if missing:
            return 'A required Windows library could not load: ' + missing[-1][:350] + '. Export Logs for the dependency details.'
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


MODEL_DLLS = ('d3dx9_30.dll', 'd3dx9_35.dll')
DIRECTX_SOURCE_SHA256 = '053f76dcbb28802e23341b6a787e3b0791c0fa5c8d4d011b1044172dbf89c73b'


def prepare_model_libraries(source=Path('/directx'), prefix=PREFIX):
    """Validate the complete pair before changing Wine's 32-bit system folder."""
    manifest_path = source / 'directx.json'
    if not manifest_path.is_file() or manifest_path.is_symlink() or manifest_path.stat().st_size > 16384:
        raise ValueError('Install DirectX model helpers in the Client tab first')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('format') != 1 or manifest.get('source_sha256') != DIRECTX_SOURCE_SHA256:
        raise ValueError('Unsupported DirectX helper manifest; install the matching Microsoft package again')
    verified = {}
    for name in MODEL_DLLS:
        path = source / name
        meta = manifest.get('files', {}).get(name, {})
        if not path.is_file() or path.is_symlink() or not 128 <= path.stat().st_size <= 16*1024*1024:
            raise ValueError('Missing or invalid DirectX helper: ' + name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.stat().st_size != meta.get('bytes') or digest != meta.get('sha256') or pe_machine(path) != 0x14c:
            raise ValueError('DirectX helper verification failed: ' + name)
        verified[name] = digest
    destination = prefix / 'drive_c/windows/syswow64'
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError('Initialize the Wine prefix before installing model helpers')
    backup = prefix / 'trasc-directx-originals'
    backup.mkdir(exist_ok=True)
    changed = []
    with tempfile.TemporaryDirectory(prefix='directx-', dir=prefix) as temporary:
        temporary = Path(temporary)
        try:
            for name in MODEL_DLLS:
                target = destination / name
                if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == verified[name]:
                    continue
                # Backups are regular snapshots even if Wine originally used a link.
                old = temporary / (name + '.old')
                if target.exists():
                    shutil.copy2(target, old)
                    if not (backup / name).exists(): shutil.copy2(target, backup / name)
                elif target.is_symlink():
                    raise ValueError('Broken Wine system-library link: ' + name)
                fresh = temporary / name
                shutil.copy2(source / name, fresh)
                os.replace(fresh, target)
                changed.append((target, old if old.exists() else None))
        except Exception:
            for target, old in reversed(changed):
                if old: os.replace(old, target)
                else: target.unlink(missing_ok=True)
            raise
    return verified


def model_dll_status(log):
    loaded, evidence = {}, []
    for line in log.splitlines():
        if 'loaddll' not in line.lower(): continue
        match = re.search(r'Loaded L".*\\+(d3dx9_(?:30|35)\.dll)".*: (native|builtin)\s*$', line, re.I)
        if match:
            loaded[match[1].lower()] = match[2].lower()
            evidence.append(line)
    return loaded, evidence[-8:]


def graphics_status(requested, guest, host=''):
    """Report measured driver identity, never equate a requested bridge with a GPU."""
    match = re.search(r'^OpenGL renderer string:\s*(.+)$', guest, re.M)
    if not match: raise RuntimeError('OpenGL driver check failed; see client-graphics.log and try Software graphics')
    renderer = match[1].strip()
    if requested == 'virgl' and not renderer.lower().startswith('virgl'):
        raise RuntimeError('GPU bridge was requested but Mesa did not load VirGL. See client-gpu.log and client-graphics.log; choose Software graphics to recover')
    native = re.search(r'^TRASC GPU renderer:\s*(.+)$', host, re.M)
    native = native[1].strip() if native and requested == 'virgl' else ''
    software = any(word in (renderer+' '+native).lower() for word in ('llvmpipe','softpipe','swiftshader','lavapipe','software'))
    return {'renderer': 'WineD3D / '+renderer, 'graphics_backend': requested,
            'host_gl_renderer': native,
            'graphics_acceleration': 'software' if software else 'host_gpu' if native else 'unknown'}


class Supervisor:
    def __init__(self, request):
        self.request = request
        self.children = []
        self.wine_log = None
        self.log_thread = None
        self.last_thread_sample = 0
        self.launch_token = secrets.token_hex(16)
        self.started_monotonic = time.monotonic()
        self.status = {'phase': 'starting', 'mode': request['mode'], 'resolution': request['resolution'], 'fullscreen': request.get('fullscreen', False), 'display_target_fps': 30,
                       'native_dinput8_requested': request['mode']=='client' and request.get('native_dinput8', True), 'native_loaded': False,
                       'system_dinput8_loaded': False,
                       'diagnostic_logging': request.get('diagnostic_logging', False),
                       'native_d3dx_requested': request['mode']=='client' and request.get('native_d3dx', False),
                       'renderer': 'Checking graphics driver', 'graphics_backend': request.get('renderer','software'),
                       'graphics_acceleration': 'unknown', 'started_at': time.time()}
        self.status.update(cpu_profile=request.get('cpu_profile', 'balanced'), timings_seconds={})
        self.status['graphics_threading'] = request.get('graphics_threading', 'multi')
        self.status.update(runtime_mode=request.get('runtime_mode', 'auto'),
                           runtime_acceleration=request.get('runtime_acceleration', 'unspecified'),
                           storage=request.get('storage', {}))
        self.env = dict(os.environ, DISPLAY=':7', XAUTHORITY=str(SESSION / 'Xauthority'),
                        WINEPREFIX=str(PREFIX), WINEARCH='win64', WINEDEBUG=wine_debug(),
                        WINEDLLOVERRIDES='winemenubuilder,mscoree,mshtml,winegstreamer=',
                        BOX64_DYNAREC_STRONGMEM='1', BOX64_DYNAREC_BIGBLOCK='0', BOX64_DYNAREC_SAFEFLAGS='2',
                        BOX64_LOG='1', BOX64_NOBANNER='0', BOX64_PATH='/opt/wine/bin',
                        BOX64_LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/opt/wine/lib/wine/x86_64-unix',
                        LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe', LP_NUM_THREADS='4')
        if Path(__file__).with_name('wineserver-patch.json').is_file():
            # Wine 10 prefers its adjacent binary over WINESERVER. Android binds
            # the verified APK helper here for the lifetime of this session.
            self.env['WINESERVER'] = '/opt/wine/bin/wineserver'
        # Wine 10's supported per-launch configuration overrides registry state.
        # No prefix edits: stop/relaunch switches modes independently of CPU flags.
        self.env['WINE_D3D_CONFIG'] = 'csmt=' + ('1' if request.get('graphics_threading', 'multi') == 'multi' else '0')
        # DRI's supported override starts Mesa's native GL command worker.
        # Keep old modes explicit so switching back removes the experiment.
        self.env['mesa_glthread'] = 'true' if request.get('graphics_threading') == 'opengl_worker' else 'false'
        self.status['mesa_glthread_requested'] = self.env['mesa_glthread'] == 'true'
        self.env['TRASC_CLIENT_LAUNCH'] = self.launch_token
        if request.get('renderer','software') == 'virgl':
            # swrast's virpipe transport forwards rendering to the native GLES
            # server. LIBGL_ALWAYS_SOFTWARE selects that headless DRI loader;
            # it does not select llvmpipe when GALLIUM_DRIVER is virpipe.
            self.env.update(GALLIUM_DRIVER='virpipe', VTEST_SOCKET_NAME='/tmp/.virgl_test')
        if request.get('cpu_profile', 'balanced') in ('balanced', 'accurate'):
            self.env.update(BOX64_DYNAREC_BIGBLOCK='2', BOX64_DYNAREC_SAFEFLAGS='1',
                            BOX64_MAXCPU='0', BOX64_RCFILE=str(SESSION / 'box64.rc'))
        if request.get('cpu_profile') == 'accurate':
            # Independent of GPU mapping. The pinned Box64 documents single
            # precision x87 and fast rounding/NaN defaults. This comparison
            # preserves double intermediates and x86 rounding semantics.
            self.env.update(BOX64_DYNAREC_X87DOUBLE='1', BOX64_DYNAREC_FASTNAN='0',
                            BOX64_DYNAREC_FASTROUND='0', BOX64_SYNC_ROUNDING='1')
        self.status['cpu_affinity'] = request.get('cpu_affinity', 'available')
        if request.get('renderer') == 'turnip':
            version = request.get('turnip_driver', client_vulkan.DEFAULT_DRIVER)
            self.status['turnip_driver_requested'] = version
            client_vulkan.configure_environment(self.env, Path(__file__).parent, SESSION, PREFIX, version)
            self.env['DXVK_CONFIG'] = client_vulkan.npc_configuration(request.get('npc_rendering', 'compatibility'))
            self.status['npc_rendering'] = request.get('npc_rendering', 'compatibility')
            self.status['mesa_glthread_requested'] = False
        else:
            # Built-in WineD3D ignores a previously installed DXVK copy. This
            # makes switching back work without a prefix repair or registry edit.
            self.env['WINEDLLOVERRIDES'] += ';d3d9=b'
        if request.get('audio', False): client_audio.configure_environment(self.env, SESSION)
        else: self.env['WINEDLLOVERRIDES'] += ';winepulse.drv=d;winealsa.drv=d'

    def configure_cpu(self):
        if self.request.get('cpu_profile', 'balanced') in ('balanced', 'accurate'):
            # This runtime only launches our Wine desktop and the imported ROF2.
            # Box64's stock [wine] entry overrides the environment with 64 CPUs.
            # Use a private rcfile so the real CPU count and selected flags win;
            # preserve its explorer-specific small-block startup workaround.
            (SESSION / 'box64.rc').write_text(
                '[wine]\nBOX64_MAXCPU=0\n[wine64]\nBOX64_MAXCPU=0\n'
                '[explorer.exe]\nBOX64_DYNAREC_BIGBLOCK=0\n'
                '[eqgame.exe]\nBOX64_DYNAREC_BIGBLOCK=2\nBOX64_DYNAREC_SAFEFLAGS=1\nBOX64_DYNAREC_STRONGMEM=1\n')
        settings = {k: v for k, v in self.env.items() if k.startswith('BOX64_')}
        try: affinity = sorted(os.sched_getaffinity(0))
        except (AttributeError, OSError): affinity = []
        self.update(cpu_settings=settings, available_cpu_ids=affinity)

    @contextmanager
    def timed(self, name):
        started = time.monotonic()
        try: yield
        finally:
            elapsed = round(time.monotonic() - started, 3)
            self.status['timings_seconds'][name] = elapsed
            self.update()
            print(f'Client timing: {name}={elapsed}s', flush=True)

    def prefix_signature(self):
        # Content fingerprints survive backup/restore and invalidate on runtime
        # upgrades. The overlay is checked separately before this is called.
        paths = [Path('/etc/trasc-client-runtime.json'), Path('/opt/wine/share/wine/wine.inf'),
                 Path('/opt/wine/lib/wine/i386-windows/ntdll.dll')]
        return {'format': 1, 'runtime': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                'wined3d': self.status.get('wined3d_sha256', '')}

    def prepare_prefix(self):
        marker = PREFIX / '.trasc-prefix-ready.json'
        signature = self.prefix_signature()
        try: previous = json.loads(marker.read_text())
        except (OSError, ValueError): previous = None
        ready = previous == signature and prefix_diagnostics()['prefix_ready']
        # -u forces Wine to copy/register its system files again, even when
        # unchanged. -i boots services and honors Wine's own update timestamp.
        # Invalidate first so interrupted or failed checks always retry -u.
        marker.unlink(missing_ok=True)
        self.update('preparing_prefix', prefix_update='reuse' if ready else 'update')
        with self.timed('wine_prefix'):
            self.run(['/usr/local/bin/box64', '/opt/wine/bin/wine', 'wineboot', '-i' if ready else '-u'])
        with self.timed('wine32_check'): self.check_prefix()
        temporary = marker.with_suffix('.new')
        temporary.write_text(json.dumps(signature)); os.replace(temporary, marker)

    def update(self, phase=None, **fields):
        if phase: self.status['phase'] = phase
        self.status.update(fields)
        p = SESSION / 'status.json'; tmp = p.with_suffix('.new')
        tmp.write_text(json.dumps(self.status, indent=2)); os.replace(tmp, p)
        report = LOGS / 'client-state.json'; tmp = report.with_suffix('.new')
        tmp.write_text(json.dumps(self.status, indent=2)); os.replace(tmp, report)

    def stopping(self):
        if (SESSION / 'gpu-failed').exists():
            raise RuntimeError('Android GPU bridge exited unexpectedly; see client-gpu.log. Choose Software graphics to compare')
        if stop_requested or (SESSION / 'stop').exists():
            self.status['stop_reason'] = stop_reason or 'stop_request'
            return True
        return False

    def spawn(self, args, log, env=None):
        if log == 'client-wine.log':
            self.wine_log = WineLog(LOGS / log)
            process = subprocess.Popen(args, env=env or self.env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True, cwd=CLIENT)
            self.log_thread = threading.Thread(target=self.wine_log.pump, args=(process.stdout,), daemon=True)
            self.log_thread.start()
            self.children.append(process)
            return process
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
        self.run(['/usr/local/bin/box64', '/opt/wine/bin/wine', r'C:\windows\syswow64\cmd.exe', '/d', '/c', 'exit', '0'],
                 timeout=60, label='32-bit Wine check')
        self.update(wine32_ready=True)

    def check_graphics(self):
        self.update('checking_graphics')
        if self.request.get('renderer') == 'turnip':
            version = self.request.get('turnip_driver', client_vulkan.DEFAULT_DRIVER)
            manifest, command = client_vulkan.prepare_probe(Path(__file__).parent, SESSION, PREFIX, self.env, version)
            self.update(turnip_driver={'version': version, 'file': client_vulkan.driver_file(version),
                        'sha256': manifest['files'][client_vulkan.driver_file(version)]},
                        vulkan_bundle=manifest)
            process = self.spawn(command, 'client-vulkan.log')
            deadline = time.monotonic()+30
            while process.poll() is None:
                if self.stopping(): raise StopRequested()
                if time.monotonic()>deadline: raise RuntimeError('Turnip '+version+' preflight timed out. Stop, select Turnip 24.3.4 or VirGL, and export Logs.')
                time.sleep(.1)
            if process.returncode: raise RuntimeError('Turnip '+version+' device/presentation check failed. See client-vulkan.log; select Turnip 24.3.4 or VirGL to recover.')
            report = client_vulkan.parse_probe((LOGS/'client-vulkan.log').read_text(errors='replace'),
                allow_software=os.environ.get('TRASC_TEST_ALLOW_SOFTWARE_VULKAN') == '1', expected_mesa=version)
            self.update(renderer='DXVK / '+report['driver']+' ('+report['device']+')',
                        graphics_acceleration='software_test' if report['software'] else 'host_gpu',
                        vulkan=report, vulkan_bundle=manifest, presentation='Vulkan → X11 copy → in-app display')
            return
        command = ['python3', str(Path(__file__).with_name('graphics_probe.py'))] if self.request.get('renderer')=='virgl' else ['glxinfo', '-B']
        process = self.spawn(command, 'client-graphics.log')
        deadline = time.monotonic()+30
        while process.poll() is None:
            if self.stopping(): raise StopRequested()
            if time.monotonic()>deadline: raise RuntimeError('OpenGL driver check timed out; choose Software graphics and export Logs')
            time.sleep(.1)
        if process.returncode: raise RuntimeError('OpenGL driver setup failed; see client-graphics.log and client-gpu.log. Choose Software graphics to compare')
        host = LOGS / 'client-gpu.log'
        host_text = host.read_text(errors='replace')[-65536:] if host.is_file() else ''
        report = graphics_status(self.request.get('renderer','software'), (LOGS/'client-graphics.log').read_text(errors='replace'), host_text)
        self.update(**report)

    def start(self):
        self.status['spell_test'] = validate_request(self.request)
        print(f"Client session started at {self.status['started_at']}: {self.request['mode']}", flush=True)
        for p in (SESSION, PREFIX, LOGS): p.mkdir(parents=True, exist_ok=True)
        previous_state = LOGS/'client-state.json'
        if previous_state.is_file() and not previous_state.is_symlink() and previous_state.stat().st_size <= 131072:
            shutil.copyfile(previous_state, LOGS/'client-state.previous.json')
        self.configure_cpu()
        if self.request.get('audio', False):
            self.update(audio=client_audio.prepare(Path(__file__).parent, SESSION))
        else: self.update(audio={'backend': 'disabled'})
        if 'WINESERVER' in self.env:
            patch = json.loads(Path(__file__).with_name('wineserver-patch.json').read_text())
            binary = Path(self.env['WINESERVER'])
            if binary.is_symlink() or not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != patch['sha256']:
                raise RuntimeError('Bundled Wine server failed verification')
            self.update(wineserver_patch=patch['patch'], wineserver_sha256=patch['sha256'], wineserver_exit_grace_seconds=patch['exit_grace_seconds'], wineserver_path=str(binary))
        native_log = LOGS / 'client-proot.log'
        observed = False
        if native_log.is_file():
            with native_log.open('rb') as source:
                observed = b'TRASC PRoot: seccomp acceleration observed' in source.read(4096)
        self.update(runtime_acceleration_observed=observed)
        if self.request.get('runtime_acceleration') == 'seccomp' and not observed:
            raise RuntimeError('Runtime acceleration was not confirmed. Select Compatibility runtime mode and export Logs.')
        for name in ('client-wine.log', 'client-prefix.log', 'client-display.log', 'client-graphics.log', 'client-threads.log', 'client-vulkan.log', 'eqgame_d3d9.log'):
            archive_log(LOGS / name)
        sound_report = LOGS / 'client-wine.sound.json'
        if sound_report.is_file(): sound_report.replace(LOGS / 'client-wine.sound.previous.json')
        (LOGS / 'client-wine.overflow.log').unlink(missing_ok=True)
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
        self.update(display_ready=True)
        with self.timed('graphics_check'): self.check_graphics()
        patch = Path(__file__).with_name('wined3d-patch.json')
        if patch.is_file():
            expected = json.loads(patch.read_text())
            actual = hashlib.sha256(Path('/opt/wine/lib/wine/i386-windows/wined3d.dll').read_bytes()).hexdigest()
            if actual != expected['sha256']: raise RuntimeError('WineD3D compatibility fix failed verification')
            self.update(wined3d_patch=expected['patch'], wined3d_sha256=actual)
        self.prepare_prefix()
        if self.request.get('renderer') == 'turnip':
            self.update(dxvk_d3d9_sha256=client_vulkan.install_d3d9(Path(__file__).parent, PREFIX, CLIENT))
        devices = PREFIX / 'dosdevices'; devices.mkdir(exist_ok=True)
        drive = devices / 'd:'
        if drive.is_symlink(): drive.unlink()
        if drive.exists(): raise RuntimeError('Wine D: drive is already occupied')
        drive.symlink_to(CLIENT)
        args = ['/usr/local/bin/box64', '/opt/wine/bin/wine', 'explorer', '/desktop=TRASC,' + self.request['resolution']]
        env = dict(self.env)
        env['WINEDEBUG'] = wine_debug(self.request.get('diagnostic_logging', False), self.request.get('sound_diagnostics', False))
        if self.request['mode'] == 'client':
            preserve_game_log()
            self.update(sound_diagnostics=self.request.get('sound_diagnostics', False),
                        sound_assets=client_audio.inspect_client(CLIENT, LOGS, packed=self.request.get('sound_diagnostics', False)))
            self.update(skin_shader=client_vulkan.skin_shader_status(CLIENT))
            if 'fullscreen' in self.request:
                self.update(display_settings=apply_display(CLIENT, PREFIX, self.request['resolution'], self.request['fullscreen']))
            args += ['D:\\' + self.request['executable'], 'patchme']
            # The imported DLL forwards DirectInput8Create to an absolute system
            # dinput8 path. Native-only blocks Wine's system DLL and breaks input.
            override = 'n,b' if self.request.get('native_dinput8', True) else 'b'
            env['WINEDLLOVERRIDES'] += ';dinput8=' + override
            native_models = self.request.get('native_d3dx', False)
            if native_models:
                with self.timed('model_helpers'):
                    self.update('preparing_models', model_library_sha256=prepare_model_libraries())
            for name in MODEL_DLLS:
                env['WINEDLLOVERRIDES'] += ';' + name[:-4] + ('=n,b' if native_models else '=b')
            self.status['dinput8_override'] = override
        launcher = self.spawn(args, 'client-wine.log', env)
        self.status['timings_seconds']['until_launch_requested'] = round(time.monotonic() - self.started_monotonic, 3)
        self.update('launch_requested', display_ready=True, launcher_pid=launcher.pid)
        while not self.stopping():
            if xserver.poll() is not None: raise RuntimeError('Display exited; see client-display.log')
            observed, fatal = self.wine_log.snapshot()
            if fatal: raise RuntimeError(fatal)
            if time.monotonic() - self.last_thread_sample >= 10:
                self.last_thread_sample = time.monotonic()
                before = time.monotonic()
                sample = process_threads(launcher.pid, launch_token=self.launch_token)
                if self.request.get('cpu_affinity', 'available') == 'available' and self.request['mode'] == 'client':
                    sample['affinity_update'] = allow_game_cpus(sample, self.launch_token)
                    self.status['affinity_update'] = sample['affinity_update']
                sample['collection_seconds'] = round(time.monotonic()-before, 4)
                self.status['mesa_glthread_observed'] = bool(sample['mesa_gl_workers'])
                # Keep the once-per-second status file small. Full thread
                # counters belong only in the ten-second diagnostic log.
                self.status['thread_sample'] = {k:v for k,v in sample.items() if k != 'threads'}
                self.status['thread_sample']['thread_count'] = len(sample['threads'])
                path = LOGS/'client-threads.log'
                if path.exists() and path.stat().st_size > WINE_LOG_LIMIT:
                    os.replace(path, path.with_suffix('.overflow.log'))
                with path.open('a') as output:
                    output.write(json.dumps(sample)+'\n')
            self.update(launcher_exit=launcher.poll(), **observed)
            time.sleep(1)

    def stop(self):
        try:
            subprocess.run(['/usr/local/bin/box64', self.env.get('WINESERVER', '/opt/wine/bin/wineserver'), '-k'], env=self.env,
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
        if self.log_thread:
            self.log_thread.join(timeout=2)
            self.status.update(self.wine_log.snapshot()[0])
        (SESSION / 'display.sock').unlink(missing_ok=True)
        self.update(display_ready=False)


def main():
    global stop_requested, stop_reason
    def stop(signum, _frame):
        global stop_requested, stop_reason
        stop_requested = True
        stop_reason = signal.Signals(signum).name
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
            print(f"Client session ended at {time.time()}: {supervisor.status.get('error') or supervisor.status.get('stop_reason', 'completed')}", flush=True)


if __name__ == '__main__': main()
