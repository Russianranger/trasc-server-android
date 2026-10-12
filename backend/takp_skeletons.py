"""Opt-in classic skeleton assets, adapted from MIT EqSkelePatcher.

Nick Gal's c3382bc492a9810bcbea50e78cda4463f514c95b changes SKE to LSK
in the WLD string table of gequip5.s3d and global6_chr.s3d. This bounded
implementation preserves every other asset's compressed bytes, every WLD
fragment and the user's exact original archives. Attribution/source accompany
the APK under takp-skeleton-patcher/. No game executable or DLL is modified.
"""
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import struct
import tempfile
import zlib

REVISION = 'c3382bc492a9810bcbea50e78cda4463f514c95b'
ARCHIVES = ('gequip5.s3d', 'global6_chr.s3d')
CACHES = ('gequip5.wld.txc', 'global6_chr.wld.txc')
FILES = ARCHIVES + CACHES
PRIVATE = '.trasc-skeletons'
MAX_ARCHIVE = 256 * 1024**2
MAX_WLD = 32 * 1024**2
MAX_DIRECTORY = 2 * 1024**2
MAX_ENTRIES = 10000
MAX_TOTAL = 512 * 1024**2
MAX_CACHE = 64 * 1024**2
DIRECTORY_CRC = 0x61580ac9
XOR_KEY = bytes.fromhex('953ac52a957a956a')


def _file(parent, name):
    from managed_content import client_file
    result = client_file(parent, name)
    if result.exists() and not result.is_file():
        raise ValueError('Skeleton assets require ordinary files: ' + name)
    return result


def _directory(path, create=False):
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError('Skeleton backup directory changed')
    if create:
        created = not path.exists()
        path.mkdir(mode=0o700, parents=False, exist_ok=True)
        path.chmod(0o700)
        _sync_dir(path)
        if created: _sync_dir(path.parent)
    return path


