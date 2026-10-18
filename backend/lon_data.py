"""Bounded, reviewed import of the client's LegendsOfNorrath/data tree.

The card-table validator follows Triptych world/lon_service.cpp's Reader,
ParseArchetype and LoadData. It does not start the service or change database
rules. Source archives are searched without extracting the rest of the client.
"""
from datetime import datetime
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import struct
import time
import zipfile
import zlib

import custom_deployment as deployment

BUFFER = 256 * 1024
MAX_ENTRIES = 200000
MAX_DIRECTORY_BYTES = 64 * 1024**2
MAX_TOTAL = 16 * 1024**3
MAX_FILE = 8 * 1024**3
MAX_RECORD = 8 * 1024**2
RESERVE = 64 * 1024**2
KIND = 'lon_data'


def _check(engine):
    check = getattr(engine, 'check_cancel', None)
    if check:
        check()
    elif getattr(engine, 'cancel', None) is not None and engine.cancel.is_set():
        raise ValueError('Legends of Norrath import cancelled')


def _progress(engine, phase, files=0, total_files=0, copied=0, total=0):
    job = getattr(engine, 'current_job', None)
    if job is not None:
        job['progress'] = {'phase': phase, 'message': 'Legends of Norrath: ' + phase,
                           'files': files, 'total_files': total_files,
                           'bytes': copied, 'total_bytes': total,
                           'downloaded_bytes': copied}


def _name(value, directory=False):
    if not isinstance(value, str) or not value or '\\' in value or any(c in value for c in '\0\r\n'):
        raise ValueError('Unsafe Legends of Norrath path')
    name = value[:-1] if directory and value.endswith('/') else value
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/'))
            or ':' in path.parts[0] or path.as_posix() != name):
        raise ValueError('Unsafe Legends of Norrath path: ' + value)
    return name


def _confined(engine, value):
    name = _name(value)
    root = Path(engine.work)
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Legends of Norrath sources cannot use symbolic links')
    if not path.exists():
        raise ValueError('The selected Legends of Norrath source no longer exists')
    return path


def _regular(path):
    if any(parent.is_symlink() for parent in (Path(path), *Path(path).parents)):
        raise ValueError('Legends of Norrath sources cannot use symbolic links')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stream = os.fdopen(fd, 'rb')
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        stream.close()
        raise ValueError('Legends of Norrath data must contain ordinary files')
    return stream


def _walk(engine, root):
    """Bound metadata and never follow a source link or special file."""
    rows, folded, total = [], set(), 0
    stack = [(Path(root), '')]
    while stack:
        _check(engine)
        directory, prefix = stack.pop()
        with os.scandir(directory) as stream:
            for entry in stream:
                _check(engine)
                relative = _name(prefix + entry.name)
                key = relative.casefold()
                if key in folded:
                    raise ValueError('Ambiguous case-insensitive source path: ' + relative)
                folded.add(key)
                if len(folded) > MAX_ENTRIES:
                    raise ValueError('Legends of Norrath source has too many entries')
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    stack.append((Path(entry.path), relative + '/'))
                    rows.append((relative, True, 0, info.st_mtime, Path(entry.path)))
                elif stat.S_ISREG(info.st_mode):
                    if info.st_size > MAX_FILE:
                        raise ValueError('Legends of Norrath file exceeds the supported size: ' + relative)
                    total += info.st_size
                    if total > MAX_TOTAL:
                        raise ValueError('Legends of Norrath data exceeds the supported size')
                    rows.append((relative, False, info.st_size, info.st_mtime, Path(entry.path)))
                else:
                    raise ValueError('Legends of Norrath sources cannot contain links or special files: ' + relative)
    return rows


