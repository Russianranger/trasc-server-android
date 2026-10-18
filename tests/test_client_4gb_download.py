"""Official tool downloads are bounded, verified and never replace client data."""
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch, Mock
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_connection as connection
from engine import Engine


def pe():
    raw = bytearray(512)
    raw[:2] = b'MZ'
    struct.pack_into('<I', raw, 0x3c, 64)
    raw[64:68] = b'PE\0\0'
    struct.pack_into('<HH', raw, 68, 0x14c, 1)
    struct.pack_into('<HHH', raw, 84, 224, 0x0103, 0x10b)
    struct.pack_into('<II', raw, 328, 128, 384)
    return bytes(raw)


def archive(raw, name='4gb_patch.exe', mode=0):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        entry = zipfile.ZipInfo(name)
        entry.external_attr = mode << 16
        bundle.writestr(entry, raw)
    return out.getvalue()


class Response(io.BytesIO):
    def __init__(self, raw, url=connection.PATCH_URL, headers=None):
        super().__init__(raw)
        self.url = url
        self.headers = headers or {}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.client = self.work / 'client/current'
        self.client.mkdir(parents=True)
        self.marker = self.client / 'trasc-client.json'
        self.marker.write_text(json.dumps({'imported': True, 'executable': 'eqgame.exe', 'imported_at': 42}))
        self.exe = self.client / 'eqgame.exe'
        self.exe.write_bytes(pe())
        self.host = self.client / 'eqhost.txt'
        self.host.write_bytes(b'[LoginServer]\r\nHost=10.20.30.40:5999\r\n')
        self.tool = self.client / '4gb_patch.exe'
        self.engine = types.SimpleNamespace(work=self.work, profile='custom', cancel=threading.Event())
        # Synthetic, valid PE tool, with independent wire/archive checksum pins.
        # No third-party executable is redistributed in the test suite.
        self.tool_bytes = pe() + b'NTCore download fixture'
        self.zip_bytes = archive(self.tool_bytes)
        constants = patch.multiple(connection, PATCH_ZIP_BYTES=len(self.zip_bytes), PATCH_ZIP_SHA256=connection.sha(self.zip_bytes),
                                   PATCH_EXE_BYTES=len(self.tool_bytes), PATCH_EXE_SHA256=connection.sha(self.tool_bytes))
        constants.start(); self.addCleanup(constants.stop)
        self.opener = Mock()
        self.open = self.opener.open
        self.open.side_effect = lambda request, timeout: Response(self.zip_bytes)
        network = patch.object(connection.urllib.request, 'build_opener', return_value=self.opener)
        network.start(); self.addCleanup(network.stop)

    def download(self, **args):
        args.setdefault('revision', connection.status(self.engine)['patch']['revision'])
        return connection.mutate(self.engine, 'client_4gb_download', args)

    def fixture(self, data):
        self.zip_bytes = data
        connection.PATCH_ZIP_BYTES = len(data)
        connection.PATCH_ZIP_SHA256 = connection.sha(data)

    def assert_client_intact(self):
        self.assertEqual(self.exe.read_bytes(), pe())
        self.assertEqual(self.host.read_bytes(), b'[LoginServer]\r\nHost=10.20.30.40:5999\r\n')
        self.assertFalse((self.work / connection.RECOVERY).exists())

    def test_download_verifies_and_saves_tool_without_applying_or_backups(self):
        state = connection.status(self.engine)
        self.assertTrue(state['patch']['download']['can_download'])
        self.assertFalse(state['patch']['download']['downloaded'])
        result = self.download()
        self.assertEqual(self.tool.read_bytes(), self.tool_bytes)
        self.assertEqual(stat.S_IMODE(self.tool.stat().st_mode), 0o644)
        self.assertTrue(result['patch']['download']['downloaded'])
        self.assertTrue(result['patch']['download']['can_download'])
        self.assertEqual(result['patch']['download']['path'], 'client/current/4gb_patch.exe')
        self.assertFalse(result['patch']['patched'])
        request = self.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://ntcore.com/files/4gb_patch.zip')
        self.assertEqual(self.open.call_args.kwargs['timeout'], 30)
        self.assert_client_intact()

    def test_verified_existing_tool_is_reused_without_network_or_writes(self):
        self.tool = self.tool.with_name('4GB_PATCH.EXE')
        self.tool.write_bytes(self.tool_bytes)
        before = self.tool.stat()
        result = self.download()
        self.open.assert_not_called()
        self.assertIn('already downloaded', result['message'])
        self.assertEqual(result['patch']['download']['path'], 'client/current/4GB_PATCH.EXE')
        self.assertEqual((self.tool.stat().st_ino, self.tool.stat().st_mtime_ns), (before.st_ino, before.st_mtime_ns))
        self.assertFalse((self.client / '4gb_patch.exe').exists())
        self.assert_client_intact()

    def test_builtin_patch_and_protected_original_survive_download(self):
        connection.mutate(self.engine, 'client_4gb_apply', {'revision': connection.sha(pe())})
        before = {str(p.relative_to(self.work)): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        self.download()
        for name, raw in before.items():
            self.assertEqual((self.work / name).read_bytes(), raw)
        self.assertTrue(connection.status(self.engine)['patch']['can_restore'])
        connection.mutate(self.engine, 'client_4gb_restore', {'revision': connection.sha(self.exe.read_bytes())})
        self.assertEqual(self.exe.read_bytes(), pe())
        self.assertEqual(self.tool.read_bytes(), self.tool_bytes)

    def test_only_custom_imported_valid_client_is_allowed(self):
        for profile in ('traditional', 'takp'):
            self.engine.profile = profile
            self.assertFalse(connection.status(self.engine)['patch']['download']['can_download'])
            with self.assertRaisesRegex(ValueError, 'Custom'):
                self.download()
        self.engine.profile = 'custom'
        self.marker.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing client file'):
            self.download()
        self.marker.write_text(json.dumps({'imported': True, 'executable': 'eqgame.exe', 'imported_at': 42}))
        self.exe.write_bytes(b'not an executable')
        with self.assertRaisesRegex(ValueError, 'DOS/PE'):
            self.download(revision=connection.sha(self.exe.read_bytes()))
        self.open.assert_not_called()
        self.assertFalse(self.tool.exists())

    def test_unknown_existing_tool_links_and_ambiguous_casing_are_never_replaced(self):
        self.tool.write_bytes(b'keep my existing tool')
        self.assertFalse(connection.status(self.engine)['patch']['download']['can_download'])
        with self.assertRaisesRegex(ValueError, 'unrecognized'):
            self.download()
        self.assertEqual(self.tool.read_bytes(), b'keep my existing tool')
        self.tool.unlink()
        self.tool.symlink_to(self.exe)
        with self.assertRaisesRegex(ValueError, 'symbolic'):
            self.download()
        self.tool.unlink()
        self.tool.write_bytes(self.tool_bytes)
        (self.client / '4GB_PATCH.EXE').write_bytes(self.tool_bytes)
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            self.download()
        self.open.assert_not_called()
        self.assert_client_intact()

    def test_stale_revision_and_active_client_are_refused_before_network(self):
        with self.assertRaisesRegex(ValueError, 'Reload'):
            self.download(revision='stale')
        run = self.work / 'run'
        run.mkdir()
        (run / 'client-active.json').write_text(json.dumps({'pid': os.getpid()}))
        with self.assertRaisesRegex(ValueError, 'Stop the client'):
            self.download()
        self.open.assert_not_called()
        self.assertFalse(self.tool.exists())
        self.assert_client_intact()

    def test_network_errors_and_cancel_leave_no_partial_tool(self):
        self.open.side_effect = urllib.error.URLError('offline')
        with self.assertRaisesRegex(ValueError, 'connection'):
            self.download()
        self.engine.cancel.set()
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.download()
        self.assertEqual(self.open.call_count, 1)
        self.assertFalse(self.tool.exists())
        self.assert_client_intact()

    def test_response_url_size_headers_and_unbounded_body_are_rejected(self):
        cases = [(self.zip_bytes, 'http://ntcore.com/files/4gb_patch.zip', {}, 'address'),
                 (self.zip_bytes, connection.PATCH_URL, {'Content-Length': '999999999'}, 'size'),
                 (self.zip_bytes, connection.PATCH_URL, {'Content-Length': 'unknown'}, 'size'),
                 (self.zip_bytes + b'x', connection.PATCH_URL, {}, 'limit'),
                 (self.zip_bytes[:-1], connection.PATCH_URL, {}, 'checksum')]
        for raw, url, headers, message in cases:
            with self.subTest(message=message):
                self.open.side_effect = lambda request, timeout, r=raw, u=url, h=headers: Response(r, u, h)
                with self.assertRaisesRegex(ValueError, message):
                    self.download()
                self.assertFalse(self.tool.exists())
        self.assert_client_intact()

    def test_archive_checksum_failure_is_rejected_before_unpacking(self):
        raw = bytearray(self.zip_bytes); raw[20] ^= 1
        self.open.side_effect = lambda request, timeout: Response(raw)
        with self.assertRaisesRegex(ValueError, 'archive checksum'):
            self.download()
        self.assertFalse(self.tool.exists())

    def test_invalid_member_paths_links_duplicates_sizes_and_bytes_are_rejected(self):
        extra = io.BytesIO()
        with zipfile.ZipFile(extra, 'w') as source:
            source.writestr('4gb_patch.exe', self.tool_bytes)
            source.writestr('extra.exe', self.tool_bytes)
        cases = [archive(self.tool_bytes, '../4gb_patch.exe'), archive(self.tool_bytes, 'folder/4gb_patch.exe'),
                 archive(self.tool_bytes, mode=stat.S_IFLNK | 0o777), extra.getvalue(),
                 archive(self.tool_bytes + b'x'), archive(self.tool_bytes[:-1] + b'x'), b'not a ZIP']
        for raw in cases:
            self.fixture(raw)
            with self.subTest(archive_size=len(raw)), self.assertRaises(ValueError):
                self.download()
            self.assertFalse(self.tool.exists())
        self.assertFalse((self.work / '4gb_patch.exe').exists())
        self.assert_client_intact()

    def test_changed_client_installation_executable_or_lease_during_fetch_is_refused(self):
        def changed_marker():
            self.marker.write_text(json.dumps({'imported': True, 'executable': 'eqgame.exe', 'imported_at': 43}))
        def changed_exe():
            self.exe.write_bytes(pe() + b'updated')
        def active_client():
            (self.work / 'run').mkdir(exist_ok=True)
            (self.work / 'run/client-active.json').write_text(json.dumps({'pid': os.getpid()}))
        for change in (changed_marker, changed_exe, active_client):
            self.marker.write_text(json.dumps({'imported': True, 'executable': 'eqgame.exe', 'imported_at': 42}))
            self.exe.write_bytes(pe())
            def fetch(*args):
                change()
                return self.tool_bytes
            with self.subTest(change=change.__name__), patch.object(connection, 'fetch_patch', side_effect=fetch), self.assertRaises(ValueError):
                self.download()
            self.assertFalse(self.tool.exists())

    def test_exclusive_creation_refuses_late_existing_file_without_hardlinks(self):
        original_open = os.open
        def raced_open(path, flags, *args, **kwargs):
            if Path(path) == self.tool and flags & os.O_CREAT:
                self.tool.write_bytes(b'late existing tool')
            return original_open(path, flags, *args, **kwargs)
        with patch.object(connection.os, 'open', side_effect=raced_open), patch.object(connection.os, 'link', side_effect=OSError('unsupported')), self.assertRaisesRegex(ValueError, 'appeared'):
            self.download()
        self.assertEqual(self.tool.read_bytes(), b'late existing tool')
        self.assert_client_intact()

    def test_failed_write_removes_only_own_partial_and_success_needs_no_hardlinks(self):
        with patch.object(connection.os, 'fsync', side_effect=OSError('disk full')), self.assertRaises(OSError):
            self.download()
        self.assertFalse(self.tool.exists())
        with patch.object(connection.os, 'link', side_effect=OSError('unsupported')):
            self.download()
        self.assertEqual(self.tool.read_bytes(), self.tool_bytes)
        self.assert_client_intact()

    def test_write_cleanup_cannot_remove_a_replacement_file(self):
        def replace_during_failure(fd):
            self.tool.unlink()
            self.tool.write_bytes(b'concurrent replacement')
            raise OSError('write failed')
        with patch.object(connection.os, 'fsync', side_effect=replace_during_failure), self.assertRaises(OSError):
            self.download()
        self.assertEqual(self.tool.read_bytes(), b'concurrent replacement')
        self.assert_client_intact()

    def test_cancellation_during_network_and_deadline_stop_before_install(self):
        class CancelledResponse(Response):
            def read(response, count):
                self.engine.cancel.set()
                return super().read(count)
        self.open.side_effect = lambda request, timeout: CancelledResponse(self.zip_bytes)
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.download()
        self.engine.cancel.clear()
        with patch.object(connection.time, 'monotonic', side_effect=[0, 121]), self.assertRaisesRegex(ValueError, 'timed out'):
            self.download()
        self.assertFalse(self.tool.exists())
        self.assert_client_intact()

    def test_redirects_cannot_leave_the_fixed_official_download(self):
        redirect = connection.OfficialPatchRedirect()
        request = urllib.request.Request(connection.PATCH_URL)
        for url in ('http://ntcore.com/files/4gb_patch.zip', 'https://evil.example/4gb_patch.zip', 'https://ntcore.com/other.zip'):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'unexpected'):
                redirect.redirect_request(request, None, 302, 'Found', {}, url)

    def test_engine_dispatch_rejects_stale_profile_and_routes_download(self):
        engine = Engine.__new__(Engine)
        engine.work, engine.profile = self.work, 'custom'
        revision = connection.sha(self.exe.read_bytes())
        with self.assertRaisesRegex(ValueError, 'World profile changed'):
            engine.dispatch('client_4gb_download', {'__profile': 'takp', 'revision': revision})
        self.open.assert_not_called()
        result = engine.dispatch('client_4gb_download', {'__profile': 'custom', 'revision': revision})
        self.assertTrue(result['patch']['download']['downloaded'])


if __name__ == '__main__':
    unittest.main()
