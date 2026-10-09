"""TAKP isolation, content rollback, login secrets and two-file export policy."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine
import takp_build
import takp_runtime
from integration_takp_runtime import npc_spawn_ids


class TakpServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root / 'takp', 'takp')
        self.custom = Engine(self.root / 'custom')

    def archive(self, files):
        target = self.engine.work / 'incoming/content.zip'
        with zipfile.ZipFile(target, 'w') as archive:
            for name, value in files.items():
                archive.writestr(name, value)
        return target.name

    def test_independent_defaults_and_cross_profile_rejection(self):
        self.assertEqual(self.engine.config['database'], 'takp')
        self.assertEqual(self.engine.config['login_port'], 6000)
        self.assertEqual(self.engine.config['repo'], takp_build.REPOSITORY)
        before = self.custom.config_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'different world'):
            Engine(self.custom.work, 'takp')
        self.assertEqual(before, self.custom.config_path.read_bytes())
        for operation in ('takp_setup', 'takp_initialize_database', 'takp_create_account'):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'TAKP World'):
                self.custom.dispatch(operation, {})
        for operation in ('client_dll_deploy', 'ferry_service_apply', 'apply_spell_test', 'player_restore', 'spire_search'):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                self.engine.dispatch(operation, {})

    def test_invalid_source_import_leaves_current_source_and_settings(self):
        current = self.engine.work / 'sources/current'
        current.mkdir()
        (current / 'keep.txt').write_text('existing source')
        before = self.engine.config_path.read_bytes()
        name = self.archive({'Server/CMakeLists.txt': 'project(no)', 'Server/zone/main.cpp': 'wrong fork'})
        with self.assertRaisesRegex(ValueError, 'complete TAKP'):
            self.engine.import_source({'file': name})
        self.assertEqual((current / 'keep.txt').read_text(), 'existing source')
        self.assertEqual(before, self.engine.config_path.read_bytes())

    def test_flat_maps_import_and_failed_replacement_restore_old_files(self):
        name = self.archive({'Maps/qeynos.map': b'original', 'Maps/qeynos.wtr': b'water'})
        self.engine.import_maps({'file': name})
        path = self.engine.work / 'maps/qeynos.map'
        self.assertEqual(path.read_bytes(), b'original')
        self.assertFalse((self.engine.work / 'maps/base').exists())
        name = self.archive({'Maps/qeynos.map': b'new'})
        original = takp_runtime.os.replace
        def fail(source, destination):
            if Path(source).name == 'prepared':
                raise OSError('storage failure')
            return original(source, destination)
        with patch('takp_runtime.os.replace', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'storage failure'):
                self.engine.import_maps({'file': name, 'replace': True})
        self.assertEqual(path.read_bytes(), b'original')
        self.assertFalse((self.engine.work / 'run/takp-maps-swap.json').exists())

    def test_quests_include_lua_helpers_and_source_is_preserved(self):
        custom_file = self.custom.work / 'server/custom.txt'
        custom_file.write_text('custom data')
        name = self.archive({'quests/qeynos/guard.lua': 'quest', 'quests/global/global_player.lua': 'global',
                             'quests/lua_modules/utils.lua': 'module'})
        self.engine.dispatch('import_content', {'kind': 'quests', 'file': name})
        self.assertTrue(takp_runtime.status(self.engine)['quests_ready'])
        self.assertEqual(custom_file.read_text(), 'custom data')
        name = self.archive({'quests/global/global_player.lua': 'missing modules'})
        with self.assertRaisesRegex(ValueError, 'lua_modules'):
            self.engine.dispatch('import_content', {'kind': 'quests', 'file': name, 'replace': True})
        self.assertEqual((self.engine.work / 'server/quests/lua_modules/utils.lua').read_text(), 'module')

    def test_database_initialization_refuses_existing_database_without_sql(self):
        self.engine.config['database_imported'] = True
        before = self.engine.config_path.read_bytes()
        with patch.object(self.engine, 'mysql') as mysql:
            with self.assertRaisesRegex(ValueError, 'never replaces'):
                self.engine.dispatch('takp_initialize_database', {})
        mysql.assert_not_called()
        self.assertEqual(before, self.engine.config_path.read_bytes())

    def test_explicit_account_uses_salted_sha1_and_never_stores_password(self):
        queries = []
        def mysql(query, **kwargs):
            queries.append(query)
            if query.startswith('SELECT COUNT'):
                return 'COUNT(*)\n1\n'
            return 'LoginServerID\n'
        password = 'fixture-password'
        with patch('takp_runtime.verify_database'), patch.object(self.engine, 'mysql', side_effect=mysql):
            result = self.engine.dispatch('takp_create_account', {'username': 'localplayer', 'password': password})
        inserts = [query for query in queries if query.startswith('INSERT')]
        self.assertEqual(len(inserts), 1)
        expected = hashlib.sha1((password + self.engine.config['server_key']).encode()).hexdigest()
        self.assertIn(expected, inserts[0])
        self.assertIn('creationIP,ForumName', inserts[0])
        self.assertNotIn(password, ''.join(queries))
        self.assertNotIn(password, json.dumps(result))
        self.assertNotIn(password, self.engine.config_path.read_text())

    def test_local_account_replacement_is_refused(self):
        with patch('takp_runtime.verify_database'), patch.object(self.engine, 'mysql', return_value='LoginServerID\n5\n') as mysql:
            with self.assertRaisesRegex(ValueError, 'left unchanged'):
                self.engine.dispatch('takp_create_account', {'username': 'existing', 'password': 'replacement'})
        self.assertEqual(mysql.call_count, 1)

    def test_config_distinguishes_legacy_udp_and_world_tcp_and_shared_path(self):
        self.engine.write_config()
        server = json.loads((self.engine.work / 'server/eqemu_config.json').read_text())['server']
        login = json.loads((self.engine.work / 'server/login.json').read_text())
        self.assertEqual(server['world']['loginserver']['port'], 5998)
        self.assertEqual(login['client_configuration']['listen_port'], 5998)
        self.assertEqual(login['Old']['port'], 6000)
        self.assertEqual(login['database']['salt'], self.engine.config['server_key'])
        self.assertFalse(login['account']['auto_create_accounts'])
        self.assertTrue(server['directories']['shared_memory'].endswith('/'))
        self.assertEqual(server['files']['chat_opcodes'], 'chat_opcodes.conf')
        self.assertFalse(server['auto_database_updates'])

    def test_spawn_logging_is_best_effort_and_preserves_existing_detail(self):
        levels = {15: 0, 23: 2, 1: 0, 20: 0}
        queries = []
        def mysql(query):
            queries.append(query)
            self.assertEqual(query, 'UPDATE logsys_categories SET log_to_file=GREATEST(log_to_file,1) '
                                   'WHERE log_category_id IN (15,23);')
            for category in (15, 23):
                levels[category] = max(levels[category], 1)
        with patch.object(self.engine, 'mysql', side_effect=mysql):
            takp_runtime.enable_spawn_logging(self.engine)
            takp_runtime.enable_spawn_logging(self.engine)
        self.assertEqual(levels, {15: 1, 23: 2, 1: 0, 20: 0})
        self.assertEqual(len(queries), 2)
        with patch.object(self.engine, 'mysql', side_effect=ValueError('diagnostic database unavailable')):
            takp_runtime.enable_spawn_logging(self.engine)
        with patch.object(self.custom, 'mysql') as mysql:
            with self.assertRaisesRegex(ValueError, 'TAKP World'):
                takp_runtime.enable_spawn_logging(self.custom)
            mysql.assert_not_called()

    def test_qualification_counts_zone_file_creation_events_without_console_suffix(self):
        log_root = self.engine.work / 'server/logs/zone'
        log_root.mkdir(parents=True)
        # Pinned server's actual file format, including a duplicate event and a
        # loaded spawnentry count, must not overstate distinct NPC creations.
        line = '[10-09-2026 15:56:39] [Zone] [Spawns] [spawn2.cpp::Process:295] '
        creation = line + 'Spawn2 [368298]: Group [223442] spawned [Gerot_Kastane000] ([75004]) at ([671.000], [799.000], [-122.100]).\n'
        (log_root / 'paineel_port_7118_83.log').write_text(creation + creation + line + 'Loaded [117] spawn entries\n')
        (log_root / 'qeynos_port_7117_83.log').write_text(creation.replace('368298', '1000'))
        self.assertEqual(npc_spawn_ids(self.engine.work / 'server/logs', 'paineel'), {368298})

    def test_export_uses_only_two_unfiltered_files(self):
        data = {'spells_us.txt': b'1^spell\n50000^full spell\n', 'SkillCaps.txt': b'1^0^1^5^0\n'}
        def export(*args, **kwargs):
            folder = self.engine.work / 'server/export'
            for name, contents in data.items():
                (folder / name).write_bytes(contents)
            (folder / 'BaseData.txt').write_text('unrelated stale export')
        with patch('takp_runtime.require_client_data'), patch.object(self.engine, 'run', side_effect=export):
            result = self.engine.export_client({})
        self.assertEqual(result['files'], list(takp_runtime.CLIENT_FILES))
        self.assertFalse(result['filter_applied'])
        with zipfile.ZipFile(self.engine.work / result['file']) as archive:
            self.assertEqual(set(archive.namelist()), set(data) | {'client-data-export.json'})
            self.assertEqual(archive.read('spells_us.txt'), data['spells_us.txt'])


if __name__ == '__main__':
    unittest.main()
