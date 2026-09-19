#!/usr/bin/env python3
"""TRASC's local control daemon. Runs inside the app-owned ARM64 rootfs.

Only the Android app receives the randomly generated API token. Processes, SQL,
source builds and file operations never use the user's Termux installation.
"""
import argparse
import contextlib
import gzip
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import queue
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import tarfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from rule_catalog import KNOWN, metadata, parse_source, validate_value
from managed_content import ManagedContent
import client_addons
import client_dll
import client_settings
import player_data
import spire
from log_retention import rotate

VERSION = '0.3.4'
DEFAULT_REPO = 'https://github.com/Russianranger/Triptych-Triumvirate'
BINARIES = ('world', 'zone', 'loginserver', 'shared_memory', 'ucs', 'eqlaunch', 'queryserv', 'export_client_files')
CLIENT_FILES = ('spells_us.txt', 'dbstr_us.txt', 'SkillCaps.txt', 'BaseData.txt')
MAX_EXTRACT_BYTES = 40 * 1024**3
MAX_FILES = 400000


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.new')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def safe_path(root, name, must_exist=False):
    """Confine all user/archive paths and reject symlink escapes."""
    root = Path(root).resolve()
    if '\\' in str(name) or '\x00' in str(name):
        raise ValueError('Invalid path')
    p = PurePosixPath(str(name))
    if p.is_absolute() or '..' in p.parts or (p.parts and ':' in p.parts[0]):
        raise ValueError('Path must stay inside the selected directory')
    result = (root / str(p)).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Path escapes the selected directory')
    if must_exist and not result.exists():
        raise ValueError('File does not exist')
    return result


