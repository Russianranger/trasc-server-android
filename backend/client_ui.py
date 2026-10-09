"""Install RoF2 interface skins into one profile without changing client settings."""
import hashlib
import json
import math
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
MAX_CHARACTER_SCAN = 20000
MAX_CHARACTER_FILES = 64
MAX_INI_BYTES = 2 * 1024**2
MAX_CHARACTER_TOTAL_BYTES = 16 * 1024**2
MAX_LAYOUT_XML_BYTES = 32 * 1024**2
MAX_ACTIVATION_BACKUPS = 256
ACTIVATION_BACKUPS = 'backups/client-ui-activation'
_WINDOW_CACHE = {}
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


def skin_name(value, allow_default=False):
    if not isinstance(value, str) or not value or len(value) > 80:
        raise ValueError('Use a skin name of 1 to 80 characters')
    if (value in ('.', '..') or value.endswith((' ', '.')) or
            any(ord(c) < 32 or c in '/\\:<>"|?*' for c in value) or
            value.split('.')[0].casefold() in WINDOWS_RESERVED):
        raise ValueError('Use an ordinary Windows folder name for the UI skin')
    if value.casefold() in PROTECTED and not allow_default:
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
    if engine.profile == 'takp':
        raise ValueError('RoF2 UI ZIPs are incompatible with TAKP. Use a TAKP skin included in its client and /loadskin <skin> 1 in game')
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


def _character_name(value):
    if (not isinstance(value, str) or len(value) > 255 or
            not re.fullmatch(r'UI_.+\.ini', value, re.IGNORECASE) or
            value.endswith((' ', '.')) or
            any(ord(c) < 32 or c in '/\\:<>"|?*' for c in value)):
        raise ValueError('Choose an existing character UI INI filename')
    return value


def _ordinary_bytes(path, maximum=MAX_INI_BYTES):
    """Bound reads and reject links, including a replacement during opening."""
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
        raise ValueError('Choose an ordinary, bounded UI settings file')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError('UI settings changed. Refresh before continuing')
        raw = source.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('UI settings exceed the 2 MiB limit')
    return raw


