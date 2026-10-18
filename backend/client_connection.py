"""Explicit, reversible edits to eqhost.txt and the Custom client's PE LAA flag.

Normal preparation never replaces an existing eqhost.txt. Recovery originals live
outside the client import tree, and every restore verifies installation, path and
both the original and current checksums before touching a file.
"""
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
import time
import secrets
import urllib.error
import urllib.request
import zipfile

MAX_HOST = 16384
MAX_EXE = 128 * 1024**2
RECOVERY = 'backups/client-connection'
MUTATIONS = ('client_host_save', 'client_host_restore', 'client_4gb_apply', 'client_4gb_restore', 'client_4gb_download')

# NTCore's reviewed official release. Fetch on explicit request only; the tool
# is never bundled, executed, or substituted for the reversible built-in patch.
PATCH_URL = 'https://ntcore.com/files/4gb_patch.zip'
PATCH_PAGE = 'https://ntcore.com/4gb-patch/'
PATCH_VERSION = '1.0.0.1'
PATCH_ZIP_BYTES = 21464
PATCH_ZIP_SHA256 = '1e13c263dc55e85cf62e3e30c6b2ce936d4c7e16e3bba3e311a5a8bed4be16ca'
PATCH_EXE_BYTES = 45056
PATCH_EXE_SHA256 = '980bf5eb62d30c749e5fbf7593e9d25094a4d849a959aa2b7b3fc979b1c93b5a'
PATCH_NAME = '4gb_patch.exe'


class OfficialPatchRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if newurl != PATCH_URL:
            raise ValueError('The official 4GB patch download redirected to an unexpected address')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_download(engine, deadline=None):
    cancel = getattr(engine, 'cancel', None)
    if cancel is not None and cancel.is_set():
        raise ValueError('4GB patch download cancelled; client files were left unchanged')
    if deadline is not None and time.monotonic() > deadline:
        raise ValueError('The official 4GB patch download timed out; try again')


