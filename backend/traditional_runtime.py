"""Offline deployment and local login for the qualified Traditional build.

Compilation manifests remain unchanged, including builds made with 0.6.5–0.6.7.
This adapter validates them before activation and never runs Custom repairs.
"""
import json
import os
from pathlib import PurePosixPath
import re
import secrets
import shutil
import socket
import time

import traditional_build as build
import traditional_content as content

DATABASE_VERSION = 9328
BOTS_VERSION = 9055
REQUIRED_ASSETS = ('patches/patch_RoF2.conf', 'opcodes/opcodes.conf',
                   'opcodes/mail_opcodes.conf', 'opcodes/login_opcodes.conf',
                   'opcodes/login_opcodes_sod.conf', 'opcodes/login_opcodes_larion.conf')
SCHEMA = {
    'account': ('id', 'name', 'lsaccount_id'),
    'character_data': ('id', 'account_id', 'name'),
    'rule_sets': ('ruleset_id', 'name'),
    'rule_values': ('ruleset_id', 'rule_name', 'rule_value'),
    'variables': ('varname', 'value'),
    'launcher': ('name', 'dynamics'),
    'db_version': ('version', 'bots_version', 'custom_version'),
    'login_accounts': ('id', 'account_name', 'account_password', 'account_email',
                       'source_loginserver', 'last_ip_address', 'last_login_date',
                       'created_at', 'updated_at'),
    'login_server_admins': ('id', 'account_name', 'account_password'),
    'login_server_list_types': ('id', 'description'),
    'login_world_servers': ('id', 'long_name', 'short_name', 'tag_description',
                          'login_server_list_type_id', 'last_login_date',
                          'last_ip_address', 'login_server_admin_id', 'is_server_trusted', 'note'),
    'login_api_tokens': ('id', 'token', 'can_read', 'can_write'),
}


def _path(engine, relative, directory=False):
    """Validate every existing ancestor, not only the resolved final path."""
    parsed = PurePosixPath(relative)
    if parsed.is_absolute() or '..' in parsed.parts or '\\' in relative or '\x00' in relative:
        raise ValueError('Traditional path escapes the workspace')
    path = engine.work / relative
    if not path.is_relative_to(engine.work):
        raise ValueError('Traditional path escapes the workspace')
    for candidate in (path, *path.parents):
        if candidate == engine.work.parent:
            break
        if candidate.is_symlink():
            raise ValueError('Traditional deployment paths cannot be symbolic links')
    if path.exists() and (not path.is_dir() if directory else not path.is_file()):
        raise ValueError('Invalid Traditional deployment path: ' + relative)
    return path


def _record(engine, name='server/bin'):
    root = _path(engine, name, True)
    info_path = _path(engine, name + '/build-info.json')
    report_path = _path(engine, name + '/verification.json')
    info, report = build._json(info_path), build._json(report_path)
    runtime = build._runtime(engine)
    if (not runtime['ready'] or info.get('format') != 1 or info.get('recipe') != build.RECIPE
            or info.get('recipe_identity') != build._recipe_identity()
            or info.get('runtime_identity') != runtime['identity']
            or info.get('verification_sha256') != build._digest(report)):
        raise ValueError('Traditional binaries do not match the qualified runtime and build recipe')
    signature = (name, build._stat_signature(info_path), build._stat_signature(report_path),
                 tuple((binary, build._stat_signature(_path(engine, name + '/' + binary)))
                       for binary in build.BINARIES), runtime['identity'])
    caches = getattr(engine, '_traditional_deployed_cache', {})
    cached = caches.get(name)
    if not cached or cached[0] != signature:
        build._verification(report, root, engine.check_cancel)
        caches[name] = (signature, info)
        engine._traditional_deployed_cache = caches
    return info


def _assets_ready(engine):
    try:
        return all(_path(engine, 'server/assets/' + name).stat().st_size > 0
                   for name in REQUIRED_ASSETS)
    except (OSError, ValueError):
        return False