def _parse_ini(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        raise ValueError('UTF-16 character UI settings are unsupported')
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text = raw[len(bom):].decode('latin-1')
    if any(ord(c) < 32 and c not in '\t\r\n' for c in text):
        raise ValueError('Malformed character UI settings')
    # Latin-1 byte 0x85 is an ordinary legacy Windows character, not a newline.
    lines = [line for line in re.findall(r'[^\r\n]*(?:\r\n|\r|\n|$)', text) if line]
    sections, entries = {}, {}
    section = None
    for index, line in enumerate(lines):
        stripped = line.rstrip('\r\n').strip()
        if not stripped or stripped.startswith((';', '#')):
            continue
        if stripped.startswith('['):
            match = re.fullmatch(r'\[([^\]]+)\][ \t]*(?:[;#].*)?', stripped)
            if not match or not match[1].strip() or len(match[1]) > 128:
                raise ValueError('Malformed character UI settings section')
            name = match[1].strip()
            section = name.casefold()
            if section in sections:
                raise ValueError('Duplicate character UI settings section')
            sections[section] = {'name': name, 'line': index}
            continue
        if section is None or '=' not in stripped:
            raise ValueError('Malformed character UI settings entry')
        key, value = stripped.split('=', 1)
        key = key.strip()
        if not key or len(key) > 128 or '[' in key or ']' in key:
            raise ValueError('Malformed character UI settings key')
        identity = (section, key.casefold())
        if identity in entries:
            raise ValueError('Duplicate character UI settings key')
        value = re.split(r'[ \t]+[;#]', value, maxsplit=1)[0].strip()
        entries[identity] = {'section': sections[section]['name'], 'key': key,
                             'value': value, 'line': index}
    if not sections or not entries:
        raise ValueError('Character UI settings have no INI entries')
    return {'bom': bom, 'lines': lines, 'sections': sections, 'entries': entries,
            'newline': re.search(r'\r\n|\r|\n', text)[0] if re.search(r'\r\n|\r|\n', text) else '\r\n'}


def _current_skin(parsed):
    return parsed['entries'].get(('main', 'uiskin'), {}).get('value') or 'Default'


def _merge_ini(parsed, changes):
    """Change only approved values; retain every unrelated line and byte."""
    pending = dict(changes)
    replacements, additions = {}, {}
    for identity, entry in parsed['entries'].items():
        if identity not in pending:
            continue
        section, key, value = pending.pop(identity)
        if entry['value'] == value:
            continue
        line = parsed['lines'][entry['line']]
        ending = re.search(r'(\r\n|\r|\n)$', line)
        suffix = ending[0] if ending else ''
        body = line[:-len(suffix)] if suffix else line
        left, old = body.split('=', 1)
        leading = re.match(r'[ \t]*', old)[0]
        rest = old[len(leading):]
        comment = re.search(r'[ \t]+[;#].*$', rest)
        trailing = comment[0] if comment else re.search(r'[ \t]*$', rest)[0]
        replacements[entry['line']] = left + '=' + leading + value + trailing + suffix
    headers = sorted((section['line'], identity) for identity, section in parsed['sections'].items())
    new_sections = {}
    for identity, (section, key, value) in pending.items():
        if identity[0] in parsed['sections']:
            following = next((line for line, _ in headers if line > parsed['sections'][identity[0]]['line']), len(parsed['lines']))
            additions.setdefault(following, []).append(key + '=' + value + parsed['newline'])
        else:
            new_sections.setdefault(identity[0], (section, []))[1].append(key + '=' + value + parsed['newline'])
    output = []
    for index in range(len(parsed['lines']) + 1):
        if index in additions:
            if output and not output[-1].endswith(('\r', '\n')):
                output.append(parsed['newline'])
            output.extend(additions[index])
        if index < len(parsed['lines']):
            output.append(replacements.get(index, parsed['lines'][index]))
    for section, lines in new_sections.values():
        if output and not output[-1].endswith(('\r', '\n')):
            output.append(parsed['newline'])
        output.append('[' + section + ']' + parsed['newline'])
        output.extend(lines)
    return parsed['bom'] + ''.join(output).encode('latin-1')


def _installed_skin(ui, value):
    name = skin_name(value, allow_default=True)
    folder = _ordinary_directory(client_file(ui, name))
    if not folder.is_dir():
        raise ValueError('Choose an installed UI skin')
    # Retain the exact installed filename casing in UISkin.
    xml = []
    seen = set()
    for index, path in enumerate(folder.iterdir()):
        if index >= MAX_STATUS_FILES:
            raise ValueError('UI skin has too many root files')
        if path.name.casefold() in seen:
            raise ValueError('Ambiguous UI skin filenames')
        seen.add(path.name.casefold())
        if path.is_symlink():
            raise ValueError('UI skin cannot contain linked files')
        if _ui_xml(path):
            xml.append(path)
    if not xml:
        raise ValueError('Installed UI skin needs EQUI XML files')
    return folder, xml


def _window_names(folder, xml, budget=None):
    signature = tuple((path.name, path.stat().st_size, path.stat().st_mtime_ns) for path in sorted(xml))
    cache_key = str(folder)
    if _WINDOW_CACHE.get(cache_key, {}).get('signature') == signature:
        return _WINDOW_CACHE[cache_key]['names']
    names, total = set(), 0
    for path in xml:
        size = path.stat().st_size
        total += size
        if size > MAX_XML_BYTES or total > MAX_LAYOUT_XML_BYTES:
            raise ValueError('UI definitions exceed the layout validation limit')
        if budget is not None:
            budget[0] -= size
            if budget[0] < 0:
                raise ValueError('Layout scan reached its byte limit')
        try:
            document = ET.fromstring(_ordinary_bytes(path, MAX_XML_BYTES), parser=ET.XMLParser(target=_UiTreeBuilder()))
        except (ET.ParseError, ValueError) as exc:
            raise ValueError('Invalid installed UI definitions for layout') from exc
        for element in document.iter():
            if element.tag.rsplit('}', 1)[-1].casefold() != 'screen':
                continue
            if element.get('item'):
                names.add(element.get('item').casefold())
            for child in element:
                if child.tag.rsplit('}', 1)[-1].casefold() in ('ininame', 'screenid') and child.text:
                    names.add(child.text.strip().casefold())
    # Native chat windows share their one XML Screen; their INI names are dynamic.
    if 'chatwindow' in names:
        names.add('mainchat')
    if len(_WINDOW_CACHE) >= MAX_STATUS_SKINS:
        _WINDOW_CACHE.clear()
    _WINDOW_CACHE[cache_key] = {'signature': signature, 'names': names}
    return names


def _layout_value(key, value):
    key = key.casefold()
    if key in ('show', 'locked') or re.fullmatch(r'minimized(?:\d{3,5}x\d{3,5})?', key):
        if value.casefold() not in ('0', '1', 'true', 'false'):
            raise ValueError('Layout visibility must be a boolean')
        return value
    if key in ('xscale', 'yscale', 'wscale', 'hscale'):
        if not re.fullmatch(r'-?\d+(?:\.\d+)?', value) or not math.isfinite(float(value)) or abs(float(value)) > 16:
            raise ValueError('Invalid layout viewport scale')
        return value
    if not re.fullmatch(r'-?\d{1,6}', value):
        raise ValueError('Layout geometry must be an ordinary integer')
    number = int(value)
    bound = 1024 if key == 'iniversion' else 32768
    if abs(number) > bound or ((key == 'iniversion' or 'width' in key or 'height' in key or key in ('w', 'h')) and number < 0):
        raise ValueError('Layout geometry is out of range')
    return value


def _layout_changes(folder, xml, character, existing, budget=None):
    preset = client_file(folder, character + '.txt')
    if not preset.is_file():
        raise ValueError('This skin has no included layout matching this character')
    if budget is not None:
        budget[0] -= preset.stat().st_size
        if budget[0] < 0:
            raise ValueError('Layout scan reached its byte limit')
    parsed = _parse_ini(_ordinary_bytes(preset))
    windows = _window_names(folder, xml, budget)
    changes = {}
    geometry = re.compile(r'(?:restore)?(?:xpos|ypos|width|height)(?:\d{3,5}x\d{3,5})?|minimized(?:\d{3,5}x\d{3,5})?')
    for identity, entry in parsed['entries'].items():
        section, key = identity
        if section in ('main', 'chatmanager'):
            continue
        viewport = re.fullmatch(r'viewport(\d{3,5})x(\d{3,5})', section)
        if viewport:
            if not all(320 <= int(dimension) <= 16384 for dimension in viewport.groups()):
                raise ValueError('Invalid layout viewport resolution')
            approved = key in ('x', 'y', 'w', 'h', 'xscale', 'yscale', 'wscale', 'hscale')
        else:
            dynamic_chat = bool(re.fullmatch(r'chat \d{1,2}', section)) and 'chatwindow' in windows
            if dynamic_chat and section not in existing['sections']:
                continue  # Position existing chat panes without creating new ones.
            if section not in windows and not dynamic_chat:
                continue
            approved = bool(geometry.fullmatch(key)) or key in ('show', 'locked', 'iniversion')
        if approved:
            value = _layout_value(key, entry['value'])
            changes[identity] = (entry['section'], entry['key'], value)
    if not changes:
        raise ValueError('Included layout has no supported window geometry or visibility')
    return changes


def _character_file(client, value):
    name = _character_name(value)
    path = client_file(client, name)
    if not path.is_file():
        raise ValueError('Choose an existing character UI settings file')
    raw = _ordinary_bytes(path)
    return path, raw, _parse_ini(raw)


def _revision(raw):
    return hashlib.sha256(raw).hexdigest()


def _expected_revision(raw, expected):
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected) or _revision(raw) != expected:
        raise ValueError('Character UI settings changed. Refresh before continuing')


