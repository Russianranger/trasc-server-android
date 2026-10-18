"""Compare launcher validation with the pinned, actual Triptych C++ decoder.

These cases contain only generated card records, never licensed client data.
The reference is host-only; no test fixture is packaged into the launcher.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import lon_data


def unsigned(value):
    value &= 0xffffffff
    negative = 1 if (~value & 0xffffffff) < value else 0
    magnitude = (~value & 0xffffffff) if negative else value
    tail = bytearray()
    rest = magnitude >> 4
    while rest:
        tail.append(rest & 255)
        rest >>= 8
    return bytes([(magnitude & 15) | ((2 * len(tail) + negative) << 4)]) + tail


def words(*values):
    return b''.join(unsigned(value) for value in values)


def text(value):
    value = value.encode('latin1')
    return unsigned(len(value)) + value + b'\0'


def card(identifier=20000001, set_id=1, subtype='Unit', unsupported=False):
    # Include every property type recognized by the upstream parser, plus a
    # negative integer and values requiring multi-byte custom varints.
    properties = [words(73, 1, 1, 2, 1, set_id),
                  words(5, 1, 1, 3, 1) + text(subtype),
                  words(1, 1, 1, 3, 1) + text('Synthetic card'),
                  words(2051, 1, 1, 1, 1, 1),
                  words(76, 1, 1, 2, 1, 70035),
                  words(999, 1, 1, 6, 1, 3, -1, 0, 65536)]
    if unsupported:
        properties.append(words(1000, 1, 1, 7, 1))
    return words(1, 1, 1, 1, identifier, 0, 0, 0, 1, 1, 0x17, 1, len(properties)) + b''.join(properties)


def data_tree(directory, records, mutate_index=None, mutate_storage=None):
    directory = Path(directory)
    archetypes = directory / 'archetypes'
    archetypes.mkdir()
    index, storage = bytearray(words(1, 1)), bytearray()
    for number, record in enumerate(records):
        compressed = zlib.compress(record)
        index.extend(words(number, len(compressed), len(record), len(storage)))
        storage.extend(compressed)
    if mutate_index:
        index = mutate_index(index)
    if mutate_storage:
        storage = mutate_storage(storage)
    (archetypes / 'index.dat').write_bytes(index)
    (archetypes / 'storage.dat').write_bytes(storage)
    return directory


class Engine:
    current_job = None

    def check_cancel(self):
        pass


class LoNLoaderParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='trasc-lon-parity-')
        compiler = shutil.which('g++') or shutil.which('clang++')
        if not compiler:
            cls.temporary.cleanup()
            raise unittest.SkipTest('C++ host compiler is unavailable')
        cls.reference = Path(cls.temporary.name) / 'reference'
        subprocess.run([compiler, '-std=c++17', '-O2',
                        str(Path(__file__).parent / 'fixtures/lon-loader-reference.cpp'),
                        '-lz', '-o', str(cls.reference)], check=True,
                       capture_output=True, text=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def compare(self, records, valid, mutate_index=None, mutate_storage=None):
        with tempfile.TemporaryDirectory(dir=self.temporary.name) as directory:
            root = data_tree(directory, records, mutate_index, mutate_storage)
            expected = json.loads(subprocess.run([str(self.reference), str(root)],
                                                 check=True, capture_output=True,
                                                 text=True, timeout=10).stdout)
            actual = lon_data.validate(Engine(), root)
            self.assertEqual(expected['valid'], valid)
            for field in ('valid', 'parsed_archetypes', 'booster_sets'):
                self.assertEqual(actual[field], expected[field], field)
            return actual, expected

    def test_recognized_properties_and_custom_integer_encoding(self):
        actual, expected = self.compare([card(), card(identifier=20000002, set_id=16)], True)
        self.assertEqual(actual['booster_sets'], 2)
        self.assertEqual(actual['unreadable_archetypes'], expected['unreadable_archetypes'])

    def test_required_booster_pool_and_loot_subtype_rules(self):
        for record in (card(identifier=10), card(set_id=-1), card(subtype='EverQuest II Loot Card')):
            with self.subTest(record=record[:20]):
                self.compare([record], False)
        self.compare([card(subtype='EverQuest Loot Card')], True)

    def test_duplicate_archetype_last_record_controls_pool(self):
        self.compare([card(set_id=1), card(set_id=-1)], False)
        self.compare([card(set_id=-1), card(set_id=1)], True)

    def test_malformed_compression_and_unsupported_property(self):
        self.compare([card()], False, mutate_storage=lambda data: bytearray(b'x' * len(data)))
        self.compare([card(unsupported=True)], False)
        self.compare([b'\x80'], False)

    def test_bad_index_bounds_and_record_size(self):
        for entries in (words(1, 1, 1, 10**6), words(1, 1, 0, 0), words(1, 1, 8 * 1024**2 + 1, 0)):
            with self.subTest(entries=entries):
                self.compare([card()], False, mutate_index=lambda _data: words(1, 1) + entries)

    def test_partial_index_does_not_hide_preceding_valid_card(self):
        # Upstream stops at a truncated entry and keeps preceding valid cards.
        self.compare([card()], True, mutate_index=lambda data: data + b'\x80')

    def test_empty_files_do_not_initialize_service(self):
        self.compare([], False)


if __name__ == '__main__':
    unittest.main()
