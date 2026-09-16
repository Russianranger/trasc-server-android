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
import client_audio
import client_runner
import client_vulkan


class AudioTests(unittest.TestCase):
    def test_bundle_requires_integrity_architecture_and_live_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=bytearray(64);data[:5]=b'\x7fELF\x02';struct.pack_into('<H',data,18,183)
            library=root/'libasound_module_pcm_trasc.so';library.write_bytes(data)
            manifest={'protocol':1,'architecture':'arm64-glibc','sha256':hashlib.sha256(data).hexdigest()}
            (root/'audio-bundle.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'not listening'):client_audio.prepare(root,root)
            self.assertFalse((root/'asound.conf').exists())
            library.write_bytes(data+b'changed')
            with self.assertRaisesRegex(RuntimeError,'checksum'):client_audio.prepare(root,root)
            self.assertFalse((root/'asound.conf').exists())

    def test_audio_selection_does_not_change_other_wine_drivers_or_user_environment(self):
        with patch.dict(os.environ,{},clear=True):
            off=client_runner.Supervisor({'mode':'desktop','resolution':'800x600','audio':False}).env
            on=client_runner.Supervisor({'mode':'desktop','resolution':'800x600','audio':True}).env
            self.assertIn('winealsa.drv=d',off['WINEDLLOVERRIDES'])
            self.assertNotIn('winealsa.drv=d',on['WINEDLLOVERRIDES'])
            self.assertEqual(on['TRASC_AUDIO_SOCKET'],'/session/audio.sock')
            self.assertNotIn('ALSA_CONFIG_PATH',os.environ)
        with self.assertRaisesRegex(ValueError,'audio'):client_runner.validate_request({'audio':'true'})

    def test_npc_comparison_is_explicit_and_shader_diagnostics_do_not_replace_assets(self):
        self.assertIn('floatEmulation = Strict',client_vulkan.npc_configuration('compatibility'))
        self.assertIn('allowDirectBufferMapping = True',client_vulkan.npc_configuration('compatibility'))
        self.assertEqual(client_vulkan.npc_configuration('compatibility_042'),client_vulkan.npc_configuration('compatibility').replace('Mapping = True','Mapping = False'))
        client_runner.validate_request({'mode':'desktop','resolution':'1280x720','npc_rendering':'compatibility_042'})
        self.assertEqual(client_vulkan.npc_configuration('standard'),'')
        with self.assertRaises(ValueError):client_vulkan.npc_configuration('unknown')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertFalse(client_vulkan.skin_shader_status(root)['present'])
            shader=root/'rendereffects/spl/skinmeshcbs1_vsb.FXO';shader.parent.mkdir(parents=True);shader.write_bytes(b'fixture')
            self.assertEqual(client_vulkan.skin_shader_status(root)['sha256'],hashlib.sha256(b'fixture').hexdigest())
            self.assertEqual(shader.read_bytes(),b'fixture')


if __name__=='__main__':unittest.main()
