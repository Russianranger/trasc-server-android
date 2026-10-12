"""Real compiler and legacy-deployment qualification for source updates.

The small native CMake fixture tests the common update transaction for every
profile. Its source qualification pins are deliberately fixture-specific; it
does not claim to compile an EQ server. The separate bootstrap command uses
the exact released 0.6.23 backend and complete 25bf70a TAKP source, including
the production native build, database, deployment and server startup.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest import mock
import zipfile

LEGACY_APP_COMMIT = 'cf6bec71d6f3171de27851d7df625cf84da096f8'
LEGACY_SERVER_COMMIT = '25bf70acb6bd24853cf09e447ddd62b96a4491a4'
LATEST_SERVER_COMMIT = '03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167'
FIXTURE_USER = 'takpfixture'
FIXTURE_PASSWORD = 'takp-fixture-pass'


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive_tree(source, target, selected=None):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        files = sorted(source.rglob('*')) if selected is None else selected
        for path in files:
            relative = path.relative_to(source)
            if path.is_file() and not path.is_symlink() and '.git' not in relative.parts:
                archive.write(path, Path('fixture') / relative)
    return target.name


def stamps(root, suffix=None):
    """Actual file identities; compiling an unchanged file must alter a stamp."""
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if (path.is_file() and not path.is_symlink() and '.git' not in path.relative_to(root).parts
                and name != 'trasc-source.json' and (suffix is None or name.endswith(suffix))):
            info = path.stat()
            result[name] = [info.st_ino, info.st_mtime_ns, info.st_size]
    return result


def tree_hashes(root):
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(Path(root).rglob('*')) if path.is_file() and not path.is_symlink()}


@contextlib.contextmanager
def immutable_archives(engine, sources, repository):
    """Resolve public pinned fixtures in the intentionally offline container.

    Only immutable qualified revisions can be resolved. The real importer and
    updater still parse, inventory and qualify every byte of these ZIPs.
    """
    original = engine.github_download
    def download(url, ref, target):
        if url.rstrip('/') != repository.rstrip('/') or ref not in sources:
            raise RuntimeError('Native fixture attempted an unpinned source download: ' + str(ref))
        archive_tree(sources[ref], target)
        return {'repo': repository, 'ref': ref, 'commit': ref}
    engine.github_download = download
    try:
        yield
    finally:
        engine.github_download = original


def bootstrap_legacy(args):
    """Child process: imports only the exact old app backend, never new modules."""
    sys.path.insert(0, str(args.baseline_app))
    from engine import Engine, atomic_json
    import takp_build
    import takp_runtime
    if takp_build.REVISION != LEGACY_SERVER_COMMIT:
        raise RuntimeError('Baseline app backend does not pin the released legacy TAKP revision')
    if (args.work / 'sources/current').exists():
        raise RuntimeError('Legacy native bootstrap requires a fresh isolated workspace')
    engine = Engine(args.work, 'takp')
    started = time.monotonic()
    try:
        with immutable_archives(engine, {LEGACY_SERVER_COMMIT: args.baseline_source}, takp_build.REPOSITORY):
            engine.import_source({'url': takp_build.REPOSITORY, 'ref': LEGACY_SERVER_COMMIT})
        for kind, source in (('quests', args.quests), ('maps', args.maps)):
            selected = None
            if kind == 'maps':
                selected = [path for path in source.iterdir()
                            if path.name.startswith(('qeynos.', 'paineel.', 'README', 'LICENSE'))]
            name = archive_tree(source, engine.work / ('incoming/' + kind + '.zip'), selected)
            engine.dispatch('import_content', {'kind': kind, 'file': name})
        engine.sync_content({})
        engine.build({'jobs': args.jobs})
        engine.dispatch('takp_initialize_database', {})
        engine.dispatch('takp_create_account', {'username': FIXTURE_USER, 'password': FIXTURE_PASSWORD})
        engine.config['workers'] = 1
        engine.save()
        engine.deploy({})
        state = engine.state()
        if not state['takp']['deployment']['start_allowed'] or not state['binaries_ready']:
            raise RuntimeError('Released legacy build was not ready before app upgrade')
        engine.start({})
        # start() itself waits for the real world listener and starts the legacy
        # login, world, chat, query and launcher processes.
        if not engine.server_running():
            raise RuntimeError('Released legacy TAKP server failed to start')
        stopped = engine.stop({})
        if not stopped['clean_shutdown']:
            raise RuntimeError('Released legacy TAKP server did not stop cleanly')
        build_dir = engine.work / ('builds/takp-' + LEGACY_SERVER_COMMIT[:12])
        objects = stamps(build_dir, '.o')
        if not objects or not any(name.endswith('player_bot.cpp.o') for name in objects):
            raise RuntimeError('Native legacy build did not produce real bot object files')
        receipt = {'format': 1, 'baseline_app_commit': LEGACY_APP_COMMIT,
                   'source_commit': LEGACY_SERVER_COMMIT,
                   'recipe_sha256': sha256(args.baseline_app / 'takp_build.py'),
                   'source_tree_sha256': takp_build.SOURCE_TREE_SHA256,
                   'build_directory': str(build_dir.relative_to(engine.work)),
                   'source_stamps': stamps(engine.source_root()), 'object_stamps': objects,
                   'deployed_hashes': tree_hashes(engine.work / 'server/bin'),
                   'cmake_cache_sha256': sha256(build_dir / 'CMakeCache.txt'),
                   'ninja_log_sha256': sha256(build_dir / '.ninja_log'),
                   'elapsed_seconds': round(time.monotonic() - started, 3),
                   'checks': {'production_legacy_build': True,
                              'seed_content_account_and_real_deployment': True,
                              'legacy_server_started_and_stopped': True}, 'result': 'passed'}
        atomic_json(args.output, receipt)
        print(json.dumps({key: value for key, value in receipt.items()
                          if key not in ('source_stamps', 'object_stamps', 'deployed_hashes')}, indent=2), flush=True)
    finally:
        engine.shutdown()


def qualify_tiny(args):
    sys.path.insert(0, '/opt/trasc')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    from engine import Engine, atomic_json
    import source_updates
    import takp_build
    import traditional_build
    args.work.mkdir(parents=True, exist_ok=True)
    reports = {}
    for profile in ('custom', 'traditional', 'takp'):
        fixture = args.work / (profile + '-fixture')
        original, changed = fixture / 'original', fixture / 'changed'
        for root in (original, changed):
            (root / 'zone').mkdir(parents=True)
            for dependency in ('libs/luabind', 'submodules/fmt', 'submodules/libuv'):
                (root / dependency).mkdir(parents=True)
                (root / dependency / 'CMakeLists.txt').write_text('# vendored fixture\n')
            (root / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(update_fixture CXX)\n'
                'add_library(stable STATIC stable.cpp)\nadd_executable(zone zone/player_bot.cpp)\n'
                'target_link_libraries(zone PRIVATE stable)\n')
            (root / 'stable.cpp').write_text('int stable_answer() { return 41; }\n')
        (original / 'zone/player_bot.cpp').write_text('extern int stable_answer(); int main() { return stable_answer() == 41 ? 0 : 1; }\n')
        (changed / 'zone/player_bot.cpp').write_text('extern int stable_answer(); int main() { return stable_answer() + 1 == 42 ? 0 : 1; }\n')
        engine = Engine(fixture / 'work', profile)
        qualification = {'commit': 'f' * 40, 'tree_sha256': 'f' * 64,
                         'files': 6, 'bytes': 1, 'bundled_dependencies': True}
        pins = {'CMakeLists.txt': sha256(changed / 'CMakeLists.txt')}
        try:
            with mock.patch.object(takp_build, 'qualify_source', return_value=qualification), \
                    mock.patch.dict(traditional_build.SOURCE_HASHES, pins, clear=True):
                name = archive_tree(original, engine.work / 'incoming/original.zip')
                engine.import_source({'file': name})
                source = engine.source_root()
                build = engine.work / 'builds/fixture'
                options = ('-DCMAKE_BUILD_TYPE=Release',)
                actual_compiler = subprocess.check_output(['g++', '--version'], text=True)
                actual_cmake = subprocess.check_output(['cmake', '--version'], text=True)
                runtime = hashlib.sha256((actual_compiler + actual_cmake).encode()).hexdigest()
                cache = source_updates.cache_identity(profile, runtime, 'native-cmake-fixture-v1', source, options)
                source_updates.ensure_cache(engine, build, cache, source, options)
                subprocess.run(['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja', *options], check=True)
                subprocess.run(['cmake', '--build', str(build)], check=True)
                subprocess.run([str(build / 'zone')], check=True)
                inputs = stamps(source)
                objects = stamps(build, '.o')
                name = archive_tree(changed, engine.work / 'incoming/changed.zip')
                reviewed = engine.source_update_preview({'file': name})
                if reviewed['counts'] != {'added': 0, 'deleted': 0, 'changed': 1} or not reviewed['apply_allowed']:
                    raise RuntimeError(profile + ' native fixture did not review its exact one-file change')
                engine.source_update_apply({'token': reviewed['token']})
                updated = stamps(source)
                unchanged = set(inputs) - {'zone/player_bot.cpp'}
                if any(inputs[name] != updated[name] for name in unchanged):
                    raise RuntimeError(profile + ' update touched an unchanged compiler input')
                source_updates.ensure_cache(engine, build, cache, source, options, incremental=True)
                result = subprocess.run(['cmake', '--build', str(build)], check=True, text=True, capture_output=True)
                print(result.stdout, end='')
                rebuilt = stamps(build, '.o')
                changed_objects = sorted(name for name in objects if objects[name] != rebuilt[name])
                if changed_objects != ['CMakeFiles/zone.dir/zone/player_bot.cpp.o']:
                    raise RuntimeError(profile + ' incremental fixture rebuilt unrelated objects: ' + str(changed_objects))
                subprocess.run([str(build / 'zone')], check=True)
                noop = subprocess.run(['cmake', '--build', str(build)], check=True, text=True, capture_output=True)
                if 'no work to do' not in noop.stdout or stamps(build, '.o') != rebuilt:
                    raise RuntimeError(profile + ' no-op native build performed compiler work')
                # A real compiler failure must leave the deployed fixture and
                # the previous successfully built executable usable.
                deployed = engine.work / 'server/bin/fixture-zone'
                deployed.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(build / 'zone', deployed)
                before_failure = sha256(deployed)
                (source / 'zone/player_bot.cpp').write_text('this is deliberately invalid C++\n')
                failure = subprocess.run(['cmake', '--build', str(build)], text=True, capture_output=True)
                if failure.returncode == 0 or sha256(deployed) != before_failure:
                    raise RuntimeError(profile + ' failed compile altered deployed binaries')
                subprocess.run([str(deployed)], check=True)
                reports[profile] = {'changed_source_files': 1, 'unchanged_source_stamps': len(unchanged),
                    'changed_object_files': changed_objects, 'no_op_ninja': noop.stdout.strip(),
                    'production_cache_receipt_verified_after_source_change': True,
                    'actual_invalid_cpp_compile_failed': True, 'deployed_executable_preserved_and_runs': True}
        finally:
            engine.shutdown()
    report = {'format': 1, 'kind': 'bounded_native_cmake_fixture', 'profiles': reports, 'result': 'passed',
              'scope': 'Real C++ compiler/Ninja and common updater; fixture-specific source pins, not full server builds'}
    atomic_json(args.output, report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap-legacy', action='store_true')
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-app', type=Path)
    parser.add_argument('--baseline-source', type=Path)
    parser.add_argument('--quests', type=Path)
    parser.add_argument('--maps', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    arguments = parser.parse_args()
    if arguments.bootstrap_legacy:
        if not all((arguments.baseline_app, arguments.baseline_source, arguments.quests, arguments.maps)):
            parser.error('Legacy bootstrap requires baseline app/source, quests and maps')
        bootstrap_legacy(arguments)
    else:
        qualify_tiny(arguments)
