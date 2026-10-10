"""Qualified, server-owned offline creation for Traditional and TRASC Custom.

The launcher never synthesizes bot_data rows for modern worlds. This adapter
adds a one-shot command to the exact reviewed zone server and verifies its
deployed byte hash and protocol before invoking normal server creation logic.
"""
import argparse
import hashlib
import json
from pathlib import Path
import secrets

RECIPE = 'trasc-modern-offline-bots-v1'
REVISIONS = {'traditional': '4aceae18b94ffaafc08e2b17bc41cd72c77f795d',
             'custom': '8f6ca0795f424a7b4eab750ff38fc6473d48375c'}
GUARDS = {
    'traditional': {
        'zone/main.cpp': '18b67065843c48c70f73648dc21acf052cb195cea6adfd1d422e274bd04a2ddf',
        'zone/client.h': 'a5354c520afbb9efee0149d30de953faceab9b64addb9ae4a600c6ed2730ea80',
        'zone/client.cpp': 'd4c2f32d1e34de08d5f631b7034fbe6d8c70ec84c7c67af5ec361454834ef253',
        'zone/zone.h': '5b9e1660575d4fd942fec9ffa3aa290915c80b7577c5ae07c703263e9cb0b704',
        'zone/zone.cpp': '3c8bf67f90c89af1bf3c5824159d162ea8a73fcfd9dbe3bc80735ccc1413c31c',
        'common/dbcore.h': '76a3455ec98908f0228f0454d0983c37e6ba76cbe54e10a4ab64efc765fefe97',
        'common/dbcore.cpp': '577a53ab4a67a00979e41416ff6271be1132e9f8dca8d922fb59d895bd7ef513',
        'common/shareddb.h': 'faf44aa7e51be1bf60f0f925a3b76ed473450883b061663fd6ff55efdf331966',
        'common/shareddb.cpp': 'ea4a12dc8a24a7ab0690405314088590df53b1c86160bc32709d722c2b12a10b',
        'zone/bot_command.cpp': 'a2e206c47a3418ad68cbec7e494124f74f757605e044ab9f0079a152b0a5c312',
        'zone/bot.cpp': '60ccf8e2ccee7f8cf7920063c6335dee1c87605c84f42c3976926db6f31eee40',
        'zone/client_bot.cpp': 'eb0ffcae4b7ae21e4c5453a0eb23bb5ed1e6037174d3a8864b8320537c10185f',
        'zone/bot_database.cpp': '98d0bd7929bc32308a393cdf3a2bd86a08ea5f129689c6091e0eb7a7b9cad302',
        'common/repositories/base/base_bot_data_repository.h': '52e38e93ea2d3b04df1cc5322170a44c4b599ce68190158faab9b20b4a3d5163',
    },
    'custom': {
        'zone/main.cpp': '6b7421f4a45a5ca8ba7f1e70d953faa94eb6be6e9a51298c10363756fabec08f',
        'zone/client.h': 'bd235638c43704d4daa6b0ea70cc3c21da696f8b24c04131b8de23cd49c25e7d',
        'zone/client.cpp': '67a264ae55979b83790a99659f5649343da098e684c0917ba6a2c24ee7d7efee',
        'zone/zone.h': 'd888e3db36711aeec49a2ec6a51a1d8fb16b7d47481016af01427df71d9e35f5',
        'zone/zone.cpp': '0e0229380c73da51f73bfd4e76d012a29a2eb349ed9c2c91a4063bfbe17f0010',
        'common/dbcore.h': '65d8e32249315315a3cd42ed72a0b2896bb3a5a28e76ab9bafd61694d809d63e',
        'common/dbcore.cpp': 'f6b80871b0dcae480bf02eeeb0395474c64e211d16157ae25ed1de49a4df6726',
        'common/shareddb.h': '3314393604778b95baeaa85e3f4ac02206a796f9b5029fe9ddf5888925e8b37e',
        'common/shareddb.cpp': '2942034c3a798ca09f90e2e5e5c6c1b2f85c3d8afa44bc357483c815c7382980',
        'zone/bot_command.cpp': '8bc57efe8dd7bc74800ed4bcfbfca8f1ffdb07f7fcd4af17b8affd2e2598f04e',
        'zone/bot.cpp': '0e344bbc0a50ae37e42102d0420bb1611265a1668d7411831e4ec4ada25ac049',
        'zone/client_bot.cpp': '2460d9fd7d9fcaf0ff577cff2917ddc8890296bca259e730b0203a2e6c3682e6',
        'zone/bot_database.cpp': '53758d0c92d56bf6fa45fa71bebad922df5f82a995d2f9aea19370bb38adb8d3',
        'common/repositories/base/base_bot_data_repository.h': 'be775a8da15f3e788671ef05806d74092886741fab1a46aefe8555f630ba1f8b',
    },
}
PATCHED = ('zone/main.cpp', 'zone/client.h', 'zone/client.cpp', 'zone/zone.h', 'zone/zone.cpp', 'common/dbcore.h', 'common/dbcore.cpp', 'common/shareddb.h', 'common/shareddb.cpp')
# Reproducible outputs of the source transformations, independent of the
# source-tree marker. The generated header is checked against this module's
# own current template and identity below. Editing a marker cannot qualify an
# arbitrary modified server source.
PATCHED_GUARDS = {
    'traditional': {
        'zone/main.cpp': 'ee1db78faa9c5324baa2ee1f6cf4165209e037eb8ee835de59109ee58354763b',
        'zone/client.h': '13c7a6a31a824ff10877e41409c98a5cf10fd04aee5f1231f15e85ccf7cb0a24',
        'zone/client.cpp': '02efe9f3b18af2f7b60f231457d77f600dc680cf9b5fb139d3ea36864c63b835',
        'zone/zone.h': 'c54d5c5c887172489bb45fcd3020a1946f72ffbfc13b83f9f7e16842b0bf3339',
        'zone/zone.cpp': 'b6f14927e64cb5b1de3e3737c94582e917ee00a561d61fd14b9d2cc88fdb4946',
        'common/dbcore.h': 'bd0efaf8185d233ccf2b4a054acb1b9e1b5df7e57c38dd702f516e798c42ac63',
        'common/dbcore.cpp': 'b09f16f62b04b3403fc8e5946904be0ff88c6c78cdcd727536172a5d05c6f451',
        'common/shareddb.h': '57ff0c587e917a1e067724ed8737a685c75000dd00a330621a6bb794482b4b20',
        'common/shareddb.cpp': 'c267bbb78095e48aeae728c03bfedac99fb19e2316c65db0feb2b76c909c216c',
    },
    'custom': {
        'zone/main.cpp': 'c959bd48e5517224600b75a4732a5f1b6f603c514bc72bf11759e82241b3b8ea',
        'zone/client.h': 'eaaa2b79675cc0156a2bf0bb9e170c3b6f532463cd7895324c24e529004ed338',
        'zone/client.cpp': '36625aa5965134b1b1f4118f0044565d155ae314a7dbd21fdf7cba2a8c009c94',
        'zone/zone.h': 'f77dcc9ad5a267e06e07d770f49068c3169b6dc61327ceed7893a0a6aaf7b123',
        'zone/zone.cpp': '67a04a3eaec1cdfa73a463ad2022407a7cf0e8c1dd6822ca5137fcedf99fc3bf',
        'common/dbcore.h': '4030587c5bc68444b59ce48099653cddd66c389be0ecb32e4f56ddd1265d67b1',
        'common/dbcore.cpp': 'c7b7de66515fa0337234d8d20b255b8a31855e82d0d3fc0c8d557d18e51be61c',
        'common/shareddb.h': '0824dabddf5b5ddd3eaeca49da66ad5ca487af1bbad70b9041489cb5c768ca57',
        'common/shareddb.cpp': '114b71e8e4248ca1ca7f9cb4e7783442cb83e20c352a3ae238efb134eb536a5f',
    },
}


