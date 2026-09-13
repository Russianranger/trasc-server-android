import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine
from managed_content import NEKTULOS
from rule_catalog import parse_source, validate_value


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine = Engine(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def maps(self):
        for name in NEKTULOS:
            for prefix, contents in (('maps/', 'original '), ('maps/legacy/', 'legacy ')):
                path = self.root / (prefix + name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents + name)

    def test_nektulos_pair_apply_repeat_and_revert_preserve_originals(self):
        self.maps()
        result = self.engine.fix_nektulos({})
        self.engine.fix_nektulos({})
        for name in NEKTULOS:
            self.assertEqual((self.root / 'maps' / name).read_text(), 'legacy ' + name)
            self.assertEqual((self.root / result['backup'] / name).read_text(), 'original ' + name)
        self.engine.revert_nektulos({})
        for name in NEKTULOS:
            self.assertEqual((self.root / 'maps' / name).read_text(), 'original ' + name)
        self.assertFalse(self.engine.nektulos_status()['applied'])

    def test_missing_legacy_file_changes_neither_live_file(self):
        self.maps()
        (self.root / 'maps/legacy/nav/nektulos.nav').unlink()
        with self.assertRaises(ValueError): self.engine.fix_nektulos({})
        for name in NEKTULOS:
            self.assertEqual((self.root / 'maps' / name).read_text(), 'original ' + name)

    def test_reapply_detects_intervening_map_import_or_edit(self):
        self.maps()
        self.engine.fix_nektulos({})
        (self.root / 'maps/base/nektulos.map').write_text('later map import')
        with self.assertRaisesRegex(ValueError, 'changed since Apply'): self.engine.fix_nektulos({})
        self.engine.revert_nektulos({})
        saved = list((self.root / 'backups/nektulos').glob('before-revert-*/base/nektulos.map'))
        self.assertEqual(saved[0].read_text(), 'later map import')

    def test_second_map_copy_failure_rolls_back_both_files(self):
        self.maps()
        copy = shutil.copy2
        def fail_second(src, dest, *args, **kwargs):
            if str(dest).endswith('nektulos.nav.replacing'): raise OSError('simulated storage failure')
            return copy(src, dest, *args, **kwargs)
        with patch('managed_content.shutil.copy2', side_effect=fail_second):
            with self.assertRaises(OSError): self.engine.fix_nektulos({})
        for name in NEKTULOS:
            self.assertEqual((self.root / 'maps' / name).read_text(), 'original ' + name)

    def test_interrupted_apply_recovers_original_pair(self):
        self.maps()
        self.engine.fix_nektulos({})
        marker = self.root / 'backups/nektulos/current.json'
        data = json.loads(marker.read_text()); data['state'] = 'applying'; marker.write_text(json.dumps(data))
        self.engine.recover_nektulos()
        for name in NEKTULOS:
            self.assertEqual((self.root / 'maps' / name).read_text(), 'original ' + name)

    def test_corrupt_map_backup_does_not_replace_either_live_file(self):
        self.maps()
        result = self.engine.fix_nektulos({})
        (self.root / result['backup'] / 'nav/nektulos.nav').write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum'): self.engine.revert_nektulos({})
        for name in NEKTULOS:
            self.assertEqual((self.root / 'maps' / name).read_text(), 'legacy ' + name)

    def test_map_actions_blocked_while_server_running(self):
        self.maps()
        with patch.object(self.engine, 'server_running', return_value=True):
            for method in (self.engine.fix_nektulos, self.engine.revert_nektulos):
                with self.assertRaisesRegex(ValueError, 'Stop the server'): method({})

    def test_client_import_deletes_only_app_archive_and_recognizes_dll(self):
        original = self.root / 'original.zip'
        with zipfile.ZipFile(original, 'w') as z:
            z.writestr('ROF2/EQGame.exe', b'MZclient')
            z.writestr('ROF2/DINPUT8.DLL', b'MZdll')
            z.writestr('ROF2/Resources/test.txt', 'test')
        local = self.root / 'incoming/client.zip'; shutil.copy2(original, local)
        result = self.engine.import_client_zip({'file': 'client.zip'})
        self.assertTrue(result['client']['dinput8_present'])
        self.assertTrue(original.exists()); self.assertFalse(local.exists())
        self.assertEqual((self.root / 'client/current/EQGame.exe').read_bytes(), b'MZclient')
        self.assertFalse(result['client']['launch_available'])

    def test_invalid_client_preserves_previous_installation_and_cleans_staging(self):
        current = self.root / 'client/current'; current.mkdir(); (current / 'keep').write_text('old client')
        local = self.root / 'incoming/invalid.zip'
        with zipfile.ZipFile(local, 'w') as z: z.writestr('../escape', 'unsafe')
        with self.assertRaises(ValueError): self.engine.import_client_zip({'file': 'invalid.zip'})
        self.assertTrue((current / 'keep').exists()); self.assertFalse(local.exists())
        self.assertEqual(list((self.root / 'client').glob('import-*')), [])


class RuleCatalogTests(unittest.TestCase):
    def setUp(self):
        self.rules = parse_source('''
// RULE_INT(Fake, Ignored, 5, "comment")
RULE_INT(World, MaxClientsPerIP, -1, "-1 disables the limit")
RULE_REAL(Character, FinalRaidExpMultiplier, 0.0000000000001, "XP")
RULE_REAL(Character, RaidExpMultiplier, 0.3, "Raid penalty fraction")
RULE_REAL(Character, TradeskillUpMinChance, 25.0f, "Cannot go below 2.5")
RULE_BOOL(Zone, StateSavingOnShutdown, true, "Persist zones")
RULE_STRING(Custom, Welcome, "hello, world", "Quoted \\"text\\" " "and more")
RULE_INT(Test, Bound, 2, "Valid range: 1 to 9")
''')

    def test_types_multiline_strings_and_comments(self):
        self.assertNotIn('Fake:Ignored', self.rules)
        self.assertEqual(self.rules['Custom:Welcome']['default'], 'hello, world')
        self.assertIn('and more', self.rules['Custom:Welcome']['description'])

    def test_sentinels_tiny_numbers_and_unbounded_custom_xp(self):
        for name, value in (('World:MaxClientsPerIP', '-1'), ('Character:FinalRaidExpMultiplier', '1e-13'), ('Character:FinalRaidExpMultiplier', '150')):
            self.assertEqual(validate_value(name, value, self.rules[name]), value)

    def test_field_specific_bounds_and_types(self):
        for name, value in (('Test:Bound', '10'), ('Character:TradeskillUpMinChance', '2.4'), ('Character:RaidExpMultiplier', '1.01'), ('World:MaxClientsPerIP', '1.5'), ('World:MaxClientsPerIP', '2147483648'), ('Character:FinalRaidExpMultiplier', 'NaN'), ('Character:FinalRaidExpMultiplier', '1e-100')):
            with self.assertRaisesRegex(ValueError, name): validate_value(name, value, self.rules[name])

if __name__ == '__main__': unittest.main()
