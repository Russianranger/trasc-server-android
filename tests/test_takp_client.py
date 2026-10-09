"""TAKP import/prepare transactions and policies; no proprietary game fixture."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_display
import client_mouse
import client_runner
import client_ui
import managed_content
import takp_client


def pe32(machine=0x14c):
    data = bytearray(160)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<H', data, 68, machine)
    struct.pack_into('<H', data, 88, 0x10b)
    return bytes(data)


class TestEngine(managed_content.ManagedContent):
    def __init__(self, root):
        self.work = root / 'profiles/takp/work'
        self.work.mkdir(parents=True)
        (self.work / 'incoming').mkdir()
        self.profile = 'takp'
        self.config = {'ip': '127.0.0.1', 'login_port': 6000}
    def check_cancel(self): pass
    def _export_client_data(self):
        folder = self.work / 'server/export'
        folder.mkdir(parents=True, exist_ok=True)
        for name in takp_client.CLIENT_FILES:
            (folder / name).write_bytes(b'TAKP native ' + name.encode())
        return {'files': list(takp_client.CLIENT_FILES), 'filter_applied': False}


class TakpClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.engine = TestEngine(self.root)
        self.client = self.engine.work / 'client/current'

    def content(self, folder, spell='spells_en.txt'):
        folder.mkdir(parents=True)
        for name in takp_client.WINDOWS_FILES:
            (folder / name).write_bytes(pe32())
        for name in ('eqmac.exe', spell, 'eqstr_en.txt', 'global_chr.s3d'):
            (folder / name).write_bytes(b'fixture ' + name.encode())
        (folder / 'eqclient.ini').write_bytes(b'; user settings\r\n[Other]\r\nName=caf\xe9\r\n')
        return folder

    def import_zip(self, content):
        archive = self.engine.work / 'incoming/client.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            for path in content.rglob('*'):
                if path.is_file(): output.write(path, 'TAKP/' + str(path.relative_to(content)))
        return self.engine.import_client_zip({'file':'client.zip'})

    def test_full_import_overlays_only_pinned_takp_mods_and_keeps_other_world(self):
        other = self.root / 'profiles/traditional/work/client/current'
        other.mkdir(parents=True); (other / 'eqgame.exe').write_bytes(b'Traditional untouched')
        content = self.content(self.root / 'source')
        (content / 'd3d8.dll').write_bytes(b'old dgvoodoo')
        result = self.import_zip(content)
        self.assertEqual(result['client']['executable'], 'eqgame.exe')
        self.assertEqual(result['client']['checksum_file'], 'eqmac.exe')
        self.assertEqual(result['client']['client_type'], 'takp')
        self.assertFalse(result['client']['prepared'])
        for name, expected in takp_client.PATCHES.items():
            self.assertEqual(hashlib.sha256((self.client/name).read_bytes()).hexdigest(), expected)
        self.assertFalse((self.client/'dinput8.dll').exists())
        self.assertEqual((other/'eqgame.exe').read_bytes(), b'Traditional untouched')
        self.assertFalse((self.engine.work/'incoming/client.zip').exists())

    def test_legacy_us_import_remains_supported(self):
        self.import_zip(self.content(self.root/'source', spell='spells_us.txt'))
        original = (self.client/'spells_us.txt').read_bytes()
        self.assertFalse((self.client/'spells_en.txt').exists())
        result = self.engine.prepare_client({})
        self.assertFalse((self.client/'spells_en.txt').exists())
        self.assertEqual((self.client/'spells_us.txt').read_bytes(), b'TAKP native spells_us.txt')
        self.assertEqual((self.engine.work/result['backup']/'spells_us.txt').read_bytes(), original)
        self.assertEqual(result['client']['required_files']['spells_en.txt'], 'spells_us.txt')
        self.assertEqual(result['copied_files'], 2)

    def test_en_file_wins_when_both_names_exist_and_sync_preserves_its_checksum(self):
        content = self.content(self.root/'source')
        (content/'spells_us.txt').write_bytes(b'legacy file')
        (content/'spells_en.txt').rename(content/'Spells_EN.TXT')
        self.import_zip(content)
        result = takp_client.install_export(self.engine, self.client, self.engine._export_client_data())
        self.assertEqual((self.client/'Spells_EN.TXT').read_bytes(), b'fixture spells_en.txt')
        self.assertEqual((self.client/'spells_us.txt').read_bytes(), b'TAKP native spells_us.txt')
        backup = self.engine.work / result['backup']
        self.assertEqual((backup/'spells_us.txt').read_bytes(), b'legacy file')
        self.assertFalse((backup/'Spells_EN.TXT').exists())
        self.assertEqual(takp_client.validate_client(self.client)['required_files']['spells_en.txt'], 'Spells_EN.TXT')
        self.assertFalse((self.client/'spells_en.txt').exists())

    def test_missing_or_empty_spell_file_rejects_and_preserves_previous_client(self):
        self.client.mkdir(parents=True); (self.client/'keep').write_bytes(b'previous')
        content = self.content(self.root/'source')
        (content/'spells_en.txt').write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'missing spells_en.txt'): self.import_zip(content)
        self.assertEqual((self.client/'keep').read_bytes(), b'previous')
        (content/'spells_en.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'missing spells_en.txt'): self.import_zip(content)
        self.assertEqual((self.client/'keep').read_bytes(), b'previous')

    def test_incomplete_or_rof2_upload_rejects_and_preserves_previous_install(self):
        self.client.mkdir(parents=True); (self.client/'keep').write_bytes(b'previous')
        content = self.content(self.root / 'source'); (content/'eqgfx_dx8.dll').unlink()
        with self.assertRaisesRegex(ValueError, 'eqgfx_dx8.dll'): self.import_zip(content)
        self.assertEqual((self.client/'keep').read_bytes(), b'previous')
        self.assertFalse((self.engine.work/'client/previous').exists())
        content = self.content(self.root / 'wrong-architecture')
        (content/'eqmain.dll').write_bytes(pe32(0x8664))
        with self.assertRaisesRegex(ValueError, '32-bit x86'): self.import_zip(content)
        self.assertEqual((self.client/'keep').read_bytes(), b'previous')

    def test_import_invalid_bundle_never_replaces_live_client(self):
        self.client.mkdir(parents=True); (self.client/'keep').write_bytes(b'previous')
        content = self.content(self.root/'source')
        with patch.object(takp_client, 'verify_bundle', side_effect=ValueError('bundle mismatch')):
            with self.assertRaisesRegex(ValueError, 'bundle mismatch'): self.import_zip(content)
        self.assertEqual((self.client/'keep').read_bytes(), b'previous')

    def test_prepare_two_files_legacy_login_and_native_window_settings_with_backups(self):
        self.import_zip(self.content(self.root/'source'))
        original = (self.client/'eqclient.ini').read_bytes()
        original_spells = (self.client/'spells_en.txt').read_bytes()
        result = self.engine.prepare_client({'resolution':'1280x720','fullscreen':True})
        self.assertEqual(result['copied_files'], 2)
        self.assertFalse(result['filter_applied'])
        self.assertTrue(result['client']['prepared'])
        self.assertFalse((self.client/'Resources').exists())
        for name in takp_client.CLIENT_FILES:
            self.assertEqual((self.client/name).read_bytes(), b'TAKP native '+name.encode())
        self.assertEqual((self.client/'spells_en.txt').read_bytes(), original_spells)
        self.assertFalse((self.client/'BaseData.txt').exists()); self.assertFalse((self.client/'dbstr_us.txt').exists())
        host = (self.client/'eqhost.txt').read_bytes()
        self.assertIn(b'[Registration Servers]', host); self.assertIn(b'[Login Servers]', host)
        self.assertNotIn(b'[RegistrationServers]', host); self.assertNotIn(b'[LoginServers]', host)
        self.assertEqual(host.count(b'"127.0.0.1:6000"'),2)
        self.assertNotIn(b'Host=',host)
        ini = (self.client/'eqclient.ini').read_bytes()
        for value in (b'FullScreenMode=TRUE', b'BitsPerPixel=32', b'Width=1280', b'Height=720', b'Name=caf\xe9', b'MaxMouseLookFPS=60'):
            self.assertIn(value,ini)
        backup = self.engine.work / result['backup']
        self.assertEqual((backup/'eqclient.ini').read_bytes(),original)
        self.assertFalse((backup/'spells_en.txt').exists())
        self.assertEqual((self.client/'eqmac.exe').read_bytes(),b'fixture eqmac.exe')

    def test_old_login_file_is_repaired_with_backup_and_endpoint_unchanged(self):
        self.client.mkdir(parents=True)
        prefix = self.engine.work/'client/prefix'
        original = b'; keep comment\r\n[RegistrationServers]\r\n{\r\n"192.168.1.20:6000"\r\n}\r\n[LoginServers]\r\n{\r\n"192.168.1.20:6000"\r\n}\r\n'
        (self.client/'EQHOST.TXT').write_bytes(original)
        result = takp_client.repair_login_file(self.client, prefix)
        expected = original.replace(b'[RegistrationServers]', b'[Registration Servers]').replace(b'[LoginServers]', b'[Login Servers]')
        self.assertTrue(result['repaired'])
        self.assertEqual((self.client/'EQHOST.TXT').read_bytes(), expected)
        self.assertFalse((self.client/'eqhost.txt').exists())
        self.assertEqual((prefix/'trasc-takp-login-originals/eqhost.txt').read_bytes(), original)
        self.assertEqual((prefix/'trasc-takp-login-originals/eqhost.previous.txt').read_bytes(), original)
        self.assertFalse(takp_client.repair_login_file(self.client, prefix)['repaired'])
        self.assertEqual((prefix/'trasc-takp-login-originals/eqhost.previous.txt').read_bytes(), original)

    def test_login_repair_rejects_duplicate_sections_before_any_write(self):
        self.client.mkdir(parents=True)
        original = takp_client.login_text('127.0.0.1', 6000).encode() + b'[LoginServers]\r\n{\r\n"127.0.0.1:6000"\r\n}\r\n'
        (self.client/'eqhost.txt').write_bytes(original)
        prefix = self.engine.work/'client/prefix'
        with self.assertRaisesRegex(ValueError, 'one \\[Login Servers\\]'):
            takp_client.repair_login_file(self.client, prefix)
        self.assertEqual((self.client/'eqhost.txt').read_bytes(), original)
        self.assertFalse((prefix/'trasc-takp-login-originals').exists())

    def test_login_repair_refuses_linked_backup_without_changing_host(self):
        self.client.mkdir(parents=True)
        prefix = self.engine.work/'client/prefix'; prefix.mkdir()
        outside = self.root/'outside'; outside.mkdir()
        (prefix/'trasc-takp-login-originals').symlink_to(outside, target_is_directory=True)
        original = takp_client.login_text('127.0.0.1', 6000).replace('Registration Servers', 'RegistrationServers').replace('Login Servers', 'LoginServers').encode()
        (self.client/'eqhost.txt').write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'ordinary directory'):
            takp_client.repair_login_file(self.client, prefix)
        self.assertEqual((self.client/'eqhost.txt').read_bytes(), original)
        self.assertEqual(list(outside.iterdir()), [])

    def test_prepare_cancel_rolls_back_all_files_and_does_not_mark_prepared(self):
        self.import_zip(self.content(self.root/'source'))
        original = {p.name:p.read_bytes() for p in self.client.iterdir() if p.is_file()}
        with patch.object(self.engine, 'check_cancel', side_effect=[None, None, RuntimeError('cancelled')]):
            with self.assertRaisesRegex(RuntimeError,'cancelled'): self.engine.prepare_client({})
        self.assertEqual({p.name:p.read_bytes() for p in self.client.iterdir() if p.is_file()},original)
        self.assertFalse(json.loads((self.client/'trasc-client.json').read_text())['prepared'])

    def test_patch_tamper_and_case_collision_are_rejected(self):
        self.import_zip(self.content(self.root/'source'))
        (self.client/'eqw.dll').write_bytes(b'tampered')
        with self.assertRaises(ValueError): takp_client.validate_client(self.client,patched=True)
        (self.client/'EQGAME.EXE').write_bytes(pe32())
        with self.assertRaisesRegex(ValueError,'Ambiguous'): self.engine.prepare_client({})

    def test_launch_profile_suppresses_every_rof2_hook_and_preserves_graphics_choice(self):
        requested = {'profile':'takp','mode':'client','resolution':'800x600','executable':'eqgame.exe',
                     'renderer':'software', 'native_dinput8':True,'mouse_warp':True,'fast_spell_parse':True,
                     'reduce_load_pauses':True,'particle_mode':'repair','boat_mode':'profile',
                     'native_d3dx':True,'npc_rendering':'compatibility','name_sky_compatibility':True}
        effective = takp_client.effective_request(requested)
        for name in takp_client.DISABLED: self.assertIs(effective[name],False)
        self.assertTrue(requested['native_dinput8'])
        self.assertEqual(effective['npc_rendering'],'standard')
        self.assertEqual(effective['renderer'],'software')
        self.assertEqual(client_runner.client_arguments(effective),['D:\\eqgame.exe'])
        self.assertEqual(client_runner.client_arguments({'executable':'eqgame.exe','profile':'custom'}),['D:\\eqgame.exe','patchme'])
        for function in (client_mouse.launch_mode,client_mouse.loading_mode,client_mouse.display_mode,client_mouse.boat_mode,client_mouse.particle_mode):
            self.assertEqual(function(requested,self.root/'nonexistent'),'off')
        supervisor=client_runner.Supervisor(requested)
        self.assertFalse(supervisor.status['native_dinput8_requested'])
        with self.assertRaises(ValueError): takp_client.effective_request({**requested,'mode':'compiler'})

    def test_loader_status_requires_actual_native_module_traces(self):
        log = client_runner.WineLog(self.root/'wine.log')
        log.observe(b'WINEDLLOVERRIDES=eqw=n;eqgame=n;d3d8=n\n')
        self.assertFalse(log.snapshot()[0]['takp_patch_modules_loaded'])
        log.observe(b'00a4:trace:loaddll:build_module Loaded L"D:\\eqw.dll" at 10000000: native\n')
        self.assertFalse(log.snapshot()[0]['takp_patch_modules_loaded'])
        for name in ('eqgame.dll','d3d8.dll'):
            log.observe(('00a4:trace:loaddll:build_module Loaded L"D:\\'+name+'" at 10000000: native\n').encode())
        self.assertTrue(log.snapshot()[0]['takp_patch_modules_loaded'])

    def test_required_helpers_fail_actionably_and_do_not_claim_loader_success(self):
        prefix = self.root/'prefix'; system = prefix/'drive_c/windows/syswow64'; system.mkdir(parents=True)
        directx = self.root/'directx'; directx.mkdir()
        with self.assertRaisesRegex(ValueError,'msvcp140'): takp_client.runtime_dependencies(prefix,directx)
        for name in takp_client.RUNTIME_LIBRARIES: (system/name).write_bytes(pe32())
        with self.assertRaisesRegex(ValueError,'d3dx9_43'): takp_client.runtime_dependencies(prefix,directx)
        dll = pe32(); (directx/'d3dx9_43.dll').write_bytes(dll)
        (directx/'directx.json').write_text(json.dumps({'source_sha256':client_runner.DIRECTX_SOURCE_SHA256,'files':{'d3dx9_43.dll':{'sha256':hashlib.sha256(dll).hexdigest(),'bytes':len(dll)}}}))
        report = takp_client.runtime_dependencies(prefix,directx)
        self.assertEqual(report['verification'],'file_architecture_only'); self.assertFalse(report['loaded'])
        self.assertEqual((system/'d3dx9_43.dll').read_bytes(),dll)

    def test_roF2_ui_operations_are_blocked_and_native_fps_preference_survives(self):
        for function in (client_ui.install,client_ui.activate,client_ui.restore_settings):
            with self.assertRaisesRegex(ValueError,'TAKP'): function(self.engine,{})
        text = client_display.display_ini('[Options]\r\nMaxFPS=45\r\n', '800x600',False,'takp')
        self.assertIn('MaxFPS=45',text); self.assertNotIn('WindowedWidth=',text)
        self.assertIn('FullScreenMode=FALSE',text); self.assertIn('MaxBGFPS=30',text)


if __name__ == '__main__': unittest.main()