class UnsupportedSource(ValueError):
    """A pristine source revision is usable, but its bot logic is unqualified."""


BOT_DATA_COLUMNS = (
    'bot_id', 'owner_id', 'spells_id', 'name', 'last_name', 'title', 'suffix',
    'zone_id', 'gender', 'race', 'class', 'level', 'deity', 'creation_day', 'last_spawn',
    'time_spawned', 'size', 'face', 'hair_color', 'hair_style', 'beard', 'beard_color',
    'eye_color_1', 'eye_color_2', 'drakkin_heritage', 'drakkin_tattoo', 'drakkin_details',
    'ac', 'atk', 'hp', 'mana', 'str', 'sta', 'cha', 'dex', 'int', 'agi', 'wis',
    'extra_haste', 'fire', 'cold', 'magic', 'poison', 'disease', 'corruption')


def bot_data_columns(profile):
    if profile not in REVISIONS:
        raise ValueError('Unknown modern bot profile')
    return BOT_DATA_COLUMNS + (('expansion_bitmask',) if profile == 'traditional' else ())


def _database_schema(ctx):
    available = ctx.get('shape', {}).get('column_names', {}).get('bot_data', [])
    missing = sorted(set(bot_data_columns(ctx['profile'])) - set(available))
    if missing:
        raise ValueError('The bot database does not match this server: missing ' + ', '.join(missing)
                         + '. Rebuild and deploy this world before generating bots')


