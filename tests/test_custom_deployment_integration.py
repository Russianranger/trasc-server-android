"""Exercise Custom deployment through its real Engine boundaries.

The filesystem fixtures are isolated worlds. MariaDB is observed at the actual
subprocess boundary, so an accidental initializer, grant or seed is visible.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine
import custom_deployment as deployment


OPERATIONS = (
    'quest_sync_status', 'quest_sync_scan', 'quest_sync_files', 'quest_sync_diff',
    'quest_sync_apply', 'lon_data_status', 'lon_data_scan', 'lon_data_files',
    'lon_data_apply', 'lon_data_verify', 'custom_deployment_recover',
)


class CustomDeploymentEngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        # Skip the daemon worker, not any method under test.
        self.engine = Engine.__new__(Engine)
        self.engine.work = self.work
        self.engine.profile = 'custom'
        self.engine.config = {
            'profile': 'custom', 'database_imported': True, 'root_password': 'a' * 40,
            'db_password': 'b' * 40, 'database': 'triune', 'db_port': 13306,
            'ip': '127.0.0.1', 'server_key': 'c' * 40, 'login_port': 5999,
        }
        self.engine.config_path = self.work / 'settings.json'
        self.engine.process_lock = threading.RLock()
        self.engine.processes = {}
        self.engine.db = None
        self.engine.cancel = threading.Event()
        self.engine.current_job = None
        self.engine.command = None
        self.engine.custom_deployment_recovery_error = ''
        for name in ('run', 'logs', 'database', 'server', 'sources', 'incoming', 'backups', 'exports'):
            (self.work / name).mkdir()
        self.engine.ensure_mysql_options()

    def write(self, relative, value):
        target = self.work / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value.encode() if isinstance(value, str) else value)
        return target

    @staticmethod
    def running_process():
        process = Mock()
        process.poll.return_value = None
        return process

    def test_existing_database_readiness_runs_select_only_without_initializer(self):
        self.write('database/mysql/sentinel', b'existing system tables')
        self.write('database/players.ibd', b'player data, version 160')
        self.write('run/mysql-init.sql', b'old initializer must stay unchanged')
        self.engine.config['db_password'] = 'not needed for read-only rule inspection'
        process = self.running_process()
        with patch('engine.subprocess.Popen', return_value=process) as popen, \
                patch('engine.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '1\n', '')) as mysql, \
                patch.object(self.engine, 'run', side_effect=AssertionError('Database initializer invoked')):
            self.engine.ensure_db(existing_only=True)
        self.assertEqual(popen.call_count, 1)
        command = popen.call_args.args[0]
        self.assertEqual(command[0], 'mariadbd')
        self.assertIn('--datadir=' + str(self.work / 'database'), command)
        self.assertFalse(any(argument.startswith('--init-file') for argument in command))
        self.assertEqual(mysql.call_count, 1)
        self.assertEqual(mysql.call_args.args[0][0], 'mariadb')
        self.assertEqual(mysql.call_args.kwargs['input'], 'SELECT 1;')
        self.assertEqual((self.work / 'run/mysql-init.sql').read_bytes(), b'old initializer must stay unchanged')
        self.assertEqual((self.work / 'database/players.ibd').read_bytes(), b'player data, version 160')
        self.assertEqual((self.work / 'database/mysql/sentinel').read_bytes(), b'existing system tables')

    def test_existing_database_refuses_missing_or_unimported_world_before_processes(self):
        for imported, mysql_exists in ((True, False), (False, False), (False, True)):
            with self.subTest(imported=imported, mysql_exists=mysql_exists):
                self.engine.config['database_imported'] = imported
                if mysql_exists:
                    (self.work / 'database/mysql').mkdir(exist_ok=True)
                with patch('engine.subprocess.Popen') as popen, patch('engine.subprocess.run') as run, \
                        patch.object(self.engine, 'run') as initialize:
                    with self.assertRaisesRegex(ValueError, 'existing imported Custom database'):
                        self.engine.ensure_db(existing_only=True)
                popen.assert_not_called()
                run.assert_not_called()
                initialize.assert_not_called()
                self.assertFalse((self.work / 'run/mysql-init.sql').exists())

    def test_existing_running_database_needs_no_restart_or_credential_mutation(self):
        (self.work / 'database/mysql').mkdir()
        self.engine.db = self.running_process()
        with patch('engine.subprocess.Popen') as popen, patch('engine.subprocess.run') as run:
            self.engine.ensure_db(existing_only=True)
        popen.assert_not_called()
        run.assert_not_called()
        self.assertFalse((self.work / 'run/mysql-init.sql').exists())

    def test_regular_database_setup_still_initializes_credentials_and_application_schema(self):
        with patch('engine.subprocess.Popen', return_value=self.running_process()) as popen, \
                patch('engine.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '1\n', '')) as mysql, \
                patch.object(self.engine, 'run') as initialize:
            self.engine.ensure_db()
        self.assertEqual(initialize.call_count, 1)
        self.assertEqual(initialize.call_args.args[0][0], 'mariadb-install-db')
        self.assertIn('--init-file=' + str(self.work / 'run/mysql-init.sql'), popen.call_args.args[0])
        self.assertIn("ALTER USER 'root'@'localhost'", (self.work / 'run/mysql-init.sql').read_text())
        queries = [call.kwargs['input'] for call in mysql.call_args_list]
        self.assertEqual(queries[0], 'SELECT 1;')
        self.assertEqual(len(queries), 2)
        self.assertIn('CREATE DATABASE IF NOT EXISTS `triune`', queries[1])
        self.assertIn('GRANT ALL ON `triune`.*', queries[1])

    def test_write_config_preserves_scalar_and_array_targets_in_runtime_and_parent_config(self):
        cases = (
            {'quests': 'custom-quests', 'plugins': 'custom-quests/plugins', 'lua_modules': 'modules'},
            {'quests': 'fallback', 'plugins': 'fallback/plugins', 'lua_modules': 'fallback/modules',
             'quest_paths': ['quests-a', 'quests-b'], 'plugin_paths': ['plugins-a', 'plugins-b'],
             'lua_module_paths': ['modules-a', str(self.work / 'server/modules-b')]},
        )
        for path in ('server/eqemu_config.json', 'eqemu_config.json'):
            for directories in cases:
                with self.subTest(path=path, directories=directories):
                    for old in (self.work / 'server/eqemu_config.json', self.work / 'eqemu_config.json'):
                        old.unlink(missing_ok=True)
                    active = self.write(path, json.dumps({'server': {'directories': directories,
                                                                  'world': {'custom-setting': 'preserve'}}}))
                    before = deployment.destinations(self.engine)
                    self.engine.write_config()
                    after = deployment.destinations(self.engine)
                    for field in ('runtime', 'quests', 'quest_paths', 'plugins', 'plugin_paths', 'lua_modules', 'lua_module_paths'):
                        self.assertEqual(before[field], after[field], field)
                    actual = json.loads(active.read_text())['server']
                    for key, value in directories.items():
                        self.assertEqual(actual['directories'][key], value)
                    self.assertEqual(actual['world']['custom-setting'], 'preserve')
                    if path == 'eqemu_config.json':
                        self.assertFalse((self.work / 'server/eqemu_config.json').exists())

    def test_write_config_preserves_destinations_when_existing_config_omits_directories(self):
        self.write('server/eqemu_config.json', '{"server":{"world":{"shortname":"old"}}}')
        before = deployment.destinations(self.engine)
        self.engine.write_config()
        after = deployment.destinations(self.engine)
        for field in ('runtime', 'quests', 'quest_paths', 'plugins', 'plugin_paths', 'lua_modules', 'lua_module_paths'):
            self.assertEqual(before[field], after[field], field)

    def test_new_dispatch_actions_refuse_other_profiles_and_stale_profile_arguments(self):
        for operation in OPERATIONS:
            for profile in ('traditional', 'takp'):
                with self.subTest(operation=operation, profile=profile):
                    self.engine.profile = profile
                    with self.assertRaisesRegex(ValueError, 'TRASC Custom'):
                        self.engine.dispatch(operation, {'__profile': profile})
            self.engine.profile = 'custom'
            with self.subTest(operation=operation, profile='stale'):
                with self.assertRaisesRegex(ValueError, 'World profile changed'):
                    self.engine.dispatch(operation, {'__profile': 'traditional'})
        self.assertFalse((self.work / deployment.RECOVERY).exists())

    def test_unrecoverable_interrupted_deployment_blocks_server_and_source_mutations(self):
        journal = self.write(deployment.RECOVERY + '/journal.events', b'orphaned durable event\n')
        for operation in ('start', 'deploy', 'deploy_update', 'import_source', 'source_update_apply'):
            with self.subTest(operation=operation):
                with patch.object(self.engine, operation) as target:
                    with self.assertRaisesRegex(ValueError, 'lost its header'):
                        self.engine.dispatch(operation, {'__profile': 'custom'})
                    target.assert_not_called()
                self.assertEqual(journal.read_bytes(), b'orphaned durable event\n')

    def test_recovery_action_refuses_live_server_and_recovers_safe_empty_event(self):
        journal = self.write(deployment.RECOVERY + '/journal.events', b'')
        self.engine.processes['world'] = self.running_process()
        with self.assertRaisesRegex(ValueError, 'Stop the Custom server'):
            self.engine.dispatch('custom_deployment_recover', {'__profile': 'custom'})
        self.assertTrue(journal.exists())
        self.engine.processes.clear()
        result = self.engine.dispatch('custom_deployment_recover', {'__profile': 'custom'})
        self.assertEqual(result['profile'], 'custom')
        self.assertFalse(journal.exists())

    def test_file_manager_cannot_move_recovery_parent_or_insert_recovery_content(self):
        protected = self.write(deployment.RECOVERY + '/history/original', b'protected before-image')
        source = self.write('incoming/user-file', b'user-file')
        cases = (
            {'action': 'move', 'path': deployment.RECOVERY, 'destination': 'exports/moved-recovery'},
            {'action': 'move', 'path': 'backups', 'destination': 'exports/moved-backups'},
            {'action': 'move', 'path': str(protected.relative_to(self.work)), 'destination': 'exports/original'},
            {'action': 'copy', 'path': str(source.relative_to(self.work)),
             'destination': deployment.RECOVERY + '/injected'},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(ValueError, 'protected'):
                    self.engine.edit_file(arguments)
                self.assertEqual(protected.read_bytes(), b'protected before-image')
                self.assertEqual(source.read_bytes(), b'user-file')
                self.assertFalse((self.work / arguments['destination']).exists())

    def test_scan_and_apply_work_through_engine_dispatch_without_database_or_client_writes(self):
        self.write('sources/current/trasc-source.json', json.dumps({'type': 'github', 'commit': 'd' * 40,
            'repo': 'https://github.com/Russianranger/Triptych-Triumvirate', 'ref': 'main'}))
        self.write('sources/current/Release-NMS-Quests/qeynos/player.lua', 'return "quest"\n')
        self.write('sources/current/Release-NMS-Quests/lua_modules/module.lua', 'return "module"\n')
        self.write('sources/current/Release-NMS-Plugins/plugin.pl', '1;\n')
        self.write('server/eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'quests', 'plugins': 'quests/plugins', 'lua_modules': 'quests/lua_modules'}}}))
        sentinel = self.write('database/player-data', b'version-160 player data')
        executable = self.write('client/current/eqgame.exe', b'executable stays unchanged')
        with patch('engine.subprocess.Popen', side_effect=AssertionError('Unexpected process launch')), \
                patch.object(self.engine, 'ensure_db', side_effect=AssertionError('Unexpected database access')):
            preview = self.engine.dispatch('quest_sync_scan', {'__profile': 'custom'})
            self.assertEqual(preview['summary']['new'], 3)
            result = self.engine.dispatch('quest_sync_apply', {'__profile': 'custom', 'token': preview['token']})
            self.assertEqual(result['copied_files'], 3)
            following = self.engine.dispatch('quest_sync_scan', {'__profile': 'custom'})
            self.assertEqual(following['summary']['matching'], 3)
        self.assertEqual(sentinel.read_bytes(), b'version-160 player data')
        self.assertEqual(executable.read_bytes(), b'executable stays unchanged')
        self.assertEqual((self.work / 'server/quests/plugins/plugin.pl').read_text(), '1;\n')
        self.assertEqual((self.work / 'server/quests/lua_modules/module.lua').read_text(), 'return "module"\n')


if __name__ == '__main__':
    unittest.main()
