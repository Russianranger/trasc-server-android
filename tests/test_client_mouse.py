import hashlib
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_mouse


class CameraMouseTests(unittest.TestCase):
    def test_android_runtime_deploys_all_dll_adapter_headers(self):
        # The hosted DLL build sees backend/ directly; Android sees only assets
        # copied by RuntimeManager into the directory mounted at /opt/trasc.
        # Check that boundary, which APK asset-presence checks cannot cover.
        repo = Path(__file__).resolve().parents[1]
        manager = (repo / 'app/src/main/java/io/github/russianranger/trasc/RuntimeManager.java').read_text()
        deployment = re.search(
            r'for\(String name:new String\[\]\{([^}]+)\}\)\s*'
            r'try\(InputStream in=context.getAssets\(\).open\(name\)\)\s*'
            r'\{ copy\(in,new File\(backend,name\)\); \}', manager)
        self.assertIsNotNone(deployment, 'Review the Android backend deployment contract')
        deployed = set(re.findall(r'"([^"]+)"', deployment.group(1)))
        self.assertIn('client_mouse.py', deployed)
        self.assertIn('client_dll.py', deployed)
        missing = set(client_mouse.HEADERS) - deployed
        self.assertFalse(missing, 'DLL adapter headers missing from /opt/trasc: ' + ', '.join(sorted(missing)))
        for name in deployed:
            self.assertTrue((repo / 'backend' / name).is_file(), 'Missing packaged backend asset: ' + name)

    def test_launch_requires_opt_in_matching_executable_and_new_native_dll(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exe = root / 'eqgame.exe'; exe.write_bytes(b'\0' * 8774656)
            dll = root / 'DINPUT8.dll'; dll.write_bytes(b'old working DLL')
            request = {'mode':'client', 'executable':'eqgame.exe', 'mouse_warp':True}
            self.assertEqual(client_mouse.launch_mode(request, root), 'unsupported_executable')
            with patch.object(client_mouse, 'EXE_SHA256', hashlib.sha256(exe.read_bytes()).hexdigest()):
                self.assertEqual(client_mouse.launch_mode(request, root), 'needs_dll')
                dll.write_bytes(client_mouse.MARKER.encode()+client_mouse.LOADING_MARKER.encode())
                self.assertEqual(client_mouse.launch_mode(request, root), 'enabled')
                self.assertEqual(client_mouse.launch_mode(dict(request, mouse_warp=False), root), 'off')
                self.assertEqual(client_mouse.launch_mode(dict(request, native_dinput8=False), root), 'needs_dll')
                self.assertEqual(client_mouse.launch_mode(dict(request, mode='desktop'), root), 'off')
                self.assertEqual(client_mouse.loading_mode(request, root), 'profile')
                self.assertEqual(client_mouse.loading_mode(dict(request, fast_spell_parse=True, mouse_warp=False), root), 'fast')
                self.assertEqual(client_mouse.loading_mode(dict(request, native_dinput8=False), root), 'needs_dll')
                self.assertEqual(client_mouse.loading_mode(dict(request, mode='desktop'), root), 'off')
                self.assertEqual(client_mouse.display_mode(dict(request,reduce_load_pauses=True),root),'needs_dll')
                dll.write_bytes(client_mouse.MARKER.encode()+client_mouse.LOADING_MARKER.encode()+client_mouse.DISPLAY_MARKER.encode())
                self.assertEqual(client_mouse.display_mode(request,root),'profile')
                self.assertEqual(client_mouse.display_mode(dict(request,reduce_load_pauses=True),root),'yield')
                self.assertEqual(client_mouse.display_mode(dict(request,native_dinput8=False),root),'needs_dll')
                self.assertEqual(client_mouse.display_mode(dict(request,mode='desktop'),root),'off')
                self.assertEqual(client_mouse.loading_mode(dict(request,fast_spell_parse=True),root),'fast')
                dll.write_bytes(client_mouse.MARKER.encode()+b'TRASC_EQ_LOAD_V1')
                self.assertEqual(client_mouse.launch_mode(request, root), 'enabled')
                self.assertEqual(client_mouse.loading_mode(request, root), 'needs_dll')
                dll.write_bytes(b'TRASC_EQ_CAMERA_MOUSE_V1')
                self.assertEqual(client_mouse.launch_mode(request, root), 'needs_dll')

    def test_build_overlay_keeps_original_sources_and_rejects_changed_wrapper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); original = {}
            for suffix in ('A', 'W'):
                name = f'IDirectInputDevice8{suffix}.cpp'
                original[name] = ('#include "dinput8.h"\n' +
                    f'HRESULT m_IDirectInputDevice8{suffix}::GetDeviceState(DWORD cbData, LPVOID lpvData)\n'
                    '{\n\treturn ProxyInterface->GetDeviceState(cbData, lpvData);\n}')
                (root / name).write_text(original[name])
            original['eqgame.cpp'] = ('HRESULT WINAPI DirectInput8Create(HINSTANCE hinst, DWORD dwVersion,\n'
                '                                  REFIID riidltf, LPVOID *ppvOut,\n'
                '                                  LPUNKNOWN punkOuter) {\nreturn S_OK;\n}')
            (root / 'eqgame.cpp').write_text(original['eqgame.cpp'])
            original['MQ2DetourAPI.cpp'] = Path(__file__).with_name('fixtures').joinpath('checksum_upstream.cpp').read_text()
            (root / 'MQ2DetourAPI.cpp').write_text(original['MQ2DetourAPI.cpp'])
            build = root / 'build'; build.mkdir()
            prepared = client_mouse.prepare_sources(root / 'project.vcxproj', build)
            for name, target in prepared.items():
                self.assertEqual((root / name).read_text(), original[name])
                content = target.read_text()
                if name == 'eqgame.cpp':
                    self.assertIn('trasc_loading::install();', content)
                    self.assertIn('trasc_particles::install();', content)
                elif name == 'MQ2DetourAPI.cpp': self.assertEqual(content.count('trasc_checksum::disjoint'), 2)
                else: self.assertLess(content.index('HRESULT result = ProxyInterface->GetDeviceState'), content.index('trasc_camera::afterRead'))
            (root / 'IDirectInputDevice8W.cpp').write_text('// custom wrapper')
            second = root / 'second'; second.mkdir()
            with self.assertRaisesRegex(ValueError, 'wrapper changed'):
                client_mouse.prepare_sources(root / 'project.vcxproj', second)

    def test_particles_require_both_exact_binaries_new_dll_and_explicit_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            exe=root/'eqgame.exe'; exe.write_bytes(b'\0'*8774656)
            graphics=root/'EQGraphicsDX9.dll'; graphics.write_bytes(b'\0'*1604608)
            dll=root/'dinput8.dll'; dll.write_bytes(b'old')
            request={'mode':'client','executable':'eqgame.exe','particle_mode':'repair'}
            self.assertEqual(client_mouse.particle_mode(dict(request,particle_mode='off'),root),'off')
            self.assertEqual(client_mouse.particle_mode(request,root),'unsupported_executable')
            with patch.object(client_mouse,'EXE_SHA256',hashlib.sha256(exe.read_bytes()).hexdigest()):
                self.assertEqual(client_mouse.particle_mode(request,root),'needs_dll')
                dll.write_bytes(client_mouse.PARTICLE_MARKER.encode())
                self.assertEqual(client_mouse.particle_mode(request,root),'unsupported_graphics')
                with patch.object(client_mouse,'GRAPHICS_SHA256',hashlib.sha256(graphics.read_bytes()).hexdigest()):
                    self.assertEqual(client_mouse.particle_mode(request,root),'repair')
                    self.assertEqual(client_mouse.particle_mode(dict(request,particle_mode='profile'),root),'profile')
                    self.assertEqual(client_mouse.particle_mode(dict(request,mode='desktop'),root),'off')
                    self.assertEqual(client_mouse.particle_mode(dict(request,native_dinput8=False),root),'needs_dll')
                    duplicate=root/'eqgraphicsdx9.dll'; duplicate.write_bytes(graphics.read_bytes())
                    self.assertEqual(client_mouse.particle_mode(request,root),'unsupported_graphics')
                    duplicate.unlink(); graphics.rename(root/'original-graphics.dll')
                    graphics.symlink_to(root/'original-graphics.dll')
                    self.assertEqual(client_mouse.particle_mode(request,root),'unsupported_graphics')

    def test_checksum_overlay_rejects_semantic_source_changes(self):
        source = Path(__file__).with_name('fixtures').joinpath('checksum_upstream.cpp').read_text()
        self.assertEqual(client_mouse.checksum_overlay(source).count('CAutoLock lock(&gDetourCS)'), 2)
        for old, new in [('return ~eax;', 'return eax;'), ('eax = 0xffffffff;', 'eax = 0;'),
                         ('struct mckey key) \n{', 'struct mckey key)\n{')]:
            with self.assertRaisesRegex(ValueError, 'changed'):
                client_mouse.checksum_overlay(source.replace(old, new))
