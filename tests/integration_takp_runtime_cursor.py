#!/usr/bin/env python3
"""Run the same PE32 fixture through the published ARM64 client input path.

All Wine registry changes apply to new fixture prefixes. This program runs only
inside the pinned CI rootfs; it never imports or modifies player data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback

from integration_takp_cursor import run

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from client_xauthority import write_xauthority

CASES = (
    ('default', None, None, False),
    ('global-disabled', 'N', None, True),
    ('global-enabled', 'Y', None, False),
    ('app-disables-global', 'Y', 'N', True),
    ('app-enables-global', 'N', 'Y', False),
)


def run_case(name, global_grab, app_grab, negative, args):
    output = args.output / name
    output.mkdir(parents=True, exist_ok=True)
    settings = {'BOX64_DYNAREC_STRONGMEM': '1', 'BOX64_DYNAREC_BIGBLOCK': '2',
                'BOX64_DYNAREC_SAFEFLAGS': '1', 'BOX64_LOG': '1', 'BOX64_NOBANNER': '0',
                'BOX64_PATH': '/opt/wine/bin',
                'BOX64_LD_LIBRARY_PATH': '/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:/opt/wine/lib/wine/x86_64-unix',
                'BOX64_MAXCPU': '0', 'BOX64_RCFILE': str(output / 'box64.rc'),
                'BOX64_DYNAREC_X87DOUBLE': '1', 'BOX64_DYNAREC_FASTNAN': '0',
                'BOX64_DYNAREC_FASTROUND': '0', 'BOX64_SYNC_ROUNDING': '1',
                'WINESERVER': '/opt/wine/bin/wineserver',
                'XAUTHORITY': str(output / 'Xauthority'),
                'TRASC_FIXTURE_CONFIGURATION': str(output / 'prefix-configuration.json')}
    (output / 'box64.rc').write_text(
        '[wine]\nBOX64_MAXCPU=0\n[wine64]\nBOX64_MAXCPU=0\n'
        '[explorer.exe]\nBOX64_DYNAREC_BIGBLOCK=0\n'
        '[eqgame.exe]\nBOX64_DYNAREC_BIGBLOCK=2\nBOX64_DYNAREC_SAFEFLAGS=1\nBOX64_DYNAREC_STRONGMEM=1\n')
    for variable, value in (('TRASC_FIXTURE_GLOBAL_GRAB', global_grab),
                            ('TRASC_FIXTURE_APP_GRAB', app_grab)):
        if value is not None:
            settings[variable] = value
    prior = dict(os.environ)
    os.environ.pop('TRASC_FIXTURE_GLOBAL_GRAB', None)
    os.environ.pop('TRASC_FIXTURE_APP_GRAB', None)
    os.environ.update(settings)
    write_xauthority(settings['XAUTHORITY'], 33)
    result = {'case': name, 'global_grab': global_grab, 'app_grab': app_grab,
              'negative_control': negative, 'box64_settings': settings,
              'fixture_geometry': '800x600', 'thor_geometry': '1280x720',
              'physical_device_acceptance': False}
    error = None
    try:
        run(args.wine, args.probe, output, args.assets / 'input-probe', args.observer,
            ['-geometry', '800x600', '-depth', '24', '-rfbport', '-1',
             '-rfbunixpath', str(output / 'display.sock'), '-rfbunixmode', '0600',
             '-SecurityTypes', 'None', '-nolisten', 'tcp', '-nolock',
             '-auth', settings['XAUTHORITY'], '-AlwaysShared', '-FrameRate', '60',
             '-desktop', 'TRASC client'])
        result['fixture_completed'] = True
    except Exception as failure:
        error = failure
        result.update(fixture_completed=False, error_type=type(failure).__name__,
                      error=str(failure))
        (output / 'fixture-failure.log').write_text(traceback.format_exc())
    finally:
        # Closing all prefix-owned Wine processes is necessary before releasing
        # this display number and starting the next disposable fixture prefix.
        env = dict(os.environ, WINEPREFIX=str(output / 'prefix'))
        for command in (['/usr/local/bin/box64', '/opt/wine/bin/wineserver', '-k'],
                        ['/usr/local/bin/box64', '/opt/wine/bin/wineserver', '-w']):
            try:
                subprocess.run(command, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=15)
            except subprocess.TimeoutExpired:
                result['wineserver_cleanup_timeout'] = True
        os.environ.clear()
        os.environ.update(prior)
    configuration = output / 'prefix-configuration.json'
    if configuration.is_file():
        result['configuration'] = json.loads(configuration.read_text())
    diagnosis = output / 'cursor-diagnostics.log'
    rows = json.loads(diagnosis.read_text()) if diagnosis.is_file() else []
    capture = next((row for row in reversed(rows)
                    if row['stage'] in ('raw-capture-ready', 'fixture-failure')), None)
    observed_disabled = bool(isinstance(error, AssertionError) and capture and
        any(row['stage'] == 'raw-capture-ready' for row in rows) and
        capture['native']['clip'] == [400, 300, 401, 301] and
        capture['native']['foreground'] and capture['native']['focused'] and
        capture['native']['visible'] and capture['native']['rmb'] and
        tuple(capture['x_pointer']) != (400, 300))
    result['accepted'] = observed_disabled if negative else error is None
    result['disabled_capture_control_observed'] = observed_disabled
    result['interpretation'] = ('Expected accepted clip with escaped physical pointer' if observed_disabled
                                else 'Complete signed-input fixture passed' if error is None
                                else 'Unclassified fixture failure; inspect native and Wine telemetry')
    (output / 'runtime-camera-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('wine', 'probe', 'observer', 'assets', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('wine', 'probe', 'observer', 'assets', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('The published input path requires a native ARM64 CI runner')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'runtime-packages.log').write_text(subprocess.check_output(
        ['dpkg-query', '-W', 'tigervnc-standalone-server', 'libx11-6', 'libxi6', 'libxtst6'], text=True))
    results = [run_case(*case, args) for case in CASES]
    sources = ('tests/integration_takp_cursor.py', 'tests/integration_takp_runtime_cursor.py',
               'tests/takp_box64_wine.py', 'tests/takp_cursor_probe.cpp',
               'tests/takp_input_transport.py', 'scripts/prepare-takp-camera-runtime.py',
               'native/presentation/input.h', 'native/presentation/takp-xinput-observe.c',
               'native/presentation/observe-log.h', 'tests/takp_runtime_observer.Dockerfile')
    root = Path(__file__).resolve().parents[1]
    receipt = {'format': 1, 'github_commit': os.environ.get('GITHUB_SHA'),
               'github_run_id': os.environ.get('GITHUB_RUN_ID'),
               'runtime_rebuilt': False, 'production_input_bridge_rebuilt': False,
               'published_inputs': json.loads((args.assets / 'published-inputs.json').read_text()),
               'fixture_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources},
               'observer_sha256': hashlib.sha256(args.observer.read_bytes()).hexdigest(),
               'cases': results, 'all_cases_accepted': all(row['accepted'] for row in results),
               'scope': 'Published ARM64 Bookworm/Box64/Wine/TigerVNC and production TRASCIN1 input bridge; open PE32 consumer, not Android/PRoot/GPU or physical Thor acceptance'}
    (args.output / 'runtime-camera-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['all_cases_accepted'] else 1


if __name__ == '__main__':
    sys.exit(main())
