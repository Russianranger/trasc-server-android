"""Reviewed, transactional source deltas for archive-based server workspaces.

GitHub archives are fetched by immutable commit. We do not pretend archive
imports contain .git, and never replace an unrecognized local edit. Unchanged
inputs keep their inode and mtime so CMake/Ninja can reuse its dependency graph.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import time

MAX_FILES = 100000
MAX_BYTES = 4 * 1024**3
MAX_FILE = 256 * 1024**2
MAX_RECEIPT = 32 * 1024**2
FORMAT = 1


def _atomic(path, value):
    from engine import atomic_json
    _mkdir_durable(Path(path).parent)
    atomic_json(path, value)
    _fsync_parent(Path(path).parent)


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECEIPT:
        raise ValueError('Missing or oversized source update receipt')
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Invalid source update receipt')
    return value


def _name(name):
    if not isinstance(name, str):
        raise ValueError('Invalid managed source path')
    path = PurePosixPath(name)
    if (not isinstance(name, str) or not name or path.is_absolute() or '..' in path.parts
            or '\\' in name or any(c in name for c in '\0\n\r') or ':' in path.parts[0]
            or path.as_posix() != name or '.git' in path.parts):
        raise ValueError('Invalid managed source path')
    return name


def _path(root, name):
    path = Path(root) / _name(name)
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError('Source update paths cannot be symbolic links')
        if parent != path and parent.exists() and not parent.is_dir():
            raise ValueError('Source update ancestor is not an ordinary directory')
        if parent == Path(root):
            break
    return path


def _digest(path, check=lambda: None):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check()
            block = stream.read(1024 * 1024)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def inventory(root, check=lambda: None):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Import a complete server source tree first')
    result, total = {}, 0
    def walk(directory, prefix=''):
        nonlocal total
        check()
        with os.scandir(directory) as stream:
            children = sorted(stream, key=lambda value: value.name)
        for entry in children:
            check()
            name = prefix + entry.name
            if entry.name == '.git' or name == 'trasc-source.json':
                continue
            _name(name)
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                walk(Path(entry.path), name + '/')
            elif stat.S_ISREG(info.st_mode):
                total += info.st_size
                if info.st_size > MAX_FILE or total > MAX_BYTES or len(result) >= MAX_FILES:
                    raise ValueError('Server source exceeds the bounded update inventory')
                result[name] = {'bytes': info.st_size, 'sha256': _digest(entry.path, check),
                                'executable': bool(info.st_mode & 0o111)}
            else:
                raise ValueError('Source contains a symlink or special file: ' + name)
    walk(root)
    if not result:
        raise ValueError('Server source tree is empty')
    return result


def identity(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _validated_entries(entries):
    if not isinstance(entries, dict) or len(entries) > MAX_FILES:
        raise ValueError('Invalid managed source inventory')
    total = 0
    for name, info in entries.items():
        _name(name)
        if (not isinstance(info, dict) or set(info) != {'bytes', 'sha256', 'executable'}
                or isinstance(info['bytes'], bool) or not isinstance(info['bytes'], int)
                or not 0 <= info['bytes'] <= MAX_FILE or not isinstance(info['executable'], bool)
                or not re.fullmatch('[0-9a-f]{64}', str(info['sha256']))):
            raise ValueError('Invalid managed source file receipt')
        total += info['bytes']
    if total > MAX_BYTES:
        raise ValueError('Managed source inventory exceeds its size bound')
    return entries


def _source_marker(value):
    if (not isinstance(value, dict) or value.get('type') not in ('archive', 'github')
            or isinstance(value.get('imported'), bool) or not isinstance(value.get('imported'), (int, float))
            or not 0 < value['imported'] < 10**12):
        raise ValueError('Invalid source provenance in recovery receipt')
    if 'archive_sha256' in value and not re.fullmatch('[0-9a-f]{64}', str(value['archive_sha256'])):
        raise ValueError('Invalid source archive identity in recovery receipt')
    if value['type'] == 'github':
        if (not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', str(value.get('repo', '')))
                or not re.fullmatch('[0-9a-f]{40}', str(value.get('commit', '')))
                or not isinstance(value.get('ref'), str) or len(value['ref']) > 1024):
            raise ValueError('Invalid GitHub source identity in recovery receipt')
    return value


def _affected_paths(names):
    if (not isinstance(names, list) or len(names) > MAX_FILES
            or not all(isinstance(name, str) for name in names) or len(set(names)) != len(names)):
        raise ValueError('Invalid source update rollback paths')
    for name in names:
        _name(name)
    return names


def remember(engine, root=None):
    """Record only source bytes the importer/build adapter has just qualified."""
    root = Path(root) if root else engine.source_root()
    entries = inventory(root, engine.check_cancel)
    marker = _read(root / 'trasc-source.json')
    _atomic(engine.work / 'sources/managed-source.json',
            {'format': FORMAT, 'profile': engine.profile, 'source': marker,
             'entries': entries, 'tree_sha256': identity(entries)})
    return entries


def remember_patch_outputs(engine, before):
    """Advance only bytes changed by the independently guarded Custom adapters.

    A build is allowed to use user-edited source, but it does not grant an
    updater permission to overwrite those edits later.
    """
    path = engine.work / 'sources/managed-source.json'
    if not path.exists():
        return  # Legacy baseline is reconstructed from its original commit.
    info = _read(path)
    root = engine.source_root()
    if info.get('source') != _read(root / 'trasc-source.json'):
        return
    expected = dict(_validated_entries(info.get('entries')))
    after = inventory(root, engine.check_cancel)
    for name in set(before) | set(after):
        if before.get(name) != after.get(name) and expected.get(name) == before.get(name):
            if name in after:
                expected[name] = after[name]
            else:
                expected.pop(name, None)
    info.update(entries=expected, tree_sha256=identity(expected))
    _atomic(path, info)


def _candidate(engine, folder, args, baseline=False):
    from engine import extract_archive, safe_path
    import takp_build
    import traditional_build
    folder.mkdir(parents=True)
    archive = folder / 'incoming.zip'
    metadata = {'imported': time.time(), 'type': 'archive'}
    if args.get('file'):
        archive = safe_path(engine.work / 'incoming', args['file'], True)
    else:
        repo = args.get('url') or engine.config['repo']
        ref = args.get('ref', engine.config.get('ref', ''))
        if not baseline and engine.profile == 'takp':
            repo, ref = takp_build.REPOSITORY, takp_build.REVISION
        elif not baseline and engine.profile == 'traditional':
            repo, ref = traditional_build.REPOSITORY, traditional_build.REVISION
        metadata.update(engine.github_download(repo, ref, archive))
        metadata['type'] = 'github'
    metadata['archive_sha256'] = _digest(archive, engine.check_cancel)
    if engine.profile == 'takp':
        import traditional_content
        traditional_content.validate_archive_members(archive)
    extracted = folder / 'extracted'
    extract_archive(archive, extracted)
    roots = [root for root in [extracted, *[p for p in extracted.iterdir() if p.is_dir()]]
             if (root / 'Release-NMS-Server/CMakeLists.txt').is_file()
             or ((root / 'CMakeLists.txt').is_file() and (root / 'zone').is_dir())]
    if len(roots) != 1:
        raise ValueError('Archive must contain one complete server source tree')
    root = roots[0]
    inventory(root, engine.check_cancel)
    if not baseline:
        if engine.profile == 'takp':
            metadata['takp'] = takp_build.qualify_source(root, engine.check_cancel)
        elif engine.profile == 'traditional':
            if (root / 'Release-NMS-Server').exists():
                raise ValueError('Choose a Traditional EQEmu server tree')
            for name, expected in traditional_build.SOURCE_HASHES.items():
                if _digest(_path(root, name), engine.check_cancel) != expected:
                    raise ValueError('Traditional update is not qualified for its build recipe: ' + name)
        elif engine.profile == 'custom':
            server = root / 'Release-NMS-Server' if (root / 'Release-NMS-Server').is_dir() else root
            for name in ('libs/luabind/CMakeLists.txt', 'submodules/fmt/CMakeLists.txt', 'submodules/libuv/CMakeLists.txt'):
                if not _path(server, name).is_file():
                    raise ValueError('Custom update lacks bundled dependency: ' + name)
    _atomic(root / 'trasc-source.json', metadata)
    if archive == folder / 'incoming.zip':
        archive.unlink()  # Extracted qualified bytes are the activation source.
    return root, metadata


def _baseline(engine, current, actual, folder):
    receipt = engine.work / 'sources/managed-source.json'
    marker = _read(current / 'trasc-source.json')
    if receipt.exists():
        info = _read(receipt)
        expected = _validated_entries(info.get('entries'))
        if (info.get('format') != FORMAT or info.get('profile') != engine.profile
                or info.get('source') != marker or info.get('tree_sha256') != identity(expected)):
            raise ValueError('Source provenance changed; keep local files and reimport the original source to establish a baseline')
        return expected
    if marker.get('type') != 'github' or not re.fullmatch('[0-9a-f]{40}', str(marker.get('commit', ''))):
        raise ValueError('This older offline import has no verified update baseline. Keep it backed up and reimport the original source ZIP first')
    engine.log('Verifying the original immutable source before calculating this update')
    root, _ = _candidate(engine, folder, {'url': marker['repo'], 'ref': marker['commit']}, baseline=True)
    expected = inventory(root, engine.check_cancel)
    if expected == actual:
        return expected
    if engine.profile == 'custom':
        import server_ferry
        import modern_bot_bridge
        server = root / 'Release-NMS-Server' if (root / 'Release-NMS-Server').is_dir() else root
        # Reproduce only independently guarded launcher-owned patches. Never
        # trust a local patch marker as authorization to ignore edited bytes.
        with contextlib.suppress(ValueError, OSError):
            server_ferry.prepare(server)
        with contextlib.suppress(modern_bot_bridge.UnsupportedSource):
            modern_bot_bridge.prepare(server, 'custom')
        expected = inventory(root, engine.check_cancel)
    return expected


def _differences(old, new):
    return {'added': sorted(new.keys() - old.keys()), 'deleted': sorted(old.keys() - new.keys()),
            'changed': sorted(name for name in old.keys() & new.keys() if old[name] != new[name])}


def _conflicts(expected, actual):
    delta = _differences(expected, actual)
    return sorted(set(delta['added'] + delta['deleted'] + delta['changed']))


def preview(engine, args):
    recover(engine)
    if engine.server_running():
        raise ValueError('Stop the server before checking source updates')
    current = engine.source_root()
    token = secrets.token_hex(16)
    folder = engine.work / 'sources' / ('update-' + token)
    try:
        candidate, metadata = _candidate(engine, folder, args)
        incoming = inventory(candidate, engine.check_cancel)
        actual = inventory(current, engine.check_cancel)
        expected = _baseline(engine, current, actual, folder / 'baseline')
        if (folder / 'baseline').exists():
            shutil.rmtree(folder / 'baseline')
        conflicts = _conflicts(expected, actual)
        changes = _differences(actual, incoming)
        affected = sorted(set(changes['added'] + changes['deleted'] + changes['changed']))
        # Refuse directory/file transitions instead of removing a directory
        # that could contain a local file not represented by this transaction.
        for name in affected:
            for parent in PurePosixPath(name).parents:
                if str(parent) != '.' and (str(parent) in actual or str(parent) in incoming):
                    raise ValueError('Source update changes a file into a directory; use a backed-up full import for this revision')
        marker = _read(current / 'trasc-source.json')
        summary = {'token': token, 'profile': engine.profile, 'from_commit': marker.get('commit'),
                   'to_commit': metadata.get('commit') or metadata.get('takp', {}).get('commit'),
                   'apply_allowed': not conflicts, 'up_to_date': not affected,
                   'counts': {kind: len(names) for kind, names in changes.items()},
                   'files': {kind: names[:200] for kind, names in changes.items()},
                   'files_truncated': any(len(names) > 200 for names in changes.values()),
                   'conflicts': conflicts[:200], 'conflict_count': len(conflicts),
                   'download_mode': 'immutable-archive',
                   'message': ('Local source edits detected; nothing has been changed' if conflicts else
                               'No source changes' if not affected else 'Source update reviewed; unchanged inputs and compiled objects will be retained')}
        info = {'format': FORMAT, 'profile': engine.profile, 'token': token, 'source': marker,
                'candidate': str(candidate.relative_to(folder)), 'new_source': metadata,
                'before': actual, 'after': incoming, 'changes': changes, 'summary': summary}
        _atomic(folder / 'preview.json', info)
        _atomic(engine.work / 'sources/update-preview.json', summary)
        for old in (engine.work / 'sources').iterdir():
            if old != folder and re.fullmatch('update-[0-9a-f]{32}', old.name) and old.is_dir() and not old.is_symlink():
                shutil.rmtree(old)
        return summary
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def _fsync_parent(path):
    descriptor = os.open(Path(path), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _mkdir_durable(path):
    missing, ancestor = [], Path(path)
    while not ancestor.exists():
        if ancestor.is_symlink():
            raise ValueError('Managed source directories cannot be symbolic links')
        missing.append(ancestor)
        ancestor = ancestor.parent
    if ancestor.is_symlink() or not ancestor.is_dir():
        raise ValueError('Managed source parent is not an ordinary directory')
    for directory in reversed(missing):
        directory.mkdir()
        _fsync_parent(directory.parent)


def _copy_verified(source, destination, expected, fresh=False):
    _mkdir_durable(destination.parent)
    temporary = destination.with_name(destination.name + '.update-' + secrets.token_hex(8))
    try:
        shutil.copy2(source, temporary)
        if temporary.stat().st_size != expected['bytes'] or _digest(temporary) != expected['sha256']:
            raise ValueError('Source changed while applying its reviewed update')
        temporary.chmod(0o755 if expected.get('executable', bool(Path(source).stat().st_mode & 0o111)) else 0o644)
        if fresh:
            # A historical archive mtime can be older than a compiled object.
            # Changed inputs must be newer, not simply preserve archive dates.
            os.utime(temporary, None)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        _fsync_parent(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _rollback(engine, journal):
    current = engine.work / 'sources/current'
    backup = engine.work / 'sources/update-backups' / journal['token']
    before = _validated_entries(journal['before'])
    source_marker = _source_marker(journal.get('source'))
    names = _affected_paths(journal.get('affected'))
    # Validate every retained preimage before the first recovery write.
    for root in (current, backup):
        _path(engine.work, root.relative_to(engine.work).as_posix())
        if not root.is_dir():
            raise ValueError('Source recovery directory is missing')
    metadata_targets = (current / 'trasc-source.json', engine.work / 'sources/managed-source.json')
    for target in metadata_targets:
        _path(engine.work, target.relative_to(engine.work).as_posix())
        if target.exists() and not target.is_file():
            raise ValueError('Source recovery metadata is not an ordinary file')
    for name in names:
        destination = _path(current, name)
        if destination.exists() and not destination.is_file():
            raise ValueError('Source recovery target is not an ordinary file')
        if name in before:
            source = _path(backup, name)
            if not source.is_file() or source.stat().st_size != before[name]['bytes'] or _digest(source) != before[name]['sha256']:
                raise ValueError('Source recovery copy changed; preserve this workspace for repair')
    for name in reversed(names):
        target = _path(current, name)
        if name in before:
            _copy_verified(_path(backup, name), target, before[name])
        else:
            target.unlink(missing_ok=True)
            if target.parent.is_dir():
                _fsync_parent(target.parent)
    _atomic(current / 'trasc-source.json', source_marker)
    _atomic(engine.work / 'sources/managed-source.json', {'format': FORMAT, 'profile': engine.profile,
            'source': source_marker, 'entries': before, 'tree_sha256': identity(before)})


def recover(engine):
    recover_custom_stage(engine)
    path = engine.work / 'run/source-update.json'
    if not path.exists():
        return
    value = _read(path)
    if (value.get('format') != FORMAT or value.get('profile') != engine.profile
            or not re.fullmatch('[0-9a-f]{32}', str(value.get('token', '')))
            or value.get('phase') not in ('applying', 'committed')):
        raise ValueError('Invalid source recovery journal; preserve this workspace for repair')
    _source_marker(value.get('source'))
    _validated_entries(value.get('before'))
    _affected_paths(value.get('affected'))
    if value['phase'] != 'committed':
        _rollback(engine, value)
        engine.log('Recovered the source files from an interrupted update; deployed binaries were preserved')
    path.unlink()
    _fsync_parent(path.parent)


def recover_custom_stage(engine):
    """Restore the previous successful stage if process death interrupts swap."""
    path = engine.work / 'run/custom-build-stage.json'
    if not path.exists():
        return
    value = _read(path)
    if (engine.profile != 'custom' or value.get('format') != FORMAT
            or value.get('phase') not in ('applying', 'committed')
            or not isinstance(value.get('previous'), bool)
            or not re.fullmatch('bin.custom-preparing-[0-9a-f]{16}', str(value.get('prepared', '')))
            or not re.fullmatch('bin.staged-retained-[0-9a-f]{16}', str(value.get('retained', '')))):
        raise ValueError('Invalid Custom stage recovery receipt')
    current = _path(engine.work, 'server/bin.staged')
    prepared = _path(engine.work, 'server/' + value['prepared'])
    retained = _path(engine.work, 'server/' + value['retained'])
    for directory in (current, prepared, retained):
        if directory.exists() and not directory.is_dir():
            raise ValueError('Custom stage recovery path is not a directory')
    if value['phase'] != 'committed':
        if value['previous']:
            if retained.exists():
                if current.exists():
                    if prepared.exists():
                        raise ValueError('Ambiguous Custom stage recovery state')
                    os.replace(current, prepared)
                os.replace(retained, current)
            elif not current.exists():
                raise ValueError('Previous Custom staged build cannot be located')
        elif current.exists():
            if prepared.exists():
                raise ValueError('Ambiguous Custom stage recovery state')
            os.replace(current, prepared)
        _fsync_parent(engine.work / 'server')
    path.unlink()
    _fsync_parent(path.parent)


def promote_custom_stage(engine, prepared):
    recover_custom_stage(engine)
    current = _path(engine.work, 'server/bin.staged')
    prepared = _path(engine.work, str(Path(prepared).relative_to(engine.work)))
    retained = _path(engine.work, 'server/bin.staged-retained-' + secrets.token_hex(8))
    journal = engine.work / 'run/custom-build-stage.json'
    value = {'format': FORMAT, 'phase': 'applying', 'prepared': prepared.name,
             'retained': retained.name, 'previous': current.exists()}
    _fsync_parent(prepared)
    _fsync_parent(prepared.parent)
    _atomic(journal, value)
    try:
        if current.exists():
            os.replace(current, retained)
            _fsync_parent(current.parent)
        os.replace(prepared, current)
        _fsync_parent(current.parent)
        _atomic(journal, dict(value, phase='committed'))
    except BaseException:
        recover_custom_stage(engine)
        raise
    journal.unlink()
    _fsync_parent(journal.parent)


def apply(engine, args):
    recover(engine)
    if engine.server_running():
        raise ValueError('Stop the server before applying source updates')
    token = str(args.get('token', ''))
    if not re.fullmatch('[0-9a-f]{32}', token):
        raise ValueError('Check source updates first and use its reviewed token')
    folder = engine.work / 'sources' / ('update-' + token)
    info = _read(folder / 'preview.json')
    if info.get('format') != FORMAT or info.get('profile') != engine.profile or info.get('token') != token:
        raise ValueError('This source preview belongs to a different profile')
    if not info['summary']['apply_allowed']:
        raise ValueError('Local source edits must be preserved; this update cannot overwrite them')
    _source_marker(info.get('source'))
    _source_marker(info.get('new_source'))
    before, after = _validated_entries(info['before']), _validated_entries(info['after'])
    current = engine.source_root()
    if inventory(current, engine.check_cancel) != before or _read(current / 'trasc-source.json') != info['source']:
        raise ValueError('Source changed after review; check the update again')
    candidate = _path(folder, info['candidate'])
    if inventory(candidate, engine.check_cancel) != after:
        raise ValueError('Downloaded source changed after review; check the update again')
    if engine.profile == 'takp':
        import takp_build
        qualified = takp_build.qualify_source(candidate, engine.check_cancel)
        if info['new_source'].get('takp') != qualified:
            raise ValueError('The reviewed TAKP revision does not match this application release')
    elif engine.profile == 'traditional':
        import traditional_build
        for name, expected in traditional_build.SOURCE_HASHES.items():
            if _digest(_path(candidate, name), engine.check_cancel) != expected:
                raise ValueError('The reviewed Traditional source does not match this build recipe')
    changes = _differences(before, after)
    affected = sorted(set(changes['added'] + changes['deleted'] + changes['changed']))
    backup = engine.work / 'sources/update-backups' / token
    if backup.exists():
        raise ValueError('This reviewed source update has already been applied')
    _mkdir_durable(backup)
    needed = sum(before.get(name, {}).get('bytes', 0) + after.get(name, {}).get('bytes', 0) for name in affected)
    if shutil.disk_usage(backup).free < needed + 256 * 1024**2:
        raise ValueError('Not enough free space for the reversible source update')
    for name in affected:
        engine.check_cancel()
        if name in before:
            _copy_verified(_path(current, name), _path(backup, name), before[name])
    _atomic(backup / 'recovery.json', {'format': FORMAT, 'source': info['source'], 'before': before, 'affected': affected})
    engine.check_cancel()
    if inventory(current, engine.check_cancel) != before or _read(current / 'trasc-source.json') != info['source']:
        raise ValueError('Source changed while its recovery copy was prepared; check the update again')
    journal_path = engine.work / 'run/source-update.json'
    journal = {'format': FORMAT, 'profile': engine.profile, 'token': token, 'phase': 'applying',
               'source': info['source'], 'before': before, 'affected': affected}
    _atomic(journal_path, journal)
    _fsync_parent(journal_path.parent)
    try:
        # Activation is deliberately noncancellable after the durable journal;
        # failures restore all previous inputs before returning.
        for name in affected:
            destination = _path(current, name)
            if name in after:
                _copy_verified(_path(candidate, name), destination, after[name], fresh=True)
            else:
                destination.unlink()
                _fsync_parent(destination.parent)
        if inventory(current) != after:
            raise ValueError('Activated source does not match the reviewed update; restoring prior source')
        _atomic(current / 'trasc-source.json', info['new_source'])
        _atomic(engine.work / 'sources/managed-source.json', {'format': FORMAT, 'profile': engine.profile,
                'source': info['new_source'], 'entries': after, 'tree_sha256': identity(after)})
        journal['phase'] = 'committed'
        _atomic(journal_path, journal)
        _fsync_parent(journal_path.parent)
    except BaseException:
        _rollback(engine, journal)
        journal_path.unlink(missing_ok=True)
        raise
    journal_path.unlink()
    _fsync_parent(journal_path.parent)
    if info['new_source'].get('repo'):
        engine.config.update(repo=info['new_source']['repo'], ref=info['new_source']['ref'])
        engine.save()
    result = dict(info['summary'], applied=True, recovery_copy=str(backup.relative_to(engine.work)),
                  message='Source update applied. Compile incrementally, then deploy the verified build; running data and previous binaries are preserved')
    _atomic(engine.work / 'sources/update-preview.json', result)
    return result


def status(engine):
    import takp_build
    import traditional_build
    target = takp_build.REVISION if engine.profile == 'takp' else traditional_build.REVISION if engine.profile == 'traditional' else engine.config.get('ref', 'main')
    result = {'profile': engine.profile, 'target_revision': target, 'download_mode': 'immutable-archive',
              'source_available': (engine.work / 'sources/current/trasc-source.json').is_file(),
              'recovery_required': (engine.work / 'run/source-update.json').exists()}
    for kind, directory in (('deployed_revision', 'server/bin'), ('staged_revision', 'server/bin.staged')):
        result[kind] = None
        with contextlib.suppress(OSError, ValueError, TypeError):
            info = _read(engine.work / directory / 'build-info.json')
            result[kind] = info.get('source', {}).get('commit')
    result['update_build_ready'] = staged_ready(engine)
    result.update(cache_status(engine))
    with contextlib.suppress(OSError, ValueError, TypeError):
        value = _read(engine.work / 'sources/update-preview.json')
        if value.get('profile') == engine.profile:
            result['preview'] = value
    return result


def cache_status(engine):
    """Explain reuse/fallback before a potentially expensive build is selected."""
    result = {'cache_reusable': False, 'requires_fresh_build': False,
              'cache_message': 'Import server source and install the build runtime first'}
    try:
        root = engine.source_root()
        trusted = False
        if engine.profile == 'takp':
            import takp_build
            runtime = takp_build.runtime(engine)
            if not runtime['ready']:
                result['cache_message'] = runtime['message']
                return result
            directory = takp_build.build_directory(engine)
            options, recipe = takp_build.BUILD_OPTIONS, takp_build.RECIPE
            source = root
            with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
                takp_build.record(engine, 'server/bin')
                trusted = True
        elif engine.profile == 'traditional':
            import traditional_build
            import traditional_runtime
            runtime = traditional_build._runtime(engine)
            if not runtime['ready']:
                result['cache_message'] = runtime['message']
                return result
            directory = engine.work / 'builds/traditional/objects'
            source = engine.work / 'builds/traditional/source'
            options = (*traditional_build.BUILD_OPTIONS, '-DTRASC_WEBSOCKETPP_INCLUDE_DIR=' + str(source / 'submodules/websocketpp'))
            recipe = traditional_build.RECIPE
            with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
                traditional_runtime._record(engine, 'server/bin')
                trusted = True
        else:
            source = root / 'Release-NMS-Server' if (root / 'Release-NMS-Server').is_dir() else root
            options = ('-DCMAKE_BUILD_TYPE=Release', '-DEQEMU_BUILD_LOGIN=ON', '-DEQEMU_BUILD_SERVER=ON',
                       '-DEQEMU_BUILD_CLIENT_FILES=ON', '-DEQEMU_PREFER_LUA=ON', '-DLUA_INCLUDE_DIR=/usr/include/lua5.1',
                       '-DLUA_LIBRARY=/usr/lib/aarch64-linux-gnu/liblua5.1.so')
            runtime, recipe = {'identity': custom_runtime_identity(engine)}, 'custom-ninja-v1'
            directory = engine.work / 'builds/current'
            pointer = engine.work / 'builds/custom-cache.json'
            if pointer.exists():
                name = _read(pointer).get('directory', '')
                if not re.fullmatch(r'current(?:-[0-9a-f]{12})?', str(name)):
                    raise ValueError('Invalid Custom compiler-cache receipt')
                directory = engine.work / 'builds' / name
        result['cache_directory'] = str(directory.relative_to(engine.work))
        if not (directory / 'CMakeCache.txt').exists():
            result['cache_message'] = 'No compiler cache is installed; the first build compiles all required targets'
            return result
        compatibility = cache_identity(engine.profile, runtime['identity'], recipe, source, options)
        marker = directory / 'incremental-cache.json'
        if marker.exists():
            value = _read(marker)
            reusable = value.get('format') == FORMAT and value.get('identity') == compatibility
        else:
            reusable = trusted
        reusable = reusable and _cache_matches(directory, source, options)
        result.update(cache_reusable=bool(reusable), requires_fresh_build=not reusable,
                      cache_message=('Verified compatible Ninja cache; unchanged objects will be reused' if reusable else
                                     'The older cache cannot prove this compiler/runtime/recipe. Build once with a fresh cache; the old cache and installed binaries are preserved'))
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        result.update(requires_fresh_build=False, cache_message=str(error))
    return result


def _stat_tree(root):
    result = []
    for directory, children, files in os.walk(root, followlinks=False):
        children[:] = sorted(name for name in children if name != '.git')
        for name in children + sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative == 'trasc-source.json':
                continue
            info = path.lstat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError('Source changed to a symlink or special file')
            result.append((relative, info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                           info.st_ctime_ns, info.st_mode))
            if len(result) > 2 * MAX_FILES:
                raise ValueError('Source stat inventory exceeds its bound')
    return hashlib.sha256(json.dumps(result, separators=(',', ':')).encode()).hexdigest()


def source_identity_cached(engine):
    root = engine.source_root()
    signature = _stat_tree(root)
    cached = getattr(engine, '_update_source_cache', None)
    if cached and cached[0] == signature:
        return cached[1]
    fingerprint = identity(inventory(root, engine.check_cancel))
    if _stat_tree(root) != signature:
        raise ValueError('Source changed during qualification')
    engine._update_source_cache = (signature, fingerprint)
    return fingerprint


def staged_ready(engine):
    """Durable eligibility for Deploy updated build, including source edits."""
    try:
        if engine.profile == 'takp':
            import takp_build
            info = takp_build.record(engine)
            return bool(info.get('input_sha256') and info['input_sha256'] == source_identity_cached(engine))
        if engine.profile == 'traditional':
            import traditional_build
            _, _, source = traditional_build._guard_source(engine)
            runtime = traditional_build._runtime(engine)
            return bool(runtime['ready'] and traditional_build._staged(engine, source, runtime['identity'])[0])
        from engine import BINARIES
        stage = engine.work / 'server/bin.staged'
        info = _read(stage / 'build-info.json')
        if (set(info.get('binaries', {})) != set(BINARIES)
                or info.get('source') != _read(engine.source_root() / 'trasc-source.json')
                or info.get('source_tree_sha256') != source_identity_cached(engine)
                or info.get('runtime_identity') != custom_runtime_identity(engine)):
            return False
        signature = tuple((name, (stage / name).stat().st_size, (stage / name).stat().st_mtime_ns,
                           (stage / name).stat().st_ctime_ns) for name in BINARIES)
        key = (signature, json.dumps(info, sort_keys=True))
        if getattr(engine, '_update_binary_cache', None) != key:
            for name in BINARIES:
                if _path(stage, name).is_symlink() or _digest(stage / name, engine.check_cancel) != info['binaries'][name]:
                    return False
            engine._update_binary_cache = key
        return True
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return False


def cache_identity(profile, runtime_identity, recipe, source, options):
    return hashlib.sha256(json.dumps({'profile': profile, 'runtime': runtime_identity, 'recipe': recipe,
            'source': str(source), 'options': list(options), 'generator': 'Ninja'}, sort_keys=True).encode()).hexdigest()


def custom_runtime_identity(engine=None):
    """Fingerprint the actual app-owned compiler and relevant runtime inputs."""
    values, stamps = {}, {}
    for name in ('/usr/bin/g++', '/usr/bin/cmake', '/usr/bin/ninja', '/var/lib/dpkg/status',
                 '/usr/lib/aarch64-linux-gnu/liblua5.1.so', '/etc/trasc-runtime.json'):
        path = Path(name)
        if path.exists():
            info = path.stat()
            stamps[name] = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
    signature = hashlib.sha256(json.dumps(stamps, sort_keys=True).encode()).hexdigest()
    cached = getattr(engine, '_custom_compiler_cache', None)
    if cached and cached[0] == signature:
        return cached[1]
    for command in (('/usr/bin/g++', '-dumpfullversion'), ('/usr/bin/g++', '-dumpmachine'), ('/usr/bin/cmake', '--version')):
        values[' '.join(command)] = subprocess.check_output(command, text=True, timeout=30,
                                                             stderr=subprocess.STDOUT).strip()
    if 'aarch64' not in values['/usr/bin/g++ -dumpmachine']:
        raise ValueError('Server updates require the app-owned ARM64 compiler runtime')
    values.update(stamps)
    result = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    if engine is not None:
        engine._custom_compiler_cache = (signature, result)
    return result


def _cache_values(directory):
    cache = Path(directory) / 'CMakeCache.txt'
    if cache.is_symlink() or not cache.is_file() or cache.stat().st_size > 2 * 1024**2:
        raise ValueError('Build cache is missing or oversized')
    result = {}
    for line in cache.read_text().splitlines():
        if line and not line.startswith(('#', '//')) and '=' in line and ':' in line.split('=', 1)[0]:
            name = line.split(':', 1)[0]
            result[name] = line.split('=', 1)[1]
    return result


def _cache_matches(directory, source, options):
    values = _cache_values(directory)
    if (values.get('CMAKE_HOME_DIRECTORY') != str(source)
            or values.get('CMAKE_CACHEFILE_DIR') != str(directory)
            or values.get('CMAKE_GENERATOR') != 'Ninja'):
        return False
    compiler = values.get('CMAKE_CXX_COMPILER')
    if not compiler or Path(compiler).resolve() != Path('/usr/bin/g++').resolve():
        return False
    for option in options:
        if option.startswith('-D') and '=' in option:
            key, value = option[2:].split('=', 1)
            if values.get(key) != value:
                return False
    if any(values.get(name, '') for name in ('CMAKE_TOOLCHAIN_FILE', 'CMAKE_CXX_FLAGS', 'CMAKE_C_FLAGS',
                                              'CMAKE_EXE_LINKER_FLAGS', 'CMAKE_SHARED_LINKER_FLAGS')):
        return False
    return True


def ensure_cache(engine, directory, expected, source, options=(), receipt='incremental-cache.json', incremental=False, trusted_legacy=False):
    """Never delete an incompatible cache or a successful build receipt."""
    directory = Path(directory)
    _path(engine.work, directory.relative_to(engine.work).as_posix())
    marker = _path(directory, receipt)
    if marker.exists():
        stored = _read(marker)
        if (stored.get('format') != FORMAT or stored.get('identity') != expected
                or ((directory / 'CMakeCache.txt').exists() and not _cache_matches(directory, source, options))):
            raise ValueError('Build cache uses a different runtime, compiler or recipe. Keep it preserved and use Original setup → clean build in a new cache')
    elif (directory / 'CMakeCache.txt').exists():
        if not trusted_legacy or not _cache_matches(directory, source, options):
            raise ValueError('This older cache cannot be verified against its runtime/compiler/recipe. It is preserved; use a clean build in a new cache')
        engine.log('Adopting the compatible existing Ninja cache; previous binaries and build receipts are retained')
    elif incremental:
        engine.log('No reusable compiler cache is installed; the first build will compile all required targets')
    directory.mkdir(parents=True, exist_ok=True)
    _atomic(marker, {'format': FORMAT, 'identity': expected, 'source': str(source), 'created': time.time()})


def reconcile(engine, source, destination, old, new):
    """Apply a qualified overlay delta without changing unchanged input times.

    The caller first validates the complete old overlay and its recipe receipt.
    Recovery has already left the previous staged/deployed binary sets intact;
    overlay failures discard no compiler objects and remain visibly invalid.
    """
    for name in _differences(old, new)['deleted']:
        engine.check_cancel()
        _path(destination, name).unlink()
    changes = _differences(old, new)
    for name in changes['added'] + changes['changed']:
        engine.check_cancel()
        _copy_verified(_path(source, name), _path(destination, name), new[name], fresh=True)
