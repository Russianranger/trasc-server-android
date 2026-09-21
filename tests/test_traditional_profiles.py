import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine, atomic_json
import traditional_content as content


class TraditionalProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.custom = Engine(self.root / 'custom')
        self.engine = Engine(self.root / 'traditional', 'traditional')

    def tearDown(self):
        self.tmp.cleanup()

    def archive(self, files):
        archive = self.engine.work / 'incoming/content.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            for name, value in files.items():
                out.writestr(name, value)
        return archive.name

    def install(self, kind, files, **args):
        return self.engine.dispatch('import_content', dict(kind=kind, file=self.archive(files), **args))

    def test_defaults_and_settings_identity(self):
        self.assertEqual(self.custom.config['database'], 'triune')
        self.assertEqual(self.engine.config['database'], 'peq')
        self.assertEqual(self.engine.config['repo'], 'https://github.com/EQEmu/EQEmu')
        before = self.custom.config_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'different world'):
            Engine(self.custom.work, 'traditional')
        self.assertEqual(before, self.custom.config_path.read_bytes())
        self.assertNotEqual(self.custom.config['db_password'], self.engine.config['db_password'])

    def test_all_components_are_separate_and_custom_unchanged(self):
        custom_file = self.custom.work / 'server/keep.txt'
        custom_file.write_text('live world')
        files = {'projecteq-master/qeynos/guard.pl': 'quest', 'projecteq-master/global/global_player.lua': 'global',
                 'projecteq-master/plugins/check.pl': 'plugin', 'projecteq-master/lua_modules/utils.lua': 'module'}
        for kind in ('quests', 'plugins', 'lua_modules'):
            self.install(kind, files)
        self.install('assets', {'assets-master/opcodes/patch_RoF2.conf': 'OP_Unknown=0x0000'})
        self.assertEqual((self.engine.work / 'server/quests/qeynos/guard.pl').read_text(), 'quest')
        self.assertFalse((self.engine.work / 'server/quests/plugins').exists())
        self.assertEqual((self.engine.work / 'server/plugins/check.pl').read_text(), 'plugin')
        self.assertEqual((self.engine.work / 'server/lua_modules/utils.lua').read_text(), 'module')
        self.assertTrue(all(x['imported'] for x in content.status(self.engine)['components'].values()))
        self.assertFalse(content.status(self.engine)['compilation_ready'])
        self.assertEqual(custom_file.read_text(), 'live world')

    def test_replacement_preserves_old_directory(self):
        self.install('quests', {'qeynos/guard.pl': 'original'})
        with self.assertRaisesRegex(ValueError, 'Replace'):
            self.install('quests', {'qeynos/guard.pl': 'new'})
        result = self.install('quests', {'qeynos/guard.pl': 'new'}, replace=True)
        self.assertEqual((self.engine.work / result['backup'] / 'qeynos/guard.pl').read_text(), 'original')
        self.assertEqual((self.engine.work / 'server/quests/qeynos/guard.pl').read_text(), 'new')
        self.assertEqual(len(result['component']['archive_sha256']), 64)

    def test_failed_activation_rolls_back(self):
        self.install('plugins', {'plugins/check.pl': 'old'})
        original = os.replace
        def replace(src, dest):
            if Path(src).name == 'prepared': raise OSError('simulated storage failure')
            return original(src, dest)
        with patch('traditional_content.os.replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'storage failure'):
                self.install('plugins', {'plugins/check.pl': 'new'}, replace=True)
        self.assertEqual((self.engine.work / 'server/plugins/check.pl').read_text(), 'old')
        self.assertFalse((self.engine.work / 'run/content-plugins.json').exists())

    def test_restart_recovers_interrupted_swap(self):
        self.install('plugins', {'plugins/check.pl': 'old'})
        backup = self.engine.work / 'backups/content/plugins-recovery'
        backup.parent.mkdir(parents=True, exist_ok=True)
        os.replace(self.engine.work / 'server/plugins', backup)
        atomic_json(self.engine.work / 'run/content-plugins.json', {'id': 'pending', 'backup': backup.name, 'previous': True})
        content.recover(self.engine)
        self.assertEqual((self.engine.work / 'server/plugins/check.pl').read_text(), 'old')

    def test_archive_validation_and_cancel_preserve_current(self):
        self.install('plugins', {'plugins/check.pl': 'old'})
        for files in ({'plugins/../../escape.pl': 'bad'}, {'readme.txt': 'wrong content'}):
            with self.assertRaises(ValueError): self.install('plugins', files, replace=True)
        self.engine.cancel.set()
        with self.assertRaises(ValueError): self.install('plugins', {'plugins/check.pl': 'new'}, replace=True)
        self.assertEqual((self.engine.work / 'server/plugins/check.pl').read_text(), 'old')
        self.assertFalse((self.root / 'escape.pl').exists())

    def test_cross_profile_and_unvalidated_builds_are_blocked(self):
        for op in ('build', 'deploy', 'rollback', 'start', 'prepare_client', 'export_client',
                   'ferry_service_apply', 'boat_trial_apply', 'client_dll_deploy', 'client_addons_copy', 'apply_spell_test', 'fix_nektulos'):
            with self.subTest(op=op), self.assertRaises(ValueError): self.engine.dispatch(op, {})
        with self.assertRaisesRegex(ValueError, 'profile changed'):
            self.engine.dispatch('state', {'__profile': 'custom'})
        with self.assertRaisesRegex(ValueError, 'Traditional EQEmu profile'):
            self.custom.dispatch('import_content', {'kind': 'plugins'})

    def test_running_server_and_symlink_targets_rejected(self):
        with patch.object(self.engine, 'server_running', return_value=True):
            with self.assertRaisesRegex(ValueError, 'Stop the server'):
                self.install('plugins', {'plugins/check.pl': 'new'})
        (self.engine.work / 'server/plugins').symlink_to(self.custom.work / 'server', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            self.install('plugins', {'plugins/check.pl': 'new'})
        self.assertFalse((self.custom.work / 'server/check.pl').exists())

    def test_split_seed_order_and_single_database_reset(self):
        work = self.engine.work
        (work / 'incoming/world.sql').write_text('CREATE DATABASE wrong;\nUSE wrong;\nCREATE TABLE zone(id int);\n')
        (work / 'incoming/players.sql').write_text('CREATE TABLE account(id int);\n')
        executed = []
        queries = []
        def mysql(query, **kwargs):
            queries.append(query)
            return '\n'.join(('account','character_data','rule_values','rule_sets','variables','launcher'))
        with patch.object(self.engine, 'ensure_db'), patch.object(self.engine, 'mysql', side_effect=mysql), patch.object(self.engine, 'run', side_effect=lambda cmd, **kw: executed.append(kw['input_file'].read_text())):
            self.engine.dispatch('import_database', {'selection': 'incoming/world.sql', 'selections': ['incoming/world.sql','incoming/players.sql']})
        self.assertEqual(len(executed), 1)
        self.assertLess(executed[0].index('zone'), executed[0].index('account'))
        self.assertNotIn('USE wrong', executed[0])
        self.assertNotIn('CREATE DATABASE wrong', executed[0])
        self.assertEqual(sum('DROP DATABASE' in q for q in queries), 1)
        self.assertTrue(self.engine.config['database_imported'])


if __name__ == '__main__': unittest.main()
