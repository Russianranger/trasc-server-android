import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import traditional_camera as camera
import client_mouse


class TraditionalCameraTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.client = self.root / 'client'; self.client.mkdir()
        self.exe = self.client / 'eqgame.exe'; self.exe.write_bytes(b'\0' * 8774656)
        sha = hashlib.sha256(self.exe.read_bytes()).hexdigest()
        self.guard = patch.object(camera, 'EXE_SHA256', sha); self.guard.start(); self.addCleanup(self.guard.stop)
        self.asset = self.root / 'trasc-camera-dinput8.dll'
        raw = bytearray(1024); raw[:2] = b'MZ'; struct.pack_into('<I', raw, 60, 128)
        raw[128:132] = b'PE\0\0'; struct.pack_into('<H', raw, 132, 0x14c)
        raw[256:256+len(camera.MARKER)] = camera.MARKER
        self.asset.write_bytes(raw)
        self.receipt = self.asset.with_name('traditional-camera-bundle.json')
        self.receipt.write_text(json.dumps({'adapter':'traditional-camera-only-v1','file':self.asset.name,
            'sha256':hashlib.sha256(raw).hexdigest(),'executable_sha256':sha}))
        self.request = {'profile':'traditional','mode':'client','executable':'eqgame.exe','mouse_warp':True,'native_dinput8':False}
        self.settings = self.client / 'UI_Rusuty_Traditional.ini'; self.settings.write_bytes(b'font=3\nfilter=saved\n')

    def manager(self):
        instance = camera.Adapter(self.client)
        self.addCleanup(lambda: instance.lock.close() if not instance.lock.closed else None)
        return instance

    def test_absent_dll_is_restored_to_absence_and_preferences_unchanged(self):
        unrelated = self.client/'dinput8.dll.new'; unrelated.write_bytes(b'user-staged DLL')
        manager = self.manager()
        self.assertEqual(manager.prepare(self.request, self.asset)['mode'], 'enabled')
        self.assertEqual(client_mouse.launch_mode(self.request, self.client), 'enabled')
        self.assertEqual((self.client/'dinput8.dll').read_bytes(), self.asset.read_bytes())
        manager.close()
        self.assertFalse((self.client/'dinput8.dll').exists())
        self.assertEqual(self.settings.read_bytes(), b'font=3\nfilter=saved\n')
        self.assertEqual(unrelated.read_bytes(), b'user-staged DLL')
        self.assertFalse(manager.journal.exists())

    def test_exact_imported_filename_bytes_and_metadata_restore(self):
        original = self.client/'DINPUT8.DLL'; original.write_bytes(b'Imported clean DLL')
        original.chmod(0o640); before = original.stat()
        manager = self.manager(); manager.prepare(self.request, self.asset)
        self.assertTrue(manager.backup.exists()); self.assertFalse((self.client/'dinput8.dll').exists())
        manager.close()
        self.assertEqual(original.read_bytes(), b'Imported clean DLL')
        self.assertEqual(original.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(original.stat().st_mode, before.st_mode)

    def test_disable_desktop_and_custom_recover_before_launch(self):
        for changes in ({'mouse_warp':False},{'mode':'desktop'},{'profile':'custom'}):
            manager = self.manager(); manager.prepare(self.request, self.asset)
            manager.lock.close() # Simulate a supervisor killed without finally.
            recovery = self.manager()
            report = recovery.prepare(dict(self.request, **changes), self.asset)
            self.assertEqual(report['mode'], 'off'); self.assertTrue(report['previous_settings_restored'])
            self.assertFalse((self.client/'dinput8.dll').exists()); recovery.close()

    def test_unsupported_executable_and_bad_bundle_leave_original_intact(self):
        original = self.client/'dinput8.dll'; original.write_bytes(b'original')
        manager = self.manager()
        self.exe.write_bytes(b'unsupported')
        self.assertEqual(manager.prepare(self.request, self.asset)['mode'], 'unsupported_executable')
        self.assertEqual(original.read_bytes(), b'original')
        self.exe.write_bytes(b'\0' * 8774656)
        self.asset.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'verification'): manager.prepare(self.request, self.asset)
        self.assertEqual(original.read_bytes(), b'original'); self.assertFalse(manager.journal.exists())

    def test_crash_each_install_boundary_recovers_original(self):
        for boundary in ('before_backup','after_backup'):
            original = self.client/'Dinput8.dll'; original.write_bytes(b'original')
            manager = self.manager(); real_write = manager._write
            if boundary == 'before_backup':
                def interrupted(path, raw):
                    real_write(path, raw)
                    if path == manager.journal: raise SystemExit('simulate kill')
            else:
                def interrupted(path, raw):
                    if path != manager.journal: raise SystemExit('simulate kill')
                    real_write(path, raw)
            with patch.object(manager, '_write', interrupted):
                with self.assertRaises(SystemExit): manager.prepare(self.request, self.asset)
            manager.lock.close()
            recovery = self.manager(); self.assertTrue(recovery.recover()); recovery.close()
            self.assertEqual(original.read_bytes(), b'original'); original.unlink()

    def test_foreign_replacement_is_never_overwritten(self):
        original = self.client/'dinput8.dll'; original.write_bytes(b'original')
        manager = self.manager(); manager.prepare(self.request, self.asset)
        original.write_bytes(b'foreign replacement')
        with self.assertRaisesRegex(ValueError, 'changed'): manager.recover()
        self.assertEqual(original.read_bytes(), b'foreign replacement')
        self.assertEqual(manager.backup.read_bytes(), b'original'); self.assertTrue(manager.journal.exists())

    def test_symlink_and_case_duplicate_are_rejected(self):
        original = self.client/'dinput8.dll'; original.symlink_to(self.settings)
        manager = self.manager()
        with self.assertRaisesRegex(ValueError, 'regular'): manager.prepare(self.request, self.asset)
        self.assertTrue(original.is_symlink()); original.unlink()
        original.write_bytes(b'a'); (self.client/'DINPUT8.dll').write_bytes(b'b')
        with self.assertRaisesRegex(ValueError, 'More than one'): manager.prepare(self.request, self.asset)

    def test_executable_change_blocks_restore_without_losing_backup(self):
        original = self.client/'dinput8.dll'; original.write_bytes(b'original')
        manager = self.manager(); manager.prepare(self.request, self.asset)
        self.exe.write_bytes(b'new executable')
        with self.assertRaisesRegex(ValueError, 'executable changed'): manager.recover()
        self.assertEqual(manager.backup.read_bytes(), b'original')
        self.assertEqual(original.read_bytes(), self.asset.read_bytes())

    def test_profile_session_archive_copy_retains_recovery_ownership(self):
        original = self.client/'DINPUT8.dll'; original.write_bytes(b'original')
        manager = self.manager(); manager.prepare(self.request, self.asset); manager.lock.close()
        copied = self.root/'restored-client'; shutil.copytree(self.client, copied)
        recovery = camera.Adapter(copied)
        try: self.assertTrue(recovery.recover())
        finally: recovery.lock.close()
        self.assertEqual((copied/'DINPUT8.dll').read_bytes(), b'original')
        self.assertEqual((copied/self.settings.name).read_bytes(), self.settings.read_bytes())

    def test_live_session_exclusive_ownership_and_custom_hooks_off(self):
        manager = self.manager()
        with self.assertRaisesRegex(ValueError, 'Another client'): camera.Adapter(self.client)
        manager.prepare(self.request, self.asset)
        custom = dict(self.request, native_dinput8=True, fast_spell_parse=True,
                      reduce_load_pauses=True, particle_mode='repair', boat_mode='profile')
        for mode in (client_mouse.loading_mode,client_mouse.display_mode,client_mouse.particle_mode,client_mouse.boat_mode):
            self.assertEqual(mode(custom, self.client), 'off')
        manager.close()


if __name__ == '__main__': unittest.main()
