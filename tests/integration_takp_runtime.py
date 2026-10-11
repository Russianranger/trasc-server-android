"""Native Bookworm ARM64: production TAKP import/build/DB/deploy/start/export.

Uses public pinned source/content fixtures and an offline container. No client
game binaries are required; physical Wine login and gameplay remain acceptance
testing. This test starts and stops its own isolated MariaDB/server processes.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, '/opt/trasc')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine, atomic_json
import takp_build
import takp_runtime
from takp_spawn_wire import qualify_spawn_wire

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
FIXTURE_USER = 'takpfixture'
FIXTURE_PASSWORD = 'takp-fixture-pass'


def archive_tree(source, target, selected=None):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        files = sorted(Path(source).rglob('*')) if selected is None else selected
        for path in files:
            relative = path.relative_to(source)
            if path.is_file() and not path.is_symlink() and '.git' not in relative.parts:
                archive.write(path, Path('fixture') / relative)
    return target.name


def logs(engine):
    paths = list((engine.work / 'logs').glob('*.log'))
    paths += list((engine.work / 'server/logs').rglob('*.log'))
    return '\n'.join(ANSI.sub('', path.read_text(errors='replace')) for path in paths if path.is_file())


def npc_spawn_ids(log_root, zone):
    """Creation events after AddNPC, rather than spawnentry database row counts."""
    found = set()
    # General Spawns is enabled for file logging, without changing console
    # verbosity. File log lines have no zone suffix; their filename scopes them.
    for path in Path(log_root).rglob(zone + '_port_*.log'):
        for line in ANSI.sub('', path.read_text(errors='replace')).splitlines():
            match = re.search(r'Spawn2 \[(\d+)[^]]*\].*\bspawned \[', line)
            if match:
                found.add(int(match[1]))
    return found


def wait_for(engine, predicate, description, seconds=120):
    deadline = time.monotonic() + seconds
    output = ''
    while time.monotonic() < deadline:
        failed = [name for name, process in engine.processes.items() if process.poll() is not None]
        if failed:
            raise RuntimeError('TAKP processes exited: ' + ', '.join(failed))
        output = logs(engine)
        if predicate(output):
            return output
        time.sleep(.5)
    raise RuntimeError('Timed out waiting for ' + description + '\n' + output[-8000:])


def qualify(args):
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('TAKP runtime qualification requires native ARM64')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    engine = Engine(args.work, 'takp')
    custom = Engine(args.work.parent / 'custom-preserved', 'custom')
    sentinel = custom.work / 'server/keep.txt'
    sentinel.write_bytes(b'Custom server and account state must remain unchanged\n')
    custom_settings = custom.config_path.read_bytes()
    report = {'format': 1, 'profile': 'takp', 'architecture': 'arm64',
              'source_commit': takp_build.REVISION, 'recipe': takp_build.RECIPE,
              'seed_sha256': takp_build.SEED_SHA256, 'checks': {}, 'result': 'running'}
    zone = None
    zone_log = None
    try:
        name = archive_tree(args.source, engine.work / 'incoming/server.zip')
        imported = engine.import_source({'file': name})
        if imported['source']['takp']['tree_sha256'] != takp_build.SOURCE_TREE_SHA256:
            raise RuntimeError('Production source importer did not qualify the pinned tree')
        report['checks']['complete_pinned_source_and_vendored_dependencies'] = True
        name = archive_tree(args.quests, engine.work / 'incoming/quests.zip')
        engine.dispatch('import_content', {'kind': 'quests', 'file': name})
        maps = [path for path in args.maps.iterdir() if path.name.startswith(('qeynos.', 'paineel.'))
                or path.name.startswith(('README', 'LICENSE'))]
        for zone_name in ('qeynos', 'paineel'):
            if not any(path.name == zone_name + '.map' for path in maps):
                raise RuntimeError('Pinned map fixture lacks ' + zone_name)
        name = archive_tree(args.maps, engine.work / 'incoming/maps.zip', maps)
        engine.import_maps({'file': name})
        engine.sync_content({})
        report['checks']['takp_quests_flat_maps_and_opcodes'] = True
        # Qualify the imported pinned bot policy, including the seed-backed
        # Yaulp scheduling regression, on this native host before the full build.
        bot_tests = engine.source_root() / 'tests/player-bots/run.py'
        if not bot_tests.is_file():
            raise RuntimeError('Pinned TAKP source lacks the standalone bot qualification runner')
        subprocess.run([sys.executable, str(bot_tests)], cwd=engine.source_root(), check=True)
        report['checks']['native_standalone_bot_policy_and_yaulp_regressions'] = True
        engine.build({'jobs': args.jobs})
        report['checks']['native_production_build_and_nine_elf_dependency_checks'] = True
        report['spawn_wire'] = qualify_spawn_wire(
            engine.work / ('builds/takp-' + takp_build.REVISION[:12]),
            engine.source_root(), args.output.parent / 'spawn-wire')
        report['checks']['native_mac_spawn_encryption_opcode_and_literal_224_byte_client_layout'] = True
        database = engine.dispatch('takp_initialize_database', {})
        active_database = database['database']
        report['database'] = active_database
        expected_versions = {str(number) for number in range(1, 12)}
        versions = {row[0] for row in takp_runtime._rows(engine, 'SELECT version FROM takp_bot_schema;')}
        if versions != expected_versions:
            raise RuntimeError('The fresh database lacks one of the eleven bot migrations')
        report['checks']['complete_four_part_seed_and_all_eleven_bot_migrations'] = True
        before = engine.mysql('SELECT COUNT(*) FROM items;')
        try:
            engine.dispatch('takp_initialize_database', {})
        except ValueError as error:
            if 'never replaces' not in str(error):
                raise
        else:
            raise RuntimeError('Repeated database initialization overwrote player storage')
        if engine.config['database'] != active_database or before != engine.mysql('SELECT COUNT(*) FROM items;'):
            raise RuntimeError('Refused database initialization still changed the database')
        report['checks']['existing_database_refused_without_replacement'] = True
        engine.dispatch('takp_create_account', {'username': FIXTURE_USER, 'password': FIXTURE_PASSWORD})
        account = takp_runtime._rows(engine, "SELECT AccountPassword,ForumName FROM tblLoginServerAccounts WHERE AccountName='" + FIXTURE_USER + "';")
        expected = hashlib.sha1((FIXTURE_PASSWORD + engine.config['server_key']).encode()).hexdigest()
        if account != [[expected, FIXTURE_USER]]:
            raise RuntimeError('Local TAKP account did not use the login server salt/schema')
        report['checks']['local_account_creation_with_salted_password'] = True
        engine.config['workers'] = 1
        engine.save()
        engine.deploy({})
        engine.start({})
        wait_for(engine, lambda output: 'ClientManager listening for RDP clients on port [6000]' in output,
                 'legacy UDP login listener')
        wait_for(engine, lambda output: 'New Zone Server connection' in output or 'dynamic_01' in output,
                 'launcher dynamic zone connection')
        registered = takp_runtime._rows(engine, "SELECT ServerLongName FROM tblWorldServerRegistration WHERE ServerShortName='TAKP';")
        if registered != [['TAKP World on Android']]:
            raise RuntimeError('The TAKP world did not register with the local login server')
        report['checks']['local_login_world_and_dynamic_zone_startup'] = True
        # Boot a real content zone in addition to the launcher's sleeping worker.
        zone_log = open(engine.work / 'logs/qeynos-probe.log', 'wb')
        zone = subprocess.Popen([str(engine.work / 'server/bin/zone'), 'qeynos:7117'],
                                cwd=engine.work / 'server', stdin=subprocess.DEVNULL,
                                stdout=zone_log, stderr=zone_log, start_new_session=True)
        output = wait_for(engine, lambda output: 'Zone booted successfully zone_id [1]' in output,
                          'Qeynos zone boot with its flat map and Lua quest modules')
        if zone.poll() is not None:
            raise RuntimeError('Qeynos stopped after boot')
        if re.search(r'(?:Error\s+(?:10\d\d|11\d\d)|Error (?:10\d\d|11\d\d):|Unknown column|Table .*doesn.t exist)', output):
            raise RuntimeError('TAKP startup encountered a database schema error')
        report['checks']['qeynos_zone_map_lua_boot_and_no_sql_schema_errors'] = True
        zone.terminate()
        zone.wait(timeout=30)
        zone = None
        zone_log.close()
        zone_log = None
        # Qualify the reported starting zone using actual NPC creation events.
        # This does not establish client visibility or count entities later.
        expected_spawns = {int(row[0]) for row in takp_runtime._rows(engine,
            "SELECT id FROM spawn2 WHERE zone='paineel' AND enabled=1;")}
        if len(expected_spawns) != 156:
            raise RuntimeError('Pinned Paineel fixture does not contain 156 enabled spawn points')
        zone_log = open(engine.work / 'logs/paineel-probe.log', 'wb')
        zone = subprocess.Popen([str(engine.work / 'server/bin/zone'), 'paineel:7118'],
                                cwd=engine.work / 'server', stdin=subprocess.DEVNULL,
                                stdout=zone_log, stderr=zone_log, start_new_session=True)
        output = wait_for(engine, lambda output: 'Zone booted successfully zone_id [75]' in output
                         and expected_spawns <= npc_spawn_ids(engine.work / 'server/logs', 'paineel'),
                         'Paineel boot with pinned content and creation of all 156 seeded NPCs')
        if zone.poll() is not None:
            raise RuntimeError('Paineel stopped after NPC creation')
        if re.search(r'(?:Unknown column|Table .*doesn.t exist|yeilded an invalid NPC type|'
                     r'Unable to locate spawn group|not spawning|SIGSEGV|print_trace|Fatal error)', output):
            raise RuntimeError('Paineel encountered a schema, NPC creation or crash error')
        report['checks']['paineel_zone_boot_with_pinned_content_and_all_156_seeded_npc_creation_events'] = True
        report['paineel_seeded_npc_creation_count'] = len(expected_spawns)
        exported = engine.export_client({})
        with zipfile.ZipFile(engine.work / exported['file']) as archive:
            if set(archive.namelist()) != set(takp_runtime.CLIENT_FILES) | {'client-data-export.json'}:
                raise RuntimeError('TAKP exporter used files from the RoF2 profile')
            if any(not archive.read(name) for name in takp_runtime.CLIENT_FILES):
                raise RuntimeError('TAKP exporter produced an empty client file')
        if exported['filter_applied'] or exported['files'] != list(takp_runtime.CLIENT_FILES):
            raise RuntimeError('TAKP export applied the RoF2 spell filter')
        report['checks']['actual_two_file_unfiltered_takp_export'] = True
        zone.terminate()
        zone.wait(timeout=30)
        zone = None
        stopped = engine.stop({})
        if not stopped['clean_shutdown']:
            raise RuntimeError('TAKP did not stop cleanly: ' + str(stopped['shutdown_errors']))
        report['checks']['native_zone_and_launcher_clean_shutdown'] = True
        if custom.config_path.read_bytes() != custom_settings or sentinel.read_bytes() != b'Custom server and account state must remain unchanged\n':
            raise RuntimeError('TAKP altered the Custom workspace')
        report['checks']['custom_workspace_and_credentials_preserved'] = True
        report['result'] = 'passed'
        atomic_json(args.output, report)
        print(json.dumps(report, indent=2), flush=True)
    finally:
        if zone and zone.poll() is None:
            zone.terminate()
            try:
                zone.wait(timeout=30)
            except subprocess.TimeoutExpired:
                zone.kill()
                zone.wait()
        if zone_log:
            zone_log.close()
        engine.shutdown()
        with contextlib.suppress(OSError):
            shutil.copytree(engine.work / 'logs', args.output.parent / 'logs', dirs_exist_ok=True)
            shutil.copytree(engine.work / 'server/logs', args.output.parent / 'server-logs', dirs_exist_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--quests', type=Path, required=True)
    parser.add_argument('--maps', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    qualify(parser.parse_args())
