"""Independent EQEmu content directories; never install or run archive scripts."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import time

KINDS = ('quests', 'plugins', 'lua_modules', 'assets')
MARKER = '.trasc-content.json'


def paths(engine, kind):
    from engine import safe_path
    if kind not in KINDS:
        raise ValueError('Choose quests, plugins, Lua modules or server assets')
    for name in ('server', 'backups', 'backups/content', 'run'):
        p = engine.work / name
        if p.is_symlink():
            raise ValueError('Content directories cannot be symbolic links')
    if (engine.work / 'server' / kind).is_symlink():
        raise ValueError('Content directory cannot be a symbolic link')
    target = safe_path(engine.work, 'server/' + kind)
    return target, engine.work / 'run' / ('content-' + kind + '.json')


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
    if (root / kind).is_dir():
        root = root / kind
    files = [p for p in root.rglob('*') if p.is_file()]
    relative = [p.relative_to(root) for p in files]
    if kind == 'quests':
        valid = any(len(p.parts) >= 2 and p.parts[0] not in KINDS and p.suffix.lower() in ('.pl', '.lua') for p in relative)
    elif kind == 'plugins':
        valid = any(p.suffix.lower() in ('.pl', '.pm') for p in relative)
    elif kind == 'lua_modules':
        valid = any(p.suffix.lower() == '.lua' for p in relative)
    else:
        valid = any(p.name.lower() == 'patch_rof2.conf' for p in relative)
    if not valid:
        raise ValueError({'quests': 'Quest ZIP needs zone/global folders containing .pl or .lua scripts',
                          'plugins': 'Plugin ZIP needs Perl .pl or .pm files',
                          'lua_modules': 'Lua modules ZIP needs .lua files',
                          'assets': 'Server assets ZIP needs patch_RoF2.conf; import server assets, not client game files'}[kind])
    return root


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
    prepared = stage / 'prepared'
    metadata = {'kind': kind, 'profile': 'traditional', 'transaction': transaction, 'imported': time.time()}
    try:
        if args.get('url'):
            archive = engine.work / 'incoming' / (kind + '-download.zip')
            metadata.update(engine.github_download(args['url'], args.get('ref', ''), archive))
        else:
            archive = safe_path(engine.work / 'incoming', args['file'], True)
        with archive.open('rb') as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                engine.check_cancel()
                digest.update(block)
        metadata['archive_sha256'] = digest.hexdigest()
        extract_archive(archive, stage / 'unpacked')
        root = content_root(stage / 'unpacked', kind)
        prepared.mkdir(parents=True)
        count = 0
        for source in root.iterdir():
            engine.check_cancel()
            # Plugins and Lua modules have their own explicit import controls.
            if source.name in ('.git', '__MACOSX', MARKER) or (kind == 'quests' and source.name in ('plugins', 'lua_modules', 'assets')):
                continue
            destination = prepared / source.name
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
        for p in prepared.rglob('*'):
            if p.is_file():
                count += 1
        metadata['files'] = count
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


def status(engine):
    result = {}
    for kind in KINDS:
        target = engine.work / 'server' / kind
        marker = target / MARKER
        metadata = None
        try:
            if marker.is_file() and marker.stat().st_size < 16384:
                metadata = json.loads(marker.read_text())
        except (ValueError, OSError):
            pass
        result[kind] = {'imported': bool(metadata and metadata.get('profile') == 'traditional'),
                        'path': 'server/' + kind, 'source': metadata}
    return {'components': result, 'compilation_ready': False,
            'message': 'Content preparation only. Android compilation, deployment and first login validation are the next milestone.'}