def _directory_root(engine, selected):
    # Search names first, so a selected client can be large without summing or
    # reading unrelated files. Only the discovered data subtree is inventoried.
    candidates, seen = [], 0
    stack = [selected]
    while stack:
        _check(engine)
        directory = stack.pop()
        archetypes = directory / 'archetypes'
        if archetypes.is_symlink():
            raise ValueError('Legends of Norrath archetypes cannot be a symbolic link')
        if archetypes.is_dir() and ((archetypes / 'index.dat').exists() or (archetypes / 'storage.dat').exists()):
            candidates.append(directory)
        with os.scandir(directory) as stream:
            for entry in stream:
                _check(engine)
                seen += 1
                if seen > MAX_ENTRIES:
                    raise ValueError('The selected folder has too many entries; select LegendsOfNorrath/data directly')
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    stack.append(Path(entry.path))
                elif not stat.S_ISREG(info.st_mode):
                    # Imported Wine prefixes may contain links unrelated to LoN.
                    # Do not traverse them; links within the selected data root
                    # are rejected later by _walk.
                    if directory == selected and selected.name.casefold() == 'data':
                        raise ValueError('Legends of Norrath data cannot contain symbolic links or special files')
    if len(candidates) != 1:
        if candidates:
            raise ValueError('Multiple Legends of Norrath data folders were found; select the intended data folder directly')
        raise ValueError('No Legends of Norrath data found; select the client, LegendsOfNorrath, or its data folder')
    return candidates[0]


def _zip_bounds(stream):
    """Check classic and ZIP64 central-directory bounds before ZipFile allocates."""
    stream.seek(0, os.SEEK_END)
    length = stream.tell()
    stream.seek(max(0, length - 65557))
    tail = stream.read(65557)
    position = tail.rfind(b'PK\x05\x06')
    if position < 0 or position + 22 > len(tail):
        raise ValueError('The selected archive is not a complete ZIP')
    disk, central_disk, disk_entries, entries, size, offset, comment = struct.unpack_from('<4H2IH', tail, position + 4)
    if position + 22 + comment != len(tail):
        raise ValueError('The selected ZIP has an invalid end record')
    if disk or central_disk or disk_entries != entries:
        raise ValueError('Split ZIP archives are not supported')
    if entries == 65535 or size == 0xffffffff or offset == 0xffffffff:
        eocd = length - len(tail) + position
        if eocd < 20:
            raise ValueError('Invalid ZIP64 archive')
        stream.seek(eocd - 20)
        locator = stream.read(20)
        if len(locator) != 20 or locator[:4] != b'PK\x06\x07':
            raise ValueError('Invalid ZIP64 locator')
        locator_disk, record_offset, disks = struct.unpack_from('<IQI', locator, 4)
        if locator_disk or disks != 1 or record_offset + 56 > eocd - 20:
            raise ValueError('Split or invalid ZIP64 archive')
        stream.seek(record_offset)
        record = stream.read(56)
        if len(record) != 56 or record[:4] != b'PK\x06\x06':
            raise ValueError('Invalid ZIP64 directory')
        record_size, _, _, disk, central_disk, disk_entries, entries, size, offset = struct.unpack_from('<QHHIIQQQQ', record, 4)
        if record_size < 44 or disk or central_disk or disk_entries != entries:
            raise ValueError('Split or invalid ZIP64 archive')
    if entries > MAX_ENTRIES or size > MAX_DIRECTORY_BYTES:
        raise ValueError('ZIP directory exceeds the supported memory limit; select the LegendsOfNorrath folder instead')
    if offset + size > length:
        raise ValueError('Truncated ZIP directory')
    # ZipFile trusts the central-directory byte stream rather than its declared
    # count. Count fixed headers before allowing its per-entry allocations.
    stream.seek(offset)
    end = offset + size
    actual = 0
    while stream.tell() < end:
        header = stream.read(46)
        if len(header) != 46 or header[:4] != b'PK\x01\x02':
            raise ValueError('Invalid ZIP central directory')
        name_bytes, extra_bytes, comment_bytes = struct.unpack_from('<HHH', header, 28)
        remaining = name_bytes + extra_bytes + comment_bytes
        if stream.tell() + remaining > end:
            raise ValueError('Truncated ZIP central directory')
        actual += 1
        if actual > MAX_ENTRIES:
            raise ValueError('ZIP directory exceeds the supported entry limit')
        stream.seek(remaining, os.SEEK_CUR)
    if actual != entries:
        raise ValueError('ZIP entry count does not match its directory')
    stream.seek(0)


