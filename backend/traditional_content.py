"""Independent EQEmu content directories; never install or run archive scripts."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import tarfile
import time
import zipfile

KINDS = ('quests', 'plugins', 'lua_modules', 'assets')
MARKER = '.trasc-content.json'


def paths(engine, kind):
    from engine import safe_path
    if kind not in KINDS:
        raise ValueError('Choose quests, plugins, Lua modules or server assets')
    for name in ('incoming', 'server', 'backups', 'backups/content', 'run'):
        p = engine.work / name
        if p.is_symlink():
            raise ValueError('Content directories cannot be symbolic links')
    if (engine.work / 'server' / kind).is_symlink():
        raise ValueError('Content directory cannot be a symbolic link')
    target = safe_path(engine.work, 'server/' + kind)
    journal = engine.work / 'run' / ('content-' + kind + '.json')
    if journal.is_symlink():
        raise ValueError('Content journal cannot be a symbolic link')
    return target, journal


def recover(engine):
    """A committed marker wins; otherwise put the previous directory back."""
    from engine import safe_path
    for kind in KINDS:
        target, journal = paths(engine, kind)
        if not journal.exists():
            continue
        transaction = json.loads(journal.read_text())
        backup = safe_path(engine.work / 'backups/content', transaction['backup'])
        current = target / MARKER
        committed = current.is_file() and json.loads(current.read_text()).get('transaction') == transaction['id']
        if not committed:
            if backup.exists() and not target.exists():
                os.replace(backup, target)
            elif backup.exists() or (transaction['previous'] and not target.exists()):
                raise ValueError('Interrupted content import needs recovery: ' + kind)
        journal.unlink()


def content_root(stage, kind):
    # Accept a component ZIP or a GitHub wrapper, including a component inside
    # a quests repository. Do not mistake zone folders for wrapper directories.
    root = stage
    entries = [p for p in root.iterdir() if p.name != '__MACOSX']
    if len(entries) == 1 and entries[0].is_dir() and not (kind == 'quests' and any(p.is_file() and p.suffix.lower() in ('.pl', '.lua') for p in entries[0].iterdir())):
        root = entries[0]
    if kind == 'assets':
        # Keep the repository root available for the separate login opcode
        # files. prepare_assets selects only the known runtime config files.
        assets_plan(root)
        return root
    component_roots = [p for p in (root / kind, root / 'quests' / kind)
                       if p.is_dir()]
    if len(component_roots) > 1:
        raise ValueError('Archive contains more than one ' + kind + ' directory')
    explicit = bool(component_roots) or root.name == kind
    if component_roots:
        root = component_roots[0]
    files = [p for p in root.rglob('*') if p.is_file()]
    relative = [p.relative_to(root) for p in files]
    if kind == 'quests':
        valid = any(len(p.parts) >= 2 and p.parts[0] not in KINDS and p.suffix.lower() in ('.pl', '.lua') for p in relative)
    elif kind == 'plugins':
        valid = any(p.suffix.lower() in ('.pl', '.pm') and
                    (explicit or len(p.parts) == 1) for p in relative)
    elif kind == 'lua_modules':
        valid = any(p.suffix.lower() == '.lua' and
                    (explicit or len(p.parts) == 1) for p in relative)
    if not valid:
        raise ValueError({'quests': 'Quest ZIP needs zone/global folders containing .pl or .lua scripts',
                          'plugins': 'Plugin ZIP needs a plugins directory or top-level Perl .pl or .pm files',
                          'lua_modules': 'Lua modules ZIP needs a lua_modules directory or top-level .lua files',
                          'assets': 'Server assets ZIP needs patch_RoF2.conf; import server assets, not client game files'}[kind])
    return root


def assets_plan(root):
    """Normalize EQEmu source/asset archives to PathManager's two directories."""
    patch_dirs = [p for p in (root / 'utils/patches', root / 'assets/patches',
                              root / 'assets/opcodes', root / 'patches',
                              root / 'opcodes', root / 'assets', root)
                  if (p / 'patch_RoF2.conf').is_file()]
    if not patch_dirs:
        raise ValueError('Server assets ZIP needs patch_RoF2.conf; import server assets, not client game files')
    if len(patch_dirs) != 1:
        raise ValueError('Server assets ZIP contains more than one RoF2 patches directory')
    patch_dir = patch_dirs[0]
    selected = {}
    for source in patch_dir.iterdir():
        if source.is_file() and re.fullmatch(r'patch_[A-Za-z0-9_-]+\.conf', source.name):
            selected['patches/' + source.name] = source
    opcode_dirs = list(dict.fromkeys((root / 'utils/patches', root / 'assets/opcodes',
                                     root / 'opcodes', patch_dir, root,
                                     root / 'loginserver/login_util')))
    for filename in ('opcodes.conf', 'mail_opcodes.conf', 'login_opcodes.conf',
                     'login_opcodes_sod.conf', 'login_opcodes_larion.conf'):
        sources = [p / filename for p in opcode_dirs if (p / filename).is_file()]
        if len(sources) > 1:
            raise ValueError('Server assets ZIP contains duplicate ' + filename + ' files')
        if sources:
            selected['opcodes/' + filename] = sources[0]
    # A server source archive must provide its complete runtime opcode set.
    # Existing component ZIPs containing only patches remain importable.
    if patch_dir == root / 'utils/patches' and any(
            'opcodes/' + name not in selected for name in ('opcodes.conf', 'mail_opcodes.conf')):
        raise ValueError('Server source assets need opcodes.conf and mail_opcodes.conf alongside patch_RoF2.conf')
    for directory in dict.fromkeys((root, root / 'assets', patch_dir)):
        for filename in ('LICENSE', 'LICENSE.md', 'LICENSE.txt', 'COPYING'):
            source = directory / filename
            if source.is_file() and filename not in selected:
                selected[filename] = source
    return selected


