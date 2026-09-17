import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import log_retention as logs


class RetentionTests(unittest.TestCase):
    def test_closed_history_order_and_reduced_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/'client-wine.log'
            self.assertEqual(logs.count(root), 5)
            for n in range(8):
                path.write_text(str(n))
                logs.rotate(path)
            self.assertEqual([logs.history(path, i).read_text() for i in range(1, 6)], ['7','6','5','4','3'])
            for keep in (2, 3, 4, 5):
                (root/'retention-count.txt').write_text(str(keep))
                for n in range(6):
                    path.write_text(str(n))
                    logs.rotate(path)
                self.assertEqual(len(list(root.glob('*.log'))), keep)
                self.assertEqual(logs.history(path, keep).read_text(), str(6-keep))

    def test_bound_retains_start_and_end_and_does_not_follow_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/'client.log'
            path.write_bytes(b'START'+b'x'*5000+b'FINAL')
            logs.rotate(path, 1024)
            data = logs.history(path, 1).read_bytes()
            self.assertEqual(len(data), 1024)
            self.assertTrue(data.startswith(b'START') and data.endswith(b'FINAL'))
            outside = root/'keep.txt';outside.write_text('precious')
            path.symlink_to(outside)
            with self.assertRaises(ValueError): logs.rotate(path)
            self.assertEqual(outside.read_text(), 'precious')

    def test_invalid_setting_and_zone_stdout_share_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);(root/'logs').mkdir();(root/'server/logs').mkdir(parents=True)
            setting = root/'logs/retention-count.txt'
            for bad in ('1', '6', '2.5', 'broken', 'x'*100):
                setting.write_text(bad)
                self.assertEqual(logs.count(root/'logs'), 5)
            setting.write_text('3')
            self.assertEqual(logs.count(root/'server/logs'), 3)


if __name__ == '__main__': unittest.main()