def _database_ready(engine, ctx):
    _database_schema(ctx)
    if ctx['profile'] == 'traditional':
        import traditional_runtime
        traditional_runtime._bot_repair_pending(engine)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _read(path, maximum=8 * 1024**2):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('Offline bot adapter source is missing or unsafe: ' + path.name)
    return path.read_bytes()


def digest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Offline bot adapter cannot follow a binary symlink')
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def metadata(profile):
    if profile not in REVISIONS:
        raise ValueError('Offline modern bots belong to Custom or Traditional')
    return {'format': 1, 'recipe': RECIPE, 'profile': profile, 'source_revision': REVISIONS[profile],
            'patch_identity': fingerprint({'recipe': RECIPE, 'profile': profile, 'source_revision': REVISIONS[profile],
                'guards': GUARDS[profile], 'adapter': digest(__file__),
                'template': hashlib.sha256(_read(Path(__file__).with_suffix('.h'))).hexdigest()})}


def _replace(text, before, after, path):
    if text.count(before) != 1:
        raise ValueError('Offline bot adapter patch anchor changed: ' + path)
    return text.replace(before, after, 1)


def _header(profile):
    spec = metadata(profile)
    template = _read(Path(__file__).with_suffix('.h')).decode('utf-8')
    for key, value in (('@TRASC_PROFILE@', profile), ('@TRASC_REVISION@', spec['source_revision']), ('@TRASC_IDENTITY@', spec['patch_identity'])):
        template = template.replace(key, value)
    return template.encode()


DB_GUARD = r'''
    void SetTrascAtomicBatch(bool active) { m_trasc_atomic_batch = active; }
    uint64_t GetTrascQueryFailures() const { return m_trasc_query_failures; }
    void SetTrascWritableTables(const std::set<std::string>& tables) { m_trasc_writable_tables = tables; }
private:
    bool m_trasc_atomic_batch = false;
    uint64_t m_trasc_query_failures = 0;
    std::set<std::string> m_trasc_writable_tables;
    void TrascGuardQuery(const char* query, uint32 length) {
        if (!m_trasc_atomic_batch) return;
        std::string sql(query, length);
        const std::regex read(R"(^\s*(SELECT|SHOW|DESCRIBE)\s)", std::regex::icase);
        if (std::regex_search(sql, read)) return;
        const std::regex write(R"(^\s*(?:INSERT\s+(?:IGNORE\s+)?INTO|REPLACE(?:\s+INTO)?|UPDATE|DELETE\s+FROM)\s+`?([A-Za-z0-9_]+)`?(?:\s|\())", std::regex::icase);
        std::smatch match;
        // Multi-table UPDATE/DELETE can write another non-transactional table.
        // Normal bot saves are single-table statements; reject wider targets.
        const std::regex multi(R"(^\s*(?:UPDATE\s+[^;]*?(?:\sJOIN\s|,)[^;]*?\sSET\s|DELETE\s+[^;]*?(?:\sJOIN\s|\sUSING\s)))", std::regex::icase);
        if (std::regex_search(sql, match, write) && !std::regex_search(sql, multi) && m_trasc_writable_tables.count(match[1].str())) return;
        ++m_trasc_query_failures;
        throw std::runtime_error("Offline bot creation requires transactional SQL writes; a quest attempted an unsupported operation.");
    }
public:
'''


