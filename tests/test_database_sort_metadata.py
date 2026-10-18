"""Database sort metadata must describe the selectable input without reading it."""
from datetime import datetime
import gzip
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine, _zip_modified_time
import peq_database


class DatabaseSortMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_zip(self, path, entries):
        with zipfile.ZipFile(path, 'w') as archive:
            for name, date, payload in entries:
                archive.writestr(zipfile.ZipInfo(name, date_time=date), payload)

    def test_plain_and_gzip_use_filesystem_modification_time_in_all_profiles(self):
        for profile in ('custom', 'traditional', 'takp'):
            with self.subTest(profile=profile):
                engine = Engine(self.work / profile, profile)
                plain = engine.work / 'incoming/seed.sql'
                compressed = engine.work / 'incoming/seed.sql.gz'
                plain.write_bytes(b'-- seed\n')
                compressed.write_bytes(gzip.compress(b'-- compressed seed\n', mtime=1))
                os.utime(plain, (1700000000, 1700000000))
                os.utime(compressed, (1700100000, 1700100000))
                catalog = {item['id']: item for item in engine.database_candidates()}
                self.assertEqual(catalog['incoming/seed.sql']['modified'], 1700000000)
                self.assertEqual(catalog['incoming/seed.sql.gz']['modified'], 1700100000)
                self.assertEqual(catalog['incoming/seed.sql']['size'], plain.stat().st_size)
                self.assertEqual(catalog['incoming/seed.sql.gz']['size'], compressed.stat().st_size)

    def test_zip_uses_member_dates_and_does_not_open_sql_payloads(self):
        engine = Engine(self.work)
        date = (2021, 4, 12, 7, 30, 16)
        self.write_zip(engine.work / 'incoming/seeds.zip', [
            ('older.sql', date, b'-- seed'),
            ('newer.sql.gz', (2025, 9, 23, 12, 0, 0), b'not decompressed during listing'),
        ])
        os.utime(engine.work / 'incoming/seeds.zip', (1800000000, 1800000000))
        with patch('engine.zipfile.ZipFile.open', side_effect=AssertionError('SQL payload opened')):
            catalog = {item['id']: item for item in engine.database_candidates()}
        self.assertEqual(catalog['incoming/seeds.zip!older.sql']['modified'], datetime(*date).timestamp())
        self.assertNotEqual(catalog['incoming/seeds.zip!older.sql']['modified'], 1800000000)
        self.assertGreater(catalog['incoming/seeds.zip!newer.sql.gz']['modified'],
                           catalog['incoming/seeds.zip!older.sql']['modified'])
        self.assertEqual(set(catalog), {'incoming/seeds.zip!older.sql', 'incoming/seeds.zip!newer.sql.gz'})
        self.assertFalse((engine.work / 'incoming/older.sql').exists())

    def test_invalid_zip_member_dates_remain_selectable_with_unknown_time(self):
        engine = Engine(self.work)
        # ZIP can encode zero month/day even though these are not calendar dates.
        self.write_zip(engine.work / 'incoming/invalid-date.zip', [
            ('seed.sql', (2026, 0, 0, 0, 0, 0), b'-- retained input'),
        ])
        candidate, = engine.database_candidates()
        self.assertEqual(candidate['id'], 'incoming/invalid-date.zip!seed.sql')
        self.assertEqual(candidate['kind'], 'sql')
        self.assertIsNone(candidate['modified'])
        for malformed in (None, (), (2026, 2, 31, 0, 0, 0), ('bad',) * 6):
            with self.subTest(malformed=malformed):
                self.assertIsNone(_zip_modified_time(SimpleNamespace(date_time=malformed)))
        self.assertIsNone(_zip_modified_time(SimpleNamespace()))

    def test_bundle_time_is_latest_component_not_manifest_or_archive(self):
        engine = Engine(self.work, 'traditional')
        manifest = ''.join('source ' + name + ';\n' for name in peq_database.PARTS)
        dates = [(2023, 3, 1 + index, 14, 0, 0) for index in range(len(peq_database.PARTS))]
        self.write_zip(engine.work / 'incoming/peq.zip', [
            ('peq/create_all_tables.sql', (2026, 10, 18, 0, 0, 0), manifest),
            *[('peq/' + name, date, b'-- SQL component')
              for name, date in zip(peq_database.PARTS, dates)],
        ])
        os.utime(engine.work / 'incoming/peq.zip', (1800000000, 1800000000))
        catalog = engine.database_candidates()
        bundle = catalog[0]
        self.assertEqual(bundle['id'], 'incoming/peq.zip!peq/create_all_tables.sql')
        self.assertEqual(bundle['kind'], 'peq_bundle')
        self.assertEqual(bundle['modified'], datetime(*dates[-1]).timestamp())
        self.assertEqual(bundle['selections'], ['incoming/peq.zip!peq/' + name for name in peq_database.PARTS])
        self.assertEqual(bundle['size'], len(b'-- SQL component') * len(peq_database.PARTS))

    def test_directory_bundle_uses_component_times_and_keeps_seed_order(self):
        engine = Engine(self.work, 'traditional')
        root = engine.work / 'incoming/peq'
        root.mkdir()
        wrapper = root / 'create_all_tables.sql'
        wrapper.write_text(''.join('source ' + name + ';\n' for name in peq_database.PARTS))
        os.utime(wrapper, (1800000000, 1800000000))
        dates = [1700000100, 1700000500, 1700000300, 1700000400, 1700000200]
        for name, modified in zip(peq_database.PARTS, dates):
            part = root / name
            part.write_bytes(b'-- SQL component')
            os.utime(part, (modified, modified))
        bundle = engine.database_candidates()[0]
        self.assertEqual(bundle['modified'], max(dates))
        self.assertEqual(bundle['selections'], ['incoming/peq/' + name for name in peq_database.PARTS])

    def test_bundle_uses_known_components_and_null_when_all_are_unknown(self):
        engine = Engine(self.work, 'traditional')
        manifest = ''.join('source ' + name + ';\n' for name in peq_database.PARTS)
        invalid = (2026, 0, 0, 0, 0, 0)
        known = (2020, 5, 6, 7, 8, 10)
        for date in (known, invalid):
            with self.subTest(date=date):
                self.write_zip(engine.work / 'incoming/peq.zip', [
                    ('peq/create_all_tables.sql', (2026, 10, 18, 0, 0, 0), manifest),
                    *[('peq/' + name, date if index == 1 else invalid, b'-- SQL component')
                      for index, name in enumerate(peq_database.PARTS)],
                ])
                bundle = engine.database_candidates()[0]
                self.assertEqual(bundle['kind'], 'peq_bundle')
                self.assertEqual(bundle['modified'], datetime(*known).timestamp() if date == known else None)

    def test_metadata_does_not_change_default_recommendations_or_ids(self):
        engine = Engine(self.work)
        source = engine.work / 'sources/current'
        source.mkdir()
        inputs = [
            (source / 'large-new.sql', 1000, 1800000000),
            (engine.work / 'incoming/small-new.sql', 10, 1800000000),
            (engine.work / 'incoming/large-old.sql', 100, 1600000000),
            (engine.work / 'incoming/release-peq.sql', 1, 1500000000),
        ]
        for path, size, modified in inputs:
            path.write_bytes(b' ' * size)
            os.utime(path, (modified, modified))
        self.assertEqual([item['id'] for item in engine.database_candidates()], [
            'incoming/release-peq.sql', 'incoming/large-old.sql', 'incoming/small-new.sql',
            'sources/current/large-new.sql',
        ])


if __name__ == '__main__':
    unittest.main()