def _zip_rows(engine, archive):
    rows, folded = [], set()
    for info in archive.infolist():
        _check(engine)
        directory = info.is_dir()
        if info.orig_filename != info.filename:
            raise ValueError('Unsafe ZIP filename')
        relative = _name(info.filename, directory)
        key = relative.casefold()
        if key in folded:
            raise ValueError('Duplicate or case-ambiguous ZIP path: ' + relative)
        folded.add(key)
        mode = stat.S_IFMT(info.external_attr >> 16)
        if mode not in (0, stat.S_IFDIR if directory else stat.S_IFREG):
            raise ValueError('Legends of Norrath ZIP cannot contain links or special files')
        if info.flag_bits & 1:
            raise ValueError('Encrypted ZIP archives are not supported')
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ValueError('Unsupported ZIP compression method')
        try:
            modified = datetime(*info.date_time).timestamp()
        except (ValueError, OverflowError, OSError):
            modified = None
        rows.append((relative, directory, info.file_size, modified, info))
    files = {row[0] for row in rows if not row[1]}
    candidates = set()
    for name in files:
        if name == 'archetypes/index.dat' or name.endswith('/archetypes/index.dat'):
            candidates.add(name[:-len('archetypes/index.dat')])
        elif name == 'archetypes/storage.dat' or name.endswith('/archetypes/storage.dat'):
            candidates.add(name[:-len('archetypes/storage.dat')])
    if len(candidates) != 1:
        if candidates:
            raise ValueError('Multiple Legends of Norrath data folders were found in this ZIP; select a more specific archive or folder')
        raise ValueError('No Legends of Norrath archetypes/index.dat or storage.dat found in the ZIP')
    prefix = next(iter(candidates))
    selected = []
    for name, directory, size, modified, info in rows:
        if prefix and not name.startswith(prefix):
            continue
        name = name[len(prefix):]
        if not name:
            continue
        selected.append((name, directory, size, modified, info))
    total = sum(row[2] for row in selected if not row[1])
    if total > MAX_TOTAL or any(row[2] > MAX_FILE for row in selected):
        raise ValueError('Legends of Norrath data exceeds the supported size')
    # Reject file/folder shadowing even if a malicious ZIP omitted directory entries.
    file_names = {row[0].casefold() for row in selected if not row[1]}
    for name, _, _, _, _ in selected:
        if any(parent.as_posix().casefold() in file_names for parent in PurePosixPath(name).parents if parent != PurePosixPath('.')):
            raise ValueError('ZIP contains a file where a parent folder is required')
    return prefix, selected


def _copy(engine, rows, target, opener):
    total = sum(row[2] for row in rows if not row[1])
    files = sum(not row[1] for row in rows)
    if shutil.disk_usage(target.parent).free < total + RESERVE:
        raise ValueError('Not enough free space to stage Legends of Norrath data')
    copied = count = 0
    for name, directory, size, modified, original in rows:
        _check(engine)
        destination = target / _name(name)
        if directory:
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with opener(original) as source, destination.open('xb') as out:
            before = None
            try:
                before = os.fstat(source.fileno())
            except (AttributeError, OSError):
                pass
            while True:
                _check(engine)
                block = source.read(min(BUFFER, size - written + 1))
                if not block:
                    break
                written += len(block)
                copied += len(block)
                if written > size:
                    raise ValueError('Legends of Norrath source changed size during import')
                out.write(block)
                _progress(engine, 'staging data', count, files, copied, total)
            if written != size:
                raise ValueError('Legends of Norrath source is truncated or changed during import')
            if before is not None:
                after = os.fstat(source.fileno())
                if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError('Legends of Norrath source changed during import; select it again')
            out.flush()
            os.fsync(out.fileno())
        destination.chmod(0o644)
        if modified is not None:
            os.utime(destination, (modified, modified))
        count += 1
        _progress(engine, 'staging data', count, files, copied, total)
    return {'files': count, 'bytes': copied}


class _Reader:
    def __init__(self, source):
        self.source = source

    def u(self):
        first = self.source.read(1)
        if not first:
            raise ValueError('Truncated LoN varint')
        value, extra = first[0] & 15, first[0] >> 5
        for index in range(extra):
            byte = self.source.read(1)
            if not byte:
                raise ValueError('Truncated LoN varint')
            value |= byte[0] << (4 + index * 8)
        value &= 0xffffffff
        return (~value & 0xffffffff) if first[0] & 16 else value

    def i(self):
        value = self.u()
        return value - 0x100000000 if value & 0x80000000 else value

    def s(self):
        length = self.u()
        if length > 0x100000:
            raise ValueError('Oversized LoN property string')
        value = self.source.read(length + 1)
        if len(value) != length + 1:
            raise ValueError('Truncated LoN property string')
        return value[:-1].decode('latin1')


