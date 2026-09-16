"""Reversible on-device comparison, including partial writes and recovery."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_spells
import managed_content
from engine import Engine


def row(i):
    fields = [b'0'] * 237
    fields[0] = str(i).encode(); fields[1] = b'Unchanged \xe9'
    fields[145] = b'216' if i == 26 else b'278'
    return b'^'.join(fields) + b'\r\n'


class SpellComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name); self.engine = Engine(self.work)
        self.client = self.work / 'client/current'; self.client.mkdir()
        (self.client / 'trasc-client.json').write_text('{"imported":true}')
        (self.client / 'rEsOuRcEs').mkdir()
        self.paths = [self.client/'SPELLS_US.TXT', self.client/'rEsOuRcEs/Spells_Us.txt']
        self.kept = b'\xef\xbb\xbf'+row(26)+row(200)+row(44999)
        self.full = self.kept + b''.join(row(i) for i in range(50000,50008))
        for path in self.paths: path.write_bytes(self.full)
        self.export = self.work/'server/export/spells_us.txt'
        self.export.parent.mkdir(parents=True); self.export.write_bytes(self.full)
        self.other = self.client/'dbstr_us.txt'; self.other.write_bytes(b'unchanged')

    def test_apply_restart_idempotence_launch_evidence_and_restore(self):
        result = self.engine.dispatch('apply_spell_test', {})
        record = result['spell_test']
        for p in self.paths: self.assertEqual(p.read_bytes(), self.kept)
        self.assertEqual(self.export.read_bytes(), self.full)
        self.assertEqual(self.other.read_bytes(), b'unchanged')
        evidence = client_spells.verify_installed_test(self.client, record)
        self.assertEqual([x['rows'] for x in evidence['installed']], [3, 3])
        self.assertEqual(record['excluded_ids'], list(range(50000,50008)))
        self.assertEqual(record['reported_spells']['26']['spell_animation'], 216)
        restarted = Engine(self.work)
        self.assertEqual(restarted.apply_spell_test({})['spell_test']['backup_id'], record['backup_id'])
        self.assertEqual(restarted.client_status()['spell_test']['state'], 'applied')
        restarted.dispatch('restore_spell_test', {})
        for p in self.paths: self.assertEqual(p.read_bytes(), self.full)
        self.assertEqual(client_spells.test_record(self.work)['state'], 'restored')
        self.assertEqual(json.loads((self.work/'logs/client-spell-test.json').read_text())['state'], 'restored')
        self.assertIn('No spell exclusion', restarted.restore_spell_test({})['message'])

    def test_no_other_client_mutations_while_active(self):
        self.engine.apply_spell_test({})
        for op in ('export_client', 'prepare_client', 'import_client_zip'):
            with self.assertRaisesRegex(ValueError, 'Restore full spell'):
                self.engine.dispatch(op, {})
        for p in self.paths: self.assertEqual(p.read_bytes(), self.kept)

    def test_mismatch_and_unexpected_high_ids_leave_originals_intact(self):
        for bad in (self.full+b'\n', self.full+row(50008), self.kept+row(45000)):
            self.paths[1].write_bytes(bad)
            with self.assertRaises(ValueError): self.engine.apply_spell_test({})
            self.assertEqual(self.paths[0].read_bytes(), self.full)
            self.assertEqual(self.paths[1].read_bytes(), bad)
        for p in self.paths: p.write_bytes(self.full+row(50008))
        with self.assertRaisesRegex(ValueError, 'exactly spell IDs'): self.engine.apply_spell_test({})
        self.assertFalse(client_spells.test_active(self.work))

    def test_cancel_and_second_replace_failure_restore_both(self):
        real = managed_content.replace_client_file
        for failure in ('cancel', 'io'):
            calls = 0
            def replace(target, value):
                nonlocal calls
                if target in self.paths and value == self.kept:
                    calls += 1
                    if calls == 2: raise OSError('injected second replacement failure')
                return real(target, value)
            cancels = 0
            def cancel():
                nonlocal cancels
                cancels += 1
                if cancels == 2: raise RuntimeError('injected cancellation')
            if failure == 'cancel':
                with patch.object(self.engine, 'check_cancel', side_effect=cancel):
                    with self.assertRaisesRegex(RuntimeError, 'cancellation'): self.engine.apply_spell_test({})
            else:
                with patch.object(managed_content, 'replace_client_file', side_effect=replace):
                    with self.assertRaisesRegex(OSError, 'replacement failure'): self.engine.apply_spell_test({})
            for p in self.paths: self.assertEqual(p.read_bytes(), self.full)
            self.assertEqual(client_spells.test_record(self.work)['state'], 'restored')

    def test_interrupted_apply_and_restore_block_launch_and_can_resume(self):
        self.engine.apply_spell_test({})
        record = client_spells.test_record(self.work); record['state'] = 'applying'
        client_spells._save_test(self.work, record)
        self.paths[0].write_bytes(self.full)  # Simulate death between replacements.
        with self.assertRaisesRegex(ValueError, 'interrupted'): client_spells.verify_installed_test(self.client, record)
        real = managed_content.replace_client_file
        def fail(target, data):
            if target == self.paths[1]: raise OSError('restore interrupted')
            return real(target, data)
        with patch.object(managed_content, 'replace_client_file', side_effect=fail):
            with self.assertRaises(OSError): self.engine.restore_spell_test({})
        self.assertEqual(client_spells.test_record(self.work)['state'], 'restoring')
        Engine(self.work).restore_spell_test({})
        for p in self.paths: self.assertEqual(p.read_bytes(), self.full)

    def test_corrupt_backup_and_intervening_changes_are_not_overwritten(self):
        record = self.engine.apply_spell_test({})['spell_test']
        backup = self.work/'backups/client-spell-test'/record['backup_id']/'resources.txt'
        backup.write_bytes(b'bad backup')
        with self.assertRaisesRegex(ValueError, 'checksum'): self.engine.restore_spell_test({})
        for p in self.paths: self.assertEqual(p.read_bytes(), self.kept)
        backup.write_bytes(self.full)
        self.paths[1].write_bytes(self.kept+b'\n')
        with self.assertRaisesRegex(ValueError, 'changed outside'): self.engine.restore_spell_test({})
        with self.assertRaisesRegex(ValueError, 'files changed'): client_spells.verify_installed_test(self.client, record)
        self.assertEqual(self.paths[1].read_bytes(), self.kept+b'\n')

    def test_symlink_and_ambiguous_case_rejected_before_writes(self):
        duplicate = self.client/'spells_us.txt'; duplicate.write_bytes(self.full)
        with self.assertRaisesRegex(ValueError, 'ambiguous'): self.engine.apply_spell_test({})
        duplicate.unlink(); self.paths[1].unlink(); self.paths[1].symlink_to(self.export)
        with self.assertRaisesRegex(ValueError, 'linked'): self.engine.apply_spell_test({})
        self.assertEqual(self.paths[0].read_bytes(), self.full)
        self.assertEqual(self.export.read_bytes(), self.full)


if __name__ == '__main__': unittest.main()
