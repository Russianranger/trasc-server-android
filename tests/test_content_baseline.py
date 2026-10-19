"""Future imports establish verifiable baselines without certifying remote HEAD."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine
import content_baseline as baseline
import traditional_content
import takp_runtime
import update_checklist


class ContentBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root / 'custom')

    def archive(self, engine, contents, name='content.zip'):
        output = engine.work / 'incoming' / name
        with zipfile.ZipFile(output, 'w') as archive:
            for path, value in contents.items():
                archive.writestr(path, value)
        return name

    def maps(self, contents=None):
        return self.engine.import_maps({'file': self.archive(self.engine, contents or {
            'repo/maps/base/qeynos.map': 'map1', 'repo/maps/nav/qeynos.nav': 'navigation'})})

    def test_new_map_import_baseline_matches_and_does_not_claim_remote_latest(self):
        self.maps()
        row = update_checklist._maps(self.engine)
        self.assertEqual(row['state'], 'current')
        self.assertEqual(row['counts']['matching'], 2)
        self.assertIn('remote freshness is not checked', row['detail'])
        self.assertTrue((self.engine.work / 'maps' / baseline.NAME).is_file())
        self.assertFalse((self.engine.work / 'run/maps-import-pending.json').exists())
        # Inspection cannot modify any game file or receipt.
        before = {p: p.read_bytes() for p in self.engine.work.rglob('*') if p.is_file()}
        update_checklist._maps(self.engine)
        self.assertEqual(before, {p: p.read_bytes() for p in self.engine.work.rglob('*') if p.is_file()})

    def test_map_changes_missing_files_and_preserved_additions_are_distinguished(self):
        self.maps()
        (self.engine.work / 'maps/base/local.map').write_text('keep local addition')
        row = update_checklist._maps(self.engine)
        self.assertEqual(row['state'], 'current')
        self.assertEqual(row['counts']['runtime_only'], 1)
        (self.engine.work / 'maps/base/qeynos.map').write_text('edited')
        (self.engine.work / 'maps/nav/qeynos.nav').unlink()
        row = update_checklist._maps(self.engine)
        self.assertEqual(row['state'], 'attention')
        self.assertEqual(row['counts']['changed'], 1)
        self.assertEqual(row['counts']['new'], 1)

    def test_legacy_or_tampered_evidence_never_becomes_current(self):
        self.maps()
        marker = self.engine.work / 'maps' / baseline.MAPS_MARKER
        value = json.loads(marker.read_text())
        value['commit'] = 'b' * 40
        marker.write_text(json.dumps(value))
        self.assertEqual(update_checklist._maps(self.engine)['state'], 'review')
        (self.engine.work / 'maps' / baseline.NAME).unlink()
        self.assertEqual(update_checklist._maps(self.engine)['state'], 'review')

    def test_receipts_from_another_world_are_rejected(self):
        self.maps()
        traditional = Engine(self.root / 'traditional', 'traditional')
        shutil.copytree(self.engine.work / 'maps', traditional.work / 'maps', dirs_exist_ok=True)
        self.assertEqual(update_checklist._maps(traditional)['state'], 'review')

    def test_cancelled_map_preparation_retains_active_files_and_prior_backups(self):
        self.maps()
        current = self.engine.work / 'maps'
        (current / 'base/local-one.map').write_text('local one')
        (current / 'base/local-two.map').write_text('local two')
        before = {p.relative_to(current): p.read_bytes() for p in current.rglob('*') if p.is_file()}
        copied = shutil.copy2
        def cancel_after_copy(source, target, *args, **kwargs):
            result = copied(source, target, *args, **kwargs)
            self.engine.cancel.set()
            return result
        with patch('content_baseline.shutil.copy2', side_effect=cancel_after_copy):
            with self.assertRaisesRegex(ValueError, 'cancel'):
                self.maps({'base/qeynos.map': 'updated map'})
        self.engine.cancel.clear()
        self.assertEqual(before, {p.relative_to(current): p.read_bytes() for p in current.rglob('*') if p.is_file()})
        self.assertFalse((self.engine.work / baseline.MAPS_PENDING).exists())
        changed = self.maps({'base/qeynos.map': 'updated map'})
        backup = self.engine.work / changed['previous_files']
        self.assertEqual((backup / 'base/qeynos.map').read_text(), 'map1')
        self.assertEqual((current / 'base/local-one.map').read_text(), 'local one')
        again = self.maps({'base/qeynos.map': 'updated again'})
        self.assertNotEqual(changed['previous_files'], again['previous_files'])
        self.assertEqual((backup / 'base/qeynos.map').read_text(), 'map1')
        self.assertEqual((self.engine.work / again['previous_files'] / 'base/qeynos.map').read_text(), 'updated map')

    def test_activation_error_restores_the_complete_previous_directory(self):
        self.maps()
        original = baseline.os.replace
        def fail_activation(source, target):
            if Path(source).name == 'prepared' and Path(target) == self.engine.work / 'maps':
                raise OSError('activation denied')
            return original(source, target)
        with patch('content_baseline.os.replace', side_effect=fail_activation):
            with self.assertRaisesRegex(OSError, 'activation denied'):
                self.maps({'base/qeynos.map': 'updated'})
        self.assertEqual((self.engine.work / 'maps/base/qeynos.map').read_text(), 'map1')
        self.assertEqual(update_checklist._maps(self.engine)['state'], 'current')
        self.assertFalse((self.engine.work / baseline.MAPS_PENDING).exists())

    def test_engine_startup_recovers_interruption_between_directory_renames(self):
        self.maps()
        current = self.engine.work / 'maps'
        marker = json.loads((current / baseline.MAPS_MARKER).read_text())
        backup = self.engine.work / 'backups/maps-before-import' / ('a' * 16)
        current.rename(backup)
        prepared = self.engine.work / ('maps-import-' + 'a' * 8) / 'prepared'
        prepared.mkdir(parents=True)
        (prepared / 'incomplete.map').write_text('never activated')
        (self.engine.work / baseline.MAPS_PENDING).write_text(json.dumps({'format': 1,
            'profile': 'custom', 'kind': 'maps', 'previous': True,
            'prepared': str(prepared.relative_to(self.engine.work)),
            'backup': str(backup.relative_to(self.engine.work)),
            'baseline_sha256': marker['baseline_sha256']}))
        restarted = Engine(self.engine.work)
        self.assertEqual((restarted.work / 'maps/base/qeynos.map').read_text(), 'map1')
        self.assertFalse(prepared.parent.exists())
        self.assertFalse((restarted.work / baseline.MAPS_PENDING).exists())

    def test_restart_after_activation_keeps_new_maps_and_original_backup(self):
        self.maps()
        update = self.maps({'base/qeynos.map': 'new map'})
        current = self.engine.work / 'maps'
        marker = json.loads((current / baseline.MAPS_MARKER).read_text())
        stage = self.engine.work / ('maps-import-' + 'b' * 8)
        stage.mkdir()
        (stage / 'unpacked-readme.txt').write_text('discardable staging')
        (self.engine.work / baseline.MAPS_PENDING).write_text(json.dumps({'format': 1,
            'profile': 'custom', 'kind': 'maps', 'previous': True,
            'prepared': str((stage / 'prepared').relative_to(self.engine.work)),
            'backup': update['previous_files'], 'baseline_sha256': marker['baseline_sha256']}))
        restarted = Engine(self.engine.work)
        self.assertEqual((restarted.work / 'maps/base/qeynos.map').read_text(), 'new map')
        self.assertEqual((restarted.work / update['previous_files'] / 'base/qeynos.map').read_text(), 'map1')
        self.assertFalse(stage.exists())
        self.assertFalse((restarted.work / baseline.MAPS_PENDING).exists())

    def test_map_symlink_cannot_write_another_profile(self):
        other = self.root / 'traditional/maps'
        other.mkdir(parents=True)
        shutil.rmtree(self.engine.work / 'maps')
        (self.engine.work / 'maps').symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            self.maps()
        self.assertEqual(list(other.iterdir()), [])

    def test_traditional_quests_helpers_share_one_import_baseline(self):
        engine = Engine(self.root / 'traditional', 'traditional')
        content = {'quests/qeynos/player.lua': 'quest', 'quests/plugins/helper.pl': 'plugin',
                   'quests/lua_modules/helper.lua': 'lua'}
        traditional_content.install(engine, {'kind': 'quests', 'file': self.archive(engine, content)})
        rows = {row['id']: row for row in update_checklist._independent_content(engine)}
        for key in ('quests', 'plugins', 'lua_modules'):
            self.assertEqual(rows[key]['state'], 'current', rows[key])
            self.assertEqual(rows[key]['counts']['matching'], 1)
        (engine.work / 'server/quests/plugins/helper.pl').write_text('local plugin edit')
        rows = {row['id']: row for row in update_checklist._independent_content(engine)}
        self.assertEqual(rows['plugins']['state'], 'attention')
        self.assertEqual(rows['quests']['state'], 'current')

    def test_traditional_replacement_backups_keep_matching_receipts(self):
        engine = Engine(self.root / 'traditional', 'traditional')
        def install(value, replace=False):
            return traditional_content.install(engine, {'kind': 'quests', 'replace': replace,
                'file': self.archive(engine, {'quests/qeynos/player.lua': value})})
        install('old quest')
        result = install('new quest', True)
        target = engine.work / 'server/quests'
        old = engine.work / result['backup']
        old_marker = json.loads((old / traditional_content.MARKER).read_text())
        self.assertEqual(baseline.inspect(engine, old, 'quests', old_marker)['counts']['matching'], 1)
        # Swapping only a stale receipt cannot approve the newer files.
        shutil.copy2(old / traditional_content.MARKER, target / traditional_content.MARKER)
        row = update_checklist._independent_content(engine)[0]
        self.assertEqual(row['state'], 'review')
        # A coherent older directory + both matching receipts is truthful again.
        shutil.rmtree(target)
        shutil.copytree(old, target)
        self.assertEqual(update_checklist._independent_content(engine)[0]['state'], 'current')

    def test_takp_maps_and_quests_become_verifiable_after_explicit_import(self):
        engine = Engine(self.root / 'takp', 'takp')
        takp_runtime.import_content(engine, {'kind': 'maps', 'file': self.archive(engine, {'maps/qeynos.map': 'flat map'})})
        self.assertEqual(update_checklist._maps(engine)['state'], 'current')
        takp_runtime.import_content(engine, {'kind': 'quests', 'file': self.archive(engine, {
            'quests/global/global_player.lua': 'quest', 'quests/lua_modules/helper.lua': 'helper'})})
        rows = {row['id']: row for row in update_checklist._independent_content(engine)}
        self.assertEqual(rows['quests']['state'], 'current')
        self.assertEqual(rows['lua_modules']['state'], 'current')
        self.assertEqual(rows['plugins']['state'], 'not_applicable')
        (engine.work / 'server/quests/lua_modules/helper.lua').unlink()
        rows = {row['id']: row for row in update_checklist._independent_content(engine)}
        self.assertEqual(rows['lua_modules']['state'], 'attention')

    def test_cancellation_stops_hashing_before_content_activation(self):
        engine = Engine(self.root / 'traditional', 'traditional')
        name = self.archive(engine, {'quests/qeynos/player.lua': 'quest'})
        engine.cancel.set()
        with self.assertRaisesRegex(ValueError, 'cancel'):
            traditional_content.install(engine, {'kind': 'quests', 'file': name})
        self.assertFalse((engine.work / 'server/quests').exists())


if __name__ == '__main__':
    unittest.main()