def _archetype(raw):
    import io
    reader = _Reader(io.BytesIO(raw))
    for _ in range(4):
        reader.u()
    identifier = reader.u()
    reader.u(); reader.u()
    card = {'set': -1, 'subtype': ''}
    if reader.u() != 0:
        return identifier, card
    reader.u(); reader.u()
    if reader.u() != 0x17:
        raise ValueError('Invalid LoN PropertySet')
    reader.u()
    count = reader.u()
    if count > len(raw):
        raise ValueError('Oversized LoN property count')
    for _ in range(count):
        key = reader.u()
        reader.u(); reader.u()
        kind = reader.u()
        reader.u()
        if kind == 1:
            reader.u()
        elif kind == 2:
            value = reader.i()
            if key == 73:
                card['set'] = value
        elif kind == 3:
            value = reader.s()
            if key == 5:
                card['subtype'] = ('EverQuest Loot Card' if value == 'EverQuest Loot Card' else
                                   'Other Loot Card' if value.endswith(' Loot Card') else '')
        elif kind == 6:
            length = reader.u()
            if length > len(raw):
                raise ValueError('Oversized LoN integer array')
            for _ in range(length):
                reader.i()
        else:
            raise ValueError('Unsupported LoN property type')
    return identifier, card


def _inflate(stream, compressed, expanded, check=lambda: None):
    inflater = zlib.decompressobj()
    result = bytearray()
    remaining = compressed
    while remaining:
        check()
        block = stream.read(min(BUFFER, remaining))
        if not block:
            raise ValueError('Truncated LoN compressed record')
        remaining -= len(block)
        # The server reserves u + 64 bytes, and accepts any nonzero output that
        # fits. One compressed record is bounded independently of the full file.
        result.extend(inflater.decompress(block, expanded + 65 - len(result)))
        if len(result) > expanded + 64 or inflater.unconsumed_tail:
            raise ValueError('LoN compressed record exceeds its declared bound')
        if inflater.eof:
            break
    if not inflater.eof or not result:
        raise ValueError('Invalid LoN compressed record')
    return bytes(result)


def validate(engine, root):
    """Parse real card records and require LoadData's nonempty booster pools."""
    root = Path(root)
    result = {'valid': False, 'errors': [], 'warnings': [], 'parsed_archetypes': 0,
              'unreadable_archetypes': 0, 'booster_sets': 0,
              'server_initialization': 'pending_restart',
              'requirements': 'Triptych world/lon_service.cpp LoadData / ParseArchetype'}
    index, storage = root/'archetypes/index.dat', root/'archetypes/storage.dat'
    cards = {}
    if root.is_symlink():
        raise ValueError('LoN data root cannot be a symbolic link')
    try:
        for path in (index, storage):
            current = root
            for part in path.relative_to(root).parts:
                current = current/part
                if current.is_symlink():
                    raise ValueError('LoN card data cannot contain symbolic links')
        with _regular(index) as indices, _regular(storage) as records:
            size = os.fstat(records.fileno()).st_size
            reader = _Reader(indices)
            reader.u(); reader.u()
            count = 0
            while True:
                _check(engine)
                marker = indices.read(1)
                if not marker:
                    break
                indices.seek(-1, os.SEEK_CUR)
                count += 1
                if count > MAX_ENTRIES:
                    raise ValueError('LoN archetype index exceeds the supported record count')
                try:
                    reader.u()
                    compressed, expanded, offset = reader.u(), reader.u(), reader.u()
                except ValueError:
                    result['unreadable_archetypes'] += 1
                    break
                if offset + compressed > size or expanded == 0 or expanded > MAX_RECORD:
                    result['unreadable_archetypes'] += 1
                    continue
                try:
                    records.seek(offset)
                    raw = _inflate(records, compressed, expanded, lambda: _check(engine))
                    identifier, card = _archetype(raw)
                except (ValueError, zlib.error):
                    result['unreadable_archetypes'] += 1
                    continue
                cards[identifier] = card
                result['parsed_archetypes'] += 1
                if count % 100 == 0:
                    _progress(engine, 'validating card data', count)
    except OSError as error:
        result['errors'].append('Required archetypes/index.dat and archetypes/storage.dat could not be read: ' + str(error))
    except ValueError as error:
        # Cancellation must abort the job instead of being shown as bad content.
        _check(engine)
        result['errors'].append(str(error))
    pools = set()
    for identifier, card in cards.items():
        if identifier < 20000000 or card['set'] < 0:
            continue
        if card['subtype'].endswith(' Loot Card') and card['subtype'] != 'EverQuest Loot Card':
            continue
        pools.add(card['set'])
    result['booster_sets'] = len(pools)
    if result['parsed_archetypes'] == 0:
        result['errors'].append('No readable LoN card archetypes were found')
    if not pools:
        result['errors'].append('No usable LoN booster set was found; the server would refuse this card data')
    result['valid'] = not result['errors']
    if result['unreadable_archetypes']:
        result['warnings'].append(str(result['unreadable_archetypes']) + ' unreadable archetype records; the server skips these records')
    if not (root/'campaign.dat').is_file():
        result['warnings'].append('campaign.dat is absent; scenario rewards may be unavailable')
    if not (root/'decks').is_dir():
        result['warnings'].append('decks/ is absent; starter decks may be unavailable')
    result['message'] = ('Card data passes the server loader checks. Restart the server and verify the LoN listening message.'
                         if result['valid'] else 'Card data failed the server loader checks.')
    return result


