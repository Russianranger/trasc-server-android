"""Bounded, reviewed filesystem deployments for the isolated Custom world.

Previews bind content hashes, selected source and runtime configuration. Every
replacement has a durable before-image and write-ahead journal; cancellation or
restart rolls the whole deployment back. No database writes or runtime pruning.
"""
import contextlib
import difflib
try:
    import fcntl
except ImportError:  # Windows can qualify the DLL compiler, not POSIX deployments.
    fcntl = None
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import threading
import time

FORMAT = 1
CHUNK = 64 * 1024
MAX_FILES = 100000
MAX_FILE = 32 * 1024**3
MAX_BYTES = 256 * 1024**3
MAX_RECORD = 128 * 1024**2
MAX_JOURNAL = 512 * 1024**2
RECOVERY = 'backups/custom-deployment'
_LOCK = threading.RLock()
_KINDS = {'quest_sync', 'quests', 'lon_data'}


def require_custom(engine):
    if engine.profile != 'custom':
        raise ValueError('This deployment belongs to TRASC Custom')


def check(engine):
    method = getattr(engine, 'check_cancel', None)
    if method:
        method()


def progress(engine, phase, **values):
    job = getattr(engine, 'current_job', None)
    if isinstance(job, dict):
        job['progress'] = dict(phase=phase, **values)