def output_files(root, profile):
    """Return exact output bytes after checking all creation-critical inputs."""
    root = Path(root)
    spec = metadata(profile)
    inputs = {}
    for name, expected in GUARDS[profile].items():
        data = _read(root / name)
        if hashlib.sha256(data).hexdigest() != expected:
            raise UnsupportedSource('The ' + profile + ' source is not qualified for offline bot creation: ' + name)
        inputs[name] = data
    output = {}
    for name in PATCHED:
        data = inputs[name]
        newline = '\r\n' if b'\r\n' in data else '\n'
        text = data.decode('utf-8').replace('\r\n', '\n')
        if name == 'zone/main.cpp':
            text = _replace(text, 'int main(int argc, char **argv)\n{', '#include "trasc_bot_bridge.h"\n\nint main(int argc, char **argv)\n{\n'
                '    if (argc == 2 && !strcmp(argv[1], "--trasc-bot-capabilities")) {\n'
                '        std::cout << TrascBotBridge::Capabilities().dump() << std::endl;\n        return 0;\n    }\n'
                '    const bool trasc_offline_bots = argc == 2 && !strcmp(argv[1], "--trasc-bot-create");', name)
            text = _replace(text, 'if (ZoneCLI::RanConsoleCommand(argc, argv) && !(ZoneCLI::RanSidecarCommand(argc, argv) || ZoneCLI::RanTestCommand(argc, argv))) {',
                'if (!trasc_offline_bots && ZoneCLI::RanConsoleCommand(argc, argv) && !(ZoneCLI::RanSidecarCommand(argc, argv) || ZoneCLI::RanTestCommand(argc, argv))) {', name)
            text = _replace(text, 'PlayerEventLogs::Instance()->SetDatabase(&database)->Init();',
                'if (!trasc_offline_bots) PlayerEventLogs::Instance()->SetDatabase(&database)->Init();', name)
            text = _replace(text, 'int retval = command_init();',
                'int retval = trasc_offline_bots ? 0 : command_init();', name)
            text = _replace(text, 'int botretval = bot_command_init();',
                'int botretval = trasc_offline_bots ? 0 : bot_command_init();', name)
            before = ('\tEQEmuLogSys::Instance()->SetDatabase(&database)\n'
                '\t\t->SetLogPath(PathManager::Instance()->GetLogPath())\n'
                '\t\t->LoadLogDatabaseSettings(ZoneCLI::RanTestCommand(argc, argv))\n'
                '\t\t->SetGMSayHandler(&Zone::GMSayHookCallBackProcess)\n'
                '\t\t->StartFileLogs();')
            text = _replace(text, before, '\tif (!trasc_offline_bots) {\n' + before + '\n\t}', name)
            text = _replace(text, '\tparse->ReloadQuests();',
                '\tif (!trasc_offline_bots) parse->ReloadQuests();', name)
            text = _replace(text, '\tif (!database.LoadItems(hotfix_name)) {',
                '\tif (!database.LoadItems(hotfix_name)) {\n'
                '        if (trasc_offline_bots) {\n'
                '            std::cout << "TRASC_BOT_RESULT " << TrascBotBridge::Json({{"format", 1}, {"ok", false},\n'
                '                {"error", "Shared item data is unavailable; start and stop this world server to prepare items before generating bots."}}).dump() << std::endl;\n'
                '            return 1;\n        }', name)
            text = _replace(text, '\tQServ->CheckForConnectState();\n\n\tworldserver.Connect();',
                '    if (trasc_offline_bots) return TrascBotBridge::Create();\n\n\tQServ->CheckForConnectState();\n\n\tworldserver.Connect();', name)
        elif name == 'zone/client.h':
            text = _replace(text, 'inline void SetCharacterId(uint32_t id) { character_id = id; }',
                'inline void SetCharacterId(uint32_t id) { character_id = id; }\n'
                'private:\n    bool m_trasc_offline_bot_owner = false;\npublic:\n'
                '    bool PrepareTrascOfflineBotOwner(uint32_t owner_id, uint32_t owner_account_id);', name)
        elif name == 'zone/client.cpp':
            text = _replace(text, '\tUpdateWho(2);\n\n\tif(IsHoveringForRespawn())',
                '\tif (!m_trasc_offline_bot_owner) UpdateWho(2);\n\n\tif(IsHoveringForRespawn())', name)
        elif name == 'zone/zone.h':
            text = _replace(text, 'Zone(uint32 in_zoneid, uint32 in_instanceid, const char *in_short_name);',
                'Zone(uint32 in_zoneid, uint32 in_instanceid, const char *in_short_name, bool trasc_offline = false);\n'
                '    int GetTrascOfflineRuleset() const { return default_ruleset; }\n'
                'private:\n    bool m_trasc_offline = false;\npublic:', name)
        elif name == 'zone/zone.cpp':
            text = _replace(text, 'Zone::Zone(uint32 in_zoneid, uint32 in_instanceid, const char* in_short_name)',
                'Zone::Zone(uint32 in_zoneid, uint32 in_instanceid, const char* in_short_name, bool trasc_offline)', name)
            text = _replace(text, '\tzoneid = in_zoneid;',
                '\tm_trasc_offline = trasc_offline;\n\tzoneid = in_zoneid;', name)
            text = _replace(text, '\tdatabase.QGlobalPurge();', '\tif (!trasc_offline) database.QGlobalPurge();', name)
            text = _replace(text, '\tentity_list.Clear();\n\tparse->ReloadQuests();',
                '\tentity_list.Clear();\n'
                '\t// The one-shot owner context has no zone loop to reload.\n'
                '\tif (!m_trasc_offline) parse->ReloadQuests();', name)
            text = _replace(text, '\tif (worldserver.Connected()) {\n\t\tworldserver.SetZoneData(0);\n\t}',
                '\tif (!m_trasc_offline && worldserver.Connected()) {\n\t\tworldserver.SetZoneData(0);\n\t}', name)
        elif name == 'common/dbcore.h':
            text = '#include <cstdint>\n#include <regex>\n#include <set>\n#include <stdexcept>\n#include <string>\n' + text
            text = _replace(text, '\tDBcore();', DB_GUARD + '\n\tDBcore();', name)
        elif name == 'common/dbcore.cpp':
            text = _replace(text, 'MySQLRequestResult DBcore::QueryDatabase(const char *query, uint32 querylen, bool retryOnFailureOnce)\n{',
                'MySQLRequestResult DBcore::QueryDatabase(const char *query, uint32 querylen, bool retryOnFailureOnce)\n{\n'
                '    TrascGuardQuery(query, querylen);\n'
                '    if (m_trasc_atomic_batch) {\n'
                '        if (pStatus != Connected) { ++m_trasc_query_failures; throw std::runtime_error("Bot database connection was lost; no batch may reconnect."); }\n'
                '        retryOnFailureOnce = false;\n    }', name)
            text = _replace(text, 'if (mysql_real_query(mysql, query, querylen) != 0) {',
                'if (mysql_real_query(mysql, query, querylen) != 0) {\n        ++m_trasc_query_failures;', name)
            text = _replace(text, 'MySQLRequestResult DBcore::QueryDatabaseMulti(const std::string &query)\n{',
                'MySQLRequestResult DBcore::QueryDatabaseMulti(const std::string &query)\n{\n'
                '    if (m_trasc_atomic_batch) { ++m_trasc_query_failures; throw std::runtime_error("Multiple SQL statements are unavailable during offline bot creation."); }', name)
            text = _replace(text, 'mysql::PreparedStmt DBcore::Prepare(std::string query)\n{',
                'mysql::PreparedStmt DBcore::Prepare(std::string query)\n{\n'
                '    if (m_trasc_atomic_batch) { ++m_trasc_query_failures; throw std::runtime_error("Prepared quest SQL is unavailable during offline bot creation."); }', name)
        elif name == 'common/shareddb.h':
            text = _replace(text, 'bool GetInventory(Client* c);',
                'bool GetInventory(Client* c, bool trasc_readonly = false);', name)
            text = _replace(text, 'bool GetSharedBank(uint32 id, EQ::InventoryProfile *inv, bool is_charid);',
                'bool GetSharedBank(uint32 id, EQ::InventoryProfile *inv, bool is_charid, bool trasc_readonly = false);', name)
        elif name == 'common/shareddb.cpp':
            text = _replace(text, 'bool SharedDatabase::GetInventory(Client *c)',
                'bool SharedDatabase::GetInventory(Client *c, bool trasc_readonly)', name)
            text = _replace(text, 'bool SharedDatabase::GetSharedBank(uint32 id, EQ::InventoryProfile *inv, bool is_charid)',
                'bool SharedDatabase::GetSharedBank(uint32 id, EQ::InventoryProfile *inv, bool is_charid, bool trasc_readonly)', name)
            text = _replace(text, '\t\tif (is_charid) {\n\t\t\tSaveInventory(id, nullptr, e.slot_id);',
                '\t\tif (is_charid && !trasc_readonly) {\n\t\t\tSaveInventory(id, nullptr, e.slot_id);', name)
            text = _replace(text, '\t\t\t\tauto r = CharacterEvolvingItemsRepository::InsertOne(*this, e);\n\t\t\t\te.id = r.id;',
                '\t\t\t\tif (!trasc_readonly) {\n'
                '\t\t\t\t\tauto r = CharacterEvolvingItemsRepository::InsertOne(*this, e);\n'
                '\t\t\t\t\te.id = r.id;\n\t\t\t\t}', name)
            text = _replace(text, '\tif (!queue.empty()) {\n\t\tInventoryRepository::ReplaceMany(*this, queue);',
                '\tif (!trasc_readonly && !queue.empty()) {\n\t\tInventoryRepository::ReplaceMany(*this, queue);', name)
            text = _replace(text, 'return GetSharedBank(char_id, &inv, true);',
                'return GetSharedBank(char_id, &inv, true, trasc_readonly);', name)
        output[name] = text.replace('\n', newline).encode('utf-8')
    output['zone/trasc_bot_bridge.h'] = _header(profile)
    if any(hashlib.sha256(output[name]).hexdigest() != expected for name, expected in PATCHED_GUARDS[profile].items()):
        raise ValueError('Offline bot adapter output does not match its qualified recipe')
    return output