def _compatible_helpers(engine, component):
    """The pinned zone binary requires CheckHandin in each helper directory."""
    try:
        root = _path(engine, component['path'], True)
        files = [_path(engine, str(path.relative_to(engine.work))) for path in root.iterdir()
                 if path.is_file()]
        signature = tuple((str(path), build._stat_signature(path)) for path in sorted(files))
        caches = getattr(engine, '_traditional_helpers_cache', {})
        cached = caches.get(component['path'])
        if cached and cached[0] == signature:
            return cached[1]
        compatible = False
        for path in files:
            # Match the server's top-level content check without reading an
            # arbitrarily large user-provided file into memory.
            previous = b''
            with path.open('rb') as source:
                for block in iter(lambda: source.read(65536), b''):
                    if b'CheckHandin' in previous + block:
                        compatible = True
                        break
                    previous = block[-16:]
            if compatible:
                break
        caches[component['path']] = (signature, compatible)
        engine._traditional_helpers_cache = caches
        return compatible
    except (OSError, ValueError):
        return False


def prerequisites(engine):
    components = content.components(engine)
    missing = []
    if not engine.config.get('database_imported'):
        missing.append('Import the complete PEQ database')
    for kind, label in (('quests', 'quests'), ('plugins', 'Perl plugins'),
                        ('lua_modules', 'Lua modules')):
        if not components[kind]['imported']:
            missing.append('Import quests containing ' + label if kind != 'quests'
                           else 'Import the quest repository')
        elif kind != 'quests' and not _compatible_helpers(engine, components[kind]):
            missing.append('Update the ' + label + ' from ProjectEQ quests: this server requires CheckHandin support')
    if not _assets_ready(engine):
        missing.append('Import the complete server assets including RoF2 and all login opcodes')
    return missing


def status(engine, staged=None):
    missing = prerequisites(engine)
    valid = previous_valid = False
    message = 'Deploy the compiled Traditional server'
    try:
        info = _record(engine)
        manifest = build._json(_path(engine, 'server/bin/deployment.json'))
        valid = (manifest.get('format') == 1 and manifest.get('profile') == 'traditional'
                 and manifest.get('verification_sha256') == info['verification_sha256']
                 and manifest.get('database_version') == DATABASE_VERSION)
        if not valid:
            message = 'Deploy the verified Traditional build to qualify its database and local login'
    except (OSError, ValueError, KeyError, TypeError) as error:
        message = 'Traditional deployment is not ready: ' + str(error)
    if (engine.work / 'server/bin.previous').exists():
        try:
            _record(engine, 'server/bin.previous')
            previous_valid = (engine.work / 'server/bin.previous/deployment.json').is_file()
        except (OSError, ValueError, KeyError, TypeError):
            pass
    staged = build.status(engine) if staged is None else staged
    recovery = bool(getattr(engine, 'traditional_recovery_error', None) or any(
        (engine.work / name).exists() for name in
        ('run/traditional-deploy.json', 'run/traditional-stage.json', 'server/bin.swap')))
    idle = not engine.server_running()
    try:
        maps = _path(engine, 'maps/base', True).is_dir()
    except ValueError:
        maps = False
    if valid:
        message = 'Traditional binaries, local login and database are deployed. Ready to start.'
    if missing:
        message = '; '.join(missing)
    elif valid and not maps:
        message = 'Import maps before starting the Traditional server'
    if recovery:
        message = 'Interrupted Traditional deployment needs recovery; restart the runtime'
    return {'deployed_valid': valid, 'deploy_allowed': bool(staged.get('staged_valid') and idle and not missing and not recovery),
            'start_allowed': valid and maps and not missing and not recovery,
            'client_data_allowed': valid and not missing and not recovery,
            'rollback_allowed': previous_valid and idle and not recovery,
            'message': message, 'prerequisites': missing,
            'database_version': DATABASE_VERSION, 'login_source': 'local'}


def sync_content(engine):
    missing = prerequisites(engine)
    if missing:
        raise ValueError('; '.join(missing))
    for folder in ('shared', 'logs', 'export'):
        _path(engine, 'server/' + folder, True).mkdir(exist_ok=True)


