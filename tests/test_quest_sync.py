"""Quest synchronization wiring, version identity, destinations and witnesses."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import custom_deployment as deployment
import quest_sync


class QuestSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.engine = types.SimpleNamespace(work=self.work, profile='custom',
            current_job={}, cancel=threading.Event(), config={}, processes={})
        self.engine.server_running = lambda: False
        self.engine.check_cancel = self.check_cancel
        self.engine.log = lambda text: None
        self.source = self.work/'sources/current'
        self.server = self.work/'server'
        for name in ('incoming', 'run', 'backups', 'server'):
            (self.work/name).mkdir(parents=True, exist_ok=True)
        self.write(self.source/'trasc-source.json', json.dumps({
            'type': 'github', 'repo': 'https://github.com/Russianranger/Triptych-Triumvirate',
            'ref': 'main', 'commit': 'a'*40, 'imported': 12345}))
        self.write(self.source/'Release-NMS-Quests/qeynos/player.lua', 'return "quest"\n')
        self.write(self.source/'Release-NMS-Quests/lua_modules/support.lua', 'return "module"\n')
        self.write(self.source/'Release-NMS-Plugins/support.pl', '1;\n')
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'quests', 'plugins': 'quests/plugins', 'lua_modules': 'quests/lua_modules'}}}))
        # No deployment operation may alter these otherwise unrelated bytes.
        self.protected = {'database/player_data': b'player-data-version-160',
                          'client/current/eqgame.exe': b'client-executable',
                          'server/bin/world': b'server-binary'}
        for name, raw in self.protected.items():
            self.write(self.work/name, raw)

    def check_cancel(self):
        if self.engine.cancel.is_set():
            raise ValueError('Operation cancelled')

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode() if isinstance(value, str) else value)
        return path

    def assert_protected(self):
        for relative, raw in self.protected.items():
            self.assertEqual((self.work/relative).read_bytes(), raw)

    def test_integrated_sha_scan_and_sync_preserve_runtime_only_and_structure(self):
        self.write(self.server/'quests/qeynos/local.lua', 'my local quest')
        result = quest_sync.scan(self.engine)
        self.assertEqual(result['summary']['new'], 3)
        self.assertEqual(result['summary']['runtime_only'], 1)
        self.assertEqual(result['summary']['errors'], 0)
        self.assertEqual(result['group_summaries']['quests']['new'], 1)
        self.assertEqual(result['group_summaries']['plugins']['new'], 1)
        self.assertEqual(result['group_summaries']['lua_modules']['new'], 1)
        rows = quest_sync.files(self.engine, {'token': result['token'], 'limit': 100})['rows']
        self.assertEqual(len(rows), 4)
        self.assertTrue(all('modified' in (row['source'] or row['destination']) for row in rows))
        copied = quest_sync.apply(self.engine, {'token': result['token']})
        self.assertEqual(copied['copied_files'], 3)
        self.assertEqual((self.server/'quests/qeynos/local.lua').read_text(), 'my local quest')
        self.assertFalse((self.server/'quests/Release-NMS-Quests').exists())
        self.assertFalse((self.server/'quests/plugins/Release-NMS-Plugins').exists())
        self.assertEqual((self.server/'quests/plugins/support.pl').read_bytes(),
                         (self.source/'Release-NMS-Plugins/support.pl').read_bytes())
        self.assertEqual((self.server/'quests/lua_modules/support.lua').read_bytes(),
                         (self.source/'Release-NMS-Quests/lua_modules/support.lua').read_bytes())
        after = quest_sync.scan(self.engine)
        self.assertEqual(after['summary']['matching'], 3)
        self.assertEqual(after['summary']['files'], 0)
        self.assertEqual(after['summary']['runtime_only'], 1)
        self.assert_protected()

    def test_freshness_and_local_modification_require_explicit_conflict_approval(self):
        first = quest_sync.scan(self.engine)
        quest_sync.apply(self.engine, {'token': first['token']})
        state = quest_sync.status(self.engine)
        self.assertEqual(state['source']['last_commit'], 'a'*40)
        self.assertIsNotNone(state['source']['last_sync'])
        self.assertFalse(state['source']['dirty'])
        source = self.source/'Release-NMS-Quests/qeynos/player.lua'
        old = source.stat()
        source.write_text('return "other"\n')
        os.utime(source, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertTrue(quest_sync.status(self.engine)['source']['dirty'])
        target = self.server/'quests/qeynos/player.lua'
        target.write_text('my customized quest')
        preview = quest_sync.scan(self.engine)
        self.assertEqual(preview['summary']['changed'], 1)
        self.assertEqual(preview['summary']['conflicts'], 1)
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            quest_sync.apply(self.engine, {'token': preview['token']})
        with self.assertRaisesRegex(ValueError, 'conflict approval'):
            quest_sync.apply(self.engine, {'token': preview['token'], 'confirm_overwrite': True})
        self.assertEqual(target.read_text(), 'my customized quest')
        applied = quest_sync.apply(self.engine, {'token': preview['token'],
                                    'confirm_overwrite': True, 'approve_conflicts': True})
        self.assertEqual(target.read_bytes(), source.read_bytes())
        originals = list(Path(applied['backup']).glob('*.original'))
        self.assertEqual([item.read_text() for item in originals], ['my customized quest'])
        self.assertFalse(quest_sync.status(self.engine)['source']['dirty'])
        self.engine.cancel.set()
        # An old cancellation must not turn a read-only status into unavailable.
        self.assertTrue(quest_sync.status(self.engine)['source_available'])
        self.assert_protected()

    def test_new_only_review_preserves_changed_files_and_text_diff_is_bound(self):
        self.write(self.server/'quests/qeynos/player.lua', 'my existing quest')
        preview = quest_sync.scan(self.engine)
        difference = quest_sync.diff(self.engine, {'token': preview['token'],
                                   'group': 'quests', 'path': 'qeynos/player.lua'})
        self.assertIn('-my existing quest', difference['diff'])
        self.assertIn('+return "quest"', difference['diff'])
        result = quest_sync.apply(self.engine, {'token': preview['token'],
                                   'include_new': True, 'include_changed': False})
        self.assertEqual(result['copied_files'], 2)
        self.assertEqual((self.server/'quests/qeynos/player.lua').read_text(), 'my existing quest')
        filtered = quest_sync.files(self.engine, {'token': preview['token'],
                                     'classification': 'changed', 'sort': 'size_desc'})
        self.assertEqual(filtered['total'], 1)
        self.assert_protected()

    def test_alternate_lua_sync_mirrors_default_and_preserves_local_modules(self):
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'quests', 'plugins': 'quests/plugins', 'lua_modules': 'lua-alternate'}}}))
        self.write(self.server/'quests/lua_modules/local.lua', 'local module')
        preview = quest_sync.scan(self.engine)
        quest_sync.apply(self.engine, {'token': preview['token']})
        self.assertEqual((self.server/'lua-alternate/support.lua').read_bytes(),
                         (self.source/'Release-NMS-Quests/lua_modules/support.lua').read_bytes())
        self.assertEqual((self.server/'quests/lua_modules/local.lua').read_text(), 'local module')
        self.assertEqual((self.server/'quests/lua_modules/support.lua').read_bytes(),
                         (self.source/'Release-NMS-Quests/lua_modules/support.lua').read_bytes())
        self.assert_protected()

    def test_multiple_lua_search_paths_are_mirrored_and_deduplicated(self):
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quest_paths': ['quests', 'preserved-quests'],
            'plugin_paths': ['quests/plugins', 'preserved-plugins'],
            'lua_module_paths': ['lua-first', 'lua-second', 'quests/lua_modules', 'lua-first']}}}))
        self.write(self.server/'preserved-quests/local.lua', 'leave this quest')
        self.write(self.server/'preserved-plugins/local.pl', 'leave this plugin')
        preview = quest_sync.scan(self.engine)
        self.assertEqual(preview['summary']['new'], 5)
        self.assertEqual(len(preview['lua_destinations']), 3)
        self.assertEqual(set(preview['group_summaries']),
                         {'quests', 'plugins', 'lua_modules', 'lua_modules_2', 'lua_modules_default'})
        self.assertEqual(sum(value['new'] for key, value in preview['group_summaries'].items()
                             if key.startswith('lua_modules')), 3)
        quest_sync.apply(self.engine, {'token': preview['token']})
        for directory in ('lua-first', 'lua-second', 'quests/lua_modules'):
            self.assertEqual((self.server/directory/'support.lua').read_bytes(),
                             (self.source/'Release-NMS-Quests/lua_modules/support.lua').read_bytes())
        self.assertEqual((self.server/'preserved-quests/local.lua').read_text(), 'leave this quest')
        self.assertEqual((self.server/'preserved-plugins/local.pl').read_text(), 'leave this plugin')
        self.assert_protected()

    def test_default_lua_mirror_local_change_is_an_independent_conflict(self):
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'quests', 'plugins': 'quests/plugins', 'lua_module_paths': ['lua-first']}}}))
        preview = quest_sync.scan(self.engine)
        quest_sync.apply(self.engine, {'token': preview['token']})
        target = self.server/'quests/lua_modules/support.lua'
        target.write_text('local default module change')
        preview = quest_sync.scan(self.engine)
        self.assertEqual(preview['group_summaries']['lua_modules']['matching'], 1)
        self.assertEqual(preview['group_summaries']['lua_modules_default']['conflicts'], 1)
        with self.assertRaisesRegex(ValueError, 'conflict approval'):
            quest_sync.apply(self.engine, {'token': preview['token'], 'confirm_overwrite': True})
        self.assertEqual(target.read_text(), 'local default module change')
        self.assert_protected()

    def test_lua_feature_report_requires_every_configured_and_default_placement(self):
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'quests', 'plugins': 'quests/plugins', 'lua_module_paths': ['lua-first']}}}))
        feature = {'name': 'Lua witness', 'update': 'October 9',
                   'files': ('Release-NMS-Quests/lua_modules/support.lua',)}
        with patch.object(quest_sync, 'FEATURES', (feature,)):
            preview = quest_sync.scan(self.engine)
            copied = quest_sync.apply(self.engine, {'token': preview['token']})
            item = copied['features']['features'][0]['files'][0]
            self.assertEqual(item['state'], 'source_present_deployed')
            self.assertEqual(len(item['destinations']), 2)
            (self.server/'quests/lua_modules/support.lua').write_text('changed locally')
            report = quest_sync.feature_report(self.engine)['features'][0]
            self.assertEqual(report['state'], 'source_present_not_deployed')
            self.assertEqual([x['state'] for x in report['files'][0]['destinations']],
                             ['source_present_deployed', 'source_present_not_deployed'])

    def test_placement_configuration_change_is_not_a_source_content_edit(self):
        preview = quest_sync.scan(self.engine)
        quest_sync.apply(self.engine, {'token': preview['token']})
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'quests', 'plugins': 'quests/plugins', 'lua_module_paths': ['lua-new']}}}))
        self.assertFalse(quest_sync.status(self.engine)['source']['dirty'])
        preview = quest_sync.scan(self.engine)
        self.assertFalse(preview['source']['dirty'])
        self.assertEqual(preview['group_summaries']['lua_modules']['new'], 1)
        self.assertEqual(preview['group_summaries']['lua_modules_default']['matching'], 1)

    def test_configured_helper_root_cannot_hide_source_quest_content(self):
        self.write(self.source/'Release-NMS-Quests/qeynos/extra.lua', 'quest zone content')
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'quests', 'plugins': 'quests/plugins', 'lua_module_paths': ['quests/qeynos']}}}))
        with self.assertRaisesRegex(ValueError, 'overlaps quest source content'):
            quest_sync.scan(self.engine)
        self.assert_protected()

    def test_source_change_during_scan_cannot_issue_a_misidentified_preview(self):
        original = deployment.preview
        def change_before_preview(*args, **kwargs):
            (self.source/'Release-NMS-Quests/qeynos/player.lua').write_text('changed mid scan')
            return original(*args, **kwargs)
        with patch.object(deployment, 'preview', side_effect=change_before_preview):
            with self.assertRaisesRegex(ValueError, 'changed during inspection'):
                quest_sync.scan(self.engine)
        self.assertFalse((self.server/'quests').exists())
        self.assert_protected()

    def test_lua_witness_does_not_follow_a_linked_default_root(self):
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'quests', 'plugins': 'quests/plugins', 'lua_module_paths': ['lua-first']}}}))
        outside = self.work/'outside-lua'
        self.write(outside/'support.lua', 'return "module"\n')
        (self.server/'quests').mkdir()
        (self.server/'quests/lua_modules').symlink_to(outside, target_is_directory=True)
        feature = {'name': 'Lua witness', 'update': 'October 9',
                   'files': ('Release-NMS-Quests/lua_modules/support.lua',)}
        with patch.object(quest_sync, 'FEATURES', (feature,)):
            report = quest_sync.feature_report(self.engine)['features'][0]
            self.assertEqual(report['state'], 'source_present_not_deployed')
            placement = report['files'][0]['destinations'][1]
            self.assertIn('symbolic link', placement['error'])
            self.assertNotIn('sha256', placement)

    def test_active_server_prevents_any_replacement(self):
        preview = quest_sync.scan(self.engine)
        self.engine.server_running = lambda: True
        with self.assertRaisesRegex(ValueError, 'Stop the Custom server'):
            quest_sync.apply(self.engine, {'token': preview['token']})
        self.assertFalse((self.server/'quests').exists())
        self.assert_protected()

    def test_source_revision_exact_selected_import_and_no_network(self):
        identity = quest_sync._source_identity(self.engine)
        self.assertEqual(identity['commit'], 'a'*40)
        self.assertEqual(identity['revision'], 'a'*40)
        self.assertEqual(identity['source_path'], str(self.source))
        self.assertEqual(len(identity['source_marker_sha256']), 64)
        self.assertEqual(identity['ref'], 'main')
        # The fixture has neither download nor run: a scan uses installed bytes.
        with patch.object(deployment, 'preview', return_value={'token': 'test'}) as preview:
            result = quest_sync.scan(self.engine)
        self.assertEqual(result['source']['commit'], 'a'*40)
        self.assertEqual(preview.call_args.args[3]['commit'], 'a'*40)
        self.assert_protected()

    def test_unknown_archive_commit_is_not_invented(self):
        self.write(self.source/'trasc-source.json', '{"type":"archive","imported":12345}')
        identity = quest_sync._source_identity(self.engine)
        self.assertIsNone(identity['commit'])
        self.assertIn('not recorded', identity['revision_label'])

    def test_invalid_commit_and_oversized_marker_refused(self):
        self.write(self.source/'trasc-source.json', '{"commit":"main"}')
        with self.assertRaisesRegex(ValueError, 'commit identity'):
            quest_sync._source_identity(self.engine)
        self.write(self.source/'trasc-source.json', b' '*(quest_sync.SOURCE_LIMIT+1))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            quest_sync._source_identity(self.engine)

    def test_custom_only_source_and_actions(self):
        for profile in ('traditional', 'takp'):
            self.engine.profile = profile
            for operation, args in ((quest_sync.status, {}), (quest_sync.scan, {}),
                                    (quest_sync.files, {'token': 'not-used'}),
                                    (quest_sync.diff, {'token': 'not-used'}),
                                    (quest_sync.apply, {'token': 'not-used'})):
                with self.subTest(profile=profile, operation=operation.__name__), self.assertRaises(ValueError):
                    operation(self.engine, args)
        self.assert_protected()

    def test_group_roots_do_not_duplicate_plugins_or_lua_modules(self):
        groups = quest_sync._groups(self.engine)
        by_name = {group['name']: group for group in groups}
        self.assertEqual(set(by_name), {'quests', 'plugins', 'lua_modules'})
        self.assertEqual(by_name['quests']['source'], self.source/'Release-NMS-Quests')
        self.assertEqual(by_name['plugins']['destination'], self.server/'quests/plugins')
        self.assertEqual(set(by_name['quests']['exclude']), {'plugins', 'lua_modules'})
        self.assertEqual(by_name['lua_modules']['destination'], self.server/'quests/lua_modules')

    def test_configured_alternate_lua_module_destination(self):
        self.write(self.server/'eqemu_config.json', json.dumps({'server': {'directories': {
            'quests': 'custom_quests', 'plugins': 'custom_plugins', 'lua_modules': 'custom_lua'}}}))
        groups = {group['name']: group for group in quest_sync._groups(self.engine)}
        self.assertEqual(groups['quests']['destination'], self.server/'custom_quests')
        self.assertEqual(groups['plugins']['destination'], self.server/'custom_plugins')
        self.assertEqual(groups['lua_modules']['destination'], self.server/'custom_lua')

    def test_missing_source_fails_clearly_without_mutation(self):
        (self.source/'Release-NMS-Plugins/support.pl').unlink()
        (self.source/'Release-NMS-Plugins').rmdir()
        with self.assertRaisesRegex(ValueError, 'Release-NMS-Plugins'):
            quest_sync.scan(self.engine)
        self.assert_protected()

    def test_source_directory_symlink_is_rejected(self):
        (self.source/'Release-NMS-Plugins/support.pl').unlink()
        (self.source/'Release-NMS-Plugins').rmdir()
        outside = self.work/'external_plugins'
        outside.mkdir()
        (self.source/'Release-NMS-Plugins').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ordinary'):
            quest_sync.scan(self.engine)

    def test_each_update_witness_is_hashed_not_just_a_directory(self):
        feature = {'name': 'test witness', 'update': 'October 9',
                   'files': ('Release-NMS-Quests/qeynos/player.lua',)}
        destination = self.server/'quests/qeynos/player.lua'
        with patch.object(quest_sync, 'FEATURES', (feature,)):
            result = quest_sync.feature_report(self.engine)['features'][0]
            self.assertEqual(result['state'], 'source_present_not_deployed')
            self.write(destination, 'return "other"\n')
            result = quest_sync.feature_report(self.engine)['features'][0]
            self.assertEqual(result['state'], 'source_present_not_deployed')
            self.write(destination, (self.source/feature['files'][0]).read_bytes())
            result = quest_sync.feature_report(self.engine)['features'][0]
            self.assertEqual(result['state'], 'source_present_deployed')
            self.assertEqual(result['files'][0]['source_sha256'], result['files'][0]['destination_sha256'])
        self.assert_protected()

    def test_missing_update_witness_and_link_never_report_success(self):
        feature = {'name': 'missing', 'update': 'October 16',
                   'files': ('Release-NMS-Quests/missing/script.lua',)}
        (self.source/'Release-NMS-Quests/missing').mkdir()
        with patch.object(quest_sync, 'FEATURES', (feature,)):
            self.assertEqual(quest_sync.feature_report(self.engine)['features'][0]['state'], 'missing_or_additional_setup')
        feature['files'] = ('Release-NMS-Quests/qeynos/player.lua',)
        outside = self.write(self.work/'outside.lua', 'return "quest"\n')
        linked = self.server/'quests/qeynos'
        linked.parent.mkdir(parents=True, exist_ok=True)
        linked.symlink_to(outside.parent, target_is_directory=True)
        with patch.object(quest_sync, 'FEATURES', (feature,)):
            result = quest_sync.feature_report(self.engine)['features'][0]
            self.assertNotEqual(result['state'], 'source_present_deployed')
            self.assertIn('symbolic link', result['files'][0]['error'])

    def test_server_code_evidence_does_not_claim_a_migration_or_rebuild(self):
        self.write(self.source/'Release-NMS-Server/zone/achievement_manager.cpp', 'engine source')
        feature = {'name': 'Native achievements', 'update': 'October 16',
                   'files': ('Release-NMS-Server/zone/achievement_manager.cpp',)}
        with patch.object(quest_sync, 'FEATURES', (feature,)):
            result = quest_sync.feature_report(self.engine)
            self.assertEqual(result['features'][0]['state'], 'database_or_server_code')
            self.assertIn('No database migration', result['scope'])
        self.assert_protected()

    def test_actual_update_mapping_uses_exact_files_and_no_legacy_achievement_proxy(self):
        by_name = {feature['name']: feature for feature in quest_sync.FEATURES}
        self.assertIn('Release-NMS-Quests/rivervale/#Cake_Defense_Baker.lua',
                      by_name['Cake Defense baking and shroud mission']['files'])
        self.assertIn('Release-NMS-Quests/global/items/script_8884.pl',
                      by_name['Legends of Norrath support']['files'])
        self.assertEqual(len(by_name['Deity rank 2 quests']['files']), 19)
        self.assertFalse(any('Aurelian' in name for name in by_name['Native achievements']['files']))
        self.assertTrue(all(name.startswith('Release-NMS-Server/') for name in by_name['Native achievements']['files']))


if __name__ == '__main__':
    unittest.main()
