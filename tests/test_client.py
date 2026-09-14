import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_runner
from engine import Engine, CLIENT_FILES
from managed_content import update_ini


def pe(path, machine=0x14c):
    data=bytearray(256);data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,128);data[128:132]=b'PE\0\0';struct.pack_into('<H',data,132,machine);path.write_bytes(data)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.engine=Engine(self.root)
        self.client=self.root/'client/current';self.client.mkdir();pe(self.client/'eqgame.exe');pe(self.client/'dinput8.dll')
        (self.client/'trasc-client.json').write_text(json.dumps({'executable':'eqgame.exe','imported':True}))

    def tearDown(self): self.temp.cleanup()

    def test_pe32_and_native_dll_architecture_validation(self):
        request={'mode':'client','resolution':'800x600','executable':'eqgame.exe','native_dinput8':True}
        with patch.object(client_runner,'CLIENT',self.client):
            client_runner.validate_request(request)
            pe(self.client/'dinput8.dll',0x8664)
            with self.assertRaisesRegex(ValueError,'32-bit'): client_runner.validate_request(request)
            client_runner.validate_request(dict(request,native_dinput8=False))
            with self.assertRaisesRegex(ValueError,'executable name'): client_runner.validate_request(dict(request,executable='../eqgame.exe'))
            with self.assertRaisesRegex(ValueError,'resolution'): client_runner.validate_request(dict(request,resolution='800x600; bad'))

    def test_presence_and_override_are_not_native_load_confirmation(self):
        self.assertFalse(client_runner.dll_status('dinput8.dll present; WINEDLLOVERRIDES=dinput8=n')['native_loaded'])
        self.assertFalse(client_runner.dll_status('trace:loaddll:build_module Loaded L"C:\\windows\\system32\\dinput8.dll": builtin')['native_loaded'])
        self.assertTrue(client_runner.dll_status('trace:loaddll:build_module Loaded L"D:\\dinput8.dll" at 00100000: native')['native_loaded'])

    def test_reported_loader_failure_is_fatal_but_optional_driver_warnings_are_not(self):
        error=client_runner.fatal_launch_error('wine: could not load kernel32.dll, status c0000135')
        self.assertIn('c0000135',error)
        self.assertIn('kernel32.dll',error)
        self.assertIsNone(client_runner.fatal_launch_error('err:ntoskrnl:ZwLoadDriver winebth failed\nError loading needed lib libXcomposite.so.1'))
        dependency='err:module:import_dll Library VCRUNTIME140.dll (which is needed by L"D:\\dinput8.dll") not found'
        self.assertIsNone(client_runner.fatal_launch_error(dependency))
        self.assertIn('VCRUNTIME140.dll',client_runner.fatal_launch_error(dependency+'\nerr:module:loader_init Importing dlls for L"D:\\eqgame.exe" failed, status c0000135'))

    def test_prefix_check_distinguishes_incomplete_prefix_from_missing_runtime(self):
        prefix=self.root/'prefix';wine=self.root/'wine'
        for parent in (prefix/'drive_c/windows/syswow64',wine/'lib/wine/i386-windows'):
            parent.mkdir(parents=True)
            for name in ('ntdll.dll','kernel32.dll','kernelbase.dll','cmd.exe'):pe(parent/name)
        self.assertTrue(client_runner.prefix_diagnostics(prefix,wine)['prefix_ready'])
        (prefix/'drive_c/windows/syswow64/kernel32.dll').unlink()
        report=client_runner.prefix_diagnostics(prefix,wine)
        self.assertFalse(report['prefix_ready']);self.assertTrue(report['runtime_ready'])
        pe(wine/'lib/wine/i386-windows/kernel32.dll',0x8664)
        self.assertFalse(client_runner.prefix_diagnostics(prefix,wine)['runtime_ready'])

    def export_fixture(self, _):
        folder=self.root/'server/export';folder.mkdir(parents=True,exist_ok=True)
        for name in CLIENT_FILES:(folder/name).write_text('generated '+name)
        return {}

    def test_prepare_keeps_other_settings_and_dll_and_backs_up_handshake_files(self):
        (self.client/'eqclient.ini').write_text('; keep comment\n[Defaults]\nWindowedMode=FALSE\nFoo=untouched\n[Other]\nMusic=1\n')
        (self.client/'EQHOST.TXT').write_text('old endpoint');(self.client/'resources').mkdir()
        (self.client/'resources/spells_us.txt').write_text('old spells')
        dll=(self.client/'dinput8.dll').read_bytes()
        with patch.object(self.engine,'export_client',side_effect=self.export_fixture): result=self.engine.prepare_client({'resolution':'960x540'})
        self.assertIn('Host=127.0.0.1:5999',(self.client/'EQHOST.TXT').read_text())
        self.assertFalse((self.client/'eqhost.txt').exists())
        ini=(self.client/'eqclient.ini').read_text();self.assertIn('Foo=untouched',ini);self.assertIn('Music=1',ini);self.assertIn('; keep comment',ini);self.assertIn('WindowedWidth=960',ini)
        self.assertEqual((self.client/'dinput8.dll').read_bytes(),dll)
        self.assertEqual((self.root/result['backup']/'resources/spells_us.txt').read_text(),'old spells')
        for name in CLIENT_FILES:
            self.assertEqual((self.client/name).read_bytes(),(self.client/'resources'/name).read_bytes())

    def test_failed_prepare_restores_already_replaced_files(self):
        first=CLIENT_FILES[0];(self.client/first).write_text('original')
        calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==3: raise RuntimeError('test interruption')
        with patch.object(self.engine,'export_client',side_effect=self.export_fixture),patch.object(self.engine,'check_cancel',side_effect=cancel):
            with self.assertRaisesRegex(RuntimeError,'interruption'):self.engine.prepare_client({})
        self.assertEqual((self.client/first).read_text(),'original')
        self.assertFalse((self.client/'Resources'/first).exists())

    def test_ini_sections_are_preserved_and_values_replace_case_insensitively(self):
        text='[defaults]\nwindowedmode=FALSE\n[Unrelated]\nWidth=7\n'
        updated=update_ini(text,'Defaults',{'WindowedMode':'TRUE'})
        self.assertIn('windowedmode=TRUE\r\n[Unrelated]\r\nWidth=7',updated)
        self.assertEqual(updated.count('[defaults]'),1)


if __name__=='__main__':unittest.main()