def write_config(engine):
    from engine import atomic_json
    runtime = _path(engine, 'server', True)
    components = content.components(engine)
    directories = {'maps': str(engine.work / 'maps'), 'quests': 'quests',
                   'plugins': components['plugins']['path'].removeprefix('server/'),
                   'lua_modules': components['lua_modules']['path'].removeprefix('server/'),
                   'patches': 'assets/patches', 'opcodes': 'assets/opcodes',
                   'shared_memory': 'shared/', 'logs': 'logs'}
    db = {'host': '127.0.0.1', 'port': engine.config['db_port'], 'username': 'trasc',
          'password': engine.config['db_password'], 'db': engine.config['database']}
    server = {
        'world': {'shortname': 'Traditional', 'longname': 'Traditional EQEmu on Android',
                  'address': engine.config['ip'], 'localaddress': engine.config['ip'],
                  'key': engine.config['server_key'],
                  'loginserver': {'host': '127.0.0.1', 'port': 5998, 'account': '', 'password': '', 'legacy': 0},
                  'tcp': {'ip': '127.0.0.1', 'port': 9000},
                  'telnet': {'ip': '127.0.0.1', 'port': 9002, 'enabled': False},
                  'http': {'enabled': False}},
        'database': db.copy(), 'content_database': db.copy(), 'qsdatabase': db.copy(),
        'directories': directories,
        'files': {'opcodes': 'assets/opcodes/opcodes.conf', 'mail_opcodes': 'assets/opcodes/mail_opcodes.conf'},
        'zones': {'defaultstatus': 0, 'ports': {'low': 7000, 'high': 7100}},
        'ucs': {'host': engine.config['ip'], 'port': 7778},
        'queryserver': {'host': '127.0.0.1', 'port': 9003},
        'launcher': {'exe': str(runtime / 'bin/zone')},
        # Migrations are an explicit, backed-up deployment operation.
        'auto_database_updates': False, 'disable_config_checks': True,
    }
    login = {'database': {'host': '127.0.0.1', 'port': engine.config['db_port'],
                         'user': 'trasc', 'password': engine.config['db_password'], 'db': engine.config['database']},
             'general': {'listen_port': 5998,
                         'default_loginserver_name': 'local',
                         'eqemu_loginserver_address': engine.config['ip'] + ':' + str(engine.config['login_port'])},
             'security': {'mode': 14, 'allow_token_login': False},
             'account': {'auto_create_accounts': True},
             'worldservers': {'unregistered_allowed': True, 'reject_duplicate_servers': False},
             'client_configuration': {'sod_port': engine.config['login_port']},
             'web_api': {'enabled': False}}
    for filename, value in (('eqemu_config.json', {'server': server}), ('login.json', login)):
        path = _path(engine, 'server/' + filename)
        _path(engine, 'server/' + filename + '.new')
        atomic_json(path, value)
        path.chmod(0o600)


