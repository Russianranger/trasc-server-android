"""Exercise the Android client-only staging boundary in an isolated interpreter.

The server and hosted tests see backend/ in full. The Wine client only sees the
files ClientRuntime stages at /opt/trasc-client, which is a separate deployment.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from test_client_spellbook import synthetic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_spellbook


REPO = Path(__file__).resolve().parents[1]
CLIENT_RUNTIME = REPO / 'app/src/main/java/io/github/russianranger/trasc/ClientRuntime.java'

# Only the staged Python files enter sys.path: -I ignores PYTHONPATH, the
# repository cwd, the user's site packages and the parent test interpreter.
# The two Wine-facing configure methods run unchanged; registry subprocesses
# are recorded rather than requiring Wine/PRoot on the qualification host.
PROBE = r'''
import hashlib
import json
from pathlib import Path
import sys

stage, work, profile, base_hash, patched, guest_alias = sys.argv[1:]
sys.path.insert(0, stage)
import client_runner
import client_mouse
client_mouse.EXE_SHA256 = base_hash  # Invented, synthetic-only test executable.
if patched == 'yes':
    import client_spellbook
    client_spellbook.BASE_SHA256 = base_hash
    if guest_alias:
        # Qualification-host emulation of PRoot's /client and /work binds.
        # Hardlinks retain file identity; a plain copy is the negative case.
        client_spellbook.GUEST_CLIENT = Path(guest_alias)
        client_spellbook.GUEST_WORK = Path(work)
client_runner.CLIENT = Path(guest_alias) if guest_alias else Path(work) / 'client/current'
request = {'profile': profile, 'mode': 'client', 'executable': 'eqgame.exe',
           'native_dinput8': True, 'mouse_warp': True,
           'fast_spell_parse': True, 'reduce_load_pauses': True,
           'boat_mode': 'profile', 'particle_mode': 'off'}
supervisor = client_runner.Supervisor.__new__(client_runner.Supervisor)
supervisor.request = request
supervisor.env = {}
supervisor.camera_adapter_report = {'mode': 'off'}
state, registry = {}, []
supervisor.update = lambda **fields: state.update(fields)
supervisor.run = lambda *args, **kwargs: registry.append((args, kwargs))
supervisor.configure_mouse()
supervisor.configure_loading()
origins = {name: str(Path(module.__file__).resolve())
           for name, module in sys.modules.items()
           if name.startswith(('client_', 'traditional_', 'takp_', 'log_retention'))
           and getattr(module, '__file__', None)}
assert all(Path(path).parent == Path(stage) for path in origins.values()), origins
print(json.dumps({'state': state, 'env': supervisor.env,
                  'registry_calls': len(registry), 'origins': origins}))
'''


class ClientRunnerPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = synthetic(True)
        cls.original_hash = hashlib.sha256(cls.original).hexdigest()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stage = self.root / 'client-backend'
        self.stage.mkdir()
        source = CLIENT_RUNTIME.read_text()
        deployment = re.search(
            r'for\(String name:new String\[\]\{([^}]+)\}\)\s*'
            r'try\(InputStream in=context.getAssets\(\).open\(name\)\)\s*'
            r'\{RuntimeManager.copy\(in,new File\(backend,name\)\);\}', source)
        self.assertIsNotNone(deployment, 'Review the Android client staging contract')
        self.deployed = re.findall(r'"([^"]+)"', deployment.group(1))
        for name in self.deployed:
            if name.endswith('.py'):
                shutil.copyfile(REPO / 'backend' / name, self.stage / name)
        self.work = self.root / 'work'
        self.client = self.work / 'client/current'
        self.client.mkdir(parents=True)
        self.exe = self.client / 'eqgame.exe'
        self.exe.write_bytes(self.original)
        self.exe.chmod(0o755)
        (self.client / 'trasc-client.json').write_text(json.dumps({
            'executable': 'eqgame.exe', 'imported': True, 'imported_at': 10}))
        (self.client / 'dinput8.dll').write_bytes(
            b'TRASC_EQ_CAMERA_MOUSE_V2\0TRASC_EQ_LOAD_V2\0'
            b'TRASC_EQ_DISPLAY_V1\0TRASC_EQ_BOATS_V2')

    def probe(self, profile='custom', patched=False, guest_alias=None):
        result = subprocess.run(
            [sys.executable, '-I', '-c', PROBE, str(self.stage), str(self.work),
             profile, self.original_hash, 'yes' if patched else 'no',
             str(guest_alias) if guest_alias else ''],
            cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout.splitlines()[-1])

    def test_stock_client_configures_without_server_backend_or_test_path(self):
        report = self.probe()
        self.assertEqual(report['state']['camera_mouse'], 'enabled')
        self.assertEqual(report['state']['spell_loading'], 'fast')
        self.assertEqual(report['state']['display_loading'], 'yield')
        self.assertEqual(report['state']['boat_mode'], 'profile')
        self.assertEqual(report['registry_calls'], 1)
        self.assertNotIn('client_spellbook', report['origins'])

    def apply_patch(self):
        engine = types.SimpleNamespace(work=self.work, profile='custom',
                                       cancel=threading.Event(), server_running=lambda: False)
        with patch.object(client_spellbook, 'BASE_SHA256', self.original_hash):
            result = client_spellbook.mutate(engine, 'client_spellbook_apply', {
                'revision': self.original_hash, 'confirm_apply': True})
        self.assertTrue(result['patched'])

    def test_patched_client_runs_real_protected_backup_recognition_from_staged_files(self):
        self.apply_patch()
        report = self.probe(patched=True)
        self.assertEqual(report['state']['camera_mouse'], 'enabled')
        self.assertEqual(report['state']['spell_loading'], 'fast')
        self.assertEqual(report['state']['display_loading'], 'yield')
        self.assertEqual(report['state']['boat_mode'], 'profile')
        self.assertEqual(Path(report['origins']['client_spellbook']), self.stage / 'client_spellbook.py')

    def test_patched_client_keeps_optional_hooks_through_verified_guest_bind_alias(self):
        self.apply_patch()
        guest = self.root / 'guest-client'
        guest.mkdir()
        # A host hardlink emulates the inode identity of the actual Android
        # PRoot /client => /work/client/current bind; this is not a PRoot test.
        for name in ('eqgame.exe', 'dinput8.dll'):
            os.link(self.client / name, guest / name)
        self.assertTrue(self.exe.samefile(guest / 'eqgame.exe'))
        report = self.probe(patched=True, guest_alias=guest)
        self.assertEqual(report['state']['camera_mouse'], 'enabled')
        self.assertEqual(report['state']['spell_loading'], 'fast')
        self.assertEqual(report['state']['display_loading'], 'yield')
        self.assertEqual(report['state']['boat_mode'], 'profile')

    def test_identical_copy_at_guest_alias_cannot_borrow_other_clients_patch_proof(self):
        self.apply_patch()
        guest = self.root / 'unrelated-client'
        guest.mkdir()
        for name in ('eqgame.exe', 'dinput8.dll'):
            shutil.copyfile(self.client / name, guest / name)
        self.assertEqual(self.exe.read_bytes(), (guest / 'eqgame.exe').read_bytes())
        self.assertFalse(self.exe.samefile(guest / 'eqgame.exe'))
        report = self.probe(patched=True, guest_alias=guest)
        for name in ('camera_mouse', 'spell_loading', 'display_loading', 'boat_mode'):
            self.assertEqual(report['state'][name], 'unsupported_executable')

    def test_unsupported_client_disables_optional_hooks_without_fatal_import(self):
        self.exe.write_bytes(b'Unrecognized client executable: continue without optional hooks')
        report = self.probe()
        for name in ('camera_mouse', 'spell_loading', 'display_loading', 'boat_mode'):
            self.assertEqual(report['state'][name], 'unsupported_executable')
        self.assertEqual(report['env']['TRASC_EQ_CAMERA_MOUSE_V2'], '0')
        self.assertEqual(report['env']['TRASC_EQ_LOAD_V2'], 'off')
        self.assertEqual(report['env']['TRASC_EQ_DISPLAY_V1'], 'off')
        self.assertEqual(report['env']['TRASC_EQ_BOATS_V2'], 'off')
        self.assertEqual(Path(report['origins']['client_spellbook']), self.stage / 'client_spellbook.py')

    def test_traditional_and_takp_keep_their_own_launch_paths(self):
        # Prove the new Custom dependency is not required by the other profiles,
        # even with a different executable and no spellbook module available.
        (self.stage / 'client_spellbook.py').unlink()
        self.exe.write_bytes(b'Another profile executable')
        traditional = self.probe('traditional')
        self.assertEqual(traditional['state']['camera_mouse'], 'off')
        self.assertEqual(traditional['state']['spell_loading'], 'off')
        self.assertEqual(traditional['state']['boat_mode'], 'off')
        self.assertNotIn('client_spellbook', traditional['origins'])
        takp = self.probe('takp')
        self.assertEqual(takp['state']['camera_mouse'], 'takp_eqw')
        self.assertEqual(takp['state']['spell_loading'], 'off')
        self.assertEqual(takp['state']['boat_mode'], 'off')
        self.assertEqual(takp['registry_calls'], 0)
        self.assertNotIn('client_spellbook', takp['origins'])


if __name__ == '__main__':
    unittest.main()
