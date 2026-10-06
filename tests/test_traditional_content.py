import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import traditional_content as content


class TraditionalContentImports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.work = self.root / 'traditional'
        for name in ('incoming', 'server', 'backups', 'run'):
            (self.work / name).mkdir(parents=True)
        self.engine = SimpleNamespace(work=self.work, profile='traditional',
                                      server_running=Mock(return_value=False),
                                      check_cancel=Mock())

    def tearDown(self):
        self.tmp.cleanup()

    def archive(self, files):
        archive = self.work / 'incoming/content.zip'
        entries = files.items() if isinstance(files, dict) else files
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(archive, 'w') as output:
                for name, value in entries:
                    output.writestr(name, value)
        return archive

    def install(self, kind, files, **args):
        return content.install(self.engine, dict(kind=kind, file=self.archive(files).name, **args))

    def relative_files(self, kind):
        root = self.work / 'server' / kind
        return {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name != content.MARKER}

    def server_source(self):
        prefix = 'Server-master/'
        files = {
            'CMakeLists.txt': 'project(server)', 'zone/main.cpp': '// excluded source',
            'utils/patches/README.md': 'excluded docs',
            'utils/patches/install.sh': 'excluded executable',
            'utils/patches/opcodes.conf': 'OP_Test=0x0001',
            'utils/patches/mail_opcodes.conf': 'OP_Mail=0x0002',
            'loginserver/login_util/login_opcodes.conf': 'OP_Login=0x0003',
            'loginserver/login_util/login_opcodes_sod.conf': 'OP_Login=0x0004',
            'loginserver/login_util/login_opcodes_larion.conf': 'OP_Login=0x0005',
            'loginserver/login_util/login_schema.sql': 'DROP DATABASE peq;',
            'loginserver/login_util/login.json': '{"database":"wrong"}',
            'LICENSE.md': 'GPL-3.0 source license',
        }
        for name in ('Titanium', 'SoF', 'SoD', 'UF', 'RoF', 'RoF2'):
            files['utils/patches/patch_' + name + '.conf'] = 'OP_Test=0x0001'
        return {prefix + name: value for name, value in files.items()}

    def test_projecteq_plugins_and_modules_are_isolated(self):
        files = {'projecteqquests-master/qeynos/guard.pl': 'zone script',
                 'projecteqquests-master/global/global_player.lua': 'global script',
                 'projecteqquests-master/plugins/check.pl': 'perl plugin',
                 'projecteqquests-master/plugins/lib/helpers.pm': 'perl module',
                 'projecteqquests-master/lua_modules/general.lua': 'lua module',
                 'projecteqquests-master/lua_modules/commands/rules.lua': 'commands',
                 'projecteqquests-master/lua_modules/constants/races.lua': 'constants',
                 'projecteqquests-master/README.md': 'repo docs'}
        custom = self.root / 'custom/server/plugins/check.pl'
        custom.parent.mkdir(parents=True)
        custom.write_text('custom plugin')
        self.install('plugins', files)
        self.install('lua_modules', files)
        self.assertEqual(self.relative_files('plugins'), {'check.pl', 'lib/helpers.pm'})
        self.assertEqual(self.relative_files('lua_modules'),
                         {'general.lua', 'commands/rules.lua', 'constants/races.lua'})
        self.assertEqual(custom.read_text(), 'custom plugin')

    def test_one_quest_import_detects_plugins_and_lua_from_same_tree(self):
        files = {'projecteqquests-main/qeynos/guard.pl': 'zone script',
                 'projecteqquests-main/plugins/check.pl': 'perl plugin',
                 'projecteqquests-main/plugins/lib/helpers.pm': 'perl module',
                 'projecteqquests-main/plugins/README.md': 'documentation',
                 'projecteqquests-main/lua_modules/general.lua': 'lua module',
                 'projecteqquests-main/lua_modules/constants/races.lua': 'constants'}
        result = self.install('quests', files)
        detected = content.components(self.engine)
        for kind, total, scripts in (('plugins', 3, 2), ('lua_modules', 2, 2)):
            with self.subTest(kind=kind):
                self.assertTrue(detected[kind]['imported'])
                self.assertTrue(detected[kind]['present'])
                self.assertTrue(detected[kind]['quests_present'])
                self.assertEqual(detected[kind]['origin'], 'quests')
                self.assertEqual(detected[kind]['path'], 'server/quests/' + kind)
                self.assertEqual(detected[kind]['files'], total)
                self.assertEqual(detected[kind]['scripts'], scripts)
                self.assertEqual(detected[kind]['source'], result['component'])
                self.assertFalse((self.work / 'server' / kind).exists())

    def test_legacy_standalone_helpers_remain_usable_until_quests_supply_them(self):
        self.install('plugins', {'plugins/check.pl': 'legacy plugin'})
        self.install('lua_modules', {'lua_modules/general.lua': 'legacy module'})
        self.install('quests', {'qeynos/guard.pl': 'zone script'})
        detected = content.components(self.engine)
        for kind in ('plugins', 'lua_modules'):
            self.assertTrue(detected[kind]['imported'])
            self.assertFalse(detected[kind]['quests_present'])
            self.assertEqual(detected[kind]['origin'], 'standalone')
            self.assertEqual(detected[kind]['path'], 'server/' + kind)
            self.assertEqual(detected[kind]['quests_path'], 'server/quests/' + kind)
        self.install('quests', {'qeynos/guard.pl': 'new zone script',
                               'plugins/check.pl': 'new plugin',
                               'lua_modules/general.lua': 'new module'}, replace=True)
        for kind in ('plugins', 'lua_modules'):
            self.assertEqual(content.components(self.engine)[kind]['origin'], 'quests')
        self.assertEqual((self.work / 'server/plugins/check.pl').read_text(), 'legacy plugin')

    def test_unmarked_existing_quest_helpers_are_detected(self):
        for relative, value in (('server/quests/plugins/check.pl', 'plugin'),
                                ('server/quests/lua_modules/general.lua', 'lua')):
            path = self.work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        for kind in ('plugins', 'lua_modules'):
            detected = content.components(self.engine)[kind]
            self.assertTrue(detected['imported'])
            self.assertEqual(detected['origin'], 'quests')
            self.assertIsNone(detected['source'])

    def test_empty_or_documentation_only_helper_directories_are_missing(self):
        self.install('quests', {'qeynos/guard.pl': 'zone',
                               'plugins/README.md': 'no Perl scripts',
                               'lua_modules/README.md': 'no Lua scripts'})
        for kind in ('plugins', 'lua_modules'):
            detected = content.components(self.engine)[kind]
            self.assertTrue(detected['present'])
            self.assertTrue(detected['quests_present'])
            self.assertFalse(detected['imported'])
            self.assertEqual(detected['origin'], 'missing')
            self.assertEqual(detected['scripts'], 0)

    def test_quests_replacement_updates_helper_detection_and_preserves_backup(self):
        self.install('quests', {'qeynos/guard.pl': 'old zone', 'plugins/check.pl': 'old plugin',
                               'lua_modules/general.lua': 'old module'})
        result = self.install('quests', {'qeynos/guard.pl': 'new zone', 'plugins/new.pl': 'new plugin'}, replace=True)
        detected = content.components(self.engine)
        self.assertTrue(detected['plugins']['imported'])
        self.assertEqual(detected['plugins']['files'], 1)
        self.assertFalse(detected['lua_modules']['imported'])
        backup = self.work / result['backup']
        self.assertEqual((backup / 'plugins/check.pl').read_text(), 'old plugin')
        self.assertEqual((backup / 'lua_modules/general.lua').read_text(), 'old module')

    def test_symlink_helper_or_quest_parent_cannot_count_as_available(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'check.pl').write_text('outside plugin')
        quests = self.work / 'server/quests'
        quests.mkdir()
        (quests / 'plugins').symlink_to(outside, target_is_directory=True)
        detected = content.components(self.engine)['plugins']
        self.assertFalse(detected['imported'])
        self.assertFalse(detected['safe'])
        (quests / 'plugins').unlink()
        quests.rmdir()
        quests.symlink_to(outside, target_is_directory=True)
        self.assertFalse(content.components(self.engine)['plugins']['imported'])

    def test_symlink_inside_helper_tree_is_rejected_without_following_it(self):
        self.install('quests', {'qeynos/guard.pl': 'zone', 'plugins/check.pl': 'plugin'})
        outside = self.root / 'outside.pm'
        outside.write_text('external module')
        (self.work / 'server/quests/plugins/external.pm').symlink_to(outside)
        detected = content.components(self.engine)['plugins']
        self.assertFalse(detected['imported'])
        self.assertFalse(detected['safe'])
        self.assertEqual(detected['files'], 0)

    def test_invalid_quest_marker_does_not_hide_usable_local_helpers(self):
        self.install('quests', {'qeynos/guard.pl': 'zone', 'plugins/check.pl': 'plugin'})
        (self.work / 'server/quests' / content.MARKER).write_text('[]')
        detected = content.components(self.engine)['plugins']
        self.assertTrue(detected['imported'])
        self.assertEqual(detected['origin'], 'quests')
        self.assertIsNone(detected['source'])

    def test_full_quests_repo_without_requested_folder_is_rejected(self):
        files = {'projecteqquests-master/qeynos/guard.pl': 'zone script',
                 'projecteqquests-master/global/global_player.lua': 'global script'}
        for kind in ('plugins', 'lua_modules'):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'directory or top-level'):
                self.install(kind, files)
            self.assertFalse((self.work / 'server' / kind).exists())

    def test_explicit_nested_component_directory(self):
        result = self.install('plugins', {'pack-main/quests/plugins/check.pl': 'plugin',
                                         'pack-main/quests/qeynos/guard.pl': 'zone'})
        self.assertEqual(self.relative_files('plugins'), {'check.pl'})
        self.assertEqual(result['component']['source_path'], 'pack-main/quests/plugins')

    def test_flat_component_and_github_wrapper_are_supported(self):
        self.install('plugins', {'check.pl': 'plugin'})
        self.install('lua_modules', {'modules-main/general.lua': 'module',
                                     'modules-main/commands/rules.lua': 'commands'})
        self.assertEqual(self.relative_files('plugins'), {'check.pl'})
        self.assertEqual(self.relative_files('lua_modules'), {'general.lua', 'commands/rules.lua'})

    def test_ambiguous_plugin_directories_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'more than one plugins'):
            self.install('plugins', {'pack/plugins/a.pl': 'one', 'pack/quests/plugins/b.pl': 'two'})

    def test_default_server_source_selects_only_runtime_assets(self):
        quests = self.work / 'server/quests/qeynos/guard.pl'
        quests.parent.mkdir(parents=True)
        quests.write_text('existing quests')
        result = self.install('assets', self.server_source())
        expected = {'patches/patch_' + name + '.conf' for name in ('Titanium', 'SoF', 'SoD', 'UF', 'RoF', 'RoF2')}
        expected.update({'opcodes/opcodes.conf', 'opcodes/mail_opcodes.conf',
                         'opcodes/login_opcodes.conf', 'opcodes/login_opcodes_sod.conf',
                         'opcodes/login_opcodes_larion.conf', 'LICENSE.md'})
        self.assertEqual(self.relative_files('assets'), expected)
        self.assertTrue(result['component']['opcodes_ready'])
        self.assertEqual(result['component']['files'], len(expected))
        self.assertEqual(result['component']['asset_layout'],
                         {'patches': 'assets/patches', 'opcodes': 'assets/opcodes'})
        self.assertIn('utils/patches/patch_RoF2.conf', result['component']['source_paths'])
        self.assertEqual(quests.read_text(), 'existing quests')

    def test_direct_asset_bundle_keeps_normalized_patch_and_opcode_paths(self):
        self.install('assets', {'assets/patches/patch_RoF2.conf': 'patch',
                                'assets/opcodes/opcodes.conf': 'opcodes',
                                'assets/opcodes/mail_opcodes.conf': 'mail',
                                'assets/opcodes/login_opcodes.conf': 'login',
                                'assets/opcodes/login_opcodes_sod.conf': 'sod',
                                'assets/install.sh': 'excluded script'})
        self.assertEqual(self.relative_files('assets'),
                         {'patches/patch_RoF2.conf', 'opcodes/opcodes.conf', 'opcodes/mail_opcodes.conf',
                          'opcodes/login_opcodes.conf', 'opcodes/login_opcodes_sod.conf'})

    def test_legacy_patch_zip_is_normalized_and_marked_partial(self):
        result = self.install('assets', {'assets-master/opcodes/patch_RoF2.conf': 'patch'})
        self.assertEqual(self.relative_files('assets'), {'patches/patch_RoF2.conf'})
        self.assertFalse(result['component']['opcodes_ready'])

    def test_incomplete_source_preserves_previous_assets(self):
        self.install('assets', self.server_source())
        before = (self.work / 'server/assets' / content.MARKER).read_bytes()
        incomplete = self.server_source()
        del incomplete['Server-master/utils/patches/mail_opcodes.conf']
        with self.assertRaisesRegex(ValueError, 'mail_opcodes.conf'):
            self.install('assets', incomplete, replace=True)
        self.assertEqual((self.work / 'server/assets' / content.MARKER).read_bytes(), before)
        self.assertFalse(any((self.work / 'backups').rglob('patch_RoF2.conf')))

    def test_assets_replacement_preserves_entire_previous_component(self):
        self.install('assets', {'patch_RoF2.conf': 'old'})
        result = self.install('assets', self.server_source(), replace=True)
        self.assertEqual((self.work / result['backup'] / 'patches/patch_RoF2.conf').read_text(), 'old')
        self.assertTrue((self.work / 'server/assets/opcodes/login_opcodes.conf').is_file())

    def test_unrelated_client_archive_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not client game files'):
            self.install('assets', {'client/eqclient.ini': '[Defaults]', 'client/spells_us.txt': 'data'})

    def test_ambiguous_asset_directories_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'more than one RoF2'):
            self.install('assets', {'pack/utils/patches/patch_RoF2.conf': 'one',
                                    'pack/assets/patches/patch_RoF2.conf': 'two'})

    def test_ambiguous_opcode_files_are_rejected(self):
        files = self.server_source()
        files['Server-master/opcodes/opcodes.conf'] = 'conflicting config'
        with self.assertRaisesRegex(ValueError, 'duplicate opcodes.conf'):
            self.install('assets', files)

    def test_duplicate_archive_entries_preserve_previous_component(self):
        self.install('plugins', {'plugins/check.pl': 'old'})
        for entries in ([('plugins/check.pl', 'one'), ('plugins/check.pl', 'two')],
                        [('plugins/check.pl', 'one'), ('./plugins/check.pl', 'two')]):
            with self.subTest(entries=entries), self.assertRaisesRegex(ValueError, 'duplicate paths'):
                self.install('plugins', entries, replace=True)
        self.assertEqual((self.work / 'server/plugins/check.pl').read_text(), 'old')

    def test_archive_traversal_and_symlink_are_rejected(self):
        with self.assertRaises(ValueError):
            self.install('plugins', {'plugins/../../escape.pl': 'bad'})
        self.assertFalse((self.work / 'escape.pl').exists())
        link = zipfile.ZipInfo('plugins/check.pl')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.install('plugins', [(link, '../outside')])

    def test_staging_collision_cannot_follow_symbolic_link(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.work / 'content-import-fixed').symlink_to(outside, target_is_directory=True)
        with patch('traditional_content.secrets.token_hex', return_value='fixed'), \
                self.assertRaisesRegex(ValueError, 'already exists'):
            self.install('plugins', {'plugins/check.pl': 'new'})
        self.assertEqual(list(outside.iterdir()), [])

    def test_incoming_and_journal_symlinks_are_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        archive = self.archive({'plugins/check.pl': 'new'})
        incoming = self.work / 'incoming'
        archive.unlink()
        incoming.rmdir()
        incoming.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            content.install(self.engine, {'kind': 'plugins', 'url': 'https://github.com/example/plugins'})
        incoming.unlink()
        incoming.mkdir()
        journal = self.work / 'run/content-plugins.json'
        journal.symlink_to(outside / 'journal.json')
        with self.assertRaisesRegex(ValueError, 'journal'):
            self.install('plugins', {'plugins/check.pl': 'new'})
        self.assertEqual(list(outside.iterdir()), [])

    def test_downloaded_source_uses_same_safe_asset_selection(self):
        source = self.archive(self.server_source())
        def download(url, ref, destination):
            destination.write_bytes(source.read_bytes())
            return {'repo': url, 'commit': 'a' * 40, 'ref': ref or 'master'}
        self.engine.github_download = Mock(side_effect=download)
        result = content.install(self.engine, {'kind': 'assets', 'url': 'https://github.com/Russianranger/Server', 'ref': ''})
        self.assertTrue(result['component']['opcodes_ready'])
        self.assertEqual(result['component']['commit'], 'a' * 40)
        self.engine.github_download.assert_called_once()
        metadata = json.loads((self.work / 'server/assets' / content.MARKER).read_text())
        self.assertEqual(metadata['archive_sha256'], result['component']['archive_sha256'])

    def test_native_picker_incoming_path_is_accepted(self):
        archive = self.archive({'plugins/check.pl': 'new'})
        content.install(self.engine, {'kind': 'plugins', 'file': 'incoming/' + archive.name})
        self.assertEqual((self.work / 'server/plugins/check.pl').read_text(), 'new')

    def test_content_file_path_cannot_escape_incoming(self):
        self.archive({'plugins/check.pl': 'new'})
        for filename in ('incoming/../content.zip', '../content.zip', 'other/content.zip', '/tmp/content.zip', '', 'content.zip/..'):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                content.install(self.engine, {'kind': 'plugins', 'file': filename})
        self.assertFalse((self.work / 'server/plugins').exists())

    def test_download_destination_symlink_is_rejected(self):
        outside = self.root / 'outside.zip'
        outside.write_bytes(b'keep')
        (self.work / 'incoming/plugins-download.zip').symlink_to(outside)
        self.engine.github_download = Mock()
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            content.install(self.engine, {'kind': 'plugins', 'url': 'https://github.com/example/plugins'})
        self.engine.github_download.assert_not_called()
        self.assertEqual(outside.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