def qualify_database(engine, migrate=False, binary_root='server/bin', allow_pending=False):
    engine.ensure_db()
    tables = set(engine.mysql('SHOW TABLES;').splitlines())
    missing = sorted(set(SCHEMA) - tables)
    if missing:
        raise ValueError('Traditional needs the complete PEQ database including local-login tables. Missing: ' + ', '.join(missing))
    for table, required in SCHEMA.items():
        columns = {row.split('\t', 1)[0] for row in engine.mysql('SHOW COLUMNS FROM `' + table + '`;').splitlines()}
        if not set(required) <= columns:
            raise ValueError('Traditional database schema mismatch in ' + table + ': ' + ', '.join(sorted(set(required) - columns)))
    rows = engine.mysql('SELECT version,bots_version,custom_version FROM db_version;').splitlines()[1:]
    if len(rows) != 1:
        raise ValueError('Traditional db_version must contain exactly one version row')
    try:
        versions = tuple(int(value) for value in rows[0].split('\t'))
    except ValueError:
        raise ValueError('Traditional database version is invalid') from None
    if len(versions) != 3 or versions[0] > DATABASE_VERSION or versions[1] > BOTS_VERSION or versions[2] != 0:
        raise ValueError('The database is newer than or belongs to a different server than this qualified Traditional build')
    if migrate:
        engine.run([engine.work / binary_root / 'world', 'database:updates', '--skip-backup'],
                   cwd=engine.work / 'server', timeout=900)
        rows = engine.mysql('SELECT version,bots_version,custom_version FROM db_version;').splitlines()[1:]
        versions = tuple(int(value) for value in rows[0].split('\t')) if len(rows) == 1 else ()
    if not allow_pending and (len(versions) != 3 or versions[0] != DATABASE_VERSION or versions[1] not in (0, BOTS_VERSION) or versions[2] != 0):
        raise ValueError('Traditional database migrations did not reach the qualified version. Restore the retained database backup if needed; see operation.log.')
    # Never rewrite an imported password or player row. The local login server
    # creates new accounts on their first successful credential handshake.
    if migrate:
        engine.mysql("INSERT IGNORE INTO login_server_list_types (id,description) VALUES (1,'Legends'),(2,'Preferred'),(3,'Standard');")
        # The pinned login server's first-registration branch omits assigning
        # the new ID to its in-memory world. Preseed only this local world.
        engine.mysql("INSERT INTO login_world_servers (long_name,short_name,tag_description,login_server_list_type_id,last_login_date,last_ip_address,login_server_admin_id,is_server_trusted,note) SELECT 'Traditional EQEmu on Android','Traditional','',3,NOW(),'127.0.0.1',0,0,'Traditional local world' WHERE NOT EXISTS (SELECT 1 FROM login_world_servers WHERE long_name='Traditional EQEmu on Android' AND short_name='Traditional');")
    return {'version': versions[0], 'bots_version': versions[1], 'custom_version': versions[2]}


def recover(engine):
    swap = _path(engine, 'server/bin.swap', True)
    if swap.exists():
        _record(engine, 'server/bin.swap')
        current = _path(engine, 'server/bin', True)
        previous = _path(engine, 'server/bin.previous', True)
        if current.exists() == previous.exists():
            raise ValueError('Interrupted Traditional rollback needs manual recovery')
        os.replace(swap, previous if current.exists() else current)
    journal = _path(engine, 'run/traditional-deploy.json')
    if not journal.exists():
        return
    record = build._json(journal)
    if (record.get('format') != 1 or not re.fullmatch(r'[0-9a-f]{24}', str(record.get('id', '')))
            or record.get('backup') != record['id']
            or not isinstance(record.get('had_current'), bool)
            or not isinstance(record.get('had_previous'), bool)
            or not isinstance(record.get('configs'), dict)
            or set(record['configs']) != {'eqemu_config.json', 'login.json'}
            or any(not isinstance(value, bool) for value in record['configs'].values())):
        raise ValueError('Invalid Traditional deployment recovery journal')
    backup = _path(engine, 'backups/deployment/' + record['backup'], True)
    retained = _path(engine, 'backups/deployment/' + record['backup'] + '/previous-bin', True)
    current = _path(engine, 'server/bin', True)
    previous = _path(engine, 'server/bin.previous', True)
    manifest = _path(engine, 'server/bin/deployment.json')
    committed = False
    if manifest.is_file():
        committed = build._json(manifest).get('transaction') == record['id']
    if not committed:
        if previous.exists() and record['had_current']:
            if not current.exists():
                os.replace(previous, current)
        for name, existed in record['configs'].items():
            target = _path(engine, 'server/' + name)
            if existed:
                source = _path(engine, 'backups/deployment/' + record['backup'] + '/' + name)
                shutil.copy2(source, target)
            else:
                target.unlink(missing_ok=True)
        if retained.exists():
            if previous.exists():
                raise ValueError('Interrupted Traditional deployment has conflicting prior binaries')
            os.replace(retained, previous)
    elif retained.exists():
        shutil.rmtree(retained)
    journal.unlink()


