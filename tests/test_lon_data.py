"""Real temporary-tree LoN discovery, streaming, safety and repair tests."""
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import threading
import tracemalloc
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import custom_deployment as deployment
import lon_data


def unsigned(value):
    value &= 0xffffffff
    negative = (~value & 0xffffffff) < value
    magnitude = (~value & 0xffffffff) if negative else value
    tail = bytearray()
    rest = magnitude >> 4
    while rest:
        tail.append(rest & 255)
        rest >>= 8
    return bytes([(magnitude & 15) | ((2 * len(tail) + int(negative)) << 4)]) + tail


def words(*values):
    return b''.join(unsigned(value) for value in values)


def fixture():
    # One valid card with a set property. The server creates a booster-set pool
    # for this non-loot archetype even without a rarity/name property.
    record = words(1, 1, 1, 1, 20000001, 0, 0, 0, 1, 1, 0x17, 1, 1,
                   73, 1, 1, 2, 1, 1)
    compressed = zlib.compress(record)
    return {'archetypes/index.dat': words(1, 1, 20000001, len(compressed), len(record), 0),
            'archetypes/storage.dat': compressed,
            'campaign.dat': b'campaign payload preserved',
            'ban.dat': b'ban payload', 'restrict.dat': b'restrict payload',
            'collections/nested/card.dat': b'collection payload',
            'decks/FighterStarter.eqd': b'optional deck payload',
            'tutorial/deeper/readme.txt': b'tutorial payload'}


class LoNDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        for directory in ('incoming', 'run', 'server', 'client/current', 'backups', 'sources/current'):
            (self.work/directory).mkdir(parents=True, exist_ok=True)
        (self.work/'server/eqemu_config.json').write_text(json.dumps({'server': {'directories': {}}}))
        self.running = False
        self.engine = SimpleNamespace(work=self.work, profile='custom', current_job={},
                                      cancel=threading.Event(), server_running=lambda: self.running)
        self.engine.check_cancel = self.check_cancel
        self.rule = {'path': 'lon_data', 'enabled': True, 'ruleset': 'Triune',
                     'path_origin': 'ruleset 1', 'ruleset_found': True}
        self.rule_patch = patch.object(deployment, 'lon_rule', side_effect=lambda engine: dict(self.rule))
        self.rule_patch.start()
        self.addCleanup(self.rule_patch.stop)
        self.destination = self.work/'server/lon_data'
        self.source = self.work/'client/current/LegendsOfNorrath/data'
        self.write_tree(self.source)

    def check_cancel(self):
        if self.engine.cancel.is_set():
            raise ValueError('Operation cancelled')

    def write_tree(self, root, files=None):
        for name, value in (fixture() if files is None else files).items():
            target = Path(root)/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
        (Path(root)/'tutorial/empty').mkdir(parents=True, exist_ok=True)

    def archive(self, prefix='EverQuest_RoF2PT/EverQuest_RoF2PT/LegendsOfNorrath/data/', extras=None, zip64=False):
        archive = self.work/'incoming/client.zip'
        with patch.object(zipfile, 'ZIP64_LIMIT', 100 if zip64 else zipfile.ZIP64_LIMIT):
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as out:
                for name, value in fixture().items():
                    out.writestr(prefix + name, value)
                out.writestr(prefix + 'tutorial/empty/', b'')
                for name, value in (extras or {}).items():
                    out.writestr(name, value)
        return archive

    def scan(self, **args):
        return lon_data.scan(self.engine, args)

    def apply(self, preview, **args):
        return lon_data.apply(self.engine, {'token': preview['token'], **args})

    def stage_directories(self):
        root = self.work/'incoming/custom-deployment'
        return list(root.glob('lon-*')) if root.exists() else []

    def assert_copied(self):
        for name, value in fixture().items():
            self.assertEqual((self.destination/name).read_bytes(), value, name)
        self.assertTrue((self.destination/'tutorial/empty').is_dir())
        self.assertFalse((self.destination/'data').exists())

    def test_all_three_folder_selection_levels_discover_exact_data_root(self):
        for source in ('client/current', 'client/current/LegendsOfNorrath', 'client/current/LegendsOfNorrath/data'):
            with self.subTest(source=source):
                result = self.scan(source=source, kind='directory')
                self.assertEqual(result['source_identity']['data_root'], 'client/current/LegendsOfNorrath/data')
                self.assertEqual(result['summary']['new'], len(fixture()))
                self.assertTrue(result['extra']['validation']['valid'])
                self.assertEqual(result['extra']['validation']['parsed_archetypes'], 1)
                self.assertEqual(result['extra']['validation']['booster_sets'], 1)
        self.assertFalse(self.destination.exists())

    def test_nested_zip_discovers_data_without_extracting_unrelated_client(self):
        self.archive(extras={'EverQuest_RoF2PT/eqgame.exe': b'unrelated client',
                             'EverQuest_RoF2PT/Maps/zone.map': b'unrelated map'})
        preview = self.scan(source='incoming/client.zip', kind='zip')
        staged = self.stage_directories()[0]/'data'
        self.assertEqual({p.relative_to(staged).as_posix() for p in staged.rglob('*') if p.is_file()}, set(fixture()))
        result = self.apply(preview)
        self.assertEqual(result['copied_files'], len(fixture()))
        self.assertEqual(result['copied_bytes'], sum(map(len, fixture().values())))
        self.assert_copied()
        self.assertTrue(result['validation']['valid'])
        self.assertEqual(result['server_initialization'], 'pending_restart')
        self.assertTrue(result['restart_required'])

    def test_data_root_zip_and_zip64_are_supported(self):
        for prefix, zip64 in (('', False), ('arbitrary-wrapper/data/', True)):
            with self.subTest(prefix=prefix, zip64=zip64):
                self.archive(prefix=prefix, zip64=zip64)
                preview = self.scan(source='incoming/client.zip')
                self.assertEqual(preview['summary']['new'], len(fixture()))
                self.assertEqual(preview['source_identity']['data_root'], prefix)

    def test_matching_scan_is_read_only_and_counts_are_hash_based(self):
        self.write_tree(self.destination)
        original = (self.destination/'ban.dat').stat()
        preview = self.scan()
        self.assertEqual(preview['summary']['matching'], len(fixture()))
        self.assertEqual(preview['summary']['files'], 0)
        self.assertEqual(preview['summary']['bytes'], 0)
        self.assertEqual((self.destination/'ban.dat').stat().st_ino, original.st_ino)
        rows = lon_data.files(self.engine, {'token': preview['token'], 'filter': 'matching'})
        self.assertEqual(rows['total'], len(fixture()))
        self.assertFalse((self.work/'backups/custom-deployment/lon_data-latest.json').exists())

    def test_repair_backs_up_changed_files_and_preserves_runtime_only(self):
        self.write_tree(self.destination)
        old = self.destination/'ban.dat'
        old.write_bytes(b'old destination')
        (self.destination/'local-custom.dat').write_bytes(b'keep runtime only')
        (self.destination/'restrict.dat').unlink()
        preview = self.scan()
        self.assertEqual((preview['summary']['new'], preview['summary']['changed'], preview['summary']['runtime_only']), (1, 1, 1))
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.apply(preview)
        self.assertEqual(old.read_bytes(), b'old destination')
        result = self.apply(preview, confirm_overwrite=True)
        self.assertEqual(result['copied_files'], 2)
        self.assertEqual((self.destination/'local-custom.dat').read_bytes(), b'keep runtime only')
        originals = list(Path(result['backup']).glob('*.original'))
        self.assertEqual(len(originals), 1)
        self.assertEqual(originals[0].read_bytes(), b'old destination')
        self.assertEqual(stat.S_IMODE(originals[0].stat().st_mode), 0o400)
        self.assert_copied()

    def test_locally_modified_file_requires_explicit_conflict_approval(self):
        self.apply(self.scan())
        (self.destination/'ban.dat').write_bytes(b'user customization')
        preview = self.scan()
        self.assertEqual(preview['summary']['conflicts'], 1)
        rows = lon_data.files(self.engine, {'token': preview['token'], 'filter': 'conflict'})
        self.assertEqual(rows['rows'][0]['path'], 'ban.dat')
        with self.assertRaisesRegex(ValueError, 'conflict approval'):
            self.apply(preview, confirm_overwrite=True)
        self.assertEqual((self.destination/'ban.dat').read_bytes(), b'user customization')
        self.apply(preview, confirm_overwrite=True, approve_conflicts=True)
        self.assert_copied()

    def test_partial_repair_cannot_mix_different_card_index_storage_pairs(self):
        preview = self.scan()
        for flags in ({'include_new': False}, {'include_changed': False}):
            with self.subTest(flags=flags), self.assertRaisesRegex(ValueError, 'index and storage consistent'):
                self.apply(preview, **flags)
        self.assertFalse(self.destination.exists())

    def test_custom_rule_destination_is_resolved_and_rechecked(self):
        self.rule['path'] = 'data/alternate-lon'
        preview = self.scan()
        self.assertEqual(preview['extra']['destination'], str(self.work/'server/data/alternate-lon'))
        self.rule['path'] = 'different-lon'
        with self.assertRaisesRegex(ValueError, 'configuration changed'):
            self.apply(preview)
        self.assertFalse((self.work/'server/data/alternate-lon').exists())

    def test_disabled_service_is_reported_without_changing_any_rules(self):
        self.rule['enabled'] = False
        preview = self.scan()
        self.assertIn('LoNEnabled is disabled', ' '.join(preview['extra']['validation']['warnings']))
        self.apply(preview)
        self.assertFalse(self.rule['enabled'])

    def test_live_server_can_be_scanned_but_not_replaced(self):
        self.running = True
        preview = self.scan()
        with self.assertRaisesRegex(ValueError, 'Stop the Custom server'):
            self.apply(preview)
        self.assertFalse(self.destination.exists())

    def test_invalid_card_data_is_rejected_and_stage_removed(self):
        (self.source/'archetypes/storage.dat').write_bytes(b'not zlib')
        with self.assertRaisesRegex(ValueError, 'No readable LoN card archetypes'):
            self.scan()
        self.assertEqual(self.stage_directories(), [])
        self.assertFalse(self.destination.exists())

    def test_multiple_data_roots_are_ambiguous(self):
        self.write_tree(self.work/'client/current/other/LegendsOfNorrath/data')
        with self.assertRaisesRegex(ValueError, 'Multiple Legends'):
            self.scan()
        self.archive(extras={'other/data/' + name: value for name, value in fixture().items()})
        with self.assertRaisesRegex(ValueError, 'Multiple Legends'):
            self.scan(source='incoming/client.zip')

    def test_unsafe_paths_and_symlinks_never_escape_source(self):
        for source in ('../outside', '/tmp/outside', 'client/current/../current', 'client\\current'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.scan(source=source)
        (self.source/'linked').symlink_to(self.work/'server')
        with self.assertRaisesRegex(ValueError, 'links or special files'):
            self.scan()
        (self.source/'linked').unlink()
        outside = self.work/'outside'
        outside.mkdir()
        linked = self.work/'incoming/link'
        linked.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            self.scan(source='incoming/link')
        self.assertEqual(list(outside.iterdir()), [])

    def test_unsafe_zip_entries_rejected_even_outside_selected_subtree(self):
        for unsafe in ('../escape', '/absolute', 'client/../../escape', 'client\\escape', 'C:/escape', 'client//escape'):
            with self.subTest(unsafe=unsafe):
                self.archive(extras={unsafe: b'bad'})
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    self.scan(source='incoming/client.zip')
                self.assertEqual(self.stage_directories(), [])

    def test_zip_duplicates_case_collisions_and_links_are_rejected(self):
        for extra in ('EverQuest_RoF2PT/EverQuest_RoF2PT/LegendsOfNorrath/data/ban.dat',
                      'EverQuest_RoF2PT/EverQuest_RoF2PT/LegendsOfNorrath/data/BAN.DAT'):
            with self.subTest(extra=extra), warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                self.archive(extras={extra: b'collision'})
                with self.assertRaisesRegex(ValueError, 'Duplicate or case-ambiguous'):
                    self.scan(source='incoming/client.zip')
        archive = self.archive()
        info = zipfile.ZipInfo('unrelated/unsafe-link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, 'a') as out:
            out.writestr(info, b'../../outside')
        with self.assertRaisesRegex(ValueError, 'links or special files'):
            self.scan(source='incoming/client.zip')

    def test_zip_file_parent_shadowing_is_rejected(self):
        self.archive(extras={'EverQuest_RoF2PT/EverQuest_RoF2PT/LegendsOfNorrath/data/tutorial': b'file shadows directory'})
        with self.assertRaisesRegex(ValueError, 'parent folder'):
            self.scan(source='incoming/client.zip')

    def test_cancellation_removes_only_uncommitted_stage(self):
        original = self.engine.check_cancel
        checks = 0
        def cancel():
            nonlocal checks
            checks += 1
            if checks > 25:
                self.engine.cancel.set()
            original()
        self.engine.check_cancel = cancel
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.scan()
        self.assertEqual(self.stage_directories(), [])
        self.assertTrue((self.source/'ban.dat').is_file())
        self.assertFalse(self.destination.exists())

    def test_large_file_staging_keeps_memory_bounded(self):
        large = self.source/'collections/large.bin'
        with large.open('wb') as out:
            for _ in range(64):
                out.write(b'x' * (1024 * 1024))
        tracemalloc.start()
        try:
            preview = self.scan()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 8 * 1024**2)
        staged = Path(deployment.load_preview(self.engine, 'lon_data', preview['token'])['groups'][0]['source'])/'collections/large.bin'
        self.assertEqual(staged.stat().st_size, 64 * 1024**2)
        self.assertEqual(deployment.digest(staged), deployment.digest(large))
        self.assertEqual(self.engine.current_job['progress']['total_bytes'], preview['extra']['staged']['bytes'])

    def test_free_space_and_metadata_limits_fail_before_deployment(self):
        with patch.object(lon_data.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(ValueError, 'free space'):
                self.scan()
        self.assertEqual(self.stage_directories(), [])
        self.archive()
        with patch.object(lon_data, 'MAX_ENTRIES', 2):
            with self.assertRaisesRegex(ValueError, 'memory limit'):
                self.scan(source='incoming/client.zip')
        self.assertFalse(self.destination.exists())

    def test_precommit_validation_failure_rolls_back_existing_installation(self):
        self.write_tree(self.destination)
        (self.destination/'ban.dat').write_bytes(b'old runtime payload')
        preview = self.scan()
        validate = lon_data.validate
        calls = 0
        def invalid_install(engine, root):
            nonlocal calls
            calls += 1
            result = validate(engine, root)
            if calls == 2:
                return dict(result, valid=False, errors=['simulated installed validation failure'])
            return result
        with patch.object(lon_data, 'validate', side_effect=invalid_install):
            with self.assertRaisesRegex(ValueError, 'all changed files were rolled back'):
                self.apply(preview, confirm_overwrite=True)
        self.assertEqual((self.destination/'ban.dat').read_bytes(), b'old runtime payload')
        self.assertFalse((self.work/'backups/custom-deployment/lon_data-latest.json').exists())
        self.assertFalse((self.work/'backups/custom-deployment/journal.json').exists())

    def test_successful_commit_cleans_private_stages_but_not_original_client(self):
        preview = self.scan()
        self.assertEqual(len(self.stage_directories()), 1)
        result = self.apply(preview)
        self.assertEqual(self.stage_directories(), [])
        self.assertEqual(len(result['cleanup']['removed']), 1)
        self.assertTrue((self.source/'archetypes/index.dat').is_file())

    def test_native_owned_zip_is_removed_only_after_successful_commit(self):
        identifier = '12345678-1234-4321-abcd-123456789abc'
        native = self.work/('incoming/lon-import-' + identifier)
        native.mkdir()
        archive = self.archive()
        archive.rename(native/'source.zip')
        (native/'trasc-lon-import.json').write_text(json.dumps(
            {'format': 1, 'profile': 'custom', 'id': identifier, 'kind': 'zip',
             'source': 'source.zip', 'complete': True}))
        preview = self.scan(source=str((native/'source.zip').relative_to(self.work)))
        self.assertTrue(native.is_dir())
        result = self.apply(preview)
        self.assertFalse(native.exists())
        self.assertEqual(result['cleanup']['warnings'], [])
        self.assertEqual(len(result['cleanup']['removed']), 2)
        self.assert_copied()

    def test_unmarked_incoming_zip_is_never_removed(self):
        archive = self.archive()
        preview = self.scan(source='incoming/client.zip')
        self.apply(preview)
        self.assertTrue(archive.is_file())

    def test_wrong_native_ownership_marker_is_retained_as_warning(self):
        identifier = '12345678-1234-4321-abcd-123456789abc'
        native = self.work/('incoming/lon-import-' + identifier)
        native.mkdir()
        self.archive().rename(native/'source.zip')
        (native/'trasc-lon-import.json').write_text('{}')
        preview = self.scan(source=str((native/'source.zip').relative_to(self.work)))
        result = self.apply(preview)
        self.assertTrue((native/'source.zip').is_file())
        self.assertIn('ownership marker', ' '.join(result['cleanup']['warnings']))
        self.assert_copied()

    def test_verify_requires_live_world_and_fresh_success_log(self):
        self.apply(self.scan())
        (self.work/'logs').mkdir()
        log = self.work/'logs/world.log'
        log.write_text('[LoN] card service listening on port [5996]\n')
        result = lon_data.verify(self.engine)
        self.assertEqual(result['server_initialization'], 'pending_restart')
        self.engine.processes = {'world': SimpleNamespace(poll=lambda: None)}
        with patch.object(lon_data, '_process_started', return_value=__import__('time').time()):
            result = lon_data.verify(self.engine)
        self.assertEqual(result['server_initialization'], 'confirmed')
        self.assertFalse(result['restart_required'])
        last_sync = deployment.status(self.engine, 'lon_data')['last_sync']
        os.utime(log, (last_sync - 10, last_sync - 10))
        self.assertEqual(lon_data.verify(self.engine)['server_initialization'], 'pending_restart')

    def test_appended_old_success_cannot_confirm_a_predeployment_world_process(self):
        self.apply(self.scan())
        (self.work/'logs').mkdir()
        (self.work/'logs/world.log').write_text('[LoN] card service listening on port [5996]\n[World] later unrelated message\n')
        self.engine.processes = {'world': SimpleNamespace(poll=lambda: None)}
        last_sync = deployment.status(self.engine, 'lon_data')['last_sync']
        with patch.object(lon_data, '_process_started', return_value=last_sync - 100):
            result = lon_data.verify(self.engine)
        self.assertEqual(result['server_initialization'], 'pending_restart')
        self.assertIn('restarted after deployment', result['service']['log_warning'])

    def test_old_precommit_failure_log_appended_later_stays_pending(self):
        (self.work/'logs').mkdir()
        log = self.work/'logs/world.log'
        log.write_text('[LoN] card service NOT started\n')
        self.apply(self.scan())
        with log.open('a') as out:
            out.write('[World] unrelated later message\n')
        result = lon_data.verify(self.engine)
        self.assertEqual(result['server_initialization'], 'pending_restart')
        self.assertIn('pre-deployment world log', result['service']['log_warning'])

    def test_verify_distinguishes_service_failure_and_disabled_rule(self):
        self.write_tree(self.destination)
        (self.work/'logs').mkdir()
        (self.work/'logs/world.log').write_text('[LoN] card data missing under [lon_data]\n[LoN] card service NOT started\n')
        result = lon_data.verify(self.engine)
        self.assertTrue(result['validation']['valid'])
        self.assertEqual(result['server_initialization'], 'failed')
        self.rule['enabled'] = False
        self.assertEqual(lon_data.verify(self.engine)['server_initialization'], 'disabled')

    def test_profile_isolation_for_every_public_action(self):
        for profile in ('traditional', 'takp'):
            self.engine.profile = profile
            for operation, args in ((lon_data.status, None), (lon_data.scan, {}), (lon_data.files, {}),
                                    (lon_data.apply, {}), (lon_data.verify, None)):
                with self.subTest(profile=profile, operation=operation.__name__), self.assertRaisesRegex(ValueError, 'TRASC Custom'):
                    operation(self.engine, args)
        self.assertFalse(self.destination.exists())

    def test_status_does_not_guess_rule_path_or_start_database(self):
        with patch.object(deployment, 'lon_rule', side_effect=AssertionError('status must not query DB')):
            result = lon_data.status(self.engine)
        self.assertIsNone(result['destination'])
        self.assertTrue(result['destination_resolution_required'])
        self.assertIn('client/current', result['source_candidates'])

    def test_verify_parses_existing_destination_and_reports_pending_server_restart(self):
        self.write_tree(self.destination)
        result = lon_data.verify(self.engine)
        self.assertTrue(result['validation']['valid'])
        self.assertEqual(result['destination'], str(self.destination))
        self.assertEqual(result['server_initialization'], 'pending_restart')


if __name__ == '__main__':
    unittest.main()
