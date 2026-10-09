import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_vulkan


class RenderAssetsTests(unittest.TestCase):
    def test_shader_constant_experiment_changes_only_one_flag_and_is_reversible(self):
        for mode in ('standard', 'compatibility', 'compatibility_042', 'direct_043'):
            baseline = client_vulkan.npc_configuration(mode)
            enabled = client_vulkan.npc_configuration(mode, True)
            self.assertEqual(enabled, baseline + ('; ' if baseline else '') + 'd3d9.strictConstantCopies = True')
            self.assertEqual(client_vulkan.npc_configuration(mode, False), baseline)
        self.assertIn('allowDirectBufferMapping = False', client_vulkan.npc_configuration('compatibility_042', True))
        for invalid in (None, 'false', 1):
            with self.assertRaises(ValueError): client_vulkan.npc_configuration('standard', invalid)

    def test_inventory_hashes_selected_files_and_never_exports_private_ini_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ini = root / 'EQCLIENT.INI'
            ini.write_bytes(b'\xef\xbb\xbf; preserve\r\n[Defaults]\r\nSky=1\r\nVertexShaders=TRUE\r\nShowNamesLevel=4\r\nAccount=Secret\r\nFont=Private Name\r\n[Other]\r\nSky=999\r\n')
            (root / 'DEFAULTS.INI').write_bytes(b'[Defaults]\nSkyType=2\n')
            (root / 'eqgame.exe').write_bytes(b'private executable fixture')
            effects = root / 'rendereffects' / 'spl'
            effects.mkdir(parents=True)
            (effects / 'skinmeshcbs1_vsb.fxo').write_bytes(b'private shader fixture')
            before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
            report = client_vulkan.render_assets_status(root)
            self.assertEqual(report['settings']['eqclient.ini']['values'],
                             {'sky': '1', 'vertexshaders': 'TRUE', 'shownameslevel': '4'})
            self.assertEqual(report['files']['eqgame.exe']['sha256'], hashlib.sha256(before[root / 'eqgame.exe']).hexdigest())
            self.assertEqual(report['files']['RenderEffects/SPL/SkinMeshCBS1_VSB.fxo']['bytes'], 22)
            self.assertTrue(report['read_only'])
            self.assertNotIn('Secret', str(report)); self.assertNotIn('Private Name', str(report))
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob('*') if path.is_file()})

    def test_duplicate_choices_are_reported_without_guessing_which_value_wins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'eqclient.ini').write_bytes(b'[Defaults]\nSky=garbage\nSKY=1\nVertexShaders=TRUE\nvertexshaders=FALSE\n')
            report = client_vulkan.render_assets_status(root)
            self.assertEqual(report['settings']['eqclient.ini'], {'values': {}, 'ambiguous_keys': ['sky', 'vertexshaders']})
            (root / 'EQCLIENT.INI').write_bytes(b'other')
            report = client_vulkan.render_assets_status(root)
            self.assertEqual(report['files']['eqclient.ini']['reason'], 'ambiguous')

    def test_symlinked_files_and_directories_are_never_read(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); root = base / 'client'; root.mkdir()
            outside = base / 'outside'; outside.mkdir()
            (outside / 'sky.s3d').write_bytes(b'outside sky')
            (outside / 'skies.ini').write_bytes(b'outside skies')
            (root / 'sky.s3d').symlink_to(outside / 'sky.s3d')
            (root / 'Resources').symlink_to(outside, target_is_directory=True)
            report = client_vulkan.render_assets_status(root)
            for name in ('sky.s3d', 'Resources/skies.ini'):
                self.assertEqual(report['files'][name]['reason'], 'symlink_rejected')
                self.assertNotIn('sha256', report['files'][name])

    def test_oversized_ini_and_asset_are_metadata_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, size in (('eqclient.ini', 2 * 1024 * 1024 + 1), ('eqgame.exe', 32 * 1024 * 1024 + 1)):
                with (root / name).open('wb') as stream: stream.truncate(size)
            report = client_vulkan.render_assets_status(root)
            self.assertEqual(report['read_bytes'], 0)
            for name in ('eqclient.ini', 'eqgame.exe'):
                self.assertTrue(report['files'][name]['present'])
                self.assertEqual(report['files'][name]['reason'], 'read_limit')
                self.assertNotIn('sha256', report['files'][name])

    def test_utf16_and_missing_candidates_are_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'eqclient.ini').write_bytes('[Defaults]\nSky=1'.encode('utf-16'))
            report = client_vulkan.render_assets_status(root)
            self.assertEqual(report['settings']['eqclient.ini']['status'], 'unsupported_utf16')
            self.assertEqual(report['files']['sky.s3d']['reason'], 'not_located')
            self.assertIn('not proof', report['note'])
