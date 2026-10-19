"""Checklist evidence must be live, isolated, conservative and read-only."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine, BINARIES
import source_updates
import update_checklist as checklist


class ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name) / 'custom'
        self.work.mkdir()
        self.engine = types.SimpleNamespace(work=self.work, profile='custom',
            config={'database_imported': True}, current_job={}, check_cancel=lambda: None)
        self.write('sources/current/trasc-source.json', {'type': 'github', 'commit': 'a' * 40,
                   'repo': 'https://github.com/example/server', 'ref': 'main', 'imported': 1})
        self.write('sources/current/Release-NMS-Server/world/main.cpp', 'code')
        self.write('sources/current/Release-NMS-Server/utils/patches/patch_RoF2.conf', 'opcodes')
        self.write('sources/current/Release-NMS-Quests/qeynos/player.lua', 'quest')
        self.write('sources/current/Release-NMS-Quests/lua_modules/helper.lua', 'lua')
        self.write('sources/current/Release-NMS-Plugins/helper.pl', 'plugin')
        self.write('server/eqemu_config.json', {'server': {'directories': {'quests': 'quests',
                   'plugins': 'quests/plugins', 'lua_modules': 'quests/lua_modules'}}})
        self.write('database/player.ibd', 'player data remains untouched')
        self.write('client/current/eqgame.exe', 'client executable remains untouched')
        self.write('server/quests/local.lua', 'local custom quest retained')

    def write(self, relative, value):
        path = self.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, dict):
            value = json.dumps(value)
        path.write_bytes(value.encode() if isinstance(value, str) else value)
        return path

    def rows(self):
        return {row['id']: row for row in checklist.scan(self.engine)['rows']}

    def install_scripts(self):
        self.write('server/quests/qeynos/player.lua', 'quest')
        self.write('server/quests/lua_modules/helper.lua', 'lua')
        self.write('server/quests/plugins/helper.pl', 'plugin')
        self.write('server/patch_RoF2.conf', 'opcodes')

    def install_build(self, directory='server/bin'):
        hashes = {}
        for name in BINARIES:
            self.write(directory + '/' + name, ('binary:' + name).encode())
            hashes[name] = hashlib.sha256(('binary:' + name).encode()).hexdigest()
        source = json.loads((self.work / 'sources/current/trasc-source.json').read_text())
        digest = source_updates.identity(source_updates.inventory(self.work / 'sources/current'))
        self.write(directory + '/build-info.json', {'source': source, 'built': 1,
                   'source_tree_sha256': digest, 'binaries': hashes})

    def snapshot(self):
        return {str(path.relative_to(self.work.parent)): path.read_bytes()
                for path in self.work.parent.rglob('*') if path.is_file()}

    def test_live_exact_matching_with_runtime_only_files_and_no_writes(self):
        self.install_scripts()
        self.install_build()
        before = self.snapshot()
        rows = self.rows()
        self.assertEqual(self.snapshot(), before)
        for key in ('source', 'build', 'deployed', 'quests', 'plugins', 'lua_modules', 'assets'):
            self.assertEqual(rows[key]['state'], 'current', (key, rows[key]))
        self.assertEqual(rows['quests']['counts']['runtime_only'], 1)
        for key in ('maps', 'lon', 'client_data', 'database'):
            self.assertNotEqual(rows[key]['state'], 'current')

    def test_new_source_revision_invalidates_build_even_with_identical_bytes(self):
        self.install_build()
        self.assertEqual(self.rows()['deployed']['state'], 'current')
        marker = json.loads((self.work / 'sources/current/trasc-source.json').read_text())
        marker['commit'] = 'b' * 40
        self.write('sources/current/trasc-source.json', marker)
        self.assertEqual(self.rows()['deployed']['state'], 'attention')

    def test_local_source_changes_invalidate_unchanged_revision(self):
        self.install_build()
        self.write('sources/current/Release-NMS-Server/world/main.cpp', 'edited code')
        self.assertEqual(self.rows()['deployed']['state'], 'attention')

    def test_staged_and_deployed_are_independent(self):
        self.install_build()
        self.write('sources/current/Release-NMS-Server/world/main.cpp', 'new code')
        self.install_build('server/bin.staged')
        rows = self.rows()
        self.assertEqual(rows['build']['state'], 'current')
        self.assertEqual(rows['deployed']['state'], 'attention')

    def test_changed_binary_and_legacy_or_malformed_receipts_are_never_current(self):
        self.install_build()
        self.write('server/bin/zone', 'changed')
        self.assertEqual(self.rows()['deployed']['state'], 'attention')
        for value in ({'source': {'commit': 'a' * 40}}, {'source': []}, {'source': 'bad'}, []):
            self.write('server/bin/build-info.json', json.dumps(value))
            self.assertNotEqual(self.rows()['deployed']['state'], 'current')

    def test_scan_uses_live_quest_files_and_source_not_previous_sync_status(self):
        self.install_scripts()
        self.assertEqual(self.rows()['quests']['state'], 'current')
        self.write('server/quests/qeynos/player.lua', 'local edit')
        self.write('sources/current/Release-NMS-Quests/qeynos/new.lua', 'new source script')
        with patch('quest_sync.status', return_value={'current': True}):
            rows = self.rows()
        self.assertEqual(rows['quests']['state'], 'attention')
        self.assertEqual(rows['quests']['counts']['changed'], 1)
        self.assertEqual(rows['quests']['counts']['new'], 1)
        self.assertEqual((self.work / 'server/quests/qeynos/player.lua').read_text(), 'local edit')

    def test_local_conflicts_use_last_sync_baseline_without_overwriting_files(self):
        import custom_deployment
        self.install_scripts()
        target = self.work / 'server/quests/qeynos/player.lua'
        manifest = custom_deployment._manifest_path(self.engine, 'quest_sync')
        self.write(str(manifest.relative_to(self.work)), {'entries': {
            str(target): {'sha256': hashlib.sha256(b'quest').hexdigest()}}})
        self.write('sources/current/Release-NMS-Quests/qeynos/player.lua', 'upstream edit')
        counts = self.rows()['quests']['counts']
        self.assertEqual((counts['changed'], counts['conflicts'], counts['untracked_changes']), (1, 0, 0))
        self.write('server/quests/qeynos/player.lua', 'my local edit')
        before = self.snapshot()
        row = self.rows()['quests']
        self.assertEqual(row['condition'], 'modified')
        self.assertEqual(row['counts']['conflicts'], 1)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_script_baseline_does_not_claim_zero_local_modifications(self):
        self.install_scripts()
        self.write('server/quests/qeynos/player.lua', 'custom script')
        row = self.rows()['quests']
        self.assertEqual(row['counts']['untracked_changes'], 1)
        self.assertIn('no prior baseline', row['detail'])

    def test_component_conditions_and_failed_scan_are_independent(self):
        self.install_scripts()
        self.install_build()
        self.write('sources/current/Release-NMS-Server/world/main.cpp', 'new source')
        rows = self.rows()
        self.assertEqual(rows['deployed']['condition'], 'outdated')
        self.assertEqual(rows['maps']['condition'], 'missing')
        self.assertEqual(rows['quests']['condition'], 'current')

        with patch.object(checklist, '_maps', side_effect=ValueError('Map read failed')):
            rows = self.rows()
        self.assertEqual(rows['maps']['condition'], 'review')
        self.assertEqual(rows['quests']['condition'], 'current')

    def test_compatibility_reuses_nonblocking_preflight_and_actual_dll_option(self):
        with patch('client_launch_compatibility.preflight', return_value={
                'allowed': True, 'requirements': {'known_deployed': True}, 'warnings': []}) as preflight:
            result = checklist.scan(self.engine, {'client_options': {'native_dinput8': False}})
        row = next(row for row in result['rows'] if row['id'] == 'compatibility')
        self.assertEqual(row['state'], 'current')
        self.assertIs(preflight.call_args.args[1]['native_dinput8'], False)
        with patch('client_launch_compatibility.preflight', return_value={
                'allowed': True, 'requires_confirmation': True, 'warnings': ['Known mismatch']}) as preflight:
            row = self.rows()['compatibility']
        self.assertEqual(row['state'], 'review')
        self.assertTrue(row['requires_confirmation'])
        self.assertIn('Launch remains available', row['detail'])
        self.engine.profile = 'takp'
        with patch('client_launch_compatibility.preflight', side_effect=AssertionError('Custom only')):
            self.assertEqual(self.rows()['compatibility']['state'], 'review')

    def test_absent_source_and_support_files_cannot_be_current(self):
        shutil.rmtree(self.work / 'sources/current')
        rows = self.rows()
        for key in ('source', 'build', 'deployed', 'quests', 'plugins', 'lua_modules', 'assets'):
            self.assertNotEqual(rows[key]['state'], 'current', key)

    def test_map_folder_or_recorded_commit_does_not_prove_freshness(self):
        self.write('maps/base/qeynos.map', 'old map')
        self.assertEqual(self.rows()['maps']['state'], 'review')
        self.engine.profile = 'takp'
        self.write('maps/qeynos.map', 'old TAKP map')
        self.write('maps/.trasc-takp-content.json', {'profile': 'takp', 'kind': 'maps',
                   'repo': 'https://github.com/example/maps', 'commit': 'b' * 40})
        self.assertEqual(self.rows()['maps']['state'], 'review')

    def test_traditional_content_receipt_is_not_live_hash_evidence(self):
        self.engine.profile = 'traditional'
        self.install_scripts()
        self.write('server/quests/.trasc-content.json', {'profile': 'traditional', 'kind': 'quests',
                   'commit': 'a' * 40, 'files': 999})
        rows = self.rows()
        for key in ('quests', 'plugins', 'lua_modules'):
            self.assertEqual(rows[key]['state'], 'review')
            self.assertEqual(rows[key]['action']['target'], 'content-git')
        self.assertEqual(rows['lon']['state'], 'not_applicable')

    def test_takp_does_not_reuse_custom_quest_or_lon_claims(self):
        self.engine.profile = 'takp'
        rows = self.rows()
        self.assertEqual(rows['plugins']['state'], 'not_applicable')
        self.assertEqual(rows['lon']['state'], 'not_applicable')
        self.assertEqual(rows['quests']['action']['target'], 'takp-content-kind')

    def test_matching_export_still_does_not_prove_database_freshness(self):
        names = ('spells_us.txt', 'dbstr_us.txt', 'SkillCaps.txt', 'BaseData.txt')
        hashes = {}
        for name in names:
            hashes[name] = hashlib.sha256(name.encode()).hexdigest()
            for root in ('server/export', 'client/current', 'client/current/Resources'):
                self.write(root + '/' + name, name)
        self.write('logs/client-data-sync.json', {'local_client_synced': True, 'sha256': hashes})
        row = self.rows()['client_data']
        self.assertEqual(row['state'], 'review')
        self.assertTrue(row['local_export_matches'])
        self.write('client/current/Resources/spells_us.txt', 'different spells')
        row = self.rows()['client_data']
        self.assertEqual(row['state'], 'attention')
        self.assertFalse(row.get('local_export_matches', False))

    def test_profile_fence_and_no_cross_profile_reads_or_writes(self):
        other = self.work.parent / 'traditional/server/quests/private.lua'
        other.parent.mkdir(parents=True)
        other.write_text('other world untouched')
        before = self.snapshot()
        self.rows()
        self.assertEqual(self.snapshot(), before)
        with self.assertRaisesRegex(ValueError, 'profile changed'):
            checklist.scan(self.engine, {'__profile': 'traditional'})
        self.engine.profile = 'invalid'
        with self.assertRaisesRegex(ValueError, 'Unknown world'):
            checklist.scan(self.engine)

    def test_symlinks_fail_closed_without_reading_other_world(self):
        other = self.work.parent / 'traditional/server/quests'
        other.mkdir(parents=True)
        (other / 'private.lua').write_text('private')
        shutil.rmtree(self.work / 'server/quests')
        (self.work / 'server/quests').symlink_to(other, target_is_directory=True)
        rows = self.rows()
        self.assertEqual(rows['quests']['state'], 'review')
        self.assertNotIn('private', json.dumps(rows))

    def test_cancellation_propagates_and_engine_dispatch_routes_scan(self):
        self.engine.check_cancel = lambda: (_ for _ in ()).throw(ValueError('Cancelled'))
        with self.assertRaisesRegex(ValueError, 'Cancelled'):
            checklist.scan(self.engine)
        self.engine.check_cancel = lambda: None
        engine = Engine.__new__(Engine)
        engine.__dict__.update(vars(self.engine))
        result = engine.dispatch('update_checklist_scan', {'__profile': 'custom'})
        self.assertTrue(result['read_only'])
        self.assertEqual(result['profile'], 'custom')

    def test_source_marker_changes_during_scan_invalidate_all_green_rows(self):
        self.install_scripts()
        self.install_build()
        assets = checklist._assets
        def changed(engine):
            marker = json.loads((self.work / 'sources/current/trasc-source.json').read_text())
            marker['commit'] = 'c' * 40
            self.write('sources/current/trasc-source.json', marker)
            return assets(engine)
        with patch.object(checklist, '_assets', side_effect=changed):
            result = checklist.scan(self.engine)
        self.assertTrue(result['source']['changed_during_scan'])
        self.assertEqual(result['summary']['current'], 0)
        self.assertEqual(result['deployed']['state'], 'review')

    def test_native_runtime_stages_scan_module(self):
        root = Path(__file__).resolve().parents[1]
        java = (root / 'app/src/main/java/io/github/russianranger/trasc/RuntimeManager.java').read_text()
        self.assertIn('"update_checklist.py"', java)


if __name__ == '__main__':
    unittest.main()
