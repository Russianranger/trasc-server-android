"""Exercise bundle selection and safeguards before the managed DB is replaced."""
import gzip
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine
import peq_database


class PeqDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.engine = Engine(self.work, 'traditional')
        self.wrapper = 'incoming/peq.zip!peq-dump/create_all_tables.sql'
        self.manifest = ''.join('source ' + name + ';\n' for name in peq_database.PARTS)
        self.payloads = {name: ('-- ' + name + '\nCREATE TABLE part_' + str(index) + '(id int);\n')
                         for index, name in enumerate(peq_database.PARTS)}
        self.required = '\n'.join(('account', 'character_data', 'rule_values', 'rule_sets', 'variables', 'launcher'))

    def tearDown(self):
        self.tmp.cleanup()

    def archive(self, manifest=None, payloads=None, extra=()):
        payloads = self.payloads if payloads is None else payloads
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.work / 'incoming/peq.zip', 'w') as archive:
                archive.writestr('peq-dump/create_all_tables.sql', self.manifest if manifest is None else manifest)
                for name, data in payloads.items():
                    archive.writestr('peq-dump/' + name, data)
                for name, data in extra:
                    archive.writestr(name, data)

    def candidate(self):
        return next(item for item in self.engine.database_candidates() if item['id'] == self.wrapper)

    def import_capture(self, args=None):
        captured, queries = [], []
        def mysql(query, **kwargs):
            queries.append(query)
            return self.required
        with patch.object(self.engine, 'ensure_db'), patch.object(self.engine, 'mysql', side_effect=mysql), \
                patch.object(self.engine, 'run', side_effect=lambda cmd, **kwargs: captured.append(kwargs['input_file'].read_bytes())):
            result = self.engine.import_database({'selection': self.wrapper, **(args or {})})
        return captured, queries, result

    def test_complete_bundle_lists_exact_order_and_payload_size(self):
        self.archive()
        bundle = self.candidate()
        self.assertEqual(bundle['kind'], 'peq_bundle')
        self.assertEqual(bundle['label'], 'Complete PEQ database · 5 parts')
        self.assertEqual(bundle['origin'], 'uploaded')
        self.assertEqual(bundle['parts'], list(peq_database.PARTS))
        self.assertEqual(bundle['selections'], ['incoming/peq.zip!peq-dump/' + name for name in peq_database.PARTS])
        self.assertEqual(bundle['size'], sum(len(value.encode()) for value in self.payloads.values()))

    def test_import_expands_once_in_seed_order_and_never_executes_wrapper(self):
        self.archive()
        captured, queries, result = self.import_capture()
        expected = b''.join(self.payloads[name].encode() + b'\n' for name in peq_database.PARTS)
        self.assertEqual(captured, [expected])
        self.assertNotIn(b'source ', captured[0].lower())
        self.assertEqual(sum('DROP DATABASE' in query for query in queries), 1)
        self.assertEqual(result['imported'], self.wrapper)
        self.assertEqual(self.engine.config['database_source'], self.wrapper)
        self.assertEqual(self.engine.config['database_sources'], self.candidate()['selections'])
        self.assertTrue(self.engine.config['database_imported'])
        self.assertFalse((self.work / 'run/database-import.sql').exists())
        self.assertFalse(list((self.work / 'run').glob('selected-database-*')))

    def test_directory_bundle_and_commented_manifest(self):
        root = self.work / 'incoming/peq-dump'
        root.mkdir()
        (root / 'create_all_tables.sql').write_text('-- PEQ installer\n/* parts below */\n' + self.manifest.replace('source ', 'SOURCE '))
        for name, data in self.payloads.items(): (root / name).write_text(data)
        self.wrapper = 'incoming/peq-dump/create_all_tables.sql'
        self.assertEqual(self.candidate()['kind'], 'peq_bundle')
        captured, _, _ = self.import_capture()
        self.assertEqual(captured, [b''.join(self.payloads[name].encode() + b'\n' for name in peq_database.PARTS)])

    def test_missing_part_is_unsupported_and_rejected_before_database_start(self):
        payloads = dict(self.payloads)
        del payloads[peq_database.PARTS[2]]
        self.archive(payloads=payloads)
        bundle = self.candidate()
        self.assertEqual(bundle['kind'], 'unsupported_bundle')
        self.assertIn('missing create_tables_player.sql', bundle['reason'])
        with patch.object(self.engine, 'ensure_db') as ensure, patch.object(self.engine, 'mysql') as mysql:
            with self.assertRaisesRegex(ValueError, 'missing'):
                self.engine.import_database({'selection': self.wrapper})
        ensure.assert_not_called()
        mysql.assert_not_called()

    def test_duplicate_zip_parts_and_manifests_fail_closed(self):
        for member in ('create_all_tables.sql', peq_database.PARTS[0]):
            with self.subTest(member=member):
                self.archive(extra=[('peq-dump/' + member, self.manifest if member == 'create_all_tables.sql' else 'ambiguous')])
                self.assertEqual(self.candidate()['kind'], 'unsupported_bundle')
                with patch.object(self.engine, 'ensure_db') as ensure:
                    with self.assertRaises(ValueError): self.engine.import_database({'selection': self.wrapper})
                ensure.assert_not_called()

    def test_invalid_manifest_commands_traversal_repetition_and_order(self):
        invalid = [self.manifest.replace(peq_database.PARTS[0], '../' + peq_database.PARTS[0]),
                   self.manifest + 'source create_tables_content.sql;\n',
                   self.manifest.replace('source create_tables_login.sql;\n', ''),
                   self.manifest + 'DROP DATABASE mysql;\n',
                   self.manifest.replace(peq_database.PARTS[0], peq_database.PARTS[0] + '.gz'),
                   self.manifest.replace('source create_tables_content.sql;\n', 'source create_tables_content.sql\n'),
                   self.manifest + ' ' * peq_database.MAX_MANIFEST_BYTES]
        for manifest in invalid:
            with self.subTest(manifest=manifest[:80]):
                self.archive(manifest=manifest)
                self.assertEqual(self.candidate()['kind'], 'unsupported_bundle')
                with patch.object(self.engine, 'ensure_db') as ensure:
                    with self.assertRaises(ValueError): self.engine.import_database({'selection': self.wrapper})
                ensure.assert_not_called()

    def test_zip_traversal_and_symlink_cannot_satisfy_bundle_parts(self):
        payloads = dict(self.payloads)
        del payloads[peq_database.PARTS[0]]
        self.archive(payloads=payloads, extra=[('peq-dump/../' + peq_database.PARTS[0], 'unsafe')])
        self.assertEqual(self.candidate()['kind'], 'unsupported_bundle')
        self.archive(payloads=payloads)
        with zipfile.ZipFile(self.work / 'incoming/peq.zip', 'a') as archive:
            info = zipfile.ZipInfo('peq-dump/' + peq_database.PARTS[0])
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, '/etc/passwd')
        self.assertEqual(self.candidate()['kind'], 'unsupported_bundle')

    def test_complete_bundle_survives_hundreds_of_source_migrations(self):
        self.archive()
        root = self.work / 'sources/current/utils/sql'
        root.mkdir(parents=True)
        for index in range(1600): (root / (str(index) + '.sql')).write_text('-- source migration\n' + ' ' * 500)
        candidates = self.engine.database_candidates()
        self.assertEqual(len(candidates), 1500)
        self.assertEqual(candidates[0]['id'], self.wrapper)
        self.assertTrue(set(self.candidate()['selections']).issubset({item['id'] for item in candidates[:6]}))
        self.assertTrue(all(item['origin'] == 'source' for item in candidates[6:]))
        self.assertGreater(len(self.engine.database_catalog()), 1500)
        self.import_capture()

    def test_changed_archive_is_revalidated_before_import(self):
        self.archive()
        self.assertEqual(self.candidate()['kind'], 'peq_bundle')
        self.archive(payloads={})
        with patch.object(self.engine, 'ensure_db') as ensure, patch.object(self.engine, 'mysql') as mysql:
            with self.assertRaisesRegex(ValueError, 'missing'):
                self.engine.import_database({'selection': self.wrapper})
        ensure.assert_not_called()
        mysql.assert_not_called()

    def test_custom_profile_cannot_import_complete_peq_bundle(self):
        self.archive()
        self.engine.profile = 'custom'
        with patch.object(self.engine, 'ensure_db') as ensure:
            with self.assertRaisesRegex(ValueError, 'Traditional EQEmu'):
                self.engine.import_database({'selection': self.wrapper})
        ensure.assert_not_called()

    def test_explicit_bundle_parts_must_match_validated_complete_order(self):
        self.archive()
        parts = self.candidate()['selections']
        with patch.object(self.engine, 'ensure_db') as ensure:
            for selections in (parts[:-1], list(reversed(parts)), [parts[0]], [self.wrapper, parts[0]]):
                with self.subTest(selections=selections), self.assertRaisesRegex(ValueError, 'validated seed order'):
                    self.engine.import_database({'selection': self.wrapper, 'selections': selections})
        ensure.assert_not_called()
        self.import_capture({'selections': parts})

    def test_replacement_still_requires_confirmation_and_both_backups(self):
        self.archive()
        self.engine.config['database_imported'] = True
        with patch.object(self.engine, 'ensure_db'), patch.object(self.engine, 'backup_database') as backup, \
                patch('engine.player_data.export_players') as players, patch.object(self.engine, 'mysql') as mysql:
            with self.assertRaisesRegex(ValueError, 'Enable replacement'):
                self.engine.import_database({'selection': self.wrapper})
        backup.assert_not_called()
        players.assert_not_called()
        mysql.assert_not_called()
        self.assertTrue(self.engine.config['database_imported'])
        events = []
        def mysql(query, **kwargs):
            events.append('drop' if 'DROP DATABASE' in query else 'tables')
            return self.required
        with patch.object(self.engine, 'ensure_db'), \
                patch('engine.player_data.export_players', side_effect=lambda *args: events.append('players') or {'file': 'backups/players.zip'}), \
                patch.object(self.engine, 'backup_database', side_effect=lambda *args: events.append('backup')), \
                patch.object(self.engine, 'mysql', side_effect=mysql), \
                patch.object(self.engine, 'run', side_effect=lambda *args, **kwargs: events.append('import')):
            result = self.engine.import_database({'selection': self.wrapper, 'replace': True})
        self.assertEqual(events, ['players', 'backup', 'drop', 'import', 'tables'])
        self.assertEqual(result['player_backup'], 'backups/players.zip')

    def test_payload_source_commands_fail_before_database_drop(self):
        for command in ('source /etc/passwd;\n', '\\. /etc/passwd\n'):
            with self.subTest(command=command):
                payloads = dict(self.payloads)
                payloads[peq_database.PARTS[0]] += command
                self.archive(payloads=payloads)
                with patch.object(self.engine, 'ensure_db'), patch.object(self.engine, 'mysql') as mysql, \
                        patch.object(self.engine, 'run') as run:
                    with self.assertRaisesRegex(ValueError, 'SOURCE commands'):
                        self.engine.import_database({'selection': self.wrapper})
                mysql.assert_not_called()
                run.assert_not_called()
                self.assertFalse(self.engine.config['database_imported'])

    def test_standalone_gzip_import_and_seed_directive_normalization_are_preserved(self):
        with gzip.open(self.work / 'incoming/seed.sql.gz', 'wb') as stream:
            stream.write(b'CREATE DATABASE wrong;\nUSE wrong;\nCREATE TABLE account(id int);\n')
        self.wrapper = 'incoming/seed.sql.gz'
        captured, _, _ = self.import_capture()
        self.assertEqual(captured, [b'CREATE TABLE account(id int);\n\n'])


if __name__ == '__main__': unittest.main()
