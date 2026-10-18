"""Synthetic-only exact port parity and reversible filesystem qualification."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import tracemalloc
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_connection as connection
import client_spellbook as spellbook


def synthetic(laa=False, relocation_small=False):
    """Invented PE; no EverQuest executable/code outside published patch guards."""
    raw = bytearray(spellbook.BASE_SIZE)
    raw[:2] = b'MZ'
    struct.pack_into('<I', raw, 0x3c, 0x80)
    raw[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', raw, 0x84, 0x14c, 2)
    struct.pack_into('<HH', raw, 0x94, 224, 0x103 | (0x20 if laa else 0))
    opt = 0x98
    struct.pack_into('<H', raw, opt, 0x10b)
    struct.pack_into('<I', raw, opt+28, 0x400000)
    struct.pack_into('<I', raw, opt+56, 0x900000)
    struct.pack_into('<II', raw, opt+96+5*8, 0x880000, 0x100)
    tab = opt+224
    raw[tab:tab+8] = b'.text\0\0\0'
    struct.pack_into('<IIII', raw, tab+8, 0x800000, 0x1000, 0x800000, 0x400)
    raw[tab+40:tab+48] = b'.reloc\0\0'
    struct.pack_into('<IIII', raw, tab+48, 0x100 if relocation_small else 0x800,
                     0x880000, 0x800, 0x801000)
    for row in spellbook.TABLE:
        offset = int(row['va'], 16)-0x400000-0x1000+0x400
        before = bytes.fromhex(row['expect'])
        raw[offset:offset+len(before)] = before
    offset = 0x57cbd1-0x400000-0x1000+0x400
    hook = bytes.fromhex('68d00200008d97bc1a0000528bcee8') + struct.pack('<I', (0x57b600-0x57cbe4) & 0xffffffff)
    raw[offset:offset+len(hook)] = hook
    offset = 0x578fd6-0x400000-0x1000+0x400
    raw[offset:offset+7] = bytes.fromhex('8bbcb3bc1a0000')
    return bytes(raw)


class AlgorithmTests(unittest.TestCase):
    def test_table_pinned_and_all_sites_present(self):
        self.assertEqual(len(spellbook.TABLE), 115)
        self.assertEqual(hashlib.sha256(json.dumps(spellbook.TABLE, sort_keys=True, separators=(',', ':')).encode()).hexdigest(), spellbook.TABLE_SHA256)

    def test_node_reference_byte_for_byte_stock_laa_and_relocation_growth(self):
        self.assertIsNotNone(shutil.which('node'), 'Node is required for independent upstream patch parity')
        fixture = Path(__file__).parent/'fixtures/spellbook-patch-reference.js'
        script = "const fs=require('fs');const p=require(process.argv[1]);const j=JSON.parse(fs.readFileSync(0,'utf8'));fs.writeFileSync(process.argv[3],p.build(fs.readFileSync(process.argv[2]),j.table,j.setLaa));"
        with tempfile.TemporaryDirectory() as folder:
            source, dest = Path(folder)/'synthetic.exe', Path(folder)/'patched.exe'
            for laa, set_laa, growth in ((False, True, False), (True, False, False), (False, False, True)):
                with self.subTest(laa=laa, set_laa=set_laa, relocation_growth=growth):
                    raw = synthetic(laa, growth)
                    source.write_bytes(raw)
                    subprocess.run(['node', '-e', script, str(fixture), str(source), str(dest)], input=json.dumps({'table': spellbook.TABLE, 'setLaa': set_laa}), text=True, check=True, capture_output=True)
                    actual = spellbook.build(raw, set_laa)
                    self.assertEqual(actual, dest.read_bytes())
                    self.assertEqual(len(actual), len(raw)+512)
                    pe = spellbook.parse_pe(actual)
                    self.assertEqual(pe['count'], 3)
                    self.assertEqual(pe['sections'][-1]['name'], '.sbook')
                    for row in spellbook.TABLE:
                        offset = int(row['va'], 16)-0x400000-0x1000+0x400
                        after = bytes.fromhex(row['replace'])
                        self.assertEqual(actual[offset:offset+len(after)], after)

    def test_each_byte_guard_rejects_modified_site(self):
        good = synthetic()
        for row in spellbook.TABLE:
            with self.subTest(va=row['va']):
                raw = bytearray(good)
                offset = int(row['va'], 16)-0x400000-0x1000+0x400
                raw[offset] ^= 1
                with self.assertRaises(ValueError):
                    spellbook.build(raw)

    def test_profile_hooks_header_and_relocation_guards(self):
        good = synthetic()
        for offset in (0x57cbd1-0x400000-0x1000+0x400,
                       0x578fd6-0x400000-0x1000+0x400,
                       0x98+224+80, 0x98+96+5*8):
            with self.subTest(offset=offset):
                raw = bytearray(good); raw[offset] ^= 1
                with self.assertRaises(ValueError):
                    spellbook.build(raw)
        raw = bytearray(good)
        struct.pack_into('<I', raw, 0x98+96+5*8+4, 0x800)
        with self.assertRaisesRegex(ValueError, 'relocation-section'):
            spellbook.build(raw)
        with self.assertRaisesRegex(ValueError, 'already'):
            spellbook.build(spellbook.build(good))

    def test_malformed_pe_refused(self):
        for raw in (b'', b'MZ'+b'\0'*1024, synthetic()[:1024]):
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                spellbook.build(raw)

    def test_full_size_patch_has_bounded_memory(self):
        raw = synthetic(True)
        tracemalloc.start()
        try:
            result = spellbook.build(raw)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual(len(result), spellbook.PATCHED_SIZE)
        self.assertLess(peak, 32 * 1024**2)


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = synthetic(True)
        cls.original_hash = connection.sha(cls.original)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.client = self.work/'client/current'
        self.client.mkdir(parents=True)
        self.path = self.client/'eqgame.exe'
        self.path.write_bytes(self.original)
        self.path.chmod(0o755)
        self.marker = self.client/'trasc-client.json'
        self.marker.write_text(json.dumps({'executable': 'eqgame.exe', 'imported': True, 'imported_at': 10}))
        self.engine = types.SimpleNamespace(work=self.work, profile='custom', cancel=threading.Event(), server_running=lambda: False)
        self.base_patch = patch.object(spellbook, 'BASE_SHA256', self.original_hash)
        self.base_patch.start()
        self.addCleanup(self.base_patch.stop)

    def mutate(self, op='client_spellbook_apply', **args):
        args.setdefault('revision', connection.sha(self.path.read_bytes()))
        args.setdefault('confirm_apply', True)
        return spellbook.mutate(self.engine, op, args)

    def test_apply_idempotent_restore_reapply_and_protected_original(self):
        self.assertFalse(spellbook.status(self.engine)['patched'])
        self.assertTrue(spellbook.recognizes_supported_executable(self.path))
        result = self.mutate()
        self.assertTrue(result['patched'])
        self.assertTrue(result['can_apply'])
        self.assertTrue(result['can_restore'])
        self.assertTrue(spellbook.recognizes_supported_executable(self.path))
        patched = self.path.read_bytes()
        backup = self.work/result['backup_path']
        self.assertEqual(backup.read_bytes(), self.original)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o755)
        inode = self.path.stat().st_ino
        self.mutate()
        self.assertEqual(self.path.stat().st_ino, inode)
        with self.assertRaisesRegex(ValueError, 'Confirm restoration'):
            self.mutate('client_spellbook_restore')
        self.mutate('client_spellbook_restore', confirm_restore=True)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.mutate()
        self.assertEqual(self.path.read_bytes(), patched)
        self.assertEqual(backup.read_bytes(), self.original)
        self.assertEqual(len(list((self.work/connection.RECOVERY).glob('*/original'))), 1)

    def test_only_exact_base_and_laa_bit_variant_are_allowed(self):
        raw = bytearray(self.original)
        offset, _ = connection.pe_info(raw)
        raw[offset] ^= 0x20
        self.path.write_bytes(raw)
        self.assertTrue(spellbook.status(self.engine)['can_apply'])
        self.mutate()
        self.assertTrue(spellbook.status(self.engine)['patched'])
        self.mutate('client_spellbook_restore', confirm_restore=True)
        raw[-1] ^= 1
        self.path.write_bytes(raw)
        self.assertFalse(spellbook.status(self.engine)['supported'])
        with self.assertRaisesRegex(ValueError, 'not the verified'):
            self.mutate()

    def test_legacy_4gb_restore_then_spellbook_reapply_preserves_first_original(self):
        # Establish a genuine legacy 4 GB recovery record from the exact
        # opposite LAA-bit variant before creating the spellbook record.
        stock = bytearray(self.original)
        flag, _ = connection.pe_info(stock)
        stock[flag] ^= 0x20
        stock = bytes(stock)
        self.path.write_bytes(stock)
        connection.mutate(self.engine, 'client_4gb_apply', {'revision': connection.sha(stock)})
        first = self.mutate()
        patched = self.path.read_bytes()
        retained = self.work/first['backup_path']
        retained_inode = retained.stat().st_ino
        self.assertEqual(retained.read_bytes(), self.original)
        self.mutate('client_spellbook_restore', confirm_restore=True)
        connection.mutate(self.engine, 'client_4gb_restore', {'revision': connection.sha(self.path.read_bytes())})
        self.assertEqual(self.path.read_bytes(), stock)
        self.assertTrue(spellbook.status(self.engine)['can_apply'])
        result = self.mutate()
        self.assertTrue(result['patched'])
        self.assertEqual(self.path.read_bytes(), patched)
        self.assertEqual(result['backup_path'], first['backup_path'])
        self.assertEqual(retained.stat().st_ino, retained_inode)
        self.assertEqual(retained.read_bytes(), self.original)
        self.assertEqual(len(list((self.work/connection.RECOVERY).glob('*/original'))), 2)
        # Both old controls can be used again after spellbook restoration.
        self.mutate('client_spellbook_restore', confirm_restore=True)
        connection.mutate(self.engine, 'client_4gb_restore', {'revision': connection.sha(self.path.read_bytes())})
        connection.mutate(self.engine, 'client_4gb_apply', {'revision': connection.sha(self.path.read_bytes())})
        self.mutate()
        self.assertEqual(self.path.read_bytes(), patched)
        self.assertEqual(retained.read_bytes(), self.original)
        self.assertEqual(retained.stat().st_ino, retained_inode)

    def test_base_variant_record_admission_refuses_any_unrelated_change(self):
        result = self.mutate()
        self.mutate('client_spellbook_restore', confirm_restore=True)
        _, path, identity, raw, record, _ = spellbook._inspect(self.engine)
        altered = bytearray(raw)
        flag, _ = connection.pe_info(altered)
        altered[flag] ^= 0x20
        altered[-1] ^= 1
        before = json.dumps(record, sort_keys=True)
        with self.assertRaisesRegex(ValueError, 'outside the supported'):
            spellbook._retain_base_variant(self.engine, path, identity, bytes(altered), record)
        after = connection.recovery(self.engine, spellbook.KIND, path, identity)
        self.assertEqual(json.dumps(after, sort_keys=True), before)
        self.assertEqual((self.work/result['backup_path']).read_bytes(), self.original)

    def test_wrong_profile_process_and_confirmation_guards(self):
        for profile in ('traditional', 'takp'):
            self.engine.profile = profile
            self.assertFalse(spellbook.status(self.engine)['can_apply'])
            with self.assertRaisesRegex(ValueError, 'Custom'):
                self.mutate()
        self.engine.profile = 'custom'
        self.engine.server_running = lambda: True
        with self.assertRaisesRegex(ValueError, 'Stop the server'):
            self.mutate()
        self.engine.server_running = lambda: False
        active = self.work/'run/client-active.json'; active.parent.mkdir()
        active.write_text(json.dumps({'pid': os.getpid()}))
        with self.assertRaisesRegex(ValueError, 'Stop the client'):
            self.mutate()
        active.unlink()
        with self.assertRaisesRegex(ValueError, 'Confirm the'):
            self.mutate(confirm_apply=False)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_stale_revision_and_cancellation_leave_original(self):
        with self.assertRaisesRegex(ValueError, 'Refresh compatibility'):
            self.mutate(revision='0'*64)
        self.engine.cancel.set()
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.mutate()
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse((self.work/connection.RECOVERY).exists())

    def test_atomic_failure_retains_verified_backup_and_can_retry(self):
        atomic = connection.atomic
        def fail_client(path, raw, mode=None):
            if path == self.path:
                raise OSError('simulated interrupted replacement')
            return atomic(path, raw, mode)
        with patch.object(connection, 'atomic', side_effect=fail_client), self.assertRaises(OSError):
            self.mutate()
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertTrue(spellbook.status(self.engine)['backup_exists'])
        self.mutate()
        self.assertTrue(spellbook.status(self.engine)['patched'])

    def test_modified_exe_original_or_import_identity_refuses_restore(self):
        state = self.mutate()
        patched = self.path.read_bytes()
        raw = bytearray(patched); raw[-1] ^= 1; self.path.write_bytes(raw)
        self.assertFalse(spellbook.recognizes_supported_executable(self.path))
        with self.assertRaises(ValueError):
            self.mutate('client_spellbook_restore', confirm_restore=True)
        self.path.write_bytes(patched)
        backup = self.work/state['backup_path']
        backup.chmod(0o600); backup.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'checksum failed'):
            self.mutate('client_spellbook_restore', confirm_restore=True)
        backup.write_bytes(self.original)
        self.marker.write_text(json.dumps({'executable': 'eqgame.exe', 'imported': True, 'imported_at': 20}))
        with self.assertRaises(ValueError):
            self.mutate('client_spellbook_restore', confirm_restore=True)

    def test_symlinks_and_ambiguous_exe_are_refused(self):
        self.path.unlink(); self.path.symlink_to(self.work/'outside.exe')
        self.assertFalse(spellbook.status(self.engine)['supported'])
        self.path.unlink(); self.path.write_bytes(self.original)
        (self.client/'EQGAME.EXE').write_bytes(self.original)
        self.assertFalse(spellbook.status(self.engine)['supported'])

    def test_late_external_change_is_not_overwritten(self):
        backup = connection.checked_backup
        changed = b'changed after preview'
        def mutate_after_journal(*args, **kwargs):
            result = backup(*args, **kwargs)
            self.path.write_bytes(changed)
            return result
        with patch.object(connection, 'checked_backup', side_effect=mutate_after_journal), self.assertRaisesRegex(ValueError, 'client changed'):
            self.mutate()
        self.assertEqual(self.path.read_bytes(), changed)


if __name__ == '__main__':
    unittest.main()
