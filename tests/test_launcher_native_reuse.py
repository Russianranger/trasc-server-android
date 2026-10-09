"""Reject changed/incomplete baseline payloads before an APK-only release."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('native_reuse',Path(__file__).resolve().parents[1]/'scripts/reuse-launcher-native.py')
reuse=importlib.util.module_from_spec(spec);spec.loader.exec_module(reuse)

class NativeReuseTests(unittest.TestCase):
    def fixture(self,path,missing=None,changed=None,include_camera=False):
        with zipfile.ZipFile(path,'w') as archive:
            for name in ['lib/arm64-v8a/'+n for n in reuse.LIBRARIES]+['assets/'+n for n in reuse.ASSETS+(reuse.CAMERA_ASSETS if include_camera else ())]:
                if name!=missing:archive.writestr(name,b'changed' if name==changed else name.encode())
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_only_verified_payload_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);apk=root/'base.apk';sha=self.fixture(apk)
            with self.assertRaises(ValueError):reuse.extract(apk,root/'bad','0'*64)
            self.assertFalse((root/'bad').exists())
            receipt=reuse.extract(apk,root/'out',sha)
            reuse.verify(apk,receipt)
            self.assertEqual(len(receipt['files']),19)
            for record in receipt['files']:
                self.assertEqual(hashlib.sha256((root/'out'/record['path']).read_bytes()).hexdigest(),record['sha256'])

    def test_missing_payload_is_atomic_and_changed_new_apk_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);apk=root/'base.apk';sha=self.fixture(apk,missing='assets/wineserver')
            with self.assertRaises(KeyError):reuse.extract(apk,root/'out',sha)
            self.assertFalse((root/'out').exists())
            sha=self.fixture(apk);receipt=reuse.extract(apk,root/'out',sha)
            changed=root/'changed.apk';self.fixture(changed,changed='assets/turnip.so')
            with self.assertRaises(ValueError):reuse.verify(changed,receipt)

    def test_camera_payload_is_preserved_on_launcher_only_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);apk=root/'base.apk';sha=self.fixture(apk,include_camera=True)
            receipt=reuse.extract(apk,root/'out',sha,'0.6.12',True)
            self.assertEqual(receipt['baseline_version'],'0.6.12')
            self.assertEqual(len(receipt['files']),21)
            reuse.verify(apk,receipt)
            changed=root/'changed.apk';self.fixture(changed,changed='assets/trasc-camera-dinput8.dll',include_camera=True)
            with self.assertRaises(ValueError):reuse.verify(changed,receipt)
            sha=self.fixture(apk,missing='assets/traditional-camera-bundle.json',include_camera=True)
            with self.assertRaises(KeyError):reuse.extract(apk,root/'missing',sha,'0.6.12',True)
            self.assertFalse((root/'missing').exists())

if __name__=='__main__':unittest.main()
