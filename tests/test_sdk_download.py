"""Consent, verified downloads, reusable caches and transactional SDK preparation."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import client_toolchain as sdk
import client_dll
from engine import Engine
import test_sdk_packer


class Response(io.BytesIO):
    def __init__(self, data, headers=None, url='https://download.microsoft.com/file'):
        super().__init__(data)
        self.headers = headers or {}
        self.url = url


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root / 'work')
        self.cache = sdk.cache_path(self.engine)
        self.cache.mkdir(parents=True)
        self.addCleanup(patch.stopall)
        patch('client_toolchain.shutil.disk_usage', return_value=SimpleNamespace(
            total=32 * 1024**3, used=8 * 1024**3, free=24 * 1024**3)).start()
        patch('client_toolchain.MANIFEST_SHA256', hashlib.sha256(b'{}').hexdigest()).start()
        patch('client_toolchain.MANIFEST_BYTES', 2).start()

    def plan(self):
        (self.cache / 'manifest.json').write_text('{}')
        plan = {'manifest_sha256': sdk.sha(self.cache / 'manifest.json'),
                'manifest_version': sdk.MANIFEST_VERSION,
                'license_url': 'https://go.microsoft.com/fwlink/?linkid=2086102',
                'downloader_sha256': sdk.packer().DOWNLOADER_SHA256,
                'options': sdk.OPTIONS, 'prepared_at': sdk.time.time(),
                'download_bytes': 7, 'installed_bytes': 100, 'required_free_bytes': sdk.MIN_FREE}
        plan['token'] = sdk.plan_token(plan)
        sdk.atomic_json(self.cache / 'plan.json', plan)
        return plan

    def test_no_download_or_dependency_setup_without_explicit_acceptance(self):
        plan = self.plan()
        with patch.object(self.engine, 'run') as run:
            for accepted in (None, False, 'true', 1):
                with self.assertRaisesRegex(ValueError, 'explicitly accept'):
                    sdk.download(self.engine, {'accepted': accepted, 'token': plan['token']})
            run.assert_not_called()

    def test_consent_is_bound_to_manifest_terms_options_and_downloader(self):
        for mutation in ('manifest', 'license_url', 'options', 'downloader_sha256', 'expiry'):
            plan = self.plan()
            if mutation == 'manifest':
                (self.cache / 'manifest.json').write_text('{"changed":true}')
            else:
                if mutation == 'license_url': plan[mutation] += '9'
                elif mutation == 'options': plan[mutation] = ['--major', '18']
                elif mutation == 'downloader_sha256': plan[mutation] = '0' * 64
                else: plan['prepared_at'] = sdk.time.time() - sdk.PLAN_AGE - 1
                sdk.atomic_json(self.cache / 'plan.json', plan)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'expired or changed'):
                sdk.load_plan(self.cache, plan['token'])

    def test_self_consistent_changed_catalog_cannot_replace_the_pinned_catalog(self):
        plan = self.plan()
        # Same byte count as '{}' so only the pinned digest rejects it.
        (self.cache / 'manifest.json').write_text('[]')
        plan['manifest_sha256'] = sdk.sha(self.cache / 'manifest.json')
        plan['token'] = sdk.plan_token(plan)
        sdk.atomic_json(self.cache / 'plan.json', plan)
        with self.assertRaisesRegex(ValueError, 'expired or changed'):
            sdk.load_plan(self.cache, plan['token'])

    def test_low_storage_never_starts_download_or_replaces_compiler(self):
        plan = self.plan()
        with patch('client_toolchain.shutil.disk_usage', return_value=SimpleNamespace(free=sdk.MIN_FREE - 1)), patch.object(self.engine, 'run') as run:
            with self.assertRaisesRegex(ValueError, '8 GiB'):
                sdk.download(self.engine, {'accepted': True, 'token': plan['token']})
            run.assert_not_called()

    def test_retry_reclaims_interrupted_staging_before_checking_free_storage(self):
        plan = self.plan()
        abandoned = self.cache / 'prepare-interrupted'
        abandoned.mkdir()
        (abandoned / 'partially-extracted-sdk').write_bytes(b'abandoned staging')
        cached = self.cache / 'downloads/verified.vsix'
        cached.parent.mkdir(); cached.write_bytes(b'keep verified downloads')
        def space(path):
            return SimpleNamespace(free=sdk.MIN_FREE - 1 if abandoned.exists() else sdk.MIN_FREE + 1)
        with patch('client_toolchain.shutil.disk_usage', side_effect=space), \
             patch('client_toolchain.prepare_msiextract', return_value=None), \
             patch.object(self.engine, 'run', side_effect=ValueError('test reached download')) as run:
            with self.assertRaisesRegex(ValueError, 'test reached download'):
                sdk.download(self.engine, {'accepted': True, 'token': plan['token']})
            run.assert_called_once()
        self.assertFalse(abandoned.exists())
        self.assertEqual(cached.read_bytes(), b'keep verified downloads')

    def fetch_fixture(self, data, expected=None, size=None, limit=100, headers=None):
        opener = SimpleNamespace(open=lambda *args, **kwargs: Response(data, headers))
        with patch('client_toolchain.urllib.request.build_opener', return_value=opener):
            return sdk.fetch('https://download.microsoft.com/file', self.root / 'payload', limit,
                             expected_sha=expected, expected_size=size)

    def test_verified_bytes_promoted_and_bad_payloads_do_not_replace_cached_file(self):
        data = b'fixture'
        digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(self.fetch_fixture(data, digest, len(data)), len(data))
        for damaged in (b'corrupt', b'cut', b'fixtureEXTRA'):
            with self.assertRaises(ValueError):
                self.fetch_fixture(damaged, digest, len(data))
            self.assertEqual((self.root / 'payload').read_bytes(), data)
            self.assertFalse((self.root / 'payload.part').exists())

    def test_download_cap_applies_to_unknown_lengths_and_declared_lengths(self):
        with self.assertRaisesRegex(ValueError, 'limit'):
            self.fetch_fixture(b'x' * 20, limit=10)
        with self.assertRaisesRegex(ValueError, 'size'):
            self.fetch_fixture(b'x', limit=10, headers={'Content-Length': '1000'})
        self.assertFalse((self.root / 'payload').exists())

    def test_hash_verified_payload_accepts_actual_length_despite_catalog_estimate(self):
        data = b'signed Microsoft payload fixture'
        digest = hashlib.sha256(data).hexdigest()
        # For payloads, the caller uses a bounded ceiling rather than requiring
        # equality with Microsoft's stale estimate; the SHA remains exact.
        self.assertEqual(self.fetch_fixture(data, digest, limit=128,
                         headers={'Content-Length': str(len(data))}), len(data))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.fetch_fixture(b'x' * len(data), digest, limit=128,
                               headers={'Content-Length': str(len(data))})

    def test_cached_actual_bytes_count_toward_the_total_download_bound(self):
        plan = self.plan()
        payloads = []
        for name in ('one', 'two'):
            data = name.encode() * 2  # Six bytes each; catalog estimate is one.
            payload = {'path': 'Fixture/' + name, 'size': 1,
                       'url': 'https://download.microsoft.com/' + name,
                       'sha256': hashlib.sha256(data).hexdigest()}
            payloads.append(payload)
            file = self.cache / 'downloads' / payload['path']
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        selected = (SimpleNamespace(accept_license=True), [], payloads, plan['license_url'])
        with patch('client_toolchain.checked_downloader'), \
             patch('client_toolchain.selection', return_value=selected), \
             patch('client_toolchain.shutil.which', return_value='/fixture/msiextract'), \
             patch('client_toolchain.MAX_DOWNLOAD', 10), \
             patch('client_toolchain.fetch') as fetch:
            with self.assertRaisesRegex(ValueError, 'Total Microsoft package download'):
                sdk.run_worker(self.cache, self.root / 'stage', self.root / 'output.zip', plan['token'])
            fetch.assert_not_called()
        self.assertFalse((self.root / 'output.zip').exists())

    def test_only_https_microsoft_package_urls_and_redirects_are_allowed(self):
        for url in ('http://download.microsoft.com/file', 'https://microsoft.com.attacker.test/file',
                    'https://user:password@microsoft.com/file', 'file:///tmp/fixture',
                    'https://microsoft.com:444/file'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                sdk.microsoft_url(url)
        with self.assertRaises(ValueError):
            sdk.SecureRedirect().redirect_request(None, None, 302, '', {}, 'http://download.microsoft.com/file')

    def test_cancel_during_stream_removes_partial_file(self):
        opener = SimpleNamespace(open=lambda *args, **kwargs: Response(b'fixture'))
        with patch('client_toolchain.urllib.request.build_opener', return_value=opener):
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                sdk.fetch('https://download.microsoft.com/file', self.root / 'payload', 100,
                          check=lambda: (_ for _ in ()).throw(ValueError('cancelled')))
        self.assertFalse((self.root / 'payload.part').exists())

    def test_download_failure_and_cancellation_preserve_the_existing_compiler(self):
        plan = self.plan()
        current = self.engine.work / 'client/toolchain'
        current.mkdir()
        (current / 'old-compiler').write_text('preserve me')
        for failure in (ValueError('cancelled'), ValueError('checksum mismatch')):
            with patch('client_toolchain.prepare_msiextract', return_value=None), patch.object(self.engine, 'run', side_effect=failure):
                with self.assertRaisesRegex(ValueError, str(failure)):
                    sdk.download(self.engine, {'accepted': True, 'token': plan['token']})
            self.assertEqual((current / 'old-compiler').read_text(), 'preserve me')
            self.assertFalse(list(self.cache.glob('prepare-*')))
            self.assertFalse(list((self.engine.work / 'incoming').glob('microsoft-sdk-*')))
            self.assertEqual(sdk.progress(self.engine)['phase'], 'stopped')

    def test_download_packages_and_imports_real_packer_output_reusing_verified_cache(self):
        fixture = test_sdk_packer.PortableSdkTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        plan = self.plan()
        downloaded = b'fixture'
        payload = {'path': 'Microsoft.Fixture-1/package.vsix',
                   # Authentic Microsoft sizes can differ from SHA-verified
                   # bytes: exercise cache reuse despite the stale estimate.
                   'url': 'https://download.microsoft.com/package.vsix', 'size': 1,
                   'sha256': hashlib.sha256(downloaded).hexdigest()}
        def select(downloader, manifest, accepted=False):
            return SimpleNamespace(accept_license=accepted), [], [payload], plan['license_url']
        def extract(selected, cache, dest):
            shutil.copytree(fixture.vs, dest)
        downloader = SimpleNamespace(extractPackages=extract)
        fetched = []
        def fetch(url, target, *args, **kwargs):
            fetched.append(url)
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_bytes(downloaded)
        def execute(command, **kwargs):
            # Exercise the complete worker and real packer/importer; only the
            # licensed package source/extractor is replaced by generated fixtures.
            sdk.run_worker(Path(command[command.index('--cache') + 1]),
                           Path(command[command.index('--stage') + 1]),
                           Path(command[command.index('--output') + 1]),
                           command[command.index('--accepted-token') + 1])
        with patch('client_toolchain.prepare_msiextract', return_value=None), \
             patch('client_toolchain.checked_downloader', return_value=downloader), \
             patch('client_toolchain.selection', side_effect=select), \
             patch('client_toolchain.shutil.which', return_value='/fixture/msiextract'), \
             patch('client_toolchain.fetch', side_effect=fetch), \
             patch.object(self.engine, 'run', side_effect=execute):
            for _ in range(2):
                result = sdk.download(self.engine, {'accepted': True, 'token': plan['token']})
                self.assertIn('downloaded and imported', result['message'])
                self.assertEqual((self.engine.work / 'client/toolchain/bin/cl.exe').read_bytes(), fixture.pe)
                self.assertTrue(client_dll.compiler_status(self.engine)['sdk'])
                self.assertEqual(sdk.progress(self.engine)['phase'], 'complete')
            self.assertEqual(len(fetched), 1, 'Retry must reuse only checksum-verified package bytes')
            (self.cache / 'downloads' / payload['path']).write_bytes(b'corrupt')
            sdk.download(self.engine, {'accepted': True, 'token': plan['token']})
            self.assertEqual(len(fetched), 2, 'Corrupt cached package must be fetched again')

    def test_dependency_bootstrap_uses_download_only_and_private_extraction(self):
        stage = self.cache / 'fixture-stage'; stage.mkdir()
        commands = []
        def run(command, **kwargs):
            command = [str(item) for item in command]; commands.append(command)
            if '--download-only' in command:
                (stage / 'debs/msitools.deb').write_bytes(b'fixture')
            if command[:2] == ['dpkg-deb', '-x']:
                binary = Path(command[-1]) / 'usr/bin/msiextract'
                binary.parent.mkdir(parents=True); binary.write_text('fixture')
                (Path(command[-1]) / 'lib/aarch64-linux-gnu').mkdir(parents=True)
        with patch('client_toolchain.shutil.which', return_value=None), patch.object(self.engine, 'run', side_effect=run):
            wrapper = sdk.prepare_msiextract(self.engine, stage) / 'msiextract'
        self.assertIn('lib/aarch64-linux-gnu', wrapper.read_text())
        self.assertFalse(any('upgrade' in cmd or 'dpkg' == cmd[0] for cmd in commands))
        install = next(cmd for cmd in commands if 'install' in cmd)
        self.assertIn('--download-only', install)
        self.assertEqual(install[-1], 'msitools')


class CatalogPinTests(unittest.TestCase):
    def test_catalog_pin_is_the_independently_verified_official_release(self):
        self.assertEqual(sdk.MANIFEST_VERSION, '16.11.60+37627.13')
        self.assertEqual(sdk.MANIFEST_BYTES, 11154648)
        self.assertEqual(sdk.MANIFEST_SHA256, '406969c30f4eb8bf0075a0850e339340ac83942705b76269156bb5b70f01b631')
        self.assertEqual(sdk.microsoft_url(sdk.MANIFEST_URL), sdk.MANIFEST_URL)
        self.assertIn('/e2324e87-3765-4b14-85e5-1234d99f6254/', sdk.MANIFEST_URL)


if __name__ == '__main__':
    unittest.main()
