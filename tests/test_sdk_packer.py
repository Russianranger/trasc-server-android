"""Verify the portable packer's ZIP against the production Android importer."""
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from engine import Engine
import client_dll

spec = importlib.util.spec_from_file_location('sdk_packer', ROOT / 'tools/pack-client-sdk.py')
packer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packer)


class PortableSdkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vs = self.root / 'unpacked'
        self.vc = self.vs / 'VC/Tools/MSVC/14.29.30133'
        self.kits = self.vs / 'Windows Kits/10'
        self.crt = self.vs / 'VC/Redist/MSVC/14.29.30157/x64/Microsoft.VC142.CRT'
        self.pe = bytearray(154)
        self.pe[:2] = b'MZ'
        struct.pack_into('<I', self.pe, 60, 128)
        self.pe[128:132] = b'PE\0\0'
        struct.pack_into('<H', self.pe, 132, 0x8664)
        struct.pack_into('<H', self.pe, 152, 0x20b)
        for name in ('cl.exe', 'link.exe', 'c1xx.dll', 'c2.dll', 'vctip.exe'):
            self.put(self.vc / 'bin/Hostx64/x86' / name, self.pe)
        for name in ('vcruntime140.dll', 'msvcp140.dll'):
            self.put(self.crt / name, self.pe)
        self.put(self.vc / 'include/vector', b'header')
        self.put(self.vc / 'lib/x86/libcmt.lib', b'library')
        for name in ('um', 'ucrt', 'shared', 'winrt'):
            (self.kits / 'Include/10.0.19041.0' / name).mkdir(parents=True)
        self.put(self.kits / 'Include/10.0.19041.0/um/WINDOWS.H', b'header')
        self.put(self.kits / 'Lib/10.0.19041.0/um/x86/kernel32.lib', b'library')
        self.put(self.kits / 'Lib/10.0.19041.0/ucrt/x86/libucrt.lib', b'library')
        self.output = self.root / 'toolchain.zip'

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def test_archive_imports_with_case_insensitive_headers_and_empty_folders(self):
        packer.package(self.vs, self.output)
        engine = Engine(self.root / 'work')
        shutil.copyfile(self.output, engine.work / 'incoming/toolchain.zip')
        client_dll.import_sdk(engine, {'file': 'toolchain.zip'})
        imported = engine.work / 'client/toolchain'
        self.assertEqual((imported / 'bin/cl.exe').read_bytes(), self.pe)
        self.assertTrue((imported / 'include/winrt').is_dir())
        self.assertFalse((imported / 'bin/vctip.exe').exists())
        self.assertEqual(json.loads((imported / 'sdk.json').read_text())['msvc_version'], '14.29.30133')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            packer.package(self.vs, self.output)

    def test_wrong_host_architecture_and_wrong_toolset_are_rejected(self):
        bad = bytearray(self.pe)
        struct.pack_into('<H', bad, 132, 0xaa64)
        self.put(self.vc / 'bin/Hostx64/x86/cl.exe', bad)
        with self.assertRaisesRegex(ValueError, 'x64-host'):
            packer.package(self.vs, self.output)
        self.assertFalse(self.output.exists())
        self.vc.rename(self.vc.with_name('14.44.12345'))
        with self.assertRaisesRegex(ValueError, 'Required version'):
            packer.package(self.vs, self.output)

    def test_missing_runtime_and_symlink_cannot_create_an_import(self):
        runtime = self.crt / 'msvcp140.dll'
        runtime.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing'):
            packer.package(self.vs, self.output)
        runtime.symlink_to(self.crt / 'vcruntime140.dll')
        with self.assertRaisesRegex(ValueError, 'Linked CRT'):
            packer.package(self.vs, self.output)
        self.assertFalse(self.output.exists())

    def test_failed_activation_and_interrupted_swap_preserve_compiler(self):
        packer.package(self.vs, self.output)
        engine = Engine(self.root / 'work')
        shutil.copyfile(self.output, engine.work / 'incoming/toolchain.zip')
        client_dll.import_sdk(engine, {'file': 'toolchain.zip'})
        current = engine.work / 'client/toolchain'
        (current / 'old-compiler-marker').write_text('keep installed compiler')
        rename = Path.rename
        def failed_activation(source, destination):
            if source.name.startswith('toolchain-import-'):
                raise OSError('simulated activation failure')
            return rename(source, destination)
        with patch.object(Path, 'rename', failed_activation):
            with self.assertRaisesRegex(OSError, 'activation failure'):
                client_dll.import_sdk(engine, {'file': 'toolchain.zip'})
        self.assertEqual((current / 'old-compiler-marker').read_text(), 'keep installed compiler')
        current.rename(engine.work / 'client/toolchain-previous')
        restarted = Engine(engine.work)
        self.assertTrue(client_dll.compiler_status(restarted)['compiler'])
        self.assertEqual((current / 'old-compiler-marker').read_text(), 'keep installed compiler')


if __name__ == '__main__':
    unittest.main()
