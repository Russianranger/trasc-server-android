"""Source delta review, stale-state refusal, and durable rollback boundaries."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine, atomic_json
import source_updates as updates
import takp_build


class SourceUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = Engine(Path(self.tmp.name))
        self.root = self.engine.work / 'sources/current'
        self.before = {'CMakeLists.txt': 'project(fixture)', 'zone/a.cpp': 'old', 'zone/b.cpp': 'unchanged',
                       'zone/deleted.cpp': 'deleted', 'libs/luabind/CMakeLists.txt': '# library',
                       'submodules/fmt/CMakeLists.txt': '# library', 'submodules/libuv/CMakeLists.txt': '# library'}
        self.archive('initial.zip', self.before)
        self.engine.import_source({'file': 'initial.zip'})
        self.after = dict(self.before, **{'zone/a.cpp': 'new', 'zone/added.cpp': 'added'})
        self.after.pop('zone/deleted.cpp')
        self.archive('update.zip', self.after)
        self.protected = {}
        for name in ('server/bin/zone', 'server/bin.staged/build-info.json', 'database/players',
                     'client/current/eqclient.ini', 'maps/local.map', 'builds/current/object.o'):
            path = self.engine.work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'protected')
            self.protected[name] = (path.read_bytes(), path.stat().st_mtime_ns)

    def archive(self, name, entries):
        archive = self.engine.work / 'incoming' / name
        with zipfile.ZipFile(archive, 'w') as output:
            for name, value in entries.items():
                output.writestr('Server/' + name, value)
        return archive

    def preview(self):
        return self.engine.source_update_preview({'file': 'update.zip'})

    def assert_protected(self):
        for name, value in self.protected.items():
            path = self.engine.work / name
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), value)

    def test_delta_preserves_unchanged_inode_mtime_runtime_and_compiler_cache(self):
        unchanged = self.root / 'zone/b.cpp'
        before = (unchanged.stat().st_ino, unchanged.stat().st_mtime_ns)
        changed = self.root / 'zone/a.cpp'
        os.utime(changed, ns=(1, 1))
        result = self.preview()
        self.assertEqual(result['counts'], {'added': 1, 'deleted': 1, 'changed': 1})
        self.assertTrue(result['apply_allowed'])
        self.assertEqual(changed.read_text(), 'old')
        applied = self.engine.source_update_apply({'token': result['token']})
        self.assertTrue(applied['applied'])
        self.assertEqual((unchanged.stat().st_ino, unchanged.stat().st_mtime_ns), before)
        self.assertGreater(changed.stat().st_mtime_ns, 1)
        self.assertEqual(changed.read_text(), 'new')
        self.assertEqual((self.engine.work / applied['recovery_copy'] / 'zone/a.cpp').read_text(), 'old')
        self.assertFalse((self.root / 'zone/deleted.cpp').exists())
        self.assertFalse((self.engine.work / 'run/source-update.json').exists())
        self.assert_protected()

    def test_unrecognized_local_edits_are_reviewed_and_never_overwritten(self):
        (self.root / 'zone/a.cpp').write_text('my edit')
        (self.root / 'zone/local.cpp').write_text('my file')
        result = self.preview()
        self.assertFalse(result['apply_allowed'])
        self.assertEqual(result['conflicts'], ['zone/a.cpp', 'zone/local.cpp'])
        with self.assertRaisesRegex(ValueError, 'cannot overwrite'):
            self.engine.source_update_apply({'token': result['token']})
        self.assertEqual((self.root / 'zone/a.cpp').read_text(), 'my edit')
        self.assert_protected()

    def test_source_or_candidate_change_after_review_is_rejected(self):
        preview = self.preview()
        (self.root / 'zone/b.cpp').write_text('later edit')
        with self.assertRaisesRegex(ValueError, 'Source changed after review'):
            self.engine.source_update_apply({'token': preview['token']})
        (self.root / 'zone/b.cpp').write_text(self.before['zone/b.cpp'])
        folder = self.engine.work / 'sources' / ('update-' + preview['token'])
        info = json.loads((folder / 'preview.json').read_text())
        (folder / info['candidate'] / 'zone/a.cpp').write_text('download edited')
        with self.assertRaisesRegex(ValueError, 'Downloaded source changed'):
            self.engine.source_update_apply({'token': preview['token']})
        self.assert_protected()

    def test_partial_activation_failure_rolls_back_every_changed_file(self):
        preview = self.preview()
        original = updates._copy_verified
        failed = False
        def copy(source, destination, expected, fresh=False):
            nonlocal failed
            if fresh and Path(destination).name == 'added.cpp' and not failed:
                failed = True
                raise OSError('simulated storage failure')
            return original(source, destination, expected, fresh)
        with patch.object(updates, '_copy_verified', side_effect=copy):
            with self.assertRaisesRegex(OSError, 'storage failure'):
                self.engine.source_update_apply({'token': preview['token']})
        self.assertEqual({name: (self.root / name).read_text() for name in self.before}, self.before)
        self.assertFalse((self.root / 'zone/added.cpp').exists())
        self.assertFalse((self.engine.work / 'run/source-update.json').exists())
        self.assert_protected()

    def test_process_death_journal_restores_source_before_other_work(self):
        preview = self.preview()
        folder = self.engine.work / 'sources' / ('update-' + preview['token'])
        info = json.loads((folder / 'preview.json').read_text())
        token = preview['token']
        backup = self.engine.work / 'sources/update-backups' / token
        names = ['zone/a.cpp', 'zone/added.cpp', 'zone/deleted.cpp']
        for name in names:
            if name in info['before']:
                updates._copy_verified(self.root / name, backup / name, info['before'][name])
        (self.root / 'zone/a.cpp').write_text('partly activated')
        (self.root / 'zone/added.cpp').write_text('partly activated')
        (self.root / 'zone/deleted.cpp').unlink()
        atomic_json(self.engine.work / 'run/source-update.json', {
            'format': 1, 'profile': 'custom', 'phase': 'applying', 'token': token,
            'source': info['source'], 'before': info['before'], 'affected': names})
        updates.recover(self.engine)
        self.assertEqual(updates.inventory(self.root), info['before'])
        self.assert_protected()

    def test_corrupt_preimage_or_cross_profile_journal_never_mutates_source(self):
        before = updates.inventory(self.root)
        journal = {'format': 1, 'profile': 'traditional', 'phase': 'applying', 'token': 'a' * 32,
                   'source': json.loads((self.root / 'trasc-source.json').read_text()), 'before': before, 'affected': ['zone/a.cpp']}
        atomic_json(self.engine.work / 'run/source-update.json', journal)
        with self.assertRaisesRegex(ValueError, 'Invalid source recovery'):
            updates.recover(self.engine)
        journal['profile'] = 'custom'
        (self.engine.work / 'sources/update-backups' / journal['token']).mkdir(parents=True)
        atomic_json(self.engine.work / 'run/source-update.json', journal)
        with self.assertRaisesRegex(ValueError, 'recovery copy changed'):
            updates.recover(self.engine)
        self.assertEqual(updates.inventory(self.root), before)
        self.assert_protected()

    def test_rollback_prevalidates_all_targets_and_metadata_before_any_live_write(self):
        before = updates.inventory(self.root)
        backup = self.engine.work / 'sources/update-backups' / ('b' * 32)
        names = ['zone/a.cpp', 'zone/b.cpp']
        for name in names:
            updates._copy_verified(self.root / name, backup / name, before[name])
        (self.root / 'zone/a.cpp').write_text('first live input must stay unchanged on refusal')
        (self.root / 'zone/b.cpp').unlink()
        (self.root / 'zone/b.cpp').symlink_to(backup / 'zone/b.cpp')
        journal = {'format': 1, 'profile': 'custom', 'phase': 'applying', 'token': 'b' * 32,
                   'source': json.loads((self.root / 'trasc-source.json').read_text()),
                   'before': before, 'affected': names}
        marker_bytes = (self.root / 'trasc-source.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            updates._rollback(self.engine, journal)
        self.assertEqual((self.root / 'zone/a.cpp').read_text(), 'first live input must stay unchanged on refusal')
        (self.root / 'zone/b.cpp').unlink()
        for invalid in (None, [], {'type': 'github', 'imported': 1, 'commit': '../wrong'}):
            with self.assertRaisesRegex(ValueError, 'source.*(provenance|identity)|source provenance'):
                updates._rollback(self.engine, dict(journal, source=invalid))
            self.assertEqual((self.root / 'zone/a.cpp').read_text(), 'first live input must stay unchanged on refusal')
            self.assertEqual((self.root / 'trasc-source.json').read_bytes(), marker_bytes)
        self.assert_protected()

    def test_rollback_rejects_file_ancestor_before_restoring_an_earlier_target(self):
        before = updates.inventory(self.root)
        backup = self.engine.work / 'sources/update-backups' / ('c' * 32)
        names = ['CMakeLists.txt', 'zone/b.cpp']
        for name in names:
            updates._copy_verified(self.root / name, backup / name, before[name])
        (self.root / 'CMakeLists.txt').write_text('live first target must remain unchanged')
        os.replace(self.root / 'zone', self.root / 'zone-away')
        (self.root / 'zone').write_text('directory was replaced by a file')
        journal = {'format': 1, 'profile': 'custom', 'phase': 'applying', 'token': 'c' * 32,
                   'source': json.loads((self.root / 'trasc-source.json').read_text()),
                   'before': before, 'affected': names}
        with self.assertRaisesRegex(ValueError, 'ancestor.*ordinary directory'):
            updates._rollback(self.engine, journal)
        self.assertEqual((self.root / 'CMakeLists.txt').read_text(), 'live first target must remain unchanged')
        self.assertEqual((self.root / 'zone').read_text(), 'directory was replaced by a file')
        self.assert_protected()

    def test_legacy_github_import_is_reconstructed_from_exact_original_commit(self):
        marker = json.loads((self.root / 'trasc-source.json').read_text())
        marker.update(type='github', repo=self.engine.config['repo'], ref='main', commit='a' * 40)
        atomic_json(self.root / 'trasc-source.json', marker)
        (self.engine.work / 'sources/managed-source.json').unlink()
        fetched = []
        def fetch(url, ref, target):
            fetched.append(ref)
            archive = 'initial.zip' if ref == 'a' * 40 else 'update.zip'
            shutil.copy2(self.engine.work / 'incoming' / archive, target)
            return {'repo': url, 'ref': ref, 'commit': 'a' * 40 if ref == 'a' * 40 else 'b' * 40}
        with patch.object(self.engine, 'github_download', side_effect=fetch):
            result = self.engine.source_update_preview({})
        self.assertEqual(fetched, ['main', 'a' * 40])
        self.assertEqual(result['from_commit'], 'a' * 40)
        self.assertEqual(result['to_commit'], 'b' * 40)
        self.assertTrue(result['apply_allowed'])
        folder = self.engine.work / 'sources' / ('update-' + result['token'])
        self.assertFalse((folder / 'baseline').exists())
        self.assertFalse((folder / 'incoming.zip').exists())

    def test_legacy_offline_import_has_no_assumed_clean_baseline(self):
        (self.engine.work / 'sources/managed-source.json').unlink()
        with self.assertRaisesRegex(ValueError, 'older offline import'):
            self.preview()
        self.assertEqual((self.root / 'zone/a.cpp').read_text(), 'old')
        self.assert_protected()

    def test_import_inventory_failure_preserves_current_previous_and_receipt(self):
        previous = self.engine.work / 'sources/previous'
        previous.mkdir()
        (previous / 'older-source').write_text('older recovery copy')
        receipt = (self.engine.work / 'sources/managed-source.json').read_bytes()
        with patch.object(updates, 'MAX_FILE', 1):
            with self.assertRaisesRegex(ValueError, 'bounded update inventory'):
                self.engine.import_source({'file': 'update.zip'})
        self.assertEqual((self.root / 'zone/a.cpp').read_text(), 'old')
        self.assertEqual((previous / 'older-source').read_text(), 'older recovery copy')
        self.assertEqual((self.engine.work / 'sources/managed-source.json').read_bytes(), receipt)
        self.assert_protected()

    def test_cache_status_exposes_unverified_legacy_custom_fallback_before_build(self):
        directory = self.engine.work / 'builds/current'
        (directory / 'CMakeCache.txt').write_text('old cache without compiler identity')
        with patch.object(updates, 'custom_runtime_identity', return_value='a' * 64):
            state = updates.status(self.engine)
        self.assertTrue(state['requires_fresh_build'])
        self.assertFalse(state['cache_reusable'])
        self.assertIn('old cache and installed binaries are preserved', state['cache_message'])
        with patch.object(self.engine, 'build', return_value={'staged': True}) as build:
            self.engine.build_update({'jobs': 1, 'allow_fresh': True})
            build.assert_called_once_with({'jobs': 1, 'allow_fresh': True, 'incremental': False})

    def test_symlink_source_and_changed_profile_token_are_refused(self):
        (self.root / 'zone/link').symlink_to(self.root / 'zone/a.cpp')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.preview()
        (self.root / 'zone/link').unlink()
        result = self.preview()
        folder = self.engine.work / 'sources' / ('update-' + result['token'])
        info = json.loads((folder / 'preview.json').read_text())
        info['profile'] = 'takp'
        atomic_json(folder / 'preview.json', info)
        with self.assertRaisesRegex(ValueError, 'different profile'):
            self.engine.source_update_apply({'token': result['token']})

    def test_guarded_patch_recording_does_not_adopt_unrelated_local_edits(self):
        (self.root / 'zone/b.cpp').write_text('local edit')
        before = updates.inventory(self.root)
        (self.root / 'zone/a.cpp').write_text('guarded adapter output')
        updates.remember_patch_outputs(self.engine, before)
        result = self.preview()
        self.assertEqual(result['conflicts'], ['zone/b.cpp'])

    def test_deploy_updated_refuses_an_earlier_successful_stage(self):
        with patch.object(self.engine, 'deploy') as deploy:
            with self.assertRaisesRegex(ValueError, 'Compile the current updated source'):
                self.engine.deploy_update({})
        deploy.assert_not_called()
        self.assert_protected()

    def test_custom_stage_activation_failure_preserves_prior_successful_stage(self):
        prepared = self.engine.work / ('server/bin.custom-preparing-' + 'a' * 16)
        prepared.mkdir()
        (prepared / 'build-info.json').write_text('new stage')
        original = updates.os.replace
        def replace(source, destination):
            if Path(source) == prepared and Path(destination).name == 'bin.staged':
                raise OSError('simulated stage activation failure')
            return original(source, destination)
        with patch.object(updates.os, 'replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'activation failure'):
                updates.promote_custom_stage(self.engine, prepared)
        self.assertEqual((self.engine.work / 'server/bin.staged/build-info.json').read_bytes(), b'protected')
        self.assertFalse((self.engine.work / 'run/custom-build-stage.json').exists())
        self.assert_protected()

    def test_custom_stage_process_death_recovers_before_other_source_operations(self):
        prepared = self.engine.work / ('server/bin.custom-preparing-' + 'a' * 16)
        retained = self.engine.work / ('server/bin.staged-retained-' + 'b' * 16)
        prepared.mkdir()
        (prepared / 'build-info.json').write_text('new stage')
        os.replace(self.engine.work / 'server/bin.staged', retained)
        os.replace(prepared, self.engine.work / 'server/bin.staged')
        updates._atomic(self.engine.work / 'run/custom-build-stage.json', {
            'format': 1, 'phase': 'applying', 'prepared': prepared.name, 'retained': retained.name, 'previous': True})
        updates.recover(self.engine)
        self.assertEqual((self.engine.work / 'server/bin.staged/build-info.json').read_bytes(), b'protected')
        self.assertEqual((prepared / 'build-info.json').read_text(), 'new stage')
        self.assert_protected()

    def test_server_running_blocks_check_apply_build_and_deploy(self):
        result = self.preview()
        with patch.object(self.engine, 'server_running', return_value=True):
            for call in (lambda: self.preview(), lambda: self.engine.source_update_apply({'token': result['token']}),
                         lambda: self.engine.build_update({})):
                with self.assertRaisesRegex(ValueError, 'Stop the server'):
                    call()
        self.assert_protected()


class CacheReceiptTests(unittest.TestCase):
    def test_legacy_adoption_requires_actual_cache_options_and_explicit_receipt_proof(self):
        with tempfile.TemporaryDirectory() as name:
            engine = Engine(name)
            directory = engine.work / 'builds/fixture'
            directory.mkdir()
            source = engine.work / 'sources/current'
            cache = ('CMAKE_HOME_DIRECTORY:INTERNAL=' + str(source) + '\nCMAKE_CACHEFILE_DIR:INTERNAL=' + str(directory)
                     + '\nCMAKE_GENERATOR:INTERNAL=Ninja\nCMAKE_CXX_COMPILER:FILEPATH=/usr/bin/g++\nCMAKE_BUILD_TYPE:STRING=Release\n')
            (directory / 'CMakeCache.txt').write_text(cache)
            (directory / 'protected.o').write_text('expensive compiled object')
            with self.assertRaisesRegex(ValueError, 'older cache'):
                updates.ensure_cache(engine, directory, 'a' * 64, source, ('-DCMAKE_BUILD_TYPE=Release',))
            updates.ensure_cache(engine, directory, 'a' * 64, source, ('-DCMAKE_BUILD_TYPE=Release',), trusted_legacy=True)
            with self.assertRaisesRegex(ValueError, 'different runtime'):
                updates.ensure_cache(engine, directory, 'b' * 64, source, ('-DCMAKE_BUILD_TYPE=Release',))
            (directory / 'CMakeCache.txt').write_text(cache.replace('Release', 'Debug'))
            with self.assertRaisesRegex(ValueError, 'different runtime'):
                updates.ensure_cache(engine, directory, 'a' * 64, source, ('-DCMAKE_BUILD_TYPE=Release',))
            self.assertEqual((directory / 'protected.o').read_text(), 'expensive compiled object')


class TakpDeployedReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = Engine(Path(self.tmp.name), 'takp')
        self.addCleanup(patch.stopall)
        patch.object(takp_build, 'runtime', return_value={'ready': True, 'identity': 'a' * 64, 'message': 'fixture'}).start()
        patch('traditional_verify.inspect_elf').start()
        self.directory = self.engine.work / 'server/bin'
        self.directory.mkdir()
        hashes = {}
        for binary in takp_build.BINARIES:
            (self.directory / binary).write_bytes(b'qualified fixture ' + binary.encode())
            hashes[binary] = hashlib.sha256((self.directory / binary).read_bytes()).hexdigest()
        (tree, recipe), (commit, files, size) = next(iter(takp_build.DEPLOYED_RECIPES.items()))
        self.info = {'format': 1, 'profile': 'takp', 'recipe': takp_build.RECIPE, 'recipe_sha256': recipe,
                     'source_tree_sha256': tree, 'runtime_identity': 'a' * 64, 'binaries': hashes,
                     'source': {'commit': commit, 'tree_sha256': tree, 'files': files, 'bytes': size,
                                'bundled_dependencies': True}}
        atomic_json(self.directory / 'build-info.json', self.info)

    def test_exact_old_deployed_binaries_remain_ready_without_the_latest_source(self):
        self.assertEqual(takp_build.record(self.engine, 'server/bin'), self.info)
        self.assertTrue(takp_build.status(self.engine)['deployed_valid'])
        self.assertFalse(takp_build.status(self.engine)['source_ready'])
        shutil.copytree(self.directory, self.engine.work / 'server/bin.staged')
        with self.assertRaisesRegex(ValueError, 'qualified source, recipe'):
            takp_build.record(self.engine)

    def test_old_receipt_still_checks_exact_recipe_provenance_runtime_and_binaries(self):
        original = dict(self.info)
        for field, value in (('recipe_sha256', 'b' * 64), ('source_tree_sha256', 'b' * 64), ('runtime_identity', 'b' * 64)):
            atomic_json(self.directory / 'build-info.json', dict(original, **{field: value}))
            with self.assertRaises(ValueError):
                takp_build.record(self.engine, 'server/bin')
        atomic_json(self.directory / 'build-info.json', dict(original, source=dict(original['source'], commit='b' * 40)))
        with self.assertRaises(ValueError):
            takp_build.record(self.engine, 'server/bin')
        atomic_json(self.directory / 'build-info.json', original)
        (self.directory / 'zone').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'binary has changed'):
            takp_build.record(self.engine, 'server/bin')


if __name__ == '__main__':
    unittest.main()
