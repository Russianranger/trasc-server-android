"""Pinned EQMacEmu build in TAKP's independent Bookworm ARM64 workspace.

The server fork vendors its dependencies as ordinary files. Source archives
must contain that complete, qualified tree; no host binaries are downloaded.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time

import traditional_build
import traditional_verify

REPOSITORY = 'https://github.com/Russianranger/Servertakp'
REVISION = '03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167'
SOURCE_TREE_SHA256 = '3bcfc1f604909594a33ebfa8217d71f7fade167f4d439492fbe75e8ce0f44cf5'
SOURCE_FILES = 5552
SOURCE_BYTES = 147902744
SEED_SHA256 = '6f5a61206b22d3d70c20ece7fb8c617bbe0849d286b2cb48279841f4c6103433'
RECIPE = 'eqmac-bookworm-arm64-luajit-v1'
BINARIES = ('world', 'zone', 'loginserver', 'shared_memory', 'ucs', 'eqlaunch',
            'queryserv', 'export_client_files', 'import_client_files')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def qualify_source(root, check=lambda: None):
    """Qualify GitHub and offline ZIP imports by content, including all libs."""
    root = Path(root)
    files = []
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if '.git' in relative.parts or relative.as_posix() == 'trasc-source.json':
            continue
        if path.is_symlink():
            raise ValueError('TAKP source must contain ordinary files, including its bundled dependencies')
        if path.is_file():
            files.append((relative.as_posix(), path))
    if len(files) != SOURCE_FILES:
        raise ValueError('Use the complete TAKP server ZIP at revision ' + REVISION[:7]
                         + '; its bundled dependencies and database must be included')
    tree = hashlib.sha256()
    total = 0
    for name, path in sorted(files):
        check()
        total += path.stat().st_size
        tree.update(name.encode() + b'\0' + bytes.fromhex(digest(path)))
    if total != SOURCE_BYTES or tree.hexdigest() != SOURCE_TREE_SHA256:
        raise ValueError('TAKP source does not match the qualified server revision ' + REVISION[:7])
    return {'commit': REVISION, 'tree_sha256': SOURCE_TREE_SHA256,
            'files': len(files), 'bytes': total, 'bundled_dependencies': True}


def runtime(engine):
    # Java qualifies the downloaded Traditional dependency image and writes a
    # TAKP marker only inside the separately installed profiles/takp rootfs.
    marker_path = traditional_build.RUNTIME_MARKER
    try:
        marker = marker_path.read_bytes()
        tracked = ('/usr/bin/g++', '/usr/bin/cmake', '/usr/bin/openssl', '/var/lib/dpkg/status',
                   '/usr/include/boost/version.hpp', '/usr/include/luajit-2.1/lua.h',
                   '/usr/include/mariadb/mysql.h', '/usr/include/openssl/evp.h',
                   '/usr/include/sodium.h', '/usr/include/zlib.h',
                   '/usr/lib/aarch64-linux-gnu/libluajit-5.1.so.2',
                   '/usr/lib/aarch64-linux-gnu/libcrypto.so.3',
                   '/usr/lib/aarch64-linux-gnu/ossl-modules/legacy.so')
        stamps = []
        for path in tracked:
            try:
                value = Path(path).stat()
                stamps.append((path, value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns))
            except FileNotFoundError:
                stamps.append((path, None))
        signature = hashlib.sha256(marker + json.dumps(stamps).encode()).hexdigest()
        cached = getattr(engine, '_takp_runtime_cache', None)
        if cached and cached[0] == signature:
            return cached[1]
        value = json.loads(marker)
        if (value.get('format') != 1 or value.get('architecture') != 'arm64'
                or value.get('distribution') != 'debian-bookworm' or value.get('profile') != 'takp'
                or value.get('runtime') != 'takp-1.0' or value.get('build_adapter') != 1
                or value.get('source_profile') != 'traditional' or value.get('source_runtime') != 'traditional-1.0'):
            raise ValueError('Install the TAKP build runtime before compiling its server')
        tool = traditional_build._tool
        if tool(['/usr/bin/uname', '-m']) != 'aarch64' or 'aarch64' not in tool(['/usr/bin/g++', '-dumpmachine']):
            raise ValueError('TAKP compilation requires its app-owned ARM64 runtime')
        compiler = tool(['/usr/bin/g++', '-dumpfullversion'])
        cmake = tool(['/usr/bin/cmake', '--version']).splitlines()[0]
        if not re.match(r'^12\.', compiler) or not cmake.startswith('cmake version 3.25.'):
            raise ValueError('TAKP requires the packaged Bookworm GCC 12 and CMake 3.25 toolchain')
        for name in ('boost/version.hpp', 'luajit-2.1/lua.h', 'mariadb/mysql.h', 'openssl/evp.h', 'sodium.h', 'zlib.h'):
            if not Path('/usr/include', name).is_file():
                raise ValueError('TAKP build runtime is missing ' + name)
        packages = tool(['/usr/bin/dpkg-query', '-W', '-f=${Package}=${Version}\n',
                        'g++', 'cmake', 'ninja-build', 'libboost-dev', 'libluajit-5.1-dev',
                        'libmariadb-dev', 'libssl-dev', 'libsodium-dev', 'zlib1g-dev'])
        providers = tool(['/usr/bin/openssl', 'list', '-providers', '-provider', 'default', '-provider', 'legacy'])
        if not {'default', 'legacy'} <= traditional_verify._active_providers(providers):
            raise ValueError('TAKP client login needs OpenSSL default and legacy providers')
        identity = hashlib.sha256(marker + compiler.encode() + cmake.encode() + packages.encode()).hexdigest()
        result = {'ready': True, 'identity': identity, 'message': 'TAKP ARM64 Bookworm build runtime is qualified'}
        engine._takp_runtime_cache = (signature, result)
        return result
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        return {'ready': False, 'identity': None, 'message': str(error)}


def _json(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing TAKP build manifest')
    return json.loads(path.read_text())


def _path(engine, relative):
    path = engine.work / relative
    for ancestor in (path, *path.parents):
        if ancestor == engine.work.parent:
            break
        if ancestor.is_symlink():
            raise ValueError('TAKP managed server paths cannot be symbolic links')
    return path


def record(engine, directory='server/bin.staged'):
    root = _path(engine, directory)
    info = _json(root / 'build-info.json')
    current_runtime = runtime(engine)
    if (info.get('format') != 1 or info.get('profile') != 'takp'
            or info.get('recipe') != RECIPE or info.get('source_tree_sha256') != SOURCE_TREE_SHA256
            or info.get('recipe_sha256') != digest(__file__)
            or not current_runtime['ready'] or info.get('runtime_identity') != current_runtime['identity']
            or set(info.get('binaries', {})) != set(BINARIES)):
        raise ValueError('TAKP binaries do not match the qualified source, recipe and runtime')
    signature = tuple((name, (root / name).stat().st_size, (root / name).stat().st_mtime_ns,
                       (root / name).stat().st_ctime_ns) for name in BINARIES)
    cache = getattr(engine, '_takp_binary_cache', {})
    key = (directory, hashlib.sha256(json.dumps(info, sort_keys=True).encode()).hexdigest(), signature)
    if cache.get(directory) != key:
        for name in BINARIES:
            path = root / name
            traditional_verify.inspect_elf(path)
            if digest(path) != info['binaries'][name]:
                raise ValueError('TAKP binary has changed: ' + name)
        cache[directory] = key
        engine._takp_binary_cache = cache
    return info


def status(engine):
    environment = runtime(engine)
    staged = deployed = previous = False
    for directory in ('server/bin.staged', 'server/bin', 'server/bin.previous'):
        try:
            record(engine, directory)
            if directory.endswith('.staged'):
                staged = True
            elif directory.endswith('.previous'):
                previous = True
            else:
                deployed = True
        except (OSError, ValueError, KeyError, TypeError):
            pass
    source = engine.work / 'sources/current/trasc-source.json'
    try:
        qualified = _json(source).get('takp', {}).get('tree_sha256') == SOURCE_TREE_SHA256
    except (OSError, ValueError, TypeError):
        qualified = False
    return {'runtime_ready': environment['ready'], 'runtime_message': environment['message'],
            'source_ready': qualified, 'build_allowed': bool(environment['ready'] and qualified and not engine.server_running()),
            'staged_valid': staged, 'deployed_valid': deployed, 'previous_valid': previous,
            'recipe': RECIPE, 'revision': REVISION}


def build(engine, args):
    from engine import atomic_json
    if engine.server_running():
        raise ValueError('Stop the TAKP server before compiling')
    environment = runtime(engine)
    if not environment['ready']:
        raise ValueError(environment['message'])
    source = engine.source_root()
    provenance = qualify_source(source, engine.check_cancel)
    jobs = int(args.get('jobs', engine.config['jobs']))
    if not 1 <= jobs <= 4:
        raise ValueError('Choose 1–4 build jobs for this device')
    if shutil.disk_usage(engine.work).free < 3 * 1024**3:
        raise ValueError('Free at least 3 GiB before compiling the TAKP server')
    build_dir = _path(engine, 'builds/takp-' + REVISION[:12])
    build_dir.mkdir(parents=True, exist_ok=True)
    engine.config['jobs'] = jobs
    engine.save()
    engine.run(['cmake', '-S', source, '-B', build_dir, '-G', 'Ninja',
                '-DCMAKE_BUILD_TYPE=Release', '-DEQEMU_BUILD_SERVER=ON',
                '-DEQEMU_BUILD_LOGIN=ON', '-DEQEMU_BUILD_CLIENT_FILES=ON',
                '-DEQEMU_BUILD_TESTS=OFF', '-DEQEMU_BUILD_LUA=ON',
                '-DEQEMU_PREFER_LUA=OFF', '-DEQEMU_SFMT19937=OFF'], timeout=900)
    engine.run(['cmake', '--build', build_dir, '--parallel', str(jobs),
                '--target', *BINARIES], timeout=24 * 3600)
    prepared = _path(engine, 'server/bin.preparing-' + secrets.token_hex(6))
    prepared.mkdir()
    try:
        hashes = {}
        for name in BINARIES:
            engine.check_cancel()
            source_binary = build_dir / 'bin' / name
            traditional_verify.inspect_elf(source_binary)
            target = prepared / name
            shutil.copy2(source_binary, target)
            target.chmod(0o755)
            dependencies = traditional_verify._command(['ldd', str(target)])
            if 'not found' in dependencies:
                raise ValueError('TAKP binary has unresolved dependencies: ' + name)
            if name == 'zone' and not re.search(r'libluajit-5\.1\.so\.2\s+=>', dependencies):
                raise ValueError('TAKP zone must include the runtime LuaJIT quest parser')
            (build_dir / (name + '.ldd.txt')).write_text(dependencies)
            dynamic = traditional_verify._command(['readelf', '--wide', '-d', str(target)])
            if any(('(RPATH)' in line or '(RUNPATH)' in line) and
                   any(prefix in line for prefix in ('/work/builds', '/work/sources', str(build_dir)))
                   for line in dynamic.splitlines()):
                raise ValueError('TAKP binary depends on a build directory: ' + name)
            hashes[name] = digest(target)
        qualify_source(source, engine.check_cancel)
        atomic_json(prepared / 'build-info.json', {'format': 1, 'profile': 'takp', 'recipe': RECIPE,
                    'recipe_sha256': digest(__file__), 'source': provenance,
                    'source_tree_sha256': SOURCE_TREE_SHA256, 'runtime_identity': environment['identity'],
                    'built': time.time(), 'binaries': hashes})
        stage = _path(engine, 'server/bin.staged')
        old = _path(engine, 'server/bin.staged.old')
        if old.exists():
            shutil.rmtree(old)
        if stage.exists():
            os.replace(stage, old)
        try:
            os.replace(prepared, stage)
        except BaseException:
            if old.exists() and not stage.exists():
                os.replace(old, stage)
            raise
        if old.exists():
            shutil.rmtree(old)
    finally:
        if prepared.exists():
            shutil.rmtree(prepared)
    return {'staged': True, 'source': provenance,
            'message': 'TAKP ARM64 build passed. Initialize the TAKP database, then deploy the build.'}
