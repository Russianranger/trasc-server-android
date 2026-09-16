"""Real export entry point: both installed copies, complete data, and rollback."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine, CLIENT_FILES
import managed_content


class ClientExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root)
        self.client = self.root/'client/current'
        self.data = {name: b'full export\r\n'+name.encode()+b'\xff\n' for name in CLIENT_FILES}
        self.data['spells_us.txt'] = b''.join(b'^'.join([str(i).encode()]+[b'0']*236)+b'\r\n' for i in (26, 200, 50000, 50007))
        for method in ('ensure_db', 'write_config'):
            patcher = patch.object(self.engine, method)
            patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(self.engine, 'run', side_effect=self.exporter)
        patcher.start(); self.addCleanup(patcher.stop)

    def exporter(self, *args, **kwargs):
        folder = self.root/'server/export'; folder.mkdir(parents=True, exist_ok=True)
        for name, data in self.data.items(): (folder/name).write_bytes(data)

    def import_client(self):
        self.client.mkdir()
        (self.client/'trasc-client.json').write_text('{"imported":true}')

    def test_export_overwrites_all_eight_case_insensitive_paths_and_backs_up_originals(self):
        self.import_client()
        (self.client/'rEsOuRcEs').mkdir()
        originals = {}
        for parent in (self.client, self.client/'rEsOuRcEs'):
            for name in CLIENT_FILES:
                target = parent/name.upper()
                originals[target] = b'original '+str(target.relative_to(self.client)).encode()
                target.write_bytes(originals[target])
        for name in ('eqhost.txt', 'eqclient.ini', 'dinput8.dll'):
            (self.client/name).write_bytes(b'keep '+name.encode())
        result = self.engine.export_client({})
        self.assertTrue(result['local_client_synced']); self.assertEqual(result['copied_files'], 8)
        self.assertFalse(result['filter_applied'])
        backup = self.root/result['backup']
        for target, original in originals.items():
            canonical = next(n for n in CLIENT_FILES if n.lower() == target.name.lower())
            self.assertEqual(target.read_bytes(), self.data[canonical])
            self.assertEqual((backup/target.relative_to(self.client)).read_bytes(), original)
        self.assertFalse((self.client/'Resources').exists())
        self.assertFalse((self.client/'spells_us.txt').exists())
        for name in ('eqhost.txt', 'eqclient.ini', 'dinput8.dll'):
            self.assertEqual((self.client/name).read_bytes(), b'keep '+name.encode())
        record = json.loads((backup/'manifest.json').read_text())
        self.assertEqual(record['state'], 'applied'); self.assertEqual(len(record['files']), 8)
        self.assertEqual(json.loads((self.root/'logs/client-data-sync.json').read_text()), result)
        with zipfile.ZipFile(self.root/result['file']) as archive:
            for name, data in self.data.items():
                self.assertEqual(archive.read(name), data)
                self.assertEqual(archive.read('Resources/'+name), data)
                self.assertEqual(result['sha256'][name], hashlib.sha256(data).hexdigest())

    def test_missing_resources_is_created_and_repeat_exports_keep_separate_backups(self):
        self.import_client()
        first = self.engine.export_client({})
        self.data['dbstr_us.txt'] = b'newer export'
        second = self.engine.export_client({})
        self.assertNotEqual(first['backup'], second['backup'])
        self.assertNotEqual(first['file'], second['file'])
        for name, data in self.data.items():
            for relative in (name, 'Resources/'+name):
                self.assertEqual((self.client/relative).read_bytes(), data)
        self.assertEqual((self.root/second['backup']/'dbstr_us.txt').read_bytes(), b'full export\r\ndbstr_us.txt\xff\n')

    def test_without_import_export_still_produces_full_zip(self):
        result = self.engine.export_client({})
        self.assertFalse(result['local_client_synced']); self.assertEqual(result['copied_files'], 0)
        self.assertFalse(self.client.exists())
        with zipfile.ZipFile(self.root/result['file']) as archive:
            self.assertEqual(archive.read('Resources/spells_us.txt'), self.data['spells_us.txt'])

    def test_invalid_destinations_reject_before_any_export_or_replacement(self):
        self.import_client()
        original = self.client/'spells_us.txt'; original.write_bytes(b'original')
        resources = self.client/'Resources'
        outside = self.root/'other'; outside.mkdir()
        scenarios = ('linked_resources', 'ambiguous_resources', 'resources_file', 'linked_data', 'ambiguous_data', 'data_directory')
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                if scenario == 'linked_resources': resources.symlink_to(outside, target_is_directory=True)
                elif scenario == 'resources_file': resources.write_text('invalid folder')
                else: resources.mkdir()
                if scenario == 'ambiguous_resources': (self.client/'resources').mkdir()
                if scenario == 'linked_data': (resources/'dbstr_us.txt').symlink_to(original)
                if scenario == 'ambiguous_data': (self.client/'SPELLS_US.TXT').write_bytes(b'collision')
                if scenario == 'data_directory': (resources/'BaseData.txt').mkdir()
                with self.assertRaises(ValueError): self.engine.export_client({})
                self.assertEqual(original.read_bytes(), b'original')
                self.engine.run.assert_not_called()
                for path in (resources/'dbstr_us.txt', self.client/'SPELLS_US.TXT'):
                    if path.is_symlink() or path.is_file(): path.unlink()
                if (resources/'BaseData.txt').is_dir(): (resources/'BaseData.txt').rmdir()
                if (self.client/'resources').exists(): (self.client/'resources').rmdir()
                if resources.is_symlink() or resources.is_file(): resources.unlink()
                else: resources.rmdir()

    def test_linked_client_is_rejected_even_when_target_is_inside_workspace(self):
        self.import_client()
        other = self.client.with_name('other'); self.client.rename(other)
        self.client.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlinks'): self.engine.export_client({})
        self.engine.run.assert_not_called()

    def test_cancel_rolls_back_replacements_and_removes_new_files_and_folder(self):
        self.import_client()
        (self.client/'spells_us.txt').write_bytes(b'original')
        with patch.object(self.engine, 'check_cancel', side_effect=[None, None, RuntimeError('cancelled')]):
            with self.assertRaisesRegex(RuntimeError, 'cancelled'): self.engine.export_client({})
        self.assertEqual((self.client/'spells_us.txt').read_bytes(), b'original')
        self.assertFalse((self.client/'Resources').exists())
        manifest = next((self.root/'backups/client-setup').glob('*/manifest.json'))
        self.assertEqual(json.loads(manifest.read_text())['state'], 'rolled_back')
        self.assertFalse((self.root/'logs/client-data-sync.json').exists())

    def test_failed_copy_restores_both_originals_and_cleans_staging_files(self):
        self.import_client(); (self.client/'Resources').mkdir()
        for parent in (self.client, self.client/'Resources'):
            (parent/'spells_us.txt').write_bytes(b'old '+parent.name.encode())
        real_copy = managed_content.shutil.copy2
        def fail(source, target, *args, **kwargs):
            if Path(source) == self.root/'server/export/dbstr_us.txt':
                Path(target).write_bytes(b'partial'); raise OSError('copy failed')
            return real_copy(source, target, *args, **kwargs)
        with patch.object(managed_content.shutil, 'copy2', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'copy failed'): self.engine.export_client({})
        for parent in (self.client, self.client/'Resources'):
            self.assertEqual((parent/'spells_us.txt').read_bytes(), b'old '+parent.name.encode())
            self.assertFalse((parent/'dbstr_us.txt').exists())
        self.assertEqual(list(self.client.rglob('.trasc-*')), [])

    def test_incomplete_export_does_not_touch_local_files(self):
        self.import_client(); (self.client/'spells_us.txt').write_bytes(b'original')
        self.data.pop('BaseData.txt')
        with self.assertRaisesRegex(ValueError, 'BaseData.txt'): self.engine.export_client({})
        self.assertEqual((self.client/'spells_us.txt').read_bytes(), b'original')
        self.assertFalse((self.client/'Resources').exists())


if __name__ == '__main__': unittest.main()
