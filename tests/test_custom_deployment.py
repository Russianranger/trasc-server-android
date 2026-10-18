"""Real-file qualification of reviewed Custom deployment transactions."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import tracemalloc
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import custom_deployment as deployment


class Deployments(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.cancelled = False
        self.running = False
        self.engine = types.SimpleNamespace(work=self.work, profile='custom', current_job={},
            check_cancel=self.check, server_running=lambda: self.running)
        self.source = self.work / 'sources/current/Release-NMS-Quests'
        self.target = self.work / 'server/quests'
        self.source.mkdir(parents=True)
        self.target.mkdir(parents=True)
        self.config = self.work / 'server/eqemu_config.json'
        self.config.write_text(json.dumps({'server': {'directories': {'quests': 'quests',
            'plugins': 'quests/plugins', 'lua_modules': 'quests/lua_modules'}}}))
        self.marker = self.work / 'sources/current/trasc-source.json'
        self.marker.write_text(json.dumps({'type': 'github', 'commit': 'a' * 40}))

    def check(self):
        if self.cancelled:
            raise ValueError('Operation cancelled')

    def put(self, root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
        return path

    def scan(self, **kwargs):
        groups = kwargs.pop('groups', [{'name': 'quests', 'source': self.source, 'destination': self.target}])
        return deployment.preview(self.engine, 'quest_sync', groups,
                                  {'revision': 'a' * 40}, **kwargs)

    def apply(self, preview, **kwargs):
        return deployment.apply(self.engine, 'quest_sync', {'token': preview['token'], **kwargs})

    def journal(self):
        return self.work / deployment.RECOVERY / 'journal.json'

    def test_matching_tree_is_read_only_scan_and_zero_transfer(self):
        self.put(self.source, 'zone/npc.lua', 'hello')
        path = self.put(self.target, 'zone/npc.lua', 'hello')
        before = path.stat()
        result = self.scan()
        self.assertEqual(result['summary']['matching'], 1)
        self.assertEqual(result['transfer_bytes'], 0)
        self.assertEqual(path.stat().st_ino, before.st_ino)
        self.assertFalse((self.work / deployment.RECOVERY / 'quest_sync-latest.json').exists())

    def test_counts_hash_contents_and_preserves_runtime_only(self):
        self.put(self.source, 'new.lua', 'new')
        self.put(self.source, 'changed.lua', 'AAAA')
        self.put(self.target, 'changed.lua', 'BBBB')
        self.put(self.source, 'same.lua', 'same')
        self.put(self.target, 'same.lua', 'same')
        self.put(self.target, 'custom/local.lua', 'private')
        os.utime(self.source / 'changed.lua', (1000, 1000))
        os.utime(self.target / 'changed.lua', (1000, 1000))
        preview = self.scan()
        summary = preview['summary']
        self.assertEqual([summary[key] for key in ('new', 'changed', 'matching', 'runtime_only', 'errors')], [1, 1, 1, 1, 0])
        self.assertEqual((summary['new_bytes'], summary['changed_bytes']), (3, 4))
        result = self.apply(preview, confirm_overwrite=True)
        self.assertEqual((result['copied_files'], result['copied_bytes']), (2, 7))
        self.assertEqual((self.target / 'changed.lua').read_text(), 'AAAA')
        self.assertEqual((self.target / 'custom/local.lua').read_text(), 'private')
        saved = self.work / deployment.RECOVERY / 'history' / preview['token'] / '0.original'
        self.assertEqual(saved.read_text(), 'BBBB')
        self.assertEqual(stat.S_IMODE(saved.stat().st_mode), 0o400)
        manifest = deployment.status(self.engine, 'quest_sync')
        self.assertEqual(manifest['last_commit'], 'a' * 40)
        self.assertIsInstance(manifest['last_sync'], float)

    def test_confirmation_required_before_changed_file_replacement(self):
        self.put(self.source, 'one.lua', 'new')
        self.put(self.target, 'one.lua', 'old')
        preview = self.scan()
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.apply(preview)
        self.assertEqual((self.target / 'one.lua').read_text(), 'old')
        self.assertFalse(self.journal().exists())

    def test_select_new_only_leaves_changed_file_untouched(self):
        self.put(self.source, 'new.lua', 'new')
        self.put(self.source, 'changed.lua', 'newer')
        self.put(self.target, 'changed.lua', 'old')
        result = self.apply(self.scan(), include_changed=False)
        self.assertEqual(result['copied_files'], 1)
        self.assertEqual((self.target / 'changed.lua').read_text(), 'old')
        self.assertEqual((self.target / 'new.lua').read_text(), 'new')

    def test_select_changed_only_does_not_install_new_files(self):
        self.put(self.source, 'new.lua', 'new')
        self.put(self.source, 'changed.lua', 'newer')
        self.put(self.target, 'changed.lua', 'old')
        result = self.apply(self.scan(), include_new=False, confirm_overwrite=True)
        self.assertEqual(result['copied_files'], 1)
        self.assertFalse((self.target / 'new.lua').exists())

    def test_new_only_sync_tracks_later_edits_to_skipped_existing_files(self):
        self.put(self.source, 'new.lua', 'new')
        self.put(self.source, 'changed.lua', 'upstream')
        self.put(self.target, 'changed.lua', 'existing customization')
        self.apply(self.scan(), include_changed=False)
        self.assertEqual(self.scan()['summary']['conflicts'], 0)
        self.put(self.target, 'changed.lua', 'later local edit')
        preview = self.scan()
        self.assertEqual(preview['summary']['conflicts'], 1)
        # Another successful new-only operation cannot clear that conflict.
        self.apply(preview, include_changed=False)
        preview = self.scan()
        self.assertEqual(preview['summary']['conflicts'], 1)
        with self.assertRaisesRegex(ValueError, 'conflict approval'):
            self.apply(preview, confirm_overwrite=True)
        self.assertEqual((self.target / 'changed.lua').read_text(), 'later local edit')
        self.apply(preview, confirm_overwrite=True, approve_conflicts=True)
        self.assertEqual((self.target / 'changed.lua').read_text(), 'upstream')

    def test_local_edit_since_last_success_requires_separate_approval(self):
        self.put(self.source, 'npc.lua', 'upstream')
        self.apply(self.scan())
        self.put(self.target, 'npc.lua', 'locally customized')
        self.put(self.source, 'npc.lua', 'upstream changed')
        preview = self.scan()
        self.assertEqual(preview['summary']['conflicts'], 1)
        with self.assertRaisesRegex(ValueError, 'conflict approval'):
            self.apply(preview, confirm_overwrite=True)
        self.assertEqual((self.target / 'npc.lua').read_text(), 'locally customized')
        self.apply(preview, confirm_overwrite=True, approve_conflicts=True)
        self.assertEqual((self.target / 'npc.lua').read_text(), 'upstream changed')

    def test_source_changed_after_preview_is_rejected(self):
        self.put(self.source, 'a.lua', 'a')
        preview = self.scan()
        self.put(self.source, 'a.lua', 'b')
        with self.assertRaisesRegex(ValueError, 'changed since preview'):
            self.apply(preview)
        self.assertFalse((self.target / 'a.lua').exists())

    def test_runtime_changed_after_preview_is_rejected(self):
        self.put(self.source, 'a.lua', 'a')
        preview = self.scan()
        self.put(self.target, 'user.lua', 'keep')
        with self.assertRaisesRegex(ValueError, 'changed since preview'):
            self.apply(preview)

    def test_config_changed_after_preview_is_rejected(self):
        self.put(self.source, 'a.lua', 'a')
        preview = self.scan()
        self.config.write_text('{"server":{"directories":{"quests":"alternate"}}}')
        with self.assertRaisesRegex(ValueError, 'configuration changed'):
            self.apply(preview)

    def test_source_revision_change_after_preview_is_rejected(self):
        self.put(self.source, 'a.lua', 'a')
        preview = self.scan()
        self.marker.write_text('{"commit":"' + 'b' * 40 + '"}')
        with self.assertRaisesRegex(ValueError, 'Source selection'):
            self.apply(preview)

    def test_running_server_can_scan_but_cannot_deploy(self):
        self.running = True
        self.put(self.source, 'a.lua', 'a')
        preview = self.scan()
        with self.assertRaisesRegex(ValueError, 'Stop the Custom server'):
            self.apply(preview)

    def test_other_profiles_cannot_scan_apply_or_status(self):
        for profile in ('traditional', 'takp'):
            self.engine.profile = profile
            with self.assertRaisesRegex(ValueError, 'TRASC Custom'):
                self.scan()
            with self.assertRaisesRegex(ValueError, 'TRASC Custom'):
                deployment.status(self.engine, 'quest_sync')
            self.assertEqual(deployment.recover(self.engine), {'recovered': False})

    def test_preview_token_is_action_bound(self):
        self.put(self.source, 'a.lua', 'a')
        preview = self.scan()
        with self.assertRaisesRegex(ValueError, 'different profile or action'):
            deployment.load_preview(self.engine, 'lon_data', preview['token'])
        for value in ('../../etc/passwd', 'a' * 31, None):
            with self.assertRaisesRegex(ValueError, 'token'):
                deployment.load_preview(self.engine, 'quest_sync', value)

    def test_symbolic_links_are_inspection_errors(self):
        outside = self.work / 'private'
        outside.write_text('secret')
        (self.source / 'escape.lua').symlink_to(outside)
        preview = self.scan()
        self.assertEqual(preview['summary']['errors'], 1)
        with self.assertRaisesRegex(ValueError, 'inspection error'):
            self.apply(preview)

    def test_symbolic_link_ancestor_is_rejected(self):
        link = self.work / 'server/link'
        link.symlink_to(self.target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            deployment.confined(self.engine, link / 'new.lua', True)

    def test_outside_and_protected_destinations_rejected(self):
        for path in (self.work.parent / 'outside', self.work / 'database/new', self.work / 'sources/new',
                     self.work / 'server', self.work / 'server/bin', self.work / 'backups/new'):
            with self.assertRaises(ValueError):
                deployment.confined(self.engine, path, True)
        for value in ('../escape', '/absolute', 'x\\y', 'x/../y', './x', 'C:/x', 'a\nb', ''):
            with self.assertRaises(ValueError):
                deployment.name(value)

    def test_nested_groups_require_exclusion_and_have_no_double_count(self):
        plugins = self.work / 'sources/current/Release-NMS-Plugins'
        self.put(plugins, 'helper.pl', 'helper')
        self.put(self.source, 'plugins/obsolete.pl', 'old')
        self.put(self.source, 'global/player.pl', 'quest')
        groups = [{'name': 'quests', 'source': self.source, 'destination': self.target},
                  {'name': 'plugins', 'source': plugins, 'destination': self.target / 'plugins'}]
        with self.assertRaisesRegex(ValueError, 'excluded'):
            self.scan(groups=groups)
        groups[0]['exclude'] = ['plugins']
        preview = self.scan(groups=groups)
        self.assertEqual(preview['summary']['new'], 2)
        self.apply(preview)
        self.assertTrue((self.target / 'plugins/helper.pl').is_file())
        self.assertFalse((self.target / 'plugins/obsolete.pl').exists())

    def test_empty_source_directories_are_preserved(self):
        (self.source / 'empty/nested').mkdir(parents=True)
        preview = self.scan()
        self.apply(preview)
        self.assertTrue((self.target / 'empty/nested').is_dir())

    def test_cancel_after_first_replacement_rolls_back_all_bytes(self):
        self.put(self.source, 'a.lua', 'new-a')
        self.put(self.source, 'b.lua', 'new-b')
        self.put(self.target, 'a.lua', 'original-a')
        self.put(self.target, 'b.lua', 'original-b')
        preview = self.scan()
        original = deployment._copy
        def copying(engine, source, target, expected, **kwargs):
            if Path(source) == self.source / 'b.lua':
                self.cancelled = True
            return original(engine, source, target, expected, **kwargs)
        with patch.object(deployment, '_copy', side_effect=copying):
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                self.apply(preview, confirm_overwrite=True)
        self.assertEqual((self.target / 'a.lua').read_text(), 'original-a')
        self.assertEqual((self.target / 'b.lua').read_text(), 'original-b')
        self.assertFalse(self.journal().exists())
        self.assertFalse(list(self.target.glob('.*trasc-deploy*')))

    def interrupt(self, *, new=True):
        self.put(self.source, 'a.lua', 'new-a')
        self.put(self.source, 'b.lua', 'new-b')
        if not new:
            self.put(self.target, 'a.lua', 'original-a')
        preview = self.scan()
        original = deployment._copy
        def copying(engine, source, target, expected, **kwargs):
            result = original(engine, source, target, expected, **kwargs)
            if Path(source) == self.source / 'b.lua':
                raise SystemExit('simulate killed process')
            return result
        # A real SIGKILL cannot enter the rollback handler. Leave exactly the
        # write-ahead state it would leave after one install and a partial copy.
        with patch.object(deployment, '_copy', side_effect=copying), patch.object(deployment, '_rollback', side_effect=RuntimeError('process gone')):
            with self.assertRaisesRegex(RuntimeError, 'process gone'):
                self.apply(preview, confirm_overwrite=True)
        self.assertTrue(self.journal().exists())
        self.assertEqual((self.target / 'a.lua').read_text(), 'new-a')
        return preview

    def test_process_restart_recovers_new_and_replaced_files(self):
        self.interrupt(new=False)
        result = deployment.recover(self.engine)
        self.assertTrue(result['rolled_back'])
        self.assertEqual((self.target / 'a.lua').read_text(), 'original-a')
        self.assertFalse((self.target / 'b.lua').exists())
        self.assertFalse(self.journal().exists())
        self.assertFalse(list(self.target.glob('.*trasc-deploy*')))

    def test_recovery_fail_closed_on_external_edit_before_any_rollback(self):
        self.interrupt()
        self.put(self.target, 'a.lua', 'outside edit')
        with self.assertRaisesRegex(ValueError, 'edited externally'):
            deployment.recover(self.engine)
        self.assertEqual((self.target / 'a.lua').read_text(), 'outside edit')
        self.assertTrue(self.journal().exists())
        with self.assertRaisesRegex(ValueError, 'Recover'):
            self.scan()

    def test_recovery_rejects_corrupted_backup_and_keeps_journal(self):
        preview = self.interrupt(new=False)
        backup = self.work / deployment.RECOVERY / 'history' / preview['token'] / '0.original'
        backup.chmod(0o600)
        backup.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'backup hash'):
            deployment.recover(self.engine)
        self.assertTrue(self.journal().exists())

    def test_committed_journal_recovery_never_reverts_successful_files(self):
        self.put(self.source, 'a.lua', 'new-a')
        preview = self.scan()
        real_unlink = Path.unlink
        failed = False
        def unlink(path, *args, **kwargs):
            nonlocal failed
            if path == self.journal() and not failed:
                failed = True
                raise OSError('unlink interrupted')
            return real_unlink(path, *args, **kwargs)
        # Completion cleanup failure safely takes the same rollback path.
        with patch.object(Path, 'unlink', unlink):
            with self.assertRaisesRegex(OSError, 'unlink interrupted'):
                self.apply(preview)
        self.assertFalse((self.target / 'a.lua').exists())
        self.assertFalse(self.journal().exists())

    def test_failed_second_deployment_restores_previous_manifest(self):
        self.put(self.source, 'a.lua', 'first')
        self.apply(self.scan())
        old = deployment.read(self.engine, self.work / deployment.RECOVERY / 'quest_sync-latest.json')
        self.put(self.source, 'a.lua', 'second')
        self.put(self.source, 'b.lua', 'second-b')
        preview = self.scan()
        real_copy = deployment._copy
        def copying(engine, source, target, expected, **kwargs):
            if Path(source) == self.source / 'b.lua':
                raise ValueError('failure')
            return real_copy(engine, source, target, expected, **kwargs)
        with patch.object(deployment, '_copy', side_effect=copying):
            with self.assertRaisesRegex(ValueError, 'failure'):
                self.apply(preview, confirm_overwrite=True)
        self.assertEqual((self.target / 'a.lua').read_text(), 'first')
        latest = deployment.read(self.engine, self.work / deployment.RECOVERY / 'quest_sync-latest.json')
        self.assertEqual(latest, old)

    def test_failed_copy_removes_created_empty_directories(self):
        self.put(self.source, 'new/nested/a.lua', 'new-a')
        preview = self.scan()
        with patch.object(deployment, '_copy', side_effect=ValueError('failure')):
            with self.assertRaisesRegex(ValueError, 'failure'):
                self.apply(preview)
        self.assertFalse((self.target / 'new').exists())

    def test_large_copy_uses_bounded_memory_and_exact_sha(self):
        path = self.source / 'large.dat'
        block = b'x' * (64 * 1024)
        with path.open('wb') as out:
            for _ in range(256):
                out.write(block)
        tracemalloc.start()
        try:
            preview = self.scan()
            self.apply(preview)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 3 * 1024**2)
        self.assertEqual(deployment.digest(path), deployment.digest(self.target / 'large.dat'))
        self.assertEqual(preview['transfer_bytes'], 16 * 1024**2)

    def test_free_space_is_checked_before_any_replacement(self):
        self.put(self.source, 'a.lua', 'a')
        preview = self.scan()
        with patch.object(deployment.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=1024)):
            with self.assertRaisesRegex(ValueError, 'free space'):
                self.apply(preview)
        self.assertFalse(self.journal().exists())

    def test_file_details_filter_sort_pagination_and_diff(self):
        self.put(self.source, 'b.lua', 'large new\n')
        self.put(self.source, 'a.lua', 'new\n')
        self.put(self.target, 'a.lua', 'old\n')
        preview = self.scan()
        details = deployment.details(self.engine, {'token': preview['token'], 'sort': 'size_desc', 'limit': 1})
        self.assertEqual(details['rows'][0]['path'], 'b.lua')
        self.assertEqual(details['total'], 2)
        details = deployment.details(self.engine, {'token': preview['token'], 'classification': 'changed'})
        self.assertEqual(details['rows'][0]['path'], 'a.lua')
        diff = deployment.diff(self.engine, 'quest_sync', {'token': preview['token'], 'path': 'a.lua', 'group': 'quests'})
        self.assertIn('-old', diff['diff'])
        self.assertIn('+new', diff['diff'])

    def test_diff_rechecks_file_hash_and_bounds_large_text(self):
        self.put(self.source, 'a.lua', 'a')
        self.put(self.target, 'a.lua', 'b')
        preview = self.scan()
        self.put(self.target, 'a.lua', 'changed since scan')
        with self.assertRaisesRegex(ValueError, 'changed since preview'):
            deployment.diff(self.engine, 'quest_sync', {'token': preview['token'], 'path': 'a.lua', 'group': 'quests'})

    def test_configured_arrays_take_precedence_and_absolute_path_is_honored(self):
        alternate = str(self.work / 'alternate-lua')
        self.config.write_text(json.dumps({'server': {'directories': {'quests': 'ignored',
            'quest_paths': ['alternate-quests', 'secondary'], 'plugins': 'plugins',
            'lua_module_paths': [alternate, 'lua_modules']}}}))
        layout = deployment.destinations(self.engine)
        self.assertEqual(layout['quests'], str(self.work / 'server/alternate-quests'))
        self.assertEqual(layout['lua_modules'], alternate)
        self.assertEqual(len(layout['quest_paths']), 2)
        self.assertNotIn('lon_data', layout)

    def test_parent_runtime_config_changes_effective_world_cwd(self):
        self.config.unlink()
        (self.work / 'eqemu_config.json').write_text('{"server":{"directories":{"quests":"customquests"}}}')
        self.assertEqual(deployment.destinations(self.engine)['quests'], str(self.work / 'customquests'))

    def test_missing_active_config_fails_closed_before_preview(self):
        self.config.unlink()
        self.put(self.source, 'a.lua', 'a')
        with self.assertRaisesRegex(ValueError, 'Deploy the Custom server first'):
            self.scan()
        self.assertFalse((self.work / deployment.RECOVERY / 'previews').exists())

    def test_concurrent_deployment_lease_rejects_second_lock(self):
        with deployment.lease(self.engine):
            with self.assertRaisesRegex(ValueError, 'Another Custom deployment'):
                with deployment.lease(self.engine):
                    pass

    def rule_engine(self, selected='custom', sets=(('7', 'default'), ('9', 'custom')), values=None):
        self.queries = []
        self.ensure_calls = []
        values = values or {7: [('Custom:LoNDataPath', 'cards-default'), ('Custom:LoNEnabled', 'false')],
                            9: [('Custom:LoNDataPath', 'cards-active'), ('Custom:LoNEnabled', 'true')]}
        def mysql(query):
            self.queries.append(query)
            if 'FROM variables' in query:
                return 'value\n' + ((selected + '\n') if selected is not None else '')
            if 'FROM rule_sets' in query:
                return 'ruleset_id\tname\n' + ''.join('\t'.join(row) + '\n' for row in sets)
            if 'COUNT(*)' in query:
                return 'COUNT(*)\n1\n'
            for key, rows in values.items():
                if 'ruleset_id=' + str(key) + ' ' in query:
                    return 'rule_name\trule_value\n' + ''.join('\t'.join(row) + '\n' for row in rows)
            return 'rule_name\trule_value\n'
        self.engine.mysql = mysql
        self.engine.ensure_db = lambda **kwargs: self.ensure_calls.append(kwargs)

    def test_lon_rule_active_and_default_overlays_are_read_only(self):
        self.rule_engine()
        layout = deployment.destinations(self.engine, include_lon=True)
        self.assertEqual(layout['lon_data'], str(self.work / 'server/cards-active'))
        self.assertTrue(layout['lon_rule']['enabled'])
        self.assertEqual(self.ensure_calls, [{'existing_only': True}])
        self.assertTrue(all(query.startswith('SELECT ') for query in self.queries))

    def test_lon_rule_default_overlay_and_invalid_ruleset_fail_closed(self):
        self.rule_engine(selected='custom', values={7: [('Custom:LoNDataPath', 'default-data')]})
        self.assertEqual(deployment.lon_rule(self.engine)['path'], 'default-data')
        self.rule_engine(selected='nonexistent', sets=(('7', 'default'),))
        with self.assertRaisesRegex(ValueError, 'ruleset is missing'):
            deployment.lon_rule(self.engine)

    def test_lon_database_unavailable_is_not_assumed_default(self):
        self.engine.mysql = lambda query: (_ for _ in ()).throw(ValueError('database unavailable'))
        with self.assertRaisesRegex(ValueError, 'Cannot resolve'):
            deployment.destinations(self.engine, include_lon=True)
        # Quest deployment remains independent of LoN database availability.
        self.assertIn('quests', deployment.destinations(self.engine))

    def test_lon_rule_destination_cannot_escape_into_other_world(self):
        self.rule_engine(values={9: [('Custom:LoNDataPath', '../../outside')]})
        with self.assertRaisesRegex(ValueError, 'inside this world'):
            deployment.destinations(self.engine, include_lon=True)

    def test_lon_preview_rejects_changed_rule_at_apply(self):
        self.rule_engine()
        root = self.work / 'incoming/custom-deployment/lon/data'
        self.put(root, 'card.dat', 'card')
        target = deployment.destinations(self.engine, include_lon=True)['lon_data']
        preview = deployment.preview(self.engine, 'lon_data', [{'name': 'lon_data', 'source': root,
            'destination': target}], {'revision': None})
        self.rule_engine(values={9: [('Custom:LoNDataPath', 'different-path')]})
        with self.assertRaisesRegex(ValueError, 'configuration changed'):
            deployment.apply(self.engine, 'lon_data', {'token': preview['token']})

    def test_destination_validation_failure_rolls_back_before_manifest_commit(self):
        self.put(self.source, 'a.lua', 'new')
        self.put(self.target, 'a.lua', 'old')
        preview = self.scan()
        seen = []
        def validate():
            seen.append((self.target / 'a.lua').read_text())
            raise ValueError('merged data invalid')
        with self.assertRaisesRegex(ValueError, 'merged data invalid'):
            deployment.apply(self.engine, 'quest_sync', {'token': preview['token'], 'confirm_overwrite': True}, validate=validate)
        self.assertEqual(seen, ['new'])
        self.assertEqual((self.target / 'a.lua').read_text(), 'old')
        self.assertIsNone(deployment.status(self.engine, 'quest_sync')['last_sync'])
        self.assertFalse(self.journal().exists())

    def test_destination_validation_success_is_recorded(self):
        self.put(self.source, 'a.lua', 'new')
        result = deployment.apply(self.engine, 'quest_sync', {'token': self.scan()['token']}, validate=lambda: {'valid': True})
        self.assertEqual(result['validation'], {'valid': True})
        self.assertEqual(deployment.status(self.engine, 'quest_sync')['last_result']['validation'], {'valid': True})

    def test_recovery_ignores_only_torn_final_unapplied_event(self):
        self.interrupt()
        events = self.work / deployment.RECOVERY / 'journal.events'
        with events.open('ab') as out:
            out.write(b'{"operation":{"target":"torn-final-record')
        deployment.recover(self.engine)
        self.assertFalse((self.target / 'a.lua').exists())
        self.assertFalse(events.exists())

    def test_recovery_fails_closed_on_corrupt_complete_event(self):
        self.interrupt()
        events = self.work / deployment.RECOVERY / 'journal.events'
        with events.open('ab') as out:
            out.write(b'not a json record\n')
        with self.assertRaisesRegex(ValueError, 'Corrupt'):
            deployment.recover(self.engine)
        self.assertEqual((self.target / 'a.lua').read_text(), 'new-a')

    def test_journal_header_writes_are_constant_with_file_count(self):
        for index in range(20):
            self.put(self.source, str(index) + '.lua', str(index))
        preview = self.scan()
        real_atomic = deployment.atomic
        calls = []
        def write(engine, path, value):
            if Path(path) == self.journal():
                calls.append(value['phase'])
            return real_atomic(engine, path, value)
        with patch.object(deployment, 'atomic', side_effect=write):
            self.apply(preview)
        self.assertEqual(calls, ['applying', 'committed'])

    def test_committed_restart_recovers_when_event_cleanup_already_finished(self):
        self.put(self.source, 'a.lua', 'new')
        preview = self.scan()
        original = deployment._remove_journal
        def interrupted_cleanup(engine):
            events = self.work / deployment.RECOVERY / 'journal.events'
            events.unlink()
            raise SystemExit('killed after removing events')
        with patch.object(deployment, '_remove_journal', side_effect=interrupted_cleanup), patch.object(deployment, '_rollback', side_effect=RuntimeError('killed')):
            with self.assertRaisesRegex(RuntimeError, 'killed'):
                self.apply(preview)
        result = deployment.recover(self.engine)
        self.assertTrue(result['committed'])
        self.assertEqual((self.target / 'a.lua').read_text(), 'new')
        self.assertFalse(self.journal().exists())

    def test_symlink_cannot_be_hidden_by_parent_normalization(self):
        (self.work / 'server/linked').symlink_to(self.work / 'source', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            deployment.confined(self.engine, self.work / 'server/linked/../quests', True)

    def test_configured_array_cannot_hide_symlink_before_parent_segment(self):
        (self.work / 'server/linked').symlink_to(self.work / 'elsewhere', target_is_directory=True)
        self.config.write_text(json.dumps({'server': {'directories': {'quest_paths': ['linked/../quests']}}}))
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            deployment.destinations(self.engine)

    def test_killed_rollback_resumes_from_recorded_partial_restore(self):
        self.interrupt(new=False)
        backend = Path(deployment.__file__).parent
        script = '''
import os, sys, types
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import custom_deployment as d
engine=types.SimpleNamespace(work=Path(sys.argv[2]),profile='custom',server_running=lambda:False)
original=d._copy
def interrupted(engine,source,target,expected,**kwargs):
    if kwargs.get('cancel') is False:
        with Path(target).open('xb') as out:
            out.write(b'orig')
            out.flush()
            os.fsync(out.fileno())
        os._exit(73)
    return original(engine,source,target,expected,**kwargs)
d._copy=interrupted
d.recover(engine)
'''
        result = subprocess.run([sys.executable, '-c', script, str(backend), str(self.work)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertTrue(list(self.target.glob('.*.restore-*')))
        self.assertEqual((self.target / 'a.lua').read_text(), 'new-a')
        recovered = deployment.recover(self.engine)
        self.assertTrue(recovered['rolled_back'])
        self.assertEqual((self.target / 'a.lua').read_text(), 'original-a')
        self.assertFalse(list(self.target.glob('.*.restore-*')))
        self.assertFalse(self.journal().exists())

    def test_lon_rule_missing_default_or_empty_default_fails_closed(self):
        self.rule_engine(sets=(('9', 'custom'),))
        with self.assertRaisesRegex(ValueError, 'ruleset is missing'):
            deployment.lon_rule(self.engine)
        self.rule_engine()
        original = self.engine.mysql
        self.engine.mysql = lambda query: 'COUNT(*)\n0\n' if 'COUNT(*)' in query else original(query)
        with self.assertRaisesRegex(ValueError, 'ruleset is empty'):
            deployment.lon_rule(self.engine)

    def test_lon_enabled_boolean_matches_server_parser(self):
        for text, expected in (('on', True), ('2', True), ('-1', True), ('TRUE', False), ('0', False), ('false', False), ('enabled', True)):
            with self.subTest(text=text):
                self.rule_engine(values={9: [('Custom:LoNEnabled', text)]})
                self.assertEqual(deployment.lon_rule(self.engine)['enabled'], expected)


if __name__ == '__main__':
    unittest.main()
