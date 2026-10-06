"""Install RoF2 interface skins into one profile without changing client settings."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import time
import xml.etree.ElementTree as ET
import zipfile

from managed_content import client_file

MARKER = '.trasc-ui.json'
MAX_BYTES = 512 * 1024**2
MAX_FILES = 20000
MAX_XML_BYTES = 8 * 1024**2
MAX_THEME_METADATA_BYTES = 1024**2
MAX_SKINS = 32
MAX_STATUS_SKINS = 256
MAX_STATUS_FILES = 4096
PROTECTED = {'default', 'default_old'}
EXTENSIONS = {'.xml', '.tga', '.bmp', '.dds', '.png', '.jpg', '.jpeg',
              '.gif', '.ico', '.cur', '.ttf', '.otf', '.txt', '.md'}
THEME_METADATA = {'stone_theme_manifest.json'}
WINDOWS_RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)),
                    *(f'lpt{i}' for i in range(1, 10))}


class _UiTreeBuilder(ET.TreeBuilder):
    def doctype(self, name, public_id, system_id):
        # Expat invokes this for every XML encoding before reading the root;
        # reject both internal entity subsets and external DTD declarations.
        raise ValueError('UI XML entity declarations are unsupported')


def skin_name(value):
    if not isinstance(value, str) or not value or len(value) > 80:
        raise ValueError('Use a skin name of 1 to 80 characters')
    if (value in ('.', '..') or value.endswith((' ', '.')) or
            any(ord(c) < 32 or c in '/\\:<>"|?*' for c in value) or
            value.split('.')[0].casefold() in WINDOWS_RESERVED):
        raise ValueError('Use an ordinary Windows folder name for the UI skin')
    if value.casefold() in PROTECTED:
        raise ValueError('The default UI is protected. Give this skin a different name')
    return value


def _ordinary_directory(path):
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError('UI directories must be ordinary folders')
    return path


def _locations(engine, required=True):
    client = engine._local_client(required)
    if client is None:
        return None, None, None
    ui = _ordinary_directory(client_file(client, 'uifiles'))
    for name in ('backups', 'backups/client-ui', 'run'):
        _ordinary_directory(engine.work / name)
    journal = engine.work / 'run/client-ui-import.json'
    if journal.is_symlink() or (journal.exists() and not journal.is_file()):
        raise ValueError('Unsafe UI import recovery journal')
    return client, ui, journal


def _read_marker(folder):
    marker = folder / MARKER
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 16384:
        return None
    try:
        value = json.loads(marker.read_text())
        return value if isinstance(value, dict) else None
    except (ValueError, OSError):
        return None


def _check_tree(folder):
    _ordinary_directory(folder)
    count = 0
    if folder.exists():
        for path in folder.rglob('*'):
            count += 1
            if count > MAX_FILES or path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise ValueError('Existing UI skin contains linked or unsupported files')


def recover(engine):
    """Commit a fully installed set, or roll back every partial directory swap."""
    _, ui, journal = _locations(engine, False)
    if journal is None or not journal.exists():
        return
    if journal.stat().st_size > 65536:
        raise ValueError('Invalid UI import recovery journal')
    record = json.loads(journal.read_text())
    identity = record.get('id')
    entries = record.get('skins')
    if (record.get('format') != 1 or record.get('profile') != engine.profile or
            not isinstance(identity, str) or not re.fullmatch('[0-9a-f]{24}', identity) or
            not isinstance(entries, list) or not 1 <= len(entries) <= MAX_SKINS):
        raise ValueError('Invalid UI import recovery journal')
    backup = _ordinary_directory(engine.work / 'backups/client-ui' / identity)
    stage = _ordinary_directory(engine.work / 'client' / ('ui-import-' + identity))
    targets = []
    seen = set()
    for entry in entries:
        name = skin_name(entry.get('name'))
        if name.casefold() in seen or not isinstance(entry.get('previous'), bool):
            raise ValueError('Invalid UI import recovery skin')
        seen.add(name.casefold())
        target = _ordinary_directory(client_file(ui, name))
        saved = _ordinary_directory(backup / name)
        targets.append((entry, target, saved, _read_marker(target)))
    complete = all(marker and marker.get('transaction') == identity for _, _, _, marker in targets)
    if not complete:
        for entry, target, saved, marker in reversed(targets):
            installed = bool(marker and marker.get('transaction') == identity)
            if saved.exists():
                _check_tree(saved)
                if target.exists():
                    if not installed:
                        raise ValueError('UI skin changed during interrupted import: ' + target.name)
                    _check_tree(target)
                    shutil.rmtree(target)
                os.replace(saved, target)
            elif entry['previous']:
                if not target.exists() or installed:
                    raise ValueError('UI skin backup is missing: ' + target.name)
            elif target.exists():
                if not installed:
                    raise ValueError('UI skin changed during interrupted import: ' + target.name)
                _check_tree(target)
                shutil.rmtree(target)
    journal.unlink()
    if stage.exists():
        shutil.rmtree(stage)


def _archive(engine, value):
    from engine import safe_path
    if not isinstance(value, str) or not value:
        raise ValueError('Choose a UI ZIP through the Android file picker')
    name = value[9:] if value.startswith('incoming/') else value
    if PurePosixPath(name).name != name or '\\' in name:
        raise ValueError('Choose a UI ZIP through the Android file picker')
    incoming = _ordinary_directory(engine.work / 'incoming')
    path = incoming / name
    if path.is_symlink() or safe_path(incoming, name, True) != path or not path.is_file():
        raise ValueError('UI ZIP must be an ordinary incoming file')
    if not zipfile.is_zipfile(path):
        raise ValueError('Choose a ZIP containing a RoF2 UI skin')
    return path


def _validate_zip(archive):
    """Reject Windows-case collisions before the shared streaming extractor runs."""
    seen, spellings = {}, {}
    total = 0
    with zipfile.ZipFile(archive) as source:
        if len(source.infolist()) > MAX_FILES:
            raise ValueError('UI ZIP has too many files')
        for info in source.infolist():
            name = info.filename
            parts = PurePosixPath(name).parts
            if (not parts or PurePosixPath(name).is_absolute() or
                    any(p in ('.', '..') or p.endswith((' ', '.')) or
                        any(ord(c) < 32 or c in '\\:<>"|?*' for c in p) or
                        p.split('.')[0].casefold() in WINDOWS_RESERVED for p in parts)):
                raise ValueError('Unsafe UI ZIP path: ' + name)
            mode = info.external_attr >> 16
            if (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) or
                    info.flag_bits & 1):
                raise ValueError('UI ZIP needs ordinary, unencrypted files and folders')
            canonical = '/'.join(parts)
            key = canonical.casefold()
            if key in seen:
                raise ValueError('Duplicate Windows-case UI ZIP path: ' + name)
            seen[key] = info.is_dir()
            for i in range(1, len(parts) + 1):
                prefix = '/'.join(parts[:i])
                previous = spellings.setdefault(prefix.casefold(), prefix)
                if previous != prefix:
                    raise ValueError('Ambiguous Windows-case UI ZIP folder: ' + name)
            total += info.file_size
            if info.file_size < 0 or total > MAX_BYTES:
                raise ValueError('UI ZIP exceeds the 512 MiB import limit')
        for key in seen:
            parts = key.split('/')
            if any(seen.get('/'.join(parts[:i])) is False for i in range(1, len(parts))):
                raise ValueError('UI ZIP file conflicts with a folder')


def _ui_xml(path):
    return path.is_file() and path.suffix.casefold() == '.xml' and (
        path.name.casefold().startswith('equi') or path.name.casefold() == 'sidl.xml')


def _roots(stage):
    candidates = sorted({p.parent for p in stage.rglob('*') if _ui_xml(p)}, key=lambda p: (len(p.parts), str(p)))
    roots = []
    for path in candidates:
        if not any(path.is_relative_to(parent) for parent in roots):
            roots.append(path)
    if not roots:
        raise ValueError('UI ZIP needs a skin folder containing EQUI XML files')
    if len(roots) > MAX_SKINS:
        raise ValueError('Import at most 32 UI skins at a time')
    return roots


def _theme_metadata(path, relative):
    """Validate and omit known packaging metadata; it is not a client asset."""
    if len(relative.parts) != 1 or path.name.casefold() not in THEME_METADATA:
        return False
    if path.stat().st_size > MAX_THEME_METADATA_BYTES:
        raise ValueError('StoneUI theme metadata exceeds the 1 MiB limit: ' + str(relative))
    def unsupported_constant(value):
        raise ValueError('Unsupported JSON constant: ' + value)
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'), parse_constant=unsupported_constant)
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid StoneUI theme metadata: ' + str(relative)) from exc
    if not isinstance(value, dict):
        raise ValueError('StoneUI theme metadata must be a JSON object: ' + str(relative))
    return True


def _prepare(engine, root, destination):
    files = size = 0
    destination.mkdir(parents=True)
    for path in sorted(root.rglob('*')):
        engine.check_cancel()
        relative = path.relative_to(root)
        if any(part == '__MACOSX' or part.startswith('._') for part in relative.parts):
            continue
        if path.is_dir():
            continue
        if path.name.casefold() in (MARKER, '.ds_store', 'thumbs.db', 'desktop.ini'):
            continue
        if _theme_metadata(path, relative):
            continue
        if path.suffix.casefold() not in EXTENSIONS:
            raise ValueError('Unsupported file in UI skin: ' + str(relative))
        if path.suffix.casefold() == '.xml':
            if path.stat().st_size > MAX_XML_BYTES:
                raise ValueError('UI XML exceeds the 8 MiB limit: ' + str(relative))
            raw = path.read_bytes()
            try:
                document = ET.fromstring(raw, parser=ET.XMLParser(target=_UiTreeBuilder()))
            except ET.ParseError as exc:
                raise ValueError('Invalid UI XML: ' + str(relative)) from exc
            except ValueError as exc:
                raise ValueError(str(exc) + ': ' + str(relative)) from exc
            if _ui_xml(path) and document.tag.rsplit('}', 1)[-1].casefold() != 'xml':
                raise ValueError('Expected EQ interface XML: ' + str(relative))
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Bound each copy and observe cancellation between blocks.
        with path.open('rb') as source, target.open('xb') as output:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                engine.check_cancel()
                output.write(block)
        target.chmod(0o644)
        files += 1
        size += path.stat().st_size
    return files, size


def install(engine, args):
    from engine import atomic_json, extract_archive
    # Android serializes this operation with ClientRuntime.start/stop and blocks
    # both live and starting clients. Linux has a separate client rootfs/process.
    if not isinstance(args.get('replace', False), bool):
        raise ValueError('Choose whether to replace an existing UI skin')
    if not isinstance(args.get('name', ''), str):
        raise ValueError('Use a text name for the UI skin')
    archive_name = args.get('archive_name', '')
    if not isinstance(archive_name, str) or '/' in archive_name or '\\' in archive_name:
        raise ValueError('Invalid original UI ZIP filename')
    client, ui, journal = _locations(engine)
    recover(engine)
    archive = _archive(engine, args.get('file'))
    _validate_zip(archive)
    identity = secrets.token_hex(12)
    stage = engine.work / 'client' / ('ui-import-' + identity)
    backup = engine.work / 'backups/client-ui' / identity
    records = []
    try:
        extract_archive(archive, stage / 'unpacked', limit=MAX_BYTES)
        roots = _roots(stage / 'unpacked')
        rename = args.get('name', '')
        if rename and len(roots) != 1:
            raise ValueError('Give a custom skin name only when importing one skin')
        seen = set()
        targets = []
        with archive.open('rb') as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                engine.check_cancel()
                digest.update(block)
        for root in roots:
            inferred = ((Path(archive_name).stem if archive_name else archive.stem)
                        if root == stage / 'unpacked' else root.name)
            name = skin_name(rename or inferred)
            if name.casefold() in seen:
                raise ValueError('UI ZIP has duplicate skin names: ' + name)
            seen.add(name.casefold())
            target = _ordinary_directory(client_file(ui, name))
            _check_tree(target)
            if target.exists() and not args.get('replace', False):
                raise ValueError('Select Replace existing skin to back it up and install ' + name)
            name = target.name  # Preserve existing Windows filename casing.
            prepared = stage / 'prepared' / name
            files, size = _prepare(engine, root, prepared)
            record = {'format': 1, 'profile': engine.profile, 'name': name,
                      'transaction': identity, 'installed_at': time.time(),
                      'archive_sha256': digest.hexdigest(), 'files': files, 'bytes': size,
                      'backup': ('backups/client-ui/' + identity + '/' + name) if target.exists() else None}
            atomic_json(prepared / MARKER, record)
            records.append(record)
            targets.append((prepared, target))
        engine.check_cancel()
        ui.mkdir(parents=True, exist_ok=True)
        backup.mkdir(parents=True)
        atomic_json(journal, {'format': 1, 'profile': engine.profile, 'id': identity,
                             'skins': [{'name': target.name, 'previous': target.exists()} for _, target in targets]})
        try:
            for prepared, target in targets:
                engine.check_cancel()
                if target.exists():
                    os.replace(target, backup / target.name)
                os.replace(prepared, target)
        except Exception:
            recover(engine)
            raise
        journal.unlink()
        result = status(engine)
        return {'message': 'UI skin' + ('s' if len(records) != 1 else '') + ' installed: ' +
                ', '.join(record['name'] for record in records) + '. Select in game with /loadskin <skin> 1.',
                'installed': records, 'ui': result}
    finally:
        if not journal.exists() and stage.exists():
            shutil.rmtree(stage)


def status(engine):
    result = {'client_imported': False, 'imported': False, 'skins': [],
              'activation_hint': 'Select an installed skin in game with /loadskin <skin> 1.'}
    try:
        client, ui, _ = _locations(engine, False)
        result['client_imported'] = client is not None
        if ui is not None and ui.exists():
            count = 0
            remaining = MAX_STATUS_FILES
            for path in ui.iterdir():
                count += 1
                if count > MAX_STATUS_SKINS:
                    result['truncated'] = True
                    break
                if path.is_symlink() or not path.is_dir():
                    continue
                marker = _read_marker(path)
                imported = bool(marker and marker.get('profile') == engine.profile and marker.get('format') == 1)
                if not imported:
                    found = False
                    for entry in path.iterdir():
                        if remaining <= 0:
                            break
                        remaining -= 1
                        if _ui_xml(entry):
                            found = True
                            break
                    if not found:
                        continue
                record = {'name': path.name, 'imported': imported, 'protected': path.name.casefold() in PROTECTED,
                          'path': str(path.relative_to(engine.work))}
                if imported:
                    record.update({key: marker.get(key) for key in ('files', 'bytes', 'installed_at', 'archive_sha256', 'backup')})
                result['skins'].append(record)
            result['skins'].sort(key=lambda skin: skin['name'].casefold())
        result['imported'] = any(skin['imported'] for skin in result['skins'])
        result['message'] = ('Choose a UI ZIP after importing this profile’s RoF2 client.' if not result['client_imported'] else
                             'Installed skins: ' + ', '.join(skin['name'] for skin in result['skins']) if result['skins'] else
                             'No UI skins imported yet. Choose a RoF2 UI ZIP.')
    except (ValueError, OSError) as exc:
        result['message'] = 'UI import needs attention: ' + str(exc)
        result['error'] = str(exc)
    return result
