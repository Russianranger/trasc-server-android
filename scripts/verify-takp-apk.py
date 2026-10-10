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
    'eqw.dll': 'c103e024f1cde7829603475e1532d3baabd0764280c63ca2797e7e72569554f4',
}


def verify(apk, signing_report, root):
    expected_certificate = (root / 'docs/preview-signing.sha256').read_text().strip()
    match = re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})',
                      signing_report.read_text())
    if not match or match.group(1) != expected_certificate:
        raise ValueError('APK signing certificate changed; this is not a compatible update')
    with zipfile.ZipFile(apk) as archive:
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
        if camera['marker'] != 'TRASC_TAKP_WINE_RAW_LOOK_V2':
            raise ValueError('TAKP raw camera repair identity is missing')
        for name, digest in camera['patched_source_sha256'].items():
            preserved = root/'native/takp-eqw-source/eqw_takp'/name
            if hashlib.sha256(preserved.read_bytes()).hexdigest() != digest:
                raise ValueError('Preserved EQW patched source differs: ' + name)
        source = root / 'native/takp-eqw-source/eqw_takp/game_input.cpp'
        if hashlib.sha256(source.read_bytes()).hexdigest() != camera['patched_game_input_sha256']:
            raise ValueError('Preserved EQW source differs from compiled provenance')
        proof = json.loads(archive.read('assets/takp-client/eqw-cursor-verification.json'))
        for name in ('tests/takp_cursor_probe.cpp', 'tests/integration_takp_cursor.py', 'native/takp_camera_recenter.h'):
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
        for name in ('eqw-LICENSE.txt', 'd3d8to9-LICENSE.txt'):
            data = archive.read('assets/takp-client/' + name)
            if not data or data != (root / 'backend/takp-client' / name).read_bytes():
                raise ValueError('TAKP helper license is missing or changed: ' + name)
        if 'assets/takp-client/eqw.pdb' in archive.namelist():
            raise ValueError('The debug symbol file must not inflate the runtime APK')
    print('PASS: preserved certificate, exact x86 TAKP helpers, camera source/proof and Bots modules')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--signing-report', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args()
    verify(options.apk, options.signing_report, options.root)