def fetch_patch(engine):
    """Bound and verify both the official archive and its fixed executable."""
    deadline = time.monotonic() + 120
    check_download(engine, deadline)
    request = urllib.request.Request(PATCH_URL, headers={'User-Agent': 'TRASC-4GB-Patch/1'})
    try:
        with urllib.request.build_opener(OfficialPatchRedirect()).open(request, timeout=30) as response:
            if response.url != PATCH_URL:
                raise ValueError('Unexpected official 4GB patch download address')
            try:
                declared = int(response.headers.get('Content-Length', '0'))
            except (TypeError, ValueError) as error:
                raise ValueError('Invalid official 4GB patch response size') from error
            if declared not in (0, PATCH_ZIP_BYTES):
                raise ValueError('The official 4GB patch download size changed; this launcher needs an updated verified release')
            archive = bytearray()
            while True:
                check_download(engine, deadline)
                block = response.read(min(8192, PATCH_ZIP_BYTES - len(archive) + 1))
                if not block:
                    break
                archive.extend(block)
                if len(archive) > PATCH_ZIP_BYTES:
                    raise ValueError('The official 4GB patch download exceeds its size limit')
        check_download(engine, deadline)
    except (OSError, urllib.error.URLError) as error:
        raise ValueError('Could not download the official 4GB patch; check your connection and try again') from error
    if len(archive) != PATCH_ZIP_BYTES or sha(archive) != PATCH_ZIP_SHA256:
        raise ValueError('The official 4GB patch archive checksum failed; client files were left unchanged')
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            entries = source.infolist()
            if len(entries) != 1:
                raise ValueError('The official 4GB patch archive has unexpected entries')
            entry = entries[0]
            file_type = stat.S_IFMT(entry.external_attr >> 16)
            if (entry.filename != PATCH_NAME or entry.is_dir() or file_type not in (0, stat.S_IFREG)
                    or entry.flag_bits & 1 or entry.file_size != PATCH_EXE_BYTES
                    or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError('The official 4GB patch archive has an invalid executable entry')
            with source.open(entry) as member:
                raw = member.read(PATCH_EXE_BYTES + 1)
            if len(raw) != PATCH_EXE_BYTES or sha(raw) != PATCH_EXE_SHA256:
                raise ValueError('The official 4GB patch executable checksum failed')
            pe_info(raw)
            return raw
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
        raise ValueError('The official 4GB patch archive could not be verified') from error


def tool_status(root, eligible):
    result = dict(can_download=False, downloaded=False, path='client/current/' + PATCH_NAME,
                  source_url=PATCH_PAGE, download_url=PATCH_URL, version=PATCH_VERSION,
                  sha256=PATCH_EXE_SHA256, warning='')
    if root is None:
        return result
    try:
        path = lookup(root, PATCH_NAME)
        result['path'] = 'client/current/' + path.name
        raw = read(path, PATCH_EXE_BYTES, missing=True)
        if raw is not None:
            if len(raw) != PATCH_EXE_BYTES or sha(raw) != PATCH_EXE_SHA256:
                raise ValueError('An unrecognized 4gb_patch.exe already exists; it was left unchanged. Move it before downloading the verified NTCore tool.')
            result['downloaded'] = True
        result['can_download'] = eligible
    except (ValueError, OSError) as error:
        result['warning'] = str(error)
    return result


def download_patch(engine, root, executable, identity, revision):
    """Save only the fixed verified tool, without replacing any client file."""
    pe_info(read(lookup(root, executable), MAX_EXE))
    existing = tool_status(root, True)
    if existing['warning']:
        raise ValueError(existing['warning'])
    if existing['downloaded']:
        return dict(status(engine), message='The verified NTCore 4GB patch is already downloaded at ' + existing['path'] + '.')
    raw = fetch_patch(engine)
    # Network activity may take time. Recheck the client installation, exe and
    # lease immediately before adding the tool; no executable or backup changes.
    current_root, current_executable, current_identity = local(engine)
    if (current_root != root or current_executable != executable or current_identity != identity
            or sha(read(lookup(current_root, current_executable), MAX_EXE)) != revision):
        raise ValueError('The client changed during download. Reload connection settings before continuing.')
    require_stopped(engine)
    check_download(engine)
    existing = tool_status(root, True)
    if existing['warning']:
        raise ValueError(existing['warning'])
    if not existing['downloaded']:
        destination = lookup(root, PATCH_NAME)
        created = None
        try:
            # Android/PRoot can deny hard links. Exclusive creation works there
            # and cannot replace any existing file, including a late symlink.
            # A process crash could leave a partial tool, which is subsequently
            # reported as a conflict rather than silently replaced or executed.
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
            created = os.fstat(fd)
            with os.fdopen(fd, 'wb') as out:
                out.write(raw)
                out.flush()
                os.fsync(out.fileno())
        except FileExistsError as error:
            raise ValueError('A 4gb_patch.exe appeared during download; it was left unchanged. Reload connection settings.') from error
        except Exception:
            if created is not None:
                try:
                    current = destination.lstat()
                    if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                        destination.unlink()
                except FileNotFoundError:
                    pass
            raise
    return dict(status(engine), message='NTCore 4GB Patch downloaded to client/current/4gb_patch.exe. Open it from the Wine desktop if needed. No client executable was changed.')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def confined(engine, relative):
    """Reject linked ancestors, even links whose targets remain in the workspace."""
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts) or '\\' in str(relative) or '\x00' in str(relative):
        raise ValueError('Invalid client recovery path')
    target = engine.work
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError('Client files and recovery originals cannot use symbolic links')
    return target


def read(path, limit, missing=False):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if missing:
            return None
        raise ValueError('Missing client file: ' + path.name)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError(path.name + ' must be an ordinary file within the supported size')
        raw = source.read(limit + 1)
        if len(raw) > limit:
            raise ValueError(path.name + ' exceeds the supported size')
        return raw


