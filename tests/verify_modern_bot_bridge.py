"""Qualify the real modern bot creation utility on native ARM64 and MariaDB.

This uses the production source adapters, actual world migrations, shared item
and spell data, normal server bot creation, and a local Lua player quest. It
does not substitute launcher SQL for the native bot creation path. Gameplay
spawning and party invitations still require client/device acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
sys.path.insert(0, '/opt/trasc')
from engine import Engine, atomic_json
import bots
import modern_bot_bridge as bridge
import server_ferry
import traditional_build

PEQ_SHA256 = 'ac8649f23d2c3aea2cade138dfe10d46d1b21ad1a80d08ca95f5434fab7f218d'
OWNER_ID = 890001
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(engine, query):
    return [line.split('\t') for line in engine.mysql(query, timeout=120).splitlines()[1:]]


def scalar(engine, query):
    result = rows(engine, query)
    require(len(result) == 1 and len(result[0]) == 1, 'Expected one database scalar')
    return result[0][0]


def command(arguments, cwd, log, seconds=3600, environment=None):
    with log.open('wb') as output:
        completed = subprocess.run([str(value) for value in arguments], cwd=cwd,
                                   stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.STDOUT, timeout=seconds, env=environment)
    require(completed.returncode == 0, 'Native command failed; see ' + log.name)


def build(args, evidence):
    source = args.work / 'native-source'
    require(not source.exists(), 'Use a fresh qualification workspace')
    # The mounted checkout stays pristine. CI fetches websocketpp before
    # entering the network-disabled runtime; both builds are then offline.
    shutil.copytree(args.source, source, symlinks=True,
                    ignore=shutil.ignore_patterns('.git', 'bin', 'build', 'builds'))
    for name, expected in bridge.GUARDS[args.profile].items():
        require(sha(source / name) == expected, 'Unqualified source: ' + name)
    if args.profile == 'traditional':
        for name, expected in traditional_build.SOURCE_HASHES.items():
            require(sha(source / name) == expected, 'Traditional source changed: ' + name)
        traditional_build._apply_patches(source)
        require((source / 'submodules/websocketpp/websocketpp/config/asio_no_tls.hpp').is_file(),
                'Fetch the pinned websocketpp submodule before qualification')
        flags = [
            '-DCMAKE_CXX_COMPILER=/usr/bin/g++', '-DCMAKE_C_COMPILER=/usr/bin/gcc',
            '-DCMAKE_TOOLCHAIN_FILE=', '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG -fno-strict-aliasing',
            '-DEQEMU_USE_SYSTEM_DEPENDENCIES=ON',
            '-DTRASC_WEBSOCKETPP_INCLUDE_DIR=' + str(source / 'submodules/websocketpp'),
            '-DLUAJIT_INCLUDE_DIR=/usr/include/luajit-2.1',
            '-DLUAJIT_LIBRARY=/usr/lib/aarch64-linux-gnu/libluajit-5.1.so',
        ]
    else:
        server_ferry.prepare(source)
        bridge.prepare(source, 'custom')
        flags = ['-DEQEMU_PREFER_LUA=ON', '-DLUA_INCLUDE_DIR=/usr/include/lua5.1',
                 '-DLUA_LIBRARY=/usr/lib/aarch64-linux-gnu/liblua5.1.so']
    objects = args.work / 'native-build'
    command(['cmake', '-S', source, '-B', objects, '-G', 'Ninja',
             '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
             '-DEQEMU_BUILD_PCH=ON', '-DEQEMU_BUILD_SERVER=ON',
             '-DEQEMU_BUILD_LOGIN=OFF', '-DEQEMU_BUILD_CLIENT_FILES=OFF',
             '-DEQEMU_BUILD_PERL=ON', '-DEQEMU_BUILD_LUA=ON',
             '-DEQEMU_BUILD_TESTS=OFF', '-DEQEMU_ADD_PROFILER=OFF', *flags],
            args.work, evidence / 'configure.log', 600)
    command(['cmake', '--build', objects, '--parallel', args.jobs,
             '--target', 'zone', 'shared_memory', 'world'], args.work,
            evidence / 'native-build.log', 2 * 3600)
    binaries = {}
    for name in ('zone', 'shared_memory', 'world'):
        matches = [path for path in objects.rglob(name)
                   if path.is_file() and 'CMakeFiles' not in path.parts]
        require(len(matches) == 1, 'Cannot find exactly one compiled ' + name)
        header = matches[0].read_bytes()[:20]
        require(header[:4] == b'\x7fELF' and header[4] == 2
                and int.from_bytes(header[18:20], 'little') == 183,
                name + ' must be a native ARM64 ELF executable')
        binaries[name] = matches[0]
    return source, binaries


def rule(engine, name, value, ruleset):
    engine.mysql('INSERT INTO rule_values(ruleset_id,rule_name,rule_value) VALUES('
                 + str(ruleset) + ',' + bots.literal(name) + ',' + bots.literal(value)
                 + ') ON DUPLICATE KEY UPDATE rule_value=VALUES(rule_value);')


def seed(engine, source, evidence):
    engine.run(['mariadb', '--defaults-extra-file=' + str(engine.mysql_options),
                engine.config['database']], input_file=source / 'utils/sql/bot_tables_bootstrap.sql',
               private=True, timeout=240)
    default = int(scalar(engine, "SELECT ruleset_id FROM rule_sets WHERE name='default';"))
    engine.mysql("UPDATE variables SET value='default' WHERE LOWER(varname)='ruleset';")
    for name, value in [('Bots:Enabled', 'true'), ('Bots:CreationLimit', '100'),
                        ('Bots:BotCharacterLevel', '0'), ('Bots:AllowCamelCaseNames', 'false')]:
        rule(engine, name, value, default)
    engine.write_config()
    # Apply the checked-out server's own migration code, rather than copying
    # table layouts or downloading today's bootstrap SQL from another branch.
    migration_log = evidence / 'native-migrations.log'
    migration_environment = dict(os.environ, FORCE_INTERACTIVE='1')
    command([engine.work / 'server/bin/world', 'database:updates', '--skip-backup'],
            engine.work / 'server', migration_log, 1800, migration_environment)
    text = ANSI.sub('', migration_log.read_text(errors='replace'))
    require('Required database update failed' not in text, 'Native bot migrations failed')
    version_text = (source / 'common/version.h').read_text()
    version = int(re.search(r'#define CURRENT_BINARY_BOTS_DATABASE_VERSION\s+(\d+)', version_text)[1])
    require(int(scalar(engine, 'SELECT bots_version FROM db_version;')) == version,
            'Native bot migrations did not reach their compiled version')
    require(rows(engine, "SHOW TABLES LIKE 'bot_starting_items';")
            and rows(engine, "SHOW TABLES LIKE 'bot_settings';"), 'Native bot state tables are missing')
    # Fixture-only transactional engines. Production refuses incompatible
    # engines and never performs this conversion for a user's database.
    for table in ('character_data', 'data_buckets'):
        engine.mysql('ALTER TABLE ' + bots.ident(table) + ' ENGINE=InnoDB;')
    zone_id = int(scalar(engine, "SELECT zoneidnumber FROM zone WHERE short_name='qeynos' LIMIT 1;"))
    engine.mysql('UPDATE zone SET ruleset=' + str(default) + ' WHERE zoneidnumber=' + str(zone_id) + ';'
                 'INSERT INTO account(id,name,status) VALUES(' + str(OWNER_ID) + ", 'trascbridgefixture',0);"
                 'INSERT INTO character_data(id,account_id,name,level,`class`,race,gender,zone_id,cur_hp,mana) VALUES('
                 + ','.join(map(str, (OWNER_ID, OWNER_ID))) + ",'Trascbridge',35,1,1,0," + str(zone_id) + ',100,100);')
    item_id = int(scalar(engine, 'SELECT id FROM items WHERE itemclass=0 AND (classes&1)<>0 '
                        'AND (races&1)<>0 AND (slots&4)<>0 ORDER BY id LIMIT 1;'))
    engine.mysql('DELETE FROM bot_starting_items; INSERT INTO bot_starting_items'
                 '(races,classes,item_id,item_charges,slot_id,min_expansion,max_expansion) VALUES'
                 '(1,1,' + str(item_id) + ',1,2,-1,-1);')
    # A normal character load repairs zero inventory GUIDs. Offline creation
    # must load these actual items without rewriting the player's records.
    engine.mysql('INSERT INTO inventory(character_id,slot_id,item_id,charges,guid) VALUES('
                 + str(OWNER_ID) + ',2,' + str(item_id) + ',1,0);'
                 'INSERT INTO sharedbank(account_id,slot_id,item_id,charges,guid) VALUES('
                 + str(OWNER_ID) + ',2500,' + str(item_id) + ',1,0);')
    bots.ensure_receipts(engine)
    bots._instance(engine)
    config = json.loads((engine.work / 'server/eqemu_config.json').read_text())['server']
    directories = config['directories']
    for key in ('plugins', 'lua_modules', 'quests', 'shared_memory', 'logs'):
        location = Path(directories[key])
        if not location.is_absolute():
            location = engine.work / 'server' / location
        location.mkdir(parents=True, exist_ok=True)
        if key == 'plugins':
            (location / 'trasc_ci.pl').write_text('sub CheckHandin { return 0; }\n1;\n')
        elif key == 'lua_modules':
            (location / 'trasc_ci.lua').write_text('return { CheckHandin = function() return false end }\n')
    hook = engine.work / 'server/quests/qeynos/player.lua'
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text('function event_bot_create(e)\n'
                    '  if (e.self:CharacterID() == ' + str(OWNER_ID)
                    + ' and e.self:GetItemIDAt(2) ~= ' + str(item_id)
                    + ') or e.self:GetItemIDAt(2500) ~= ' + str(item_id) + ' then\n'
                    '    error("offline owner inventory was not loaded")\n'
                    '  end\n'
                    '  e.self:SetBucket("trasc_native_" .. e.bot_name, tostring(e.bot_id))\n'
                    'end\n')
    command([engine.work / 'server/bin/shared_memory'], engine.work / 'server',
            evidence / 'shared-memory.log', 600)
    return default, zone_id, item_id, hook, version


def snapshot(engine):
    tables = [row[0] for row in rows(engine, "SHOW TABLES LIKE 'bot\\_%';")]
    tables += ['data_buckets', 'trasc_bot_creation_receipts', 'character_data', 'command_settings',
               'logsys_categories', 'inventory', 'sharedbank', 'character_evolving_items']
    result = {}
    for table in sorted(tables):
        query = 'SELECT * FROM ' + bots.ident(table)
        if table == 'character_data':
            query += ' WHERE id IN (' + str(OWNER_ID) + ',' + str(OWNER_ID + 1) + ')'
        # Sorting complete CLI rows makes this independent of physical order.
        data = '\n'.join(sorted(engine.mysql(query + ';', timeout=120).splitlines()[1:])).encode()
        result[table] = hashlib.sha256(data).hexdigest()
    return result


def request(engine, drafts, owner_id=OWNER_ID):
    ctx = bots.context(engine)
    return dict(format=1, profile=engine.profile, database=engine.config['database'],
                database_instance=ctx['instance'], request_id=secrets.token_hex(16),
                draft_hash=bridge.fingerprint(drafts), identity_hash=ctx['identity'],
                owner=bots.owner(ctx, owner_id), bots=drafts, bots_hash=bridge.fingerprint(drafts))


def native(engine, payload, evidence, label, succeed=True):
    incoming = engine.work / 'run/native-test-request.json'
    output = evidence / ('create-' + label + '.log')
    incoming.write_text(json.dumps(payload, sort_keys=True, separators=(',', ':')))
    incoming.chmod(0o600)
    with incoming.open('rb') as source, output.open('wb') as target:
        completed = subprocess.run([str(engine.work / 'server/bin/zone'), '--trasc-bot-create'],
                                   cwd=engine.work / 'server', stdin=source, stdout=target,
                                   stderr=subprocess.STDOUT, timeout=180)
    incoming.unlink(missing_ok=True)
    response = bridge._json_output(output)
    require(response.get('ok') is succeed, label + ': unexpected native result')
    require((completed.returncode == 0) is succeed, label + ': unexpected native exit status')
    if succeed:
        require(response.get('native_load_verified') is True,
                label + ': actual server Bot::LoadBot verification is missing')
    else:
        require(isinstance(response.get('error'), str) and response['error'], label + ': missing rejection reason')
    return response


def rejected(engine, payload, evidence, label, checks):
    before = snapshot(engine)
    response = native(engine, payload, evidence, label, False)
    require(snapshot(engine) == before, label + ': failed native batch changed saved rows')
    checks[label] = {'rows_unchanged': True, 'error': response['error']}


def draft(name, cls=1, race=1, gender=0):
    return {'name': name, 'class': cls, 'race': race, 'gender': gender}


def qualify(args):
    require(platform.machine() in ('aarch64', 'arm64'), 'Native modern bot qualification requires ARM64')
    require(sha(args.database_zip) == PEQ_SHA256, 'Immutable PEQ fixture hash mismatch')
    require(not (args.work / 'settings.json').exists(), 'Use a fresh qualification workspace')
    args.work.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    evidence = args.output.parent
    report = {'format': 1, 'profile': args.profile, 'architecture': platform.machine(),
              'source_revision': bridge.REVISIONS[args.profile], 'peq_sha256': PEQ_SHA256,
              'result': 'running', 'checks': {}}
    engine = None
    started = time.monotonic()
    try:
        source, binaries = build(args, evidence)
        report['checks']['native_compilation'] = {name: sha(path) for name, path in binaries.items()}
        # PEQ's five-part validated bundle is imported using its production
        # Traditional importer. The isolated fixture then adopts the matrix
        # profile; it never touches an existing Custom or Traditional world.
        engine = Engine(args.work / 'fixture', 'traditional')
        shutil.copy2(args.database_zip, engine.work / 'incoming/peq.zip')
        bundles = [value for value in engine.database_candidates() if value['kind'] == 'peq_bundle']
        require(len(bundles) == 1 and len(bundles[0]['selections']) == 5, 'PEQ bundle order is not qualified')
        engine.dispatch('import_database', {'selection': bundles[0]['id']})
        counts = {table: int(scalar(engine, 'SELECT COUNT(*) FROM ' + table + ';'))
                  for table in ('items', 'spells_new')}
        require(all(count > 10000 for count in counts.values()), 'Full PEQ content was not imported')
        report['checks']['full_peq_seed'] = counts
        engine.profile = args.profile
        engine.config['profile'] = args.profile
        engine.save()
        target = engine.work / 'server/bin'
        target.mkdir(exist_ok=True)
        for name, binary in binaries.items():
            shutil.copy2(binary, target / name)
            (target / name).chmod(0o755)
        atomic_json(target / 'build-info.json', {
            'profile': args.profile, 'bot_creation_bridge': bridge.metadata(args.profile),
            'zone_sha256': sha(target / 'zone')})
        for destination in (engine.work / 'server', engine.work / 'server/assets/patches',
                            engine.work / 'server/assets/opcodes'):
            destination.mkdir(parents=True, exist_ok=True)
            for directory in ('utils/patches', 'loginserver/login_util'):
                for asset in (source / directory).glob('*.conf'):
                    shutil.copy2(asset, destination / asset.name)
        default, zone_id, item_id, hook, version = seed(engine, source, evidence)
        report['checks']['native_migrations'] = {'bots_version': version, 'fixture_transactional_engines': ['character_data', 'data_buckets']}
        # Ordinary startup reconciles these tables, including deleting unknown
        # commands and inserting missing ones. An offline request must leave
        # them untouched even when rejection happens before any bot is saved.
        engine.mysql("INSERT INTO command_settings(`command`,access,aliases) VALUES('trasc_orphan_ci',0,'');"
                     "DELETE FROM command_settings WHERE `command`='summon';"
                     "INSERT INTO bot_command_settings(bot_command,access,aliases) VALUES('trasc_orphan_ci',0,'');"
                     "DELETE FROM bot_command_settings WHERE bot_command='botcreate';"
                     "DELETE FROM logsys_categories WHERE log_category_id=1;")
        rejected(engine, request(engine, [draft('Trascearly', gender=2)]), evidence,
                 'early-rejection-preserves-command-settings', report['checks'])
        hotfix_rows = rows(engine, "SELECT value FROM variables WHERE varname='hotfix_name' LIMIT 1;")
        hotfix = hotfix_rows[0][0] if hotfix_rows else ''
        require(re.fullmatch('[A-Za-z0-9_-]*', hotfix), 'Unexpected fixture hotfix filename')
        shared_items = engine.work / 'server/shared' / (hotfix + 'items')
        require(shared_items.is_file(), 'Real shared item memory was not generated')
        held_items = shared_items.with_name(shared_items.name + '.fixture-held')
        shared_items.rename(held_items)
        try:
            rejected(engine, request(engine, [draft('Trascnoitems')]), evidence,
                     'missing-shared-items-rejected-without-writes', report['checks'])
        finally:
            held_items.rename(shared_items)
        ctx = bots.context(engine)
        capability = bridge.capabilities(engine, ctx)
        require(capability.get('offline_create') is True, 'Compiled capability failed: ' + capability.get('reason', ''))
        report['checks']['capability_and_deployment_identity'] = capability

        drafts = [draft('Trascguard'), draft('Traschealer', 2, gender=1)]
        owner_before = engine.mysql('SELECT * FROM character_data WHERE id=' + str(OWNER_ID) + ';')
        inventory_before = {table: engine.mysql('SELECT * FROM ' + bots.ident(table) + ';')
                            for table in ('inventory', 'sharedbank', 'character_evolving_items')}
        token = secrets.token_hex(16)
        preview = bots.preview(engine, {'identity': ctx['identity'], 'owner_id': OWNER_ID,
                                        'drafts': drafts, 'request_id': token})
        value = bots.generate(engine, {'identity': ctx['identity'], 'owner_id': OWNER_ID,
                                       'drafts': drafts, 'request_id': token,
                                       'preview_hash': preview['preview_hash']})
        require(len(value['bots']) == 2 and not value['idempotent'], 'Production preview/generate failed')
        require(engine.mysql('SELECT * FROM character_data WHERE id=' + str(OWNER_ID) + ';') == owner_before,
                'Offline bot generation modified the existing owner profile')
        require(all(engine.mysql('SELECT * FROM ' + bots.ident(table) + ';') == before
                    for table, before in inventory_before.items()),
                'Offline bot generation modified existing owner inventory or evolving items')
        report['checks']['real_owner_inventory_and_sharedbank_preserved'] = {'item': item_id, 'original_guid': 0}
        ids = [bot['id'] for bot in value['bots']]
        saved = rows(engine, 'SELECT bot_id,owner_id,level,hp,mana,face,hair_color,hair_style,eye_color_1,eye_color_2 '
                     'FROM bot_data ORDER BY bot_id;')
        require(len(saved) == 2 and all(int(row[1]) == OWNER_ID and int(row[2]) == 35 and int(row[3]) > 0
                    for row in saved), 'Normal Bot::Save owner, levels, or health were not persisted')
        require(int(scalar(engine, 'SELECT mana FROM bot_data WHERE bot_id=' + str(ids[1]) + ';')) > 0,
                'Normal caster bot mana was not generated')
        require(rows(engine, 'SELECT item_id FROM bot_inventories WHERE bot_id=' + str(ids[0])
                     + ' AND slot_id=2;') == [[str(item_id)]], 'Configured native starting item was not saved')
        require(int(scalar(engine, 'SELECT COUNT(*) FROM bot_stances WHERE bot_id IN (' + ','.join(map(str, ids)) + ');')) == 2,
                'Normal bot stance saves are missing')
        require(int(scalar(engine, 'SELECT COUNT(*) FROM bot_settings WHERE bot_id IN (' + ','.join(map(str, ids)) + ');')) > 0,
                'Normal bot settings saves are missing')
        for bot in value['bots']:
            require(rows(engine, 'SELECT value FROM data_buckets WHERE character_id=' + str(OWNER_ID)
                         + ' AND `key`=' + bots.literal('trasc_native_' + bot['name']) + ';') == [[str(bot['id'])]],
                    'Actual EVENT_BOT_CREATE player quest did not receive the native bot ID')
        report['checks']['production_preview_generate_normal_state_items_hooks'] = {'ids': ids, 'state': saved, 'starting_item': item_id}
        payload = request(engine, drafts)
        payload.update(request_id=token, draft_hash=preview['preview_hash'], identity_hash=ctx['identity'])
        before = snapshot(engine)
        engine.db.terminate()
        engine.db.wait(timeout=45)
        engine.db = None
        engine.ensure_db()
        response = native(engine, payload, evidence, 'restart-retry')
        require(response['bots'] == value['bots'] and response.get('reused') is True and snapshot(engine) == before,
                'Fresh server/DB restart retry did not load the original saved bots without writes')
        report['checks']['database_restart_native_load_idempotent_retry'] = True

        checks = report['checks']
        rejected(engine, request(engine, [draft('Trascbridge')]), evidence, 'player-name-collision', checks)
        rejected(engine, request(engine, [draft('Trascguard')]), evidence, 'bot-name-collision', checks)
        rejected(engine, request(engine, [draft('Trascinvalid', 10)]), evidence, 'invalid-race-class', checks)
        rejected(engine, request(engine, [draft('Trascgender', gender=2)]), evidence, 'invalid-gender', checks)
        changed = dict(payload, bots=[draft('Trascedited')], bots_hash=bridge.fingerprint([draft('Trascedited')]))
        rejected(engine, changed, evidence, 'retry-draft-mismatch', checks)
        changed = request(engine, [draft('Trascstale')])
        changed['database_instance'] = '0' * 32
        rejected(engine, changed, evidence, 'database-incarnation-mismatch', checks)
        changed = request(engine, [draft('Trascstale')])
        changed['owner'] = dict(changed['owner'], level=36)
        rejected(engine, changed, evidence, 'owner-profile-mismatch', checks)

        rule(engine, 'Bots:BotCharacterLevel', '60', default)
        rejected(engine, request(engine, [draft('Trasclevel')]), evidence, 'owner-level-limit', checks)
        rule(engine, 'Bots:BotCharacterLevel', '0', default)
        rule(engine, 'Bots:CreationLimit', '2', default)
        rejected(engine, request(engine, [draft('Trasclimit')]), evidence, 'global-creation-limit', checks)
        rule(engine, 'Bots:CreationLimit', '3', default)
        rejected(engine, request(engine, [draft('Trascfirst'), draft('Trascsecond')]), evidence, 'mid-batch-limit-rollback', checks)
        rule(engine, 'Bots:CreationLimit', '100', default)
        engine.mysql('INSERT INTO data_buckets(`key`,value,character_id) VALUES'
                     "('bot_creation_limit_warrior','1'," + str(OWNER_ID) + ');')
        rejected(engine, request(engine, [draft('Trascclass')]), evidence, 'class-creation-limit', checks)
        engine.mysql("DELETE FROM data_buckets WHERE `key`='bot_creation_limit_warrior' AND character_id=" + str(OWNER_ID) + ';')
        engine.mysql("INSERT INTO rule_sets(ruleset_id,name) VALUES(999,'trascfixturezone');")
        rule(engine, 'Bots:Enabled', 'true', 999)
        rule(engine, 'Bots:BotCharacterLevel', '0', 999)
        rule(engine, 'Bots:CreationLimit', '3', 999)
        engine.mysql('UPDATE zone SET ruleset=999 WHERE zoneidnumber=' + str(zone_id) + ';')
        rejected(engine, request(engine, [draft('Trasczoneone'), draft('Trasczonetwo')]), evidence, 'owner-zone-rules-limit-rollback', checks)
        engine.mysql('UPDATE zone SET ruleset=' + str(default) + ' WHERE zoneidnumber=' + str(zone_id) + ';')

        normal_hook = hook.read_text()
        hook.write_text('function event_bot_create(e)\n  e.self:SetBucket("trasc_failed_hook", "ran")\n  error("intentional native fixture quest error")\nend\n')
        try:
            rejected(engine, request(engine, [draft('Traschookfail')]), evidence, 'creation-hook-error-rollback', checks)
        finally:
            hook.write_text(normal_hook)
        engine.mysql("CREATE TRIGGER trasc_test_stance_failure BEFORE INSERT ON bot_stances FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='intentional native fixture stance save failure';")
        try:
            rejected(engine, request(engine, [draft('Trascsavefail')]), evidence, 'ancillary-save-error-rollback', checks)
        finally:
            engine.mysql('DROP TRIGGER trasc_test_stance_failure;')
        # The second active character has genuinely empty possessions, while
        # sharing the account's existing bank. The real hook requires its bank
        # item to be loaded, even through the native empty-inventory branch.
        empty_owner = OWNER_ID + 1
        engine.mysql('INSERT INTO character_data(id,account_id,name,level,`class`,race,gender,zone_id,cur_hp,mana) VALUES('
                     + str(empty_owner) + ',' + str(OWNER_ID) + ",'Trascblank',35,1,1,0," + str(zone_id) + ',100,100);')
        require(scalar(engine, 'SELECT COUNT(*) FROM inventory WHERE character_id=' + str(empty_owner) + ';') == '0',
                'The secondary owner must have a genuinely empty inventory')
        empty_profile_before = engine.mysql('SELECT * FROM character_data WHERE id=' + str(empty_owner) + ';')
        inventory_before = {table: engine.mysql('SELECT * FROM ' + bots.ident(table) + ';')
                            for table in ('inventory', 'sharedbank', 'character_evolving_items')}
        empty_payload = request(engine, [draft('Trascempty')], empty_owner)
        empty_result = native(engine, empty_payload, evidence, 'empty-owner-create')
        require(empty_result['owner'] == empty_payload['owner'] and empty_result.get('reused') is False,
                'Native empty-owner creation returned another owner or an existing receipt')
        require(engine.mysql('SELECT * FROM character_data WHERE id=' + str(empty_owner) + ';') == empty_profile_before,
                'Empty-owner creation modified its character profile')
        require(all(engine.mysql('SELECT * FROM ' + bots.ident(table) + ';') == before
                    for table, before in inventory_before.items()),
                'Empty-owner creation modified inventory, sharedbank or evolving items')
        empty_bot_id = empty_result['bots'][0]['id']
        require(rows(engine, 'SELECT value FROM data_buckets WHERE character_id=' + str(empty_owner)
                     + " AND `key`='trasc_native_Trascempty';") == [[str(empty_bot_id)]],
                'The empty-owner hook did not execute with its actual shared bank')
        before = snapshot(engine)
        empty_retry = native(engine, empty_payload, evidence, 'empty-owner-retry')
        require(empty_retry['bots'] == empty_result['bots'] and empty_retry.get('reused') is True
                and snapshot(engine) == before, 'Empty-owner retry changed its saved rows')
        checks['empty_owner_real_sharedbank_hook_and_native_reload'] = {'owner_id': empty_owner, 'bot_id': empty_bot_id}
        # This demonstrates the production refusal without changing storage
        # engines behind the user's back; only the disposable CI fixture is altered.
        engine.mysql('ALTER TABLE character_data ENGINE=MyISAM;')
        try:
            rejected(engine, request(engine, [draft('Trascengine')]), evidence, 'nontransactional-owner-rejected', checks)
        finally:
            engine.mysql('ALTER TABLE character_data ENGINE=InnoDB;')
        require(not engine.server_running(), 'Offline utility unexpectedly launched world services')
        checks['no_world_services_launched'] = True
        report['result'] = 'passed'
    except BaseException as error:
        report['result'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        atomic_json(args.output, report)
        if engine is not None:
            engine.shutdown()
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--profile', required=True, choices=('traditional', 'custom'))
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--database-zip', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--jobs', type=int, choices=(1, 2, 4), default=2)
    qualify(parser.parse_args())