def _backup_root(engine):
    root = _ordinary_directory(engine.work / ACTIVATION_BACKUPS)
    _ordinary_directory(engine.work / 'backups')
    return root


def _record(engine, identity, character, budget=None):
    if not isinstance(identity, str) or not re.fullmatch(r'[0-9a-f]{24}', identity):
        raise ValueError('Choose a recorded previous UI configuration')
    folder = _ordinary_directory(_backup_root(engine) / identity)
    if budget is not None:
        budget[0] -= (folder / 'record.json').lstat().st_size
        if budget[0] < 0:
            raise ValueError('UI configuration history reached its byte limit')
    record = json.loads(_ordinary_bytes(folder / 'record.json', 16384))
    if (not isinstance(record, dict) or record.get('format') != 1 or
            record.get('profile') != engine.profile or record.get('id') != identity or
            record.get('character_file') != character or
            not isinstance(record.get('before_sha256'), str) or
            not re.fullmatch(r'[0-9a-f]{64}', record['before_sha256']) or
            type(record.get('created_at')) not in (int, float) or
            not 0 <= record['created_at'] <= 2**53 or
            not math.isfinite(record['created_at'])):
        raise ValueError('Invalid previous UI configuration record')
    if budget is not None:
        budget[0] -= (folder / character).lstat().st_size
        if budget[0] < 0:
            raise ValueError('UI configuration history reached its byte limit')
    saved = _ordinary_bytes(folder / character)
    if _revision(saved) != record['before_sha256']:
        raise ValueError('Previous UI configuration checksum failed')
    parsed = _parse_ini(saved)
    return record, saved, parsed


