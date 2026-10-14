import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock

import takp_window_diagnostics as windows


class WindowDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.supervisor = Mock(request={'profile': 'takp', 'mode': 'client'}, status={})
        self.supervisor.spawn.return_value.pid = 123
        self.elf = bytearray(64) + windows.MARKER.encode()
        self.elf[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', self.elf, 18, 183)
        self.receipt = {'format': 1, 'marker': windows.MARKER, 'bytes': len(self.elf),
            'sha256': hashlib.sha256(self.elf).hexdigest(), 'read_only': True,
            'bounded_output_bytes': 128*1024, 'max_seconds': 300}
        (self.root/'takp-window-inspect').write_bytes(self.elf)
        self.write_receipt()

    def tearDown(self):
        self.temp.cleanup()

    def write_receipt(self):
        (self.root/'takp-window-inspector.json').write_text(json.dumps(self.receipt))

    def test_verified_inspector_has_bounded_command_and_supervised_lifetime(self):
        result = windows.start(self.supervisor, self.root/'logs', self.root)
        self.supervisor.spawn.assert_called_once_with([str(self.root/'takp-window-inspect'), '300'], 'client-takp-windows.log')
        self.assertIs(self.supervisor.takp_window_inspector_process, self.supervisor.spawn.return_value)
        self.assertTrue(result['takp_window_inspector']['read_only'])

    def test_invalid_receipt_or_linked_binary_is_nonfatal_and_not_spawned(self):
        for field, value in [('sha256', 'wrong'), ('read_only', False), ('max_seconds', 0),
                             ('marker', 'unknown'), ('bounded_output_bytes', 0)]:
            with self.subTest(field=field):
                original = self.receipt[field]
                self.receipt[field] = value
                self.write_receipt()
                self.assertEqual(windows.start(self.supervisor, self.root/'logs', self.root)['takp_window_inspector']['state'], 'unavailable')
                self.supervisor.spawn.assert_not_called()
                self.receipt[field] = original
        (self.root/'takp-window-inspector.json').write_text('[]')
        self.assertEqual(windows.start(self.supervisor, self.root/'logs', self.root)['takp_window_inspector']['state'], 'unavailable')
        self.write_receipt()
        path = self.root/'takp-window-inspect'
        target = self.root/'other'
        path.rename(target)
        path.symlink_to(target)
        self.assertEqual(windows.start(self.supervisor, self.root/'logs', self.root)['takp_window_inspector']['state'], 'unavailable')
        self.supervisor.spawn.assert_not_called()

    def test_other_profiles_and_modes_never_spawn(self):
        for profile, mode in [('custom', 'client'), ('traditional', 'client'), ('takp', 'winecfg')]:
            self.supervisor.request = {'profile': profile, 'mode': mode}
            self.assertEqual(windows.start(self.supervisor, self.root/'logs', self.root), {})
        self.supervisor.spawn.assert_not_called()

    def test_final_exit_status_replaces_stale_running_without_losing_identity(self):
        self.supervisor.takp_focus_process = Mock()
        self.supervisor.takp_focus_process.poll.return_value = 0
        self.supervisor.takp_window_inspector_process = Mock()
        self.supervisor.takp_window_inspector_process.poll.return_value = 124
        self.supervisor.status = {'takp_focus_recovery': {'state': 'running', 'sha256': 'focus'},
                                 'takp_window_inspector': {'state': 'running', 'read_only': True}}
        result = windows.process_status(self.supervisor)
        self.assertEqual(result['takp_focus_recovery'], {'state': 'exited', 'sha256': 'focus', 'exit_code': 0})
        self.assertEqual(result['takp_window_inspector'], {'state': 'exited', 'read_only': True, 'exit_code': 124})


if __name__ == '__main__':
    unittest.main()
