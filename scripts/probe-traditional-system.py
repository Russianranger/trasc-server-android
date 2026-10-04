"""Scoped, investigation-only source transformations for the Bookworm trial."""
import difflib
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
shim = pathlib.Path(sys.argv[2]).resolve()
originals = {name: (root / name).read_text() for name in (
    'CMakeLists.txt', 'common/CMakeLists.txt', 'zone/CMakeLists.txt',
    'common/net/crc32.cpp', 'common/process.h', 'zone/fastmath.cpp',
    'common/json/json_archive_single_line.h', 'common/strings.cpp', 'common/database_schema.h',
    'common/event/event_loop.cpp', 'common/event/timer.cpp', 'zone/lua_ptr.h',
    'zone/lua_mod.h', 'zone/quest_interface.h', 'zone/command.h', 'zone/bot_command.h',
    'zone/bot_commands/bot_help.cpp', 'zone/bot_commands/bot_inventory.cpp',
    'zone/gm_commands/feature.cpp', 'zone/gm_commands/list.cpp',
    'zone/gm_commands/show/show_content_flags.cpp', 'zone/gm_commands/show/show_recipe.cpp',
    'zone/aa.h', 'zone/dialogue_window.h', 'zone/dialogue_window.cpp',
    'zone/beacon.cpp', 'zone/guild_mgr.h', 'zone/mob.h', 'zone/petitions.h',
    'zone/petitions.cpp', 'zone/pets.h', 'zone/qglobals.h', 'zone/task_client_state.h', 'zone/guild_mgr.cpp',
    'zone/zone_loot.cpp', 'common/repositories/zone_state_spawns_repository.h', 'zone/zonedb.cpp')}
top = root / 'CMakeLists.txt'
text = top.read_text()
original = 'if(NOT CMAKE_TOOLCHAIN_FILE)'
assert text.count(original) == 1
text = text.replace(original, 'if(NOT CMAKE_TOOLCHAIN_FILE AND NOT EQEMU_USE_SYSTEM_DEPENDENCIES)', 1)
start = text.index('find_package(Boost REQUIRED COMPONENTS dynamic_bitset foreach tuple)')
end = text.index('find_package(PerlLibs)', start) + len('find_package(PerlLibs)')
text = text[:start] + f'include("{shim}")' + text[end:]
top.write_text(text)

common = root / 'common/CMakeLists.txt'
text = common.read_text()
original = 'target_include_directories(common PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/../submodules/websocketpp")'
assert text.count(original) == 1
text = text.replace(original, 'target_include_directories(common PUBLIC "${TRASC_WEBSOCKETPP_INCLUDE_DIR}")', 1)
common.write_text(text)

zone = root / 'zone/CMakeLists.txt'
text = zone.read_text()
for name in ('lua_zone', 'perl_zone', 'gm_commands_zone'):
    original = f'set_target_properties({name} PROPERTIES UNITY_BUILD ON UNITY_BUILD_BATCH_SIZE '
    assert text.count(original) == 1
    text = text.replace(original, f'set_target_properties({name} PROPERTIES UNITY_BUILD OFF UNITY_BUILD_BATCH_SIZE ', 1)
zone.write_text(text)

# This translation unit otherwise gets uint8_t only through the optional PCH.
crc32 = root / 'common/net/crc32.cpp'
text = crc32.read_text()
assert '#include <cstdint>' not in text
crc32.write_text('#include <cstdint>\n' + text)
process_header = root / 'common/process.h'
text = process_header.read_text()
assert '#include <string>' not in text
process_header.write_text('#include <string>\n' + text)
database_schema = root / 'common/database_schema.h'
text = database_schema.read_text()
assert '#include <string>' not in text
database_schema.write_text('#include <string>\n' + text)
event_loop = root / 'common/event/event_loop.cpp'
text = event_loop.read_text()
assert '#include <cstring>' not in text
event_loop.write_text('#include <cstring>\n' + text)
event_timer = root / 'common/event/timer.cpp'
text = event_timer.read_text()
assert '#include <cstring>' not in text
event_timer.write_text('#include <cstring>\n' + text)
lua_ptr = root / 'zone/lua_ptr.h'
text = lua_ptr.read_text()
assert '#include "common/types.h"' not in text
original = '#include "lua.hpp"'
assert text.count(original) == 1
lua_ptr.write_text(text.replace(original, '#include "common/types.h"\n' + original, 1))
lua_mod = root / 'zone/lua_mod.h'
text = lua_mod.read_text()
original = 'class LuaParser;'
assert text.count(original) == 1
lua_mod.write_text(text.replace(original,
    'class Client;\nclass Mob;\nstruct DamageHitInfo;\nstruct ExtraAttackOptions;\n' + original, 1))
quest_interface = root / 'zone/quest_interface.h'
text = quest_interface.read_text()
original = '#include <any>'
assert text.count(original) == 1
quest_interface.write_text(text.replace(original,
    '#include "common/eqemu_logsys.h"\n#include "common/rulesys.h"\n#include "common/strings.h"\n'
    '#include <list>\n#include <string>\n#include <vector>\nclass Mob;\nclass Zone;\nclass Bot;\nclass Merc;\n' + original, 1))
command_header = root / 'zone/command.h'
text = command_header.read_text()
assert '#include <map>' not in text
command_header.write_text('#include <map>\n' + text)
bot_command_header = root / 'zone/bot_command.h'
text = bot_command_header.read_text()
assert '#include <map>' not in text
original = '} BotCommandRecord;'
assert text.count(original) == 1
bot_command_header.write_text('#include <map>\n' + text.replace(original, original +
    '\nextern std::map<std::string, BotCommandRecord *> bot_command_list;'
    '\nextern std::map<std::string, std::string> bot_command_aliases;', 1))
