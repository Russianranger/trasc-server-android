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
        self.assertIn('allowDirectBufferMapping = False',client_vulkan.npc_configuration('compatibility'))
        self.assertEqual(client_vulkan.npc_configuration('compatibility_042'),client_vulkan.npc_configuration('compatibility'))
        self.assertEqual(client_vulkan.npc_configuration('direct_043'),client_vulkan.npc_configuration('compatibility').replace('Mapping = False','Mapping = True'))
        client_runner.validate_request({'mode':'desktop','resolution':'1280x720','npc_rendering':'compatibility_042'})
        self.assertEqual(client_vulkan.npc_configuration('standard'),'')
        with self.assertRaises(ValueError):client_vulkan.npc_configuration('unknown')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertFalse(client_vulkan.skin_shader_status(root)['present'])
            shader=root/'rendereffects/spl/skinmeshcbs1_vsb.FXO';shader.parent.mkdir(parents=True);shader.write_bytes(b'fixture')
            self.assertEqual(client_vulkan.skin_shader_status(root)['sha256'],hashlib.sha256(b'fixture').hexdigest())
            self.assertEqual(shader.read_bytes(),b'fixture')

    def test_inventory_finds_case_insensitive_effects_without_exporting_private_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); client=root/'client';client.mkdir();logs=root/'logs';logs.mkdir()
            (client/'SoUnDs').mkdir()
            wave=b'RIFF'+struct.pack('<I',36)+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,22050,22050,1,8)+b'data'+struct.pack('<I',0)
            (client/'SoUnDs/SPELL.WAV').write_bytes(wave)
            (client/'SoundAssets.TXT').write_text('1^100^spell.wav\n2^sounds\\SPELL.WAV\n3^missing.wav\n4^../private.wav\n5^/outside.wav\n')
            ini=b'[Defaults]\nSound=TRUE\nSoundVolume=100\nAccount=PRIVATE_ACCOUNT\n[Other]\nSound=PRIVATE_SOUND\n'
            (client/'EQCLIENT.INI').write_bytes(ini)
            report=client_audio.inspect_client(client,logs)
            self.assertEqual(report['resolved_loose'],2);self.assertEqual(report['unresolved_count'],1)
            saved=(logs/'client-sound-assets.json').read_text()
            self.assertNotIn('PRIVATE',saved);self.assertNotIn('outside',saved)
            full=json.loads(saved);self.assertEqual(full['unsafe_references'],2)
            self.assertEqual(full['wav_formats'],{'tag=1,channels=1,rate=22050,bits=8':1})
            self.assertEqual(full['settings'],{'sound':'TRUE','soundvolume':'100'})
            self.assertEqual((client/'EQCLIENT.INI').read_bytes(),ini)
            client_audio.inspect_client(client,logs)
            self.assertEqual((logs/'client-sound-assets.previous.json').read_text(),saved)

    def test_inventory_does_not_follow_imported_symlinks_or_read_oversized_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);client=root/'client';client.mkdir();logs=root/'logs';logs.mkdir()
            outside=root/'outside';outside.mkdir();(outside/'private.wav').write_bytes(b'PRIVATE')
            (client/'sounds').symlink_to(outside,target_is_directory=True)
            (client/'eqclient.ini').symlink_to(outside/'private.wav')
            (client/'soundassets.txt').write_bytes(b'A'*(2*1024*1024+1))
            result=client_audio.inspect_client(client,logs)
            self.assertEqual(result['loose_wav_count'],0);self.assertEqual(result['settings'],{})
            self.assertTrue(json.loads((logs/'client-sound-assets.json').read_text())['soundassets_unreadable'])

    def test_sound_trace_is_opt_in_and_independent_of_verbose_graphics_logging(self):
        quiet=client_runner.wine_debug();focused=client_runner.wine_debug(sound=True)
        self.assertIn('warn+dsound',quiet);self.assertNotIn('trace+dsound',quiet)
        self.assertIn('trace+dsound',focused);self.assertNotIn('trace+seh',focused)
        with self.assertRaisesRegex(ValueError,'sound diagnostic'):client_runner.validate_request({'sound_diagnostics':'yes'})


if __name__=='__main__':unittest.main()