def _previous_settings(engine, character, budget=None):
    root = _backup_root(engine)
    if not root.is_dir():
        return None
    entries = []
    for index, path in enumerate(root.iterdir()):
        if index >= MAX_ACTIVATION_BACKUPS:
            raise ValueError('UI configuration history reached its supported limit')
        if not path.is_symlink() and path.is_dir() and re.fullmatch(r'[0-9a-f]{24}', path.name):
            entries.append(path)
    for path in sorted(entries, key=lambda p: p.stat().st_mtime_ns, reverse=True):
        if budget is not None and budget[0] <= 0:
            raise ValueError('UI configuration history reached its byte limit')
        try:
            record, _, parsed = _record(engine, path.name, character, budget)
            return {'id': path.name, 'backup': ACTIVATION_BACKUPS + '/' + path.name + '/' + character,
                    'skin': _current_skin(parsed), 'created_at': record['created_at']}
        except (ValueError, OSError):
            continue
    return None


def _replace_settings(engine, client, path, original, updated, operation, layout_applied=False):
    """One anchored, atomic INI replacement; failures before commit retain it."""
    from engine import atomic_json
    if updated == original:
        return None
    engine.check_cancel()
    identity = secrets.token_hex(12)
    root = _backup_root(engine)
    root.mkdir(parents=True, exist_ok=True)
    backup = root / identity
    if backup.exists() or backup.is_symlink():
        raise ValueError('UI settings backup identity already exists')
    backup.mkdir()
    descriptor = None
    temporary = '.trasc-ui-activation-' + identity + '.tmp'
    committed = False
    try:
        with (backup / path.name).open('xb') as output:
            output.write(original)
            output.flush()
            os.fsync(output.fileno())
        record = {'format': 1, 'profile': engine.profile, 'id': identity, 'character_file': path.name,
                  'created_at': time.time(), 'operation': operation, 'layout_applied': layout_applied,
                  'before_sha256': _revision(original), 'after_sha256': _revision(updated)}
        atomic_json(backup / 'record.json', record)
        descriptor = os.open(client, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        original_directory = os.fstat(descriptor)
        file_descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
        with os.fdopen(file_descriptor, 'wb') as output:
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
        engine.check_cancel()
        # Re-resolve every profile path and re-read immediately before the rename.
        current, _, _ = _locations(engine)
        if (current.stat().st_dev, current.stat().st_ino) != (original_directory.st_dev, original_directory.st_ino):
            raise ValueError('Client directory changed. Refresh before continuing')
        current_path, current_raw, _ = _character_file(current, path.name)
        if current_path.name != path.name or current_raw != original:
            raise ValueError('Character UI settings changed. Refresh before continuing')
        os.replace(temporary, path.name, src_dir_fd=descriptor, dst_dir_fd=descriptor)
        committed = True
        return ACTIVATION_BACKUPS + '/' + identity + '/' + path.name
    finally:
        if descriptor is not None:
            try:
                os.unlink(temporary, dir_fd=descriptor)
            except FileNotFoundError:
                pass
            os.close(descriptor)
        if not committed:
            shutil.rmtree(backup)


def activate(engine, args):
    if engine.profile == 'takp': raise ValueError('Select a native TAKP skin in game with /loadskin <skin> 1')
    if not isinstance(args.get('apply_layout', False), bool):
        raise ValueError('Choose whether to apply the included layout')
    client, ui, _ = _locations(engine)
    recover(engine)
    path, raw, parsed = _character_file(client, args.get('character_file'))
    _expected_revision(raw, args.get('revision'))
    folder, xml = _installed_skin(ui, args.get('skin'))
    if re.search(r'[ \t]+[;#]', folder.name):
        raise ValueError('Skin name is ambiguous with an INI comment')
    if parsed['bom'] and any(ord(character) > 127 for character in folder.name):
        raise ValueError('Use an ASCII skin name for a character INI with a UTF-8 BOM')
    try:
        folder.name.encode('latin-1')
    except UnicodeEncodeError as exc:
        raise ValueError('Skin name must fit the native Windows INI encoding') from exc
    changes = _layout_changes(folder, xml, path.name, parsed) if args.get('apply_layout', False) else {}
    changes[('main', 'uiskin')] = ('Main', 'UISkin', folder.name)
    updated = _merge_ini(parsed, changes)
    if len(updated) > MAX_INI_BYTES:
        raise ValueError('Character UI settings exceed the 2 MiB limit')
    backup = _replace_settings(engine, client, path, raw, updated, 'activate', args.get('apply_layout', False))
    return {'message': 'Selected ' + folder.name + ' for ' + path.name + '. Start the client to test it.',
            'ui': status(engine), 'backup': backup, 'skin': folder.name, 'character_file': path.name,
            'layout_applied': args.get('apply_layout', False), 'revision': _revision(updated)}


def restore_settings(engine, args):
    if engine.profile == 'takp': raise ValueError('TAKP character UI settings are managed by its native client')
    client, _, _ = _locations(engine)
    recover(engine)
    path, raw, parsed = _character_file(client, args.get('character_file'))
    _expected_revision(raw, args.get('revision'))
    _, saved, restored = _record(engine, args.get('activation_id'), path.name)
    backup = _replace_settings(engine, client, path, raw, saved, 'restore')
    return {'message': 'Previous UI settings restored for ' + path.name + '. Start the client to test them.',
            'ui': status(engine), 'backup': backup, 'skin': _current_skin(restored), 'character_file': path.name,
            'layout_applied': False, 'revision': _revision(saved)}


def _characters(engine, client, ui, skins):
    result, errors, seen = [], [], {}
    total = 0
    layout_budget = [MAX_LAYOUT_XML_BYTES]
    history_budget = [MAX_CHARACTER_TOTAL_BYTES]
    candidates = []
    for index, path in enumerate(client.iterdir()):
        if index >= MAX_CHARACTER_SCAN:
            errors.append({'error': 'Character settings scan reached its file limit'})
            break
        if re.fullmatch(r'UI_.+\.ini', path.name, re.IGNORECASE):
            seen.setdefault(path.name.casefold(), []).append(path)
            candidates.append(path)
    for path in sorted(candidates, key=lambda p: p.name.casefold())[:MAX_CHARACTER_FILES]:
        try:
            if len(seen[path.name.casefold()]) != 1:
                raise ValueError('Ambiguous character UI settings filename')
            _character_name(path.name)
            if path.lstat().st_size > MAX_CHARACTER_TOTAL_BYTES - total:
                errors.append({'error': 'Character settings scan reached its byte limit'})
                break
            raw = _ordinary_bytes(path, min(MAX_INI_BYTES, MAX_CHARACTER_TOTAL_BYTES - total))
            total += len(raw)
            if total > MAX_CHARACTER_TOTAL_BYTES:
                raise ValueError('Character settings scan reached its byte limit')
            parsed = _parse_ini(raw)
            layouts = []
            for skin in skins:
                try:
                    folder = client_file(ui, skin['name'])
                    if not client_file(folder, path.name + '.txt').exists():
                        continue
                    folder, xml = _installed_skin(ui, skin['name'])
                    _layout_changes(folder, xml, path.name, parsed, layout_budget)
                    layouts.append(folder.name)
                except (ValueError, OSError):
                    continue
            character = {'file': path.name, 'skin': _current_skin(parsed), 'revision': _revision(raw), 'layout_skins': layouts}
            try:
                previous = _previous_settings(engine, path.name, history_budget)
            except (ValueError, OSError):
                previous = None
                character['previous_settings_error'] = 'Previous UI settings history is invalid or exceeds its scan limit'
            if previous:
                character['previous_settings'] = previous
            result.append(character)
        except (ValueError, OSError):
            errors.append({'file': path.name, 'error': 'Character UI settings are invalid or unsafe'})
    return result, errors


def status(engine):
    if engine.profile == 'takp':
        return {'client_imported': engine._local_client(False) is not None, 'imported': False,
                'skins': [], 'characters': [], 'supported': False,
                'activation_hint': 'Use a native TAKP skin included in its client and /loadskin <skin> 1 in game.',
                'message': 'TAKP uses its December 2002 interface. RoF2 skin imports and layout activation are unavailable.'}
    result = {'client_imported': False, 'imported': False, 'skins': [], 'characters': [],
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
        if client is not None:
            result['characters'], errors = _characters(engine, client, ui, result['skins'])
            if errors:
                result['character_errors'] = errors
        result['message'] = ('Choose a UI ZIP after importing this profile’s RoF2 client.' if not result['client_imported'] else
                             'Installed skins: ' + ', '.join(skin['name'] for skin in result['skins']) if result['skins'] else
                             'No UI skins imported yet. Choose a RoF2 UI ZIP.')
    except (ValueError, OSError) as exc:
        result['message'] = 'UI import needs attention: ' + str(exc)
        result['error'] = str(exc)
    return result