def validate_archive_members(archive):
    """Reject overwritten members before extraction can hide ambiguity."""
    seen = {}
    def member(name, is_directory):
        key = str(PurePosixPath(name))
        if key in seen and not (is_directory and seen[key]):
            raise ValueError('Content archive contains duplicate paths: ' + key)
        seen[key] = is_directory
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                member(entry.filename, entry.is_dir())
    else:
        with tarfile.open(archive, 'r:*') as source:
            for entry in source:
                member(entry.name, entry.isdir())


def prepare_content(engine, root, kind, prepared, metadata):
    prepared.mkdir(parents=True)
    if kind == 'assets':
        selected = assets_plan(root)
        for name, source in selected.items():
            engine.check_cancel()
            destination = prepared / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        metadata['source_paths'] = [str(p.relative_to(root)) for p in selected.values()]
        metadata['asset_layout'] = {'patches': 'assets/patches', 'opcodes': 'assets/opcodes'}
        metadata['opcodes_ready'] = all('opcodes/' + name in selected for name in
                                      ('opcodes.conf', 'mail_opcodes.conf', 'login_opcodes.conf',
                                       'login_opcodes_sod.conf'))
        return
    for source in root.iterdir():
        engine.check_cancel()
        # ProjectEQ ships plugins and Lua modules alongside its zone quests.
        # Keep those directories together so one quest import updates all three.
        if source.name in ('.git', '__MACOSX', MARKER) or (kind == 'quests' and source.name == 'assets'):
            continue
        destination = prepared / source.name
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


def install(engine, args):
    from engine import atomic_json, extract_archive, safe_path
    if engine.profile != 'traditional':
        raise ValueError('Traditional content imports belong to the Traditional EQEmu profile')
    if engine.server_running():
        raise ValueError('Stop the server before replacing content')
    kind = args.get('kind')
    target, journal = paths(engine, kind)
    recover(engine)
    if target.exists() and not args.get('replace', False):
        raise ValueError('Select Replace this component to preserve a backup and replace its directory')
    transaction = secrets.token_hex(12)
    stage = engine.work / ('content-import-' + transaction)
    if stage.exists() or stage.is_symlink():
        raise ValueError('Content import staging directory already exists')
    prepared = stage / 'prepared'
    metadata = {'kind': kind, 'profile': 'traditional', 'transaction': transaction, 'imported': time.time()}
    try:
        if args.get('url'):
            archive = engine.work / 'incoming' / (kind + '-download.zip')
            if archive.is_symlink():
                raise ValueError('Downloaded content archive cannot be a symbolic link')
            metadata.update(engine.github_download(args['url'], args.get('ref', ''), archive))
        else:
            filename = str(args.get('file', ''))
            if filename.startswith('incoming/'):
                filename = filename[len('incoming/'):]
            if not filename or len(PurePosixPath(filename).parts) != 1:
                raise ValueError('Choose a content archive from incoming files')
            if (engine.work / 'incoming' / filename).is_symlink():
                raise ValueError('Content archive cannot be a symbolic link')
            archive = safe_path(engine.work / 'incoming', filename, True)
            if not archive.is_file():
                raise ValueError('Choose a content archive file')
        with archive.open('rb') as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                engine.check_cancel()
                digest.update(block)
        metadata['archive_sha256'] = digest.hexdigest()
        validate_archive_members(archive)
        extract_archive(archive, stage / 'unpacked')
        root = content_root(stage / 'unpacked', kind)
        metadata['source_path'] = str(root.relative_to(stage / 'unpacked'))
        prepare_content(engine, root, kind, prepared, metadata)
        metadata['files'] = sum(1 for p in prepared.rglob('*') if p.is_file())
        atomic_json(prepared / MARKER, metadata)
        engine.check_cancel()
        backup_name = kind + '-' + transaction
        backup = engine.work / 'backups/content' / backup_name
        backup.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(journal, {'id': transaction, 'backup': backup_name, 'previous': target.exists()})
        try:
            if target.exists():
                os.replace(target, backup)
            os.replace(prepared, target)
        except Exception:
            recover(engine)
            raise
        journal.unlink()
        return {'message': kind.replace('_', ' ').title() + ' imported into Traditional EQEmu.',
                'component': metadata, 'backup': str(backup.relative_to(engine.work)) if backup.exists() else None}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _source_metadata(target):
    marker = target / MARKER
    try:
        if not marker.is_symlink() and marker.is_file() and marker.stat().st_size < 16384:
            metadata = json.loads(marker.read_text())
            if isinstance(metadata, dict) and metadata.get('profile') == 'traditional':
                return metadata
    except (ValueError, OSError):
        pass
    return None


