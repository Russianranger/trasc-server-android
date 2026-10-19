#!/usr/bin/env python3
"""Package the authorized main-branch beta after compile/lint and native verification."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

assert os.environ['GITHUB_REF'] == 'refs/heads/main'
assert os.environ['GITHUB_REPOSITORY'] == 'Russianranger/trasc-server-android'
head = os.environ['GITHUB_SHA']
gradle = Path('app/build.gradle').read_text()
assert re.search(r"versionName\s+'0\.7\.0-beta'", gradle)
assert re.search(r'versionCode\s+92\b', gradle)
assert "VERSION = '0.7.0-beta'" in Path('backend/engine.py').read_text()
cert = re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]+)', Path('dist/apk-signing.txt').read_text()).group(1)
assert cert == Path('docs/preview-signing.sha256').read_text().strip()

apk = Path('dist/trasc-server-android-beta-0.7.0.apk')
shutil.copyfile('app/build/outputs/apk/debug/app-debug.apk', apk)
with zipfile.ZipFile(apk) as archive:
    # Check every shipped UI file, and every top-level Python backend module.
    for root, prefix, pattern in ((Path('app/src/main/assets/ui'), 'assets/ui/', '*'),
                                   (Path('backend'), 'assets/', '*.py')):
        for source in root.glob(pattern):
            if source.is_file():
                assert archive.read(prefix + source.name) == source.read_bytes(), source
    assert 'assets/ui/theme-necromancer-bones.svg' not in archive.namelist()
    dex = b''.join(archive.read(n) for n in archive.namelist() if n.startswith('classes') and n.endswith('.dex'))
    for marker in (b'update_checklist.py', b'content_baseline.py', b'ClientCompatibilityReview', b"Don't warn again"):
        assert marker in dex, marker

bundle = Path('runtime-work/beta-070-sources/launcher-source')
bundle.mkdir(parents=True, exist_ok=True)
native = bundle / 'native-sources-0.6.42.tar.gz'
with urllib.request.urlopen('https://github.com/Russianranger/trasc-server-android/releases/download/v0.6.42/launcher-sources.tar.gz') as source, native.open('wb') as target:
    shutil.copyfileobj(source, target)
sha = lambda p: hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
assert sha(native) == '404d24a6c18be44b8efa15764ddc8bef82608cd307e7f6df3c6863a4d4827561'
with (bundle / 'launcher-code-0.7.0-beta.tar.gz').open('wb') as target:
    subprocess.run(['git', 'archive', '--format=tar.gz', head], stdout=target, check=True)
for source in ('dist/native-reuse.json', 'backend-assets/traditional-camera-bundle.json', 'THIRD_PARTY_NOTICES.md'):
    shutil.copyfile(source, bundle / Path(source).name)
source_archive = Path('dist/launcher-sources.tar.gz')
with tarfile.open(source_archive, 'w:gz') as archive:
    archive.add(bundle, arcname='launcher-source')
manifest = {'commit': head, 'sha256': sha(apk), 'file': apk.name, 'bytes': apk.stat().st_size,
            'version': '0.7.0-beta', 'version_code': 92, 'application_id': 'io.github.russianranger.trasc.preview',
            'signing_certificate_sha256': cert, 'build_run': int(os.environ['GITHUB_RUN_ID']),
            'native_payload_reused_from': '0.6.42', 'native_reuse_manifest_sha256': sha(Path('dist/native-reuse.json')),
            'source_archive_sha256': sha(source_archive), 'prerelease': True}
Path('dist/release-build.json').write_text(json.dumps(manifest, indent=2) + '\n')
files = (apk.name, source_archive.name, 'release-build.json', 'native-reuse.json', 'apk-signing.txt')
Path('dist/expected-assets.json').write_text(json.dumps({name: {'size': Path('dist', name).stat().st_size,
    'digest': 'sha256:' + sha(Path('dist', name))} for name in files}, indent=2) + '\n')
print(json.dumps(manifest, sort_keys=True))
