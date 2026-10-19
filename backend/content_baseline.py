"""Durable imported-content fingerprints; never assert remote freshness.

Capture is called only by explicit import operations, before activation where
possible. Inspection is read-only. The sidecar is tied to the import marker by
its SHA-256, so restoring content without its matching receipts fails closed.
"""
import json
import os
import secrets
import shutil
import stat
from pathlib import Path
import re

import custom_deployment as files

NAME = '.trasc-content-baseline.json'
MAPS_MARKER = '.trasc-maps-import.json'
MARKERS = (NAME, MAPS_MARKER, '.trasc-content.json', '.trasc-takp-content.json', '.git', '__MACOSX')
MAX_RECEIPT = 48 * 1024**2


def _source(metadata):
    return {key: value for key, value in metadata.items() if key != 'baseline_sha256'}


def _progress(engine, phase):
    files.progress(engine, phase, message='Verifying imported content; hashing files may take time for large map sets.')


def inventory(engine, root, folders=None):
    """Use the same bounded, cancellable, link-refusing hash reader as sync."""
    _progress(engine, 'content_baseline_inventory')
    if folders is None:
        entries = files.inventory(engine, root, MARKERS)
    else:
        entries = {}
        for folder in folders:
            for name, item in files.inventory(engine, Path(root) / folder, MARKERS).items():
                entries[folder + '/' + name] = item
    if not entries:
        raise ValueError('Cannot fingerprint empty imported content')
    if len(entries) > files.MAX_FILES:
        raise ValueError('Imported content exceeds the fingerprint file limit')
    result = {}
    for name, item in entries.items():
        files.check(engine)
        if item.get('error'):
            raise ValueError('Cannot fingerprint imported content: ' + name + ': ' + item['error'])
        result[name] = {'bytes': item['bytes'], 'sha256': item['sha256']}
    if sum(item['bytes'] for item in result.values()) > files.MAX_BYTES:
        raise ValueError('Imported content exceeds the fingerprint byte limit')
    return result


def capture(engine, root, kind, metadata, entries=None):
    """Write a complete fingerprint; caller activates it with the source marker."""
    root = files.confined(engine, root)
    entries = inventory(engine, root) if entries is None else entries
    value = {'format': 1, 'profile': engine.profile, 'kind': kind,
             'source': _source(metadata), 'entries': entries,
             'tree_sha256': files.identity(entries)}
    files.check(engine)
    if len(json.dumps(value).encode()) > MAX_RECEIPT:
        raise ValueError('Content fingerprint receipt exceeds its size limit')
    files.atomic(engine, root / NAME, value)
    # Link the small import receipt to this exact complete file manifest.
    metadata['baseline_sha256'] = files.identity(value)
    return value


def _counts(expected, actual):
    result = dict(new=0, changed=0, matching=0, runtime_only=0, errors=0)
    for name in set(expected) | set(actual):
        old, live = expected.get(name), actual.get(name)
        key = ('errors' if live and live.get('error') else 'runtime_only' if old is None else
               'new' if live is None else 'matching' if old['sha256'] == live['sha256'] and old['bytes'] == live['bytes'] else 'changed')
        result[key] += 1
    return result


def inspect(engine, root, kind, metadata):
    """Compare actual installed bytes with a validated imported baseline."""
    root = files.confined(engine, root)
    path = files.confined(engine, root / NAME)
    if not metadata.get('baseline_sha256') or not path.is_file():
        raise ValueError('This older import has no per-file baseline. Review or explicitly import the selected component to record verifiable file fingerprints.')
    if path.stat().st_size > MAX_RECEIPT:
        raise ValueError('Content fingerprint receipt exceeds its size limit')
    value = files.read(engine, path)
    if (not isinstance(value, dict) or value.get('format') != 1 or value.get('profile') != engine.profile
            or value.get('kind') != kind or value.get('source') != _source(metadata)
            or files.identity(value) != metadata['baseline_sha256']):
        raise ValueError('Content fingerprint and import provenance do not match. Review import/restore records before relying on them.')
    expected = value.get('entries')
    if not isinstance(expected, dict) or not expected or len(expected) > files.MAX_FILES:
        raise ValueError('Incomplete imported-content fingerprint')
    total = 0
    for name, item in expected.items():
        files.check(engine)
        files.name(name)
        if (not isinstance(item, dict) or set(item) != {'bytes', 'sha256'}
                or isinstance(item['bytes'], bool) or not isinstance(item['bytes'], int)
                or not 0 <= item['bytes'] <= files.MAX_FILE
                or not re.fullmatch('[0-9a-f]{64}', str(item['sha256']))):
            raise ValueError('Invalid imported-content file fingerprint')
        total += item['bytes']
    if total > files.MAX_BYTES or files.identity(expected) != value.get('tree_sha256'):
        raise ValueError('Invalid imported-content tree fingerprint')
    _progress(engine, 'content_baseline_compare')
    actual = files.inventory(engine, root, MARKERS)
    groups = {}
    for group in ('quests', 'plugins', 'lua_modules'):
        def belongs(name):
            return (not name.startswith(('plugins/', 'lua_modules/')) if group == 'quests' else name.startswith(group + '/'))
        groups[group] = _counts({name: item for name, item in expected.items() if belongs(name)},
                                {name: item for name, item in actual.items() if belongs(name)})
    return {'counts': _counts(expected, actual), 'groups': groups,
            'source': value['source'], 'tree_sha256': value['tree_sha256']}


