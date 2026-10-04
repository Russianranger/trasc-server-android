"""The new Traditional pack options preserve the existing Custom manifest."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/pack-runtime.py'


class RuntimePackProfiles(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / 'rootfs.tar'
        with tarfile.open(self.source, 'w') as archive:
            content = b'{"format":1,"architecture":"arm64"}\n'
            member = tarfile.TarInfo('etc/trasc-runtime.json')
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
            member = tarfile.TarInfo('bin')
            member.type = tarfile.SYMTYPE
            member.linkname = 'usr/bin'
            archive.addfile(member)

    def tearDown(self):
        self.temporary.cleanup()

    def pack(self, *options):
        output = self.root / 'runtime-arm64.tar.gz'
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.source), str(output), *options],
                                capture_output=True, text=True)
        return result, output

    def test_defaults_keep_custom_manifest_contract_and_archive_links(self):
        result, output = self.pack()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.root / 'runtime-manifest.json').read_text())
        self.assertEqual(manifest['runtime'], '1.1')
        self.assertEqual(manifest['architecture'], 'arm64')
        self.assertEqual(manifest['file'], 'runtime-arm64.tar.gz')
        self.assertNotIn('profile', manifest)
        self.assertNotIn('build_adapter', manifest)
        self.assertEqual(manifest['bytes'], output.stat().st_size)
        self.assertEqual(manifest['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())
        with tarfile.open(output, 'r:gz') as archive:
            self.assertEqual(archive.getmember('bin').linkname, 'usr/bin')
            self.assertTrue(archive.getmember('bin').issym())

    def test_separate_traditional_manifest_keeps_pinned_adapter_identity(self):
        result, output = self.pack('--runtime', 'traditional-1.0', '--profile', 'traditional',
                                   '--build-adapter', '1', '--manifest-name', 'traditional-manifest.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'runtime-manifest.json').exists())
        manifest = json.loads((self.root / 'traditional-manifest.json').read_text())
        self.assertEqual(manifest['profile'], 'traditional')
        self.assertEqual(manifest['runtime'], 'traditional-1.0')
        self.assertEqual(manifest['build_adapter'], 1)
        self.assertEqual(manifest['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_unsafe_manifest_destination_rejected_before_writing(self):
        result, output = self.pack('--manifest-name', '../runtime-manifest.json')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())


if __name__ == '__main__': unittest.main()
