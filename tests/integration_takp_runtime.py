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
from integration_source_updates import (LEGACY_SERVER_COMMIT, archive_tree, immutable_archives,
                                        stamps, tree_hashes)

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
FIXTURE_USER = 'takpfixture'
FIXTURE_PASSWORD = 'takp-fixture-pass'


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


def qualify_legacy_source_transition(engine, args, report):
    """Same-workspace upgrade: actual released receipts, native cache and data."""
    baseline_path = args.output.parent / 'takp-legacy-baseline.json'
    baseline = json.loads(baseline_path.read_text())
    if baseline['result'] != 'passed' or baseline['source_commit'] != LEGACY_SERVER_COMMIT:
        raise RuntimeError('The legacy native bootstrap did not qualify its exact source')
    before_upgrade = engine.state()
    if not before_upgrade['binaries_ready'] or not before_upgrade['takp']['deployment']['start_allowed']:
        raise RuntimeError('App upgrade disabled the verified released TAKP server')
    deployed = tree_hashes(engine.work / 'server/bin')
    if deployed != baseline['deployed_hashes']:
        raise RuntimeError('App upgrade altered deployed TAKP binaries or receipts')
    source = engine.source_root()
    if stamps(source) != baseline['source_stamps']:
        raise RuntimeError('App upgrade changed the legacy source before update review')
    credentials = {key: engine.config[key] for key in
                   ('database', 'db_password', 'server_key', 'db_port', 'ip', 'login_port')}
    # The old-app child closed its app-owned MariaDB during shutdown. Boot the
    # same preserved database through the new runtime before issuing SQL.
    engine.ensure_db()
    player_state = engine.mysql('SELECT COUNT(*) FROM items; SELECT COUNT(*) FROM tblLoginServerAccounts;')
    with immutable_archives(engine, {LEGACY_SERVER_COMMIT: args.baseline_source,
                                     takp_build.REVISION: args.source}, takp_build.REPOSITORY):
        preview = engine.source_update_preview({})
        if (not preview['apply_allowed'] or preview['counts'] != {'added': 2, 'deleted': 0, 'changed': 2}
                or set(preview['files']['changed']) != {'zone/player_bot.cpp', 'tests/player-bots/run.py'}):
            raise RuntimeError('Native source review did not identify the exact Yaulp source delta: ' + str(preview))
        engine.source_update_apply({'token': preview['token']})
    after = stamps(source)
    affected = set().union(*map(set, preview['files'].values()))
    unchanged = set(baseline['source_stamps']) - affected
    if any(after[name] != baseline['source_stamps'][name] for name in unchanged):
        raise RuntimeError('Source update changed an unchanged file inode, size or mtime')
    if tree_hashes(engine.work / 'server/bin') != deployed:
        raise RuntimeError('Source update changed the currently deployed binaries')
    if credentials != {key: engine.config[key] for key in credentials} or player_state != engine.mysql(
            'SELECT COUNT(*) FROM items; SELECT COUNT(*) FROM tblLoginServerAccounts;'):
        raise RuntimeError('Source update changed existing database/account settings')
    if not engine.state()['takp']['deployment']['start_allowed']:
        raise RuntimeError('Source update disabled the still-qualified previous server')
    # This is a real launch using the old nine binaries through the NEW app.
    # The latest source has not been compiled yet; no staged build can mask the
    # start-disabled regression that the device reported.
    engine.start({})
    wait_for(engine, lambda output: 'ClientManager listening for RDP clients on port [6000]' in output,
             'legacy server started through the upgraded app')
    stopped = engine.stop({})
    if not stopped['clean_shutdown']:
        raise RuntimeError('Legacy server did not shut down cleanly through the upgraded app')
    stage = engine.work / 'server/bin.staged'
    shutil.copytree(engine.work / 'server/bin', stage)
    previous_stage = tree_hashes(stage)
    previous_run = engine.run
    failure_reached_ninja = False
    def fail_actual_ninja(command, *positional, **keywords):
        nonlocal failure_reached_ninja
        words = [str(word) for word in command]
        cmake = next((index for index, word in enumerate(words) if Path(word).name == 'cmake'), None)
        if cmake is not None and words[cmake + 1:cmake + 2] == ['--build']:
            failure_reached_ninja = True
            # A genuine nonzero Ninja child, after production cache selection
            # and CMake configuration, without changing the qualified source.
            words = words[:words.index('--target')] + ['--target', 'trasc_missing_qualification_target']
            return previous_run(words, *positional, **keywords)
        return previous_run(command, *positional, **keywords)
    engine.run = fail_actual_ninja
    try:
        try:
            engine.build_update({'jobs': args.jobs})
        except ValueError as error:
            if not failure_reached_ninja or 'Command failed' not in str(error):
                raise
        else:
            raise RuntimeError('Intentionally failing native build unexpectedly succeeded')
    finally:
        engine.run = previous_run
    if tree_hashes(stage) != previous_stage or tree_hashes(engine.work / 'server/bin') != deployed:
        raise RuntimeError('Failed production build altered prior staged/deployed binaries or receipts')
    if not engine.state()['takp']['deployment']['start_allowed']:
        raise RuntimeError('Failed production build disabled previous deployed server')
    build_dir = engine.work / baseline['build_directory']
    if stamps(build_dir, '.o') != baseline['object_stamps']:
        raise RuntimeError('Source review or deliberately refused build rewrote legacy compiler objects')
    transition = {'format': 1, 'from_commit': LEGACY_SERVER_COMMIT, 'to_commit': takp_build.REVISION,
                  'preview': preview, 'unchanged_source_files_preserved': len(unchanged),
                  'legacy_build_directory': baseline['build_directory'],
                  'legacy_native_object_count': len(baseline['object_stamps']),
                  'legacy_deployed_start_after_upgrade_and_source_update': True,
                  'actual_failed_ninja_preserved_staged_and_deployed_receipts': True,
                  'database_credentials_and_account_counts_preserved': True}
    report['source_update_transition'] = transition
    report['checks']['verified_released_legacy_server_remains_startable_after_app_upgrade'] = True
    report['checks']['actual_legacy_to_latest_source_delta_preserves_all_unchanged_inodes_and_mtimes'] = True
    report['checks']['failed_incremental_native_build_preserves_previous_stage_deployment_and_readiness'] = True
    return build_dir, baseline['object_stamps']


