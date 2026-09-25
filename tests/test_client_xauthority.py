"""The display's credential stays private and valid without filesystem links."""
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_xauthority


def read_record(path):
    # Parse the public Xauthority wire format independently of the writer.
    data = path.read_bytes()
    family, = struct.unpack_from('!H', data)
    offset = 2
    fields = []
    for _ in range(4):
        length, = struct.unpack_from('!H', data, offset)
        offset += 2
        fields.append(data[offset:offset + length])
        offset += length
    if offset != len(data):
        raise AssertionError('Unexpected truncated or extra Xauthority record')
    return family, fields


class XauthorityTests(unittest.TestCase):
    def test_local_credentials_for_both_private_displays_without_external_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'Xauthority'
            # A test host may allow links; force any accidental use to fail.
            with patch('os.link', side_effect=PermissionError('hard links denied')), \
                    patch('os.symlink', side_effect=AssertionError('No link workaround needed')), \
                    patch('subprocess.run', side_effect=AssertionError('No external writer needed')), \
                    patch('subprocess.Popen', side_effect=AssertionError('No external writer needed')):
                for display in (7, 8):
                    client_xauthority.write_xauthority(path, display)
                    family, fields = read_record(path)
                    self.assertEqual(family, 256, 'Use local-host scope, not FamilyWild')
                    self.assertEqual(fields[:3], [os.fsencode(socket.gethostname()),
                                                 str(display).encode('ascii'), b'MIT-MAGIC-COOKIE-1'])
                    self.assertEqual(len(fields[3]), 16)
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                    self.assertEqual({entry.name for entry in path.parent.iterdir()}, {'Xauthority'})

    def test_new_launch_replaces_stale_credentials_and_resets_permissive_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'Xauthority'
            client_xauthority.write_xauthority(path, 7)
            first = read_record(path)[1][3]
            path.chmod(0o666)
            client_xauthority.write_xauthority(path, 8)
            _, fields = read_record(path)
            self.assertEqual(fields[1], b'8')
            self.assertNotEqual(fields[3], first)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_failed_activation_keeps_existing_auth_and_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'Xauthority'
            client_xauthority.write_xauthority(path, 7)
            previous = path.read_bytes()
            with patch('os.replace', side_effect=OSError('Simulated rename failure')):
                with self.assertRaisesRegex(OSError, 'Simulated rename failure'):
                    client_xauthority.write_xauthority(path, 8)
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual({entry.name for entry in path.parent.iterdir()}, {'Xauthority'})

    def test_replacement_does_not_write_through_a_preexisting_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            other = root / 'other-file'
            other.write_bytes(b'leave this intact')
            path = root / 'Xauthority'
            path.symlink_to(other)
            client_xauthority.write_xauthority(path, 7)
            self.assertFalse(path.is_symlink())
            self.assertEqual(other.read_bytes(), b'leave this intact')
            self.assertEqual(len(read_record(path)[1][3]), 16)


if __name__ == '__main__':
    unittest.main()
