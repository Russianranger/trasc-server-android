import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock

import takp_input_diagnostics as diagnostics


class InputDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.prefix = self.root / 'prefix'
        self.prefix.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def test_named_settings_preserved_and_application_override_is_reported(self):
        content = b'''WINE REGISTRY Version 2
[Software\\\\Wine\\\\X11 Driver] 1
"GrabPointer"="N"
"PrivateValue"="do not export"
[Software\\\\Wine\\\\AppDefaults\\\\eqgame.exe\\\\X11 Driver] 2
"GrabPointer"="Y"
[Software\\\\Wine\\\\AppDefaults\\\\eqgame.exe\\\\DirectInput] 3
"MouseWarpOverride"="disable"
'''
        path = self.prefix / 'user.reg'
        path.write_bytes(content)
        before = path.stat().st_mtime_ns
        result = diagnostics.prefix_settings(self.prefix)
        self.assertTrue(result['grab_pointer_enabled'])
        self.assertEqual(result['grab_pointer_source'], 'application')
        self.assertEqual(result['source_sha256'], hashlib.sha256(content).hexdigest())
        self.assertNotIn('PrivateValue', json.dumps(result))
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_disabled_missing_and_unknown_registry_values_remain_distinct(self):
        path = self.prefix / 'user.reg'
        for raw, expected in [('"N"', False), ('"false"', False), ('"0"', False), ('"Y"', True), ('dword:00000001', None)]:
            path.write_text('[Software\\\\Wine\\\\X11 Driver]\n"GrabPointer"=' + raw + '\n')
            self.assertEqual(diagnostics.prefix_settings(self.prefix)['grab_pointer_enabled'], expected)
        path.write_text('WINE REGISTRY Version 2\n')
        result = diagnostics.prefix_settings(self.prefix)
        self.assertEqual(result['grab_pointer_source'], 'wine_default')
        self.assertTrue(result['grab_pointer_enabled'])

    def test_linked_or_oversized_registry_is_not_read(self):
        path = self.prefix / 'user.reg'
        outside = self.root / 'outside.reg'
        outside.write_text('unrelated data')
        path.symlink_to(outside)
        self.assertEqual(diagnostics.prefix_settings(self.prefix)['state'], 'unavailable')
        path.unlink()
        with path.open('wb') as source:
            source.truncate(diagnostics.REGISTRY_LIMIT + 1)
        self.assertEqual(diagnostics.prefix_settings(self.prefix)['state'], 'oversized')

    def test_wrong_observer_bytes_do_not_spawn_or_block_client(self):
        (self.root / 'takp-input-observer.json').write_text(json.dumps({'format': 1, 'bytes': 64, 'sha256': 'wrong'}))
        (self.root / 'takp-xinput-observe').write_bytes(b'not qualified ELF')
        supervisor = Mock(request={'profile': 'takp', 'mode': 'client'})
        result = diagnostics.start(supervisor, self.prefix, self.root / 'logs', self.root)
        self.assertEqual(result['takp_xinput_observer']['state'], 'unavailable')
        supervisor.spawn.assert_not_called()

    def test_verified_arm64_observer_uses_only_bounded_read_only_command(self):
        elf = bytearray(64)
        elf[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', elf, 18, 183)
        (self.root / 'takp-xinput-observe').write_bytes(elf)
        (self.root / 'takp-input-observer.json').write_text(json.dumps({'format': 1, 'bytes': len(elf), 'sha256': hashlib.sha256(elf).hexdigest()}))
        supervisor = Mock(request={'profile': 'takp', 'mode': 'client'})
        supervisor.spawn.return_value.pid = 123
        result = diagnostics.start(supervisor, self.prefix, self.root / 'logs', self.root)
        supervisor.spawn.assert_called_once_with([str(self.root / 'takp-xinput-observe'), '300'], 'client-xinput.log')
        self.assertTrue(result['takp_xinput_observer']['read_only'])
        self.assertFalse((self.prefix / 'user.reg').exists())

    def test_other_profiles_do_not_inspect_or_spawn(self):
        for profile in ('custom', 'traditional'):
            supervisor = Mock(request={'profile': profile, 'mode': 'client'})
            self.assertEqual(diagnostics.start(supervisor, self.prefix, self.root / 'logs', self.root), {})
            supervisor.spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