def prepare(root, profile):
    """Apply once to the build overlay, or verify every already applied byte."""
    root = Path(root)
    marker = root / 'zone/trasc-bot-bridge.json'
    spec = metadata(profile)
    if marker.exists():
        stored = json.loads(_read(marker))
        if stored.get('metadata') != spec:
            raise ValueError('Offline bot adapter changed; import pristine server source before rebuilding')
        expected = dict(PATCHED_GUARDS[profile], **{'zone/trasc_bot_bridge.h': hashlib.sha256(_header(profile)).hexdigest()})
        if stored.get('outputs') != expected:
            raise ValueError('Offline bot adapter source receipt is incomplete or modified')
        for name, expected_sha in expected.items():
            if hashlib.sha256(_read(root / name)).hexdigest() != expected_sha:
                raise ValueError('Previously patched offline bot source changed: ' + name)
        for name, expected_sha in GUARDS[profile].items():
            if name not in PATCHED and hashlib.sha256(_read(root / name)).hexdigest() != expected_sha:
                raise ValueError('Offline bot creation logic changed: ' + name)
        return spec
    outputs = output_files(root, profile)
    for name, data in outputs.items():
        (root / name).write_bytes(data)
    marker.write_text(json.dumps({'metadata': spec, 'outputs': {name: hashlib.sha256(data).hexdigest() for name, data in outputs.items()}}, sort_keys=True))
    return spec