def deploy(engine, args):
    from engine import atomic_json
    if engine.server_running():
        raise ValueError('Stop the server before deploying binaries')
    if getattr(engine, 'traditional_recovery_error', None):
        raise ValueError('Traditional runtime recovery needs attention: ' + engine.traditional_recovery_error)
    build.recover(engine)
    recover(engine)
    staged = build.status(engine)
    if not staged['staged_valid']:
        raise ValueError(staged['staged_message'])
    sync_content(engine)
    info = _record(engine, 'server/bin.staged')
    qualify_database(engine, allow_pending=True)
    database_backup = engine.backup_database({})['file']
    transaction = secrets.token_hex(12)
    backup = _path(engine, 'backups/deployment/' + transaction, True)
    backup.mkdir(parents=True)
    configs = {}
    for name in ('eqemu_config.json', 'login.json'):
        path = _path(engine, 'server/' + name)
        configs[name] = path.exists()
        if path.exists():
            shutil.copy2(path, backup / name)
    current = _path(engine, 'server/bin', True)
    previous = _path(engine, 'server/bin.previous', True)
    journal = _path(engine, 'run/traditional-deploy.json')
    record = {'format': 1, 'id': transaction, 'backup': transaction,
              'had_current': current.exists(), 'had_previous': previous.exists(),
              'configs': configs, 'database_backup': database_backup}
    atomic_json(journal, record)
    try:
        write_config(engine)
        schema = qualify_database(engine, migrate=True, binary_root='server/bin.staged')
        engine.check_cancel()
        manifest_path = _path(engine, 'server/bin.staged/deployment.json')
        _path(engine, 'server/bin.staged/deployment.json.new')
        atomic_json(manifest_path,
                    {'format': 1, 'profile': 'traditional', 'transaction': transaction,
                     'database_version': schema['version'], 'deployed': time.time(),
                     'verification_sha256': info['verification_sha256'], 'database_backup': database_backup})
        if previous.exists():
            os.replace(previous, backup / 'previous-bin')
        if current.exists():
            os.replace(current, previous)
        try:
            os.replace(engine.work / 'server/bin.staged', current)
        except BaseException:
            if record['had_current'] and previous.exists():
                os.replace(previous, current)
            raise
        journal.unlink()
    except BaseException:
        # Before activation the current binaries are untouched; restore config.
        for name, existed in configs.items():
            if existed:
                shutil.copy2(backup / name, engine.work / 'server' / name)
            else:
                (engine.work / 'server' / name).unlink(missing_ok=True)
        if (backup / 'previous-bin').exists() and not previous.exists():
            os.replace(backup / 'previous-bin', previous)
        journal.unlink(missing_ok=True)
        raise
    if (backup / 'previous-bin').exists():
        try:
            shutil.rmtree(backup / 'previous-bin')
        except OSError as error:
            engine.log('Traditional deployment succeeded; an older binary backup was retained: ' + str(error))
    return {'message': 'Traditional binaries deployed; local login and PEQ schema qualified. Import maps and prepare your clean RoF2 client, then start the server.',
            'database_backup': database_backup, 'database_version': schema['version'], 'deployed': True}


def require_client_data(engine):
    state = status(engine)
    if not state['client_data_allowed']:
        raise ValueError(state['message'])
    qualify_database(engine)
    sync_content(engine)


def rollback(engine, args):
    if engine.server_running():
        raise ValueError('Stop the server before rollback')
    if not status(engine)['rollback_allowed']:
        raise ValueError('No qualified previous Traditional build is available')
    qualify_database(engine)
    current = _path(engine, 'server/bin', True)
    previous = _path(engine, 'server/bin.previous', True)
    temp = _path(engine, 'server/bin.swap', True)
    if temp.exists():
        raise ValueError('An interrupted binary rollback needs recovery')
    os.replace(current, temp)
    try:
        os.replace(previous, current)
        try:
            os.replace(temp, previous)
        except BaseException:
            os.replace(current, previous)
            raise
    except BaseException:
        os.replace(temp, current)
        raise
    write_config(engine)
    return {'message': 'Previous verified Traditional binaries restored. Database backups remain available separately.'}