MAPS_PENDING = 'run/maps-import-pending.json'


def prepare_maps(engine, imported, prepared):
    """Move extracted map folders into staging; retain unrelated current files."""
    imported, prepared = files.confined(engine, imported), files.confined(engine, prepared)
    current = files.confined(engine, Path(engine.work) / 'maps')
    expected = inventory(engine, imported, ('base', 'nav', 'water', 'legacy'))
    prepared.mkdir()
    for folder in ('base', 'nav', 'water', 'legacy'):
        files.check(engine)
        source = imported / folder
        if source.exists():
            os.replace(source, prepared / folder)
    total = count = 0
    if current.exists():
        for directory, directories, names in os.walk(current, followlinks=False):
            files.check(engine)
            parent = Path(directory)
            if parent == current:
                directories[:] = [name for name in directories if name not in MARKERS]
            for name in directories + names:
                source = files.confined(engine, parent / name)
                relative = source.relative_to(current)
                if len(relative.parts) == 1 and name in MARKERS:
                    continue
                info = source.lstat()
                destination = files.confined(engine, prepared / relative)
                if stat.S_ISDIR(info.st_mode):
                    if destination.exists() and not destination.is_dir():
                        raise ValueError('Map import conflicts with an existing directory: ' + str(relative))
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError('Existing maps contain a special file: ' + str(relative))
                count += 1
                total += info.st_size
                if count > files.MAX_FILES or info.st_size > files.MAX_FILE or total > files.MAX_BYTES:
                    raise ValueError('Existing map files exceed the bounded import limit')
                files.check(engine)
                if destination.exists():
                    if not destination.is_file():
                        raise ValueError('Map import conflicts with an existing file: ' + str(relative))
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    return expected


def recover_maps(engine):
    """Recover a directory swap; never overwrite an unrecognized active tree."""
    journal = files.confined(engine, Path(engine.work) / MAPS_PENDING)
    if not journal.exists():
        return {'committed': False, 'recovered': False}
    record = files.read(engine, journal)
    if (not isinstance(record, dict) or record.get('format') != 1
            or record.get('profile') != engine.profile or record.get('kind') != 'maps'
            or not re.fullmatch(r'maps-import-[0-9a-f]{8}/prepared', str(record.get('prepared', '')))
            or not re.fullmatch(r'backups/maps-before-import/[0-9a-f]{16}', str(record.get('backup', '')))
            or not isinstance(record.get('previous'), bool)
            or not re.fullmatch('[0-9a-f]{64}', str(record.get('baseline_sha256', '')))):
        raise ValueError('Interrupted maps import has an invalid recovery record; preserve it and review the maps backup')
    prepared = files.confined(engine, Path(engine.work) / record['prepared'])
    backup = files.confined(engine, Path(engine.work) / record['backup'])
    current = files.confined(engine, Path(engine.work) / 'maps')
    committed = False
    if current.exists():
        try:
            marker = files.read(engine, current / MAPS_MARKER)
            receipt = files.read(engine, current / NAME)
            committed = (marker.get('baseline_sha256') == record['baseline_sha256']
                         and files.identity(receipt) == record['baseline_sha256'])
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        if not committed and (backup.exists() or not record['previous']):
            raise ValueError('Interrupted map import has an unrecognized active directory; both trees are preserved for review')
    elif backup.exists():
        os.replace(backup, current)
        files._fsync(Path(engine.work))
    elif record['previous']:
        raise ValueError('Interrupted maps import is missing its original directory; preserve staging and backups')
    # The generated stage is owned solely by this import. Its imported folders
    # were either activated above or never reached the active maps directory.
    if prepared.parent.exists():
        shutil.rmtree(prepared.parent)
    journal.unlink()
    files._fsync(journal.parent)
    return {'committed': committed, 'recovered': True}


def activate_maps(engine, prepared, metadata):
    """Atomically activate prepared maps with a unique, complete prior backup."""
    recover_maps(engine)
    prepared = files.confined(engine, prepared)
    current = files.confined(engine, Path(engine.work) / 'maps')
    backup = files.confined(engine, Path(engine.work) / 'backups/maps-before-import' / secrets.token_hex(8))
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        raise ValueError('Map backup destination already exists; preserve it and retry')
    capture_digest = metadata.get('baseline_sha256')
    if not capture_digest:
        raise ValueError('Prepared maps need a completed fingerprint before activation')
    # Commit the small source marker before exposing the prepared directory.
    files.atomic(engine, prepared / MAPS_MARKER, metadata)
    files.check(engine)
    previous = current.exists()
    journal = files.confined(engine, Path(engine.work) / MAPS_PENDING)
    files.atomic(engine, journal, {'format': 1, 'profile': engine.profile, 'kind': 'maps',
        'prepared': str(prepared.relative_to(engine.work)), 'backup': str(backup.relative_to(engine.work)),
        'previous': previous, 'baseline_sha256': capture_digest})
    try:
        if previous:
            os.replace(current, backup)
            files._fsync(backup.parent)
        os.replace(prepared, current)
        files._fsync(Path(engine.work))
        journal.unlink()
        files._fsync(journal.parent)
    except BaseException:
        outcome = recover_maps(engine)
        if not outcome['committed']:
            raise
    return str(backup.relative_to(engine.work)) if previous else None
