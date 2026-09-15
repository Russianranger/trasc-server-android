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
        elf=bytearray(64);elf[:5]=b'\x7fELF\x02';struct.pack_into('<H',elf,18,183)
        for n in ('turnip.so','vulkan-probe'):(self.bundle/n).write_bytes(elf)
        (self.bundle/'dxvk-d3d9.dll').write_bytes(b'test DXVK')
        manifest={'format':1,'mesa':'24.3.4','dxvk':'2.5.3','architecture':'arm64-glibc','kmd':'kgsl',
                  'files':{n:hashlib.sha256((self.bundle/n).read_bytes()).hexdigest() for n in client_vulkan.FILES}}
        (self.bundle/'vulkan-bundle.json').write_text(json.dumps(manifest))

    def tearDown(self): self.tmp.cleanup()

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


if __name__=='__main__':unittest.main()