def _deployed(engine, ctx):
    profile = ctx['profile']
    expected = metadata(profile)
    deployment = ctx.get('deployment', {})
    if deployment.get('bot_creation_bridge_unavailable'):
        raise ValueError(str(deployment['bot_creation_bridge_unavailable']))
    if deployment.get('bot_creation_bridge') != expected:
        raise ValueError('Rebuild and deploy this world server to enable offline bot generation')
    zone = engine.work / 'server/bin/zone'
    if digest(zone) != deployment.get('zone_sha256'):
        raise ValueError('Deployed zone binary changed; rebuild and deploy before generating bots')
    return zone, expected


def _json_output(path):
    data = _read(path, 1024**2).decode('utf-8')
    # Zone bootstrap can log before it reaches the one-shot handler. A single
    # anchored result frame keeps both error and success responses unambiguous.
    frames = [line[len('TRASC_BOT_RESULT '):] for line in data.splitlines() if line.startswith('TRASC_BOT_RESULT ')]
    if frames:
        if len(frames) != 1:
            raise ValueError('Offline bot utility returned multiple response frames')
        data = frames[0]
    try:
        result = json.loads(data)
    except (ValueError, TypeError):
        raise ValueError('Offline bot utility returned an invalid response') from None
    if not isinstance(result, dict) or result.get('format') != 1:
        raise ValueError('Offline bot utility protocol does not match this launcher')
    return result


