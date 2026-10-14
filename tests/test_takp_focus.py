import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock

import takp_focus


class TakpFocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.session = self.root / 'session'
        self.session.mkdir()
        self.supervisor = Mock(request={'profile': 'takp', 'mode': 'client'},
            status={'takp_input_settings': {'grab_pointer_enabled': True}},
            env={'TRASC_CLIENT_LAUNCH': '0123456789abcdef0123456789abcdef'})
        self.supervisor.spawn.return_value.pid = 123
        self.elf = bytearray(64) + takp_focus.MARKER.encode()
        self.elf[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', self.elf, 18, 183)
        self.receipt = {'format': 1, 'marker': takp_focus.MARKER, 'bytes': len(self.elf),
            'sha256': hashlib.sha256(self.elf).hexdigest(), 'bounded_output_bytes': 128*1024,
            'window_titles': ['EqW-TAKP', 'Client1'], 'window_class': 'eqgame.exe',
            'focus_event_protocol': 1, 'focus_event_max_bytes': 96}
        (self.root/'takp-xinput-focus').write_bytes(self.elf)
        self.write_receipt()

    def tearDown(self):
        self.temp.cleanup()

    def write_receipt(self):
        (self.root/'takp-input-focus.json').write_text(json.dumps(self.receipt))

    def test_only_qualified_helper_is_launched_and_lifecycle_owned(self):
        result = takp_focus.start(self.supervisor, self.root/'logs', self.root, self.session)
        self.supervisor.spawn.assert_called_once_with([str(self.root/'takp-xinput-focus')], 'client-takp-focus.log')
        self.assertIs(self.supervisor.takp_focus_process, self.supervisor.spawn.return_value)
        self.assertEqual(result['takp_focus_recovery']['state'], 'started')
        self.assertFalse(result['takp_focus_recovery']['prefix_settings_changed'])
        self.assertEqual(self.supervisor.env['TRASC_TAKP_FOCUS_EVENT_NATIVE'], str(self.session/'takp-focus.event'))

    def test_unqualified_or_broadened_identity_refuses_without_blocking_client(self):
        for field, value in [('sha256', 'wrong'), ('window_class', 'wine'), ('window_titles', ['*']),
                             ('window_titles', ['EqW-TAKP', 'Client1', 'Client2']),
                             ('focus_event_protocol', 0), ('focus_event_max_bytes', 100000),
                             ('marker', 'unknown'), ('bounded_output_bytes', 0)]:
            with self.subTest(field=field):
                original = self.receipt[field]
                self.receipt[field] = value
                self.write_receipt()
                result = takp_focus.start(self.supervisor, self.root/'logs', self.root, self.session)
                self.assertEqual(result['takp_focus_recovery']['state'], 'unavailable')
                self.supervisor.spawn.assert_not_called()
                self.receipt[field] = original
        self.write_receipt()
        (self.root/'takp-input-focus.json').write_text('[]')
        self.assertEqual(takp_focus.start(self.supervisor, self.root/'logs', self.root)['takp_focus_recovery']['state'], 'unavailable')
        self.supervisor.spawn.assert_not_called()
        self.write_receipt()
        path = self.root/'takp-xinput-focus'
        target = self.root/'other'
        path.rename(target)
        path.symlink_to(target)
        self.assertEqual(takp_focus.start(self.supervisor, self.root/'logs', self.root)['takp_focus_recovery']['state'], 'unavailable')
        self.supervisor.spawn.assert_not_called()

    def test_existing_disabled_unknown_configuration_and_other_profiles_are_preserved(self):
        for value in (False, None):
            self.supervisor.status = {'takp_input_settings': {'grab_pointer_enabled': value}}
            result = takp_focus.start(self.supervisor, self.root/'logs', self.root)
            self.assertEqual(result['takp_focus_recovery']['state'], 'preserved_configuration')
        for profile, mode in [('custom', 'client'), ('traditional', 'client'), ('takp', 'winecfg')]:
            self.supervisor.request = {'profile': profile, 'mode': mode}
            self.assertEqual(takp_focus.start(self.supervisor, self.root/'logs', self.root), {})
        self.supervisor.spawn.assert_not_called()

    def test_private_event_links_oversize_and_foreign_launch_refuse_without_modification(self):
        event = self.session/'takp-focus.event'
        other = self.root/'other-event'
        other.write_bytes(b'preserve')
        event.symlink_to(other)
        result = takp_focus.start(self.supervisor, self.root/'logs', self.root, self.session)
        self.assertEqual(result['takp_focus_recovery']['state'], 'unavailable')
        self.assertEqual(other.read_bytes(), b'preserve')
        event.unlink()
        import os
        os.link(other, event)
        self.assertEqual(takp_focus.start(self.supervisor, self.root/'logs', self.root, self.session)
                         ['takp_focus_recovery']['state'], 'unavailable')
        event.unlink()
        event.write_bytes(b'x'*97)
        self.assertEqual(takp_focus.start(self.supervisor, self.root/'logs', self.root, self.session)
                         ['takp_focus_recovery']['state'], 'unavailable')
        self.assertEqual(event.read_bytes(), b'x'*97)
        event.unlink()
        self.supervisor.env['TRASC_CLIENT_LAUNCH'] = 'foreign'
        self.assertEqual(takp_focus.start(self.supervisor, self.root/'logs', self.root, self.session)
                         ['takp_focus_recovery']['state'], 'unavailable')
        self.supervisor.spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
