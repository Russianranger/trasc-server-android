import json
import hashlib
import io
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

    def test_normal_launch_disables_hot_traces_but_keeps_errors_and_dll_proof(self):
        normal=client_runner.Supervisor({'mode':'client','resolution':'800x600'}).env['WINEDEBUG']
        self.assertEqual(normal,'-all,+timestamp,+pid,err+all,trace+loaddll')
        self.assertNotIn('trace+seh',normal)
        self.assertIn('trace+seh',client_runner.wine_debug(True))

    def test_stream_rotation_keeps_load_evidence_and_split_fatal_error(self):
        path=self.root/'client-wine.log'
        proxy=b'trace:loaddll:build_module Loaded L"D:\\dinput8.dll" at 00100000: native\n'
        system=b'trace:loaddll:build_module Loaded L"C:\\windows\\syswow64\\dinput8.dll" at 70000000: builtin\n'
        payload=proxy+system+b'ordinary output\n'*900+b'wine: could not load kernel32.dll, status c0000135'
        capture=client_runner.WineLog(path,1024)
        capture.pump(io.BufferedReader(io.BytesIO(payload),buffer_size=37))
        fields,error=capture.snapshot()
        self.assertEqual(fields['wine_log_bytes'],len(payload))
        self.assertTrue(fields['native_loaded']);self.assertTrue(fields['system_dinput8_loaded'])
        self.assertIn('c0000135',error)
        self.assertGreater(fields['wine_log_rotations'],1)
        self.assertLessEqual(path.stat().st_size,1024)
        self.assertLessEqual(path.with_suffix('.overflow.log').stat().st_size,1024)
        self.assertEqual(len(fields['dll_evidence']),2)
        self.assertIn(b'c0000135',path.read_bytes())

    def test_upgrade_archives_large_old_trace_without_copying_a_gigabyte(self):
        path=self.root/'client-wine.log';previous=path.with_suffix('.previous.log')
        path.write_bytes(b'FIRST\n'+b'a'*10000+b'\nLAST\n')
        client_runner.archive_log(path,1024)
        data=previous.read_bytes()
        self.assertFalse(path.exists());self.assertEqual(len(data),1024)
        self.assertTrue(data.startswith(b'FIRST'));self.assertTrue(data.endswith(b'LAST\n'))
        self.assertIn(b'previous log shortened',data)
        path.write_bytes(b'next small session')
        client_runner.archive_log(path,1024)
        self.assertEqual(previous.read_bytes(),b'next small session')

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

    def test_proxy_and_system_directinput_loads_are_distinguished(self):
        proxy=r'146718.383:0194:0198:trace:loaddll:build_module Loaded L"D:\\DINPUT8.dll" at 7AE60000: native'
        system=r'146720.142:0194:0198:trace:loaddll:build_module Loaded L"C:\\windows\\system32\\dinput8.dll" at 70000000: builtin'
        status=client_runner.dll_status(proxy+'\n'+system)
        self.assertTrue(status['native_loaded']);self.assertTrue(status['system_dinput8_loaded'])
        self.assertEqual(status['evidence'],[proxy,system])
        self.assertFalse(client_runner.dll_status(system)['native_loaded'])
        self.assertFalse(client_runner.dll_status(proxy)['system_dinput8_loaded'])
        self.assertFalse(client_runner.dll_status(system.replace('builtin','native'))['native_loaded'])

    def test_stop_reason_separates_requested_stop_from_error(self):
        supervisor=client_runner.Supervisor({'mode':'desktop','resolution':'800x600'})
        with patch.object(client_runner,'SESSION',self.root),patch.object(client_runner,'stop_requested',False),patch.object(client_runner,'stop_reason',None):
            self.assertFalse(supervisor.stopping())
            (self.root/'stop').touch();self.assertTrue(supervisor.stopping())
            self.assertEqual(supervisor.status['stop_reason'],'stop_request')
        with patch.object(client_runner,'stop_requested',True),patch.object(client_runner,'stop_reason','SIGTERM'):
            self.assertTrue(supervisor.stopping())
            self.assertEqual(supervisor.status['stop_reason'],'SIGTERM')

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


    def model_fixture(self):
        source=self.root/'directx';source.mkdir()
        destination=self.root/'prefix/drive_c/windows/syswow64';destination.mkdir(parents=True)
        manifest={'format':1,'source_sha256':client_runner.DIRECTX_SOURCE_SHA256,'files':{}}
        for name in client_runner.MODEL_DLLS:
            pe(source/name)
            manifest['files'][name]={'bytes':(source/name).stat().st_size,'sha256':hashlib.sha256((source/name).read_bytes()).hexdigest()}
            (destination/name).write_bytes(b'original builtin '+name.encode())
        (source/'directx.json').write_text(json.dumps(manifest))
        return source,destination

    def test_models_validate_complete_pair_and_preserve_original_system_files(self):
        source,destination=self.model_fixture()
        original={n:(destination/n).read_bytes() for n in client_runner.MODEL_DLLS}
        client_runner.prepare_model_libraries(source,self.root/'prefix')
        for name in client_runner.MODEL_DLLS:
            self.assertEqual((destination/name).read_bytes(),(source/name).read_bytes())
            self.assertEqual((self.root/'prefix/trasc-directx-originals'/name).read_bytes(),original[name])
        client_runner.prepare_model_libraries(source,self.root/'prefix')
        (source/'d3dx9_35.dll').write_bytes(b'bad'+b'x'*253)
        with self.assertRaisesRegex(ValueError,'verification'):client_runner.prepare_model_libraries(source,self.root/'prefix')
        self.assertEqual((destination/'d3dx9_30.dll').read_bytes(),(source/'d3dx9_30.dll').read_bytes())

    def test_bad_model_pair_and_failed_install_do_not_leave_partial_replacement(self):
        source,destination=self.model_fixture()
        original={n:(destination/n).read_bytes() for n in client_runner.MODEL_DLLS}
        real_replace=client_runner.os.replace
        def fail_second(src,dest):
            if Path(src).name=='d3dx9_35.dll':raise OSError('simulated install failure')
            return real_replace(src,dest)
        with patch.object(client_runner.os,'replace',side_effect=fail_second):
            with self.assertRaisesRegex(OSError,'simulated'):client_runner.prepare_model_libraries(source,self.root/'prefix')
        for name in client_runner.MODEL_DLLS:self.assertEqual((destination/name).read_bytes(),original[name])
        (source/'d3dx9_35.dll').write_bytes(b'bad'+b'x'*253)
        with self.assertRaisesRegex(ValueError,'verification'):client_runner.prepare_model_libraries(source,self.root/'prefix')
        for name in client_runner.MODEL_DLLS:self.assertEqual((destination/name).read_bytes(),original[name])

    def test_model_load_evidence_distinguishes_native_and_builtin(self):
        trace=r'0194:trace:loaddll:build_module Loaded L"C:\\windows\\system32\\D3DX9_35.dll" at 1000: native'
        self.assertEqual(client_runner.model_dll_status(trace)[0],{'d3dx9_35.dll':'native'})
        self.assertEqual(client_runner.model_dll_status(trace.replace('native','builtin'))[0],{'d3dx9_35.dll':'builtin'})
        self.assertEqual(client_runner.model_dll_status('Installed d3dx9_35.dll; d3dx9_35=n,b')[0],{})

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
