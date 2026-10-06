"""Activation, schema and startup failures for the Traditional runtime adapter.

Uses real binary-manifest validation with tiny ARM64 ELF fixtures. The separate
native CI test executes the actual server, MariaDB and encrypted login protocol.
"""
import contextlib
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
import traditional_build as build
import traditional_content as content
import traditional_runtime as runtime
import traditional_verify as verify
from test_traditional_build import arm_elf, loader_command


class TraditionalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = Engine(Path(self.tmp.name) / 'traditional', 'traditional')
        self.custom = Engine(Path(self.tmp.name) / 'custom')
        self.engine.config['database_imported'] = True
        self.versions = (9328, 0, 0)
        self.columns = {table: set(columns) for table, columns in runtime.SCHEMA.items()}
        self.queries, self.commands = [], []
        self.backups = []
        self.addCleanup(patch.stopall)
        patch('traditional_build._runtime', return_value={'ready': True, 'identity': 'a' * 64}).start()
        patch('traditional_build.status', side_effect=self.build_status).start()
        patch.object(self.engine, 'ensure_db').start()
        patch.object(self.engine, 'mysql', side_effect=self.mysql).start()
        patch.object(self.engine, 'run', side_effect=self.run_command).start()
        patch.object(self.engine, 'backup_database', side_effect=self.backup).start()
        self.install('quests', {'qeynos/guard.pl': 'quest', 'plugins/check.pl': 'sub CheckHandin {}',
                                'lua_modules/utils.lua': 'function CheckHandin() end'})
        files = {'assets/' + name: 'OP_Test=0x0000' for name in runtime.REQUIRED_ASSETS}
        self.install('assets', files)
        (self.engine.work / 'maps/base').mkdir(parents=True)
        self.stage()

    def install(self, kind, files):
        archive = self.engine.work / 'incoming' / (kind + '.zip')
        with zipfile.ZipFile(archive, 'w') as output:
            for name, text in files.items():
                output.writestr(name, text)
        content.install(self.engine, {'kind': kind, 'file': archive.name})

    def stage(self, generation=1):
        stage = self.engine.work / 'server/bin.staged'
        stage.mkdir(exist_ok=True)
        for binary in build.BINARIES:
            arm_elf(stage / binary)
            with (stage / binary).open('ab') as output:
                output.write(bytes([generation]))
        evidence = self.engine.work / 'run' / ('verification-' + str(generation))
        with patch('traditional_verify._command', side_effect=loader_command):
            report = verify.verify(stage, evidence)
        atomic_json(stage / 'verification.json', report)
        atomic_json(stage / 'build-info.json', {'format': 1, 'recipe': build.RECIPE,
                    'recipe_identity': build._recipe_identity(), 'runtime_identity': 'a' * 64,
                    'verification_sha256': build._digest(report), 'compile_only': True,
                    'generation': generation})

    def build_status(self, _engine):
        return {'staged_valid': (self.engine.work / 'server/bin.staged').exists(),
                'staged_message': 'Compile the source first', 'build_allowed': True}

    def mysql(self, query, **_kwargs):
        self.queries.append(query)
        # Engine.mysql uses --batch --raw and includes column names.
        if query == 'SHOW TABLES;':
            return 'Tables_in_peq\n' + '\n'.join(self.columns) + '\n'
        if query.startswith('SHOW COLUMNS FROM '):
            table = query.split('`')[1]
            return 'Field\tType\tNull\tKey\tDefault\tExtra\n' + ''.join(column + '\tint\tYES\t\tNULL\t\n' for column in self.columns[table])
        if query.startswith('SELECT version,'):
            return 'version\tbots_version\tcustom_version\n' + '\t'.join(map(str, self.versions)) + '\n'
        return ''

    def run_command(self, command, **kwargs):
        self.commands.append((command, kwargs))
        if len(command) > 1 and command[1] == 'database:updates':
            self.versions = (9328, 0, 0)

    def backup(self, _args):
        name = 'backups/pre-deploy-' + str(len(self.backups)) + '.sql.gz'
        (self.engine.work / name).write_bytes(b'preserved database fixture')
        self.backups.append(name)
        return {'file': name}

    def deployed(self):
        return self.engine.dispatch('deploy', {})

    def test_old_compile_manifest_deploys_without_rebuild_and_custom_is_unchanged(self):
        before = self.custom.config_path.read_bytes()
        stage_info = (self.engine.work / 'server/bin.staged/build-info.json').read_bytes()
        result = self.deployed()
        self.assertTrue(result['deployed'])
        self.assertEqual((self.engine.work / 'server/bin/build-info.json').read_bytes(), stage_info)
        self.assertEqual(self.custom.config_path.read_bytes(), before)
        cfg = json.loads((self.engine.work / 'server/eqemu_config.json').read_text())['server']
        self.assertEqual(cfg['database']['db'], 'peq')
        self.assertEqual(cfg['directories']['plugins'], 'quests/plugins')
        self.assertEqual(cfg['directories']['lua_modules'], 'quests/lua_modules')
        self.assertEqual(cfg['directories']['patches'], 'assets/patches')
        self.assertEqual(cfg['directories']['opcodes'], 'assets/opcodes')
        self.assertEqual(cfg['files']['mail_opcodes'], 'assets/opcodes/mail_opcodes.conf')
        self.assertFalse(cfg['auto_database_updates'])
        self.assertTrue(cfg['disable_config_checks'])
        login = json.loads((self.engine.work / 'server/login.json').read_text())
        self.assertEqual(login['database']['user'], 'trasc')
        self.assertEqual(login['security']['mode'], 14)
        self.assertTrue(login['account']['auto_create_accounts'])
        self.assertEqual(login['general']['default_loginserver_name'], 'local')
        self.assertEqual(self.commands[0][0][1:], ['database:updates', '--skip-backup'])
        self.assertEqual(len(self.backups), 1)
        self.assertTrue(any('WHERE NOT EXISTS' in query and 'login_world_servers' in query for query in self.queries))
        state = runtime.status(self.engine, {})
        self.assertTrue(state['deployed_valid'])
        self.assertTrue(state['start_allowed'])
        with patch.object(self.engine, 'server_running', return_value=True):
            self.assertTrue(runtime.status(self.engine, {})['start_allowed'])
            with self.assertRaisesRegex(ValueError, 'already running'):
                self.engine.start({})

    def test_schema_or_assets_fail_before_backup_and_activation(self):
        del self.columns['login_accounts']
        with self.assertRaisesRegex(ValueError, 'complete PEQ.*login_accounts'):
            self.deployed()
        self.assertFalse(self.backups)
        self.columns['login_accounts'] = set(runtime.SCHEMA['login_accounts'])
        self.columns['login_world_servers'].remove('note')
        with self.assertRaisesRegex(ValueError, 'schema mismatch.*note'):
            self.deployed()
        (self.engine.work / 'server/assets/opcodes/login_opcodes_sod.conf').unlink()
        with self.assertRaisesRegex(ValueError, 'complete server assets'):
            self.deployed()
        self.assertTrue((self.engine.work / 'server/bin.staged').exists())
        self.assertFalse((self.engine.work / 'server/bin').exists())

    def test_newer_database_and_incompatible_helpers_are_rejected(self):
        self.versions = (9329, 0, 0)
        with self.assertRaisesRegex(ValueError, 'newer than'):
            self.deployed()
        self.versions = (9328, 0, 0)
        (self.engine.work / 'server/quests/lua_modules/utils.lua').write_text('-- old helper')
        self.assertIn('CheckHandin', runtime.status(self.engine, {})['message'])
        with self.assertRaisesRegex(ValueError, 'CheckHandin'):
            self.deployed()

    def test_migration_error_restores_config_and_preserves_staged_binaries(self):
        cfg = self.engine.work / 'server/eqemu_config.json'
        cfg.write_text('{"server":{"existing":"keep"}}')
        before = cfg.read_bytes()
        with patch.object(self.engine, 'run', side_effect=ValueError('migration failed')):
            with self.assertRaisesRegex(ValueError, 'migration failed'):
                self.deployed()
        self.assertEqual(cfg.read_bytes(), before)
        self.assertFalse((self.engine.work / 'server/login.json').exists())
        self.assertTrue((self.engine.work / 'server/bin.staged/world').exists())
        self.assertFalse((self.engine.work / 'run/traditional-deploy.json').exists())
        self.assertTrue((self.engine.work / self.backups[0]).is_file())

    def test_failed_activation_preserves_current_and_previous_builds(self):
        self.deployed()
        self.stage(2)
        self.deployed()
        current = (self.engine.work / 'server/bin/world').read_bytes()
        previous = (self.engine.work / 'server/bin.previous/world').read_bytes()
        before = (self.engine.work / 'server/eqemu_config.json').read_bytes()
        self.stage(3)
        original = os.replace
        def rename(source, destination):
            if Path(source).name == 'bin.staged' and Path(destination).name == 'bin':
                raise OSError('activation failed')
            return original(source, destination)
        with patch('traditional_runtime.os.replace', side_effect=rename):
            with self.assertRaisesRegex(OSError, 'activation failed'):
                self.deployed()
        self.assertEqual((self.engine.work / 'server/bin/world').read_bytes(), current)
        self.assertEqual((self.engine.work / 'server/bin.previous/world').read_bytes(), previous)
        self.assertEqual((self.engine.work / 'server/eqemu_config.json').read_bytes(), before)
        self.assertTrue((self.engine.work / 'server/bin.staged/world').is_file())

    def test_changed_binary_or_runtime_fails_integrity_gate(self):
        self.deployed()
        binary = self.engine.work / 'server/bin/zone'
        with binary.open('ab') as output:
            output.write(b'changed')
        self.assertFalse(runtime.status(self.engine, {})['deployed_valid'])
        with self.assertRaises(ValueError):
            self.engine.dispatch('export_client', {})
        with patch('traditional_build._runtime', return_value={'ready': True, 'identity': 'b' * 64}):
            self.assertFalse(runtime.status(self.engine, {})['start_allowed'])

    def test_recovery_rejects_traversal_or_symlink_without_touching_other_world(self):
        other = self.custom.work / 'keep.json'
        other.write_text('keep')
        journal = self.engine.work / 'run/traditional-deploy.json'
        atomic_json(journal, {'format': 1, 'id': 'a' * 24, 'backup': '../custom',
                             'had_current': False, 'had_previous': False,
                             'configs': {'eqemu_config.json': True, 'login.json': False}})
        with self.assertRaisesRegex(ValueError, 'Invalid.*journal'):
            runtime.recover(self.engine)
        self.assertTrue(journal.exists())
        self.assertEqual(other.read_text(), 'keep')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            runtime._path(self.engine, 'backups/../../../custom/keep.json')
        journal.unlink()
        (self.engine.work / 'server/eqemu_config.json.new').symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            self.engine.write_config()
        self.assertEqual(other.read_text(), 'keep')

    def test_rollback_and_interrupted_rollback_preserve_qualified_generations(self):
        self.deployed()
        self.stage(2)
        self.deployed()
        result = self.engine.dispatch('rollback', {})
        self.assertIn('Previous verified', result['message'])
        self.assertEqual(json.loads((self.engine.work / 'server/bin/build-info.json').read_text())['generation'], 1)
        os.replace(self.engine.work / 'server/bin', self.engine.work / 'server/bin.swap')
        runtime.recover(self.engine)
        self.assertTrue(runtime.status(self.engine, {})['deployed_valid'])
        self.assertEqual(json.loads((self.engine.work / 'server/bin/build-info.json').read_text())['generation'], 1)

    def test_start_waits_for_real_zone_children_and_stops_on_failure(self):
        self.deployed()
        self.engine.config['workers'] = 1
        class Process:
            pid = 123
            def poll(self): return None
        def launch(name, *args):
            self.engine.processes[name] = Process()
            if name == 'eqlaunch':
                (self.engine.work / 'server/logs/zone-dynamic_01.log').write_text('Entering sleep mode\n')
            return self.engine.processes[name]
        with patch.object(self.engine, 'launch', side_effect=launch), \
             patch('traditional_runtime.socket.create_connection', return_value=contextlib.nullcontext()), \
             patch('traditional_runtime.time.sleep'), \
             patch('traditional_runtime._zone_children', return_value=(456,)) as children, \
             patch('ferry_service.boot') as ferry:
            result = self.engine.dispatch('start', {})
        self.assertIn('dynamic zones ready', result['message'])
        self.assertEqual(children.call_count, 2)
        ferry.assert_not_called()
        self.engine.processes.clear()
        with patch.object(self.engine, 'launch', side_effect=launch), \
             patch.object(self.engine, 'stop') as stopped, \
             patch('traditional_runtime.socket.create_connection', return_value=contextlib.nullcontext()), \
             patch('traditional_runtime.time.sleep'), \
             patch('traditional_runtime._zone_children', return_value=()):
            with self.assertRaisesRegex(ValueError, 'zone workers did not reach sleep mode'):
                self.engine.dispatch('start', {})
        stopped.assert_called_once_with({})

    def test_proot_loader_zone_children_and_recovery_flags(self):
        proc = Path(self.tmp.name) / 'proc'
        child = proc / '456'
        child.mkdir(parents=True)
        (child / 'stat').write_text('456 (ld-linux-aarch64) S 123 0 0')
        (child / 'cmdline').write_bytes(b'/lib/ld-linux-aarch64.so.1\0--argv0\0zone\0/work/server/bin/zone\0dynamic_01\0')
        self.assertEqual(runtime._zone_children(123, proc), (456,))
        self.assertEqual(runtime._zone_children(124, proc), ())
        self.deployed()
        self.engine.traditional_recovery_error = 'incomplete build stage'
        self.assertFalse(runtime.status(self.engine, {})['start_allowed'])
        self.assertFalse(runtime.status(self.engine, {})['client_data_allowed'])
        self.assertIn('recovery', runtime.status(self.engine, {})['message'])
        self.engine.traditional_recovery_error = None
        direct = self.engine.dispatch('traditional_status', {})
        self.assertTrue(direct['deployment']['deployed_valid'])


if __name__ == '__main__':
    unittest.main()
