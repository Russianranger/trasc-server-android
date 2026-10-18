"""Selected source must never masquerade as a deployed RoF2 ABI requirement."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_compatibility as compatibility

NEW = '38a4f2ad03203cb2f12dbff26fd613cc47efba0a'
OLD = '8f6ca0795f424a7b4eab750ff38fc6473d48375c'


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.engine = types.SimpleNamespace(work=self.work, profile='custom')
        self.source = self.work / 'sources/current'
        self.header = self.source / compatibility.HEADER
        self.header.parent.mkdir(parents=True)
        self.header.write_text('namespace spells { const int SPELLBOOK_SIZE = 1440; // was 720\n}\n')
        (self.source / 'trasc-source.json').write_text(json.dumps({'commit': NEW, 'type': 'github'}))
        self.deployed = self.work / 'server/bin'
        self.deployed.mkdir(parents=True)
        self.zone = self.deployed / 'zone'
        raw = bytearray(128)
        raw[:5] = b'\x7fELF\x02'
        raw[18:20] = (183).to_bytes(2, 'little')
        self.zone.write_bytes(raw)

    def receipt(self, revision=NEW, **extra):
        value = {'source': {'commit': revision},
                 'zone_sha256': hashlib.sha256(self.zone.read_bytes()).hexdigest(), **extra}
        (self.deployed / 'build-info.json').write_text(json.dumps(value))

    def test_selected_updated_source_cannot_assert_or_block_old_server(self):
        self.receipt(OLD)
        result = compatibility.requirements(self.engine)
        self.assertEqual(result['selected_source_commit'], NEW)
        self.assertEqual(result['selected_spellbook_slots'], 1440)
        self.assertEqual(result['deployed_source_commit'], OLD)
        self.assertEqual(result['required_spellbook_slots'], 720)
        self.assertTrue(result['known_deployed'])

    def test_selected_source_without_deployed_receipt_is_only_an_indication(self):
        result = compatibility.requirements(self.engine)
        self.assertEqual(result['selected_spellbook_slots'], 1440)
        self.assertIsNone(result['required_spellbook_slots'])
        self.assertFalse(result['known_deployed'])
        self.assertEqual(result['evidence'], 'selected_source_only')

    def test_exact_known_source_requires_matching_recorded_zone_hash(self):
        self.receipt()
        self.assertEqual(compatibility.requirements(self.engine)['required_spellbook_slots'], 1440)
        self.zone.write_bytes(self.zone.read_bytes() + b'changed')
        result = compatibility.requirements(self.engine)
        self.assertFalse(result['known_deployed'])
        self.assertIsNone(result['required_spellbook_slots'])

    def test_unrecognized_descendant_is_not_assumed_compatible(self):
        self.receipt('f' * 40)
        result = compatibility.requirements(self.engine)
        self.assertTrue(result['deployed_binary_verified'])
        self.assertFalse(result['known_deployed'])
        self.assertIsNone(result['required_spellbook_slots'])

    def test_future_build_records_exact_header_for_unknown_revision(self):
        revision = 'f' * 40
        (self.source / 'trasc-source.json').write_text(json.dumps({'commit': revision}))
        record = compatibility.source_record(self.engine)
        self.receipt(revision, client_compatibility=record)
        result = compatibility.requirements(self.engine)
        self.assertEqual(result['required_spellbook_slots'], 1440)
        self.assertEqual(result['evidence'], 'verified_build_header')
        self.assertEqual(record['source_header_sha256'], hashlib.sha256(self.header.read_bytes()).hexdigest())

    def test_tampered_build_header_receipt_is_unknown(self):
        record = compatibility.source_record(self.engine)
        for key, value in (('format', 2), ('spellbook_slots', 4096), ('source_commit', OLD),
                           ('source_header', '../elsewhere'), ('source_header_sha256', 'bad')):
            with self.subTest(key=key):
                self.receipt(client_compatibility=dict(record, **{key: value}))
                self.assertFalse(compatibility.requirements(self.engine)['known_deployed'])

    def test_disagreeing_zone_hashes_are_unknown(self):
        self.receipt(binaries={'zone': 'f' * 64})
        self.assertFalse(compatibility.requirements(self.engine)['known_deployed'])

    def test_legacy_binary_hash_field_is_supported(self):
        (self.deployed / 'build-info.json').write_text(json.dumps({'source': {'commit': NEW},
            'binaries': {'zone': hashlib.sha256(self.zone.read_bytes()).hexdigest()}}))
        self.assertEqual(compatibility.requirements(self.engine)['required_spellbook_slots'], 1440)

    def test_source_comments_and_duplicate_constants_cannot_supply_evidence(self):
        for text in ('// const int SPELLBOOK_SIZE = 1440;',
                     '/* const int SPELLBOOK_SIZE = 1440; */ const int SPELLBOOK_SIZE = 720;',
                     'const int SPELLBOOK_SIZE = 1440; const int SPELLBOOK_SIZE = 720;'):
            with self.subTest(text=text):
                self.header.write_text(text)
                result = compatibility.requirements(self.engine)
                self.assertEqual(result['selected_spellbook_slots'], 720 if text.startswith('/*') else None)

    def test_symlinks_and_malformed_metadata_stay_unknown(self):
        self.receipt()
        real = self.deployed / 'actual-zone'
        self.zone.rename(real)
        self.zone.symlink_to(real)
        self.assertFalse(compatibility.requirements(self.engine)['known_deployed'])
        self.zone.unlink()
        real.rename(self.zone)
        (self.deployed / 'build-info.json').write_text('[]')
        self.assertFalse(compatibility.requirements(self.engine)['known_deployed'])
        (self.source / 'trasc-source.json').write_text('{bad')
        self.assertIsNone(compatibility.requirements(self.engine)['selected_spellbook_slots'])

    def test_non_arm64_file_cannot_claim_deployed_requirement(self):
        self.zone.write_bytes(b'not an ARM64 ELF server')
        self.receipt()
        self.assertFalse(compatibility.requirements(self.engine)['known_deployed'])

    def test_other_profiles_are_read_only_and_unaffected(self):
        for profile in ('traditional', 'takp'):
            self.engine.profile = profile
            result = compatibility.requirements(self.engine)
            self.assertEqual(result['evidence'], 'not_custom')
            self.assertIsNone(result['required_spellbook_slots'])
            self.assertIsNone(compatibility.source_record(self.engine))
        self.assertFalse((self.work / 'backups').exists())


if __name__ == '__main__':
    unittest.main()
