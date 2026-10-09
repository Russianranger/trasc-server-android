"""TAKP content, fresh database initialization and local server deployment.

Every operation stays inside the TAKP workspace. Initial seed installation
qualifies a new database before changing the active name; it never replaces an
existing Custom, Traditional or TAKP player database.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sys
import time
import zipfile

import takp_build as build
import traditional_content
from log_retention import rotate

QUESTS_REPOSITORY = 'https://github.com/Russianranger/queststakp'
QUESTS_REVISION = 'f43d4fcfa89fecd76b5ac3fb5096f8d658a6c65f'
MAPS_REPOSITORY = 'https://github.com/Russianranger/Mapstakp'
MAPS_REVISION = '95cb9322b853e7ec2f67158b87442286315042eb'
CLIENT_FILES = ('spells_us.txt', 'SkillCaps.txt')
MARKER = '.trasc-takp-content.json'
ASSETS = {'patches/patch_Mac.conf': 'utils/patches/patch_Mac.conf',
          'opcodes/opcodes.conf': 'utils/patches/opcodes.conf',
          'opcodes/chat_opcodes.conf': 'utils/patches/chat_opcodes.conf',
          'opcodes/login_opcodes_oldver.conf': 'loginserver/login_util/login_opcodes_oldver.conf'}
SEED_UPDATES = ('2025_05_26_Add_Detail_Player_Event_Logging.sql',
                '2025_07_05_player_event_logs_table.sql')


def _require(engine):
    if engine.profile != 'takp':
        raise ValueError('This operation belongs to TAKP World')


def _rows(engine, query):
    return [line.split('\t') for line in engine.mysql(query).splitlines()[1:] if line]


def recover(engine):
    """Recover interrupted component swaps and binary activation."""
    from engine import safe_path
    for kind in ('quests', 'maps', 'assets', 'binaries'):
        journal = build._path(engine, 'run/takp-' + kind + '-swap.json')
        if not journal.exists():
            continue
        value = json.loads(journal.read_text())
        destination = safe_path(engine.work, value['destination'])
        backup = safe_path(engine.work, value['backup'])
        prepared = safe_path(engine.work, value['prepared'])
        if destination.exists():
            # A directory is activated only after it has a complete marker.
            marker = destination / ('deployment.json' if kind == 'binaries' else MARKER)
            if not marker.is_file() and backup.exists():
                raise ValueError('Interrupted TAKP activation needs attention: ' + kind)
        elif backup.exists():
            os.replace(backup, destination)
        elif value.get('previous'):
            raise ValueError('Interrupted TAKP activation is missing its previous directory: ' + kind)
        if prepared.exists():
            shutil.rmtree(prepared)
        journal.unlink()


def _activate(engine, kind, prepared, destination, marker):
    from engine import atomic_json
    recover(engine)
    backup = build._path(engine, 'backups/takp-' + kind + '-' + time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
    journal = build._path(engine, 'run/takp-' + kind + '-swap.json')
    atomic_json(prepared / MARKER, marker)
    atomic_json(journal, {'destination': str(destination.relative_to(engine.work)),
                         'backup': str(backup.relative_to(engine.work)),
                         'prepared': str(prepared.relative_to(engine.work)), 'previous': destination.exists()})
    try:
        if destination.exists():
            os.replace(destination, backup)
        os.replace(prepared, destination)
        journal.unlink()
    except BaseException:
        if backup.exists() and not destination.exists():
            os.replace(backup, destination)
        if destination.exists():
            journal.unlink(missing_ok=True)
        raise
    return str(backup.relative_to(engine.work)) if backup.exists() else None


def _component(engine, kind):
    target = build._path(engine, 'maps' if kind == 'maps' else 'server/' + kind)
    marker = target / MARKER
    try:
        record = build._json(marker)
        valid = record.get('profile') == 'takp' and record.get('kind') == kind
        if kind == 'maps':
            valid = valid and any(path.is_file() and not path.is_symlink() for path in target.glob('*.map'))
        elif kind == 'quests':
            valid = valid and (target / 'global').is_dir() and (target / 'lua_modules').is_dir()
        elif kind == 'assets':
            valid = valid and all((target / name).is_file() for name in ASSETS)
        return {'imported': bool(valid), 'path': str(target.relative_to(engine.work)), 'source': record}
    except (OSError, ValueError, TypeError):
        return {'imported': False, 'path': str(target.relative_to(engine.work)), 'source': None}


def import_content(engine, args):
    from engine import atomic_json, extract_archive, safe_path
    _require(engine)
    if engine.server_running():
        raise ValueError('Stop the TAKP server before replacing content')
    kind = args.get('kind')
    if kind not in ('quests', 'maps'):
        raise ValueError('TAKP imports support its quests or flat maps; server assets come from the qualified source')
    target = build._path(engine, 'maps' if kind == 'maps' else 'server/quests')
    if _component(engine, kind)['imported'] and not args.get('replace'):
        raise ValueError('Select replacement to preserve a backup and replace TAKP ' + kind)
    stage = build._path(engine, 'run/takp-content-' + secrets.token_hex(6))
    stage.mkdir()
    prepared = stage / 'prepared'
    metadata = {'profile': 'takp', 'kind': kind, 'imported': time.time()}
    try:
        if args.get('url'):
            archive = engine.work / 'incoming' / ('takp-' + kind + '.zip')
            repository, revision = ((QUESTS_REPOSITORY, QUESTS_REVISION) if kind == 'quests'
                                    else (MAPS_REPOSITORY, MAPS_REVISION))
            metadata.update(engine.github_download(args['url'], args.get('ref', revision if args['url'].rstrip('/') == repository else ''), archive))
        else:
            archive = safe_path(engine.work / 'incoming', args['file'], True)
        metadata['archive_sha256'] = build.digest(archive)
        traditional_content.validate_archive_members(archive)
        extract_archive(archive, stage / 'unpacked')
        engine.check_cancel()
        if kind == 'quests':
            root = traditional_content.content_root(stage / 'unpacked', 'quests')
            if not (root / 'global').is_dir() or not (root / 'lua_modules').is_dir():
                raise ValueError('TAKP quests need global/ and lua_modules/ from the TAKP quest fork')
            prepared.mkdir()
            for path in root.iterdir():
                engine.check_cancel()
                if path.name in ('.git', '__MACOSX', MARKER):
                    continue
                if path.is_dir():
                    shutil.copytree(path, prepared / path.name)
                else:
                    shutil.copy2(path, prepared / path.name)
        else:
            roots = [stage / 'unpacked'] + [path for path in (stage / 'unpacked').iterdir() if path.is_dir()]
            roots += [path / 'maps' for path in list(roots) if (path / 'maps').is_dir()]
            matches = [path for path in dict.fromkeys(roots) if any(path.glob('*.map'))]
            if len(matches) != 1:
                raise ValueError('TAKP map ZIP must contain flat zone .map/.path/.wtr/.nav files')
            root = matches[0]
            prepared.mkdir()
            count = 0
            for path in root.iterdir():
                engine.check_cancel()
                if path.is_file() and (path.suffix.lower() in ('.map', '.wtr', '.path', '.nav') or path.name.startswith(('LICENSE', 'README'))):
                    shutil.copy2(path, prepared / path.name)
                    count += 1
            metadata['files'] = count
        backup = _activate(engine, kind, prepared, target, metadata)
        return {'component': _component(engine, kind), 'backup': backup,
                'message': 'TAKP ' + kind + ' imported' + ('; previous files retained at ' + backup if backup else '.')}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def sync_content(engine):
    _require(engine)
    source = engine.source_root()
    if not _component(engine, 'assets')['imported']:
        prepared = build._path(engine, 'run/takp-assets-' + secrets.token_hex(6))
        prepared.mkdir()
        try:
            for destination, relative in ASSETS.items():
                path = source / relative
                if not path.is_file() or path.is_symlink():
                    raise ValueError('TAKP source lacks runtime opcode asset: ' + relative)
                output = prepared / destination
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, output)
            _activate(engine, 'assets', prepared, build._path(engine, 'server/assets'),
                      {'profile': 'takp', 'kind': 'assets', 'commit': build.REVISION, 'imported': time.time()})
        finally:
            if prepared.exists():
                shutil.rmtree(prepared)
    for folder in ('shared', 'logs', 'export'):
        build._path(engine, 'server/' + folder).mkdir(exist_ok=True)


def setup(engine, args):
    _require(engine)
    if engine.server_running():
        raise ValueError('Stop the TAKP server before setting up its content')
    source = engine.work / 'sources/current/trasc-source.json'
    if not source.exists():
        engine.import_source({'url': build.REPOSITORY, 'ref': build.REVISION})
    else:
        build.qualify_source(engine.source_root(), engine.check_cancel)
    sync_content(engine)
    for kind, repository, revision in (('quests', QUESTS_REPOSITORY, QUESTS_REVISION),
                                        ('maps', MAPS_REPOSITORY, MAPS_REVISION)):
        if not _component(engine, kind)['imported']:
            import_content(engine, {'kind': kind, 'url': repository, 'ref': revision})
    return {'message': 'TAKP server, quests, maps and opcode assets are ready. Compile and initialize its independent database.',
            'takp': status(engine)}


def seed_parts(source):
    """Select the four mandatory seed parts; never execute drop_system.sql."""
    archive = Path(source) / 'utils/sql/database_full/alkabor_latest.zip'
    if build.digest(archive) != build.SEED_SHA256:
        raise ValueError('TAKP seed does not match the qualified September 8 database')
    with zipfile.ZipFile(archive) as opened:
        selected = []
        for prefix in ('alkabor_', 'player_tables_', 'login_tables_', 'data_tables_'):
            matches = [entry for entry in opened.infolist() if Path(entry.filename).name.startswith(prefix)
                       and entry.filename.endswith('.sql') and not entry.is_dir()]
            if len(matches) != 1:
                raise ValueError('TAKP seed must include exactly one ' + prefix + ' SQL part')
            selected.append(matches[0].filename)
    return archive, selected


def _bot_command(engine, mode):
    source = engine.source_root()
    installer = source / 'utils/sql/player_bots/install.py'
    engine.run([sys.executable, installer, '--database', engine.config['database'],
                '--defaults-extra-file', engine.mysql_options, mode], timeout=600, private=True)


def verify_database(engine):
    if not engine.config.get('takp_database_initialized'):
        raise ValueError('Initialize the independent TAKP database first')
    engine.ensure_db()
    required = {'account', 'character_data', 'character_inventory', 'rule_values', 'variables', 'launcher',
                'tblLoginServerAccounts', 'tblServerListType', 'player_event_log_settings', 'player_event_logs'}
    available = {row[0] for row in _rows(engine, 'SHOW TABLES;')}
    if required - available:
        raise ValueError('TAKP database is missing required tables: ' + ', '.join(sorted(required - available)))
    _bot_command(engine, '--verify')
    if not _rows(engine, "SHOW COLUMNS FROM player_event_log_settings LIKE 'etl_enabled';"):
        raise ValueError('TAKP player event schema update is missing')
    if not _rows(engine, "SHOW COLUMNS FROM player_event_logs LIKE 'etl_table_id';"):
        raise ValueError('TAKP player event log schema update is missing')


def initialize_database(engine, args):
    _require(engine)
    if engine.server_running():
        raise ValueError('Stop the TAKP server before initializing its database')
    if engine.config.get('database_imported') or engine.config.get('takp_database_initialized'):
        raise ValueError('TAKP database already exists. Initialization never replaces existing player data.')
    source = engine.source_root()
    build.qualify_source(source, engine.check_cancel)
    archive, members = seed_parts(source)
    engine.ensure_db()
    if _rows(engine, 'SHOW TABLES;'):
        raise ValueError('The selected TAKP database already contains tables; initialization leaves them unchanged')
    # A fresh randomly named schema is qualified before selecting it. Failure
    # leaves the previously active database and settings untouched.
    previous = dict(engine.config)
    database = 'takp_' + secrets.token_hex(6)
    engine.mysql('CREATE DATABASE `' + database + '` CHARACTER SET utf8mb4;', database=False)
    dump = build._path(engine, 'run/takp-seed.sql')
    try:
        with zipfile.ZipFile(archive) as opened, dump.open('wb') as output:
            for member in members:
                with opened.open(member) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        engine.check_cancel()
                        output.write(block)
                output.write(b'\n')
        engine.run(['mariadb', '--defaults-extra-file=' + str(engine.mysql_options), database],
                   input_file=dump, timeout=1800, private=True)
        engine.config['database'] = database
        for filename in SEED_UPDATES:
            engine.run(['mariadb', '--defaults-extra-file=' + str(engine.mysql_options), database],
                       input_file=source / 'utils/sql/git/required' / filename, timeout=300, private=True)
        _bot_command(engine, '--apply')
        engine.mysql("INSERT INTO tblServerListType (ServerListTypeID,ServerListTypeDescription) VALUES (1,'Legends'),(2,'Preferred'),(3,'Standard');")
        engine.mysql("GRANT ALL ON `" + database + "`.* TO 'trasc'@'127.0.0.1';", database=False)
        engine.config.update(database_imported=True, takp_database_initialized=True, takp_bot_schema_ready=True,
                             database_source='TAKP September 8, 2026', takp_seed_sha256=build.SEED_SHA256,
                             takp_local_accounts=0, takp_seed_updates=list(SEED_UPDATES))
        verify_database(engine)
        sync_content(engine)
        write_config(engine)
        engine.save()
    except BaseException:
        engine.config = previous
        with contextlib.suppress(OSError, ValueError):
            write_config(engine)
        with contextlib.suppress(OSError, ValueError):
            engine.mysql('DROP DATABASE IF EXISTS `' + database + '`;', database=False)
        raise
    finally:
        dump.unlink(missing_ok=True)
    return {'message': 'TAKP database initialized with all eleven playerbot migrations. Create a local login account before playing.',
            'database': database, 'bot_versions': list(range(1, 12)), 'seed_sha256': build.SEED_SHA256}


def create_account(engine, args):
    from engine import sql_string
    _require(engine)
    username, password = args.get('username', ''), args.get('password', '')
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,19}', username):
        raise ValueError('TAKP login names must contain 1–19 letters, digits or underscores')
    if not isinstance(password, str) or not re.fullmatch(r'[!-~]{1,19}', password):
        raise ValueError('TAKP passwords must contain 1–19 printable ASCII characters without spaces')
    verify_database(engine)
    if _rows(engine, 'SELECT LoginServerID FROM tblLoginServerAccounts WHERE AccountName=' + sql_string(username) + ';'):
        raise ValueError('That TAKP login account already exists; its password was left unchanged')
    salted = hashlib.sha1((password + engine.config['server_key']).encode()).hexdigest()
    engine.mysql("INSERT INTO tblLoginServerAccounts (AccountName,AccountPassword,AccountEmail,LastLoginDate,LastIPAddress,creationIP,ForumName) VALUES ("
                 + sql_string(username) + ", '" + salted + "', 'local_creation',NOW(),'127.0.0.1','127.0.0.1'," + sql_string(username) + ');')
    engine.config['takp_local_accounts'] = int(_rows(engine, 'SELECT COUNT(*) FROM tblLoginServerAccounts;')[0][0])
    engine.save()
    return {'username': username, 'message': 'Local TAKP login created. Use this name and password in the TAKP client.'}


def write_config(engine):
    from engine import atomic_json
    _require(engine)
    database = {'host': '127.0.0.1', 'port': engine.config['db_port'], 'username': 'trasc',
                'password': engine.config['db_password'], 'db': engine.config['database']}
    runtime = engine.work / 'server'
    server = {'world': {'shortname': 'TAKP', 'longname': 'TAKP World on Android',
                       'address': engine.config['ip'], 'localaddress': engine.config['ip'],
                       'key': engine.config['server_key'],
                       'loginserver': {'host': '127.0.0.1', 'port': 5998, 'account': '', 'password': '', 'legacy': 0},
                       'tcp': {'ip': '127.0.0.1', 'port': 9000},
                       'telnet': {'enabled': False}, 'http': {'enabled': False}},
              'database': database.copy(), 'qsdatabase': database.copy(), 'content_database': database.copy(),
              'ucs': {'host': engine.config['ip'], 'port': 7778},
              'queryserver': {'host': '127.0.0.1', 'port': 9003},
              'zones': {'defaultstatus': 0, 'ports': {'low': 7000, 'high': 7100}},
              'directories': {'maps': str(engine.work / 'maps'), 'quests': 'quests',
                              'lua_modules': 'quests/lua_modules', 'patches': 'assets/patches',
                              'opcodes': 'assets/opcodes', 'shared_memory': 'shared/', 'logs': 'logs'},
              'files': {'opcodes': 'opcodes.conf', 'chat_opcodes': 'chat_opcodes.conf'},
              'launcher': {'exe': str(runtime / 'bin/zone')}, 'auto_database_updates': False}
    login_database = {'host': '127.0.0.1', 'port': engine.config['db_port'], 'user': 'trasc',
                      'password': engine.config['db_password'], 'db': engine.config['database']}
    login = {'database': dict(login_database, salt=engine.config['server_key']),
             'logsys_database': login_database,
             'account': {'auto_create_accounts': False},
             'worldservers': {'unregistered_allowed': True, 'reject_duplicate_servers': False,
                              'pc_client_allowed': True, 'intel_client_allowed': True, 'ticket_client_allowed': True},
             'security': {'mode': 5, 'allow_password_login': True, 'allow_token_login': False},
             'client_configuration': {'listen_port': 5998, 'local_network': '127.0.0.1', 'network_ip': engine.config['ip']},
             'Old': {'port': engine.config['login_port'], 'opcodes': 'login_opcodes_oldver.conf'},
             'schema': {'account_table': 'tblLoginServerAccounts', 'world_registration_table': 'tblWorldServerRegistration',
                        'world_admin_registration_table': 'tblServerAdminRegistration', 'world_server_type_table': 'tblServerListType'}}
    for filename, data in (('eqemu_config.json', {'server': server}), ('login.json', login)):
        path = build._path(engine, 'server/' + filename)
        atomic_json(path, data)
        path.chmod(0o600)


def deploy(engine, args):
    from engine import atomic_json
    _require(engine)
    if engine.server_running():
        raise ValueError('Stop the TAKP server before deployment')
    info = build.record(engine)
    verify_database(engine)
    if not _component(engine, 'quests')['imported'] or not _component(engine, 'maps')['imported']:
        raise ValueError('Import the TAKP quests and flat maps before deployment')
    sync_content(engine)
    write_config(engine)
    staged = build._path(engine, 'server/bin.staged')
    current = build._path(engine, 'server/bin')
    previous = build._path(engine, 'server/bin.previous')
    atomic_json(staged / 'deployment.json', {'format': 1, 'profile': 'takp', 'source_commit': build.REVISION,
                                            'database': engine.config['database'], 'seed_sha256': build.SEED_SHA256,
                                            'recipe': build.RECIPE, 'deployed': time.time()})
    journal = build._path(engine, 'run/takp-binaries-swap.json')
    atomic_json(journal, {'destination': 'server/bin', 'backup': 'server/bin.previous',
                         'prepared': 'server/bin.staged', 'previous': current.exists()})
    try:
        if previous.exists():
            shutil.rmtree(previous)
        if current.exists():
            os.replace(current, previous)
        os.replace(staged, current)
        journal.unlink()
    except BaseException:
        if previous.exists() and not current.exists():
            os.replace(previous, current)
        journal.unlink(missing_ok=True)
        raise
    return {'message': 'TAKP server deployed. Start it, then prepare the TAKP client.', 'deployed': True}


def rollback(engine, args):
    _require(engine)
    if engine.server_running():
        raise ValueError('Stop the TAKP server before restoring its previous binaries')
    build.record(engine, 'server/bin.previous')
    current, previous, swap = (build._path(engine, 'server/' + name) for name in ('bin', 'bin.previous', 'bin.swap'))
    if swap.exists():
        raise ValueError('Interrupted TAKP rollback needs attention')
    os.replace(current, swap)
    os.replace(previous, current)
    os.replace(swap, previous)
    return {'message': 'Previous TAKP server binaries restored.'}


def require_client_data(engine):
    build.record(engine, 'server/bin')
    verify_database(engine)


def start(engine, args):
    _require(engine)
    if engine.server_running():
        raise ValueError('TAKP server processes are already running')
    build.record(engine, 'server/bin')
    verify_database(engine)
    if not int(_rows(engine, 'SELECT COUNT(*) FROM tblLoginServerAccounts;')[0][0]):
        raise ValueError('Create a local TAKP login account before starting its server')
    if not _component(engine, 'quests')['imported'] or not _component(engine, 'maps')['imported']:
        raise ValueError('Import TAKP quests and maps before starting')
    write_config(engine)
    engine.mysql("INSERT INTO launcher (name,dynamics) VALUES ('takp',%d) ON DUPLICATE KEY UPDATE dynamics=VALUES(dynamics);" % int(engine.config['workers']))
    try:
        runtime = engine.work / 'server'
        engine.run([runtime / 'bin/shared_memory'], cwd=runtime, timeout=600)
        engine.launch('loginserver')
        engine.launch('world')
        for _ in range(120):
            engine.check_cancel()
            if any(engine.processes[name].poll() is not None for name in ('world', 'loginserver')):
                raise ValueError('TAKP world or login server stopped; inspect its log')
            try:
                with socket.create_connection(('127.0.0.1', 9000), timeout=1):
                    break
            except OSError:
                time.sleep(1)
        else:
            raise ValueError('TAKP world did not become ready within two minutes')
        for name in ('ucs', 'queryserv'):
            engine.launch(name)
        for path in (runtime / 'logs').glob('zone-dynamic_*.log'):
            rotate(path)
        engine.launch('eqlaunch', 'takp')
        time.sleep(3)
        failed = [name for name, process in engine.processes.items() if process.poll() is not None]
        if failed:
            raise ValueError('TAKP processes stopped during startup: ' + ', '.join(failed))
        engine.config['rules_pending_restart'] = False
        engine.save()
        return {'message': 'TAKP server started. Its legacy client login listens on UDP ' + str(engine.config['login_port']) + '.',
                'endpoint': engine.config['ip'] + ':' + str(engine.config['login_port'])}
    except BaseException:
        engine.stop({})
        raise


def export_client_data(engine):
    from engine import atomic_json
    require_client_data(engine)
    write_config(engine)
    runtime = engine.work / 'server'
    export = runtime / 'export'
    export.mkdir(exist_ok=True)
    for name in CLIENT_FILES:
        (export / name).unlink(missing_ok=True)
    engine.run([runtime / 'bin/export_client_files'], cwd=runtime, timeout=600)
    hashes = {}
    for name in CLIENT_FILES:
        path = export / name
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError('TAKP exporter did not create a regular nonempty file: ' + name)
        hashes[name] = build.digest(path)
    target = engine.work / 'exports' / ('takp-client-data-' + time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3) + '.zip')
    result = {'profile': 'takp', 'file': str(target.relative_to(engine.work)), 'files': list(CLIENT_FILES),
              'filter_applied': False, 'spell_filter': None, 'sha256': hashes}
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as packed:
        for name in CLIENT_FILES:
            packed.write(export / name, name)
        packed.writestr('client-data-export.json', json.dumps(result, indent=2) + '\n')
    atomic_json(engine.work / 'logs/client-spell-export.json', result)
    return result


def status(engine):
    compilation = build.status(engine)
    content = {kind: _component(engine, kind) for kind in ('quests', 'maps', 'assets')}
    database = bool(engine.config.get('takp_database_initialized') and engine.config.get('database_imported'))
    bots = bool(database and engine.config.get('takp_bot_schema_ready'))
    ready = database and bots and all(item['imported'] for item in content.values())
    idle = not engine.server_running()
    deployment = {'deploy_allowed': bool(compilation['staged_valid'] and ready and idle),
                  'start_allowed': bool(compilation['deployed_valid'] and ready and engine.config.get('takp_local_accounts', 0)),
                  'client_data_allowed': bool(compilation['deployed_valid'] and database and bots),
                  'rollback_allowed': bool(compilation['previous_valid'] and idle)}
    if not compilation['source_ready']:
        message = 'Fetch the TAKP server, quests and maps first.'
    elif not compilation['runtime_ready']:
        message = compilation['runtime_message']
    elif not compilation['staged_valid'] and not compilation['deployed_valid']:
        message = 'Compile the TAKP ARM64 server.'
    elif not database:
        message = 'Initialize the independent TAKP database.'
    elif not engine.config.get('takp_local_accounts', 0):
        message = 'Create a local TAKP login account.'
    elif not compilation['deployed_valid']:
        message = 'Deploy the verified TAKP server build.'
    else:
        message = 'TAKP server and local login are ready.'
    return {'source_ready': compilation['source_ready'], 'quests_ready': content['quests']['imported'],
            'maps_ready': content['maps']['imported'], 'database_ready': database, 'bot_schema_ready': bots,
            'local_accounts': engine.config.get('takp_local_accounts', 0), 'build': compilation,
            'deployment': deployment, 'components': content, 'message': message,
            'login_port': engine.config['login_port'],
            'provenance': {'server': {'repo': build.REPOSITORY, 'commit': build.REVISION},
                           'quests': {'repo': QUESTS_REPOSITORY, 'commit': QUESTS_REVISION},
                           'maps': {'repo': MAPS_REPOSITORY, 'commit': MAPS_REVISION}, 'seed_sha256': build.SEED_SHA256}}
