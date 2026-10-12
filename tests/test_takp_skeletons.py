"""Public-format fixtures, reversibility and interrupted asset transactions.

Fixtures contain no EverQuest assets. CRC/XOR known answers were independently
checked against EQEmu/zone-utilities and cjab/libeq primary format sources.
"""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import managed_content
import takp_skeletons as skeletons

KNOWN_CRC = {'gequip5.wld': 0xced37026, 'global6_chr.wld': 0x34a4fde1,
             'texture.bmp': 0x34eeea48, 'foo.wld': 0x9b6cd4d0, 'test.bin': 0x6e36c2ad}
KEY = bytes.fromhex('953ac52a957a956a')


def wld(strings=b'\0SKE\0FOOSKEBAR\0caf\xe9\0', version=0x15500):
    encoded = bytes(value ^ KEY[i % 8] for i, value in enumerate(strings))
    encoded += b'\0' * (-len(encoded) % 4)
    # An unknown fragment's body/trailer must be preserved rather than parsed
    # into JSON and rewritten. The native game references stay byte-identical.
    return struct.pack('<7I', 0x54503d02, version, 1, 42, 1234, len(encoded), 7) + encoded + struct.pack('<IIi', 4, 0x7e, -1) + b'\xff\xff\xff\xff'


def compress_blocks(data):
    blocks = []
    for offset in range(0, len(data), 8192):
        value = data[offset:offset+8192]; compressed = zlib.compress(value)
        blocks.append(struct.pack('<II', len(compressed), len(value)) + compressed)
    return b''.join(blocks)


def archive(wld_name, data=None, footer=b'STEVE\x12\x34\x56\x78', empty=False):
    members = [(wld_name, data if data is not None else wld()), ('texture.bmp', b'Unchanged texture\0SKE' * 1200)]
    if empty: members.append(('test.bin', b''))
    blocks, entries = bytearray(b'gap-before-blocks'), []
    for name, value in members:
        entries.append((KNOWN_CRC[name], 12 + len(blocks), len(value)))
        blocks.extend(compress_blocks(value)); blocks.extend(b'orphan')
    names = list(reversed([name for name, _ in members]))
    directory = struct.pack('<I', len(names)) + b''.join(struct.pack('<I', len(name)+1)+name.encode()+b'\0' for name in names)
    sentinel = (0x61580ac9, 12 + len(blocks), len(directory))
    blocks.extend(compress_blocks(directory))
    # Intentionally unsorted, sentinel in the middle, directory order differs.
    index_entries = [entries[1], sentinel, entries[0]] + entries[2:]
    index = 12 + len(blocks)
    return struct.pack('<I4sI', index, b'PFS ', 0x20000) + blocks + struct.pack('<I', len(index_entries)) + b''.join(struct.pack('<III', *entry) for entry in index_entries) + footer


class FormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def write(self, data, name='gequip5.s3d'):
        path = self.root/name; path.write_bytes(data); return path

    def test_independent_crc_and_xor_known_answers_match_upstream_substitution(self):
        for name, crc in KNOWN_CRC.items(): self.assertEqual(skeletons.filename_crc(name), crc)
        old = bytes.fromhex('95698e6f953cda25c6718068d42895')
        expected = bytes.fromhex('95769661953cda25d9698e68d42895')
        input_data = struct.pack('<7I', 0x54503d02, 0x15500, 1, 0, 0, len(old), 0) + old + struct.pack('<IIi', 4, 0x7e, -1)
        result, count = skeletons.patch_wld(input_data)
        self.assertEqual(result[28:28+len(old)], expected); self.assertEqual(count, 2)
        source = (Path(skeletons.__file__).parent/'takp-skeleton-patcher/upstream-main.rs').read_text()
        self.assertIn('s.replace("SKE", "LSK")', source)
        decoded = bytes(value ^ KEY[i % 8] for i, value in enumerate(old))
        # Independently model upstream's per-string StringHash JSON replace.
        reference = b'\0'.join(part.decode('cp1252').replace('SKE', 'LSK').encode('cp1252') for part in decoded.split(b'\0'))
        self.assertEqual(bytes(value ^ KEY[i % 8] for i, value in enumerate(reference)), expected)

    def test_preserves_ranges_orphans_footer_directory_other_assets_and_wld_offsets(self):
        for version in (0x15500, 0x1000c800):
            for footer in (b'', b'STEVE\x12\x34\x56\x78', b'STEVE\x78\x56\x34\x12'):
                with self.subTest(version=version, footer=footer):
                    source = self.write(archive('gequip5.wld', wld(version=version), footer, True))
                    output = self.root/'patched'; output.unlink(missing_ok=True)
                    original = skeletons.read_archive(source, 'gequip5.wld')
                    count = skeletons.patch_archive(source, output, 'gequip5.wld')
                    changed = skeletons.read_archive(output, 'gequip5.wld')
                    self.assertEqual(count, 2)
                    self.assertEqual(output.read_bytes()[12:original['index']], source.read_bytes()[12:original['index']])
                    self.assertEqual(changed['footer'], footer)
                    self.assertEqual(changed['wld'][:28], original['wld'][:28])
                    end = 28 + struct.unpack_from('<I', original['wld'], 20)[0]
                    self.assertEqual(changed['wld'][end:], original['wld'][end:])
                    self.assertEqual(len(changed['wld']), len(original['wld']))
                    for before, after in zip(original['entries'], changed['entries']):
                        if before[0] != original['target_crc']: self.assertEqual(before, after)

    def test_large_wld_crosses_block_and_xor_boundaries(self):
        source = self.write(archive('gequip5.wld', wld(b'\0' + b'ABCDSKE\0' * 2000)))
        output = self.root/'patched'
        self.assertEqual(skeletons.patch_archive(source, output, 'gequip5.wld'), 2000)
        table = skeletons.read_archive(output, 'gequip5.wld')['wld'][28:16029]
        decoded = bytes(value ^ KEY[i % 8] for i, value in enumerate(table))
        self.assertNotIn(b'SKE', decoded); self.assertIn(b'ABCDLSK', decoded)

    def test_malformed_archive_and_wld_refuse_without_output(self):
        valid = archive('gequip5.wld')
        bad = []
        bad.append(valid[:25]); bad.append(b'BAD!' + valid[4:])
        index = struct.unpack_from('<I', valid)[0]
        duplicate = bytearray(valid); duplicate[index+4:index+16] = duplicate[index+28:index+40]; bad.append(duplicate)
        overlap = bytearray(valid); struct.pack_into('<I', overlap, index+4+4, struct.unpack_from('<I', overlap, index+28+4)[0]); bad.append(overlap)
        bad.append(valid+b'extra')
        bad.append(archive('gequip5.wld', wld(b'\0No model names\0')))
        bad.append(archive('gequip5.wld', wld(version=0x12345678)))
        bad.append(archive('gequip5.wld', wld()[:-10]))
        for data in bad:
            with self.subTest(size=len(data)):
                source = self.write(data); output = self.root/'patched'; output.unlink(missing_ok=True)
                with self.assertRaises(ValueError): skeletons.patch_archive(source, output, 'gequip5.wld')
                self.assertFalse(output.exists())

    def test_bomb_and_oversized_wld_are_bounded_before_decompression(self):
        valid = bytearray(archive('gequip5.wld')); index = struct.unpack_from('<I', valid)[0]
        struct.pack_into('<I', valid, index+28+8, 0xffffffff)
        with self.assertRaisesRegex(ValueError, '512 MiB'): skeletons.read_archive(self.write(valid), 'gequip5.wld')
        data = wld(); size = len(data); compressed = zlib.compress(b'x' * 1000000)
        normal = archive('gequip5.wld'); original = skeletons.read_archive(self.write(normal), 'gequip5.wld')
        target = next(entry for entry in original['entries'] if entry[0] == original['target_crc'])
        bomb = bytearray(normal); struct.pack_into('<II', bomb, target[1], len(compressed), size)
        bomb[target[1]+8:target[1]+8+len(compressed)] = compressed
        with self.assertRaises(ValueError): skeletons.read_archive(self.write(bomb), 'gequip5.wld')