def qualify_incremental_objects(engine, args, report, build_dir, before):
    if takp_build.build_directory(engine) != build_dir:
        raise RuntimeError('Production update replaced the legacy cache instead of adopting it')
    after = stamps(build_dir, '.o')
    if set(before) != set(after):
        raise RuntimeError('A single-translation-unit update unexpectedly changed the native object inventory')
    changed = sorted(name for name in before if before[name] != after[name])
    expected = ['zone/CMakeFiles/zone.dir/player_bot.cpp.o']
    if changed != expected:
        raise RuntimeError('Yaulp incremental build compiled unrelated objects: ' + str(changed))
    transition = report['source_update_transition']
    transition['native_changed_objects'] = changed
    transition['native_unchanged_objects_preserved'] = len(after) - len(changed)
    before_noop = tree_hashes(engine.work / 'server/bin.staged')
    operation = engine.work / 'logs/operation.log'
    log_offset = operation.stat().st_size
    engine.build_update({'jobs': args.jobs})
    with operation.open('rb') as stream:
        stream.seek(log_offset)
        no_op_output = stream.read().decode(errors='replace')
    if 'ninja: no work to do.' not in no_op_output:
        raise RuntimeError('No-op production rebuild did not report an empty Ninja work graph')
    if stamps(build_dir, '.o') != after:
        raise RuntimeError('A no-op production rebuild unexpectedly recompiled C++ objects')
    # Receipt timestamps may advance, but a no-op compile may not change a
    # single server binary. All nine outputs are compared by SHA-256.
    after_noop = tree_hashes(engine.work / 'server/bin.staged')
    if any(before_noop[name] != after_noop[name] for name in takp_build.BINARIES):
        raise RuntimeError('No-op production build changed native binary bytes')
    transition['native_no_op_all_objects_and_nine_binary_hashes_preserved'] = True
    transition['native_no_op_ninja_output'] = 'ninja: no work to do.'
    transition['result'] = 'passed'
    report['checks']['real_cmake_ninja_reuses_legacy_cache_and_compiles_only_player_bot'] = True
    report['checks']['second_production_build_is_a_no_op_for_all_native_objects_and_binaries'] = True
    atomic_json(args.output.parent / 'takp-source-update-native.json', transition)


