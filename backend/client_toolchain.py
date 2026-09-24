"""Fetch Microsoft's matched v142/x86 SDK after explicit, catalog-bound consent.

Only the open-source downloader is pinned/distributed. Microsoft payloads stay
in the user's private workspace and are verified against Microsoft's catalog.
The actual download/extract/pack runs in an Engine.run process group, allowing
cancellation to stop Python, msiextract and its children together.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import sys
import time
import urllib.parse
import urllib.request

# Reproducible, reviewed Microsoft VS2019 catalog. The mutable channel's size
# and hash disagree with the catalog bytes Microsoft actually serves, including
# on independent GitHub runners. Pin the reviewed official HTTPS bytes directly
# (as for the downloader), never silently trust changed catalog contents.
MANIFEST_VERSION = '16.11.60+37627.13'
MANIFEST_SHA256 = '406969c30f4eb8bf0075a0850e339340ac83942705b76269156bb5b70f01b631'
MANIFEST_BYTES = 11154648
MANIFEST_URL = ('https://download.visualstudio.microsoft.com/download/pr/'
                'e2324e87-3765-4b14-85e5-1234d99f6254/'
                'fb642c3f891b70947e0152275e1722ffb3cca7e8700eea0f0fa0f3a7645584cc/VisualStudio.vsman')
MIN_FREE = 8 * 1024**3
RESERVE = 512 * 1024**2
MAX_DOWNLOAD = 4 * 1024**3
PLAN_AGE = 24 * 3600
OPTIONS = ['--major', '16', '--msvc-version', '16.11', '--sdk-version', '10.0.19041',
           '--host-arch', 'x64', '--architecture', 'x86', '--with-default', 'no',
           '--with-msvc', 'yes', '--with-sdk', 'yes', '--with-asan', 'no',
           '--with-atl', 'no', '--skip-patch']


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def packer():
    path = Path(__file__).with_name('pack-client-sdk.py')
    if not path.is_file():  # Source checkout; APK bundles the same standalone helper.
        path = Path(__file__).resolve().parents[1] / 'tools/pack-client-sdk.py'
    return load_module(path, 'trasc_client_sdk_packer')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024**2), b''):
            digest.update(data)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.new-' + secrets.token_hex(4))
    try:
        temporary.write_text(json.dumps(value), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def microsoft_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not (host == 'aka.ms' or host == 'microsoft.com' or host.endswith('.microsoft.com'))):
        raise ValueError('Expected a secure Microsoft package or license URL')
    return url


class SecureRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        microsoft_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, target, maximum, expected_sha=None, expected_size=None,
          check=lambda: None, report=lambda count: None, downloader=False):
    """Bound responses even without Content-Length; promote only verified bytes."""
    if not downloader:
        microsoft_url(url)
    elif url != packer().DOWNLOADER_URL:
        raise ValueError('Unrecognized downloader URL')
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + '.part')
    digest = hashlib.sha256()
    count = 0
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'TRASC-Microsoft-SDK/1'})
        with urllib.request.build_opener(SecureRedirect()).open(request, timeout=30) as response, part.open('wb') as stream:
            if downloader:
                if response.url != url:
                    raise ValueError('Unexpected downloader redirect')
            else:
                microsoft_url(response.url)
            declared = int(response.headers.get('Content-Length', '0'))
            if declared > maximum or (expected_size is not None and declared not in (0, expected_size)):
                raise ValueError('Package response size does not match the catalog')
            while True:
                check()
                block = response.read(min(1024**2, maximum - count + 1))
                if not block:
                    break
                count += len(block)
                if count > maximum or (expected_size is not None and count > expected_size):
                    raise ValueError('Package response exceeds its download limit')
                if shutil.disk_usage(target.parent).free < len(block) + RESERVE:
                    raise ValueError('Not enough free storage to finish the toolchain download')
                stream.write(block)
                digest.update(block)
                report(count)
            if expected_size is not None and count != expected_size:
                raise ValueError('Incomplete package download')
            if expected_sha and digest.hexdigest() != expected_sha.lower():
                raise ValueError('Package checksum does not match the catalog')
        check()
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return count


def cache_path(engine):
    return engine.work / 'cache/client-toolchain'


def checked_downloader(cache, check=lambda: None):
    helper = packer()
    script = cache / 'vsdownload.py'
    if not script.is_file() or sha(script) != helper.DOWNLOADER_SHA256:
        fetch(helper.DOWNLOADER_URL, script, 2 * 1024**2,
              expected_sha=helper.DOWNLOADER_SHA256, check=check, downloader=True)
    return load_module(script, 'trasc_verified_vsdownload')


def selection(downloader, manifest, accepted=False):
    args = downloader.getArgsParser().parse_args(OPTIONS + (['--accept-license'] if accepted else []))
    # Upstream prioritizes localized payloads through its module-level CLI args.
    downloader.args = args
    packages = downloader.getPackages(manifest, 'x64')
    product = downloader.findPackage(packages, 'Microsoft.VisualStudio.Product.BuildTools')
    license_url = microsoft_url(product['localizedResources'][0]['license'])
    downloader.setPackageSelection(args, packages)
    downloader.lowercaseIgnores(args)
    selected = downloader.getSelectedPackages(packages, args)
    if not selected:
        raise ValueError('Microsoft catalog no longer supplies the required v142 toolchain')
    payloads = []
    names = set()
    for package in selected:
        key = downloader.getPackageKey(package)
        if not re.fullmatch(r'[A-Za-z0-9_.+-]+', key) or key in ('.', '..'):
            raise ValueError('Invalid catalog package name')
        for payload in package.get('payloads', []):
            name = downloader.getPayloadName(payload)
            if not name or name in ('.', '..') or '/' in name or '\\' in name:
                raise ValueError('Invalid catalog payload name')
            relative = key + '/' + name
            if relative in names:
                raise ValueError('Duplicate catalog payload destination')
            names.add(relative)
            checksum = str(payload.get('sha256', '')).lower()
            size = payload.get('size')
            if (not re.fullmatch(r'[0-9a-f]{64}', checksum)
                    or not isinstance(size, int) or isinstance(size, bool) or size < 1 or size > MAX_DOWNLOAD):
                raise ValueError('Catalog package is missing a valid SHA256 or bounded size')
            payloads.append({'path': relative, 'url': microsoft_url(payload['url']),
                             'sha256': checksum, 'size': size})
    if not payloads or sum(p['size'] for p in payloads) > MAX_DOWNLOAD:
        raise ValueError('Microsoft package selection exceeds the toolchain download limit')
    return args, selected, payloads, license_url


def plan_token(plan):
    content = {name: plan[name] for name in ('manifest_sha256', 'license_url', 'downloader_sha256', 'options')}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def load_plan(cache, token):
    plan = json.loads((cache / 'plan.json').read_text())
    if (not isinstance(token, str) or not re.fullmatch('[0-9a-f]{64}', token)
            or token != plan.get('token') or token != plan_token(plan)
            or plan.get('options') != OPTIONS or plan.get('downloader_sha256') != packer().DOWNLOADER_SHA256
            or time.time() - plan.get('prepared_at', 0) > PLAN_AGE
            or plan.get('manifest_sha256') != MANIFEST_SHA256
            or plan.get('manifest_version') != MANIFEST_VERSION
            or (cache / 'manifest.json').stat().st_size != MANIFEST_BYTES
            or sha(cache / 'manifest.json') != MANIFEST_SHA256):
        raise ValueError('Toolchain download details expired or changed. Review the Microsoft license again.')
    return plan


def download_info(engine, args=None):
    """Metadata only: fetch catalogs; do not accept terms, install or run tools."""
    cache = cache_path(engine)
    cache.mkdir(parents=True, exist_ok=True)
    # Reuse a short-lived, checksum-bound catalog so retrying uses identical terms.
    try:
        stored = json.loads((cache / 'plan.json').read_text())
        plan = load_plan(cache, stored.get('token'))
        checked_downloader(cache)
    except (OSError, ValueError, KeyError, TypeError):
        downloader = checked_downloader(cache)
        fetch(MANIFEST_URL, cache / 'manifest.json', MANIFEST_BYTES,
              expected_sha=MANIFEST_SHA256, expected_size=MANIFEST_BYTES)
        manifest = json.loads((cache / 'manifest.json').read_text())
        if manifest.get('info', {}).get('productSemanticVersion') != MANIFEST_VERSION:
            raise ValueError('Microsoft catalog version does not match the reviewed toolchain')
        with contextlib.redirect_stdout(io.StringIO()):
            _, selected, payloads, license_url = selection(downloader, manifest)
        plan = {'manifest_sha256': MANIFEST_SHA256, 'manifest_version': MANIFEST_VERSION,
                'downloader_sha256': packer().DOWNLOADER_SHA256,
                'options': OPTIONS, 'license_url': license_url,
                'license_name': 'Microsoft Visual Studio Build Tools 2019 license',
                'toolset': 'MSVC v142 / 14.29 (x64 host, x86 target)',
                'sdk': 'Windows SDK 10.0.19041',
                'download_bytes': sum(p['size'] for p in payloads),
                'installed_bytes': downloader.sumInstalledSize(selected),
                'required_free_bytes': MIN_FREE, 'prepared_at': time.time()}
        plan['token'] = plan_token(plan)
        atomic_json(cache / 'plan.json', plan)
    return dict(plan, free_bytes=shutil.disk_usage(engine.work).free,
                needs_msitools=shutil.which('msiextract') is None,
                message='Downloads Microsoft packages directly to this device after you accept the linked license. '
                        'Keep 8 GiB free; verified downloads are reused if you retry. '
                        'The existing compiler is replaced only after the complete package validates.')


def write_progress(cache, phase, message, downloaded_bytes=0, total_bytes=0):
    atomic_json(cache / 'progress.json', {'phase': phase, 'message': message,
                'downloaded_bytes': downloaded_bytes, 'total_bytes': total_bytes})
    print(message, flush=True)


def progress(engine):
    try:
        return json.loads((cache_path(engine) / 'progress.json').read_text())
    except (OSError, ValueError):
        return None


def prepare_msiextract(engine, stage):
    """Download authenticated Debian dependencies; never run dpkg installation.

    Extract privately: Android denies hard links used by dpkg upgrades, and
    cancelling an install must not leave the server runtime half configured.
    """
    if shutil.which('msiextract'):
        return None
    archives = stage / 'debs'
    archives.mkdir()
    (archives / 'partial').mkdir()
    lists = stage / 'apt-lists'
    (lists / 'partial').mkdir(parents=True)
    options = ['-o', 'Acquire::Retries=2', '-o', 'Acquire::http::Timeout=30',
               '-o', 'Acquire::https::Timeout=30', '-o', 'APT::Sandbox::User=root',
               '-o', 'Dir::State::lists=' + str(lists)]
    engine.run(['apt-get', *options, 'update'], timeout=600)
    engine.run(['apt-get', *options, '-o', 'Dir::Cache::archives=' + str(archives),
                '--download-only', '--no-install-recommends', '-y', 'install', 'msitools'], timeout=900)
    tools = stage / 'msitools'
    tools.mkdir()
    packages = sorted(archives.glob('*.deb'))
    if not packages:
        raise ValueError('The runtime package repository did not supply msitools')
    for package in packages:
        engine.run(['dpkg-deb', '-x', package, tools], timeout=120)
    binary = tools / 'usr/bin/msiextract'
    if not binary.is_file():
        raise ValueError('Downloaded msitools did not contain msiextract')
    wrappers = stage / 'bin'
    wrappers.mkdir()
    libs = [str(p) for base in ('usr/lib', 'lib')
            for p in (tools / base).glob('*-linux-gnu') if p.is_dir()]
    libs += [str(tools / 'usr/lib'), str(tools / 'lib')]
    # Paths are shell-quoted; this changes only msiextract's private environment.
    wrapper = wrappers / 'msiextract'
    wrapper.write_text('#!/bin/sh\nexec env LD_LIBRARY_PATH=' + shlex.quote(':'.join(libs))
                       + ' ' + shlex.quote(str(binary)) + ' "$@"\n')
    wrapper.chmod(0o755)
    engine.run([wrapper, '--version'], timeout=30)
    return wrappers


def download(engine, args):
    import client_dll
    if args.get('accepted') is not True:
        raise ValueError('Review and explicitly accept the Microsoft license before downloading')
    if engine.server_running():
        raise ValueError('Stop the server before downloading the Microsoft toolchain')
    cache = cache_path(engine)
    try:
        plan = load_plan(cache, args.get('token'))
    except (OSError, KeyError, TypeError) as error:
        raise ValueError('Prepare the toolchain download and review its Microsoft license first') from error
    if shutil.disk_usage(engine.work).free < MIN_FREE:
        raise ValueError('At least 8 GiB of free internal storage is required for toolchain preparation')
    engine.check_cancel()
    # A process death can leave only disposable preparation trees, never an
    # installed compiler. Clear those before retrying to reclaim their space.
    for abandoned in cache.glob('prepare-*'):
        if abandoned.is_dir() and not abandoned.is_symlink():
            shutil.rmtree(abandoned)
    stage = cache / ('prepare-' + secrets.token_hex(6))
    stage.mkdir()
    prepared_archive = stage / 'toolchain.zip'
    archive = engine.work / 'incoming' / ('microsoft-sdk-' + secrets.token_hex(6) + '.zip')
    try:
        write_progress(cache, 'dependencies', 'Preparing the Microsoft package extractor', total_bytes=plan['download_bytes'])
        engine.log('Microsoft license explicitly accepted for toolchain plan ' + plan['token'] + ': ' + plan['license_url'])
        wrappers = prepare_msiextract(engine, stage)
        command = [sys.executable, '-u', Path(__file__).resolve(), '--download-worker',
                   '--cache', cache, '--stage', stage, '--output', prepared_archive,
                   '--accepted-token', args['token']]
        if wrappers:
            command += ['--extractor-path', wrappers]
        engine.run(command, timeout=7200)
        engine.check_cancel()
        if not prepared_archive.is_file():
            raise ValueError('Toolchain preparation completed without a validated SDK ZIP')
        prepared_archive.rename(archive)
        write_progress(cache, 'importing', 'Importing the verified Microsoft toolchain', plan['download_bytes'], plan['download_bytes'])
        result = client_dll.import_sdk(engine, {'file': archive.name})
        write_progress(cache, 'complete', 'Microsoft toolchain downloaded and imported', plan['download_bytes'], plan['download_bytes'])
        return dict(result, message='Microsoft v142 toolchain downloaded and imported. You can now compile dinput8.dll.',
                    license_url=plan['license_url'])
    except BaseException:
        write_progress(cache, 'stopped', 'Toolchain preparation stopped. Verified downloads are retained for retry.')
        raise
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(stage, ignore_errors=True)


def run_worker(cache, stage, output, accepted_token, extractor_path=None):
    plan = load_plan(cache, accepted_token)
    downloader = checked_downloader(cache)
    manifest = json.loads((cache / 'manifest.json').read_text())
    # This flag reaches the actual pinned downloader parser only after the UI
    # acceptance token has been validated by both the parent and this worker.
    options, selected, payloads, license_url = selection(downloader, manifest, accepted=True)
    if not options.accept_license or license_url != plan['license_url']:
        raise ValueError('Microsoft license changed; review the download again')
    if extractor_path:
        os.environ['PATH'] = str(extractor_path) + os.pathsep + os.environ.get('PATH', '')
    if not shutil.which('msiextract'):
        raise ValueError('Microsoft package extractor is unavailable')
    total = sum(p['size'] for p in payloads)
    complete = 0
    for index, payload in enumerate(payloads):
        target = cache / 'downloads' / payload['path']
        prefix = 'Microsoft package ' + str(index + 1) + '/' + str(len(payloads))
        # Microsoft's catalog sizes are estimates and differ even for bytes
        # matching its exact SHA256 (e.g. a 1071-byte entry serves 8703 bytes).
        # Keep strict hashes, per-file bounds and a cumulative real-byte bound;
        # never infer integrity from the estimate or HTTP Content-Length alone.
        ceiling = min(MAX_DOWNLOAD, max(payload['size'] * 2, payload['size'] + 1024**2))
        maximum = min(MAX_DOWNLOAD - complete, ceiling)
        if target.is_file() and target.stat().st_size <= ceiling and sha(target) == payload['sha256']:
            if target.stat().st_size > maximum:
                raise ValueError('Total Microsoft package download exceeds its byte limit')
            complete += target.stat().st_size
            write_progress(cache, 'downloading', prefix + ': using verified download', complete, total)
            continue
        target.unlink(missing_ok=True)
        for attempt in range(3):
            try:
                write_progress(cache, 'downloading', prefix + ': downloading', complete, total)
                last = [0]
                def report(count):
                    if count - last[0] >= 16 * 1024**2:
                        last[0] = count
                        write_progress(cache, 'downloading', prefix + ': downloading', complete + count, total)
                fetch(payload['url'], target, maximum, expected_sha=payload['sha256'], report=report)
                break
            except (OSError, ValueError) as error:
                if attempt == 2:
                    raise
                print(prefix + ': retrying after ' + str(error), flush=True)
        complete += target.stat().st_size
    total = complete
    write_progress(cache, 'extracting', 'Extracting verified Microsoft packages', total, total)
    root = stage / 'microsoft-v142'
    downloader.extractPackages(selected, str(cache / 'downloads'), str(root))
    write_progress(cache, 'packaging', 'Validating and packaging the matched v142 / Windows SDK toolchain', total, total)
    packer().package(root, output)
    if not output.is_file():
        raise ValueError('Microsoft SDK package was not created')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-worker', action='store_true', required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--accepted-token', required=True)
    parser.add_argument('--extractor-path', type=Path)
    args = parser.parse_args()
    socket.setdefaulttimeout(30)
    try:
        run_worker(args.cache, args.stage, args.output, args.accepted_token, args.extractor_path)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, 'Microsoft toolchain preparation failed: ' + str(error) + '\n')