def start(engine, args):
    from log_retention import rotate
    if engine.server_running():
        raise ValueError('Server processes are already running')
    state = status(engine)
    if not state['start_allowed']:
        raise ValueError(state['message'] if not engine.server_running() else 'Server processes are already running')
    qualify_database(engine)
    sync_content(engine)
    engine.backup_database({})
    write_config(engine)
    workers = int(engine.config['workers'])
    if not 1 <= workers <= 32:
        raise ValueError('Choose 1–32 zone workers')
    engine.mysql("INSERT INTO launcher (name,dynamics) VALUES ('traditional',%d) ON DUPLICATE KEY UPDATE dynamics=VALUES(dynamics);" % workers)
    runtime = engine.work / 'server'
    try:
        engine.run([runtime / 'bin/shared_memory'], cwd=runtime, timeout=600)
        engine.launch('loginserver')
        # The login TCP listener must exist before world can register locally.
        for _ in range(60):
            engine.check_cancel()
            if engine.processes['loginserver'].poll() is not None:
                raise ValueError('Traditional login server stopped; inspect loginserver.log')
            try:
                with socket.create_connection(('127.0.0.1', 5998), timeout=1):
                    break
            except OSError:
                time.sleep(1)
        else:
            raise ValueError('Traditional login server did not open its local world connection')
        engine.launch('world')
        for _ in range(600):
            engine.check_cancel()
            if engine.processes['world'].poll() is not None:
                raise ValueError('Traditional world stopped; inspect world.log')
            if engine.processes['loginserver'].poll() is not None:
                raise ValueError('Traditional login server stopped; inspect loginserver.log')
            try:
                with socket.create_connection(('127.0.0.1', 9000), timeout=1):
                    break
            except OSError:
                time.sleep(1)
        else:
            raise ValueError('Traditional world did not become ready within ten minutes')
        for name in ('ucs', 'queryserv'):
            engine.launch(name)
        for path in (runtime / 'logs').glob('zone-dynamic_*.log'):
            rotate(path)
        engine.launch('eqlaunch', 'traditional')
        stable_zones = None
        for _ in range(600):
            engine.check_cancel()
            failed = [name for name, process in engine.processes.items() if process.poll() is not None]
            if failed:
                raise ValueError('Traditional processes stopped during startup: ' + ', '.join(failed))
            zones = _zone_children(engine.processes['eqlaunch'].pid)
            ready_logs = 0
            for path in (runtime / 'logs').glob('zone-dynamic_*.log'):
                if re.fullmatch(r'zone-dynamic_\d+\.log', path.name) and not path.is_symlink():
                    with path.open('rb') as source:
                        source.seek(max(0, path.stat().st_size - 65536))
                        ready_logs += b'Entering sleep mode' in source.read()
            if ready_logs >= workers and len(zones) >= workers:
                if stable_zones == zones:
                    break
                stable_zones = zones
            else:
                stable_zones = None
            time.sleep(1)
        else:
            raise ValueError('Traditional zone workers did not reach sleep mode within ten minutes; inspect server zone logs')
        engine.config['rules_pending_restart'] = False
        engine.save()
        return {'message': 'Traditional server started with its dynamic zones ready. New local login accounts are created on first login.',
                'endpoint': engine.config['ip'] + ':' + str(engine.config['login_port'])}
    except BaseException:
        engine.stop({})
        raise


def _zone_children(launcher_pid, proc_root=None):
    """Observe live launcher children; a restarting parent alone is not ready."""
    from pathlib import Path
    result = []
    for entry in Path('/proc' if proc_root is None else proc_root).iterdir():
        if not entry.name.isdigit():
            continue
        try:
            process = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            # PRoot can expose the ELF loader as argv[0] in host /proc. The
            # zone binary or --argv0 zone remains in the full argument list.
            arguments = (entry / 'cmdline').read_bytes().decode().split('\0')
            if int(process[1]) == launcher_pid and process[0] != 'Z' and any(Path(arg).name == 'zone' for arg in arguments if arg):
                result.append(int(entry.name))
        except (OSError, ValueError, UnicodeError):
            continue
    return tuple(sorted(result))