def name(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('Invalid deployment relative path')
    parts = PurePosixPath(value)
    if (not value or parts.is_absolute() or parts.as_posix() != value
            or '..' in parts.parts or any(x in value for x in ('\\', '\0', '\r', '\n'))
            or ':' in parts.parts[0]):
        raise ValueError('Unsafe deployment relative path: ' + value)
    return value


def confined(engine, path, destination=False):
    """Resolve lexically, rejecting symlinks in every existing ancestor."""
    root = Path(engine.work).absolute()
    original = Path(path)
    if not original.is_absolute():
        original = Path.cwd() / original
    ancestor = Path(original.anchor)
    for part in original.parts[1:]:
        ancestor = ancestor / part
        if ancestor.is_symlink():
            raise ValueError('Deployment paths cannot contain symbolic links: ' + str(original))
    path = Path(os.path.abspath(str(original)))
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError('Deployment paths must remain inside this world workspace')
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError('Deployment paths cannot contain symbolic links: ' + str(path))
        if parent != path and parent.exists() and not parent.is_dir():
            raise ValueError('Deployment ancestor is not a directory: ' + str(parent))
        if parent == root:
            break
    if destination and (not relative.parts or relative.parts[0] in
                        ('sources', 'database', 'backups', 'incoming', 'run', 'client', 'builds', 'exports')
                        or relative == Path('server')):
        raise ValueError('Configured deployment destination overlaps protected world files')
    if destination and len(relative.parts) > 1 and relative.parts[0] == 'server' and relative.parts[1] in (
            'bin', 'bin.staged', 'bin.previous', 'shared', 'maps', 'logs', 'export', 'backups'):
        raise ValueError('Configured deployment destination overlaps protected server files')
    return path


def _fsync(directory):
    fd = os.open(str(directory), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _mkdir(engine, path):
    path = confined(engine, path)
    if path.exists():
        if not path.is_dir():
            raise ValueError('Expected a deployment directory')
        return
    _mkdir(engine, path.parent)
    path.mkdir(mode=0o700)
    _fsync(path.parent)


def atomic(engine, path, value):
    path = confined(engine, path)
    _mkdir(engine, path.parent)
    temp = path.with_name('.' + path.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, sort_keys=True, separators=(',', ':'))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
        _fsync(path.parent)
    finally:
        if temp.exists():
            temp.unlink()


def read(engine, path):
    path = confined(engine, path)
    fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RECORD:
            raise ValueError('Invalid or oversized deployment record')
        return json.load(stream)


def digest(path, checker=lambda: None):
    fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
            raise ValueError('Deployment source is not a bounded regular file')
        value = hashlib.sha256()
        consumed = 0
        while True:
            checker()
            block = stream.read(CHUNK)
            if not block:
                break
            consumed += len(block)
            if consumed > before.st_size or consumed > MAX_FILE:
                raise ValueError('File grew while being inspected; scan again')
            value.update(block)
        after = os.fstat(stream.fileno())
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('File changed while being inspected; scan again')
        return value.hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _content_identity(entries):
    return identity({key: {field: value.get(field) for field in ('bytes', 'sha256', 'error')}
                     for key, value in entries.items()})


def _excluded(relative, exclusions):
    return any(relative == item or relative.startswith(item + '/') for item in exclusions)


def inventory(engine, root, exclude=()):
    root = confined(engine, root)
    exclusions = [name(item.rstrip('/')) for item in exclude]
    if not root.exists():
        return {}
    if not root.is_dir():
        return {'[root]': {'error': 'Expected a directory', 'bytes': None, 'modified': None}}
    result, total = {}, 0

    def walk(directory, prefix=''):
        nonlocal total
        check(engine)
        try:
            with os.scandir(directory) as stream:
                children = sorted(stream, key=lambda item: item.name)
        except OSError as error:
            result[prefix.rstrip('/') or '[root]'] = {'error': str(error), 'bytes': None, 'modified': None}
            return
        for entry in children:
            check(engine)
            relative = prefix + entry.name
            if _excluded(relative, exclusions):
                continue
            if len(result) >= MAX_FILES:
                raise ValueError('Deployment exceeds the 100,000 file inspection limit')
            try:
                name(relative)
                metadata = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(metadata.st_mode):
                    walk(Path(entry.path), relative + '/')
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    raise ValueError('Symbolic links and special files cannot be deployed')
                total += metadata.st_size
                if metadata.st_size > MAX_FILE or total > MAX_BYTES:
                    raise ValueError('Deployment exceeds the bounded file or total byte limit')
                result[relative] = {'bytes': metadata.st_size, 'modified': metadata.st_mtime,
                                    'sha256': digest(entry.path, lambda: check(engine)),
                                    'mode': stat.S_IMODE(metadata.st_mode)}
                progress(engine, 'scanning', files=len(result), bytes=total)
            except (OSError, ValueError) as error:
                check(engine)
                result[relative] = {'error': str(error), 'bytes': None, 'modified': None}
    walk(root)
    return result


def _directories(engine, root, exclusions):
    result = []
    if not root.is_dir():
        return result
    for directory, children, _ in os.walk(root, followlinks=False):
        check(engine)
        relative = Path(directory).relative_to(root).as_posix()
        children[:] = [item for item in children if not _excluded(
            (Path(relative) / item).as_posix() if relative != '.' else item, exclusions)]
        if relative != '.':
            confined(engine, directory)
            result.append(name(relative))
        if len(result) > MAX_FILES:
            raise ValueError('Deployment contains too many directories')
    return sorted(result, key=lambda item: (item.count('/'), item))


def _configuration(engine):
    runtime = confined(engine, Path(engine.work) / 'server')
    # File::FindEqemuConfigPath checks the launch cwd and its parent; PathManager
    # then changes cwd to that configuration's parent before launching LoN.
    candidates = (runtime / 'eqemu_config.json', runtime.parent / 'eqemu_config.json')
    for candidate in candidates:
        confined(engine, candidate)
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    if not path.exists():
        raise ValueError('Deploy the Custom server first so its active eqemu_config.json can resolve the content destinations')
    config = read(engine, path)
    runtime = path.parent
    server = config.get('server', {})
    if not isinstance(server, dict):
        raise ValueError('Invalid active server configuration')
    return runtime, config, server


def destinations(engine, include_lon=False):
    require_custom(engine)
    runtime, config, server = _configuration(engine)
    directories = server.get('directories', {})
    if not isinstance(directories, dict):
        raise ValueError('Invalid server directory configuration')
    result = {'runtime': str(runtime)}
    for key, array_key, default in (('quests', 'quest_paths', 'quests'), ('plugins', 'plugin_paths', 'plugins'),
                                    ('lua_modules', 'lua_module_paths', 'lua_modules')):
        values = directories.get(array_key, [directories.get(key, default)])
        if not isinstance(values, list) or not values or len(values) > 16:
            raise ValueError('Invalid configured ' + array_key + ' directories')
        paths = []
        for value in values:
            if not isinstance(value, str) or not value.strip() or any(c in value for c in ('\0', '\r', '\n')):
                raise ValueError('Invalid configured ' + key + ' directory')
            path = str(confined(engine, Path(value) if Path(value).is_absolute() else runtime / value, True))
            if path not in paths:
                paths.append(path)
        result[key], result[array_key] = paths[0], paths
    if include_lon:
        rule = lon_rule(engine)
        value = rule['path']
        result['lon_data'] = str(confined(engine, Path(value) if Path(value).is_absolute() else runtime / value, True))
        result['lon_rule'] = rule
    result['config_sha256'] = identity(config)
    return result


def _sql_rows(engine, query):
    raw = engine.mysql(query)
    if not isinstance(raw, str) or len(raw) > 65536:
        raise ValueError('Unexpected database rule lookup response')
    return [line.split('\t') for line in raw.splitlines()[1:] if line]


def lon_rule(engine):
    """Resolve precisely the ruleset overlays loaded by world_boot/RuleManager.

    Only SELECT statements are used. Starting an already-imported MariaDB is
    delegated to the engine's existing-only mode, which performs no DDL or seed.
    An unavailable database is never interpreted as a compiled-default rule.
    """
    require_custom(engine)
    ensure = getattr(engine, 'ensure_db', None)
    if ensure:
        ensure(existing_only=True)
    if not callable(getattr(engine, 'mysql', None)):
        raise ValueError('Open the existing Custom database to resolve the active LoNDataPath rule')
    try:
        selected_rows = _sql_rows(engine, "SELECT value FROM variables WHERE varname='RuleSet' LIMIT 1;")
        selected = selected_rows[0][0] if selected_rows else 'default'
        if not selected or len(selected) > 128 or any(c in selected for c in ('\0', '\r', '\n')):
            raise ValueError('Invalid active server ruleset name')
        literal = "'" + selected.replace("'", "''").replace('\\', '\\\\') + "'"
        sets = _sql_rows(engine, "SELECT ruleset_id,name FROM rule_sets WHERE name IN ('default'," + literal + ");")
        ids = {}
        for fields in sets:
            if len(fields) != 2 or not fields[0].isdigit():
                raise ValueError('Invalid database ruleset response')
            ids[fields[1]] = int(fields[0])
        # world_boot may have loaded default rules before its selected-ruleset
        # pass. Invalid/empty configurations cannot safely be guessed from the
        # compiled fallback; demand a consistent read-only view instead.
        if selected not in ids or 'default' not in ids:
            raise ValueError('Active/default server ruleset is missing; verify the existing database ruleset configuration')
        default_count = _sql_rows(engine, 'SELECT COUNT(*) FROM rule_values WHERE ruleset_id=' + str(ids['default']) + ';')
        if len(default_count) != 1 or len(default_count[0]) != 1 or not default_count[0][0].isdigit() or int(default_count[0][0]) == 0:
            raise ValueError('Default server ruleset is empty or unreadable; verify the existing database')
        order = ([ids['default']] if selected != 'default' else []) + [ids[selected]]
        path, enabled, path_origin = 'lon_data', False, 'compiled default'
        for ruleset_id in order:
            rows = _sql_rows(engine, "SELECT rule_name,rule_value FROM rule_values WHERE ruleset_id=" + str(ruleset_id)
                             + " AND rule_name IN ('Custom:LoNDataPath','Custom:LoNEnabled');")
            for fields in rows:
                if len(fields) != 2:
                    raise ValueError('Invalid LoN rule value')
                if fields[0] == 'Custom:LoNDataPath':
                    path, path_origin = fields[1], 'ruleset ' + str(ruleset_id)
                if fields[0] == 'Custom:LoNEnabled':
                    text = fields[1]
                    numeric = int(text) if re.fullmatch(r'-?[0-9]{1,10}', text) else 0
                    enabled = any(word in text for word in ('true', 'y', 'yes', 'on', 'enable', 'enabled')) or bool(
                        numeric if -(2**31) <= numeric <= 2**31 - 1 else 0)
        if not path.strip() or len(path) > 4096 or any(c in path for c in ('\0', '\r', '\n')):
            raise ValueError('Invalid active Custom:LoNDataPath value')
        return {'path': path, 'enabled': enabled, 'ruleset': selected, 'path_origin': path_origin,
                'ruleset_found': selected in ids}
    except (ValueError, OSError) as error:
        raise ValueError('Cannot resolve the existing Custom database LoN rules: ' + str(error)) from error


def _base(engine):
    return confined(engine, Path(engine.work) / RECOVERY)


@contextlib.contextmanager
def lease(engine):
    require_custom(engine)
    if fcntl is None:
        raise ValueError('Custom content deployment requires POSIX file locking; this host supports compiler qualification only')
    with _LOCK:
        path = confined(engine, Path(engine.work) / 'run/custom-deployment.lock')
        _mkdir(engine, path.parent)
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Another Custom deployment is running')
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def require_stopped(engine):
    if getattr(engine, 'server_running', lambda: False)():
        raise ValueError('Stop the Custom server before deploying files; restart it after deployment')


def _kind(kind):
    if kind not in _KINDS:
        raise ValueError('Unknown Custom deployment kind')
    return kind


def _token(value):
    if not re.fullmatch('[0-9a-f]{32}', str(value)):
        raise ValueError('Invalid deployment preview token')
    return value


def _marker(engine):
    path = confined(engine, Path(engine.work) / 'sources/current/trasc-source.json')
    return digest(path) if path.exists() else None


def _manifest_path(engine, kind):
    return _base(engine) / (_kind(kind) + '-latest.json')


def status(engine, kind):
    require_custom(engine)
    path = _manifest_path(engine, kind)
    result = {'profile': 'custom', 'kind': kind, 'last_sync': None, 'last_commit': None,
              'last_source_identity': None, 'recovery_required': any((_base(engine) / item).exists()
                  for item in ('journal.json', 'journal.events'))}
    if path.exists():
        value = read(engine, path)
        result.update(last_sync=value.get('finished'), last_commit=value.get('source_identity', {}).get('revision'),
                      last_source_identity=value.get('source_identity'), manifest=str(path),
                      last_source_fingerprint=value.get('source_fingerprint'), last_result=value.get('result'))
    return result


def _empty_summary():
    return dict(new=0, changed=0, matching=0, runtime_only=0, errors=0, conflicts=0, files=0, bytes=0,
                new_bytes=0, changed_bytes=0)


def preview(engine, kind, groups, source_identity, extra=None):
    require_custom(engine)
    _kind(kind)
    if not isinstance(source_identity, dict) or len(json.dumps(source_identity)) > 16384:
        raise ValueError('Invalid deployment source identity')
    with lease(engine):
        if any((_base(engine) / item).exists() for item in ('journal.json', 'journal.events')):
            raise ValueError('Recover the interrupted Custom deployment before scanning')
        if not isinstance(groups, list) or not 1 <= len(groups) <= 32:
            raise ValueError('Invalid deployment groups')
        layout = destinations(engine, include_lon=kind == 'lon_data')
        saved_groups, rows, summary, group_summaries = [], [], _empty_summary(), {}
        previous_path = _manifest_path(engine, kind)
        previous = read(engine, previous_path).get('entries', {}) if previous_path.exists() else {}
        destination_paths = set()
        for group in groups:
            group_name = name(group['name'])
            if '/' in group_name or group_name in group_summaries:
                raise ValueError('Duplicate or invalid deployment group')
            source = confined(engine, group['source'])
            destination = confined(engine, group['destination'], True)
            if not source.is_dir():
                raise ValueError('Deployment source directory is missing: ' + str(source))
            if source == destination or source in destination.parents or destination in source.parents:
                raise ValueError('Source and destination directories overlap')
            exclusions = [name(item.rstrip('/')) for item in group.get('exclude', [])]
            for other in saved_groups:
                other_destination = Path(other['destination'])
                if destination == other_destination:
                    raise ValueError('Deployment destinations overlap')
                if other_destination in destination.parents:
                    relative = destination.relative_to(other_destination).as_posix()
                    if not _excluded(relative, other['exclude']):
                        raise ValueError('Nested destination must be excluded from its parent group')
                if destination in other_destination.parents:
                    relative = other_destination.relative_to(destination).as_posix()
                    if not _excluded(relative, exclusions):
                        raise ValueError('Nested destination must be excluded from its parent group')
            sources = inventory(engine, source, exclusions)
            targets = inventory(engine, destination, exclusions)
            if len(rows) + len(set(sources) | set(targets)) > MAX_FILES:
                raise ValueError('Combined deployment exceeds the 100,000 file inspection limit')
            group_summary = _empty_summary()
            for relative in sorted(set(sources) | set(targets)):
                left, right = sources.get(relative), targets.get(relative)
                classification = ('error' if (left and left.get('error')) or (right and right.get('error')) else
                                  'runtime-only' if left is None else 'new' if right is None else
                                  'matching' if left['sha256'] == right['sha256'] else 'changed')
                baseline = previous.get(str(destination / relative))
                conflict = bool(classification == 'changed' and baseline and right['sha256'] != baseline['sha256'])
                row = {'group': group_name, 'path': relative, 'classification': classification,
                       'source': left, 'destination': right, 'conflict': conflict}
                rows.append(row)
                field = {'runtime-only': 'runtime_only', 'error': 'errors'}.get(classification, classification)
                group_summary[field] += 1
                group_summary['conflicts'] += int(conflict)
                if classification in ('new', 'changed'):
                    group_summary['files'] += 1
                    group_summary['bytes'] += left['bytes']
                    group_summary[classification + '_bytes'] += left['bytes']
                if left is not None:
                    target = str(destination / relative)
                    if target in destination_paths:
                        raise ValueError('Two groups would write the same destination')
                    destination_paths.add(target)
            saved_groups.append({'name': group_name, 'source': str(source), 'destination': str(destination),
                                 'exclude': exclusions, 'source_inventory': sources, 'destination_inventory': targets,
                                 'directories': _directories(engine, source, exclusions)})
            group_summaries[group_name] = group_summary
            for key, value in group_summary.items():
                summary[key] += value
        token = secrets.token_hex(16)
        value = {'format': FORMAT, 'profile': 'custom', 'kind': kind, 'token': token, 'created': time.time(),
                 'config_sha256': layout['config_sha256'], 'source_marker_sha256': _marker(engine),
                 'source_identity': source_identity, 'source_fingerprint': identity({group['name']:
                    _content_identity(group['source_inventory']) for group in saved_groups}),
                 'groups': saved_groups, 'rows': rows, 'summary': summary, 'group_summaries': group_summaries,
                 'extra': extra or {}, 'lon_rule': layout.get('lon_rule')}
        atomic(engine, _base(engine) / 'previews' / (token + '.json'), value)
        return report(value)


def report(value):
    return {key: value[key] for key in ('profile', 'kind', 'token', 'created', 'source_identity',
            'source_fingerprint', 'summary', 'group_summaries', 'extra')} | {
                'destinations': {group['name']: group['destination'] for group in value['groups']},
                'total_files': len(value['rows']), 'transfer_files': value['summary']['files'],
                'transfer_bytes': value['summary']['bytes']}


def load_preview(engine, kind, token):
    require_custom(engine)
    value = read(engine, _base(engine) / 'previews' / (_token(token) + '.json'))
    if value.get('format') != FORMAT or value.get('profile') != 'custom' or value.get('kind') != _kind(kind) or value.get('token') != token:
        raise ValueError('Deployment preview belongs to a different profile or action')
    return value


def details(engine, args, kind=None):
    kind = kind or args.get('kind', 'quest_sync')
    value = load_preview(engine, kind, args.get('token'))
    rows = value['rows']
    classification = args.get('classification', args.get('filter', 'all'))
    if classification not in ('all', '', None):
        rows = [row for row in rows if row['classification'] == classification or classification == 'conflict' and row['conflict']]
    query = str(args.get('query', '')).casefold()[:256]
    if query:
        rows = [row for row in rows if query in row['path'].casefold()]
    if args.get('group'):
        rows = [row for row in rows if row['group'] == args['group']]
    sort = args.get('sort', 'filename')
    def key(row):
        source, destination = row.get('source') or {}, row.get('destination') or {}
        if sort in ('size', 'size_desc'):
            return (-(source.get('bytes') or destination.get('bytes') or 0), row['path'])
        if sort in ('modified', 'modified_desc'):
            return (-(source.get('modified') or destination.get('modified') or 0), row['path'])
        if sort == 'classification':
            return (row['classification'], row['path'])
        return (row['path'].casefold(), row['group'])
    rows = sorted(rows, key=key)
    offset = max(0, min(int(args.get('offset', 0)), MAX_FILES))
    limit = max(1, min(int(args.get('limit', 100)), 500))
    return {'token': value['token'], 'rows': rows[offset:offset + limit], 'files': rows[offset:offset + limit],
            'total': len(rows), 'offset': offset, 'limit': limit}


def diff(engine, kind, args):
    value = load_preview(engine, kind, args.get('token'))
    relative = name(args.get('path'))
    row = next((item for item in value['rows'] if item['path'] == relative and item['group'] == args.get('group')), None)
    if not row or row['classification'] != 'changed':
        raise ValueError('Choose a changed file from this preview')
    if Path(relative).suffix.lower() not in ('.pl', '.pm', '.lua', '.txt', '.conf', '.cfg', '.ini', '.json', '.xml', '.csv'):
        raise ValueError('Text preview is available for scripts and configuration files')
    group = next(item for item in value['groups'] if item['name'] == row['group'])
    texts = []
    for side, root in (('destination', group['destination']), ('source', group['source'])):
        path = confined(engine, Path(root) / relative)
        expected = row[side]
        if expected['bytes'] > 256 * 1024:
            raise ValueError('File is too large for a bounded text diff; hashes remain available')
        if digest(path, lambda: check(engine)) != expected['sha256']:
            raise ValueError('File changed since preview; scan again')
        with path.open('rb') as stream:
            data = stream.read(256 * 1024 + 1)
        if b'\0' in data:
            raise ValueError('This file is not plain text')
        texts.append(data.decode('utf-8', errors='replace').splitlines(keepends=True))
    lines, length = [], 0
    for line in difflib.unified_diff(texts[0], texts[1], fromfile='runtime/' + relative, tofile='source/' + relative):
        length += len(line)
        if length > 256 * 1024:
            lines.append('\n[Diff truncated at 256 KiB]\n')
            break
        lines.append(line)
    return {'path': relative, 'group': row['group'], 'diff': ''.join(lines)}


def _copy(engine, source, target, expected, *, cancel=True, on_bytes=None):
    source, target = confined(engine, source), confined(engine, target)
    checker = (lambda: check(engine)) if cancel else (lambda: None)
    _mkdir(engine, target.parent)
    fd = os.open(str(source), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        out_fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'rb') as inp, os.fdopen(out_fd, 'wb') as out:
            fd = None
            metadata = os.fstat(inp.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_FILE:
                raise ValueError('Deployment copy source is not a bounded file')
            value = hashlib.sha256()
            consumed = 0
            while True:
                checker()
                block = inp.read(CHUNK)
                if not block:
                    break
                consumed += len(block)
                if consumed > metadata.st_size or consumed > MAX_FILE:
                    raise ValueError('Source file grew during transfer; deployment rolled back')
                value.update(block)
                out.write(block)
                if on_bytes:
                    on_bytes(len(block))
            if value.hexdigest() != expected:
                raise ValueError('Source file changed during transfer; deployment rolled back')
            out.flush()
            os.fsync(out.fileno())
        if digest(target, checker) != expected:
            raise ValueError('Copied file hash verification failed')
    finally:
        if fd is not None:
            os.close(fd)


def _fingerprint_matches(engine, value):
    layout = destinations(engine, include_lon=value['kind'] == 'lon_data')
    if (layout['config_sha256'] != value['config_sha256'] or _marker(engine) != value['source_marker_sha256']
            or layout.get('lon_rule') != value.get('lon_rule')):
        raise ValueError('Source selection or runtime configuration changed; scan again')
    for group in value['groups']:
        for side in ('source', 'destination'):
            actual = inventory(engine, group[side], group['exclude'])
            if _content_identity(actual) != _content_identity(group[side + '_inventory']):
                raise ValueError('Source or runtime files changed since preview; scan again')


def _ensure_dirs(engine, directory, journal, journal_path):
    directory = confined(engine, directory)
    if directory.exists():
        if not directory.is_dir():
            raise ValueError('Destination directory collides with a file')
        return
    confined(engine, directory, True)
    if directory.parent != Path(engine.work) / 'server':
        _ensure_dirs(engine, directory.parent, journal, journal_path)
    if len(journal['created_directories']) >= MAX_FILES:
        raise ValueError('Deployment creates too many directories')
    _journal_event(engine, {'directory': str(directory)})
    journal['created_directories'].append(str(directory))
    directory.mkdir(mode=0o755)
    _fsync(directory.parent)


def _journal_event(engine, value):
    """Append and fsync before each mutation, avoiding quadratic JSON rewrites."""
    path = confined(engine, _base(engine) / 'journal.events')
    encoded = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if len(encoded) > 65536 or path.stat().st_size + len(encoded) > MAX_JOURNAL:
        raise ValueError('Deployment recovery journal exceeds its bounded size')
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'ab') as out:
        out.write(encoded)
        out.flush()
        os.fsync(out.fileno())


def _read_journal(engine, path):
    journal = read(engine, path)
    if journal.get('phase') in ('committed', 'rolled_back'):
        # Committing writes the complete journal once, making event removal safe.
        return journal
    events = confined(engine, _base(engine) / 'journal.events')
    if not events.is_file():
        raise ValueError('Interrupted deployment event journal is missing')
    if events.stat().st_size > MAX_JOURNAL:
        raise ValueError('Oversized deployment recovery event journal')
    journal['operations'], journal['created_directories'] = [], []
    fd = os.open(str(events), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        for _ in range(MAX_FILES * 2 + 1):
            line = stream.readline(65537)
            if not line:
                return journal
            if len(line) > 65536 or not line.endswith(b'\n'):
                # A torn final append occurred before its mutation was allowed.
                # A complete prefix remains sufficient to restore prior writes.
                if stream.read(1):
                    raise ValueError('Corrupt deployment recovery event journal')
                return journal
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError) as error:
                raise ValueError('Corrupt deployment recovery event record') from error
            if isinstance(event, dict) and set(event) == {'operation'}:
                journal['operations'].append(event['operation'])
            elif isinstance(event, dict) and set(event) == {'directory'}:
                journal['created_directories'].append(event['directory'])
            else:
                raise ValueError('Invalid deployment recovery event')
        raise ValueError('Deployment recovery event count exceeds its limit')


def _remove_journal(engine):
    # A committed header contains complete operations; events can be unlinked
    # first without losing restart recovery. Applying journals only get removed
    # after their rollback has completed in memory.
    for filename in ('journal.events', 'journal.json'):
        path = confined(engine, _base(engine) / filename)
        if path.exists():
            path.unlink()
            _fsync(path.parent)


def apply(engine, kind, args, validate=None):
    require_custom(engine)
    require_stopped(engine)
    with lease(engine):
        journal_path = _base(engine) / 'journal.json'
        event_path = _base(engine) / 'journal.events'
        if journal_path.exists() or event_path.exists():
            raise ValueError('Recover the interrupted deployment before synchronizing again')
        value = load_preview(engine, kind, args.get('token'))
        if value['summary']['errors']:
            raise ValueError('Resolve every inspection error before deploying')
        selected = [row for row in value['rows'] if row['classification'] == 'new' and args.get('include_new', True)
                    or row['classification'] == 'changed' and args.get('include_changed', True)]
        if any(row['classification'] == 'changed' for row in selected) and args.get('confirm_overwrite') is not True:
            raise ValueError('Confirm the preview before replacing changed destination files')
        if any(row['conflict'] for row in selected) and args.get('approve_conflicts') is not True:
            raise ValueError('Locally modified files require explicit conflict approval')
        _fingerprint_matches(engine, value)
        require_stopped(engine)
        transfer_bytes = sum(row['source']['bytes'] for row in selected)
        backup_bytes = sum((row.get('destination') or {}).get('bytes', 0) for row in selected)
        if shutil.disk_usage(engine.work).free < transfer_bytes + backup_bytes + 64 * 1024**2:
            raise ValueError('Not enough free space for the deployment and protected rollback copies')
        token = value['token']
        backup = _base(engine) / 'history' / token
        _mkdir(engine, backup)
        manifest_path = _manifest_path(engine, kind)
        old_manifest = read(engine, manifest_path) if manifest_path.exists() else None
        journal = {'format': FORMAT, 'profile': 'custom', 'kind': kind, 'token': token,
                   'phase': 'applying', 'started': time.time(), 'operations': [], 'created_directories': [],
                   'old_manifest': old_manifest}
        fd = os.open(str(event_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.fsync(fd)
        os.close(fd)
        _fsync(event_path.parent)
        atomic(engine, journal_path, journal)
        done_bytes = 0
        groups = {group['name']: group for group in value['groups']}
        try:
            # Preserve even empty directories from the selected source tree.
            if args.get('include_new', True):
                for group in value['groups']:
                    _ensure_dirs(engine, Path(group['destination']), journal, journal_path)
                    for directory in group['directories']:
                        check(engine)
                        _ensure_dirs(engine, Path(group['destination']) / name(directory), journal, journal_path)
            for index, row in enumerate(selected):
                check(engine)
                require_stopped(engine)
                group = groups[row['group']]
                source = confined(engine, Path(group['source']) / name(row['path']))
                target = confined(engine, Path(group['destination']) / row['path'], True)
                _ensure_dirs(engine, target.parent, journal, journal_path)
                before = row['destination']['sha256'] if row.get('destination') else None
                if (digest(target, lambda: check(engine)) if target.exists() else None) != before:
                    raise ValueError('Destination changed during deployment; scan again')
                old = backup / (str(index) + '.original') if before else None
                if old:
                    _copy(engine, target, old, before)
                    old.chmod(0o400)
                    _fsync(old.parent)
                temp = target.with_name('.' + target.name + '.trasc-deploy-' + token)
                if temp.exists() or temp.is_symlink():
                    raise ValueError('Temporary deployment file already exists')
                operation = {'target': str(target), 'source': str(source), 'before': before,
                             'after': row['source']['sha256'], 'backup': str(old) if old else None,
                             'temp': str(temp), 'mode': (row.get('destination') or row['source']).get('mode', 0o644),
                             'modified': (row.get('destination') or row['source']).get('modified'),
                             'restore_temp': str(target.with_name('.' + target.name + '.restore-' + token)) if before else None}
                if operation['restore_temp'] is not None:
                    reserved = confined(engine, operation['restore_temp'])
                    if reserved.exists() or reserved.is_symlink():
                        raise ValueError('Recovery temporary path is already occupied before deployment')
                _journal_event(engine, {'operation': operation})
                journal['operations'].append(operation)
                def copied(amount):
                    nonlocal done_bytes
                    done_bytes += amount
                    progress(engine, 'copying', files=index, total_files=len(selected), bytes=done_bytes, total_bytes=transfer_bytes,
                             path=row['path'])
                _copy(engine, source, temp, operation['after'], on_bytes=copied)
                # Check immediately before the atomic replacement as well.
                if (digest(target) if target.exists() else None) != before:
                    raise ValueError('Destination changed before replacement; scan again')
                temp.chmod(operation['mode'] & 0o777)
                if row['source'].get('modified') is not None:
                    os.utime(temp, (row['source']['modified'], row['source']['modified']))
                confined(engine, target, True)
                os.replace(temp, target)
                _fsync(target.parent)
                if digest(target, lambda: check(engine)) != operation['after']:
                    raise ValueError('Installed file hash verification failed')
            validation_result = None
            if validate is not None:
                check(engine)
                progress(engine, 'validating', files=len(selected), bytes=transfer_bytes, total_bytes=transfer_bytes)
                validation_result = validate()
            entries = dict((old_manifest or {}).get('entries', {}))
            selected_keys = {(row['group'], row['path']) for row in selected}
            for row in value['rows']:
                group = groups[row['group']]
                entry_key = str(Path(group['destination']) / row['path'])
                if row['classification'] == 'matching' or (row['group'], row['path']) in selected_keys:
                    entries[entry_key] = {
                        'sha256': row['source']['sha256'], 'bytes': row['source']['bytes'],
                        'group': row['group'], 'path': row['path'], 'source_modified': row['source'].get('modified'),
                        'previous_destination_modified': (row.get('destination') or {}).get('modified'), 'managed': True}
                elif row['classification'] == 'changed' and entry_key not in entries:
                    # A new-only deployment must also notice future edits to a
                    # skipped existing script. Record its observed baseline once;
                    # subsequent skipped deployments must not acknowledge away
                    # an outstanding local conflict.
                    entries[entry_key] = {
                        'sha256': row['destination']['sha256'], 'bytes': row['destination']['bytes'],
                        'group': row['group'], 'path': row['path'], 'managed': False,
                        'previous_destination_modified': row['destination'].get('modified')}
            result = report(value) | {'copied_files': len(selected), 'copied_bytes': transfer_bytes,
                                      'backup': str(backup), 'finished': time.time(), 'restart_required': True,
                                      'cancelled': False, 'rolled_back': False}
            if validation_result is not None:
                result['validation'] = validation_result
            manifest = {'format': FORMAT, 'profile': 'custom', 'kind': kind, 'token': token,
                        'source_identity': value['source_identity'], 'source_fingerprint': value['source_fingerprint'],
                        'started': journal['started'], 'finished': result['finished'], 'entries': entries,
                        'config_sha256': value['config_sha256'], 'result': result}
            check(engine)
            atomic(engine, backup / 'manifest.json', manifest)
            atomic(engine, manifest_path, manifest)
            journal['phase'] = 'committed'
            atomic(engine, journal_path, journal)
            _remove_journal(engine)
            progress(engine, 'done', files=len(selected), total_files=len(selected), bytes=transfer_bytes, total_bytes=transfer_bytes)
            return result
        except BaseException as error:
            # KeyboardInterrupt/SystemExit model process interruption in tests;
            # an actual process kill is recovered from the same durable journal.
            failure = report(value) | {
                'failed': True, 'error': str(error), 'finished': time.time(),
                'attempted_files': len(journal['operations']), 'attempted_bytes': done_bytes,
                'copied_files': None, 'copied_bytes': None, 'backup': str(backup),
                'rolled_back': False, 'recovery_required': True}
            job = getattr(engine, 'current_job', None)
            if isinstance(job, dict):
                job['failure'] = failure
            _rollback(engine, journal)
            failure.update(rolled_back=True, recovery_required=False, copied_files=0, copied_bytes=0)
            atomic(engine, backup / 'failure.json', failure)
            raise


def _valid_sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)


def _validate_journal(engine, value):
    if (not isinstance(value, dict) or value.get('format') != FORMAT or value.get('profile') != 'custom'
            or value.get('phase') not in ('applying', 'committed', 'rolled_back')):
        raise ValueError('Invalid Custom deployment recovery journal')
    _kind(value.get('kind'))
    _token(value.get('token'))
    operations = value.get('operations')
    if not isinstance(operations, list) or len(operations) > MAX_FILES:
        raise ValueError('Invalid deployment recovery operations')
    targets = set()
    backup_root = _base(engine) / 'history' / value['token']
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError('Invalid deployment recovery file record')
        target = confined(engine, operation.get('target', ''), True)
        if str(target) in targets or not _valid_sha(operation.get('after')) or operation.get('before') is not None and not _valid_sha(operation['before']):
            raise ValueError('Invalid deployment recovery file identity')
        targets.add(str(target))
        expected_temp = target.with_name('.' + target.name + '.trasc-deploy-' + value['token'])
        if operation.get('temp') != str(expected_temp):
            raise ValueError('Invalid deployment temporary path')
        confined(engine, expected_temp)
        if operation.get('before') is not None:
            if operation.get('backup') != str(backup_root / (str(index) + '.original')):
                raise ValueError('Invalid protected deployment backup path')
            confined(engine, operation['backup'])
            expected_restore = target.with_name('.' + target.name + '.restore-' + value['token'])
            if operation.get('restore_temp') != str(expected_restore):
                raise ValueError('Invalid deployment rollback temporary path')
            confined(engine, expected_restore)
        elif operation.get('restore_temp') is not None:
            raise ValueError('Unexpected rollback temporary path for a new file')
    directories = value.get('created_directories', [])
    if not isinstance(directories, list) or len(directories) > MAX_FILES * 4:
        raise ValueError('Invalid deployment directory recovery record')
    for directory in directories:
        confined(engine, directory, True)


def _rollback(engine, journal):
    _validate_journal(engine, journal)
    # Validate every before-image and live target before touching any file.
    for operation in journal['operations']:
        target = confined(engine, operation['target'], True)
        actual = digest(target) if target.exists() else None
        if actual not in (operation['before'], operation['after']):
            raise ValueError('Recovery stopped: a deployed file was edited externally; protected backups remain at ' + str(_base(engine)))
        if operation['before'] is not None and digest(confined(engine, operation['backup'])) != operation['before']:
            raise ValueError('Recovery stopped: protected backup hash is invalid')
        if operation.get('restore_temp') is not None:
            temporary = confined(engine, operation['restore_temp'])
            if temporary.exists():
                info = temporary.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_size > Path(operation['backup']).stat().st_size:
                    raise ValueError('Recovery stopped: invalid recorded rollback temporary file')
    for operation in reversed(journal['operations']):
        target = confined(engine, operation['target'], True)
        actual = digest(target) if target.exists() else None
        if actual != operation['before']:
            if operation['before'] is None:
                target.unlink()
                _fsync(target.parent)
            else:
                temp = confined(engine, operation['restore_temp'])
                try:
                    if temp.exists() and digest(temp) != operation['before']:
                        # The write-ahead operation reserved this exact path
                        # before deployment. Only its bounded, app-owned partial
                        # rollback output may be discarded and copied again.
                        temp.unlink()
                        _fsync(temp.parent)
                    if not temp.exists():
                        _copy(engine, operation['backup'], temp, operation['before'], cancel=False)
                    temp.chmod(int(operation.get('mode', 0o644)) & 0o777)
                    if operation.get('modified') is not None:
                        os.utime(temp, (operation['modified'], operation['modified']))
                    os.replace(temp, target)
                    _fsync(target.parent)
                finally:
                    if temp.exists():
                        temp.unlink()
        restore_temp = operation.get('restore_temp')
        if restore_temp is not None and confined(engine, restore_temp).exists():
            Path(restore_temp).unlink()
            _fsync(Path(restore_temp).parent)
        temp = confined(engine, operation['temp'])
        if temp.exists():
            temp.unlink()
            _fsync(temp.parent)
    for directory in reversed(journal.get('created_directories', [])):
        path = confined(engine, directory, True)
        if path.exists():
            try:
                path.rmdir()
                _fsync(path.parent)
            except OSError:
                pass  # Empty-directory removal never deletes runtime content.
    latest = _manifest_path(engine, journal['kind'])
    if journal.get('old_manifest') is not None:
        atomic(engine, latest, journal['old_manifest'])
    elif latest.exists():
        latest.unlink()
        _fsync(latest.parent)
    atomic(engine, _base(engine) / 'history' / journal['token'] / 'rollback.json',
           {'format': FORMAT, 'profile': 'custom', 'kind': journal['kind'], 'token': journal['token'],
            'rolled_back': True, 'finished': time.time(), 'files': len(journal['operations'])})
    # Mark the already-restored state durably before removing its events. A
    # crash during this cleanup may safely re-run rollback using the full header.
    saved = dict(journal, phase='rolled_back')
    atomic(engine, _base(engine) / 'journal.json', saved)
    _remove_journal(engine)


def recover(engine):
    if engine.profile != 'custom':
        return {'recovered': False}
    with lease(engine):
        path = _base(engine) / 'journal.json'
        if not path.exists():
            events = confined(engine, _base(engine) / 'journal.events')
            if events.exists():
                if events.stat().st_size:
                    raise ValueError('Recovery event journal has lost its header; protected files need attention')
                events.unlink()
                _fsync(events.parent)
            return {'recovered': False}
        require_stopped(engine)
        journal = _read_journal(engine, path)
        _validate_journal(engine, journal)
        if journal['phase'] == 'committed':
            for operation in journal['operations']:
                if digest(confined(engine, operation['target'], True)) != operation['after']:
                    raise ValueError('Committed deployment changed externally; recovery requires attention')
            _remove_journal(engine)
            return {'recovered': True, 'committed': True}
        _rollback(engine, journal)
        return {'recovered': True, 'rolled_back': True, 'files': len(journal['operations'])}
