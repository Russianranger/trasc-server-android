import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import client_vulkan
import client_runner
import client_metrics


class VulkanTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.bundle=self.root/'bundle';self.bundle.mkdir()
        elf=bytearray(64);elf[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',elf,18,183)
        for n in (*client_vulkan.DRIVERS.values(),'vulkan-probe'):(self.bundle/n).write_bytes(elf)
        (self.bundle/'dxvk-d3d9.dll').write_bytes(b'test DXVK')
        manifest={'format':2,'mesa':'24.3.4','dxvk':'2.5.3','architecture':'arm64-glibc','kmd':'kgsl','drivers':client_vulkan.DRIVERS,
                  'files':{n:hashlib.sha256((self.bundle/n).read_bytes()).hexdigest() for n in client_vulkan.FILES}}
        (self.bundle/'vulkan-bundle.json').write_text(json.dumps(manifest))

    def tearDown(self): self.tmp.cleanup()

    def test_hud_on_off_is_explicit_and_validated(self):
        request={'mode':'desktop','resolution':'1280x720','renderer':'turnip'}
        for enabled in (True,False):
            current={**request,'dxvk_hud':enabled}
            client_runner.validate_request(current)
            host=client_runner.Supervisor(current)
            self.assertEqual(host.env['DXVK_HUD'],'devinfo,fps,compiler' if enabled else '0')
            self.assertEqual(host.status['dxvk_hud'],enabled)
        self.assertEqual(client_runner.Supervisor(request).env['DXVK_HUD'],'devinfo,fps,compiler')
        for invalid in ('false',0,None):
            with self.assertRaisesRegex(ValueError,'HUD'):client_runner.validate_request({**request,'dxvk_hud':invalid})

    def test_preflight_rejects_software_wrong_driver_incomplete_presentation(self):
        good={'driver_id':18,'vendor_id':0x5143,'software':False,'api_version':(1<<22|3<<12),'presentation_frames':3}
        self.assertEqual(client_vulkan.parse_probe('diagnostic\n'+json.dumps(good)),good)
        for bad in ({'software':True},{'driver_id':13},{'vendor_id':0},{'presentation_frames':0},{'api_version':0}):
            with self.assertRaises(RuntimeError):client_vulkan.parse_probe(json.dumps({**good,**bad}))
        self.assertTrue(client_vulkan.parse_probe(json.dumps({**good,'driver_id':13,'software':True}),allow_software=True)['software'])
        with self.assertRaises(RuntimeError):client_vulkan.parse_probe('No usable Vulkan device')

    def test_bundle_verification_precedes_prefix_change_and_recovery_uses_builtin(self):
        prefix=self.root/'prefix';target=prefix/'drive_c/windows/syswow64/d3d9.dll';target.parent.mkdir(parents=True);target.write_bytes(b'original Wine')
        client=self.root/'client';client.mkdir()
        client_vulkan.install_d3d9(self.bundle,prefix,client)
        self.assertEqual((prefix/'trasc-renderers/wine-d3d9.dll').read_bytes(),b'original Wine')
        client_vulkan.install_d3d9(self.bundle,prefix,client)
        self.assertEqual((prefix/'trasc-renderers/wine-d3d9.dll').read_bytes(),b'original Wine')
        (self.bundle/'dxvk-d3d9.dll').write_bytes(b'corrupt')
        with self.assertRaisesRegex(RuntimeError,'checksum'):client_vulkan.install_d3d9(self.bundle,prefix,client)
        self.assertEqual(target.read_bytes(),b'test DXVK')
        env=client_runner.Supervisor({'mode':'desktop','resolution':'800x600','renderer':'virgl'}).env
        self.assertIn('d3d9=b',env['WINEDLLOVERRIDES']);self.assertNotIn('VK_ICD_FILENAMES',env)
        (client/'D3D9.DLL').write_bytes(b'user mod')
        with self.assertRaisesRegex(RuntimeError,'imported client contains'):client_vulkan.install_d3d9(self.bundle,prefix,client)
        self.assertEqual((client/'D3D9.DLL').read_bytes(),b'user mod')

    def test_turnip_is_explicit_and_does_not_accept_software_request_flag(self):
        request={'mode':'desktop','resolution':'800x600','renderer':'turnip','graphics_threading':'opengl_worker','allow_software':True}
        with patch.dict(os.environ,{},clear=True):
            client_runner.validate_request(request);env=client_runner.Supervisor(request).env
            self.assertEqual(env['mesa_glthread'],'false');self.assertIn('d3d9=n',env['WINEDLLOVERRIDES'])
            self.assertEqual(env['VK_ICD_FILENAMES'],'/session/turnip-icd.json')
            self.assertEqual(env['MESA_VK_WSI_DEBUG'],'sw')
        with self.assertRaisesRegex(ValueError,'CPU affinity'):client_runner.validate_request({**request,'cpu_affinity':'all-device-cpus'})

    def test_affinity_changes_only_current_game_threads_with_matching_launch_and_start(self):
        proc=self.root/'proc';proc.mkdir();(proc/'self').symlink_to(proc/'10')
        for pid,name,token in [(10,'python','launch'),(20,'eqgame.exe','launch'),(30,'server','launch')]:
            p=proc/str(pid);t=p/'task'/str(pid);t.mkdir(parents=True)
            (p/'environ').write_bytes(('TRASC_CLIENT_LAUNCH='+token+'\0').encode())
            fields=['0']*40;fields[0]='R';fields[19]='100'
            (t/'stat').write_text(str(pid)+' ('+name+') '+' '.join(fields));(t/'status').write_text('Cpus_allowed_list:\t0\n')
        sample=client_metrics.process_threads(10,proc,'launch')
        with patch.object(client_metrics.os,'sched_getaffinity',side_effect=lambda pid:{2,3} if pid==0 else {0}),patch.object(client_metrics.os,'sched_setaffinity') as change:
            report=client_metrics.allow_game_cpus(sample,'launch',proc)
            change.assert_called_once_with(20,{2,3});self.assertEqual(report['changed_threads'],1)
            change.reset_mock();client_metrics.allow_game_cpus(sample,'other-launch',proc);change.assert_not_called()
            for t in sample['threads']: t['start_ticks']=99
            client_metrics.allow_game_cpus(sample,'launch',proc);change.assert_not_called()

    def test_actual_dxvk_load_evidence_is_separate_from_a_requested_renderer(self):
        capture=client_runner.WineLog(self.root/'wine.log')
        capture.observe(b'info: DXVK: v2.5.3\ntrace:loaddll:build_module Loaded L"C:\\windows\\syswow64\\d3d9.dll" at 00100000: native\n')
        fields,_=capture.snapshot();self.assertEqual(fields['dxvk_loaded'],'2.5.3');self.assertTrue(fields['native_d3d9_loaded'])

    def test_driver_switch_selects_exact_icd_and_preserves_baseline_caches(self):
        session=self.root/'session';session.mkdir();prefix=self.root/'prefix'
        baseline_cache=prefix/'trasc-cache/mesa-turnip';baseline_cache.mkdir(parents=True)
        (baseline_cache/'existing-cache').write_bytes(b'keep')
        for version in ('24.3.4','26.0.0','24.3.4'):
            with self.subTest(version=version),patch.dict(os.environ,{},clear=True):
                env={'WINEDLLOVERRIDES':''}
                client_vulkan.configure_environment(env,self.bundle,session,prefix,version)
                manifest,args=client_vulkan.prepare_probe(self.bundle,session,prefix,env,version)
                icd=json.loads((session/'turnip-icd.json').read_text())
                self.assertEqual(icd['ICD']['library_path'],str(self.bundle/client_vulkan.DRIVERS[version]))
                self.assertEqual(args,[str(self.bundle/'vulkan-probe')])
                self.assertEqual(env['VK_DRIVER_FILES'],str(session/'turnip-icd.json'))
                expected='mesa-turnip' if version=='24.3.4' else 'mesa-turnip-26.0.0'
                self.assertEqual(env['MESA_SHADER_CACHE_DIR'],str(prefix/'trasc-cache'/expected))
                self.assertTrue(Path(env['MESA_SHADER_CACHE_DIR']).is_dir())
                self.assertEqual((baseline_cache/'existing-cache').read_bytes(),b'keep')
        request={'mode':'desktop','resolution':'800x600','renderer':'turnip'}
        with patch.dict(os.environ,{},clear=True):
            default=client_runner.Supervisor(request)
            comparison=client_runner.Supervisor(dict(request,turnip_driver='26.0.0'))
            self.assertEqual(default.status['turnip_driver_requested'],'24.3.4')
            self.assertEqual(comparison.status['turnip_driver_requested'],'26.0.0')
            self.assertNotEqual(default.env['DXVK_STATE_CACHE_PATH'],comparison.env['DXVK_STATE_CACHE_PATH'])
        for bad in ('../turnip.so','winlator.zip','',None,[]):
            with self.assertRaisesRegex(ValueError,'Turnip driver'):
                client_runner.validate_request(dict(request,turnip_driver=bad))

    def test_selected_driver_must_match_observed_mesa_version(self):
        report={'driver_id':18,'vendor_id':0x5143,'software':False,'api_version':(1<<22|3<<12),'presentation_frames':3,'driver_version':26<<22}
        client_vulkan.parse_probe(json.dumps(report),expected_mesa='26.0.0')
        with self.assertRaisesRegex(RuntimeError,'loaded Turnip version'):
            client_vulkan.parse_probe(json.dumps(report),expected_mesa='24.3.4')
        report.pop('driver_version')
        with self.assertRaisesRegex(RuntimeError,'loaded Turnip version'):
            client_vulkan.parse_probe(json.dumps(report),expected_mesa='26.0.0')

    def test_added_driver_is_verified_before_icd_change(self):
        session=self.root/'session';session.mkdir();icd=session/'turnip-icd.json';icd.write_text('old')
        (self.bundle/'turnip-26.0.0.so').write_bytes(b'not a driver')
        with self.assertRaisesRegex(RuntimeError,'checksum'):
            client_vulkan.prepare_probe(self.bundle,session,self.root/'prefix',{},'26.0.0')
        self.assertEqual(icd.read_text(),'old')
        manifest=json.loads((self.bundle/'vulkan-bundle.json').read_text())
        manifest['files']['turnip-26.0.0.so']=hashlib.sha256(b'not a driver').hexdigest()
        (self.bundle/'vulkan-bundle.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RuntimeError,'not ARM64'):client_vulkan.verify_bundle(self.bundle)


if __name__=='__main__':unittest.main()
