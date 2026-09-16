import hashlib
import json
import io
import zlib
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

    def test_packed_spell_headers_resolve_by_crc_without_extracting_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);client=root/'client';client.mkdir();logs=root/'logs';logs.mkdir()
            pcm=b'RIFF'+struct.pack('<I',36)+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,22050,44100,2,16)+b'data'+struct.pack('<I',0)
            floating=bytearray(pcm);struct.pack_into('<H',floating,20,3);struct.pack_into('<H',floating,34,32)
            # CRC constants obtained with the independent upstream table algorithm.
            entries=[('spelcast.wav',0x6e733495,pcm),('spell_1.wav',0xe89a263b,bytes(floating))]
            data=bytearray(struct.pack('<I4sI',0,b'PFS ',0x20000));records=[]
            def append_block(raw):
                offset=len(data);compressed=zlib.compress(raw)
                data.extend(struct.pack('<II',len(compressed),len(raw))+compressed)
                return offset,len(raw)
            for name,crc,raw in entries: records.append((crc,*append_block(raw)))
            names=struct.pack('<I',2)+b''.join(struct.pack('<I',len(n)+1)+n.encode()+b'\0' for n,_,_ in entries)
            records.append((0x61580ac9,*append_block(names)))
            struct.pack_into('<I',data,0,len(data));data.extend(struct.pack('<I',len(records)))
            # PFS directory order differs from name-table order.
            for record in reversed(records): data.extend(struct.pack('<III',*record))
            archive=client/'SnD2.PFS';archive.write_bytes(data)
            (client/'soundassets.txt').write_text('108^100^SpelCast.WAV\n103^spell_1.wav\n105^spell_3.wav\n')
            before={f.name:f.read_bytes() for f in client.iterdir()}
            client_audio.inspect_client(client,logs,packed=True)
            report=json.loads((logs/'client-sound-assets.json').read_text())
            self.assertTrue(report['packed_scan_complete'])
            self.assertEqual(report['resolved_packed'],2);self.assertEqual(report['unresolved_after_packed'],1)
            self.assertEqual(report['archives']['snd2.pfs']['wav_count'],2)
            self.assertEqual(report['spell_files']['spelcast.wav']['packed'],[{'archive':'snd2.pfs','format':'tag=1,channels=1,rate=22050,bits=16'}])
            self.assertEqual(report['spell_files']['spell_1.wav']['packed'][0]['format'],'tag=3,channels=1,rate=22050,bits=32')
            self.assertEqual({f.name:f.read_bytes() for f in client.iterdir()},before)
            self.assertEqual(client_audio.pfs_crc('SpelCast.WAV'),0x6e733495)
            with self.assertRaisesRegex(ValueError,'read_budget'):client_audio.inspect_pfs(archive,set(),[11])
            # Oversized blocks and dishonest inflate lengths are rejected before extraction.
            bad=bytearray(data);struct.pack_into('<I',bad,records[-1][1]+4,0xffffffff);archive.write_bytes(bad)
            with self.assertRaisesRegex(ValueError,'block_limit'):client_audio.inspect_pfs(archive,set(),[100000])
            client_audio.inspect_client(client,logs,packed=True)
            failed=json.loads((logs/'client-sound-assets.json').read_text())
            self.assertFalse(failed['packed_scan_complete']);self.assertEqual(failed['archives']['snd2.pfs']['status'],'unreadable')
            # Unscanned archives are not represented as successfully checked.
            client_audio.inspect_client(client,logs)
            self.assertFalse(json.loads((logs/'client-sound-assets.json').read_text())['packed_scan_complete'])

    def test_sound_lifecycle_survives_mixer_rotation_and_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'client-wine.log'
            create=b'100.000:0120:0124:trace:dsound:IDirectSoundImpl_CreateSoundBuffer flags=0x10 bytes=4096\n'
            mix=b'100.020:0120:0124:trace:dsound:DSOUND_MixOne mixing buffer\n'
            warning=b'110.000:0120:0124:warn:dsound:DSOUND_Create invalid format 0x0003\n'
            stop=b'120.000:0120:0124:trace:dsound:IDirectSoundBufferImpl_Stop buffer stopped'
            capture=client_runner.WineLog(path,1024)
            capture.pump(io.BufferedReader(io.BytesIO(create+mix*1000+warning+stop),buffer_size=17))
            self.assertNotIn(create,path.read_bytes());self.assertNotIn(create,path.with_suffix('.overflow.log').read_bytes())
            report=json.loads(path.with_suffix('.sound.json').read_text())
            self.assertEqual(report['filtered_mixer_lines'],1000)
            self.assertEqual(report['events']['trace:dsound:IDirectSoundImpl_CreateSoundBuffer']['count'],1)
            self.assertIn('warn:dsound:DSOUND_Create',report['events'])
            self.assertIn('trace:dsound:IDirectSoundBufferImpl_Stop',report['events'])
            collector=client_audio.SoundTrace()
            for i in range(5000): collector.observe(f'1:trace:dsound:Unique{i} '+'x'*4096)
            self.assertEqual(len(collector.events),96);self.assertEqual(collector.dropped,4904)
            for i in range(10000):collector.observe(f'1:trace:dsound:Unique0 index={i}')
            self.assertEqual(collector.events['trace:dsound:Unique0']['count'],10001)
            self.assertIn('index=9999',collector.events['trace:dsound:Unique0']['last'][-1])
            self.assertLess(len(json.dumps(collector.report())),100000)
            collector.observe('1:trace:file:CreateFileW PRIVATE_ACCOUNT_CHAT')
            self.assertNotIn('PRIVATE',json.dumps(collector.report()))

    def test_sound_trace_is_opt_in_and_independent_of_verbose_graphics_logging(self):
        quiet=client_runner.wine_debug();focused=client_runner.wine_debug(sound=True)
        self.assertIn('warn+dsound',quiet);self.assertNotIn('trace+dsound',quiet)
        self.assertIn('trace+dsound',focused);self.assertNotIn('trace+seh',focused)
        with self.assertRaisesRegex(ValueError,'sound diagnostic'):client_runner.validate_request({'sound_diagnostics':'yes'})


if __name__=='__main__':unittest.main()