def capabilities(engine, ctx):
    try:
        zone, expected = _deployed(engine, ctx)
        _database_ready(engine, ctx)
        output = engine.work / 'run' / ('bot-capabilities-' + secrets.token_hex(6) + '.json')
        try:
            engine.run([zone, '--trasc-bot-capabilities'], cwd=engine.work / 'server', output_file=output, timeout=20, private=True)
            result = _json_output(output)
            if result.get('profile') != ctx['profile'] or result.get('patch_identity') != expected['patch_identity'] or result.get('source_revision') != expected['source_revision']:
                raise ValueError('Deployed server bot creation capability does not match its build receipt')
            if result.get('creation_receipt_table') != 'trasc_bot_creation_receipts' or result.get('offline_create') is not True:
                raise ValueError('Deployed server does not support offline bot creation')
            return dict(result, reason='')
        finally:
            output.unlink(missing_ok=True)
    except (ValueError, OSError) as error:
        return {'offline_create': False, 'reason': str(error)}


def create(engine, ctx, request):
    import bots
    bots.require_stopped(engine)
    zone, _ = _deployed(engine, ctx)
    _database_ready(engine, ctx)
    if ctx['identity'] != bots.context(engine, {'identity': ctx['identity']}, writing=True)['identity']:
        raise ValueError('Bot deployment changed before generation; refresh Bots')
    engine.write_config()
    prefix = engine.work / 'run' / ('bot-create-' + secrets.token_hex(8))
    incoming, outgoing = prefix.with_suffix('.request.json'), prefix.with_suffix('.result.json')
    payload = dict(request, format=1, profile=ctx['profile'], database=engine.config['database'],
                   database_instance=ctx['instance'], bots_hash=fingerprint(request['bots']))
    try:
        incoming.write_text(json.dumps(payload, sort_keys=True, separators=(',', ':')))
        incoming.chmod(0o600)
        try:
            engine.run([zone, '--trasc-bot-create'], cwd=engine.work / 'server', input_file=incoming, output_file=outgoing, timeout=180, private=True)
        except ValueError:
            if outgoing.is_file():
                response = _json_output(outgoing)
                if response.get('ok') is False and isinstance(response.get('error'), str):
                    raise ValueError(response['error']) from None
            raise
        result = _json_output(outgoing)
        if result.get('ok') is not True or result.get('owner') != request['owner']:
            raise ValueError(result.get('error', 'Offline bot creation returned an invalid owner'))
        if not isinstance(result.get('bots'), list) or len(result['bots']) != len(request['bots']):
            raise ValueError('Offline bot creation returned an incomplete batch')
        return {'owner': result['owner'], 'bots': result['bots']}
    finally:
        incoming.unlink(missing_ok=True)
        outgoing.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--profile', required=True, choices=tuple(REVISIONS))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    result = prepare(args.source, args.profile) if args.apply else {'files': sorted(output_files(args.source, args.profile)), 'metadata': metadata(args.profile)}
    print(json.dumps(result, sort_keys=True))