def atomic(path, raw, mode=None):
    fd, name = tempfile.mkstemp(prefix='.trasc-connection-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
            if mode is not None:
                os.fchmod(out.fileno(), mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def local(engine):
    root = confined(engine, 'client/current')
    if not root.is_dir():
        raise ValueError('Import this profile\'s client first')
    marker = lookup(root, 'trasc-client.json')
    record = json.loads(read(marker, 131072))
    if not isinstance(record, dict):
        raise ValueError('Invalid imported client record')
    executable = record.get('executable')
    if not record.get('imported') or not isinstance(executable, str) or executable.casefold() != 'eqgame.exe':
        raise ValueError('Import a client with a valid eqgame.exe selection first')
    # Prepare updates validation/display fields, but never this installation ID.
    identity = sha(json.dumps({'executable': executable, 'imported_at': record.get('imported_at')}, sort_keys=True).encode())
    return root, executable, identity


def lookup(root, name):
    matches = [p for p in root.iterdir() if p.name.casefold() == name.casefold()]
    if len(matches) > 1:
        raise ValueError('Ambiguous client filename: ' + name)
    path = matches[0] if matches else root / name
    if path.is_symlink():
        raise ValueError('Client files cannot use symbolic links: ' + name)
    return path


def endpoint(value):
    match = re.fullmatch(rb'(\[[0-9a-fA-F:.]+\]|[^\s:]+)(:)([0-9]{1,5})', value)
    if not match or not 1 <= int(match[3]) <= 65535:
        raise ValueError('eqhost.txt has an invalid endpoint; keep a host and its existing port')
    return match


def host_fields(raw, profile):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        raise ValueError('eqhost.txt must use the client\'s ordinary text format')
    section, fields, sections = b'', [], set()
    # Work on bytes and absolute offsets: comments, BOM, line endings, key case,
    # indentation, quoting and the exact port spelling all survive a host edit.
    offset = 0
    for line in raw.splitlines(keepends=True):
        content = line.rstrip(b'\r\n')
        clean = content.lstrip(b'\xef\xbb\xbf') if offset == 0 else content
        header = re.fullmatch(rb'[ \t]*\[([^\]]+)\][ \t]*', clean)
        if header:
            section = re.sub(rb'[ \t]', b'', header[1]).lower()
            if section in sections:
                raise ValueError('eqhost.txt contains duplicate login sections')
            sections.add(section)
        elif profile == 'takp' and section in (b'registrationservers', b'loginservers'):
            m = re.fullmatch(rb'([ \t]*\")([^\"]+)(\"[ \t]*(?:[;#].*)?)', content)
            if m:
                parsed = endpoint(m[2])
                start = offset + m.start(2)
                fields.append((start, start + len(parsed[1]), parsed[1].decode('ascii'), parsed[3].decode('ascii'), section))
            elif content.strip() and content.strip() not in (b'{', b'}') and not content.lstrip().startswith((b';', b'#')):
                raise ValueError('Unrecognized TAKP eqhost.txt endpoint')
        elif profile != 'takp' and section == b'loginserver':
            m = re.fullmatch(rb'([ \t]*Host[ \t]*=[ \t]*)([^;#\s]+)([ \t]*(?:[;#].*)?)', content, re.I)
            if m:
                parsed = endpoint(m[2])
                start = offset + m.start(2)
                fields.append((start, start + len(parsed[1]), parsed[1].decode('ascii'), parsed[3].decode('ascii'), section))
        offset += len(line)
    if profile == 'takp':
        if len(fields) != 2 or {f[4] for f in fields} != {b'registrationservers', b'loginservers'}:
            raise ValueError('TAKP eqhost.txt needs one quoted endpoint in each Registration Servers and Login Servers section')
    elif len(fields) != 1:
        raise ValueError('eqhost.txt needs exactly one Host=address:port in [LoginServer]')
    return fields


def default_host(profile):
    if profile == 'takp':
        from takp_client import login_text
        return login_text('127.0.0.1', 6000).encode('ascii')
    return b'[LoginServer]\r\nHost=127.0.0.1:5999\r\n'


def prepare_default(engine, client, changes):
    """Only synthesize the normal local connection when eqhost.txt is absent."""
    host = lookup(client, 'eqhost.txt')
    if host.exists():
        read(host, MAX_HOST)
    else:
        changes[host] = default_host(engine.profile)


def pe_info(raw):
    if len(raw) < 64 or raw[:2] != b'MZ':
        raise ValueError('The selected eqgame.exe is not a DOS/PE executable')
    pe = struct.unpack_from('<I', raw, 0x3c)[0]
    if pe < 64 or pe + 24 > len(raw) or raw[pe:pe+4] != b'PE\0\0':
        raise ValueError('The selected eqgame.exe has an invalid PE header')
    machine, sections = struct.unpack_from('<HH', raw, pe + 4)
    optional, flags = struct.unpack_from('<HH', raw, pe + 20)
    end = pe + 24 + optional
    if machine != 0x14c or not 1 <= sections <= 96 or optional < 96 or end + sections*40 > len(raw):
        raise ValueError('The 4GB patch requires a valid 32-bit x86 PE client')
    if struct.unpack_from('<H', raw, pe + 24)[0] != 0x10b or not flags & 2 or flags & 0x2000:
        raise ValueError('The 4GB patch requires a PE32 application, not a DLL or 64-bit binary')
    for index in range(sections):
        size, start = struct.unpack_from('<II', raw, end + index*40 + 16)
        if size and (start < end + sections*40 or start + size > len(raw)):
            raise ValueError('The client has a truncated or invalid PE section')
    return pe + 22, bool(flags & 0x20)


def recovery(engine, kind, path, identity):
    marker = confined(engine, RECOVERY + '/' + kind + '-' + identity + '.json')
    raw = read(marker, 131072, missing=True)
    if raw is None:
        return None
    record = json.loads(raw)
    if not isinstance(record, dict):
        raise ValueError('Invalid client recovery record')
    if record.get('format') != 1 or record.get('kind') != kind or record.get('path') != str(path.relative_to(engine.work)) or record.get('installation') != identity:
        raise ValueError('The retained original belongs to another client installation; it remains protected')
    if not isinstance(record.get('accepted'), list) or not record['accepted'] or not all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in record['accepted']):
        raise ValueError('Invalid client recovery checksums')
    original = record.get('original_sha256')
    if original is not None and (not isinstance(original, str) or not re.fullmatch('[0-9a-f]{64}', original)):
        raise ValueError('Invalid original client checksum')
    saved = record.get('backup')
    if not isinstance(saved, str) or not re.fullmatch(RECOVERY + r'/[0-9]{8}-[0-9]{6}-[0-9a-f]{12}/original', saved):
        raise ValueError('Invalid protected client recovery path')
    backup = confined(engine, saved)
    if original is not None and sha(read(backup, MAX_HOST if kind == 'host' else MAX_EXE)) != original:
        raise ValueError('Protected original checksum failed; current client files were left unchanged')
    return record


def checked_backup(engine, kind, path, identity, before, after):
    base = confined(engine, RECOVERY)
    base.mkdir(parents=True, exist_ok=True)
    record = recovery(engine, kind, path, identity)
    current = sha(before) if before is not None else None
    if record and current not in record['accepted'] + [record['original_sha256']]:
        raise ValueError('The client file changed outside the launcher; restore or reimport before changing it again')
    if record is None:
        folder = base / (time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(6))
        folder.mkdir()
        backup = folder / 'original'
        if before is not None:
            atomic(backup, before, 0o400)
        record = {'format': 1, 'kind': kind, 'path': str(path.relative_to(engine.work)), 'installation': identity,
                  'original_sha256': current, 'backup': str(backup.relative_to(engine.work)), 'accepted': []}
    variants = [after]
    if kind == 'host' and engine.profile == 'takp':
        from takp_client import normalize_login_sections
        # Older clients repair historical section spellings on their first
        # launch. Record only hashes of that exact known full-file migration;
        # arbitrary external edits still cannot qualify for restoration.
        variants.append(normalize_login_sections(after))
        if record['original_sha256'] is not None:
            variants.append(normalize_login_sections(read(confined(engine, record['backup']), MAX_HOST)))
    for variant in variants:
        if sha(variant) not in record['accepted']:
            record['accepted'].append(sha(variant))
    # Journal before the atomic replacement; a crash leaves either a verified
    # original or one of the recorded complete replacements, both restorable.
    atomic(base / (kind + '-' + identity + '.json'), json.dumps(record, indent=2).encode(), 0o600)
    return record


def require_stopped(engine):
    lease = confined(engine, 'run/client-active.json')
    raw = read(lease, 16384, missing=True)
    if raw is not None:
        try:
            pid = json.loads(raw)['pid']
            if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise ValueError('Invalid client runtime state; stop the client before changing its files')
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            pass  # An existing process is active even across a restricted UID.
        raise ValueError('Stop the client before changing its files')


def status(engine, args=None):
    host = dict(host='127.0.0.1', port=6000 if engine.profile == 'takp' else 5999, exists=False, backup_exists=False,
                revision='', warning='', path='client/current/eqhost.txt', can_save=False, can_restore=False)
    patch = dict(eligible=False, exe='eqgame.exe', patched=False, backup_exists=False, revision='', warning='', can_apply=False, can_restore=False,
                 download=tool_status(None, False))
    result = dict(profile=engine.profile, host=host, patch=patch)
    try:
        root, executable, identity = local(engine)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        host['warning'] = patch['warning'] = str(error)
        return result
    try:
        path = lookup(root, 'eqhost.txt')
        raw = read(path, MAX_HOST, missing=True)
        host.update(path=str(path.relative_to(engine.work)), exists=raw is not None, revision=sha(raw) if raw is not None else 'missing')
        fields = host_fields(raw if raw is not None else default_host(engine.profile), engine.profile)
        ports = list(dict.fromkeys(f[3] for f in fields))
        host.update(host=fields[0][2].strip('[]'), port=int(ports[0]) if len(ports) == 1 else ', '.join(ports), can_save=True)
        record = recovery(engine, 'host', path, identity)
        if record:
            host['backup_exists'] = True
            if raw is not None and sha(raw) in record['accepted']:
                host['can_restore'] = sha(raw) != record['original_sha256']
            elif (sha(raw) if raw is not None else None) != record['original_sha256']:
                raise ValueError('eqhost.txt changed outside the launcher; the retained original remains protected')
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        host.update(warning=str(error), can_save=False)
    if engine.profile != 'custom':
        patch['warning'] = 'The 4GB patch belongs to TRASC Custom.'
        return result
    try:
        path = lookup(root, executable)
        raw = read(path, MAX_EXE)
        _, patched = pe_info(raw)
        patch.update(eligible=True, exe=path.name, patched=patched, revision=sha(raw), can_apply=not patched)
        record = recovery(engine, '4gb', path, identity)
        if record:
            patch['backup_exists'] = True
            if sha(raw) in record['accepted']:
                patch['can_restore'] = sha(raw) != record['original_sha256']
            elif sha(raw) != record['original_sha256']:
                raise ValueError('eqgame.exe changed since patching; the protected original was not applied to this replacement')
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        patch.update(warning=str(error), eligible=False, can_apply=False)
    patch['download'] = tool_status(root, patch['eligible'])
    return result


def mutate(engine, operation, args):
    require_stopped(engine)
    if operation not in MUTATIONS:
        raise ValueError('Unknown client connection operation')
    if operation.startswith('client_4gb_') and engine.profile != 'custom':
        raise ValueError('The 4GB patch belongs to TRASC Custom')
    root, executable, identity = local(engine)
    kind = 'host' if operation.startswith('client_host_') else '4gb'
    path = lookup(root, 'eqhost.txt' if kind == 'host' else executable)
    raw = read(path, MAX_HOST if kind == 'host' else MAX_EXE, missing=kind == 'host')
    revision = sha(raw) if raw is not None else 'missing'
    if args.get('revision') != revision:
        raise ValueError('The client file changed. Reload connection settings before continuing.')
    if operation == 'client_4gb_download':
        return download_patch(engine, root, executable, identity, revision)
    if operation.endswith('_restore'):
        record = recovery(engine, kind, path, identity)
        if not record:
            raise ValueError('There is no retained original to restore')
        current = sha(raw) if raw is not None else None
        if current not in record['accepted'] + [record['original_sha256']]:
            raise ValueError('The client file changed outside the launcher; restoration was refused')
        if current == record['original_sha256']:
            message = 'The original client file is already restored.'
        else:
            original = read(confined(engine, record['backup']), MAX_HOST if kind == 'host' else MAX_EXE) if record['original_sha256'] is not None else None
            require_stopped(engine)
            if original is None:
                path.unlink()
            else:
                atomic(path, original, stat.S_IMODE(path.stat().st_mode) if raw is not None else 0o644)
            message = 'Original ' + path.name + ' restored. Its protected backup is retained.'
    else:
        if kind == 'host':
            value = args.get('host')
            if not isinstance(value, str) or '%' in value:
                raise ValueError('Enter an IPv4 or IPv6 address without a port')
            try:
                address = ipaddress.ip_address(value.strip())
            except ValueError as error:
                raise ValueError('Enter a valid IP address without a port') from error
            if engine.profile == 'takp' and address.version != 4:
                raise ValueError('The legacy TAKP client requires an IPv4 address')
            replacement = ('[' + str(address) + ']' if address.version == 6 else str(address)).encode('ascii')
            before = raw if raw is not None else default_host(engine.profile)
            fields = host_fields(before, engine.profile)
            updated = before
            for start, end, _, _, _ in reversed(fields):
                updated = updated[:start] + replacement + updated[end:]
        else:
            offset, patched = pe_info(raw)
            updated = raw if patched else raw[:offset] + bytes([raw[offset] | 0x20]) + raw[offset+1:]
        if raw == updated:
            message = 'No changes needed; the client file and retained backups are unchanged.'
        else:
            checked_backup(engine, kind, path, identity, raw, updated)
            require_stopped(engine)
            atomic(path, updated, stat.S_IMODE(path.stat().st_mode) if raw is not None else 0o644)
            message = ('Login IP saved in eqhost.txt; every existing port is unchanged.' if kind == 'host' else '4GB address flag applied to the 32-bit client; every other byte is unchanged.') + ' Protected original retained for Restore.'
    return dict(status(engine), message=message)