for name in ('zone/bot_commands/bot_help.cpp', 'zone/bot_commands/bot_inventory.cpp'):
    path = root / name
    text = path.read_text()
    original = '#include "zone/bot_command.h"'
    assert text.count(original) == 1
    path.write_text(text.replace(original, original + '\n#include "zone/quest_parser_collection.h"', 1))
for name, include in (('zone/gm_commands/feature.cpp', 'zone/command.h'),
                      ('zone/gm_commands/list.cpp', 'zone/bot.h'),
                      ('zone/gm_commands/show/show_content_flags.cpp', 'common/repositories/content_flags_repository.h'),
                      ('zone/gm_commands/show/show_recipe.cpp', 'zone/object.h')):
    path = root / name
    text = path.read_text()
    original = '#include "zone/client.h"'
    assert text.count(original) == 1
    path.write_text(text.replace(original, original + f'\n#include "{include}"', 1))
for name in ('zone/aa.h', 'zone/dialogue_window.h'):
    path = root / name
    text = path.read_text()
    assert '#include "common/types.h"' not in text
    path.write_text('#include "common/types.h"\n' + text)
path = root / 'zone/dialogue_window.cpp'
text = path.read_text()
original = '#include "dialogue_window.h"'
assert text.count(original) == 1
path.write_text(text.replace(original, original + '\n#include "zone/client.h"'
    '\n#include "common/eqemu_logsys.h"\n#include "common/strings.h"', 1))
path = root / 'zone/beacon.cpp'
text = path.read_text()
original = 'extern EntityList entity_list;\nextern Zone* zone;\n\nclass Zone;'
assert text.count(original) == 1
path.write_text(text.replace(original,
    'class Zone;\n\nextern EntityList entity_list;\nextern Zone* zone;', 1))
path = root / 'zone/guild_mgr.h'
text = path.read_text()
assert '#include <memory>' not in text
original = 'class ServerPacket;'
assert text.count(original) == 1
path.write_text('#include <memory>\n' + text.replace(original,
    original + '\nnamespace EQ { class ItemInstance; }', 1))
path = root / 'zone/mob.h'
text = path.read_text()
original = 'class Client;'
assert text.count(original) == 1
path.write_text(text.replace(original, original + '\nclass HealRotation;', 1))
for name, includes in (
    ('zone/petitions.h', '#include "common/strings.h"\n#include <cstring>'),
    ('zone/pets.h', '#include "zone/npc.h"'),
    ('zone/qglobals.h', '#include "common/types.h"\n#include <string>'),
    ('zone/guild_mgr.cpp', '#include "common/misc_functions.h"')):
    path = root / name
    text = path.read_text()
    for include in includes.splitlines():
        assert include not in text
    path.write_text(includes + '\n' + text)
path = root / 'zone/petitions.cpp'
text = path.read_text()
original = '#include "petitions.h"'
assert text.count(original) == 1
path.write_text(text.replace(original, original + '\n#include "zone/client.h"'
    '\n#include "common/eq_packet.h"', 1))
path = root / 'zone/task_client_state.h'
text = path.read_text()
original = '#include "zone/tasks.h"'
assert text.count(original) == 1
path.write_text(text.replace(original, original + '\n#include <glm/vec4.hpp>\n'
    'class NPC;\nclass Corpse;\nclass Trade;\nclass DynamicZone;', 1))
for name, include in (
    ('zone/zone_loot.cpp', '#include "common/content/world_content_service.h"'),
    ('common/repositories/zone_state_spawns_repository.h', '#include "common/rulesys.h"')):
    path = root / name
    text = path.read_text()
    assert include not in text
    path.write_text(include + '\n' + text)
path = root / 'zone/zonedb.cpp'
text = path.read_text()
for include in ('#include "zone/client.h"', '#include "zone/zone.h"'):
    assert text.count(include) == 1
    text = text.replace(include + '\n', '', 1)
original = '#include "zonedb.h"'
assert text.count(original) == 1
path.write_text(text.replace(original,
    original + '\n#include "zone/client.h"\n#include "zone/zone.h"', 1))
fastmath = root / 'zone/fastmath.cpp'
text = fastmath.read_text()
assert '#include <cmath>' not in text
fastmath.write_text('#include <cmath>\n' + text)
for name, expected_count in (('common/json/json_archive_single_line.h', 4), ('common/strings.cpp', 1)):
    path = root / name
    text = path.read_text()
    assert text.count('cereal/external/rapidjson/') == expected_count
    text = text.replace('cereal/external/rapidjson/', 'rapidjson/')
    if name == 'common/json/json_archive_single_line.h':
        assert text.count('CEREAL_RAPIDJSON_ASSERT') == 1
        text = text.replace('CEREAL_RAPIDJSON_ASSERT', 'RAPIDJSON_ASSERT')
    path.write_text(text)
if len(sys.argv) > 3:
    patch = ''.join(''.join(difflib.unified_diff(
        original.splitlines(keepends=True), (root / name).read_text().splitlines(keepends=True),
        fromfile='a/' + name, tofile='b/' + name)) for name, original in originals.items())
    output = pathlib.Path(sys.argv[3])
    output.write_text(patch)
    output.with_suffix('.sha256').write_text(hashlib.sha256(patch.encode()).hexdigest() + '\n')
print('Applied scoped system-dependency and low-memory build probe transformations')
