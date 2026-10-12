"""Real immutable archive regression for the 0.6.24 stale-source setup error.

No server compilation, runtime installation or database service is started.
Only GitHub downloads are supplied by the two caller-provided archive files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine
import takp_build
import takp_runtime

OLD_REVISION = '25bf70acb6bd24853cf09e447ddd62b96a4491a4'
OLD_TREE = '2d15df9713d3742a4ad9c1041e99b081b4896c81b919081377110620a19350ec'


def qualify(old_archive, new_archive, report):
    fixture = {OLD_REVISION: Path(old_archive), takp_build.REVISION: Path(new_archive)}
    for archive in fixture.values():
        if not archive.is_file():
            raise ValueError('Provide both complete official immutable source ZIPs')
    calls = []
    with tempfile.TemporaryDirectory(prefix='trasc-takp-update-') as temporary:
        engine = Engine(Path(temporary) / 'work', 'takp')

        def download(repository, revision, target):
            assert repository == takp_build.REPOSITORY
            assert revision in fixture
            calls.append(revision)
            shutil.copy2(fixture[revision], target)
            return {'repo': repository, 'ref': revision, 'commit': revision}

        with patch.object(engine, 'github_download', side_effect=download):
            # Reproduce the exact import policy from 0.6.22/0.6.23, leaving its
            # older source marker installed when the current launcher starts.
            with patch.multiple(takp_build, REVISION=OLD_REVISION,
                                SOURCE_TREE_SHA256=OLD_TREE,
                                SOURCE_FILES=5550, SOURCE_BYTES=147884398):
                imported = engine.import_source({'url': takp_build.REPOSITORY, 'ref': OLD_REVISION})
            assert imported['source']['takp']['tree_sha256'] == OLD_TREE
            # Earlier launchers had no managed delta receipt. The update must
            # independently retrieve and verify the immutable original tree.
            (engine.work / 'sources/managed-source.json').unlink(missing_ok=True)
            current = engine.source_root()
            unchanged = current / 'CMakeLists.txt'
            unchanged_stamp = unchanged.stat()
            prior_source = (current / 'zone/player_bot.cpp').read_bytes()
            settings = {name: value for name, value in json.loads(engine.config_path.read_text()).items()
                        if name not in ('repo', 'ref')}
            protected = ('server/bin/zone', 'server/bin/build-info.json',
                         'database/existing-character-data', 'client/current/UI_Codex.ini',
                         'client/prefix/existing-wine-prefix')
            for relative in protected:
                path = engine.work / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(('preserve:' + relative).encode())
            snapshot = {name: (engine.work / name).read_bytes() for name in protected}
            calls.clear()

            # The released setup implementation took this branch before any
            # download, producing the misleading "complete ZIP" error.
            try:
                takp_build.qualify_source(current)
            except ValueError as error:
                original_error = str(error)
                assert 'complete TAKP' in original_error
            else:
                raise AssertionError('The old installed source must reproduce the released error')
            assert not calls

            # Exercise the new real setup and actual review/apply transaction.
            # Content activation is outside this source-only regression.
            with patch('takp_runtime.sync_content'), \
                    patch('takp_runtime._component', return_value={'imported': True}), \
                    patch('takp_runtime.status', return_value={}):
                takp_runtime.setup(engine, {})
            qualified = takp_build.qualify_source(current)
            assert qualified['commit'] == takp_build.REVISION
            assert calls == [takp_build.REVISION, OLD_REVISION], calls
            final_stamp = unchanged.stat()
            assert (final_stamp.st_ino, final_stamp.st_mtime_ns) == (unchanged_stamp.st_ino, unchanged_stamp.st_mtime_ns)
            assert (current / 'zone/player_bot.cpp').read_bytes() != prior_source
            assert {name: value for name, value in json.loads(engine.config_path.read_text()).items()
                    if name not in ('repo', 'ref')} == settings
            assert {name: (engine.work / name).read_bytes() for name in protected} == snapshot
            preview = json.loads((engine.work / 'sources/update-preview.json').read_text())
            assert preview['counts'] == {'added': 2, 'changed': 2, 'deleted': 0}, preview
            backup = engine.work / preview['recovery_copy']
            assert (backup / 'zone/player_bot.cpp').read_bytes() == prior_source
            assert not (engine.work / 'run/source-update.json').exists()

            # A second press must not download or rewrite anything.
            calls.clear()
            with patch('takp_runtime.sync_content'), \
                    patch('takp_runtime._component', return_value={'imported': True}), \
                    patch('takp_runtime.status', return_value={}):
                takp_runtime.setup(engine, {})
            assert not calls
            local_edit = unchanged.read_bytes() + b'\n# local change that must survive\n'
            unchanged.write_bytes(local_edit)
            with patch('takp_runtime.sync_content') as sync, \
                    patch('takp_runtime._component', return_value={'imported': True}), \
                    patch('takp_runtime.status', return_value={}):
                try:
                    takp_runtime.setup(engine, {})
                except ValueError as error:
                    assert 'Local source edits' in str(error)
                else:
                    raise AssertionError('Setup must refuse to overwrite local source edits')
                sync.assert_not_called()
            assert unchanged.read_bytes() == local_edit
            assert {name: (engine.work / name).read_bytes() for name in protected} == snapshot
            result = {'result': 'passed', 'from_commit': OLD_REVISION,
                      'to_commit': takp_build.REVISION, 'original_error': original_error,
                      'source': qualified, 'delta': preview['counts'],
                      'unchanged_inode_and_mtime_preserved': True,
                      'deployed_binaries_database_client_prefix_settings_preserved': True,
                      'prior_changed_files_retained': True, 'latest_setup_is_noop': True,
                      'local_source_edits_refused_and_preserved': True,
                      'archive_sha256': {revision: hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
                                         for revision, path in fixture.items()}}
    Path(report).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-archive', required=True)
    parser.add_argument('--new-archive', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    qualify(args.old_archive, args.new_archive, args.report)
