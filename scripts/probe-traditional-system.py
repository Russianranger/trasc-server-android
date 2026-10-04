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
    'common/event/event_loop.cpp', 'common/event/timer.cpp', 'zone/lua_ptr.h')}
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
