#!/usr/bin/env python3
"""Verify the update certificate and exact TAKP helper bytes in a built APK."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile


TAKP_HELPERS = {
    'd3d8.dll': '122928cfe225c25d30decf7184a5d37e490cecf3b58256ba3206c7e1853f8ab8',
    'eqgame.dll': 'f0ca8e4bdcf3875419ecb1067a95bd6dbf8197e564f9d51ff4dec98a30f14b97',
    'eqw.dll': 'ae556d045a0b64586b1e4f0c0957a75c99626f9f149f8e95b7bb99ed7a738fc8',
}
TAKP_OBSERVER_SHA = '5f5cf7e8f8d2d3df475284f72fa0f2944e1cadb9ba334927021799615b35744b'
TAKP_FOCUS_SHA = 'fcec1f6a4f0d1101efef56f58671b47944fd19219f0eeb3a4591a66607f5b364'
TAKP_FOCUS_V1_SHA = '90dda77cb0b0fe1d18d4fa7b39bedda7dad67af6c342d7b23c74d0129f666865'
TAKP_WINDOW_SHA = 'e1df07509f870d35f8feea87e64f20101597bd14dbc5ed0632335906b312d21c'


def verify_window_inspector(archive, root):
    binary = archive.read('assets/takp-input/takp-window-inspect')
    build = json.loads(archive.read('assets/takp-input/takp-window-inspector.json'))
    if (not isinstance(build, dict) or build.get('format') != 1
            or build.get('sha256') != TAKP_WINDOW_SHA or hashlib.sha256(binary).hexdigest() != TAKP_WINDOW_SHA
            or build.get('bytes') != len(binary) or len(binary) < 64
            or binary[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', binary, 18)[0] != 183
            or build.get('marker') != 'TRASC_TAKP_WINDOW_INSPECT_V1' or build['marker'].encode() not in binary
            or build.get('read_only') is not True or build.get('changes_focus_pointer_properties') is not False
            or build.get('bounded_output_bytes') != 128*1024 or build.get('max_seconds') != 300
            or build.get('property_bytes') != 128 or build.get('path_limit') != 16 or build.get('tree_node_limit') != 128):
        raise ValueError('TAKP read-only window inspector differs from qualified bounded ARM64 bytes')
    sources = {'native/presentation/takp-window-inspect.c', 'native/presentation/observe-log.h',
               'tests/takp_window_tools.Dockerfile', 'tests/takp_window_inspect_property.c'}
    if set(build.get('source_sha256', {})) != sources:
        raise ValueError('TAKP window inspector build provenance is incomplete')
    for name, digest in build['source_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError('TAKP window inspector source differs: ' + name)
    for name in ('takp-window-inspect', 'takp-window-inspector.json', 'window-qualification.json'):
        if archive.read('assets/takp-input/'+name) != (root/'backend/takp-input'/name).read_bytes():
            raise ValueError('TAKP window inspection asset differs: ' + name)
    if archive.read('assets/takp_window_diagnostics.py') != (root/'backend/takp_window_diagnostics.py').read_bytes():
        raise ValueError('TAKP read-only window inspector launcher differs')
    proof = json.loads(archive.read('assets/takp-input/window-qualification.json'))
    if (proof.get('format') != 1 or proof.get('inspector_sha256') != TAKP_WINDOW_SHA
            or proof.get('marker') != build['marker'] or proof.get('github_commit') != build.get('github_commit')
            or proof.get('github_run_id') != build.get('github_run_id')
            or proof.get('read_only_state_preserved') is not True or proof.get('invalid_cli_rejected') is not True
            or proof.get('signal_completion', {}).get('reason') != 'signal'):
        raise ValueError('TAKP window inspection runtime identity/completion is incomplete')
    fixtures = {'tests/integration_takp_window.py', 'tests/takp_focus_probe.cpp', 'tests/takp_cursor_probe.cpp',
                'tests/integration_takp_cursor.py', 'tests/takp_box64_wine.py', 'tests/takp_input_transport.py',
                'scripts/prepare-takp-window-runtime.py', 'scripts/prepare-takp-camera-runtime.py', 'backend/client_xauthority.py',
                'native/presentation/takp-window-inspect.c', 'native/presentation/observe-log.h', 'tests/takp_window_tools.Dockerfile'}
    if set(proof.get('fixture_sha256', {})) != fixtures:
        raise ValueError('TAKP window inspection fixture provenance is incomplete')
    for name, digest in proof['fixture_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError('TAKP window inspection fixture differs: ' + name)
    inputs = proof.get('published_inputs', {})
    if (inputs.get('apk_sha256') != '0073d46cc5b58c2a7f27c68d11e5fd3cc58a0b6afb8f208d19c7615bbba02859'
            or inputs.get('runtime', {}).get('sha256') != '2f130c07683e50bc606af111d5c35c4f503c1427772c1f9b0f45e1e4b75c76c4'
            or any(inputs.get(name) is not False for name in ('runtime_rebuilt', 'production_input_bridge_rebuilt', 'focus_helper_rebuilt', 'observer_rebuilt'))
            or inputs.get('preserved_companions_sha256') != {'takp-xinput-focus': TAKP_FOCUS_V1_SHA, 'takp-xinput-observe': TAKP_OBSERVER_SHA}):
        raise ValueError('TAKP window inspector did not reuse the published input path and original companions')
    expected = {'natural-wine-identity', 'title-optional-nul', 'class-optional-nul', 'title-wrong-type', 'class-wrong-type',
                'missing-title', 'missing-class', 'title-format-16', 'title-format-32', 'oversized-high-byte-title',
                'render-child-path', 'candidate-outside-covered-pointer-path', 'candidate-outside-screen-layout', 'idle-no-rmb'}
    cases = proof.get('cases', [])
    if (len(cases) != 14 or {row.get('case') for row in cases} != expected
            or any(row.get('before') != row.get('after') or not 0 < row.get('bytes', 0) <= 128*1024
                   or row.get('completion', {}).get('reason') != 'duration'
                   or row.get('completion', {}).get('dropped') != 0 for row in cases)):
        raise ValueError('TAKP property/layout/read-only diagnosis qualification is incomplete')
    transport = proof.get('transport', {})
    if (transport.get('protocol') != 'TRASCIN1' or not transport.get('closed')
            or transport.get('native_decoded') != {key: transport.get(key) for key in ('relative', 'absolute', 'buttons')}):
        raise ValueError('TAKP window diagnostic fixture transport verification is incomplete')


def verify_focus(archive, root):
    binary = archive.read('assets/takp-input/takp-xinput-focus')
    build = json.loads(archive.read('assets/takp-input/takp-input-focus.json'))
    if (not isinstance(build, dict) or build.get('format') != 1
            or build.get('sha256') != TAKP_FOCUS_SHA
            or hashlib.sha256(binary).hexdigest() != TAKP_FOCUS_SHA
            or build.get('bytes') != len(binary) or len(binary) < 64
            or binary[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', binary, 18)[0] != 183
            or build.get('marker') != 'TRASC_TAKP_X_FOCUS_RECOVERY_V2'
            or build['marker'].encode() not in binary
            or build.get('window_titles') != ['EqW-TAKP', 'Client1'] or build.get('window_class') != 'eqgame.exe'
            or build.get('focus_event_protocol') != 1 or build.get('focus_event_max_bytes') != 96
            or build.get('bounded_output_bytes') != 128*1024):
        raise ValueError('TAKP scoped focus helper differs from qualified ARM64 bytes')
    expected_sources = {'native/presentation/takp-xinput-focus.c', 'native/presentation/takp-focus-event.h',
                        'native/presentation/observe-log.h', 'tests/takp_focus_tools.Dockerfile', 'tests/takp_focus_event_writer.c'}
    if set(build.get('source_sha256', {})) != expected_sources:
        raise ValueError('TAKP native focus source provenance is incomplete')
    for name, digest in build['source_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError('TAKP native focus source differs: ' + name)
    for name in ('takp-xinput-focus', 'takp-input-focus.json', 'focus-qualification.json'):
        if archive.read('assets/takp-input/'+name) != (root/'backend/takp-input'/name).read_bytes():
            raise ValueError('TAKP qualified focus asset differs: ' + name)
    if archive.read('assets/takp_focus.py') != (root/'backend/takp_focus.py').read_bytes():
        raise ValueError('TAKP scoped focus launcher differs')
    proof = json.loads(archive.read('assets/takp-input/focus-qualification.json'))
    if (proof.get('format') != 1 or proof.get('focus_helper_sha256') != TAKP_FOCUS_SHA
            or proof.get('observer_sha256') != TAKP_OBSERVER_SHA
            or proof.get('github_commit') != build.get('github_commit')
            or proof.get('github_run_id') != build.get('github_run_id')):
        raise ValueError('TAKP scoped focus runtime identity is incomplete')
    sources = {'tests/integration_takp_focus.py', 'tests/takp_focus_probe_0630.cpp', 'tests/takp_focus_probe.cpp', 'tests/takp_cursor_probe.cpp',
               'tests/takp_box64_wine.py', 'tests/takp_input_transport.py', 'scripts/prepare-takp-focus-runtime.py',
               'scripts/prepare-takp-camera-runtime.py', 'native/takp_camera_recenter.h', 'native/takp_camera_trace.h',
               'native/takp_dinput_observation.h', 'native/presentation/input.h', 'native/presentation/takp-xinput-focus.c',
               'native/presentation/takp-xinput-observe.c', 'native/presentation/observe-log.h', 'tests/takp_focus_tools.Dockerfile',
               'native/takp_camera_recenter_v4.h', 'native/takp_camera_focus_event.h', 'native/presentation/takp-focus-event.h',
               'tests/takp_camera_focus_event.cpp', 'scripts/prepare-takp-eqw.py', 'scripts/record-takp-eqw.py'}
    if set(proof.get('fixture_sha256', {})) != sources:
        raise ValueError('TAKP scoped focus fixture provenance is incomplete')
    for name, digest in proof['fixture_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError('TAKP scoped focus fixture differs: ' + name)
    inputs = proof.get('published_inputs', {})
    if (inputs.get('runtime', {}).get('sha256') != '2f130c07683e50bc606af111d5c35c4f503c1427772c1f9b0f45e1e4b75c76c4'
            or inputs.get('apk_sha256') != 'e81e6afe2ac639a292d7c048cc7575a9cbd1af6a19f2cfe4a934f2c723e40fcf'
            or inputs.get('apk_asset_id') != 639098532 or inputs.get('apk_version_code') != 78
            or inputs.get('runtime_rebuilt') is not False or inputs.get('production_input_bridge_rebuilt') is not False
            or inputs.get('observer_rebuilt') is not False or inputs.get('preserved_observer_sha256') != TAKP_OBSERVER_SHA):
        raise ValueError('TAKP native focus was not tested through the preserved published input path')
    reproduction = proof.get('pointer_root_reproduction', {})
    wrong = reproduction.get('negative_reversal', {})
    if (not reproduction.get('native_foreground_preserved') or not reproduction.get('cached_clip_preserved')
            or reproduction.get('pointer_escaped') == [640, 360]
            or wrong.get('injected') != [-1, 0] or len(wrong.get('polled', [])) != 2
            or len(wrong.get('buffered', [])) != 2 or wrong['polled'][0] < 0 or wrong['buffered'][0] < 0):
        raise ValueError('TAKP PointerRoot physical failure was not reproduced')
    recovery = proof.get('recovery', {})
    path = recovery.get('pointer_path', [])
    if (recovery.get('title') != 'Client1' or recovery.get('viewport') != [1280, 720]
            or recovery.get('center') != [640, 360] or len(path) != 4 or len(set(path)) != 4
            or recovery.get('candidate') in (None, 0, 1) or path[-2] != recovery.get('candidate')
            or path[-1] != recovery.get('propertyless_render_child')
            or recovery.get('natural_title_property') != {'type':31, 'format':8, 'count':7, 'after':0, 'hex':'436c69656e7431'}
            or recovery.get('natural_class_property') != {'type':31, 'format':8, 'count':22, 'after':0, 'hex':'657167616d652e65786500657167616d652e65786500'}):
        raise ValueError('TAKP measured Client1 whole-window/render-child identity was not qualified')
    signed = recovery.get('signed_segments', [])
    expected = [[12, 0], [-12, 0], [24, 0], [-24, 0], [0, 12], [0, -12], [0, 24], [0, -24], [24, -12], [-24, 12]]
    if (len(signed) != 10 or [row.get('injected') for row in signed] != expected
            or any(row.get('polled') != row.get('injected') or row.get('buffered') != row.get('injected') for row in signed)
            or recovery.get('idle_drift') != [0, 0] or not recovery.get('physical_cursor_confined')
            or not recovery.get('focus_none_after_resume') or not recovery.get('rmb_release_restores_clip')
            or not recovery.get('menu_pointer_free')):
        raise ValueError('TAKP physical focus/capture recovery and signed input qualification is incomplete')
    legacy = recovery.get('legacy_signed_segments', [])
    if (recovery.get('legacy_title') != 'EqW-TAKP' or len(legacy) != 4
            or [row.get('injected') for row in legacy] != [[12,0], [-12,0], [0,12], [0,-12]]
            or any(row.get('polled') != row.get('injected') or row.get('buffered') != row.get('injected') for row in legacy)):
        raise ValueError('TAKP legacy exact EqW title and signed input support was not retained')
    menu = recovery.get('menu_normalization', {})
    quiet = recovery.get('legacy_quiet_baseline', {})
    if (menu.get('before_pointer') != [670,340] or menu.get('free_menu_motion') != [30,-20]
            or menu.get('normalization_while_look_off') is not True or menu.get('consumer_reset_or_drain') is not False
            or menu.get('pointer') != [640,360] or menu.get('rmb') is not False
            or menu.get('clip') != [0,0,1280,720] or menu.get('quiet_ms') != 300
            or quiet.get('quiet_ms') != 300 or quiet.get('pointer') != [640,360]
            or quiet.get('clip') != [640,360,641,361] or quiet.get('rmb') is not True
            or any(row.get(key) != [0,0] for row in (menu,quiet) for key in ('polled','buffered'))):
        raise ValueError('TAKP free-menu and legacy quiet baselines were not isolated and measured')
    guards = proof.get('negative_guards', [])
    required = {'released-button-does-not-focus', 'concrete-foreign-focus-preserved', 'wrong-title-does-not-focus',
                'title-wrong-case-does-not-focus', 'title-prefix-does-not-focus', 'title-suffix-does-not-focus',
                'title-optional-nul-does-not-focus', 'title-embedded-nul-does-not-focus',
                'legacy-title-prefix-does-not-focus', 'legacy-title-suffix-does-not-focus',
                'legacy-title-optional-nul-does-not-focus', 'missing-title-does-not-focus',
                'empty-title-does-not-focus', 'oversized-title-does-not-focus', 'title-wrong-type-does-not-focus',
                'title-format16-does-not-focus', 'title-format32-does-not-focus', 'wrong-class-does-not-focus',
                'class-wrong-case-does-not-focus', 'class-prefix-does-not-focus', 'class-suffix-does-not-focus',
                'class-optional-nul-does-not-focus', 'class-single-instance-does-not-focus',
                'missing-class-does-not-focus', 'empty-class-does-not-focus', 'oversized-class-does-not-focus',
                'class-wrong-type-does-not-focus', 'class-format16-does-not-focus', 'class-format32-does-not-focus',
                'duplicate-exact-ancestors-does-not-focus', 'foreign-pointer-window-does-not-focus', 'minimized-game-does-not-focus'}
    if (len(guards) != 32 or {row.get('case') for row in guards} != required
            or any(row.get('repairs_added') != 0 for row in guards)):
        raise ValueError('TAKP focus recovery refusal guards are incomplete')
    repairs = proof.get('focus_repairs', [])
    if (len(repairs) != 3 or [row.get('before') for row in repairs] != [1,1,0]
            or [row.get('event_sequence') for row in repairs] != [1,2,3]
            or any(not row.get('success') or row.get('candidate') != recovery['candidate']
                   or row.get('after') != recovery['candidate'] or row.get('path_depth') != 3
                   or row.get('identity') != 'EqW-TAKP|Client1/eqgame.exe'
                   or row.get('rmb') is not True or row.get('xerrors') != 0
                   or row.get('event_written') is not True or row.get('event_error') != 0 for row in repairs)):
        raise ValueError('TAKP Client1/legacy/None repair requests were not exactly scoped')
    completion = proof.get('focus_completion', {})
    if (completion.get('record') != 'end' or completion.get('attempts') != 3
            or completion.get('successes') != 3 or completion.get('dropped') != 0 or completion.get('xerrors') != 0):
        raise ValueError('TAKP focus helper normal bounded completion is incomplete')
    transport = proof.get('transport', {})
    if (transport.get('protocol') != 'TRASCIN1' or not transport.get('closed')
            or transport.get('native_decoded') != {key:transport.get(key) for key in ('relative','absolute','buttons')}):
        raise ValueError('TAKP focus fixture actual native input transport evidence is incomplete')
    notifications = recovery.get('focus_notifications', [])
    resume = recovery.get('centered_resume_signed_segments', [])
    reader_guards = recovery.get('event_reader_guards', [])
    expected_guards = {'missing-file','empty-file','truncated-record','foreign-session','wrong-protocol',
                       'stale-zero','duplicate-sequence','oversized-record','multiple-hard-links'}
    if (notifications != [{'sequence':1,'refreshes':1},{'sequence':2,'refreshes':2},{'sequence':3,'refreshes':3}]
            or recovery.get('centered_focus_loss_before_motion') is not True
            or len(resume) != 10 or [row.get('injected') for row in resume] != expected
            or any(row.get('polled') != row.get('injected') or row.get('buffered') != row.get('injected') for row in resume)
            or len(reader_guards) != 9 or {row.get('case') for row in reader_guards} != expected_guards
            or any(row.get('refreshes_added') != 0 or row.get('sequence') != 1 for row in reader_guards)
            or recovery.get('focus_event_bytes') != 47 or not re.fullmatch(r'TRASCFOCUS1 [0-9a-f]{32} 3\n', recovery.get('focus_event_tail',''))):
        raise ValueError('TAKP centered capture recovery or bounded notification refusal qualification is incomplete')
    camera = json.loads(archive.read('assets/takp-client/eqw-camera-build.json'))
    if (proof.get('shipping_eqw_build') != camera or camera.get('sha256') != TAKP_HELPERS['eqw.dll']
            or camera.get('marker') != 'TRASC_TAKP_WINE_RAW_LOOK_V4'
            or camera.get('build_commit') != proof.get('github_commit')
            or str(camera.get('build_run')) != str(proof.get('github_run_id'))):
        raise ValueError('TAKP shared-header ARM fixture did not fingerprint the actual shipping MSVC V4 build')
    shared = proof.get('shipping_eqw_shared_headers_sha256', {})
    if set(shared) != {'takp_camera_recenter_v4.h','takp_camera_focus_event.h'}:
        raise ValueError('TAKP V4 shared-header provenance is incomplete')
    for name,digest in shared.items():
        if hashlib.sha256((root/'native'/name).read_bytes()).hexdigest() != digest:
            raise ValueError('TAKP V4 event/capture header differs from tested code: ' + name)
    phases = proof.get('observer_phases', [])
    if (len(phases) != 2 or any(not 0 < row.get('bytes',0) <= 128*1024
            or row.get('completion',{}).get('reason') != 'signal' or row.get('completion',{}).get('dropped') != 0 for row in phases)):
        raise ValueError('TAKP bounded native observation phases were not completed normally')


def verify(apk, signing_report, root):
    expected_certificate = (root / 'docs/preview-signing.sha256').read_text().strip()
    match = re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})',
                      signing_report.read_text())
    if not match or match.group(1) != expected_certificate:
        raise ValueError('APK signing certificate changed; this is not a compatible update')
    with zipfile.ZipFile(apk) as archive:
        verify_window_inspector(archive, root)
        verify_focus(archive, root)
        observer = archive.read('assets/takp-input/takp-xinput-observe')
        observer_record = json.loads(archive.read('assets/takp-input/takp-input-observer.json'))
        if (hashlib.sha256(observer).hexdigest() != TAKP_OBSERVER_SHA
                or observer_record.get('sha256') != TAKP_OBSERVER_SHA
                or len(observer) != observer_record.get('bytes')
                or observer[:6] != b'\x7fELF\x02\x01'
                or struct.unpack_from('<H', observer, 18)[0] != 183
                or observer_record.get('bounded_output_bytes') != 128*1024
                or observer_record.get('maximum_seconds') != 300):
            raise ValueError('TAKP native input observer differs from its bounded ARM64 qualification')
        for name, digest in observer_record['source_sha256'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
                raise ValueError('TAKP native observer source differs from qualified build: ' + name)
        for name in ('takp-xinput-observe', 'takp-input-observer.json', 'observer-qualification.json'):
            if archive.read('assets/takp-input/'+name) != (root/'backend/takp-input'/name).read_bytes():
                raise ValueError('TAKP input diagnostic asset differs: ' + name)
        observer_proof = json.loads(archive.read('assets/takp-input/observer-qualification.json'))
        if (not observer_proof.get('all_observers_qualified') or len(observer_proof.get('cases', {})) != 5
                or observer_proof.get('verifier_sha256') != hashlib.sha256((root/'scripts/verify-takp-runtime-observer-evidence.py').read_bytes()).hexdigest()
                or any(not row.get('qualified') or row.get('bytes', 0) > 128*1024 for row in observer_proof['cases'].values())):
            raise ValueError('TAKP native observer lacks actual bounded XI2 qualification')
        runtime_proof_data = archive.read('assets/takp-client/runtime-camera-verification.json')
        if (runtime_proof_data != (root/'backend/takp-client/runtime-camera-verification.json').read_bytes()
                or hashlib.sha256(runtime_proof_data).hexdigest() != observer_proof['original_runtime_receipt_sha256']):
            raise ValueError('TAKP published-runtime receipt differs from measured input proof')
        runtime_proof = json.loads(runtime_proof_data)
        if (not runtime_proof.get('all_cases_accepted') or len(runtime_proof.get('cases', [])) != 5
                or runtime_proof.get('runtime_rebuilt') or runtime_proof.get('production_input_bridge_rebuilt')
                or runtime_proof.get('observer_sha256') != TAKP_OBSERVER_SHA):
            raise ValueError('TAKP published ARM64 input qualification is incomplete')
        for name, digest in runtime_proof['fixture_sha256'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
                raise ValueError('TAKP actual runtime fixture differs: ' + name)
        if archive.read('assets/takp_input_diagnostics.py') != (root/'backend/takp_input_diagnostics.py').read_bytes():
            raise ValueError('TAKP read-only input settings inspector differs')
        for name in ('engine.py', 'takp_build.py', 'takp_runtime.py', 'takp_client.py',
                     'bots.py', 'bot_socials.py', 'modern_bot_bridge.py', 'modern_bot_bridge.h'):
            if archive.read('assets/' + name) != (root / 'backend' / name).read_bytes():
                raise ValueError('APK is missing the current TAKP backend module: ' + name)
        for name, expected in TAKP_HELPERS.items():
            data = archive.read('assets/takp-client/' + name)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('TAKP helper differs from the reviewed pinned build: ' + name)
            if data[:2] != b'MZ' or len(data) < 64:
                raise ValueError('TAKP helper is not a PE binary: ' + name)
            offset = struct.unpack_from('<I', data, 0x3c)[0]
            if data[offset:offset + 4] != b'PE\0\0' or struct.unpack_from('<H', data, offset + 4)[0] != 0x14c:
                raise ValueError('TAKP helper must be a 32-bit x86 PE binary: ' + name)
        # The runtime receipt must ship with the exact DLLs for offline verification.
        archive_manifest = archive.read('assets/takp-client/bundle.json')
        if archive_manifest != (root / 'backend/takp-client/bundle.json').read_bytes():
            raise ValueError('TAKP helper receipt differs from the reviewed source')
        json.loads(archive_manifest)
        for name in ('eqw-camera-build.json', 'eqw-cursor-verification.json'):
            if archive.read('assets/takp-client/' + name) != (root / 'backend/takp-client' / name).read_bytes():
                raise ValueError('TAKP camera provenance differs from reviewed source: ' + name)
        camera = json.loads(archive.read('assets/takp-client/eqw-camera-build.json'))
        dll = archive.read('assets/takp-client/eqw.dll')
        if camera['sha256'] != TAKP_HELPERS['eqw.dll'] or camera['bytes'] != len(dll) or camera['marker'].encode() not in dll:
            raise ValueError('TAKP camera build receipt does not describe the compiled helper')
        for name, digest in camera['patch_files'].items():
            if hashlib.sha256((root / name.replace('\\', '/')).read_bytes()).hexdigest() != digest:
                raise ValueError('TAKP camera patch differs from its build provenance')
        if camera['marker'] != 'TRASC_TAKP_WINE_RAW_LOOK_V4':
            raise ValueError('TAKP raw camera repair identity is missing')
        if camera.get('trace_marker') != 'TRASC_TAKP_CAMERA_TRACE_V1' or camera['trace_marker'].encode() not in dll:
            raise ValueError('TAKP bounded input diagnostics identity is missing')
        event = camera.get('focus_event', {})
        if (event.get('protocol') != 'TRASCFOCUS1' or event.get('max_bytes') != 96
                or event.get('launch_token_bytes') != 32 or event.get('poll_interval_ms') != 20
                or event.get('regular_file_only') is not True or event.get('read_only') is not True
                or event.get('consume_when_look_off') is not True
                or event.get('path_environment') != 'TRASC_TAKP_FOCUS_EVENT' or event.get('token_environment') != 'TRASC_CLIENT_LAUNCH'):
            raise ValueError('TAKP V4 DLL session-event contract differs from qualification')
        for name in ('takp_camera_recenter_v4.h', 'takp_camera_focus_event.h', 'takp_camera_trace.h', 'takp_dinput_observation.h'):
            preserved_name = 'trasc_camera_recenter.h' if name == 'takp_camera_recenter_v4.h' else name
            if (root/'native/takp-eqw-source/eqw_takp'/preserved_name).read_bytes() != (root/'native'/name).read_bytes():
                raise ValueError('Preserved EQW diagnostic source differs: ' + name)
        for name, digest in camera['patched_source_sha256'].items():
            preserved = root/'native/takp-eqw-source/eqw_takp'/name
            if hashlib.sha256(preserved.read_bytes()).hexdigest() != digest:
                raise ValueError('Preserved EQW patched source differs: ' + name)
        source = root / 'native/takp-eqw-source/eqw_takp/game_input.cpp'
        if hashlib.sha256(source.read_bytes()).hexdigest() != camera['patched_game_input_sha256']:
            raise ValueError('Preserved EQW source differs from compiled provenance')
        proof = json.loads(archive.read('assets/takp-client/eqw-cursor-verification.json'))
        for name in ('tests/takp_cursor_probe.cpp', 'tests/integration_takp_cursor.py', 'native/takp_camera_recenter.h',
                     'native/takp_camera_trace.h', 'native/takp_dinput_observation.h', 'tests/takp_xinput_probe.c',
                     'tests/takp_input_transport.py', 'native/presentation/input.h'):
            if proof['fixture_sha256'].get(name) != hashlib.sha256((root/name).read_bytes()).hexdigest():
                raise ValueError('TAKP camera proof differs from its tested fixture: ' + name)
        if (proof['wine'] != 'wine-10.0' or proof['legacy_offsets'] != [20, 40, 60, 50]
                or len(proof['repaired_relative']) != 12
                or any(row['polled'] != row['injected'] or row['buffered'] != row['injected'] for row in proof['repaired_relative'])
                or proof['beyond_desktop'] != {'injected':[6400,-6400],'polled':[6400,-6400],'buffered':[6400,-6400]}
                or proof['idle_drift'] != [0,0] or not proof['rmb_release_restores_clip']
                or not proof['focus_restore_reenters_look'] or not proof['menu_pointer_free']
                or not proof['focus_loss_pointer_free'] or not proof['physical_release_no_reacquire']
                or proof['focus_restored_relative'] != {'injected':[-600,300],'polled':[-600,300],'buffered':[-600,300]}
                or proof['swapped_button_relative'] != {'injected':[300,-200],'polled':[300,-200],'buffered':[300,-200]}):
            raise ValueError('TAKP real Wine raw-input reversal qualification is missing')
        cadence = proof.get('controller_cadence', [])
        bursts = proof.get('pipelined_transport_bursts', [])
        transport = proof.get('transport', {})
        modes = proof.get('consumer_modes', {})
        trace = proof.get('diagnostic_trace', {})
        if (len(cadence) != 3 or len(bursts) != 3
                or any(row['polled'] != row['injected'] or row['buffered'] != row['injected'] for row in cadence + bursts)
                or any(row['pause_drift'] != [0,0] for row in cadence)
                or transport.get('protocol') != 'TRASCIN1' or transport.get('zero_relative', 0) < 10
                or not transport.get('closed') or transport.get('native_decoded') != {key:transport.get(key) for key in ('relative','absolute','buttons')}
                or modes.get('absolute_reset_model_after_negative_input') != [60,30]
                or modes.get('relative_state') != [40,0] or not modes.get('peek_repeats_same_events')
                or modes.get('custom_format_axis_offsets') != [8,0,4] or modes.get('custom_format_raw_memory') != [-5,0,9]
                or trace.get('marker') != 'TRASC_TAKP_CAMERA_TRACE_V1' or not 0 < trace.get('bounded_bytes', 0) <= 128*1024
                or not trace.get('foreign_file_preserved') or not trace.get('owned_session_rotated')):
            raise ValueError('TAKP production transport/consumer/diagnostics qualification is missing')
        recovery = proof.get('lost_x_grab_recovery', {})
        reversals = recovery.get('signed_reversals', [])
        if (not recovery.get('cached_rect_unchanged') or not recovery.get('native_gate_preserved')
                or recovery.get('legacy_physical_escape') == [400, 300]
                or recovery.get('same_rect_recovered_pointer') != [400, 300]
                or not recovery.get('metrics_recovered', {}).get('last_repair_ok')
                or recovery.get('metrics_recovered', {}).get('repairs', 0) <= recovery.get('metrics_lost', {}).get('repairs', 0)
                or len(reversals) != 6
                or any(row['polled'] != row['injected'] or row['buffered'] != row['injected'] for row in reversals)
                or recovery.get('idle_drift') != [0, 0]):
            raise ValueError('TAKP physical-grab recovery qualification is missing')
        for name in ('eqw-LICENSE.txt', 'd3d8to9-LICENSE.txt'):
            data = archive.read('assets/takp-client/' + name)
            if not data or data != (root / 'backend/takp-client' / name).read_bytes():
                raise ValueError('TAKP helper license is missing or changed: ' + name)
        if 'assets/takp-client/eqw.pdb' in archive.namelist():
            raise ValueError('The debug symbol file must not inflate the runtime APK')
    print('PASS: preserved certificate, exact TAKP helpers, published ARM64 scoped focus/input/observer proof and Bots modules')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--signing-report', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args()
    verify(options.apk, options.signing_report, options.root)
