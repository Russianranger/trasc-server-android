"""Cross-layer world-entry repair; synthetic executable, no game assets."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine
import client_compatibility
import client_connection
import client_launch_compatibility as launch
import client_mouse
import client_spellbook
from test_client_spellbook import synthetic

NEW = '38a4f2ad03203cb2f12dbff26fd613cc47efba0a'
OLD = '8f6ca0795f424a7b4eab750ff38fc6473d48375c'


class WorldEntryIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.engine = Engine.__new__(Engine)
        self.engine.work = self.work
        self.engine.profile = 'custom'
        self.engine.cancel = threading.Event()
        self.engine.processes = {}
        self.engine.current_job = None
        self.client = self.work / 'client/current'
        self.client.mkdir(parents=True)
        self.exe = self.client / 'eqgame.exe'
        self.original = synthetic(False)
        self.exe.write_bytes(self.original)
        self.exe.chmod(0o755)
        (self.client / 'trasc-client.json').write_text(json.dumps({
            'executable': 'eqgame.exe', 'imported': True, 'imported_at': 10}))
        (self.client / 'eqhost.txt').write_bytes(client_connection.default_host('custom'))
        base = patch.object(client_spellbook, 'BASE_SHA256', hashlib.sha256(self.original).hexdigest())
        base.start()
        self.addCleanup(base.stop)
        source = self.work / 'sources/current'
        header = source / client_compatibility.HEADER
        header.parent.mkdir(parents=True)
        header.write_text('const int SPELLBOOK_SIZE = 1440;\n')
        (source / 'trasc-source.json').write_text(json.dumps({'commit': NEW}))

    def deploy_server(self, revision=NEW):
        deployed = self.work / 'server/bin'
        deployed.mkdir(parents=True, exist_ok=True)
        raw = bytearray(128)
        raw[:5] = b'\x7fELF\x02'
        raw[18:20] = (183).to_bytes(2, 'little')
        (deployed / 'zone').write_bytes(raw)
        (deployed / 'build-info.json').write_text(json.dumps({
            'source': {'commit': revision}, 'zone_sha256': hashlib.sha256(raw).hexdigest()}))

    def apply(self):
        return self.engine.dispatch('client_spellbook_apply', {
            '__profile': 'custom', 'revision': hashlib.sha256(self.exe.read_bytes()).hexdigest(),
            'confirm_apply': True})

    def preflight(self, **options):
        return self.engine.dispatch('client_spellbook_preflight', {'__profile': self.engine.profile, **options})

    def test_world_entry_mismatches_are_advisory_and_never_refuse_launch(self):
        self.deploy_server()
        self.assertTrue(self.preflight()['allowed'])
        self.assertTrue(self.preflight()['requires_confirmation'])
        self.assertIn('1,440', self.preflight()['message'])
        result = self.apply()
        self.assertTrue(result['patched'])
        self.assertEqual(result['requirements']['required_spellbook_slots'], 1440)
        self.assertIn('freshness', result['dll'])
        self.assertTrue(self.preflight()['allowed'])
        self.assertTrue(self.preflight()['requires_confirmation'])
        self.assertIn('Compile dinput8.dll', self.preflight()['message'])
        with patch.object(launch.client_dll, 'compiler_status', return_value={
                'freshness': {'installed': {'state': 'current'}}}):
            self.assertTrue(self.preflight()['allowed'])
            self.assertFalse(self.preflight()['requires_confirmation'])
            self.assertTrue(self.preflight(native_dinput8=False)['allowed'])
            self.assertTrue(self.preflight(native_dinput8=False)['requires_confirmation'])
        self.assertTrue(self.preflight(mode='compiler')['allowed'])
        self.assertFalse(self.preflight(mode='compiler')['requires_confirmation'])

    def test_new_selected_source_does_not_break_verified_old_server(self):
        self.deploy_server(OLD)
        state = self.engine.dispatch('client_spellbook_status', {'__profile': 'custom'})
        self.assertEqual(state['requirements']['selected_spellbook_slots'], 1440)
        self.assertEqual(state['requirements']['required_spellbook_slots'], 720)
        self.assertFalse(state['can_apply'])
        with self.assertRaisesRegex(ValueError, '720-slot'):
            self.apply()
        self.assertEqual(self.exe.read_bytes(), self.original)
        self.assertTrue(self.preflight()['allowed'])
        self.assertFalse(self.preflight()['requires_confirmation'])

    def test_unknown_remote_and_other_profiles_are_not_inferred_from_selected_source(self):
        self.assertTrue(self.preflight()['allowed'])
        self.assertTrue(self.preflight()['warnings'])
        self.assertFalse(self.preflight()['requires_confirmation'])
        self.deploy_server()
        (self.client / 'eqhost.txt').write_text('[LoginServer]\nHost=192.0.2.44:5999\n')
        self.assertTrue(self.preflight()['allowed'])
        self.assertFalse(self.preflight()['requires_confirmation'])
        for profile in ('traditional', 'takp'):
            self.engine.profile = profile
            self.assertTrue(self.preflight()['allowed'])
            self.assertFalse(self.preflight()['requires_confirmation'])
            with self.assertRaisesRegex(ValueError, 'profile changed'):
                self.engine.dispatch('client_spellbook_apply', {'__profile': 'custom'})
        self.assertEqual(self.exe.read_bytes(), self.original)

    def test_legacy_laa_controls_cannot_undo_expanded_profile(self):
        client_connection.mutate(self.engine, 'client_4gb_apply', {
            'revision': hashlib.sha256(self.exe.read_bytes()).hexdigest()})
        self.apply()
        expanded = self.exe.read_bytes()
        state = client_connection.status(self.engine)['patch']
        self.assertTrue(state['can_apply'])
        self.assertFalse(state['can_restore'])
        with self.assertRaisesRegex(ValueError, '1,440-slot'):
            client_connection.mutate(self.engine, 'client_4gb_restore', {'revision': state['revision']})
        client_connection.mutate(self.engine, 'client_4gb_apply', {'revision': state['revision']})
        self.assertEqual(self.exe.read_bytes(), expanded)

    def test_expanded_client_against_older_server_warns_without_modifying_files(self):
        self.apply()
        self.deploy_server(OLD)
        before = self.exe.read_bytes()
        checked = self.preflight()
        self.assertTrue(checked['allowed'])
        self.assertTrue(checked['requires_confirmation'])
        self.assertIn('720-slot', checked['message'])
        self.assertIn('continue', checked['message'])
        self.assertEqual(self.exe.read_bytes(), before)

    def test_verified_expanded_executable_keeps_existing_adapters(self):
        self.apply()
        (self.client / 'dinput8.dll').write_bytes((' '.join((client_mouse.MARKER,
            client_mouse.LOADING_MARKER, client_mouse.DISPLAY_MARKER, client_mouse.BOAT_MARKER))).encode())
        request = {'profile': 'custom', 'mode': 'client', 'executable': 'eqgame.exe',
                   'native_dinput8': True, 'mouse_warp': True, 'fast_spell_parse': True,
                   'reduce_load_pauses': True, 'boat_mode': 'profile'}
        self.assertEqual(client_mouse.launch_mode(request, self.client), 'enabled')
        self.assertEqual(client_mouse.loading_mode(request, self.client), 'fast')
        self.assertEqual(client_mouse.display_mode(request, self.client), 'yield')
        self.assertEqual(client_mouse.boat_mode(request, self.client), 'profile')
        modified = bytearray(self.exe.read_bytes())
        modified[-1] ^= 1
        self.exe.write_bytes(modified)
        self.assertEqual(client_mouse.launch_mode(request, self.client), 'unsupported_executable')

    def test_native_compatibility_is_reviewed_without_a_runtime_refusal(self):
        java = Path(__file__).resolve().parents[1] / 'app/src/main/java/io/github/russianranger/trasc'
        runtime = (java / 'ClientRuntime.java').read_text()
        activity = (java / 'MainActivity.java').read_text()
        self.assertNotIn('client_spellbook_preflight', runtime)
        self.assertLess(activity.index('if(!reviewClientLaunch(profile,args)'),
                        activity.index('result=clientRuntime.start(args)'))
        for operation in ('client_spellbook_apply', 'client_spellbook_restore'):
            self.assertIn('"' + operation + '"', runtime)
            self.assertIn('case "' + operation + '"', activity)


if __name__ == '__main__':
    unittest.main()