class Died(BaseException): pass


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.client = Path(self.tmp.name)/'client'; self.client.mkdir()
        (self.client/'trasc-client.json').write_text(json.dumps({'imported':True,'imported_at':1234.5}))
        self.originals = {}
        for name in skeletons.ARCHIVES:
            path = self.client/name; value = archive(name[:-4]+'.wld'); path.write_bytes(value); path.chmod(0o640)
            self.originals[name] = value
        for name in skeletons.CACHES:
            (self.client/name).write_bytes(b'original cache '+name.encode())
            self.originals[name] = (self.client/name).read_bytes()
        (self.client/'unrelated.wld.txc').write_bytes(b'keep cache')
        (self.client/'eqw.dll').write_bytes(b'keep helper')
    def enable(self): return skeletons.set_enabled(self.client, True)
    def snapshot(self): return {name:(self.client/name).read_bytes() if (self.client/name).exists() else None for name in skeletons.FILES}
    def interrupted(self, enabled):
        copy = skeletons._copy; changed = False
        def die(source, target, *args, **kwargs):
            nonlocal changed
            copy(source,target,*args,**kwargs)
            if target.parent == self.client and not changed:
                changed = True; raise Died()
        with patch.object(skeletons,'_copy',side_effect=die):
            with self.assertRaises(Died): skeletons.set_enabled(self.client, enabled)
    def test_enable_revert_byte_identical_keep_other_files_modes_and_caches(self):
        result = self.enable()
        self.assertTrue(result['skeletons']['enabled'])
        for name in skeletons.CACHES: self.assertFalse((self.client/name).exists())
        for name in skeletons.ARCHIVES: self.assertEqual((self.client/name).stat().st_mode & 0o777, 0o640)
        skeletons.verify_active(self.client)
        self.assertTrue(skeletons.set_enabled(self.client, True)['skeletons']['enabled'])
        result = skeletons.set_enabled(self.client, False)
        self.assertFalse(result['skeletons']['enabled']); self.assertEqual(self.snapshot(), self.originals)
        self.assertEqual((self.client/'eqw.dll').read_bytes(), b'keep helper')
        self.assertEqual((self.client/'unrelated.wld.txc').read_bytes(), b'keep cache')
    def test_revert_retains_custom_edits_and_generated_texture_cache(self):
        self.enable(); (self.client/'gequip5.s3d').write_bytes(b'custom changed model')
        (self.client/'global6_chr.wld.txc').write_bytes(b'new generated cache')
        with self.assertRaisesRegex(ValueError,'changed after Enable'): skeletons.verify_active(self.client)
        result = skeletons.set_enabled(self.client, False)
        record = json.loads((self.client/skeletons.PRIVATE/'current.json').read_text())
        folder = self.client/skeletons.PRIVATE/record['id']/'before'
        self.assertEqual((folder/'gequip5.s3d').read_bytes(),b'custom changed model')
        self.assertEqual((folder/'global6_chr.wld.txc').read_bytes(),b'new generated cache')
        self.assertEqual(self.snapshot(),self.originals)
    def test_process_death_rolls_back_enable_and_disable_with_all_before_files(self):
        self.interrupted(True)
        self.assertEqual(skeletons.status(self.client)['state'],'interrupted')
        skeletons.recover(self.client); self.assertEqual(self.snapshot(),self.originals)
        self.enable(); before = self.snapshot(); self.interrupted(False)
        skeletons.recover(self.client); self.assertEqual(self.snapshot(),before)
        skeletons.verify_active(self.client)
    def test_unknown_change_during_interruption_retained_before_rollback(self):
        self.interrupted(True); (self.client/'global6_chr.s3d').write_bytes(b'outside modification')
        root = self.client/skeletons.PRIVATE
        journal = json.loads((root/'transaction.json').read_text())
        skeletons.recover(self.client)
        self.assertEqual((root/journal['id']/'interrupted-changes/global6_chr.s3d').read_bytes(),b'outside modification')
        self.assertEqual(self.snapshot(),self.originals)
    def test_invalid_or_partial_journal_prevalidates_before_any_live_write(self):
        self.interrupted(True); root = self.client/skeletons.PRIVATE
        original = json.loads((root/'transaction.json').read_text()); before = self.snapshot()
        variants = []
        for key in ('previous','next','files','identity'):
            value = dict(original); value.pop(key); variants.append(value)
        value = json.loads(json.dumps(original)); value['files']['global6_chr.wld.txc']['target']=42; variants.append(value)
        value = json.loads(json.dumps(original)); value['files']['global6_chr.wld.txc']['before']['name']=None; variants.append(value)
        value = json.loads(json.dumps(original)); value['next']=None; variants.append(value)
        for value in variants:
            (root/'transaction.json').write_text(json.dumps(value))
            with self.assertRaises(ValueError): skeletons.recover(self.client)
            self.assertEqual(self.snapshot(),before)
        (root/'transaction.json').write_text(json.dumps(original)); skeletons.recover(self.client)
    def test_unexpected_current_receipt_does_not_get_overwritten_by_recovery(self):
        self.interrupted(True); root = self.client/skeletons.PRIVATE; before = self.snapshot()
        foreign = {'format':1,'state':'off','identity':1234.5,'id':'a'*32}
        (root/'current.json').write_text(json.dumps(foreign))
        with self.assertRaisesRegex(ValueError,'current receipt differs'): skeletons.recover(self.client)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(json.loads((root/'current.json').read_text()),foreign)
    def test_corrupted_snapshot_and_concurrent_edit_refuse_before_journal(self):
        copy = skeletons._copy
        def corrupt(source,target,*args,**kwargs):
            copy(source,target,*args,**kwargs)
            if target.parent.name == 'before' and target.name == 'gequip5.wld.txc': target.write_bytes(b'corrupted copy')
        with patch.object(skeletons,'_copy',side_effect=corrupt):
            with self.assertRaisesRegex(ValueError,'checksum'): self.enable()
        self.assertEqual(self.snapshot(),self.originals)
        self.assertFalse((self.client/skeletons.PRIVATE/'transaction.json').exists())
        def edit(source,target,*args,**kwargs):
            copy(source,target,*args,**kwargs)
            if target.parent.name == 'originals' and target.name == 'gequip5.wld.txc':
                (self.client/'gequip5.wld.txc').write_bytes(b'concurrent user cache')
        with patch.object(skeletons,'_copy',side_effect=edit):
            with self.assertRaisesRegex(ValueError,'changed during preparation'): self.enable()
        self.assertEqual((self.client/'gequip5.wld.txc').read_bytes(),b'concurrent user cache')
        for name in skeletons.ARCHIVES: self.assertEqual((self.client/name).read_bytes(),self.originals[name])
        self.assertFalse((self.client/skeletons.PRIVATE/'transaction.json').exists())
    def test_space_check_repeats_after_staging_before_any_live_mutation(self):
        with patch.object(skeletons.shutil,'disk_usage',side_effect=[shutil_usage(1024**3),shutil_usage(1)]):
            with self.assertRaisesRegex(ValueError,'remains'): self.enable()
        self.assertEqual(self.snapshot(),self.originals)
        self.assertFalse((self.client/skeletons.PRIVATE/'transaction.json').exists())
    def test_corrupt_original_or_symlink_refuses_without_changing_live_pair(self):
        self.enable(); before=self.snapshot(); root=self.client/skeletons.PRIVATE
        record=json.loads((root/'current.json').read_text()); saved=root/record['id']/'originals/gequip5.s3d'
        saved.write_bytes(b'changed backup')
        with self.assertRaisesRegex(ValueError,'checksum'): skeletons.set_enabled(self.client,False)
        self.assertEqual(self.snapshot(),before)
        saved.unlink(); saved.symlink_to(self.client/'eqw.dll')
        with self.assertRaises(ValueError): skeletons.set_enabled(self.client,False)
        self.assertEqual(self.snapshot(),before)
    def test_new_import_identity_refuses_recovery_and_leaves_originals(self):
        self.interrupted(True); before=self.snapshot()
        (self.client/'trasc-client.json').write_text(json.dumps({'imported_at':5678}))
        with self.assertRaisesRegex(ValueError,'receipt changed'): skeletons.recover(self.client)
        self.assertEqual(self.snapshot(),before)
    def test_second_archive_incompatible_cancel_and_disk_pressure_preserve_all_assets(self):
        (self.client/'global6_chr.s3d').write_bytes(b'incompatible'); before=self.snapshot()
        with self.assertRaises(ValueError): self.enable()
        self.assertEqual(self.snapshot(),before); self.assertFalse((self.client/skeletons.PRIVATE/'transaction.json').exists())
        self.assertEqual(list((self.client/skeletons.PRIVATE).iterdir()),[])
        (self.client/'global6_chr.s3d').write_bytes(self.originals['global6_chr.s3d'])
        with patch.object(skeletons.shutil,'disk_usage',return_value=shutil_usage(1)):
            with self.assertRaisesRegex(ValueError,'free space'): self.enable()
        self.assertEqual(self.snapshot(),self.originals)
        calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==6: raise RuntimeError('cancelled')
        with self.assertRaisesRegex(RuntimeError,'cancelled'): skeletons.set_enabled(self.client,True,cancel)
        self.assertEqual(self.snapshot(),self.originals)
        self.assertEqual(list((self.client/skeletons.PRIVATE).iterdir()),[])
    def test_missing_ambiguous_and_linked_client_assets_refuse(self):
        (self.client/'gequip5.s3d').unlink()
        with self.assertRaisesRegex(ValueError,'both'): self.enable()
        (self.client/'gequip5.s3d').write_bytes(self.originals['gequip5.s3d'])
        (self.client/'GEQUIP5.S3D').write_bytes(b'duplicate')
        with self.assertRaisesRegex(ValueError,'Ambiguous'): self.enable()
        (self.client/'GEQUIP5.S3D').unlink(); (self.client/'gequip5.s3d').unlink()
        (self.client/'gequip5.s3d').symlink_to(self.client/'global6_chr.s3d')
        with self.assertRaisesRegex(ValueError,'symlinks'): self.enable()


def shutil_usage(free):
    import shutil
    return shutil._ntuple_diskusage(1024,1023,free)


if __name__ == '__main__': unittest.main()
