"""Activation, schema and startup failures for the Traditional runtime adapter.

Uses real binary-manifest validation with tiny ARM64 ELF fixtures. The separate
native CI test executes the actual server, MariaDB and encrypted login protocol.
"""
import contextlib
import hashlib
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
import modern_bot_bridge
from test_traditional_build import arm_elf, loader_command


class TraditionalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = Engine(Path(self.tmp.name) / 'traditional', 'traditional')
        self.custom = Engine(Path(self.tmp.name) / 'custom')
        self.engine.config['database_imported'] = True
        self.versions = (9328, 0, 0)
        self.migrated_versions = (9328, 0, 0)
        self.columns = {table: set(columns) for table, columns in runtime.SCHEMA.items()}
        self.queries, self.commands = [], []
        self.backups = []
        self.expansion_rule_count = 1
        self.invalid_expansion_values = 0
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
        if query == runtime.BOT_MIGRATION_9055_SQL:
            self.columns['bot_data'].add('expansion_bitmask')
        if query == "SELECT COUNT(*) FROM rule_values WHERE rule_name='Bots:BotExpansionSettings';":
            return 'COUNT(*)\n' + str(self.expansion_rule_count) + '\n'
        if query.startswith('SELECT COUNT(*) FROM (SELECT COALESCE('):
            return 'COUNT(*)\n' + str(self.invalid_expansion_values) + '\n'
        return ''

    def run_command(self, command, **kwargs):
        self.commands.append((command, kwargs))
        if len(command) > 1 and command[1] == 'database:updates':
            self.versions = self.migrated_versions

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

    def bot_schema(self, missing=('expansion_bitmask',)):
        self.versions = self.migrated_versions = (9328, 9055, 0)
        self.columns['bot_data'] = set(runtime.BOT_DATA_COLUMNS) - set(missing)
        self.columns['bot_settings'] = set(runtime.BOT_SETTINGS_COLUMNS)

    def test_deployment_replays_exact_native_9055_after_backup_and_verifies_columns(self):
        self.bot_schema()
        result = self.deployed()
        self.assertTrue(result['deployed'])
        self.assertEqual(self.queries.count(runtime.BOT_MIGRATION_9055_SQL), 1)
        self.assertEqual(hashlib.sha256(runtime.BOT_MIGRATION_9055_SQL.encode()).hexdigest(),
                         'f068977fda01564eb2a2620d208f0abd369fc9cbfc5cf38d9db87b0fa652e85d')
        self.assertEqual(self.versions, (9328, 9055, 0))
        self.assertEqual(len(self.backups), 1)
        marker = json.loads((self.engine.work / 'run/traditional-bot-schema.json').read_text())
        self.assertTrue(marker['completed'])
        self.assertEqual(marker['backup'], self.backups[0])
        self.assertEqual(marker['source_revision'], build.REVISION)
        self.assertTrue(any('`expansion_bitmask`' in query and 'LIMIT 0' in query for query in self.queries))
        runtime.qualify_database(self.engine)
        self.assertEqual(self.queries.count(runtime.BOT_MIGRATION_9055_SQL), 1)

    def test_ordinary_qualification_does_not_repair_and_other_omissions_are_rejected(self):
        self.bot_schema()
        with self.assertRaisesRegex(ValueError, 'deploy the current qualified build'):
            runtime.qualify_database(self.engine)
        self.assertNotIn(runtime.BOT_MIGRATION_9055_SQL, self.queries)
        self.columns['bot_data'].remove('owner_id')
        with self.assertRaisesRegex(ValueError, 'schema mismatch.*owner_id'):
            self.deployed()
        self.assertNotIn(runtime.BOT_MIGRATION_9055_SQL, self.queries)

    def test_schema_repair_requires_backup_current_receipt_and_exact_pin(self):
        self.bot_schema()
        with self.assertRaisesRegex(ValueError, 'completed full database backup'):
            runtime.qualify_database(self.engine, migrate=True, binary_root='server/bin.staged')
        backup = self.backup({})['file']
        with self.assertRaisesRegex(ValueError, 'exact qualified Traditional source pin'):
            runtime.qualify_bot_schema(self.engine, self.versions, repair=True,
                                      database_backup=backup, source_revision='other')
        with self.assertRaisesRegex(ValueError, 'missing or invalid'):
            runtime.qualify_bot_schema(self.engine, self.versions, repair=True,
                                      database_backup='backups/missing.sql.gz', source_revision=build.REVISION)
        path = self.engine.work / 'server/bin.staged/build-info.json'
        info = json.loads(path.read_text())
        atomic_json(path, dict(info, recipe_identity='0' * 64))
        with self.assertRaisesRegex(ValueError, 'qualified runtime and build recipe'):
            runtime.qualify_database(self.engine, migrate=True, binary_root='server/bin.staged', database_backup=backup)
        self.assertNotIn(runtime.BOT_MIGRATION_9055_SQL, self.queries)
        self.assertFalse((self.engine.work / 'run/traditional-bot-schema.json').exists())

    def test_partial_native_repair_keeps_backup_marker_and_blocks_false_add_only_success(self):
        self.bot_schema()
        real = self.mysql
        def partial(query, **kwargs):
            result = real(query, **kwargs)
            if query == runtime.BOT_MIGRATION_9055_SQL:
                raise ValueError('Native UPDATE failed after committed ADD')
            return result
        with patch.object(self.engine, 'mysql', side_effect=partial):
            with self.assertRaisesRegex(ValueError, 'UPDATE failed'):
                self.deployed()
        self.assertIn('expansion_bitmask', self.columns['bot_data'])
        marker = json.loads((self.engine.work / 'run/traditional-bot-schema.json').read_text())
        self.assertFalse(marker['completed'])
        self.assertTrue((self.engine.work / marker['backup']).is_file())
        self.assertTrue((self.engine.work / 'server/bin.staged').exists())
        for action in (lambda: runtime.qualify_database(self.engine), self.deployed):
            with self.assertRaisesRegex(ValueError, 'repair was interrupted.*Restore'):
                action()
        self.assertEqual(len(self.backups), 1)
        # A real database restore/import rotates the epoch. Its database is
        # verified afresh rather than blocked by a journal from the replaced DB.
        self.engine.config['bot_database_epoch'] = 'b' * 32
        runtime.qualify_database(self.engine)

    def test_native_repair_duplicate_rules_null_values_and_invalid_versions_fail_before_ddl(self):
        self.bot_schema()
        backup = self.backup({})['file']
        self.expansion_rule_count = 2
        with self.assertRaisesRegex(ValueError, 'unambiguous.*no schema was changed'):
            runtime.qualify_bot_schema(self.engine, self.versions, repair=True,
                                      database_backup=backup, source_revision=build.REVISION)
        self.expansion_rule_count = 1
        self.invalid_expansion_values = 1
        with self.assertRaisesRegex(ValueError, 'NULL or invalid.*no schema was changed'):
            runtime.qualify_bot_schema(self.engine, self.versions, repair=True,
                                      database_backup=backup, source_revision=build.REVISION)
        for versions in (None, (), (9328,), (9328, True, 0), (9328, '9055', 0)):
            with self.assertRaisesRegex(ValueError, 'versions are invalid'):
                runtime.qualify_bot_schema(self.engine, versions, repair=True,
                                          database_backup=backup, source_revision=build.REVISION)
        self.assertNotIn(runtime.BOT_MIGRATION_9055_SQL, self.queries)
        self.assertNotIn('expansion_bitmask', self.columns['bot_data'])
        self.assertFalse((self.engine.work / 'run/traditional-bot-schema.json').exists())

    def test_repair_fsyncs_backup_and_journal_before_ddl_and_closes_on_sync_failure(self):
        self.bot_schema()
        backup = self.backup({})['file']
        real_sync = runtime._fsync_directory
        events = []
        def synced(path):
            events.append(('sync', Path(path).name))
            real_sync(path)
        real_mysql = self.mysql
        def queried(query, **kwargs):
            if query == runtime.BOT_MIGRATION_9055_SQL:
                events.append(('native', 'ddl'))
            return real_mysql(query, **kwargs)
        with patch('traditional_runtime._fsync_directory', side_effect=synced), \
             patch.object(self.engine, 'mysql', side_effect=queried):
            runtime.qualify_bot_schema(self.engine, self.versions, repair=True,
                                      database_backup=backup, source_revision=build.REVISION)
        self.assertEqual(events, [('sync', 'backups'), ('sync', 'run'), ('native', 'ddl'), ('sync', 'run')])
        self.columns['bot_data'].remove('expansion_bitmask')
        with patch('traditional_runtime._fsync_directory', side_effect=OSError('directory sync failed')):
            with self.assertRaisesRegex(OSError, 'directory sync failed'):
                runtime.qualify_bot_schema(self.engine, self.versions, repair=True,
                                          database_backup=backup, source_revision=build.REVISION)
        self.assertEqual(self.queries.count(runtime.BOT_MIGRATION_9055_SQL), 1)

    def test_completed_journal_sync_failure_retains_fail_closed_pending_marker(self):
        self.bot_schema()
        backup = self.backup({})['file']
        real_sync = runtime._fsync_directory
        calls = 0
        def sync_failure(path):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('completed journal sync failed')
            real_sync(path)
        with patch('traditional_runtime._fsync_directory', side_effect=sync_failure):
            with self.assertRaisesRegex(OSError, 'completed journal sync failed'):
                runtime.qualify_bot_schema(self.engine, self.versions, repair=True,
                                          database_backup=backup, source_revision=build.REVISION)
        marker = json.loads((self.engine.work / 'run/traditional-bot-schema.json').read_text())
        self.assertFalse(marker['completed'])
        self.assertIn('expansion_bitmask', self.columns['bot_data'])
        with self.assertRaisesRegex(ValueError, 'repair was interrupted'):
            runtime.qualify_database(self.engine)

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

    def legacy_deployed(self):
        self.deployed()
        path=self.engine.work/'server/bin/build-info.json'
        info=json.loads(path.read_text())
        info['recipe_identity']=runtime.LEGACY_0621_RECIPE_IDENTITY
        info.pop('bot_creation_bridge',None)
        atomic_json(path,info)
        return path,info

    def test_exact_0621_deployed_recipe_keeps_normal_start_without_offline_bots(self):
        _,info=self.legacy_deployed()
        self.assertEqual(runtime._record(self.engine)['recipe_identity'],runtime.LEGACY_0621_RECIPE_IDENTITY)
        state=runtime.status(self.engine,{})
        self.assertTrue(state['deployed_valid'])
        self.assertTrue(state['start_allowed'])
        with self.assertRaisesRegex(ValueError,'Rebuild and deploy'):
            modern_bot_bridge._deployed(self.engine,{'profile':'traditional','deployment':info})

    def test_legacy_recipe_never_qualifies_a_new_staged_deployment(self):
        path=self.engine.work/'server/bin.staged/build-info.json'
        info=json.loads(path.read_text()); info['recipe_identity']=runtime.LEGACY_0621_RECIPE_IDENTITY
        atomic_json(path,info)
        with self.assertRaisesRegex(ValueError,'qualified runtime and build recipe'):
            self.deployed()
        self.assertFalse((self.engine.work/'server/bin').exists())
        self.assertFalse(self.backups)

    def test_legacy_acceptance_still_checks_verifier_runtime_manifest_report_and_binaries(self):
        path,info=self.legacy_deployed()
        original_sha=build._sha
        def changed_verifier(value,*args,**kwargs):
            return '0'*64 if Path(value).name=='traditional_verify.py' else original_sha(value,*args,**kwargs)
        with patch('traditional_build._sha',side_effect=changed_verifier):
            self.assertFalse(runtime.status(self.engine,{})['start_allowed'])
        with patch('traditional_build._runtime',return_value={'ready':True,'identity':'b'*64}):
            self.assertFalse(runtime.status(self.engine,{})['start_allowed'])
        atomic_json(path,dict(info,recipe_identity='0'*64))
        self.assertFalse(runtime.status(self.engine,{})['start_allowed'])
        atomic_json(path,dict(info,bot_creation_bridge={'format':1,'profile':'traditional'}))
        self.assertFalse(runtime.status(self.engine,{})['start_allowed'])
        atomic_json(path,info)
        binary=self.engine.work/'server/bin/zone'
        original=binary.read_bytes(); binary.write_bytes(original+b'changed')
        self.assertFalse(runtime.status(self.engine,{})['start_allowed'])
        binary.write_bytes(original)
        report=self.engine.work/'server/bin/verification.json'
        data=json.loads(report.read_text()); data['architecture']='other'; atomic_json(report,data)
        self.assertFalse(runtime.status(self.engine,{})['start_allowed'])

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