def extract_archive(archive, dest, limit=MAX_EXTRACT_BYTES):
    """Streaming ZIP/tar import with traversal, symlink and expansion limits."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    total = count = 0
    def consume(name, size, is_dir, stream, mode=0o644):
        nonlocal total, count
        count += 1
        total += size
        if count > MAX_FILES or total > limit:
            raise ValueError('Archive exceeds the supported import size')
        target = safe_path(dest, name)
        if is_dir:
            target.mkdir(parents=True, exist_ok=True)
            return
        if target == dest:
            raise ValueError('Invalid archive member')
        target.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(dest).free < size + 64 * 1024**2:
            raise ValueError('Not enough free space to extract this archive')
        written = 0
        with target.open('wb') as out:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                written += len(block)
                if written > size:
                    raise ValueError('Archive size mismatch')
                out.write(block)
        if written != size:
            raise ValueError('Archive is truncated')
        target.chmod(0o755 if mode & 0o111 else 0o644)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError('Source/maps ZIP contains a symlink; supply ordinary files')
                if info.flag_bits & 1:
                    raise ValueError('Encrypted ZIP files are not supported')
                with z.open(info) as stream:
                    consume(info.filename, info.file_size, info.is_dir(), stream, mode)
    else:
        with tarfile.open(archive, 'r:*') as t:
            for info in t:
                if not (info.isfile() or info.isdir()):
                    raise ValueError('Source/maps archives must contain ordinary files and folders')
                stream = t.extractfile(info) if info.isfile() else None
                with contextlib.closing(stream) if stream else contextlib.nullcontext():
                    consume(info.name, info.size, info.isdir(), stream, info.mode)
    return {'files': count, 'bytes': total}


def github_parts(url, ref=''):
    parsed = urllib.parse.urlparse(url.strip().rstrip('/'))
    if parsed.scheme != 'https' or parsed.hostname != 'github.com' or parsed.username or parsed.password:
        raise ValueError('Use an HTTPS github.com repository link')
    parts = [urllib.parse.unquote(p) for p in parsed.path.split('/') if p]
    if len(parts) < 2 or any(p in ('.', '..') for p in parts):
        raise ValueError('Expected https://github.com/owner/repository')
    owner, repo = parts[0], parts[1].removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', owner) or not re.fullmatch(r'[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository name')
    if len(parts) > 2:
        if parts[2] != 'tree' or len(parts) < 4:
            raise ValueError('Use a repository or /tree/branch link; use ZIP mode for release downloads')
        ref = ref or '/'.join(parts[3:])
    return owner, repo, ref


def sql_string(value):
    # Hex literals avoid dependence on the session's backslash escaping mode.
    return "CONVERT(X'%s' USING utf8mb4)" % str(value).encode().hex()


def validate_rule(name, value):
    if name not in KNOWN:
        raise ValueError('Unsupported gameplay rule')
    return validate_value(name, value, metadata(name, KNOWN[name]['type']))


class Engine(ManagedContent):
    def __init__(self, work):
        self.work = Path(work).resolve()
        for name in ('incoming', 'sources', 'server', 'maps', 'database', 'backups', 'exports', 'logs', 'run', 'builds', 'client'):
            (self.work / name).mkdir(parents=True, exist_ok=True)
        self.config_path = self.work / 'settings.json'
        self.config = json.loads(self.config_path.read_text()) if self.config_path.exists() else {
            'repo': DEFAULT_REPO, 'ref': 'main', 'ip': '127.0.0.1', 'login_port': 5999,
            'workers': 3, 'jobs': 2, 'database': 'triune', 'db_port': 13306,
            'db_password': secrets.token_hex(20), 'server_key': secrets.token_hex(20),
            'database_imported': False, 'rules_pending_restart': False,
        }
        self.config.setdefault('root_password', secrets.token_hex(20))
        self.save()
        self.processes = {}
        self.process_lock = threading.RLock()
        self.db = None
        self.queue = queue.Queue()
        self.jobs = []
        self.current_job = None
        self.cancel = threading.Event()
        self.command = None
        self.log_lock = threading.Lock()
        self.stopping = False
        self.log_path = self.work / 'logs' / 'control.log'
        self.ensure_mysql_options()
        threading.Thread(target=self.worker, daemon=True).start()
        self.log('Control service ready. Server remains stopped until Start is selected.')
        try: self.recover_nektulos()
        except (ValueError, OSError) as e: self.log('Nektulos recovery needs attention: ' + str(e))

    def save(self):
        atomic_json(self.config_path, self.config)
        self.config_path.chmod(0o600)

    def log(self, text):
        with self.log_lock:
            if self.log_path.exists() and self.log_path.stat().st_size > 8 * 1024**2:
                rotate(self.log_path)
            with self.log_path.open('a') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + str(text) + '\n')

    def enqueue(self, op, args):
        lease=self.work/'run/client-dll-building.json'
        if lease.is_file():
            try:
                pid=int(json.loads(lease.read_text())['pid'])
                if pid>0 and Path('/proc',str(pid)).exists():
                    raise ValueError('Stop the client DLL compiler before changing the server workspace')
            except (KeyError, TypeError, json.JSONDecodeError):
                raise ValueError('Invalid compiler state; stop the client runtime before continuing')
        with self.process_lock:
            if any(j['status'] in ('queued', 'running') for j in self.jobs):
                raise ValueError('Another operation is running. Wait for it or cancel it first.')
            job = {'id': secrets.token_hex(6), 'operation': op, 'status': 'queued', 'started': time.time()}
            self.jobs.append(job)
            for old in self.jobs[:-1]:
                if old['operation'] == 'gameplay': old.pop('result', None)
            self.jobs = self.jobs[-20:]
            self.queue.put((job, args))
            return job

    def worker(self):
        while True:
            job, args = self.queue.get()
            self.current_job = job
            self.cancel.clear()
            job['status'] = 'running'
            self.log('Starting ' + job['operation'])
            try:
                rotate(self.work/'logs/operation.log')
                job['result'] = self.dispatch(job['operation'], args)
                job['status'] = 'done'
                self.log('Completed ' + job['operation'])
            except Exception as e:
                job['status'] = 'error'
                job['error'] = str(e)
                self.log('Failed ' + job['operation'] + ': ' + str(e))
            finally:
                job['finished'] = time.time()
                self.current_job = None
                self.command = None
                self.queue.task_done()

    def check_cancel(self):
        if self.cancel.is_set():
            raise ValueError('Operation cancelled')

    def run(self, args, cwd=None, timeout=7200, input_file=None, output_file=None, private=False):
        self.check_cancel()
        if not private:
            self.log('Run: ' + ' '.join(str(x) for x in args))
        with (open(input_file, 'rb') if input_file else contextlib.nullcontext(None)) as inp:
            with (open(output_file, 'wb') if output_file else open(self.work / 'logs' / 'operation.log', 'ab')) as out, open(self.work / 'logs' / 'operation.log', 'ab') as errlog:
                p = subprocess.Popen([str(x) for x in args], cwd=cwd or self.work, stdin=inp or subprocess.DEVNULL,
                                     stdout=out, stderr=errlog if output_file else out, start_new_session=True)
                self.command = p
                started = time.monotonic()
                try:
                    while p.poll() is None:
                        if self.cancel.is_set() or time.monotonic() - started > timeout:
                            os.killpg(p.pid, signal.SIGTERM)
                            try: p.wait(10)
                            except subprocess.TimeoutExpired: os.killpg(p.pid, signal.SIGKILL)
                            raise ValueError('Operation cancelled or timed out. See operation.log.')
                        time.sleep(0.2)
                    if p.returncode:
                        raise ValueError(f'Command failed ({p.returncode}): see operation.log')
                finally:
                    self.command = None

    def download(self, url, target):
        p = urllib.parse.urlparse(url)
        if p.scheme != 'https' or p.username or p.password:
            raise ValueError('Download links must use HTTPS')
        request = urllib.request.Request(url, headers={'User-Agent': 'TRASC-Server/0.1'})
        target = Path(target)
        tmp = target.with_name(target.name + '.part')
        try:
            with urllib.request.urlopen(request, timeout=60) as r, tmp.open('wb') as f:
                if urllib.parse.urlparse(r.url).scheme != 'https':
                    raise ValueError('Insecure download redirect')
                size = int(r.headers.get('Content-Length', '0'))
                count = 0
                mark = 0
                if size > shutil.disk_usage(target.parent).free - 256 * 1024**2:
                    raise ValueError('Not enough space for download')
                while True:
                    self.check_cancel()
                    block = r.read(1024 * 1024)
                    if not block: break
                    count += len(block)
                    if count > MAX_EXTRACT_BYTES: raise ValueError('Download is too large')
                    f.write(block)
                    if count - mark > 32 * 1024**2:
                        self.log(f'Downloaded {count // 1024**2} MiB' + (f' / {size // 1024**2} MiB' if size else ''))
                        mark = count
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        return target

    def github_download(self, url, ref, target):
        owner, repo, ref = github_parts(url, ref)
        base = f'https://api.github.com/repos/{owner}/{repo}'
        def get(endpoint):
            request = urllib.request.Request(endpoint, headers={'User-Agent': 'TRASC-Server/0.1'})
            with urllib.request.urlopen(request, timeout=30) as r: return json.load(r)
        if not ref: ref = get(base)['default_branch']
        commit = get(base + '/commits/' + urllib.parse.quote(ref, safe=''))['sha']
        if not re.fullmatch('[0-9a-f]{40}', commit): raise ValueError('Invalid GitHub commit')
        self.log(f'Fetching {owner}/{repo} at {commit}')
        self.download(f'https://codeload.github.com/{owner}/{repo}/zip/{commit}', target)
        return {'repo': f'https://github.com/{owner}/{repo}', 'ref': ref, 'commit': commit}

    def source_root(self):
        current = self.work / 'sources' / 'current'
        if (current / 'Release-NMS-Server' / 'CMakeLists.txt').exists(): return current
        if (current / 'CMakeLists.txt').exists() and (current / 'zone').exists(): return current
        raise ValueError('Import the server source first')

    def import_source(self, args):
        stage = self.work / 'sources' / ('import-' + secrets.token_hex(4))
        metadata = {'imported': time.time(), 'type': 'archive'}
        try:
            if args.get('url'):
                archive = self.work / 'incoming' / 'source-download.zip'
                metadata.update(self.github_download(args['url'], args.get('ref', ''), archive))
                metadata['type'] = 'github'
            else:
                archive = safe_path(self.work / 'incoming', args['file'], True)
            extract_archive(archive, stage)
            self.check_cancel()
            candidates = []
            for p in [stage] + [p for p in stage.iterdir() if p.is_dir()]:
                if (p / 'Release-NMS-Server' / 'CMakeLists.txt').exists() or ((p / 'CMakeLists.txt').exists() and (p / 'zone').is_dir()): candidates.append(p)
            if len(candidates) != 1: raise ValueError('Archive must contain one Triptych/EQEmu server source tree')
            candidate = candidates[0]
            atomic_json(candidate / 'trasc-source.json', metadata)
            current, previous = self.work / 'sources/current', self.work / 'sources/previous'
            if previous.exists(): shutil.rmtree(previous)
            if current.exists(): os.replace(current, previous)
            os.replace(candidate, current)
            if metadata.get('repo'):
                self.config.update(repo=metadata['repo'], ref=metadata['ref'])
                self.save()
            return {'source': metadata, 'databases': self.database_candidates()}
        finally:
            if stage.exists(): shutil.rmtree(stage)

    def import_maps(self, args):
        if self.server_running(): raise ValueError('Stop the server before replacing maps')
        stage = self.work / ('maps-import-' + secrets.token_hex(4))
        try:
            if args.get('url'):
                archive = self.work / 'incoming/maps-download.zip'
                url = args['url']
                if urllib.parse.urlparse(url).hostname == 'github.com' and '/releases/' not in url and not url.endswith('.zip'):
                    self.github_download(url, args.get('ref', ''), archive)
                else: self.download(url, archive)
            else: archive = safe_path(self.work / 'incoming', args['file'], True)
            extract_archive(archive, stage)
            roots = [stage] + [p for p in stage.iterdir() if p.is_dir()]
            roots += [p / 'maps' for p in list(roots) if (p / 'maps').is_dir()]
            matches = [p for p in dict.fromkeys(roots) if any((p / name).is_dir() for name in ('base', 'nav', 'water', 'legacy'))]
            if len(matches) != 1: raise ValueError('Maps archive must contain base/, nav/, water/ or legacy/ folders')
            root = matches[0]
            count = 0
            self.check_cancel()
            for name in ('base', 'nav', 'water', 'legacy'):
                src = root / name
                if src.exists():
                    for p in src.rglob('*'):
                        if p.is_file():
                            target = self.work / 'maps' / p.relative_to(root)
                            if target.exists():
                                backup = self.work / 'backups/maps-before-import' / p.relative_to(root)
                                backup.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(target, backup)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(p, target)
                            count += 1
            if count == 0: raise ValueError('No map files found')
            return {'files_imported': count, 'previous_files': 'backups/maps-before-import'}
        finally:
            if stage.exists(): shutil.rmtree(stage)

    def database_candidates(self):
        results = []
        for root in (self.work / 'sources/current', self.work / 'incoming'):
            if not root.exists(): continue
            for p in root.rglob('*'):
                if not p.is_file() or p.is_symlink(): continue
                relative = str(p.relative_to(self.work))
                if p.name.lower().endswith(('.sql', '.sql.gz')):
                    results.append({'id': relative, 'size': p.stat().st_size})
                elif p.suffix.lower() == '.zip':
                    try:
                        with zipfile.ZipFile(p) as z:
                            for item in z.infolist():
                                if item.filename.lower().endswith(('.sql', '.sql.gz')):
                                    # Validate member names even though import streams one member.
                                    safe_path(self.work / 'incoming', item.filename)
                                    results.append({'id': relative + '!' + item.filename, 'size': item.file_size})
                    except (ValueError, zipfile.BadZipFile): pass
        # Full seed dumps first; migration scripts remain explicitly selectable.
        return sorted(results, key=lambda x: (-int('release-peq' in x['id'].lower()), -x['size']))[:1500]

    def ensure_mysql_options(self):
        self.mysql_options = self.work / 'run/mysql.cnf'
        self.mysql_options.write_text('[client]\nuser=root\npassword=' + self.config['root_password'] + '\nprotocol=socket\nsocket=' + str(self.work / 'run/mysql.sock') + '\ndefault-character-set=utf8mb4\n')
        self.mysql_options.chmod(0o600)

    def mysql(self, query, database=True, timeout=30):
        args = ['mariadb', '--defaults-extra-file=' + str(self.mysql_options), '--batch', '--raw']
        if database: args.append(self.config['database'])
        result = subprocess.run(args, input=query, text=True, capture_output=True, timeout=timeout)
        if result.returncode: raise ValueError(result.stderr.strip()[-3000:])
        return result.stdout

    def ensure_db(self):
        with self.process_lock:
            if self.db and self.db.poll() is None: return
            datadir = self.work / 'database'
            if not (datadir / 'mysql').exists():
                # Android's hostname need not resolve, including during offline setup.
                # --force skips the installer's DNS prerequisite; it does not ignore SQL errors.
                self.run(['mariadb-install-db', '--no-defaults', '--user=root',
                    '--datadir=' + str(datadir), '--auth-root-authentication-method=normal',
                    '--skip-test-db', '--force', '--skip-name-resolve',
                    '--innodb-use-native-aio=0', '--innodb-flush-method=fsync'], timeout=240)
            if not re.fullmatch(r'[0-9a-f]{40}', self.config['root_password']):
                raise ValueError('Invalid managed root credential')
            init = self.work / 'run/mysql-init.sql'
            init.write_text("ALTER USER 'root'@'localhost' IDENTIFIED BY '" + self.config['root_password'] + "';\nDELETE FROM mysql.global_priv WHERE User='' OR (User='root' AND Host<>'localhost');\nFLUSH PRIVILEGES;\n")
            init.chmod(0o600)
            rotate(self.work/'logs/mariadb.log')
            log = open(self.work / 'logs/mariadb.log', 'ab')
            self.db = subprocess.Popen(['mariadbd', '--no-defaults', '--user=root', '--datadir=' + str(datadir),
                '--init-file=' + str(init),
                '--socket=' + str(self.work / 'run/mysql.sock'), '--pid-file=' + str(self.work / 'run/mysql.pid'),
                '--bind-address=127.0.0.1', '--port=' + str(self.config['db_port']), '--skip-name-resolve',
                '--innodb-buffer-pool-size=128M', '--innodb-flush-method=fsync', '--innodb-use-native-aio=0',
                '--performance-schema=OFF', '--max-connections=64', '--tmpdir=/tmp'], stdout=log, stderr=log)
            log.close()
            for _ in range(180):
                if self.db.poll() is not None: raise ValueError('MariaDB stopped during startup; see mariadb.log')
                try:
                    self.mysql('SELECT 1;', database=False)
                    break
                except (ValueError, subprocess.TimeoutExpired): time.sleep(0.5)
            else: raise ValueError('MariaDB did not become ready')
            if not re.fullmatch(r'[0-9a-f]{40}', self.config['db_password']):
                raise ValueError('Invalid managed database credential')
            password = "'" + self.config['db_password'] + "'"
            self.mysql(f"CREATE DATABASE IF NOT EXISTS `{self.config['database']}` CHARACTER SET utf8mb4; CREATE USER IF NOT EXISTS 'trasc'@'127.0.0.1' IDENTIFIED BY {password}; ALTER USER 'trasc'@'127.0.0.1' IDENTIFIED BY {password}; GRANT ALL ON `{self.config['database']}`.* TO 'trasc'@'127.0.0.1';", database=False)

    def import_database(self, args):
        if self.server_running(): raise ValueError('Stop the server before importing a database')
        selection = args['selection']
        candidate = next((c for c in self.database_candidates() if c['id'] == selection), None)
        if not candidate: raise ValueError('Selected database is no longer available')
        self.ensure_db()
        if self.config['database_imported']:
            if not args.get('replace'): raise ValueError('Database exists. Enable replacement; a backup will be made first.')
            player_backup = player_data.export_players(self, {})['file']
            self.backup_database({})
        else:
            player_backup = None
        dump = self.work / 'run' / ('selected-database-' + secrets.token_hex(4) + '.sql')
        file_name, sep, member = selection.partition('!')
        source = safe_path(self.work, file_name, True)
        stack = contextlib.ExitStack()
        try:
            if sep:
                archive = stack.enter_context(zipfile.ZipFile(source))
                stream = stack.enter_context(archive.open(member))
                name = member
            else:
                stream = stack.enter_context(source.open('rb'))
                name = source.name
            if name.endswith('.gz'): stream = stack.enter_context(gzip.GzipFile(fileobj=stream))
            count = 0
            with dump.open('wb') as out:
                while True:
                    self.check_cancel()
                    b = stream.read(1024 * 1024)
                    if not b: break
                    count += len(b)
                    if count > MAX_EXTRACT_BYTES: raise ValueError('SQL dump is too large')
                    out.write(b)
            # Strip only mysqldump's database-selection directives, retaining all seed data.
            normalized = self.work / 'run/database-import.sql'
            with dump.open('rb') as inp, normalized.open('wb') as out:
                for line in inp:
                    upper = line.lstrip().upper()
                    if upper.startswith((b'CREATE DATABASE ', b'USE `', b'USE ')): continue
                    out.write(line)
            self.config['database_imported'] = False
            self.save()
            db = self.config['database']
            self.mysql(f'DROP DATABASE IF EXISTS `{db}`; CREATE DATABASE `{db}` CHARACTER SET utf8mb4;', database=False)
            self.run(['mariadb', '--defaults-extra-file=' + str(self.mysql_options), db], input_file=normalized, private=True)
            tables = self.mysql('SHOW TABLES;')
            required = ('account', 'character_data', 'rule_values', 'rule_sets', 'variables', 'launcher')
            if any(t not in tables.splitlines() for t in required):
                raise ValueError('Import finished but required server tables are missing. Choose the full database seed.')
            self.config.update(database_imported=True, database_source=selection)
            self.save()
            return {'imported': selection, 'player_backup':player_backup, 'message':'Database imported.' + (' Player/account snapshot retained at '+player_backup+'. Restore it from Database → Player data when ready.' if player_backup else '')}
        finally:
            stack.close()
            dump.unlink(missing_ok=True)
            (self.work / 'run/database-import.sql').unlink(missing_ok=True)

    def backup_database(self, args):
        self.ensure_db()
        name = 'database-' + time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(2) + '.sql'
        target = self.work / 'backups' / name
        self.run(['mariadb-dump', '--defaults-extra-file=' + str(self.mysql_options), '--lock-all-tables', '--routines', '--events', '--triggers', self.config['database']], output_file=target, private=True)
        packed = target.with_suffix('.sql.gz')
        with target.open('rb') as src, gzip.open(packed, 'wb') as dst: shutil.copyfileobj(src, dst)
        target.unlink()
        return {'file': str(packed.relative_to(self.work))}

    def restore_database(self, args):
        source = safe_path(self.work, args['file'], True)
        if not source.is_relative_to(self.work / 'backups'): raise ValueError('Select a database backup')
        incoming = self.work / 'incoming' / source.name
        shutil.copy2(source, incoming)
        return self.import_database({'selection': str(incoming.relative_to(self.work)), 'replace': True})

    def build(self, args):
        root = self.source_root()
        server = root / 'Release-NMS-Server' if (root / 'Release-NMS-Server').is_dir() else root
        jobs = int(args.get('jobs', self.config['jobs']))
        if not 1 <= jobs <= 4: raise ValueError('Choose 1–4 build jobs for this device')
        for needed in ('libs/luabind/CMakeLists.txt', 'submodules/fmt/CMakeLists.txt', 'submodules/libuv/CMakeLists.txt'):
            if not (server / needed).exists(): raise ValueError('Source lacks bundled dependencies: ' + needed + '. Import a complete source ZIP including submodules.')
        self.config['jobs'] = jobs
        self.save()
        build = self.work / 'builds' / 'current'
        # A source refresh can change CMake's absolute source path expectations.
        build.mkdir(exist_ok=True)
        self.run(['cmake', '-S', server, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DEQEMU_BUILD_LOGIN=ON', '-DEQEMU_BUILD_SERVER=ON', '-DEQEMU_BUILD_CLIENT_FILES=ON',
            '-DEQEMU_PREFER_LUA=ON', '-DLUA_INCLUDE_DIR=/usr/include/lua5.1',
            '-DLUA_LIBRARY=/usr/lib/aarch64-linux-gnu/liblua5.1.so'], timeout=600)
        self.run(['cmake', '--build', build, '--parallel', str(jobs), '--target', *BINARIES], timeout=24*3600)
        stage = self.work / 'server/bin.staged'
        if stage.exists(): shutil.rmtree(stage)
        stage.mkdir()
        for name in BINARIES:
            matches = [p for p in build.rglob(name) if p.is_file() and 'CMakeFiles' not in p.parts]
            if len(matches) != 1: raise ValueError('Cannot locate built binary: ' + name)
            with matches[0].open('rb') as binary: header = binary.read(20)
            if header[:4] != b'\x7fELF' or header[4] != 2 or int.from_bytes(header[18:20], 'little') != 183:
                raise ValueError(name + ' is not an ARM64 ELF binary')
            shutil.copy2(matches[0], stage / name)
            (stage / name).chmod(0o755)
        source_info = json.loads((root / 'trasc-source.json').read_text())
        atomic_json(stage / 'build-info.json', {'source': source_info, 'built': time.time(), 'app': VERSION})
        return {'message': 'Build passed. Stop the server, then select Deploy build.', 'staged': True}

    def deploy(self, args):
        if self.server_running(): raise ValueError('Stop the server before deploying binaries')
        stage = self.work / 'server/bin.staged'
        if not all((stage / x).exists() for x in BINARIES): raise ValueError('Complete a successful build first')
        self.sync_content(args)
        self.write_config()
        current, previous = self.work / 'server/bin', self.work / 'server/bin.previous'
        if previous.exists(): shutil.rmtree(previous)
        if current.exists(): os.replace(current, previous)
        os.replace(stage, current)
        return {'message': 'Binaries deployed. The previous binaries are available for rollback.'}

    def rollback(self, args):
        if self.server_running(): raise ValueError('Stop the server before rollback')
        current, previous, temp = self.work / 'server/bin', self.work / 'server/bin.previous', self.work / 'server/bin.swap'
        if not previous.exists(): raise ValueError('No previous build available')
        os.replace(current, temp)
        os.replace(previous, current)
        os.replace(temp, previous)
        return {'message': 'Previous binaries restored. Database migrations may require restoring the matching backup.'}

    def sync_content(self, args):
        root = self.source_root()
        runtime = self.work / 'server'
        src = root / 'Release-NMS-Server' if (root / 'Release-NMS-Server').is_dir() else root
        # Existing editable quests and maps are never silently overwritten on a build.
        if not (runtime / 'quests').exists():
            quests = root / 'Release-NMS-Quests'
            if not quests.exists(): raise ValueError('Source import is missing Release-NMS-Quests')
            shutil.copytree(quests, runtime / 'quests')
            if (root / 'Release-NMS-Plugins').exists(): shutil.copytree(root / 'Release-NMS-Plugins', runtime / 'quests/plugins', dirs_exist_ok=True)
        for name in ('maps',):
            dest = runtime / name
            if not dest.exists(): dest.symlink_to(self.work / name, target_is_directory=True)
        for folder in ('shared', 'logs', 'export'): (runtime / folder).mkdir(exist_ok=True)
        for p in src.rglob('*.conf'):
            if p.name.startswith(('patch_', 'opcodes', 'mail_opcodes', 'login_opcodes')):
                target = runtime / p.name
                if not target.exists(): shutil.copy2(p, target)
        if not (runtime / 'eqemu_config.json').exists():
            example = src / 'eqemu_config.json.example'
            if example.exists(): shutil.copy2(example, runtime / 'eqemu_config.json')
        if not (runtime / 'login.json').exists():
            example = src / 'login.json.example'
            if example.exists(): shutil.copy2(example, runtime / 'login.json')

    def write_config(self):
        runtime = self.work / 'server'
        cfg_path = runtime / 'eqemu_config.json'
        cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
        server = cfg.setdefault('server', {})
        world = server.setdefault('world', {})
        world.update(shortname='TRASC', longname='Triptych on Android', address=self.config['ip'], localaddress=self.config['ip'], key=self.config['server_key'])
        world['loginserver'] = {'host': '127.0.0.1', 'port': 5998, 'account': '', 'password': '', 'legacy': 0}
        world.pop('loginserver1', None)
        world['tcp'] = {'ip': '127.0.0.1', 'port': 9000}
        world['telnet'] = {'ip': '127.0.0.1', 'port': 9002, 'enabled': False}
        world['http'] = {'enabled': False, 'port': 9080, 'mimefile': 'mime.types'}
        db = {'host': '127.0.0.1', 'port': self.config['db_port'], 'username': 'trasc', 'password': self.config['db_password'], 'db': self.config['database']}
        server['database'] = db.copy()
        server['qsdatabase'] = db.copy()
        server['content_database'] = db.copy()
        server['zones'] = {'defaultstatus': 0, 'ports': {'low': 7000, 'high': 7100}}
        server['ucs'] = {'host': self.config['ip'], 'port': 7778}
        server['queryserver'] = {'host': '127.0.0.1', 'port': 9003}
        server['directories'] = {'maps': 'maps', 'quests': 'quests', 'plugins': 'quests/plugins', 'lua_modules': 'quests/lua_modules', 'patches': '.', 'opcodes': '.', 'shared_memory': 'shared/', 'logs': 'logs'}
        server.setdefault('launcher', {})['exe'] = str(runtime / 'bin/zone')
        server['auto_database_updates'] = True
        atomic_json(cfg_path, cfg)
        cfg_path.chmod(0o600)
        login_path = runtime / 'login.json'
        login = json.loads(login_path.read_text()) if login_path.exists() else {}
        login['database'] = {'host': '127.0.0.1', 'port': self.config['db_port'], 'user': 'trasc', 'password': self.config['db_password'], 'db': self.config['database']}
        login.setdefault('general', {})['eqemu_loginserver_address'] = f"{self.config['ip']}:{self.config['login_port']}"
        login.setdefault('worldservers', {}).update(unregistered_allowed=True, reject_duplicate_servers=False)
        login.setdefault('account', {})['auto_create_accounts'] = True
        login.setdefault('web_api', {})['enabled'] = False
        atomic_json(login_path, login)
        login_path.chmod(0o600)

    def server_running(self):
        return any(p.poll() is None for p in self.processes.values())

    def launch(self, name, *args):
        runtime = self.work / 'server'
        rotate(self.work/'logs'/(name+'.log'))
        with open(self.work / 'logs' / (name + '.log'), 'ab') as out:
            p = subprocess.Popen([str(runtime / 'bin' / name), *args], cwd=runtime, stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
        self.processes[name] = p
        return p

    def start(self, args):
        self.recover_nektulos()
        if self.server_running(): raise ValueError('Server processes are already running')
        if not self.config['database_imported']: raise ValueError('Import the full database seed first')
        if not all((self.work / 'server/bin' / x).exists() for x in BINARIES): raise ValueError('Build and deploy the server first')
        if not (self.work / 'maps/base').exists(): raise ValueError('Import the maps before starting the server')
        self.ensure_db()
        # Protect player data before the engine applies upstream schema migrations.
        self.backup_database({})
        self.write_config()
        self.mysql("INSERT INTO launcher (name,dynamics) VALUES ('trasc',%d) ON DUPLICATE KEY UPDATE dynamics=VALUES(dynamics);" % int(self.config['workers']))
        try:
            runtime = self.work / 'server'
            self.run([runtime / 'bin/shared_memory'], cwd=runtime, timeout=600)
            self.launch('loginserver')
            self.launch('world')
            # Wait for world's interserver TCP endpoint, including its migrations.
            for _ in range(600):
                self.check_cancel()
                if self.processes['world'].poll() is not None: raise ValueError('World stopped; inspect world.log')
                if self.processes['loginserver'].poll() is not None: raise ValueError('Login server stopped; inspect loginserver.log')
                try:
                    with socket.create_connection(('127.0.0.1', 9000), timeout=1): break
                except OSError: time.sleep(1)
            else: raise ValueError('World did not become ready within ten minutes')
            for name in ('ucs', 'queryserv'): self.launch(name)
            # eqlaunch overwrites its fixed zone stdout files when workers start.
            for path in (runtime/'logs').glob('zone-dynamic_*.log'):
                if re.fullmatch(r'zone-dynamic_\d+\.log', path.name):
                    rotate(path)
            self.launch('eqlaunch', 'trasc')
            time.sleep(3)
            failed = [n for n,p in self.processes.items() if p.poll() is not None]
            if failed: raise ValueError('Processes stopped during startup: ' + ', '.join(failed))
            self.config['rules_pending_restart'] = False
            self.save()
            return {'message': 'Server started. Verify zone readiness in server logs.', 'endpoint': f"{self.config['ip']}:{self.config['login_port']}"}
        except Exception:
            self.stop({})
            raise

    def stop(self, args):
        self.log('Server shutdown requested; saving zones before stopping services')
        self.stopping = True
        incomplete = []
        try:
            # This fork's eqlaunch kills remaining zones almost immediately on exit.
            # Pause its restart loop and give its children time to save before exiting it.
            launcher = self.processes.get('eqlaunch')
            if launcher and launcher.poll() is None:
                launcher.send_signal(signal.SIGSTOP)
                try:
                    children = []
                    for entry in Path('/proc').iterdir():
                        if not entry.name.isdigit(): continue
                        try:
                            status = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
                            if int(status[1]) == launcher.pid and status[0] != 'Z': children.append(int(entry.name))
                        except (OSError, ValueError): continue
                    for pid in children:
                        with contextlib.suppress(ProcessLookupError): os.kill(pid, signal.SIGTERM)
                    deadline = time.monotonic() + 90
                    while children and time.monotonic() < deadline:
                        alive = []
                        for pid in children:
                            try:
                                state = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]
                                if state != 'Z': alive.append(pid)
                            except OSError: pass
                        children = alive
                        if children: time.sleep(0.25)
                    if children:
                        self.log('Zone shutdown timed out for PIDs ' + str(children) + '; saved state may be incomplete')
                        incomplete.append('zone shutdown timed out')
                    launcher.send_signal(signal.SIGTERM)
                finally:
                    with contextlib.suppress(ProcessLookupError): launcher.send_signal(signal.SIGCONT)
            for name in ('eqlaunch', 'ucs', 'queryserv', 'loginserver', 'world'):
                p = self.processes.get(name)
                if p and p.poll() is None:
                    p.send_signal(signal.SIGTERM)
                    try: p.wait(timeout=90 if name == 'eqlaunch' else 30)
                    except subprocess.TimeoutExpired:
                        self.log(name + ' did not stop gracefully; terminating its process group')
                        incomplete.append(name + ' required forced termination')
                        os.killpg(p.pid, signal.SIGKILL)
                        p.wait()
            self.processes.clear()
            self.log('Server shutdown completed; errors=' + str(incomplete))
            return {'message': 'Server stopped. Database remains available for editing and backup.', 'clean_shutdown': not incomplete, 'shutdown_errors': incomplete}
        finally: self.stopping = False

    def shutdown(self):
        self.log('Runtime shutdown requested')
        self.cancel.set()
        if self.command and self.command.poll() is None:
            with contextlib.suppress(ProcessLookupError): os.killpg(self.command.pid, signal.SIGTERM)
        self.queue.join()
        self.stop({})
        if self.db and self.db.poll() is None:
            self.db.send_signal(signal.SIGTERM)
            try: self.db.wait(45)
            except subprocess.TimeoutExpired:
                self.log('MariaDB did not stop within 45 seconds')
                self.db.kill()
        self.log('Runtime shutdown completed')

    def gameplay(self, args):
        self.ensure_db()
        sets = self.mysql('SELECT ruleset_id,name FROM rule_sets ORDER BY ruleset_id;')
        selected = args.get('ruleset')
        active_rows = self.mysql("SELECT value FROM variables WHERE varname='RuleSet' LIMIT 1;").splitlines()[1:]
        active_name = active_rows[0] if active_rows else 'default'
        rows = [line.split('\t', 1) for line in sets.splitlines()[1:]]
        # The server resolves the set named 'default'; PEQ does not require ID 0.
        default_id = next((int(row[0]) for row in rows if row[1] == 'default'), None)
        if default_id is None: raise ValueError('The database has no ruleset named default')
        if selected is None:
            selected = next((int(row[0]) for row in rows if row[1] == active_name), None)
            if selected is None: raise ValueError('Unknown active ruleset: ' + active_name)
        selected = int(selected)
        if selected not in [int(r[0]) for r in rows]: raise ValueError('Unknown ruleset')
        # Apply default values first, then selected overrides, regardless of ID order.
        rules = self.mysql('SELECT ruleset_id,HEX(CONVERT(rule_name USING utf8mb4)),HEX(CONVERT(COALESCE(rule_value,\'\') USING utf8mb4)),HEX(CONVERT(COALESCE(notes,\'\') USING utf8mb4)) FROM rule_values ORDER BY (ruleset_id=%d),rule_name;' % selected)
        length_rows = self.mysql("SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='rule_values' AND COLUMN_NAME='rule_value';").splitlines()[1:]
        max_length = int(length_rows[0]) if length_rows else 128
        catalog = {}
        try:
            root = self.source_root()
            header = root / 'Release-NMS-Server/common/ruletypes.h'
            if not header.exists(): header = root / 'common/ruletypes.h'
            if header.is_file() and header.stat().st_size < 4 * 1024**2:
                catalog = parse_source(header.read_text(errors='replace'))
        except ValueError: pass
        values = {}
        for line in rules.splitlines()[1:]:
            cols = line.split('\t')
            if len(cols) != 4: continue
            set_id = int(cols[0])
            name, value, notes = [bytes.fromhex(c).decode('utf-8') for c in cols[1:]]
            if name not in catalog:
                kind = KNOWN.get(name, {}).get('type', 'string')
                catalog[name] = metadata(name, kind, notes)
            if set_id in (default_id, selected):
                values[name] = {'value': value, 'ruleset': set_id}
        for name, spec in catalog.items():
            spec['max_length'] = max_length
            if name not in values:
                values[name] = {'value': spec.get('default'), 'ruleset': None}
        launchers = self.mysql('SELECT name,dynamics FROM launcher;')
        return {'rulesets': [{'id':int(r[0]),'name':r[1]} for r in rows], 'selected': selected, 'active_name': active_name, 'values': values, 'metadata': catalog, 'launchers': launchers}

    def save_gameplay(self, args):
        self.ensure_db()
        ruleset = int(args['ruleset'])
        current = self.gameplay({'ruleset': ruleset})
        queries = []
        errors = []
        for name, value in args.get('values', {}).items():
            if name not in current['metadata']:
                errors.append(name + ': this rule is no longer in the database or source'); continue
            try: value = validate_value(name, value, current['metadata'][name], current['metadata'][name]['max_length'])
            except ValueError as e: errors.append(str(e)); continue
            queries.append(f'INSERT INTO rule_values (ruleset_id,rule_name,rule_value,notes) VALUES ({ruleset},{sql_string(name)},{sql_string(value)},\'TRASC GUI\') ON DUPLICATE KEY UPDATE rule_value=VALUES(rule_value);')
        raw_workers = str(args.get('workers', self.config['workers']))
        if not re.fullmatch(r'\d+', raw_workers): raise ValueError('Dynamic zone workers: enter a whole number from 1 to 20')
        workers = int(raw_workers)
        if not 1 <= workers <= 20: errors.append('Dynamic zone workers: choose 1–20 workers')
        if errors: raise ValueError('\n'.join(errors))
        if queries: self.backup_database({})
        self.mysql('START TRANSACTION;' + ''.join(queries) + 'COMMIT;')
        self.config.update(workers=workers, rules_pending_restart=True)
        self.save()
        return {'message': 'Saved. Restart the server to apply consistently to all processes. Existing saved zone state is retained.'}

    def prepare_session_backup(self, args):
        """Quiesce everything before Android reads the runtime and database files."""
        stopped = self.stop({})
        if not stopped['clean_shutdown']:
            raise ValueError('Complete backup preparation stopped: ' + ', '.join(stopped['shutdown_errors']) + '. Inspect the shutdown logs before retrying.')
        snapshot = self.backup_database({}) if self.config['database_imported'] else None
        if self.db and self.db.poll() is None:
            self.db.send_signal(signal.SIGTERM)
            try: self.db.wait(90)
            except subprocess.TimeoutExpired:
                raise ValueError('MariaDB did not shut down cleanly; session backup was not created') from None
            if self.db.returncode != 0:
                raise ValueError('MariaDB shutdown failed; inspect mariadb.log before creating a session backup')
        self.db = None
        return {'snapshot': snapshot, 'message': 'Server and database are stopped and ready for complete backup.'}

    def network(self, args):
        if self.server_running(): raise ValueError('Stop the server before changing network addresses')
        ip = str(ipaddress.ip_address(args['ip']))
        if ':' in ip: raise ValueError('Use an IPv4 address for this client/server setup')
        self.config['ip'] = ip
        self.save()
        self.write_config()
        return {'endpoint': f'{ip}:{self.config["login_port"]}', 'message': 'Advertised world, UCS and login addresses updated. Database stays local.'}

    def sql(self, args):
        self.ensure_db()
        query = args['query'].strip()
        if not query or len(query)>1000000: raise ValueError('Enter a SQL statement under 1 MB')
        if not args.get('write') and not re.match(r'^(SELECT|SHOW|DESCRIBE|DESC|EXPLAIN)\b', query, re.I): raise ValueError('Enable write mode to run modifying SQL')
        if not args.get('write'):
            # Server-enforced read-only transaction also blocks writes in trailing statements.
            if ';' in query.rstrip(';'): raise ValueError('Read mode accepts one statement at a time')
            query = 'START TRANSACTION READ ONLY; ' + query.rstrip(';') + '; ROLLBACK;'
        else:
            if self.server_running(): raise ValueError('Stop the server before running arbitrary write SQL')
            self.backup_database({})
        result = self.mysql(query, timeout=120)
        return {'output': result[:200000], 'truncated': len(result)>200000}

    def export_client(self, args):
        from client_spells import require_export_ready, install_export
        client = self._local_client(required=False)
        require_export_ready(self.work, client)
        changes = self._client_data_changes(client) if client else None
        result = self._export_client_data()
        if client:
            backup = install_export(self.work, client, lambda: self._apply_client_changes(client, changes))
            result.update(local_client_synced=True, copied_files=8, backup=backup,
                          message='All four client data files overwritten in the local client root and Resources folder. Originals saved in ' + backup + '.')
            if result['filter_applied']:
                result['message'] += ' Spell compatibility remains on: ' + str(result['spell_filter']['removed_rows']) + ' high IDs excluded. Latest full spell export retained for Restore.'
        else:
            result.update(local_client_synced=False, copied_files=0,
                          message='Client data ZIP generated. No local client is imported, so no local files were copied.')
        atomic_json(self.work / 'logs/client-data-sync.json', result)
        spire.record_export(self, result)
        self.log(result['message'])
        return result

    def _export_client_data(self):
        """Run the real database exporter, then apply the saved client policy."""
        self.ensure_db()
        self.write_config()
        runtime = self.work / 'server'
        for name in CLIENT_FILES: (runtime / 'export' / name).unlink(missing_ok=True)
        self.run([runtime / 'bin/export_client_files'], cwd=runtime, timeout=600)
        for name in CLIENT_FILES:
            source = runtime / 'export' / name
            if source.is_symlink() or not source.is_file() or not source.stat().st_size:
                raise ValueError('Exporter did not create a regular nonempty file: ' + name)
        from managed_content import digest
        from client_spells import test_record, prepare_export
        record = test_record(self.work)
        if record and record['state'] not in ('applied', 'restored'):
            raise ValueError('Spell file update incomplete. Use Restore full spell files before exporting')
        filtering = record.get('state') == 'applied'
        compatibility = prepare_export(runtime / 'export/spells_us.txt') if filtering else None
        file_hashes = {name: digest(runtime / 'export' / name) for name in CLIENT_FILES}
        spell_report = {'filter_applied': filtering, 'sha256': file_hashes['spells_us.txt'],
                        'spell_filter': compatibility,
                        'message': 'ROF2 compatibility export; complete original retained.' if filtering else 'Full export; all spell rows retained.'}
        atomic_json(self.work / 'logs/client-spell-export.json', spell_report)
        target = self.work / 'exports' / ('client-data-' + time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3) + '.zip')
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
            for name in CLIENT_FILES:
                z.write(runtime / 'export' / name, name)
                z.write(runtime / 'export' / name, 'Resources/' + name)
            z.writestr('client-data-export.json', json.dumps({'filter_applied': filtering, 'sha256': file_hashes, 'spell_filter': compatibility}, indent=2)+'\n')
        return {'file': str(target.relative_to(self.work)), 'files': list(CLIENT_FILES),
                'filter_applied': filtering, 'sha256': file_hashes, 'spell_filter': compatibility}

    def files(self, args):
        root = self.work
        p = safe_path(root, args.get('path',''),True)
        if not p.is_dir(): raise ValueError('Select a folder')
        query = args.get('query', '')
        offset, limit = args.get('offset', 0), args.get('limit', 2000)
        if not isinstance(query, str) or len(query) > 256: raise ValueError('Search must be at most 256 characters')
        if type(offset) is not int or offset < 0: raise ValueError('Invalid file page offset')
        if type(limit) is not int or not 1 <= limit <= 2000: raise ValueError('Invalid file page size')
        query = query.strip().casefold()
        items=[]
        for entry in p.iterdir():
            if entry.is_symlink(): continue
            if entry.name in ('settings.json','mysql.cnf','mysql.sock','mysql.pid'): continue
            # Filter the whole directory before pagination, including names past
            # the former 2,000-entry cutoff. Never descend into subdirectories.
            if query not in entry.name.casefold(): continue
            try:
                items.append({'name':entry.name,'path':str(entry.relative_to(root)), 'directory':entry.is_dir(),'size':entry.stat().st_size if entry.is_file() else 0})
            except FileNotFoundError:
                continue  # A running process may rotate/remove a file while listing.
        items.sort(key=lambda x:(not x['directory'],x['name'].casefold(),x['name']))
        total = len(items)
        offset = min(offset, ((total - 1) // limit) * limit if total else 0)
        return {'path':str(p.relative_to(root)), 'items':items[offset:offset+limit],
                'total':total, 'offset':offset, 'limit':limit,
                'next_offset':offset+limit if offset+limit < total else None}

    def edit_file(self, args):
        if self.server_running(): raise ValueError('Stop the server before changing runtime files')
        if self.db and self.db.poll() is None and (args.get('path','').startswith('database') or args.get('destination','').startswith('database')):
            raise ValueError('Use database backup/restore to change MariaDB data')
        src=safe_path(self.work,args['path'],True)
        if not any(src.is_relative_to(self.work / x) for x in ('server','maps','sources','incoming','backups','exports')): raise ValueError('This location is managed by the app')
        dest=safe_path(self.work,args['destination'])
        if not any(dest.is_relative_to(self.work / x) for x in ('server','maps','incoming','backups','exports')): raise ValueError('Choose a server, maps, incoming, backups or exports destination')
        if dest.exists(): raise ValueError('Destination already exists; move it to a backup path first')
        if src==dest or dest.is_relative_to(src): raise ValueError('Invalid destination')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if args.get('action')=='move': shutil.move(src,dest)
        elif src.is_dir(): shutil.copytree(src,dest)
        else: shutil.copy2(src,dest)
        return {'destination':str(dest.relative_to(self.work))}

    def export_logs(self,args):
        path=self.work/'exports'/('logs-'+time.strftime('%Y%m%d-%H%M%S')+'.zip')
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for root in (self.work/'logs', self.work/'server/logs'):
                for p in root.rglob('*') if root.exists() else []:
                    if p.is_file() and not p.is_symlink(): z.write(p,str(p.relative_to(self.work)))
            z.writestr('status.json',json.dumps(self.state(),indent=2))
        return {'file':str(path.relative_to(self.work))}

    def logs(self,args):
        name=args.get('name','control.log')
        root=self.work/'server/logs' if name.startswith('server/') else self.work/'logs'
        p=safe_path(root,name.removeprefix('server/'))
        names=[p.name for p in (self.work/'logs').glob('*.log')]
        server_logs=self.work/'server/logs'
        if server_logs.exists(): names += ['server/'+str(p.relative_to(server_logs)) for p in server_logs.rglob('*.log') if not p.is_symlink()]
        if not p.exists(): return {'text':'No log output yet.'}
        with p.open('rb') as f:
            f.seek(max(0,p.stat().st_size-64000))
            text=f.read().decode(errors='replace')
        return {'text':text,'names':sorted(names)}

    def state(self):
        source=self.work/'sources/current/trasc-source.json'
        config={k:v for k,v in self.config.items() if 'password' not in k and 'key' not in k}
        return {'version':VERSION,'settings':config,'source':json.loads(source.read_text()) if source.exists() else None,
            'runtime_ready':True,'database_running':bool(self.db and self.db.poll() is None),'database_imported':self.config['database_imported'],
            'maps_ready':(self.work/'maps/base').is_dir(),'binaries_ready':all((self.work/'server/bin'/x).exists() for x in BINARIES),
            'build_ready':(self.work/'server/bin.staged/build-info.json').exists(), 'rollback_ready':(self.work/'server/bin.previous').exists(),
            'processes':{name:{'pid':p.pid,'running':p.poll() is None,'exit':p.poll()} for name,p in self.processes.items()},
            'jobs':self.jobs,'free_bytes':shutil.disk_usage(self.work).free,'running':self.server_running(),
            'nektulos':self.nektulos_status(), 'client':self.client_status()}

    def dispatch(self,op,args):
        if op in ('spire_catalog','spire_search','spire_detail','spire_preview','spire_apply','spire_history'):
            return spire.dispatch(self,op,args)
        methods={'client_settings':lambda a:client_settings.inspect(self,a),'client_settings_save':lambda a:client_settings.save(self,a),
            'client_addons_scan':lambda a:client_addons.scan(self,a),
            'client_addons_lock':lambda a:client_addons.set_lock(self,a),'client_addons_copy':lambda a:client_addons.copy_files(self,a),
            'client_dll_status':lambda a:client_dll.compiler_status(self,a),
            'client_dll_sdk':lambda a:client_dll.import_sdk(self,a),
            'client_dll_deploy':lambda a:client_dll.deploy_dll(self,a),
            'player_export':lambda a:player_data.export_players(self,a),'player_preview':lambda a:player_data.preview_players(self,a),
            'player_restore':lambda a:player_data.restore_players(self,a),
            'import_source':self.import_source,'import_maps':self.import_maps,'import_database':self.import_database,
            'build':self.build,'deploy':self.deploy,'rollback':self.rollback,'start':self.start,'stop':self.stop,
            'backup_database':self.backup_database,'restore_database':self.restore_database,'export_client':self.export_client,
            'gameplay':self.gameplay,'save_gameplay':self.save_gameplay,'network':self.network,'sql':self.sql,
            'prepare_session_backup':self.prepare_session_backup,
            'fix_nektulos':self.fix_nektulos,'revert_nektulos':self.revert_nektulos,
            'import_client_zip':self.import_client_zip,
            'prepare_client':self.prepare_client,
            'apply_spell_test':self.apply_spell_test,'restore_spell_test':self.restore_spell_test,
            'files':self.files,'edit_file':self.edit_file,'export_logs':self.export_logs,'logs':self.logs,
            'databases':lambda a:{'candidates':self.database_candidates()},'state':lambda a:self.state()}
        if op not in methods: raise ValueError('Unknown operation')
        return methods[op](args)


def serve(work, port, token):
    engine=Engine(work)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+token):
                self.send_error(403); return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<0 or size>1100000: raise ValueError('Request too large')
                data=json.loads(self.rfile.read(size))
                op,args=data['operation'],data.get('args',{})
                if op=='exit':
                    engine.cancel.set()
                    threading.Thread(target=server.shutdown,daemon=True).start()
                    result={'message':'Stopping all processes and database'}
                elif op=='cancel': engine.cancel.set(); result={'message':'Cancellation requested'}
                elif op in ('state','files','logs','databases','client_dll_status'): result=engine.dispatch(op,args)
                else: result=engine.enqueue(op,args)
                payload=json.dumps({'ok':True,'result':result}).encode()
            except Exception as e:
                payload=json.dumps({'ok':False,'error':str(e)}).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    def shutdown(sig,frame):
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    try: server.serve_forever()
    finally: engine.shutdown(); server.server_close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',default='/work')
    parser.add_argument('--port',type=int,default=18775)
    parser.add_argument('--token-file',required=True)
    a=parser.parse_args()
    serve(a.work,a.port,Path(a.token_file).read_text().strip())