def status(engine, args=None):
    deployment.require_custom(engine)
    result = deployment.status(engine, KIND)
    result['destination'] = (result.get('last_result') or {}).get('destinations', {}).get(KIND)
    result['destination_resolution_required'] = True
    result['source_candidates'] = []
    for candidate in ('client/current', 'sources/current/Release-NMS-Server/bin/Release/lon_data',
                      'sources/current/bin/Release/lon_data'):
        try:
            path = _confined(engine, candidate)
            if path.is_dir():
                result['source_candidates'].append(candidate)
        except ValueError:
            pass
    result['default_source'] = 'client/current'
    result['server_initialization'] = 'pending_restart'
    return result


def scan(engine, args):
    deployment.require_custom(engine)
    deployment.recover(engine)
    layout = deployment.destinations(engine, include_lon=True)
    source_name = args.get('source') or 'client/current'
    source = _confined(engine, source_name)
    source_kind = args.get('kind', 'auto')
    if source_kind == 'folder':
        source_kind = 'directory'
    if source_kind not in ('auto', 'directory', 'zip'):
        raise ValueError('Choose a folder or ZIP for Legends of Norrath data')
    directory = source.is_dir()
    if source_kind == 'directory' and not directory or source_kind == 'zip' and directory:
        raise ValueError('The selected Legends of Norrath source type changed')
    base = Path(engine.work)/'incoming/custom-deployment'
    current = Path(engine.work)
    for part in ('incoming', 'custom-deployment'):
        current = current/part
        if current.is_symlink():
            raise ValueError('Legends of Norrath staging cannot use symbolic links')
    base.mkdir(parents=True, exist_ok=True)
    stage = base/('lon-' + secrets.token_hex(12))
    stage.mkdir(mode=0o700)
    data = stage/'data'
    data.mkdir()
    try:
        _progress(engine, 'discovering data')
        if directory:
            discovered = _directory_root(engine, source)
            rows = _walk(engine, discovered)
            if stage == discovered or stage.is_relative_to(discovered):
                raise ValueError('Select the client or LegendsOfNorrath/data folder, not the staging root')
            copied = _copy(engine, rows, data, _regular)
            selected_root = str(discovered.relative_to(engine.work))
        else:
            with _regular(source) as stream:
                _zip_bounds(stream)
                with zipfile.ZipFile(stream) as archive:
                    selected_root, rows = _zip_rows(engine, archive)
                    copied = _copy(engine, rows, data, archive.open)
        validation = validate(engine, data)
        if not validation['valid']:
            raise ValueError('Invalid Legends of Norrath data: ' + '; '.join(validation['errors']))
        destination = layout['lon_data']
        rule = layout['lon_rule']
        if not rule['enabled']:
            validation['warnings'].append('Custom:LoNEnabled is disabled in the active ruleset; importing files does not enable or modify database rules')
        empty_dirs = [name for name, is_dir, _, _, _ in rows if is_dir]
        source_identity = {'path': source_name, 'kind': 'directory' if directory else 'zip',
                           'data_root': selected_root, 'staged_at': time.time()}
        deployment.atomic(engine, stage/'trasc-lon-stage.json',
                          {'format': 1, 'owner': KIND, 'data': 'data', 'complete': True})
        result = deployment.preview(engine, KIND,
                                    [{'name': KIND, 'source': data, 'destination': Path(destination)}],
                                    source_identity,
                                    extra={'validation': validation, 'staged': copied, 'directories': empty_dirs,
                                           'source': source_name, 'destination': destination,
                                           'lon_rule': rule, 'restart_required': True})
        _progress(engine, 'preview ready', copied['files'], copied['files'], copied['bytes'], copied['bytes'])
        return result
    except BaseException:
        shutil.rmtree(stage)
        raise