def _directory_status(engine, relative, suffixes=()):
    """Detect usable installed files without following any symbolic links."""
    target = engine.work
    try:
        for name in PurePosixPath(relative).parts:
            target = target / name
            if target.is_symlink():
                return {'present': False, 'files': 0, 'scripts': 0, 'safe': False}
        if not target.is_dir():
            return {'present': False, 'files': 0, 'scripts': 0, 'safe': True}
        if not suffixes:
            # A full quests tree can have tens of thousands of files. Its
            # import marker already holds its count; only helpers need a scan.
            return {'present': True, 'files': 0, 'scripts': 0, 'safe': True}
        files = scripts = 0
        def inaccessible(error):
            raise error
        for directory, directories, filenames in os.walk(target, followlinks=False, onerror=inaccessible):
            root = Path(directory)
            if any((root / name).is_symlink() for name in directories + filenames):
                return {'present': True, 'files': 0, 'scripts': 0, 'safe': False}
            for name in filenames:
                if name == MARKER:
                    continue
                files += 1
                scripts += Path(name).suffix.lower() in suffixes
        return {'present': True, 'files': files, 'scripts': scripts, 'safe': True}
    except OSError:
        return {'present': False, 'files': 0, 'scripts': 0, 'safe': False}


def components(engine):
    """Prefer helpers in the pulled quests tree; retain legacy standalone ones."""
    result = {}
    for kind in ('quests', 'assets'):
        path = 'server/' + kind
        detected = _directory_status(engine, path)
        metadata = _source_metadata(engine.work / path) if detected['safe'] else None
        if metadata:
            detected['files'] = metadata.get('files', 0)
        result[kind] = dict(detected, imported=bool(metadata and detected['present']),
                            path=path, source=metadata)
    for kind, suffixes in (('plugins', ('.pl', '.pm')), ('lua_modules', ('.lua',))):
        quests_path = 'server/quests/' + kind
        embedded = _directory_status(engine, quests_path, suffixes)
        legacy_path = 'server/' + kind
        legacy = _directory_status(engine, legacy_path, suffixes)
        if embedded['scripts']:
            path, detected, origin, metadata = quests_path, embedded, 'quests', result['quests']['source']
        elif legacy['scripts']:
            path, detected, origin = legacy_path, legacy, 'standalone'
            metadata = _source_metadata(engine.work / path)
        else:
            path, detected, origin, metadata = quests_path, embedded, 'missing', result['quests']['source']
        result[kind] = dict(detected, imported=bool(detected['scripts']), path=path,
                            source=metadata, origin=origin, quests_path=quests_path,
                            quests_present=embedded['present'])
    return result


def status(engine):
    import traditional_build
    import traditional_runtime
    result = components(engine)
    build = traditional_build.status(engine)
    deployment = traditional_runtime.status(engine, build)
    return {'components': result, 'compilation_ready': build['build_allowed'], 'build': build,
            'deployment': deployment, 'message': deployment['message']}