def qualify(args):
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('TAKP runtime qualification requires native ARM64')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    if bool(args.baseline_app) != bool(args.baseline_source):
        raise ValueError('Supply both released baseline app and native source fixtures')
    subprocess.run([sys.executable, str(Path(__file__).with_name('integration_source_updates.py')),
                    '--work', str(args.work.parent / 'source-update-cmake-fixtures'),
                    '--output', str(args.output.parent / 'all-profile-source-update-cmake.json')], check=True)
    if args.baseline_app:
        subprocess.run([sys.executable, str(Path(__file__).with_name('integration_source_updates.py')),
                        '--bootstrap-legacy', '--work', str(args.work), '--baseline-app', str(args.baseline_app),
                        '--baseline-source', str(args.baseline_source), '--quests', str(args.quests),
                        '--maps', str(args.maps), '--output', str(args.output.parent / 'takp-legacy-baseline.json'),
                        '--jobs', str(args.jobs)], check=True)
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
        incremental = None
        if args.baseline_app:
            content_paths = {'quests': engine.work / 'server/quests',
                             'maps': engine.work / 'maps', 'assets': engine.work / 'server/assets'}
            retained_content = {kind: tree_hashes(path) for kind, path in content_paths.items()}
            incremental = qualify_legacy_source_transition(engine, args, report)
            imported = {'source': json.loads((engine.source_root() / 'trasc-source.json').read_text())}
        else:
            name = archive_tree(args.source, engine.work / 'incoming/server.zip')
            imported = engine.import_source({'file': name})
        if imported['source']['takp']['tree_sha256'] != takp_build.SOURCE_TREE_SHA256:
            raise RuntimeError('Production source importer did not qualify the pinned tree')
        report['checks']['complete_pinned_source_and_vendored_dependencies'] = True
        if incremental:
            # The released app already installed the same pinned content.
            # A source-only update must keep it, not request replacement.
            content = engine.state()['takp']
            if not all(content['components'][kind]['imported'] for kind in content_paths):
                raise RuntimeError('App/source upgrade invalidated retained TAKP content')
            for zone_name in ('qeynos', 'paineel'):
                if not (engine.work / 'maps' / (zone_name + '.map')).is_file():
                    raise RuntimeError('Retained map fixture lacks ' + zone_name)
        else:
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
        if incremental:
            if any(tree_hashes(path) != retained_content[kind] for kind, path in content_paths.items()):
                raise RuntimeError('Source update replaced installed TAKP quests, maps or opcode assets')
            report['checks']['existing_quests_maps_and_assets_preserved_without_reimport'] = True
            report['source_update_transition']['existing_content_preserved'] = True
        report['checks']['takp_quests_flat_maps_and_opcodes'] = True
        # Qualify the imported pinned bot policy, including the seed-backed
        # Yaulp scheduling regression, on this native host before the full build.
        bot_tests = engine.source_root() / 'tests/player-bots/run.py'
        if not bot_tests.is_file():
            raise RuntimeError('Pinned TAKP source lacks the standalone bot qualification runner')
        subprocess.run([sys.executable, str(bot_tests)], cwd=engine.source_root(), check=True)
        report['checks']['native_standalone_bot_policy_and_yaulp_regressions'] = True
        engine.build_update({'jobs': args.jobs}) if incremental else engine.build({'jobs': args.jobs})
        if incremental:
            qualify_incremental_objects(engine, args, report, *incremental)
        report['checks']['native_production_build_and_nine_elf_dependency_checks'] = True
        report['spawn_wire'] = qualify_spawn_wire(
            takp_build.build_directory(engine),
            engine.source_root(), args.output.parent / 'spawn-wire')
        report['checks']['native_mac_spawn_encryption_opcode_and_literal_224_byte_client_layout'] = True
        if incremental:
            active_database = engine.config['database']
            takp_runtime.verify_database(engine)
        else:
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
        if not incremental:
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
    parser.add_argument('--baseline-app', type=Path)
    parser.add_argument('--baseline-source', type=Path)
    qualify(parser.parse_args())