def files(engine, args):
    deployment.require_custom(engine)
    return deployment.details(engine, dict(args, kind=KIND))


def apply(engine, args):
    deployment.require_custom(engine)
    if args.get('include_new', True) is not True or args.get('include_changed', True) is not True:
        raise ValueError('LoN imports must repair all new and changed source files together to keep card index and storage consistent')
    preview = deployment.load_preview(engine, KIND, args.get('token'))
    if len(preview['groups']) != 1 or preview['groups'][0]['name'] != KIND:
        raise ValueError('Invalid Legends of Norrath deployment preview')
    validation = validate(engine, preview['groups'][0]['source'])
    if not validation['valid']:
        raise ValueError('Staged LoN card data no longer passes validation; scan again')
    def validate_installed():
        installed = validate(engine, preview['groups'][0]['destination'])
        if not installed['valid']:
            raise ValueError('Installed LoN card data failed validation; all changed files were rolled back: '
                             + '; '.join(installed['errors']))
        installed['world_log_before_restart'] = _world_log_identity(engine)
        return installed
    result = deployment.apply(engine, KIND, args, validate=validate_installed)
    # Validation happened inside the stopped-server transaction before commit.
    # A late Cancel must not turn a committed deployment into an apparent error.
    result.setdefault('validation', validation)
    result['restart_required'] = True
    result['server_initialization'] = 'pending_restart'
    result['cleanup'] = _cleanup_after_commit(engine, preview)
    result['message'] = ('Legends of Norrath files deployed and SHA-256 verified. Restart the server to initialize the card service.'
                         if validation['valid'] else 'Files were deployed, but the resulting card data is incomplete. Review the validation report and repair remaining files.')
    return result



def _cleanup_after_commit(engine, preview):
    """Delete only app-owned import staging after the durable commit.

    The user's external source and ordinary workspace/client directories are
    never removed. A cleanup problem is a warning, never a failed deployment.
    """
    result = {'removed': [], 'warnings': []}
    targets = []
    try:
        source = Path(preview['groups'][0]['source'])
        relative = source.relative_to(engine.work)
        if (len(relative.parts) == 4 and relative.parts[:2] == ('incoming', 'custom-deployment')
                and re.fullmatch(r'lon-[0-9a-f]{24}', relative.parts[2]) and relative.parts[3] == 'data'):
            targets.append((source.parent, 'trasc-lon-stage.json',
                            {'format': 1, 'owner': KIND, 'data': 'data', 'complete': True}))
    except (KeyError, TypeError, ValueError) as error:
        result['warnings'].append('Could not identify private LoN extraction staging: ' + str(error))
    try:
        selected = preview['source_identity']['path']
        parts = PurePosixPath(_name(selected)).parts
        if (len(parts) == 3 and parts[0] == 'incoming'
                and re.fullmatch(r'lon-import-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', parts[1])
                and parts[2] in ('data', 'source.zip')):
            identity = parts[1][len('lon-import-'):]
            targets.append((Path(engine.work)/parts[0]/parts[1], 'trasc-lon-import.json',
                            {'format': 1, 'profile': 'custom', 'id': identity,
                             'kind': 'zip' if parts[2] == 'source.zip' else 'directory',
                             'source': parts[2], 'complete': True}))
    except (KeyError, TypeError, ValueError) as error:
        result['warnings'].append('Could not identify private Android import staging: ' + str(error))
    for target, marker_name, expected in targets:
        try:
            confined = deployment.confined(engine, target)
            marker = deployment.read(engine, confined/marker_name)
            if marker != expected:
                raise ValueError('private import ownership marker did not match')
            if (confined/'.incomplete').exists():
                raise ValueError('private import is still incomplete')
            shutil.rmtree(confined)
            result['removed'].append(str(confined.relative_to(engine.work)))
        except (OSError, ValueError, TypeError) as error:
            result['warnings'].append('Private LoN staging was retained: ' + str(error))
    return result


