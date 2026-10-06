"""Profile-scoped UI installation, archive safety and recoverable replacement."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine, atomic_json
import client_ui

XML = b'<?xml version="1.0"?><XML><Screen item="Inventory"/></XML>'
NEW_XML = b'<?xml version="1.0"?><XML><Screen item="NewInventory"/></XML>'


class ClientUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root / 'custom')
        self.traditional = Engine(self.root / 'traditional', 'traditional')
        for engine in (self.engine, self.traditional):
            client = engine.work / 'client/current'
            client.mkdir()
            (client / 'trasc-client.json').write_text('{"imported":true}')
            for name, value in {'eqgame.exe': b'MZ original', 'eqclient.ini': b'[Defaults]\nKeep=TRUE\n',
                                'eqhost.txt': b'original host', 'dinput8.dll': b'original DLL'}.items():
                (client / name).write_bytes(value)
            default = client / 'UIFILES/Default'
            default.mkdir(parents=True)
            (default / 'EQUI_Inventory.xml').write_bytes(XML)
        self.client = self.engine.work / 'client/current'

    def archive(self, files, engine=None, name='skin.zip'):
        engine = engine or self.engine
        path = engine.work / 'incoming' / name
        with zipfile.ZipFile(path, 'w') as source:
            for member, value in files.items():
                source.writestr(member, value)
        return name

    def install(self, files, engine=None, **args):
        engine = engine or self.engine
        return engine.dispatch('import_client_ui', dict(file=self.archive(files, engine), **args))

    def test_real_dispatch_both_profiles_and_state_isolate_the_installed_skins(self):
        before = {name: (self.client / name).read_bytes() for name in ('eqgame.exe', 'eqclient.ini', 'eqhost.txt', 'dinput8.dll')}
        custom = self.install({'Stone/EQUI_Inventory.xml': XML, 'Stone/background.tga': b'texture'})
        traditional = self.install({'Classic/EQUI_Inventory.xml': NEW_XML}, self.traditional)
        self.assertEqual(custom['installed'][0]['name'], 'Stone')
        self.assertEqual(traditional['installed'][0]['profile'], 'traditional')
        self.assertEqual([s['name'] for s in self.engine.state()['client']['ui']['skins']], ['Default', 'Stone'])
        self.assertEqual([s['name'] for s in self.traditional.state()['client']['ui']['skins']], ['Classic', 'Default'])
        self.assertEqual((self.client / 'UIFILES/Default/EQUI_Inventory.xml').read_bytes(), XML)
        for name, original in before.items():
            self.assertEqual((self.client / name).read_bytes(), original)
        self.assertFalse((self.client / 'uifiles').exists())
        with self.assertRaisesRegex(ValueError, 'profile changed'):
            self.engine.dispatch('import_client_ui', {'file': 'skin.zip', '__profile': 'traditional'})

    def test_flat_skin_uses_original_archive_filename_and_native_picker_path(self):
        name = self.archive({'EQUI_Inventory.xml': XML, 'images/buttons.dds': b'buttons'}, name='179121-Skin.zip')
        result = self.engine.dispatch('import_client_ui', {'file': 'incoming/' + name, 'archive_name': 'Stone UI.zip'})
        self.assertEqual(result['installed'][0]['name'], 'Stone UI')
        self.assertEqual((self.client / 'UIFILES/Stone UI/images/buttons.dds').read_bytes(), b'buttons')
        self.assertEqual(result['installed'][0]['files'], 2)

    def test_github_wrapper_and_nested_uifiles_can_install_multiple_skins(self):
        result = self.install({'project-main/client/uifiles/Stone/EQUI_Inventory.xml': XML,
                               'project-main/client/uifiles/Luclin/EQUI_CastSpellWnd.xml': XML,
                               'project-main/README.md': b'not a skin',
                               'project-main/client/eqgame.exe': b'unrelated exe'})
        self.assertEqual(sorted(s['name'] for s in result['installed']), ['Luclin', 'Stone'])
        self.assertFalse((self.client / 'UIFILES/README.md').exists())
        self.assertEqual((self.client / 'eqgame.exe').read_bytes(), b'MZ original')

    def test_nested_optional_xml_stays_inside_parent_skin(self):
        result = self.install({'Stone/EQUI_Inventory.xml': XML, 'Stone/Options/EQUI_Inventory.xml': NEW_XML})
        self.assertEqual(len(result['installed']), 1)
        self.assertEqual((self.client / 'UIFILES/Stone/Options/EQUI_Inventory.xml').read_bytes(), NEW_XML)

    def test_platform_metadata_is_ignored_without_adding_files_to_client_root(self):
        result = self.install({'Stone/EQUI_Inventory.xml': XML, 'Stone/.DS_Store': b'mac',
                               'Stone/Thumbs.db': b'windows', 'Stone/desktop.ini': b'folder metadata',
                               '__MACOSX/Stone/._EQUI_Inventory.xml': b'resource fork'})
        self.assertEqual(result['installed'][0]['files'], 1)
        self.assertEqual(sorted(p.name for p in (self.client / 'UIFILES/Stone').iterdir()),
                         ['.trasc-ui.json', 'EQUI_Inventory.xml'])

    def test_stone_theme_metadata_is_omitted_in_both_profiles_without_xml_changes(self):
        manifest = json.dumps({'name': 'StoneUI RoF2', 'version': '0.1.0',
                               'files': ['EQUI_Inventory.xml'], 'theme': {'style': 'stone'}}).encode()
        for engine in (self.engine, self.traditional):
            with self.subTest(profile=engine.profile):
                result = self.install({'Stone/EQUI_Inventory.xml': XML,
                                       'Stone/STONE_THEME_MANIFEST.json': manifest}, engine)
                installed = engine.work / 'client/current/UIFILES/Stone'
                self.assertEqual((installed / 'EQUI_Inventory.xml').read_bytes(), XML)
                self.assertFalse((installed / 'STONE_THEME_MANIFEST.json').exists())
                self.assertEqual(result['installed'][0]['files'], 1)
                self.assertEqual(result['installed'][0]['bytes'], len(XML))

    def test_stone_theme_metadata_uses_windows_case_and_allows_utf8_bom(self):
        self.install({'Stone/EQUI_Inventory.xml': XML,
                      'Stone/stone_theme_manifest.JSON': b'\xef\xbb\xbf{"version":"0.1.0"}'})
        installed = self.client / 'UIFILES/Stone'
        self.assertEqual(sorted(p.name for p in installed.iterdir()), ['.trasc-ui.json', 'EQUI_Inventory.xml'])

    def test_invalid_theme_metadata_preserves_existing_skin_and_backup_state(self):
        self.install({'Stone/EQUI_Inventory.xml': XML})
        for value in (b'MZ executable', b'{"incomplete":', b'[]', b'null', b'{"value":NaN}', b'\xff\xfe'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'theme metadata'):
                self.install({'Stone/EQUI_Inventory.xml': NEW_XML,
                              'Stone/STONE_THEME_MANIFEST.json': value}, replace=True)
            self.assertEqual((self.client / 'UIFILES/Stone/EQUI_Inventory.xml').read_bytes(), XML)
            self.assertFalse((self.engine.work / 'run/client-ui-import.json').exists())
            self.assertFalse(any((self.engine.work / 'backups/client-ui').rglob('EQUI_Inventory.xml')))

    def test_oversized_theme_metadata_is_rejected_before_skin_activation(self):
        with patch.object(client_ui, 'MAX_THEME_METADATA_BYTES', 4):
            with self.assertRaisesRegex(ValueError, '1 MiB'):
                self.install({'Stone/EQUI_Inventory.xml': XML,
                              'Stone/STONE_THEME_MANIFEST.json': b'{"name":"StoneUI"}'})
        self.assertFalse((self.client / 'UIFILES/Stone').exists())

    def test_unknown_json_and_nested_named_metadata_remain_unsupported(self):
        for name in ('manifest.json', 'STONE_THEME_MANIFEST.json.exe', 'Options/STONE_THEME_MANIFEST.json'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unsupported file'):
                self.install({'Stone/EQUI_Inventory.xml': XML, 'Stone/' + name: b'{}'})
        self.assertFalse((self.client / 'UIFILES/Stone').exists())

    def test_theme_metadata_symbolic_link_remains_rejected(self):
        filename = self.archive({'Stone/EQUI_Inventory.xml': XML})
        with zipfile.ZipFile(self.engine.work / 'incoming' / filename, 'a') as source:
            link = zipfile.ZipInfo('Stone/STONE_THEME_MANIFEST.json')
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            source.writestr(link, '/other/metadata.json')
        with self.assertRaisesRegex(ValueError, 'ordinary'):
            client_ui.install(self.engine, {'file': filename})
        self.assertFalse((self.client / 'UIFILES/Stone').exists())

    def test_default_skin_requires_an_explicit_different_name(self):
        with self.assertRaisesRegex(ValueError, 'default UI is protected'):
            self.install({'default/EQUI_Inventory.xml': NEW_XML}, replace=True)
        result = self.install({'default/EQUI_Inventory.xml': NEW_XML}, name='MyClassic')
        self.assertEqual(result['installed'][0]['name'], 'MyClassic')
        self.assertEqual((self.client / 'UIFILES/Default/EQUI_Inventory.xml').read_bytes(), XML)

    def test_existing_skin_requires_replace_and_retains_complete_backup_with_existing_casing(self):
        self.install({'Stone/EQUI_Inventory.xml': XML, 'Stone/old.tga': b'old texture'})
        with self.assertRaisesRegex(ValueError, 'Replace existing skin'):
            self.install({'stone/EQUI_Inventory.xml': NEW_XML})
        result = self.install({'stone/EQUI_Inventory.xml': NEW_XML}, replace=True)
        skin = result['installed'][0]
        self.assertEqual(skin['name'], 'Stone')
        saved = self.engine.work / skin['backup']
        self.assertEqual((saved / 'old.tga').read_bytes(), b'old texture')
        self.assertEqual((saved / 'EQUI_Inventory.xml').read_bytes(), XML)
        self.assertEqual((self.client / 'UIFILES/Stone/EQUI_Inventory.xml').read_bytes(), NEW_XML)
        self.assertFalse((self.client / 'UIFILES/Stone/old.tga').exists())
        self.assertEqual(len(skin['archive_sha256']), 64)

    def test_all_skins_validate_before_any_existing_skin_changes(self):
        self.install({'Stone/EQUI_Inventory.xml': XML})
        with self.assertRaisesRegex(ValueError, 'Invalid UI XML'):
            self.install({'Stone/EQUI_Inventory.xml': NEW_XML, 'Other/EQUI_Window.xml': b'<broken>'}, replace=True)
        self.assertEqual((self.client / 'UIFILES/Stone/EQUI_Inventory.xml').read_bytes(), XML)
        self.assertFalse((self.client / 'UIFILES/Other').exists())
        self.assertFalse((self.engine.work / 'run/client-ui-import.json').exists())

    def test_disallowed_executables_dlls_and_ini_files_never_enter_skin_or_client(self):
        for name in ('eqgame.exe', 'dinput8.dll', 'eqclient.ini', 'run.sh'):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'Unsupported file'):
                    self.install({'Stone/EQUI_Inventory.xml': XML, 'Stone/' + name: b'bad'})
                self.assertFalse((self.client / 'UIFILES/Stone').exists())

    def test_traversal_windows_names_duplicates_and_case_collisions_rejected(self):
        for files in ({'../escape/EQUI_Inventory.xml': XML},
                      {'Stone/NUL.tga': b'bad', 'Stone/EQUI_Inventory.xml': XML},
                      {'Stone/EQUI_Inventory.xml': XML, 'Stone/equi_inventory.XML': NEW_XML},
                      {'Stone/EQUI_Inventory.xml': XML, 'stone/image.tga': b'bad'},
                      {'Stone/image.tga': b'bad', 'Stone/image.tga/inside.txt': b'bad', 'Stone/EQUI.xml': XML}):
            with self.subTest(files=list(files)):
                with self.assertRaises(ValueError):
                    self.install(files)
        self.assertFalse((self.root / 'escape').exists())

    def test_archive_symlink_and_existing_client_symlink_cannot_escape(self):
        filename = self.archive({'Stone/EQUI_Inventory.xml': XML})
        with zipfile.ZipFile(self.engine.work / 'incoming' / filename, 'a') as source:
            link = zipfile.ZipInfo('Stone/image.tga')
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            source.writestr(link, '/other/image.tga')
        with self.assertRaisesRegex(ValueError, 'ordinary'):
            client_ui.install(self.engine, {'file': filename})
        outside = self.root / 'outside'
        outside.mkdir()
        (self.client / 'UIFILES/Stone').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            self.install({'Stone/EQUI_Inventory.xml': XML})
        self.assertEqual(list(outside.iterdir()), [])

    def test_missing_client_nonincoming_source_and_invalid_names_are_rejected(self):
        (self.client / 'trasc-client.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Import a client ZIP'):
            self.install({'Stone/EQUI_Inventory.xml': XML})
        self.assertFalse(client_ui.status(self.engine)['client_imported'])
        (self.client / 'trasc-client.json').write_text('{}')
        for name in ('../skin.zip', 'sources/skin.zip', '/tmp/skin.zip'):
            with self.assertRaises(ValueError):
                client_ui.install(self.engine, {'file': name})
        for name in ('../out', 'Default', 'CON', 'trail.', 'abc:def'):
            with self.assertRaises(ValueError):
                self.install({'Stone/EQUI_Inventory.xml': XML}, name=name)

    def test_xml_entities_and_limits_rejected_before_live_changes(self):
        files = {'Stone/EQUI_Inventory.xml': b'<!DOCTYPE XML [<!ENTITY a "x">]><XML>&a;</XML>'}
        with self.assertRaisesRegex(ValueError, 'entity declarations'):
            self.install(files)
        for encoding in ('utf-16', 'utf-16-le', 'utf-16-be', 'utf-8'):
            with self.subTest(encoding=encoding):
                with self.assertRaisesRegex(ValueError, 'entity declarations'):
                    self.install({'Stone/EQUI_Inventory.xml': files['Stone/EQUI_Inventory.xml'].decode().encode(encoding)})
        with self.assertRaisesRegex(ValueError, 'EQ interface XML'):
            self.install({'Stone/EQUI_Inventory.xml': b'<NonUiConfiguration/>'})
        with patch.object(client_ui, 'MAX_XML_BYTES', 8):
            with self.assertRaisesRegex(ValueError, '8 MiB'):
                self.install({'Stone/EQUI_Inventory.xml': XML})
        with patch.object(client_ui, 'MAX_BYTES', 4):
            with self.assertRaisesRegex(ValueError, '512 MiB'):
                self.install({'Stone/EQUI_Inventory.xml': XML})

    def test_valid_utf16_xml_is_preserved(self):
        for index, encoding in enumerate(('utf-16', 'utf-16-le', 'utf-16-be')):
            name = 'Unicode' + str(index)
            xml = '<XML><Screen item="Inventory"/></XML>'.encode(encoding)
            self.install({name + '/EQUI_Inventory.xml': xml})
            self.assertEqual((self.client / 'UIFILES' / name / 'EQUI_Inventory.xml').read_bytes(), xml)

    def test_cancel_during_preparation_never_touches_existing_skin(self):
        self.install({'Stone/EQUI_Inventory.xml': XML})
        self.engine.cancel.set()
        with self.assertRaisesRegex(ValueError, 'cancel'):
            self.install({'Stone/EQUI_Inventory.xml': NEW_XML}, replace=True)
        self.assertEqual((self.client / 'UIFILES/Stone/EQUI_Inventory.xml').read_bytes(), XML)
        self.assertEqual(list((self.engine.work / 'client').glob('ui-import-*')), [])

    def test_second_skin_activation_failure_rolls_back_both_first_and_second(self):
        self.install({'First/EQUI_Inventory.xml': XML, 'Second/EQUI_Inventory.xml': XML})
        original = os.replace
        def fail(source, target):
            if Path(source).parent.name == 'prepared' and Path(source).name == 'Second':
                raise OSError('storage failure')
            return original(source, target)
        with patch.object(client_ui.os, 'replace', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'storage failure'):
                self.install({'First/EQUI_Inventory.xml': NEW_XML, 'Second/EQUI_Inventory.xml': NEW_XML}, replace=True)
        for name in ('First', 'Second'):
            self.assertEqual((self.client / 'UIFILES' / name / 'EQUI_Inventory.xml').read_bytes(), XML)
        self.assertFalse((self.engine.work / 'run/client-ui-import.json').exists())

    def test_restart_recovers_interrupted_partial_swap(self):
        self.install({'Stone/EQUI_Inventory.xml': XML})
        identity = 'a' * 24
        saved = self.engine.work / 'backups/client-ui' / identity / 'Stone'
        saved.parent.mkdir()
        os.replace(self.client / 'UIFILES/Stone', saved)
        stage = self.engine.work / 'client' / ('ui-import-' + identity)
        stage.mkdir()
        atomic_json(self.engine.work / 'run/client-ui-import.json',
                    {'format': 1, 'profile': 'custom', 'id': identity,
                     'skins': [{'name': 'Stone', 'previous': True}, {'name': 'Other', 'previous': False}]})
        restarted = Engine(self.engine.work)
        self.assertEqual((self.client / 'UIFILES/Stone/EQUI_Inventory.xml').read_bytes(), XML)
        self.assertTrue(restarted.state()['client']['ui']['imported'])
        self.assertFalse(stage.exists())
        self.assertFalse((self.engine.work / 'run/client-ui-import.json').exists())

    def test_restart_keeps_fully_committed_set_and_its_backup(self):
        self.install({'Stone/EQUI_Inventory.xml': XML})
        result = self.install({'Stone/EQUI_Inventory.xml': NEW_XML}, replace=True)
        marker = result['installed'][0]
        identity = marker['transaction']
        atomic_json(self.engine.work / 'run/client-ui-import.json',
                    {'format': 1, 'profile': 'custom', 'id': identity,
                     'skins': [{'name': 'Stone', 'previous': True}]})
        client_ui.recover(self.engine)
        self.assertEqual((self.client / 'UIFILES/Stone/EQUI_Inventory.xml').read_bytes(), NEW_XML)
        self.assertEqual((self.engine.work / marker['backup'] / 'EQUI_Inventory.xml').read_bytes(), XML)


if __name__ == '__main__':
    unittest.main()
