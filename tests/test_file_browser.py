"""Large-folder search must work beyond the old silent 2,000-entry cutoff."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine


class FileBrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root)
        self.folder = self.root / 'client/current'
        self.folder.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_searches_all_names_and_pages_past_old_cutoff(self):
        for i in range(2101): (self.folder / f'a{i:04}.txt').touch()
        (self.folder / 'DINPUT8.dll').write_bytes(b'dll')
        (self.folder / 'z-last.txt').touch()
        default = self.engine.files({'path':'client/current'})
        self.assertEqual(len(default['items']), 2000)
        self.assertEqual(default['total'], 2103)
        self.assertEqual(default['next_offset'], 2000)
        match = self.engine.files({'path':'client/current','query':'  DiNpUt  ','limit':200})
        self.assertEqual([x['path'] for x in match['items']], ['client/current/DINPUT8.dll'])
        self.assertEqual(match['items'][0]['size'], 3)
        seen = []
        offset = 0
        while offset is not None:
            page = self.engine.files({'path':'client/current','offset':offset,'limit':200})
            seen.extend(x['name'] for x in page['items'])
            offset = page['next_offset']
        self.assertEqual(len(seen), 2103)
        self.assertEqual(len(set(seen)), 2103)
        self.assertEqual(seen[-1], 'z-last.txt')

    def test_search_is_literal_scoped_and_preserves_exclusions(self):
        nested = self.folder / 'Models'; nested.mkdir()
        (nested / 'needle.dll').touch()
        (self.folder / '[needle].dll').touch()
        (self.folder / 'settings.json').touch()
        (self.folder / 'linked-needle.dll').symlink_to(nested / 'needle.dll')
        match = self.engine.files({'path':'client/current','query':'needle'})
        self.assertEqual([x['name'] for x in match['items']], ['[needle].dll'])
        self.assertEqual(self.engine.files({'path':'client/current','query':'*.dll'})['total'], 0)
        self.assertEqual(self.engine.files({'path':'client/current','query':'settings'})['total'], 0)
        page = self.engine.files({'path':'client/current'})
        self.assertEqual(page['items'][0]['name'], 'Models')
        self.assertTrue(page['items'][0]['directory'])

    def test_empty_results_and_removed_last_page_have_valid_offsets(self):
        empty = self.engine.files({'path':'client/current','query':'missing','offset':200})
        self.assertEqual((empty['total'], empty['offset'], empty['next_offset']), (0,0,None))
        (self.folder / 'remaining.txt').touch()
        page = self.engine.files({'path':'client/current','offset':200,'limit':200})
        self.assertEqual(page['offset'], 0)
        self.assertEqual(page['items'][0]['name'], 'remaining.txt')

    def test_rejects_invalid_search_pages_and_escape_paths(self):
        for args in ({'query':None},{'query':'a'*257},{'offset':-1},{'offset':True},
                     {'limit':0},{'limit':2001},{'limit':'200'},{'path':'../'}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.engine.files({'path':'client/current',**args})