def _world_log_identity(engine):
    path = Path(engine.work)/'logs/world.log'
    try:
        deployment.confined(engine, path)
        with _regular(path) as source:
            metadata = os.fstat(source.fileno())
        return {'device': metadata.st_dev, 'inode': metadata.st_ino,
                'bytes': metadata.st_size, 'modified_ns': metadata.st_mtime_ns}
    except (OSError, ValueError):
        return None


def _process_started(process):
    pid = getattr(process, 'pid', None)
    if not isinstance(pid, int) or pid <= 0:
        return None
    try:
        with open('/proc/' + str(pid) + '/stat', 'r') as source:
            record = source.read(8192)
        # The command name may contain spaces or parentheses. Field 22 is the
        # process start tick, with field 3 beginning after the final ')'.
        ticks = int(record[record.rfind(')') + 2:].split()[19])
        with open('/proc/uptime', 'r') as source:
            uptime = float(source.read(128).split()[0])
        return time.time() - uptime + ticks / os.sysconf('SC_CLK_TCK')
    except (OSError, ValueError, IndexError):
        return None


def _service_report(engine):
    report = {'state': 'pending_restart', 'evidence': None, 'world_running': False}
    process = getattr(engine, 'processes', {}).get('world')
    report['world_running'] = process is not None and process.poll() is None
    previous = deployment.status(engine, KIND)
    last_sync = previous.get('last_sync')
    baseline = ((previous.get('last_result') or {}).get('validation') or {}).get('world_log_before_restart')
    started = _process_started(process) if report['world_running'] else None
    report['world_started'] = started
    path = Path(engine.work)/'logs/world.log'
    try:
        deployment.confined(engine, path)
        with _regular(path) as source:
            metadata = os.fstat(source.fileno())
            if last_sync is not None and metadata.st_mtime < last_sync:
                return report
            if (baseline and baseline.get('bytes', 0) > 0
                    and (metadata.st_dev, metadata.st_ino) == (baseline.get('device'), baseline.get('inode'))
                    and (started is None or started < last_sync - 1)):
                report['log_warning'] = 'The pre-deployment world log has not been replaced by a fresh server start'
                return report
            # World logs rotate on every launch. Keep inspection bounded even
            # after a long session: startup and the latest output are useful.
            raw = source.read(65536)
            if metadata.st_size > 65536:
                source.seek(max(65536, metadata.st_size - 65536))
                raw += source.read(65536)
        text = re.sub(r'\x1b\[[0-9;]*m', '', raw.decode('utf-8', errors='replace'))
        success, failure, evidence = -1, -1, None
        for index, line in enumerate(text.splitlines()):
            if '[LoN] card service listening on port' in line:
                success, evidence = index, line.strip()[:512]
            if '[LoN] card service NOT started' in line or '[LoN] card data missing under' in line:
                failure = index
        if failure > success:
            report['state'] = 'failed'
            report['evidence'] = 'The latest world log reports missing card data or a card service startup failure'
        elif success >= 0:
            report['evidence'] = evidence
            if report['world_running'] and started is not None and (last_sync is None or started >= last_sync - 1):
                report['state'] = 'confirmed'
            elif report['world_running']:
                report['log_warning'] = 'The world process must be restarted after deployment before startup can be confirmed'
    except (OSError, ValueError) as error:
        report['log_warning'] = str(error)
    return report


def verify(engine, args=None):
    deployment.require_custom(engine)
    layout = deployment.destinations(engine, include_lon=True)
    destination = layout['lon_data']
    service = _service_report(engine)
    if not layout['lon_rule']['enabled']:
        service['state'] = 'disabled'
    return {'destination': destination, 'validation': validate(engine, destination),
            'lon_rule': layout['lon_rule'], 'service': service,
            'server_initialization': service['state'],
            'restart_required': service['state'] == 'pending_restart'}
