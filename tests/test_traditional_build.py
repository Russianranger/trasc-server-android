"""Filesystem and failure tests for the Traditional compile-only adapter.

The fixture deliberately substitutes tiny guarded inputs. Native CI qualifies
the real pinned source; these tests exercise the import, cache and staging
boundaries without a compiler, network connection or running server.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import traditional_build as build
import traditional_verify as verify

REAL_RUNTIME = build._runtime
REAL_FETCH = build._fetch_websocket


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def arm_elf(path):
    """A small ELF header fixture, never executed by the fake compiler."""
    interpreter = b'/lib/ld-linux-aarch64.so.1\0'
    ident = b'\x7fELF\x02\x01\x01' + bytes(9)
    header = struct.pack('<16sHHIQQQIHHHHHH', ident, 3, 183, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    program = struct.pack('<IIQQQQQQ', 3, 0, 120, 0, 0, len(interpreter), len(interpreter), 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + program + interpreter)
    path.chmod(0o755)


def tar_bytes(files, extra=None):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as archive:
        for name, value in files.items():
            value = value.encode() if isinstance(value, str) else value
            entry = tarfile.TarInfo(name)
            entry.size = len(value)
            archive.addfile(entry, io.BytesIO(value))
        if extra is not None:
            archive.addfile(extra)
    return data.getvalue()


class FakeEngine:
    def __init__(self, work):
        self.work = Path(work)
        self.profile = 'traditional'
        self.config = {'profile': 'traditional', 'database_imported': False, 'jobs': 1}
        self.cancel = threading.Event()
        self.messages = []
        self.commands = []
        self.downloads = []
        self.process_lock = threading.RLock()
        self.jobs = []
        self.processes = {}
        self.current_job = None
        self.traditional_recovery_error = ''
        self.fail_configure = False
        self.fail_compile = False
        self.omit = set()
        self.wrong_architecture = False
        self.bad_helper_hash = False
        self.on_compile = None
        self.on_verify = None
        self.compiles = 0
        for name in ('sources', 'server', 'builds', 'run', 'logs', 'incoming'):
            (self.work / name).mkdir(parents=True, exist_ok=True)

    def check_cancel(self):
        if self.cancel.is_set():
            raise ValueError('Operation cancelled')

    def log(self, message):
        self.messages.append(str(message))

    def server_running(self):
        return False

    def source_root(self):
        return self.work / 'sources/current'

    def save(self):
        write_json(self.work / 'settings.json', self.config)

    def download(self, url, target):
        self.check_cancel()
        self.downloads.append(url)
        Path(target).write_bytes(self.archive)
        return Path(target)

    def run(self, args, **kwargs):
        self.check_cancel()
        args = [str(item) for item in args]
        self.commands.append(args)
        is_cmake = any(Path(item).name == 'cmake' for item in args)
        if is_cmake and '--build' in args:
            if self.fail_compile:
                raise ValueError('Simulated compile failure')
            objects = Path(args[args.index('--build') + 1])
            self.compiles += 1
            for name in build.BINARIES:
                if name in self.omit:
                    (objects / 'bin' / name).unlink(missing_ok=True)
                    continue
                path = objects / 'bin' / name
                arm_elf(path)
                with path.open('ab') as out:
                    out.write(('compiler output %d' % self.compiles).encode())
                if self.wrong_architecture and name == 'world':
                    data = bytearray(path.read_bytes())
                    data[18:20] = struct.pack('<H', 62)
                    path.write_bytes(data)
            if self.on_compile:
                self.on_compile()
        elif is_cmake:
            if self.fail_configure:
                raise ValueError('Simulated configure failure')
            objects = Path(args[args.index('-B') + 1])
            objects.mkdir(parents=True, exist_ok=True)
            (objects / 'CMakeCache.txt').write_text('fixture CMake cache\n')
        elif any(Path(item).name == 'traditional_verify.py' for item in args):
            stage, evidence = Path(args[-2]), Path(args[-1])
            with patch.object(verify, '_command', side_effect=loader_command):
                report = verify.verify(stage, evidence)
            if self.bad_helper_hash:
                report['binaries']['world']['sha256'] = 'f' * 64
                write_json(evidence / 'binary-verification.json', report)
            if self.on_verify:
                self.on_verify()
        else:
            raise AssertionError('Unexpected command: %r' % args)
        self.check_cancel()


def loader_command(args):
    if args[0] == 'ldd':
        return ('libc.so.6 => /lib/aarch64-linux-gnu/libc.so.6\n'
                'libluajit-5.1.so.2 => /lib/aarch64-linux-gnu/libluajit-5.1.so.2\n'
                'libperl.so.5.36 => /lib/aarch64-linux-gnu/libperl.so.5.36\n'
                'libcrypto.so.3 => /lib/aarch64-linux-gnu/libcrypto.so.3\n')
    if args[0] == 'readelf':
        return 'Dynamic section: NEEDED [libc.so.6]\n'
    if args == ['openssl', 'version']:
        return 'OpenSSL 3.0.22\n'
    if '-providers' in args:
        return 'Providers:\n  default\n    status: active\n  legacy\n    status: active\n'
    if '-cipher-algorithms' in args:
        return 'DES-CBC @ legacy\n'
    raise AssertionError(args)


def fixture_text(replacements):
    """Join guarded contexts, preserving shared boundaries between hunks."""
    result = ''
    for old, _new in replacements:
        if old in result:
            continue
        overlap = 0
        for count in range(min(len(result), len(old)), 0, -1):
            if result.endswith(old[:count]):
                overlap = count
                break
        if result and not overlap:
            result += '\n'
        result += old[overlap:]
    return result


class TraditionalBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = FakeEngine(self.tmp.name)
        self.source = self.engine.work / 'sources/current'
        self.source.mkdir()
        self.pristine = {}
        for name in build.SOURCE_HASHES:
            text = fixture_text(build.SOURCE_PATCHES[name]) if name in build.SOURCE_PATCHES else '// guarded fixture\n'
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            self.pristine[name] = path.read_bytes()
        (self.source / 'ordinary.cpp').write_text('int unchanged = 1;\n')
        self.pristine['ordinary.cpp'] = (self.source / 'ordinary.cpp').read_bytes()
        self.provenance = {
            'type': 'github', 'repo': build.REPOSITORY, 'ref': 'master',
            'commit': build.REVISION, 'imported': 1.0, 'archive_sha256': 'a' * 64,
        }
        self.save_provenance()
        self.guards = self.enter(patch.object(build, 'SOURCE_HASHES', {
            name: sha(data) for name, data in self.pristine.items() if name != 'ordinary.cpp'}))
        self.runtime = self.enter(patch.object(build, '_runtime', return_value={
            'ready': True, 'message': 'Fixture ARM64 toolchain', 'identity': 'b' * 64}))
        self.websocket_files = {
            'websocketpp/config/core.hpp': b'// pinned core header\n',
            'websocketpp/server.hpp': b'// pinned server header\n',
            'README.md': b'fixture websocketpp\n',
        }
        digest = hashlib.sha256()
        for name, data in sorted(self.websocket_files.items()):
            digest.update(name.encode() + b'\0' + str(len(data)).encode() + b'\0' + sha(data).encode() + b'\n')
        self.enter(patch.object(build, 'WEBSOCKET_TREE_SHA256', digest.hexdigest()))
        self.enter(patch.object(build, 'WEBSOCKET_FILES', len(self.websocket_files)))
        self.enter(patch.object(build, 'WEBSOCKET_BYTES', sum(map(len, self.websocket_files.values()))))
        self.enter(patch.object(build, 'MIN_FREE', 0))
        memory = self.engine.work / 'meminfo.fixture'
        memory.write_text('MemAvailable: 8388608 kB\n')
        self.enter(patch.object(build, 'MEMORY_INFO', memory))
        self.websocket_wrapper = 'websocketpp-' + build.WEBSOCKET_REVISION
        self.engine.archive = tar_bytes({
            self.websocket_wrapper + '/' + name: data for name, data in self.websocket_files.items()})
        self.enter(patch.object(build, '_fetch_websocket', side_effect=lambda engine, archive:
                               engine.download(build.WEBSOCKET_URL, archive)))

    def enter(self, manager):
        result = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        return result

    def save_provenance(self):
        write_json(self.source / 'trasc-source.json', self.provenance)

    def assert_pristine(self):
        for name, value in self.pristine.items():
            with self.subTest(source=name):
                self.assertEqual((self.source / name).read_bytes(), value)

    def compile(self, **args):
        return build.build(self.engine, args)

    def overlay(self):
        root, provenance, identity = build._guard_source(self.engine)
        entries = build._inventory(root, self.engine.check_cancel, source=True)
        return build._prepare_overlay(self.engine, root, provenance, identity, entries, 'b' * 64)

    def staged_bytes(self):
        directory = self.engine.work / 'server/bin.staged'
        return {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}

    def assert_no_preparing_stage(self):
        self.assertFalse(list((self.engine.work / 'server').glob('bin.traditional-preparing-*')))
        self.assertFalse((self.engine.work / 'run/traditional-stage.json').exists())

    def test_status_requires_qualified_source_and_runtime(self):
        state = build.status(self.engine)
        self.assertTrue(state['source_supported'])
        self.assertTrue(state['build_allowed'])
        self.assertTrue(state['compile_only'])
        self.assertFalse(state['staged_valid'])
        self.runtime.return_value = {'ready': False, 'message': 'Upgrade the runtime', 'identity': None}
        state = build.status(self.engine)
        self.assertTrue(state['source_supported'])
        self.assertFalse(state['runtime_ready'])
        self.assertFalse(state['build_allowed'])
        self.assertIn('Upgrade', state['runtime_message'])

    def test_unknown_git_revision_or_repository_is_rejected(self):
        for field, value in (('commit', 'b' * 40), ('repo', 'https://github.com/example/Server')):
            with self.subTest(field=field):
                original = self.provenance[field]
                self.provenance[field] = value
                self.save_provenance()
                self.assertFalse(build.status(self.engine)['source_supported'])
                with self.assertRaises(ValueError):
                    build._guard_source(self.engine)
                self.provenance[field] = original
        self.assert_pristine()

    def test_archive_requires_sha_and_finite_import_time(self):
        self.provenance['type'] = 'archive'
        self.save_provenance()
        self.assertTrue(build.status(self.engine)['source_supported'])
        for field, value in (('archive_sha256', ''), ('imported', float('nan')), ('imported', float('inf'))):
            with self.subTest(field=field, value=value):
                original = self.provenance[field]
                self.provenance[field] = value
                self.save_provenance()
                self.assertFalse(build.status(self.engine)['source_supported'])
                self.provenance[field] = original

    def test_last_guard_mismatch_does_not_modify_imported_source(self):
        name = sorted(build.SOURCE_HASHES)[-1]
        path = self.source / name
        path.write_bytes(path.read_bytes() + b'\nunsupported change\n')
        with self.assertRaises(ValueError):
            build._guard_source(self.engine)
        self.assertFalse((self.engine.work / 'builds/traditional/source').exists())
        for other, value in self.pristine.items():
            if other != name:
                self.assertEqual((self.source / other).read_bytes(), value)

    def test_source_and_in_tree_symlinks_are_rejected(self):
        target = self.engine.work / 'server/live.txt'
        target.write_text('live world')
        (self.source / 'link.cpp').symlink_to(target)
        with self.assertRaises(ValueError):
            build._inventory(self.source, self.engine.check_cancel, source=True)
        self.assertEqual(target.read_text(), 'live world')
        (self.source / 'link.cpp').unlink()
        displaced = self.engine.work / 'sources/displaced'
        os.replace(self.source, displaced)
        self.source.symlink_to(displaced, target_is_directory=True)
        self.assertFalse(build.status(self.engine)['source_supported'])

    def test_build_stages_nine_without_database_maps_or_content(self):
        result = self.compile()
        self.assertTrue(result['staged'])
        self.assertTrue(result['compile_only'])
        stage = self.engine.work / 'server/bin.staged'
        self.assertEqual(set(path.name for path in stage.iterdir()),
                         set(build.BINARIES) | {'build-info.json', 'verification.json'})
        self.assertTrue(build.status(self.engine)['staged_valid'])
        self.assertIn('deployment', build.status(self.engine)['staged_message'])
        self.assertFalse(self.engine.config['database_imported'])
        self.assertFalse((self.engine.work / 'maps').exists())
        self.assertEqual(self.engine.downloads, [build.WEBSOCKET_URL])
        command = next(args for args in self.engine.commands if '--build' in args)
        self.assertEqual(command[command.index('--parallel') + 1], '1')
        self.assertEqual(command[command.index('--target') + 1:], list(build.BINARIES))
        self.assert_pristine()
        self.assert_no_preparing_stage()

    def test_jobs_cap_and_other_profile_are_guarded(self):
        for value in (0, 3, True, '4', '1; touch /tmp/file'):
            with self.subTest(jobs=value), self.assertRaises(ValueError):
                self.compile(jobs=value)
        self.assertFalse(self.engine.commands)
        self.compile(jobs=2)
        self.assertEqual(self.engine.config['jobs'], 2)
        self.engine.profile = 'custom'
        with self.assertRaisesRegex(ValueError, 'Traditional profile'):
            self.compile()

    def test_overlay_is_pristine_copy_and_reused_without_repatching(self):
        overlay, identity = self.overlay()
        self.assert_pristine()
        root_cmake = (overlay / 'CMakeLists.txt').read_text()
        self.assertIn('${CMAKE_CURRENT_LIST_DIR}/cmake/trasc-system-dependencies.cmake', root_cmake)
        self.assertNotIn(str(self.engine.work), root_cmake)
        self.assertEqual((overlay / 'ordinary.cpp').read_bytes(), self.pristine['ordinary.cpp'])
        self.assertIn('#include <cstdint>', (overlay / 'common/net/crc32.cpp').read_text())
        self.assertNotIn('UNITY_BUILD ON', (overlay / 'zone/CMakeLists.txt').read_text())
        times = {str(path.relative_to(overlay)): path.stat().st_mtime_ns
                 for path in overlay.rglob('*') if path.is_file()}
        again, again_identity = self.overlay()
        self.assertEqual((again, again_identity), (overlay, identity))
        self.assertEqual(times, {str(path.relative_to(again)): path.stat().st_mtime_ns
                                for path in again.rglob('*') if path.is_file()})
        self.assertEqual(self.engine.downloads, [build.WEBSOCKET_URL])

    def test_tampered_unpatched_cache_file_rebuilds_and_clears_objects(self):
        overlay, _ = self.overlay()
        objects = self.engine.work / 'builds/traditional/objects'
        objects.mkdir()
        (objects / 'stale-object.o').write_bytes(b'incompatible object')
        (overlay / 'ordinary.cpp').write_text('int injected = 2;\n')
        self.overlay()
        self.assertFalse(objects.exists())
        self.assertEqual((overlay / 'ordinary.cpp').read_bytes(), self.pristine['ordinary.cpp'])
        self.assert_pristine()

    def test_forged_cache_digest_cannot_qualify_modified_source(self):
        overlay, _ = self.overlay()
        (overlay / 'ordinary.cpp').write_text('int injected = 2;\n')
        receipt_path = self.engine.work / 'builds/traditional/overlay-receipt.json'
        receipt = json.loads(receipt_path.read_text())
        receipt['overlay_sha256'] = build._tree_sha(build._inventory(overlay))
        write_json(receipt_path, receipt)
        self.overlay()
        self.assertEqual((overlay / 'ordinary.cpp').read_bytes(), self.pristine['ordinary.cpp'])

    def test_partial_or_unknown_receipt_regenerates_overlay(self):
        overlay, _ = self.overlay()
        receipt_path = self.engine.work / 'builds/traditional/overlay-receipt.json'
        for value in ({'format': 1}, {'format': 2, 'identity': 'not-qualified'}):
            with self.subTest(receipt=value):
                write_json(receipt_path, value)
                (overlay / 'ordinary.cpp').write_bytes(b'partial overlay')
                self.overlay()
                self.assertEqual((overlay / 'ordinary.cpp').read_bytes(), self.pristine['ordinary.cpp'])

    def test_previous_stage_survives_configure_compile_and_verification_failures(self):
        self.compile()
        previous = self.staged_bytes()
        faults = ('fail_configure', 'fail_compile', 'wrong_architecture', 'bad_helper_hash')
        for fault in faults:
            with self.subTest(fault=fault):
                setattr(self.engine, fault, True)
                try:
                    with self.assertRaises((ValueError, OSError)):
                        self.compile()
                finally:
                    setattr(self.engine, fault, False)
                self.assertEqual(self.staged_bytes(), previous)
                self.assert_no_preparing_stage()
        self.assert_pristine()

    def test_missing_ninth_output_preserves_previous_stage(self):
        self.compile()
        previous = self.staged_bytes()
        self.engine.omit = {'import_client_files'}
        with self.assertRaises((ValueError, OSError)):
            self.compile()
        self.assertEqual(self.staged_bytes(), previous)
        self.assert_no_preparing_stage()

    def test_cancel_during_verification_preserves_previous_stage(self):
        self.compile()
        previous = self.staged_bytes()
        self.engine.on_verify = self.engine.cancel.set
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.compile()
        self.assertEqual(self.staged_bytes(), previous)
        self.assert_no_preparing_stage()

    def test_source_changed_during_compile_cannot_be_promoted(self):
        self.compile()
        previous = self.staged_bytes()
        self.engine.on_compile = lambda: (self.source / 'ordinary.cpp').write_text('new imported code\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            self.compile()
        self.assertEqual(self.staged_bytes(), previous)
        self.assert_no_preparing_stage()

    def test_new_import_and_runtime_make_previous_stage_stale(self):
        self.compile()
        previous = self.staged_bytes()
        self.provenance['imported'] = 2.0
        self.save_provenance()
        self.assertFalse(build.status(self.engine)['staged_valid'])
        self.assertEqual(self.staged_bytes(), previous)
        self.provenance['imported'] = 1.0
        self.save_provenance()
        self.assertTrue(build.status(self.engine)['staged_valid'])
        self.runtime.return_value['identity'] = 'c' * 64
        self.assertFalse(build.status(self.engine)['staged_valid'])
        self.assertEqual(self.staged_bytes(), previous)

    def test_unpatched_source_edit_makes_staged_build_stale(self):
        self.compile()
        previous = self.staged_bytes()
        self.assertTrue(build.status(self.engine)['staged_valid'])
        (self.source / 'ordinary.cpp').write_text('int changed = 2;\n')
        state = build.status(self.engine)
        self.assertTrue(state['source_supported'])
        self.assertFalse(state['staged_valid'])
        self.assertEqual(self.staged_bytes(), previous)

    def test_restored_source_with_same_bytes_remains_qualified(self):
        self.compile()
        self.assertTrue(build.status(self.engine)['staged_valid'])
        before_cache = self.engine._traditional_source_cache
        for name, value in self.pristine.items():
            path = self.source / name
            path.unlink()
            path.write_bytes(value)
        self.assertTrue(build.status(self.engine)['staged_valid'])
        after_cache = self.engine._traditional_source_cache
        self.assertNotEqual(before_cache[0], after_cache[0])
        self.assertEqual(before_cache[1], after_cache[1])

    def test_changed_recipe_invalidates_stage_and_object_cache(self):
        self.compile()
        previous = self.staged_bytes()
        objects = self.engine.work / 'builds/traditional/objects'
        (objects / 'stale-object.o').write_bytes(b'old recipe object')
        with patch.object(build, '_recipe_identity', return_value='c' * 64):
            self.assertFalse(build.status(self.engine)['staged_valid'])
            self.overlay()
        self.assertFalse(objects.exists())
        self.assertEqual(self.staged_bytes(), previous)

    def test_cancel_during_binary_copy_preserves_previous_stage(self):
        self.compile()
        previous = self.staged_bytes()
        read = build._read
        def cancel_after_first_binary(path, *args, **kwargs):
            value = read(path, *args, **kwargs)
            if Path(path).name == 'world' and Path(path).parent == self.engine.work / 'builds/traditional/objects/bin':
                self.engine.cancel.set()
            return value
        with patch.object(build, '_read', side_effect=cancel_after_first_binary):
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                self.compile()
        self.assertEqual(self.staged_bytes(), previous)
        self.assert_no_preparing_stage()

    def test_failed_second_rename_restores_previous_stage(self):
        self.compile()
        previous = self.staged_bytes()
        replace = os.replace
        def fail_activation(source, destination):
            if Path(source).name.startswith('bin.traditional-preparing-') and Path(destination).name == 'bin.staged':
                raise OSError('Simulated stage activation failure')
            return replace(source, destination)
        with patch.object(build.os, 'replace', side_effect=fail_activation):
            with self.assertRaisesRegex(OSError, 'activation failure'):
                self.compile()
        self.assertEqual(self.staged_bytes(), previous)
        self.assert_no_preparing_stage()

    def test_journal_commit_failure_restores_previous_stage(self):
        self.compile()
        previous = self.staged_bytes()
        unlink = Path.unlink
        failures = []
        def fail_commit(path, *args, **kwargs):
            if path.name == 'traditional-stage.json' and not failures:
                failures.append(True)
                raise OSError('Simulated journal commit failure')
            return unlink(path, *args, **kwargs)
        with patch.object(build.Path, 'unlink', new=fail_commit):
            with self.assertRaisesRegex(OSError, 'journal commit'):
                self.compile()
        self.assertEqual(self.staged_bytes(), previous)
        self.assert_no_preparing_stage()

    def test_restart_restores_journaled_previous_stage(self):
        self.compile()
        previous = self.staged_bytes()
        current = self.engine.work / 'server/bin.staged'
        backup = self.engine.work / 'server/bin.traditional-previous'
        temporary = self.engine.work / 'server' / ('bin.traditional-preparing-' + '0' * 16)
        temporary.mkdir()
        (temporary / 'world').write_bytes(b'partial new binary')
        os.replace(current, backup)
        write_json(self.engine.work / 'run/traditional-stage.json', {
            'format': 1, 'recipe': build.RECIPE, 'stage': temporary.name, 'previous': True})
        build.recover(self.engine)
        self.assertEqual(self.staged_bytes(), previous)
        self.assertFalse(backup.exists())
        self.assert_no_preparing_stage()

    def test_invalid_recovery_journal_blocks_build_and_preserves_files(self):
        self.compile()
        previous = self.staged_bytes()
        journal = self.engine.work / 'run/traditional-stage.json'
        write_json(journal, {'format': 1, 'recipe': build.RECIPE, 'stage': '../../live', 'previous': True})
        with self.assertRaisesRegex(ValueError, 'recovery journal'):
            build.recover(self.engine)
        with self.assertRaisesRegex(ValueError, 'recovery journal'):
            self.compile()
        self.assertEqual(self.staged_bytes(), previous)
        self.assertTrue(journal.exists())

    def test_status_has_no_download_compile_or_filesystem_write(self):
        before = {str(path.relative_to(self.engine.work)): path.stat().st_mtime_ns
                  for path in self.engine.work.rglob('*')}
        for _ in range(3):
            self.assertTrue(build.status(self.engine)['build_allowed'])
        after = {str(path.relative_to(self.engine.work)): path.stat().st_mtime_ns
                 for path in self.engine.work.rglob('*')}
        self.assertEqual(before, after)
        self.assertFalse(self.engine.commands)
        self.assertFalse(self.engine.downloads)

    def test_source_inventory_limits_and_cancellation(self):
        for kwargs in ({'maximum_files': 1}, {'maximum_bytes': 1}):
            with self.subTest(limit=kwargs), self.assertRaisesRegex(ValueError, 'supported size'):
                build._inventory(self.source, self.engine.check_cancel, source=True, **kwargs)
        self.engine.cancel.set()
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            build._inventory(self.source, self.engine.check_cancel, source=True)
        self.assert_pristine()

    def test_websocket_archive_traversal_symlink_and_digest_are_rejected(self):
        wrapper = self.websocket_wrapper
        symlink = tarfile.TarInfo(wrapper + '/link')
        symlink.type = tarfile.SYMTYPE
        symlink.linkname = str(self.engine.work / 'server')
        valid = {wrapper + '/' + name: data for name, data in self.websocket_files.items()}
        bad_archives = (
            tar_bytes({wrapper + '/../../escape': b'bad'}),
            tar_bytes(valid, extra=symlink),
            tar_bytes({name: data.replace(b'pinned', b'broken') for name, data in valid.items()}),
        )
        for number, data in enumerate(bad_archives):
            with self.subTest(archive=number):
                archive = self.engine.work / 'incoming/websocket.tar.gz'
                archive.write_bytes(data)
                destination = self.engine.work / ('extraction-%d' % number)
                with self.assertRaises(ValueError):
                    build._extract_websocket(self.engine, archive, destination)
                self.assertFalse((self.engine.work / 'escape').exists())
        self.assert_pristine()

    def test_failed_websocket_hydration_keeps_previous_overlay(self):
        overlay, _ = self.overlay()
        preserved = {str(path.relative_to(overlay)): path.read_bytes()
                     for path in overlay.rglob('*') if path.is_file()}
        # A new import requires a new overlay. A dependency failure must retain
        # the last complete overlay and the unmodified import.
        self.provenance['imported'] = 2.0
        self.save_provenance()
        self.engine.archive = tar_bytes({self.websocket_wrapper + '/README.md': b'wrong dependency'})
        with self.assertRaises(ValueError):
            self.overlay()
        self.assertEqual(preserved, {str(path.relative_to(overlay)): path.read_bytes()
                                     for path in overlay.rglob('*') if path.is_file()})
        self.assertFalse(list((self.engine.work / 'builds/traditional').glob('source-preparing-*')))
        self.assert_pristine()

    def test_complete_pinned_websocket_import_needs_no_download(self):
        imported = self.source / 'submodules/websocketpp'
        for name, data in self.websocket_files.items():
            target = imported / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.overlay()
        self.assertFalse(self.engine.downloads)
        for name, data in self.websocket_files.items():
            self.assertEqual((imported / name).read_bytes(), data)

    def test_cancelled_websocket_hydration_removes_partial_overlay(self):
        def fetch_and_cancel(engine, archive):
            engine.download(build.WEBSOCKET_URL, archive)
            engine.cancel.set()
        with patch.object(build, '_fetch_websocket', side_effect=fetch_and_cancel):
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                self.overlay()
        self.assertFalse((self.engine.work / 'builds/traditional/source').exists())
        self.assertFalse(list((self.engine.work / 'builds/traditional').glob('source-preparing-*')))
        self.assert_pristine()

    def test_memory_guard_matches_job_count(self):
        build.MEMORY_INFO.write_text('MemAvailable: 2097152 kB\n')
        with self.assertRaisesRegex(ValueError, '3 GiB'):
            build._memory_jobs(1)
        build.MEMORY_INFO.write_text('MemAvailable: 4194304 kB\n')
        build._memory_jobs(1)
        with self.assertRaisesRegex(ValueError, '6 GiB'):
            build._memory_jobs(2)
        build.MEMORY_INFO.write_text('MemAvailable: 7340032 kB\n')
        build._memory_jobs(2)
        build.MEMORY_INFO.unlink()
        build._memory_jobs(1)
        with self.assertRaisesRegex(ValueError, 'cannot be measured'):
            build._memory_jobs(2)

    def test_preparation_runtime_is_not_qualified_for_compilation(self):
        marker = self.engine.work / 'runtime.fixture.json'
        base = {'format': 1, 'architecture': 'arm64', 'profile': 'traditional',
                'runtime': 'traditional-1.0', 'build_adapter': 1}
        for field, value in (('runtime', '1.1'), ('profile', 'custom'), ('architecture', 'x86_64'), ('build_adapter', 0)):
            with self.subTest(marker=field):
                write_json(marker, dict(base, **{field: value}))
                with patch.object(build, 'RUNTIME_MARKER', marker), patch.object(build, '_tool') as tools:
                    state = REAL_RUNTIME(self.engine)
                self.assertFalse(state['ready'])
                self.assertIn('Traditional 1.0', state['message'])
                tools.assert_not_called()

    def test_runtime_preflight_is_cached_until_marker_changes(self):
        marker = self.engine.work / 'runtime.fixture.json'
        data = {'format': 1, 'architecture': 'arm64', 'profile': 'traditional',
                'runtime': 'traditional-1.0', 'build_adapter': 1}
        write_json(marker, data)
        def command(args):
            if args[-1] == '-m': return 'aarch64'
            if args[-1] == '-dumpmachine': return 'aarch64-linux-gnu'
            if args[-1] == '-dumpfullversion': return '12.2.0'
            if args[0] == '/usr/bin/cmake': return 'cmake version 3.25.1'
            if '-providers' in args: return 'default\nlegacy\n'
            if '-cipher-algorithms' in args: return 'DES-CBC @ legacy'
            return 'fixture package versions'
        with patch.object(build, 'RUNTIME_MARKER', marker), patch.object(build.Path, 'is_file', return_value=True), \
                patch.object(build, '_tool', side_effect=command) as tools:
            first = REAL_RUNTIME(self.engine)
            self.assertTrue(first['ready'])
            count = tools.call_count
            self.assertEqual(REAL_RUNTIME(self.engine), first)
            self.assertEqual(tools.call_count, count)
            data['generation'] = 2
            write_json(marker, data)
            self.assertTrue(REAL_RUNTIME(self.engine)['ready'])
            self.assertGreater(tools.call_count, count)

    def test_bounded_websocket_download_rejects_redirects_and_oversize(self):
        class Response(io.BytesIO):
            def __init__(self, data, url=build.WEBSOCKET_URL, declared=0):
                super().__init__(data)
                self.url = url
                self.headers = {'Content-Length': str(declared)}
        archive = self.engine.work / 'incoming/fetched.tar.gz'
        for response in (Response(b'bad', url='https://example.com/redirect'),
                         Response(b'bad', declared=build.MAX_WEBSOCKET_DOWNLOAD + 1)):
            with self.subTest(url=response.url, headers=response.headers):
                with patch.object(build.urllib.request, 'urlopen', return_value=response):
                    with self.assertRaises(ValueError):
                        REAL_FETCH(self.engine, archive)
                self.assertFalse(archive.exists())
                self.assertFalse(archive.with_name(archive.name + '.part').exists())
        with patch.object(build, 'MAX_WEBSOCKET_DOWNLOAD', 8), \
                patch.object(build.urllib.request, 'urlopen', return_value=Response(b'123456789')):
            with self.assertRaisesRegex(ValueError, 'size limit'):
                REAL_FETCH(self.engine, archive)
        self.assertFalse(archive.with_name(archive.name + '.part').exists())


if __name__ == '__main__':
    unittest.main()