def _root(client, create=False):
    client = Path(client)
    _directory(client)
    if not client.is_dir():
        raise ValueError('Import the TAKP client first')
    return _directory(client / PRIVATE, create)


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _read_json(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Skeleton receipt must be an ordinary file')
    if not path.exists(): return None
    if path.stat().st_size > 65536:
        raise ValueError('Skeleton receipt is too large')
    try: return json.loads(path.read_text())
    except (ValueError, UnicodeError) as error:
        raise ValueError('Skeleton receipt is invalid') from error


def _json(path, value):
    _file(path.parent, path.name)
    data = json.dumps(value, sort_keys=True, indent=2).encode()
    if len(data) > 65536: raise ValueError('Skeleton receipt exceeds its limit')
    fd, temporary = tempfile.mkstemp(prefix='.new-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path); _sync_dir(path.parent)
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(temporary)


def _identity(client):
    record = _read_json(_file(client, 'trasc-client.json'))
    value = record.get('imported_at') if isinstance(record, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('Prepare an imported TAKP client before changing skeleton assets')
    return value


def filename_crc(name):
    value = 0
    for byte in name.encode('ascii') + b'\0':
        value ^= byte << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04c11db7 if value & 0x80000000 else 0)) & 0xffffffff
    return value


def _exact(stream, size):
    data = stream.read(size)
    if len(data) != size: raise ValueError('Truncated skeleton archive')
    return data


def _blocks(stream, offset, raw_size, index, collect=False):
    stream.seek(offset)
    total = 0
    result = bytearray() if collect else None
    while total < raw_size:
        if stream.tell() + 8 > index: raise ValueError('Skeleton archive block leaves its data section')
        compressed, raw = struct.unpack('<II', _exact(stream, 8))
        if not 0 < raw <= 8192 or raw > raw_size - total or not 0 < compressed <= 8320 or stream.tell() + compressed > index:
            raise ValueError('Unsupported skeleton archive block sizes')
        inflater = zlib.decompressobj()
        try: data = inflater.decompress(_exact(stream, compressed), raw + 1)
        except zlib.error as error: raise ValueError('Skeleton archive zlib data is invalid') from error
        if len(data) != raw or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
            raise ValueError('Skeleton archive decompression size differs')
        if collect: result.extend(data)
        total += raw
    return stream.tell(), result


def read_archive(path, wld_name):
    """Validate PFS ranges/zlib/directory without loading textures into memory."""
    if path.stat().st_size > MAX_ARCHIVE: raise ValueError('Skeleton archive exceeds 256 MiB')
    with path.open('rb') as stream:
        index, magic, version = struct.unpack('<I4sI', _exact(stream, 12))
        size = path.stat().st_size
        if magic != b'PFS ' or version != 0x20000 or not 12 <= index <= size - 4:
            raise ValueError('Unsupported TAKP skeleton S3D archive')
        stream.seek(index)
        count = struct.unpack('<I', _exact(stream, 4))[0]
        if not 2 <= count <= MAX_ENTRIES or index + 4 + count * 12 > size:
            raise ValueError('Invalid skeleton archive index')
        entries = [struct.unpack('<III', _exact(stream, 12)) for _ in range(count)]
        footer = stream.read(10)
        if footer and (len(footer) != 9 or not footer.startswith(b'STEVE')):
            raise ValueError('Unsupported skeleton archive footer')
        if len({entry[0] for entry in entries}) != count:
            raise ValueError('Duplicate skeleton archive CRC')
        directories = [entry for entry in entries if entry[0] == DIRECTORY_CRC]
        if len(directories) != 1 or directories[0][2] > MAX_DIRECTORY:
            raise ValueError('Invalid skeleton archive filename directory')
        if sum(entry[2] for entry in entries) > MAX_TOTAL:
            raise ValueError('Skeleton archive decompressed contents exceed 512 MiB')
        ranges = []
        for crc, offset, raw in entries:
            if not 12 <= offset <= index: raise ValueError('Invalid skeleton archive data offset')
            end, _ = _blocks(stream, offset, raw, index)
            if raw: ranges.append((offset, end))
        ranges.sort()
        if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
            raise ValueError('Overlapping skeleton archive files')
        _, directory = _blocks(stream, directories[0][1], directories[0][2], index, True)
        if len(directory) < 4: raise ValueError('Invalid skeleton filename directory')
        names_count = struct.unpack_from('<I', directory)[0]
        if names_count != count - 1: raise ValueError('Skeleton archive filename count differs')
        cursor, names, crcs = 4, {}, set()
        for _ in range(names_count):
            if cursor + 4 > len(directory): raise ValueError('Truncated skeleton filenames')
            length = struct.unpack_from('<I', directory, cursor)[0]; cursor += 4
            if not 2 <= length <= 256 or cursor + length > len(directory): raise ValueError('Invalid skeleton filename size')
            value = bytes(directory[cursor:cursor+length]); cursor += length
            if value[-1:] != b'\0' or b'\0' in value[:-1]: raise ValueError('Invalid skeleton filename terminator')
            try: name = value[:-1].decode('ascii')
            except UnicodeError as error: raise ValueError('Unsupported skeleton archive filename') from error
            if any(c in name for c in '/\\') or name in ('.', '..') or any(ord(c) < 32 for c in name):
                raise ValueError('Invalid skeleton archive filename')
            crc = filename_crc(name)
            if crc == DIRECTORY_CRC or crc in crcs or name.casefold() in names:
                raise ValueError('Ambiguous skeleton archive filenames')
            crcs.add(crc); names[name.casefold()] = crc
        if cursor != len(directory) or crcs != {entry[0] for entry in entries if entry[0] != DIRECTORY_CRC}:
            raise ValueError('Skeleton filename directory differs from index')
        crc = names.get(wld_name.casefold())
        if crc is None: raise ValueError('Skeleton archive is missing ' + wld_name)
        target = next(entry for entry in entries if entry[0] == crc)
        if not 28 <= target[2] <= MAX_WLD: raise ValueError('Skeleton WLD size exceeds its limit')
        _, wld = _blocks(stream, target[1], target[2], index, True)
    return {'index': index, 'entries': entries, 'footer': footer, 'target_crc': crc, 'wld': wld}


def patch_wld(data):
    """Same byte-length substitution, leaving all string references unchanged."""
    if not 28 <= len(data) <= MAX_WLD: raise ValueError('Unsupported skeleton WLD size')
    magic, version, count, _, _, hash_size, _ = struct.unpack_from('<7I', data)
    if magic != 0x54503d02 or version not in (0x15500, 0x1000c800) or not 1 <= count <= 500000 or not 1 <= hash_size <= len(data) - 28:
        raise ValueError('Unsupported TAKP skeleton WLD header')
    end = 28 + hash_size
    cursor = end
    for _ in range(count):
        if cursor + 8 > len(data): raise ValueError('Truncated skeleton WLD fragment')
        size = struct.unpack_from('<I', data, cursor)[0]
        if size < 4 or size % 4 or cursor + 8 + size > len(data): raise ValueError('Invalid skeleton WLD fragment boundaries')
        cursor += 8 + size
    # Unknown fragment bodies, name references and trailer are kept verbatim.
    table = bytearray(byte ^ XOR_KEY[i % 8] for i, byte in enumerate(data[28:end]))
    last = table.rfind(b'\0')
    if table[0] != 0 or last < 0 or (last != hash_size - 1 and (hash_size - last - 1 > 3 or any(data[28+last+1:end]))):
        raise ValueError('Unsupported skeleton WLD string table')
    strings = table[:last+1]
    count = strings.count(b'SKE')
    if not count: raise ValueError('No SKE model identifiers found; keep these client assets unchanged')
    changed = strings.replace(b'SKE', b'LSK')
    table[:last+1] = changed
    encoded = bytes(byte ^ XOR_KEY[i % 8] for i, byte in enumerate(table))
    return bytes(data[:28]) + encoded + bytes(data[end:]), count


def patch_archive(source, destination, wld_name):
    parsed = read_archive(source, wld_name)
    changed, count = patch_wld(parsed['wld'])
    with source.open('rb') as original, destination.open('xb') as output:
        output.write(_exact(original, 12))
        remaining = parsed['index'] - 12
        while remaining:
            chunk = _exact(original, min(1024**2, remaining)); output.write(chunk); remaining -= len(chunk)
        offset = output.tell()
        for cursor in range(0, len(changed), 8192):
            raw = changed[cursor:cursor+8192]; compressed = zlib.compress(raw)
            output.write(struct.pack('<II', len(compressed), len(raw))); output.write(compressed)
        index = output.tell()
        output.write(struct.pack('<I', len(parsed['entries'])))
        for crc, old_offset, raw in parsed['entries']:
            output.write(struct.pack('<III', crc, offset if crc == parsed['target_crc'] else old_offset, raw))
        output.write(parsed['footer']); output.seek(0); output.write(struct.pack('<I', index))
        output.flush(); os.fsync(output.fileno())
    _sync_dir(destination.parent)
    # Independently reopen the actual output, including zlib and directory.
    verified = read_archive(destination, wld_name)
    if bytes(verified['wld']) != changed:
        raise ValueError('Patched skeleton archive failed verification')
    return count


def _copy(source, target, mode=0o600, mtime_ns=None):
    _file(target.parent, target.name)
    fd, temporary = tempfile.mkstemp(prefix='.new-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as output, source.open('rb') as original:
            shutil.copyfileobj(original, output, 1024**2)
            output.flush(); os.fchmod(output.fileno(), mode)
            if mtime_ns is not None: os.utime(output.fileno(), ns=(mtime_ns, mtime_ns))
            os.fsync(output.fileno())
        os.replace(temporary, target); _sync_dir(target.parent)
    finally:
        with contextlib.suppress(FileNotFoundError): os.unlink(temporary)


def _metadata(path):
    if not path.exists(): return None
    if path.stat().st_size > (MAX_ARCHIVE if path.name.casefold() in ARCHIVES else MAX_CACHE):
        raise ValueError('Skeleton asset/cache exceeds its size limit: ' + path.name)
    info = path.stat()
    return {'name': path.name, 'sha256': _hash(path), 'bytes': info.st_size,
            'mode': info.st_mode & 0o777, 'mtime_ns': info.st_mtime_ns}


def _validate_metadata(value, name):
    if value is None: return
    if not isinstance(value, dict) or not isinstance(value.get('name'), str) or value['name'].casefold() != name or not isinstance(value.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', value['sha256']):
        raise ValueError('Invalid skeleton receipt asset')
    for key in ('bytes', 'mode', 'mtime_ns'):
        if isinstance(value.get(key), bool) or not isinstance(value.get(key), int) or value[key] < 0:
            raise ValueError('Invalid skeleton receipt metadata')
    if value['mode'] > 0o777 or value['mtime_ns'] > 2**63 - 1 or value['bytes'] > (MAX_ARCHIVE if name in ARCHIVES else MAX_CACHE):
        raise ValueError('Skeleton receipt asset exceeds its limit')


def _record(record, identity):
    if record is None: return
    if not isinstance(record, dict) or type(record.get('format')) is not int or record['format'] != 1 or record.get('state') not in ('enabled', 'off') or record.get('identity') != identity or not re.fullmatch('[0-9a-f]{32}', str(record.get('id', ''))):
        raise ValueError('Skeleton receipt belongs to a different imported client or changed format')
    if record['state'] == 'enabled':
        for group in ('originals', 'patched'):
            if not isinstance(record.get(group), dict) or set(record[group]) != set(FILES):
                raise ValueError('Incomplete skeleton receipt')
            for name, value in record[group].items(): _validate_metadata(value, name)
        if any(record['originals'][name] is None or record['patched'][name] is None for name in ARCHIVES):
            raise ValueError('Skeleton receipt is missing its archive pair')


def _saved(root, identifier, folder, name, metadata):
    parent = _directory(_directory(root / identifier) / folder)
    path = _file(parent, metadata['name'] if metadata else name)
    if metadata is not None and (not path.is_file() or path.stat().st_size != metadata['bytes'] or _hash(path) != metadata['sha256']):
        raise ValueError('Skeleton original/staged backup checksum failed: ' + name)
    return path


def _verify_originals(root, record):
    if record and record['state'] == 'enabled':
        for name, metadata in record['originals'].items():
            if metadata: _saved(root, record['id'], 'originals', name, metadata)


def recover(client):
    root = _root(client)
    if not root.exists(): return
    journal = _read_json(root / 'transaction.json')
    if journal is None: return
    identity = _identity(Path(client))
    if not isinstance(journal, dict) or set(journal) != {'format', 'id', 'identity', 'state', 'previous', 'next', 'files'} or type(journal.get('format')) is not int or journal['format'] != 1 or journal.get('identity') != identity or journal.get('state') not in ('pending', 'committed') or not re.fullmatch('[0-9a-f]{32}', str(journal.get('id', ''))):
        raise ValueError('Skeleton transaction needs manual recovery; its receipt changed')
    _record(journal['previous'], identity); _record(journal['next'], identity)
    if journal['next'] is None or journal['next']['id'] != journal['id']:
        raise ValueError('Skeleton transaction destination receipt is invalid')
    current = _read_json(root / 'current.json'); _record(current, identity)
    if current != journal['previous'] and current != journal['next']:
        raise ValueError('Skeleton current receipt differs from its transaction; manual recovery is required')
    if not isinstance(journal.get('files'), dict) or set(journal['files']) != set(FILES):
        raise ValueError('Skeleton transaction is incomplete')
    # Complete every path/backup check before touching any live asset.
    targets = {}
    for name, entry in journal['files'].items():
        if not isinstance(entry, dict) or set(entry) != {'before', 'after', 'target'} or not isinstance(entry.get('target'), str) or entry['target'].casefold() != name:
            raise ValueError('Invalid skeleton transaction target')
        for field in ('before', 'after'): _validate_metadata(entry[field], name)
        targets[name] = _file(Path(client), entry['target'])
        for field in ('before', 'after'):
            if entry[field]: _saved(root, journal['id'], field, name, entry[field])
    _verify_originals(root, journal.get('previous'))
    _verify_originals(root, journal.get('next'))
    if journal['next']['state'] == 'enabled':
        if journal['next']['originals'] != {name: entry['before'] for name, entry in journal['files'].items()} or journal['next']['patched'] != {name: entry['after'] for name, entry in journal['files'].items()}:
            raise ValueError('Enabled skeleton receipt differs from its transaction assets')
    elif journal['previous'] is None or journal['previous']['state'] != 'enabled':
        raise ValueError('Original skeleton restore transaction has no enabled receipt')
    if journal['state'] == 'pending':
        retained = _directory(_directory(root / journal['id']) / 'interrupted-changes', True)
        for name, entry in journal['files'].items():
            live = targets[name]
            if live.exists() and _hash(live) not in {value['sha256'] for value in (entry['before'], entry['after']) if value}:
                saved = _file(retained, live.name)
                if saved.exists() and _hash(saved) != _hash(live):
                    raise ValueError('Repeated interrupted skeleton changes require manual recovery')
                if not saved.exists(): _copy(live, saved)
        for name, entry in journal['files'].items():
            live, before = targets[name], entry['before']
            if before:
                _copy(_saved(root, journal['id'], 'before', name, before), live, before['mode'], before['mtime_ns'])
            else:
                live.unlink(missing_ok=True); _sync_dir(live.parent)
        if journal['previous'] is None:
            (root / 'current.json').unlink(missing_ok=True); _sync_dir(root)
        else: _json(root / 'current.json', journal['previous'])
    else:
        if _read_json(root / 'current.json') != journal['next']:
            raise ValueError('Committed skeleton receipt differs; manual recovery is required')
    (root / 'transaction.json').unlink(); _sync_dir(root)


def status(client):
    result = {'supported': True, 'enabled': False, 'state': 'off', 'available': False,
              'restore_available': False, 'patcher_revision': REVISION, 'files': list(ARCHIVES),
              'message': 'Import the complete TAKP client to use classic skeletons.'}
    if client is None: return result
    try:
        client = Path(client); root = _root(client)
        result['available'] = all(_file(client, name).is_file() for name in ARCHIVES)
        record = _read_json(root / 'current.json') if root.exists() else None
        _record(record, _identity(client))
        if record:
            result.update(state=record['state'], enabled=record['state'] == 'enabled',
                          restore_available=record['state'] == 'enabled', backup=PRIVATE + '/' + record['id'])
        result['message'] = ('Classic skeletons enabled; exact originals are retained.' if result['enabled'] else
                             ('Classic skeletons off. Enable validates both local archives before changing them.' if result['available'] else 'This client is missing gequip5.s3d or global6_chr.s3d; keep its assets unchanged.'))
        if root.exists() and _read_json(root / 'transaction.json') is not None:
            result.update(state='interrupted', message='An interrupted skeleton change must recover before launch.')
    except (ValueError, OSError) as error:
        result.update(state='error', message=str(error))
    return result


def verify_active(client):
    """Launch gate: detect changed archives/originals instead of overwriting them."""
    root = _root(client)
    if not root.exists(): return
    record = _read_json(root / 'current.json')
    _record(record, _identity(Path(client)))
    _verify_originals(root, record)
    if record and record['state'] == 'enabled':
        for name in ARCHIVES:
            path = _file(Path(client), record['patched'][name]['name'])
            metadata = record['patched'][name]
            if not path.is_file() or path.stat().st_size != metadata['bytes'] or _hash(path) != metadata['sha256']:
                raise ValueError('Skeleton assets changed after Enable; restore originals before launching')


def set_enabled(client, enabled, check_cancel=lambda: None):
    if not isinstance(enabled, bool): raise ValueError('Choose whether classic skeletons are enabled')
    client = Path(client); recover(client)
    identity = _identity(client); root = _root(client, True)
    previous = _read_json(root / 'current.json'); _record(previous, identity)
    if enabled and previous and previous['state'] == 'enabled':
        verify_active(client)
        return {'message': 'Classic skeletons are already enabled; originals remain retained.', 'skeletons': status(client)}
    if not enabled and (previous is None or previous['state'] == 'off'):
        return {'message': 'Classic skeletons are already off.', 'skeletons': status(client)}
    targets = {name: _file(client, name) for name in FILES}
    metadata = {name: _metadata(path) for name, path in targets.items()}
    if enabled and any(metadata[name] is None for name in ARCHIVES):
        raise ValueError('Classic skeletons need both gequip5.s3d and global6_chr.s3d')
    _verify_originals(root, previous)
    current_bytes = sum(value['bytes'] for value in metadata.values() if value)
    if enabled:
        # Before/original/after files + the largest atomic live-copy tempfile,
        # two appended bounded WLDs, and space reserved for rollback.
        required = current_bytes * 4 + 256 * 1024**2
    else:
        originals = [value['bytes'] for value in previous['originals'].values() if value]
        required = current_bytes + sum(originals) + max(originals) + 128 * 1024**2
    if shutil.disk_usage(client).free < required:
        raise ValueError('Not enough free space to preserve skeleton originals and recover an interrupted change')
    identifier = secrets.token_hex(16); folder = _directory(root / identifier, True)
    for name in ('before', 'after', 'originals'): _directory(folder / name, True)
    next_record = {'format': 1, 'id': identifier, 'identity': identity, 'state': 'enabled' if enabled else 'off', 'revision': REVISION}
    entries = {}
    activation_started = False
    try:
        for name, path in targets.items():
            check_cancel()
            before = metadata[name]
            if before: _copy(path, folder / 'before' / path.name)
            entries[name] = {'target': path.name, 'before': before, 'after': None}
        if enabled:
            originals, patched, replacements = {}, {}, {}
            for name, path in targets.items():
                check_cancel(); original = metadata[name]; originals[name] = original
                if original: _copy(folder / 'before' / path.name, folder / 'originals' / path.name)
                if name in ARCHIVES:
                    output = folder / 'after' / path.name
                    replacements[name] = patch_archive(folder / 'before' / path.name, output, name[:-4] + '.wld')
                    value = _metadata(output); value.update(mode=original['mode'], mtime_ns=original['mtime_ns'])
                    entries[name]['after'] = value; patched[name] = value
                else: patched[name] = None  # Remove only the two related texture caches.
            next_record.update(originals=originals, patched=patched, replacements=replacements)
        else:
            # Current archives/caches remain in this retained transaction's
            # before/ directory, including custom edits made after Enable.
            for name, original in previous['originals'].items():
                check_cancel()
                if original:
                    target = folder / 'after' / targets[name].name
                    _copy(_saved(root, previous['id'], 'originals', name, original), target)
                    value = dict(original); value['name'] = targets[name].name
                    entries[name]['after'] = value
        check_cancel()
        # Verify every snapshot and retained original before journalling a
        # change. Refuse a concurrent edit rather than overwrite it silently.
        for name, entry in entries.items():
            for field in ('before', 'after'):
                if entry[field]: _saved(root, identifier, field, name, entry[field])
            if _metadata(targets[name]) != entry['before']:
                raise ValueError('Skeleton assets changed during preparation; no live files were replaced')
        _verify_originals(root, next_record)
        _verify_originals(root, previous)
        if _read_json(root / 'current.json') != previous:
            raise ValueError('Skeleton receipt changed during preparation')
        largest = max(value['bytes'] for entry in entries.values() for value in (entry['before'], entry['after']) if value)
        if shutil.disk_usage(client).free < largest + 128 * 1024**2:
            raise ValueError('Not enough free space remains for atomic skeleton activation and rollback')
        journal = {'format': 1, 'id': identifier, 'identity': identity, 'state': 'pending',
                   'previous': previous, 'next': next_record, 'files': entries}
        _json(root / 'transaction.json', journal)  # Durable before any live mutation.
        activation_started = True
        for name, entry in entries.items():
            after = entry['after']; target = targets[name]
            if after: _copy(_saved(root, identifier, 'after', name, after), target, after['mode'], after['mtime_ns'])
            else: target.unlink(missing_ok=True); _sync_dir(client)
        _json(root / 'current.json', next_record)
        journal['state'] = 'committed'; _json(root / 'transaction.json', journal)
        (root / 'transaction.json').unlink(); _sync_dir(root)
    except Exception:
        if (root / 'transaction.json').exists():
            activation_started = True
            recover(client)
        if not activation_started:
            # A refused/cancelled preparation never changed the client. Avoid
            # accumulating full archive copies after repeated failed attempts.
            shutil.rmtree(folder); _sync_dir(root)
        raise
    return {'message': ('Classic skeletons enabled. Restart the client; originals and related texture caches are retained.' if enabled else
                         'Exact original skeleton archives and pre-enable texture caches restored. Changes made while enabled remain in the retained backup.'),
            'skeletons': status(client), 'backup': 'client/current/' + PRIVATE + '/' + identifier}
