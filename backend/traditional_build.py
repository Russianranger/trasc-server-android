"""Pinned Traditional EQEmu compile adapter for the app-owned ARM64 runtime.

Imports stay pristine. The qualified source is copied, patched and compiled in
an isolated overlay; all nine binaries validate before the staged set changes.
Deployment remains a separate, currently guarded milestone.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request

REPOSITORY = "https://github.com/Russianranger/Server"
REVISION = "4aceae18b94ffaafc08e2b17bc41cd72c77f795d"
RECIPE = "eqemu-bookworm-arm64-v1"
BINARIES = ("world", "zone", "shared_memory", "eqlaunch", "ucs", "queryserv", "loginserver", "export_client_files", "import_client_files")
WEBSOCKET_REVISION = "b9aeec6eaf3d5610503439b4fae3581d9aff08e8"
WEBSOCKET_URL = "https://codeload.github.com/zaphoyd/websocketpp/tar.gz/" + WEBSOCKET_REVISION
WEBSOCKET_TREE_SHA256 = "049b0323ca61bd4eaa1c0420bf842235c974517aa90cdb07873e24ecbf3c792f"
WEBSOCKET_FILES = 272
WEBSOCKET_BYTES = 3566324
MAX_SOURCE_FILES = 30000
MAX_SOURCE_BYTES = 1024**3
MAX_FILE_BYTES = 128 * 1024**2
MAX_WEBSOCKET_DOWNLOAD = 8 * 1024**2
MIN_FREE = 3 * 1024**3
RUNTIME_MARKER = Path("/etc/trasc-runtime.json")
MEMORY_INFO = Path('/proc/meminfo')

# Full-file guards were generated from the pinned, pristine Git commit. Every
# guard is checked before any overlay transformation writes a file.
SOURCE_HASHES = {'CMakeLists.txt': '084bd46ddc363abf4dcec925989a799899557d0a5f19ffbc2d0d641b59fba214',
 'common/CMakeLists.txt': 'b4e1d63cabc9b6575f49d6429484b41d7f85f8f53ec92fae211e1dd334079755',
 'zone/CMakeLists.txt': 'c086430a8f3092c4a2c994f118e4af67cb54145dda0856b4dafda64c7ccb294a',
 'common/net/crc32.cpp': '49652bfb35cfc95af3283d495f7c2c650ab701dd3b446a7cd2b7332c48e30e89',
 'common/process.h': '91499efed591b7930ed81e981a7e25932fe311d41293663b6fdf700f45c10cdf',
 'zone/fastmath.cpp': '93ce8aaa2c355db38f0a2a1b5fe027cf793d48390a4ffb3dbb9c79e08baead12',
 'common/json/json_archive_single_line.h': '68e4bf2ebfa5a9ba67ecc01b0889ff6462176a536d1a6cb7f7d1f02e3c91ab63',
 'common/strings.cpp': '27268da4108e8e02ea086bb12c2a4c8537708b73c123e0d1dcb7f11d9133137d',
 'common/database_schema.h': '13def8eec7d5cd048572c069df85a442979cb88dccdc32c19e0acb63c0bbe511',
 'common/event/event_loop.cpp': 'e1a471ab9f8385e59eb39e3d363bd7691ddaef82d3fc2e8ae44e4b56f37a2637',
 'common/event/timer.cpp': 'eea7c25cb798c9951c7ab6f90472f6f41247127f0fb5fbc9fe0f361581e62130',
 'zone/lua_ptr.h': '7577f45c1db45103a70f75520cb74f19ca8040d9badc35229a876b558764b886',
 'zone/lua_mod.h': '6ff3e86f2596ebbbe78ec06358e5802b84b07b36df49a3accd9a5b13cb207d26',
 'zone/quest_interface.h': 'd042ac96a727a8819c09871970250868c9d432b1c2911732d36a5931280d98e6',
 'zone/command.h': '8bcfee863e6ed5a351f55553c4b530e80a972c100e460c0a5511b4a80cbf10c6',
 'zone/bot_command.h': 'd5479d10353a0ababd2508771f192d764cf37cd7b3d57a8ccc8cf7b8b84e126a',
 'zone/bot_commands/bot_help.cpp': 'b55bbd2bb325d9dac8edcd470939c2917656728d9a1c69acdf8e4c84afe144fd',
 'zone/bot_commands/bot_inventory.cpp': 'eb935c197da79a4c838d67af06c87f47f9714f8c7c31cff8e681317cfbed73f9',
 'zone/gm_commands/feature.cpp': 'b20727c90e40f8506ea216dae6f053b74b2e881503849ece89e0753d9d6fd331',
 'zone/gm_commands/list.cpp': '5d07f9237ce0feb953c33ce048c82e6eecd38b1b3ef56bc79420502a683cfc31',
 'zone/gm_commands/show/show_content_flags.cpp': '3218c91d1a53c64ea8b6a10fcb2161f173c7f2b037dd5e298ba4b6ce67ec97f7',
 'zone/gm_commands/show/show_recipe.cpp': '2b32c05a6a17cdbd5f9739609302183747f38bc4b8837c2321e6c2877997de95',
 'zone/aa.h': '8027638d4d2ac2bebda63e5c3481fd83eb936047f241e5c675581b2774121d0a',
 'zone/dialogue_window.h': '4020c6c7795158d078d88bfd536648fc8d79b1da5e71db34fc6e4410a35b7152',
 'zone/dialogue_window.cpp': 'b6185b51df65a75d37854c65bd25a3d04c32a6f8317343d61d10a02bfd392caf',
 'zone/beacon.cpp': 'a812613ef56dfb2c83a03f7e6ef3244e6672138dda0e2f3cdda45af118b249f9',
 'zone/guild_mgr.h': '004959e193ca201c9529a5cca29fb3044579f97bc8d6b68282017631f122943e',
 'zone/mob.h': '9e2631af18a81085986e6d87e74ac22be435607498661a102edbcae69d132921',
 'zone/petitions.h': '203a732a2b710e6b9529f26b8a026fee6fa37594bf5146694a02a9ad039d3784',
 'zone/petitions.cpp': '28662a5770ce3dacbb3f9559f88727ed51152a12941617521609f338dda85520',
 'zone/pets.h': 'b5eb74767410fcf2278f50d4673677944baf796fc3311d5b3af30b44b4c0b0d9',
 'zone/qglobals.h': '2a9801a3cc944e5e2bbda64c16c7cd41473f052cc577c45eff12d0c59066d2d7',
 'zone/task_client_state.h': 'a747e78a5295c11e29dbc672441d33eb83fa46a2912358ed23d9ebc0fc60743f',
 'zone/guild_mgr.cpp': '5e825a1da4af4726e3841989ac1c8fa3adf0eb15dceaf1b01b3b8fefa44e322f',
 'zone/zone_loot.cpp': 'e5f05c3aece1110da2440b00cd06fa4b018956f71a760b9049d99709e817f0ca',
 'common/repositories/zone_state_spawns_repository.h': 'db44b212f47121e8b9df0b3505deb69819ea0571cefb96740b8a2e2faaf19feb',
 'zone/zonedb.cpp': '4807331dddd3ac63b6f015bd56c376ba9c51a63914bfa1b4247f0959d3f1b15b',
 '.gitmodules': 'aa8ad4456c32b9bf77fe60fea1e0f695d2df03f06f3a69b1d3594dc4a54bfff2',
 'cmake/FindLuaJit.cmake': '8668b715af5bcd06812d6e0852c16420eef5c750162fd4bf9dad881900aaf5d7',
 'world/CMakeLists.txt': '4becaf0a49193a38a3909a3ae06cfdd20d7cf68ffd0d57656822cbfde388f2de',
 'ucs/CMakeLists.txt': '64b2490e27549445df5ed30218fe6816b0ac785b2a8141ff7e88c93afeaf373d',
 'loginserver/CMakeLists.txt': 'f9df4342fa761ace63e49c86ff4c449515df29fc07f2e2b22720a56615542850',
 'queryserv/CMakeLists.txt': '808f317cf780a25538bd61dec2577eb614fff465975d680c719f2d7bcae3be0c',
 'shared_memory/CMakeLists.txt': '0effd93c2f5adf010bc8f4baee263e5eee4f78762a13de0db58316a789bfae7e',
 'eqlaunch/CMakeLists.txt': 'e177b3d1cea0ec7aaf2515bd484623dbaa71238e385e08bf3f04d2688c84880e',
 'client_files/CMakeLists.txt': 'b59cd893c8e6c5a55baa452270ead6368a2b04b97b51110d5d128813a6bf9190',
 'client_files/export/CMakeLists.txt': '2a20845e78800bc38e762ff39578c4f84645f64032dbab50f94b662880e4ba35',
 'client_files/import/CMakeLists.txt': 'd4e1d088b43bde6614d73324a8b324e4825f3c1721d196f7c9d03b4ce1f88f38'}


# Every active bundled-library CMake definition is also a qualified input.
SOURCE_HASHES.update({
    'libs/CMakeLists.txt': '6726844a094d6b2cee409964956280c43210ff8edaeca1fcfc393da9e3045432',
    'libs/luabind/CMakeLists.txt': '0824c3210c4b3ace6c79c9dac0382ea3878a147fc5805fb9df8215a163092b19',
    'libs/perlbind/CMakeLists.txt': 'aba3ea21f15f76bdd58b0c348490d20ad25e680c89aea0b63c9678fb385f8680',
})

# Exact, context-bound edits qualified by the native Bookworm trial.
SOURCE_PATCHES = {'CMakeLists.txt': [['et(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake/" ${CMAKE_MODULE_PATH})\n'
                     '\n'
                     'if(NOT CMAKE_TOOLCHAIN_FILE)\n'
                     '\tif(DEFINED ENV{VCPKG_ROOT})\n'
                     '\t\tmessage(STATUS "Using vcpkg from VCPKG_ROOT")\n'
                     '\t\tset(CMAKE_TOOLCHAIN',
                     'et(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake/" ${CMAKE_MODULE_PATH})\n'
                     '\n'
                     'if(NOT CMAKE_TOOLCHAIN_FILE AND NOT EQEMU_USE_SYSTEM_DEPENDENCIES)\n'
                     '\tif(DEFINED ENV{VCPKG_ROOT})\n'
                     '\t\tmessage(STATUS "Using vcpkg from VCPKG_ROOT")\n'
                     '\t\tset(CMAKE_TOOLCHAIN'],
                    ['YSTEM_NAME MATCHES "Darwin")\n'
                     '\t\tadd_compile_definitions(DARWIN)\n'
                     '\t\tset(DARWIN TRUE)\n'
                     '\tendif()\n'
                     'endif()\n'
                     '\n'
                     'find_package(Boost REQUIRED COMPONENTS dynamic_bitset foreach tuple)\n'
                     'find_package(cereal CONFIG REQUIRED)\n'
                     'find_package(fmt CONFIG REQUIRED)\n'
                     'find_package(glm CONFIG REQUIRED)\n'
                     'find_package(unofficial-libmariadb CONFIG REQUIRED)\n'
                     'find_package(libuv CONFIG REQUIRED)\n'
                     'find_package(OpenSSL REQUIRED)\n'
                     'find_package(recastnavigation CONFIG REQUIRED)\n'
                     'find_package(ZLIB REQUIRED)\n'
                     'find_package(LuaJit REQUIRED)\n'
                     'find_package(unofficial-sodium CONFIG REQUIRED)\n'
                     'find_package(PerlLibs)\n'
                     '\n'
                     'message(STATUS "**************************************************")\n'
                     'message(STATUS "* Library De',
                     'YSTEM_NAME MATCHES "Darwin")\n'
                     '\t\tadd_compile_definitions(DARWIN)\n'
                     '\t\tset(DARWIN TRUE)\n'
                     '\tendif()\n'
                     'endif()\n'
                     '\n'
                     'include("${CMAKE_CURRENT_LIST_DIR}/cmake/trasc-system-dependencies.cmake")\n'
                     '\n'
                     'message(STATUS "**************************************************")\n'
                     'message(STATUS "* Library De']],
 'common/CMakeLists.txt': [['ORCE_CTOR_INIT GLM_ENABLE_EXPERIMENTAL ENABLE_SECURITY)\n'
                            'target_include_directories(common PUBLIC '
                            '"${CMAKE_CURRENT_SOURCE_DIR}/../submodules/websocketpp")\n'
                            'target_include_directories(common PRIVATE ..)\n'
                            'target_link_libraries(common PUBLIC cereal::cereal ',
                            'ORCE_CTOR_INIT GLM_ENABLE_EXPERIMENTAL ENABLE_SECURITY)\n'
                            'target_include_directories(common PUBLIC "${TRASC_WEBSOCKETPP_INCLUDE_DIR}")\n'
                            'target_include_directories(common PRIVATE ..)\n'
                            'target_link_libraries(common PUBLIC cereal::cereal ']],
 'zone/CMakeLists.txt': [['y(TARGET lua_zone PROPERTY FOLDER libraries)\n'
                          'set_target_properties(lua_zone PROPERTIES UNITY_BUILD ON UNITY_BUILD_BATCH_SIZE '
                          '8)\n'
                          'target_include_directories(lua_zone PRIVATE ..)\n'
                          '\n'
                          'set(perl_sources\n'
                          '    per',
                          'y(TARGET lua_zone PROPERTY FOLDER libraries)\n'
                          'set_target_properties(lua_zone PROPERTIES UNITY_BUILD OFF UNITY_BUILD_BATCH_SIZE '
                          '8)\n'
                          'target_include_directories(lua_zone PRIVATE ..)\n'
                          '\n'
                          'set(perl_sources\n'
                          '    per'],
                         ['TARGET perl_zone PROPERTY FOLDER libraries)\n'
                          'set_target_properties(perl_zone PROPERTIES UNITY_BUILD ON UNITY_BUILD_BATCH_SIZE '
                          '8)\n'
                          'target_link_libraries(perl_zone PUBLIC cereal::cereal fmt::fmt unofficial',
                          'TARGET perl_zone PROPERTY FOLDER libraries)\n'
                          'set_target_properties(perl_zone PROPERTIES UNITY_BUILD OFF UNITY_BUILD_BATCH_SIZE '
                          '8)\n'
                          'target_link_libraries(perl_zone PUBLIC cereal::cereal fmt::fmt unofficial'],
                         ['tories(gm_commands_zone PRIVATE ..)\n'
                          '\n'
                          'set_target_properties(gm_commands_zone PROPERTIES UNITY_BUILD ON '
                          'UNITY_BUILD_BATCH_SIZE 32)\n'
                          'set_property(TARGET gm_commands_zone PROPERTY FOLDER libraries)\n'
                          '\n'
                          'add_exe',
                          'tories(gm_commands_zone PRIVATE ..)\n'
                          '\n'
                          'set_target_properties(gm_commands_zone PROPERTIES UNITY_BUILD OFF '
                          'UNITY_BUILD_BATCH_SIZE 32)\n'
                          'set_property(TARGET gm_commands_zone PROPERTY FOLDER libraries)\n'
                          '\n'
                          'add_exe']],
 'common/net/crc32.cpp': [['/*\tEQEmu: EQEmulator\n'
                           '\n'
                           '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                           '\n'
                           '\tThis program is free softwar',
                           '#include <cstdint>\n'
                           '/*\tEQEmu: EQEmulator\n'
                           '\n'
                           '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                           '\n'
                           '\tThis program is free softwar']],
 'common/process.h': [['/*\tEQEmu: EQEmulator\n'
                       '\n'
                       '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                       '\n'
                       '\tThis program is free softwar',
                       '#include <string>\n'
                       '/*\tEQEmu: EQEmulator\n'
                       '\n'
                       '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                       '\n'
                       '\tThis program is free softwar']],
 'zone/fastmath.cpp': [['/*\tEQEmu: EQEmulator\n'
                        '\n'
                        '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                        '\n'
                        '\tThis program is free softwar',
                        '#include <cmath>\n'
                        '/*\tEQEmu: EQEmulator\n'
                        '\n'
                        '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                        '\n'
                        '\tThis program is free softwar']],
 'common/json/json_archive_single_line.h': [['AL_ARCHIVES_JSON_SL_HPP_\n'
                                             '\n'
                                             '#include <cereal/cereal.hpp>\n'
                                             '#include <cereal/details/util.hpp>\n'
                                             '#include <cereal/external/rapidjson/prettywriter.h>\n'
                                             '#include <cereal/external/rapidjson/ostreamwrapper.h>\n'
                                             '#include <cereal/external/rapidjson/istreamwrapper.h>\n'
                                             '#include <cereal/external/rapidjson/document.h>\n'
                                             '#include <cereal/external/base64.hpp>\n'
                                             '\n'
                                             '#include <limits>\n'
                                             '#include <sstream>\n'
                                             '#i',
                                             'AL_ARCHIVES_JSON_SL_HPP_\n'
                                             '\n'
                                             '#include <cereal/cereal.hpp>\n'
                                             '#include <cereal/details/util.hpp>\n'
                                             '#include <rapidjson/prettywriter.h>\n'
                                             '#include <rapidjson/ostreamwrapper.h>\n'
                                             '#include <rapidjson/istreamwrapper.h>\n'
                                             '#include <rapidjson/document.h>\n'
                                             '#include <cereal/external/base64.hpp>\n'
                                             '\n'
                                             '#include <limits>\n'
                                             '#include <sstream>\n'
                                             '#i'],
                                            ['ck(); }\n'
                                             '\t\t//! Loads a nullptr from the current node\n'
                                             '\t\tvoid loadValue(std::nullptr_t&)   { search(); '
                                             'CEREAL_RAPIDJSON_ASSERT(itsIteratorStack.back().value().IsNull()); '
                                             '++itsIteratorStack.back(); }\n'
                                             '\n'
                                             '\t\t// Speci',
                                             'ck(); }\n'
                                             '\t\t//! Loads a nullptr from the current node\n'
                                             '\t\tvoid loadValue(std::nullptr_t&)   { search(); '
                                             'RAPIDJSON_ASSERT(itsIteratorStack.back().value().IsNull()); '
                                             '++itsIteratorStack.back(); }\n'
                                             '\n'
                                             '\t\t// Speci']],
 'common/strings.cpp': [[' with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                         '*/\n'
                         '\n'
                         '#include "strings.h"\n'
                         '\n'
                         '#include "cereal/external/rapidjson/document.h"\n'
                         '#include "fmt/format.h"\n'
                         '#include <algorithm>\n'
                         '#include <cctype>\n'
                         '#include <cstdi',
                         ' with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                         '*/\n'
                         '\n'
                         '#include "strings.h"\n'
                         '\n'
                         '#include "rapidjson/document.h"\n'
                         '#include "fmt/format.h"\n'
                         '#include <algorithm>\n'
                         '#include <cctype>\n'
                         '#include <cstdi']],
 'common/database_schema.h': [['/*\tEQEmu: EQEmulator\n'
                               '\n'
                               '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                               '\n'
                               '\tThis program is free softwar',
                               '#include <string>\n'
                               '/*\tEQEmu: EQEmulator\n'
                               '\n'
                               '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                               '\n'
                               '\tThis program is free softwar']],
 'common/event/event_loop.cpp': [['/*\tEQEmu: EQEmulator\n'
                                  '\n'
                                  '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                                  '\n'
                                  '\tThis program is free softwar',
                                  '#include <cstring>\n'
                                  '/*\tEQEmu: EQEmulator\n'
                                  '\n'
                                  '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                                  '\n'
                                  '\tThis program is free softwar']],
 'common/event/timer.cpp': [['/*\tEQEmu: EQEmulator\n'
                             '\n'
                             '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                             '\n'
                             '\tThis program is free softwar',
                             '#include <cstring>\n'
                             '/*\tEQEmu: EQEmulator\n'
                             '\n'
                             '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                             '\n'
                             '\tThis program is free softwar']],
 'zone/lua_ptr.h': [['ng with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                     '*/\n'
                     '#pragma once\n'
                     '\n'
                     '#ifdef LUA_EQEMU\n'
                     '\n'
                     '#include "lua.hpp"\n'
                     '#include "luabind/luabind.hpp"\n'
                     '\n'
                     '#ifndef EQEMU_UNSAFE_LUA\n'
                     '#define Lua_Safe_Call_V',
                     'ng with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                     '*/\n'
                     '#pragma once\n'
                     '\n'
                     '#ifdef LUA_EQEMU\n'
                     '\n'
                     '#include "common/types.h"\n'
                     '#include "lua.hpp"\n'
                     '#include "luabind/luabind.hpp"\n'
                     '\n'
                     '#ifndef EQEMU_UNSAFE_LUA\n'
                     '#define Lua_Safe_Call_V']],
 'zone/lua_mod.h': [['once\n'
                     '\n'
                     '#include "common/repositories/bug_reports_repository.h"\n'
                     '\n'
                     '#include <string>\n'
                     '\n'
                     'struct lua_State;\n'
                     '\n'
                     'class LuaParser;\n'
                     'class LuaMod\n'
                     '{\n'
                     'public:\n'
                     '\tLuaMod(lua_State *ls, LuaParser *lp, const std::string &pa',
                     'once\n'
                     '\n'
                     '#include "common/repositories/bug_reports_repository.h"\n'
                     '\n'
                     '#include <string>\n'
                     '\n'
                     'struct lua_State;\n'
                     '\n'
                     'class Client;\n'
                     'class Mob;\n'
                     'struct DamageHitInfo;\n'
                     'struct ExtraAttackOptions;\n'
                     'class LuaParser;\n'
                     'class LuaMod\n'
                     '{\n'
                     'public:\n'
                     '\tLuaMod(lua_State *ls, LuaParser *lp, const std::string &pa']],
 'zone/quest_interface.h': [['://www.gnu.org/licenses/>.\n'
                             '*/\n'
                             '#pragma once\n'
                             '\n'
                             '#include "common/types.h"\n'
                             '#include "zone/event_codes.h"\n'
                             '\n'
                             '#include <any>\n'
                             '\n'
                             'class Client;\n'
                             'class NPC;\n'
                             '\n'
                             'namespace EQ {\n'
                             '\tclass ItemInstance;\n'
                             '}\n'
                             '\n'
                             'class QuestInterfa',
                             '://www.gnu.org/licenses/>.\n'
                             '*/\n'
                             '#pragma once\n'
                             '\n'
                             '#include "common/types.h"\n'
                             '#include "zone/event_codes.h"\n'
                             '\n'
                             '#include "common/eqemu_logsys.h"\n'
                             '#include "common/rulesys.h"\n'
                             '#include "common/strings.h"\n'
                             '#include <list>\n'
                             '#include <string>\n'
                             '#include <vector>\n'
                             'class Mob;\n'
                             'class Zone;\n'
                             'class Bot;\n'
                             'class Merc;\n'
                             '#include <any>\n'
                             '\n'
                             'class Client;\n'
                             'class NPC;\n'
                             '\n'
                             'namespace EQ {\n'
                             '\tclass ItemInstance;\n'
                             '}\n'
                             '\n'
                             'class QuestInterfa']],
 'zone/command.h': [['/*\tEQEmu: EQEmulator\n'
                     '\n'
                     '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                     '\n'
                     '\tThis program is free softwar',
                     '#include <map>\n'
                     '/*\tEQEmu: EQEmulator\n'
                     '\n'
                     '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                     '\n'
                     '\tThis program is free softwar']],
 'zone/bot_command.h': [['/*\tEQEmu: EQEmulator\n'
                         '\n'
                         '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                         '\n'
                         '\tThis program is free softwar',
                         '#include <map>\n'
                         '/*\tEQEmu: EQEmulator\n'
                         '\n'
                         '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                         '\n'
                         '\tThis program is free softwar'],
                        ['escription of bot command\n'
                         '\tBotCmdFuncPtr function;\t\t// null means perl function\n'
                         '} BotCommandRecord;\n'
                         '\n'
                         'extern int (*bot_command_dispatch)(Client *,char const*);\n'
                         'extern int bot_command_count;\t// number o',
                         'escription of bot command\n'
                         '\tBotCmdFuncPtr function;\t\t// null means perl function\n'
                         '} BotCommandRecord;\n'
                         'extern std::map<std::string, BotCommandRecord *> bot_command_list;\n'
                         'extern std::map<std::string, std::string> bot_command_aliases;\n'
                         '\n'
                         'extern int (*bot_command_dispatch)(Client *,char const*);\n'
                         'extern int bot_command_count;\t// number o']],
 'zone/bot_commands/bot_help.cpp': [['\n'
                                     '\talong with this program. If not, see '
                                     '<http://www.gnu.org/licenses/>.\n'
                                     '*/\n'
                                     '#include "zone/bot_command.h"\n'
                                     '\n'
                                     'void bot_command_help(Client *c, const Seperator *sep)\n'
                                     '{\n'
                                     '\tif (helper_command_alias_fail(c, "bot',
                                     '\n'
                                     '\talong with this program. If not, see '
                                     '<http://www.gnu.org/licenses/>.\n'
                                     '*/\n'
                                     '#include "zone/bot_command.h"\n'
                                     '#include "zone/quest_parser_collection.h"\n'
                                     '\n'
                                     'void bot_command_help(Client *c, const Seperator *sep)\n'
                                     '{\n'
                                     '\tif (helper_command_alias_fail(c, "bot']],
 'zone/bot_commands/bot_inventory.cpp': [['\n'
                                          '\talong with this program. If not, see '
                                          '<http://www.gnu.org/licenses/>.\n'
                                          '*/\n'
                                          '#include "zone/bot_command.h"\n'
                                          '\n'
                                          'void bot_command_inventory(Client *c, const Seperator *sep)\n'
                                          '{\n'
                                          '\tstd::vector<const char*> subcomm',
                                          '\n'
                                          '\talong with this program. If not, see '
                                          '<http://www.gnu.org/licenses/>.\n'
                                          '*/\n'
                                          '#include "zone/bot_command.h"\n'
                                          '#include "zone/quest_parser_collection.h"\n'
                                          '\n'
                                          'void bot_command_inventory(Client *c, const Seperator *sep)\n'
                                          '{\n'
                                          '\tstd::vector<const char*> subcomm']],
 'zone/gm_commands/feature.cpp': [['cense\n'
                                   '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                                   '*/\n'
                                   '#include "zone/client.h"\n'
                                   '\n'
                                   'void command_feature(Client *c, const Seperator *sep)\n'
                                   '{\n'
                                   '\tstd::string command         = sep->arg',
                                   'cense\n'
                                   '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                                   '*/\n'
                                   '#include "zone/client.h"\n'
                                   '#include "zone/command.h"\n'
                                   '\n'
                                   'void command_feature(Client *c, const Seperator *sep)\n'
                                   '{\n'
                                   '\tstd::string command         = sep->arg']],
 'zone/gm_commands/list.cpp': [['icense\n'
                                '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                                '*/\n'
                                '#include "zone/client.h"\n'
                                '#include "zone/command.h"\n'
                                '#include "zone/corpse.h"\n'
                                '#include "zone/doors.h"\n'
                                '#include "zone/objec',
                                'icense\n'
                                '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                                '*/\n'
                                '#include "zone/client.h"\n'
                                '#include "zone/bot.h"\n'
                                '#include "zone/command.h"\n'
                                '#include "zone/corpse.h"\n'
                                '#include "zone/doors.h"\n'
                                '#include "zone/objec']],
 'zone/gm_commands/show/show_content_flags.cpp': [['cense\n'
                                                   '\talong with this program. If not, see '
                                                   '<http://www.gnu.org/licenses/>.\n'
                                                   '*/\n'
                                                   '#include "zone/client.h"\n'
                                                   '#include "zone/dialogue_window.h"\n'
                                                   '\n'
                                                   'void ShowContentFlags(Client *c, const Seperator *sep)\n'
                                                   '{\n'
                                                   '\tCli',
                                                   'cense\n'
                                                   '\talong with this program. If not, see '
                                                   '<http://www.gnu.org/licenses/>.\n'
                                                   '*/\n'
                                                   '#include "zone/client.h"\n'
                                                   '#include '
                                                   '"common/repositories/content_flags_repository.h"\n'
                                                   '#include "zone/dialogue_window.h"\n'
                                                   '\n'
                                                   'void ShowContentFlags(Client *c, const Seperator *sep)\n'
                                                   '{\n'
                                                   '\tCli']],
 'zone/gm_commands/show/show_recipe.cpp': [['ies_repository.h"\n'
                                            '#include "common/repositories/tradeskill_recipe_repository.h"\n'
                                            '#include "zone/client.h"\n'
                                            '#include "zone/command.h"\n'
                                            '\n'
                                            'void ShowRecipe(Client *c, const Seperator *sep)\n'
                                            '{\n'
                                            '\tif (!sep->IsNumb',
                                            'ies_repository.h"\n'
                                            '#include "common/repositories/tradeskill_recipe_repository.h"\n'
                                            '#include "zone/client.h"\n'
                                            '#include "zone/object.h"\n'
                                            '#include "zone/command.h"\n'
                                            '\n'
                                            'void ShowRecipe(Client *c, const Seperator *sep)\n'
                                            '{\n'
                                            '\tif (!sep->IsNumb']],
 'zone/aa.h': [['/*\tEQEmu: EQEmulator\n'
                '\n'
                '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                '\n'
                '\tThis program is free softwar',
                '#include "common/types.h"\n'
                '/*\tEQEmu: EQEmulator\n'
                '\n'
                '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                '\n'
                '\tThis program is free softwar']],
 'zone/dialogue_window.h': [['/*\tEQEmu: EQEmulator\n'
                             '\n'
                             '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                             '\n'
                             '\tThis program is free softwar',
                             '#include "common/types.h"\n'
                             '/*\tEQEmu: EQEmulator\n'
                             '\n'
                             '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                             '\n'
                             '\tThis program is free softwar']],
 'zone/dialogue_window.cpp': [['e\n'
                               '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                               '*/\n'
                               '#include "dialogue_window.h"\n'
                               '\n'
                               'void DialogueWindow::Render(Client *c, std::string markdown)\n'
                               '{\n'
                               '\tstd::string output = markdown;\n',
                               'e\n'
                               '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                               '*/\n'
                               '#include "dialogue_window.h"\n'
                               '#include "zone/client.h"\n'
                               '#include "common/eqemu_logsys.h"\n'
                               '#include "common/strings.h"\n'
                               '\n'
                               'void DialogueWindow::Render(Client *c, std::string markdown)\n'
                               '{\n'
                               '\tstd::string output = markdown;\n']],
 'zone/beacon.cpp': [['\n'
                      '#include "common/races.h"\n'
                      '#include "zone/beacon.h"\n'
                      '#include "zone/entity.h"\n'
                      '#include "zone/mob.h"\n'
                      '\n'
                      'extern EntityList entity_list;\n'
                      'extern Zone* zone;\n'
                      '\n'
                      'class Zone;\n'
                      '\n'
                      "// if lifetime is 0 this is a permanent beacon.. not sure if that'll be\n"
                      '// useful for anything',
                      '\n'
                      '#include "common/races.h"\n'
                      '#include "zone/beacon.h"\n'
                      '#include "zone/entity.h"\n'
                      '#include "zone/mob.h"\n'
                      '\n'
                      'class Zone;\n'
                      '\n'
                      'extern EntityList entity_list;\n'
                      'extern Zone* zone;\n'
                      '\n'
                      "// if lifetime is 0 this is a permanent beacon.. not sure if that'll be\n"
                      '// useful for anything']],
 'zone/guild_mgr.h': [['/*\tEQEmu: EQEmulator\n'
                       '\n'
                       '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                       '\n'
                       '\tThis program is free softwar',
                       '#include <memory>\n'
                       '/*\tEQEmu: EQEmulator\n'
                       '\n'
                       '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                       '\n'
                       '\tThis program is free softwar'],
                      ['ern ZoneDatabase database;\n'
                       '\n'
                       '#define PBUFFER 50\n'
                       '#define MBUFFER 50\n'
                       '\n'
                       'class Client;\n'
                       'class ServerPacket;\n'
                       '\n'
                       'struct GuildBankItems\n'
                       '{\n'
                       '\tstd::map<int32, GuildBankRepository::GuildBank> main_area{};\n'
                       '\tstd::map<in',
                       'ern ZoneDatabase database;\n'
                       '\n'
                       '#define PBUFFER 50\n'
                       '#define MBUFFER 50\n'
                       '\n'
                       'class Client;\n'
                       'class ServerPacket;\n'
                       'namespace EQ { class ItemInstance; }\n'
                       '\n'
                       'struct GuildBankItems\n'
                       '{\n'
                       '\tstd::map<int32, GuildBankRepository::GuildBank> main_area{};\n'
                       '\tstd::map<in']],
 'zone/mob.h': [[' <set>\n'
                 '#include <vector>\n'
                 '\n'
                 'char* strn0cpy(char* dest, const char* source, uint32 size);\n'
                 '\n'
                 'class Client;\n'
                 'class EQApplicationPacket;\n'
                 'class Group;\n'
                 'class NPC;\n'
                 'class Raid;\n'
                 'class Aura;\n'
                 'struct AuraRecord;\n'
                 'stru',
                 ' <set>\n'
                 '#include <vector>\n'
                 '\n'
                 'char* strn0cpy(char* dest, const char* source, uint32 size);\n'
                 '\n'
                 'class Client;\n'
                 'class HealRotation;\n'
                 'class EQApplicationPacket;\n'
                 'class Group;\n'
                 'class NPC;\n'
                 'class Raid;\n'
                 'class Aura;\n'
                 'struct AuraRecord;\n'
                 'stru']],
 'zone/petitions.h': [['/*\tEQEmu: EQEmulator\n'
                       '\n'
                       '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                       '\n'
                       '\tThis program is free softwar',
                       '#include "common/strings.h"\n'
                       '#include <cstring>\n'
                       '/*\tEQEmu: EQEmulator\n'
                       '\n'
                       '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                       '\n'
                       '\tThis program is free softwar']],
 'zone/petitions.cpp': [['License\n'
                         '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                         '*/\n'
                         '#include "petitions.h"\n'
                         '\n'
                         '#include "common/eq_packet_structs.h"\n'
                         '#include "common/eqemu_logsys.h"\n'
                         '#include "common/servert',
                         'License\n'
                         '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                         '*/\n'
                         '#include "petitions.h"\n'
                         '#include "zone/client.h"\n'
                         '#include "common/eq_packet.h"\n'
                         '\n'
                         '#include "common/eq_packet_structs.h"\n'
                         '#include "common/eqemu_logsys.h"\n'
                         '#include "common/servert']],
 'zone/pets.h': [['/*\tEQEmu: EQEmulator\n'
                  '\n'
                  '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                  '\n'
                  '\tThis program is free softwar',
                  '#include "zone/npc.h"\n'
                  '/*\tEQEmu: EQEmulator\n'
                  '\n'
                  '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                  '\n'
                  '\tThis program is free softwar']],
 'zone/qglobals.h': [['/*\tEQEmu: EQEmulator\n'
                      '\n'
                      '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                      '\n'
                      '\tThis program is free softwar',
                      '#include "common/types.h"\n'
                      '#include <string>\n'
                      '/*\tEQEmu: EQEmulator\n'
                      '\n'
                      '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                      '\n'
                      '\tThis program is free softwar']],
 'zone/task_client_state.h': [['e <http://www.gnu.org/licenses/>.\n'
                               '*/\n'
                               '#pragma once\n'
                               '\n'
                               '#include "common/types.h"\n'
                               '#include "zone/tasks.h"\n'
                               '\n'
                               '#include <algorithm>\n'
                               '#include <list>\n'
                               '#include <string>\n'
                               '#include <vector>\n'
                               '\n'
                               'constexpr float MAX_TASK',
                               'e <http://www.gnu.org/licenses/>.\n'
                               '*/\n'
                               '#pragma once\n'
                               '\n'
                               '#include "common/types.h"\n'
                               '#include "zone/tasks.h"\n'
                               '#include <glm/vec4.hpp>\n'
                               'class NPC;\n'
                               'class Corpse;\n'
                               'class Trade;\n'
                               'class DynamicZone;\n'
                               '\n'
                               '#include <algorithm>\n'
                               '#include <list>\n'
                               '#include <string>\n'
                               '#include <vector>\n'
                               '\n'
                               'constexpr float MAX_TASK']],
 'zone/guild_mgr.cpp': [['/*\tEQEmu: EQEmulator\n'
                         '\n'
                         '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                         '\n'
                         '\tThis program is free softwar',
                         '#include "common/misc_functions.h"\n'
                         '/*\tEQEmu: EQEmulator\n'
                         '\n'
                         '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                         '\n'
                         '\tThis program is free softwar']],
 'zone/zone_loot.cpp': [['/*\tEQEmu: EQEmulator\n'
                         '\n'
                         '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                         '\n'
                         '\tThis program is free softwar',
                         '#include "common/content/world_content_service.h"\n'
                         '/*\tEQEmu: EQEmulator\n'
                         '\n'
                         '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                         '\n'
                         '\tThis program is free softwar']],
 'common/repositories/zone_state_spawns_repository.h': [['/*\tEQEmu: EQEmulator\n'
                                                         '\n'
                                                         '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                                                         '\n'
                                                         '\tThis program is free softwar',
                                                         '#include "common/rulesys.h"\n'
                                                         '/*\tEQEmu: EQEmulator\n'
                                                         '\n'
                                                         '\tCopyright (C) 2001-2026 EQEmu Development Team\n'
                                                         '\n'
                                                         '\tThis program is free softwar']],
 'zone/zonedb.cpp': [['ic License\n'
                      '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                      '*/\n'
                      '#include "zonedb.h"\n'
                      '\n'
                      '#include "common/eqemu_logsys.h"\n'
                      '#include "common/extprofile.h"\n'
                      '#include "common/repositories/a',
                      'ic License\n'
                      '\talong with this program. If not, see <http://www.gnu.org/licenses/>.\n'
                      '*/\n'
                      '#include "zonedb.h"\n'
                      '#include "zone/client.h"\n'
                      '#include "zone/zone.h"\n'
                      '\n'
                      '#include "common/eqemu_logsys.h"\n'
                      '#include "common/extprofile.h"\n'
                      '#include "common/repositories/a'],
                     ['y.h"\n'
                      '#include "common/rulesys.h"\n'
                      '#include "common/strings.h"\n'
                      '#include "zone/aura.h"\n'
                      '#include "zone/client.h"\n'
                      '#include "zone/corpse.h"\n'
                      '#include "zone/groups.h"\n'
                      '#include "zone/merc.h"\n'
                      '#include "zone/zone.h"\n'
                      '\n'
                      '#include "fmt/format.h"\n'
                      '#include <ctime>\n'
                      '#include <iostream>\n'
                      '\n'
                      'extern Zone* zone;\n'
                      '\n'
                      'ZoneDatabase ',
                      'y.h"\n'
                      '#include "common/rulesys.h"\n'
                      '#include "common/strings.h"\n'
                      '#include "zone/aura.h"\n'
                      '#include "zone/corpse.h"\n'
                      '#include "zone/groups.h"\n'
                      '#include "zone/merc.h"\n'
                      '\n'
                      '#include "fmt/format.h"\n'
                      '#include <ctime>\n'
                      '#include <iostream>\n'
                      '\n'
                      'extern Zone* zone;\n'
                      '\n'
                      'ZoneDatabase ']]}

SYSTEM_SHIM = '# Qualified Traditional Bookworm system-dependency recipe.\nfind_package(Boost REQUIRED)\nforeach(component dynamic_bitset foreach tuple)\n  if(NOT TARGET Boost::${component})\n    add_library(Boost::${component} INTERFACE IMPORTED)\n    set_target_properties(Boost::${component} PROPERTIES\n      INTERFACE_INCLUDE_DIRECTORIES "${Boost_INCLUDE_DIRS}")\n  endif()\nendforeach()\nfind_package(cereal CONFIG REQUIRED)\nfind_package(fmt CONFIG REQUIRED)\nfind_package(glm CONFIG REQUIRED)\nfind_package(PkgConfig REQUIRED)\npkg_check_modules(MARIADB REQUIRED IMPORTED_TARGET libmariadb)\nadd_library(unofficial::libmariadb ALIAS PkgConfig::MARIADB)\npkg_check_modules(UV REQUIRED IMPORTED_TARGET libuv)\nadd_library(libuv::uv ALIAS PkgConfig::UV)\npkg_check_modules(SODIUM REQUIRED IMPORTED_TARGET libsodium)\nadd_library(unofficial-sodium::sodium ALIAS PkgConfig::SODIUM)\nfind_package(OpenSSL 3 REQUIRED)\nfind_package(ZLIB REQUIRED)\nfind_package(LuaJit REQUIRED)\nfind_package(PerlLibs REQUIRED)\nfind_path(TRASC_DETOUR_INCLUDE_DIR DetourNavMesh.h PATH_SUFFIXES recastnavigation REQUIRED)\nfind_library(TRASC_DETOUR_LIBRARY Detour REQUIRED)\nadd_library(RecastNavigation::Detour UNKNOWN IMPORTED)\nset_target_properties(RecastNavigation::Detour PROPERTIES\n  IMPORTED_LOCATION "${TRASC_DETOUR_LIBRARY}"\n  INTERFACE_INCLUDE_DIRECTORIES "${TRASC_DETOUR_INCLUDE_DIR}")\nfind_path(TRASC_WEBSOCKETPP_INCLUDE_DIR websocketpp/config/core.hpp REQUIRED)\n'


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _regular(path, directory=False):
    info = Path(path).lstat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError('Traditional build requires ordinary files and directories: ' + str(path))
    return info


def _confined(engine, path):
    """Reject links in every path component, including links within /work."""
    path = Path(path)
    try:
        parts = path.relative_to(engine.work).parts
    except ValueError:
        raise ValueError('Traditional build path escapes this profile') from None
    _regular(engine.work, True)
    parent = engine.work
    for part in parts:
        if part in ('', '.', '..'):
            raise ValueError('Invalid Traditional build path')
        parent /= part
        if parent.exists() or parent.is_symlink():
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise ValueError('Traditional build path contains a symlink: ' + str(parent))
    return path


def _mkdir(engine, path):
    path = _confined(engine, path)
    path.mkdir(parents=True, exist_ok=True)
    _regular(path, True)
    return path


def _remove(engine, path):
    path = _confined(engine, path)
    if path.exists():
        _regular(path, True)
        shutil.rmtree(path)


def _read(path, limit=MAX_FILE_BYTES, check=lambda: None):
    info = _regular(path)
    if info.st_size > limit:
        raise ValueError('Traditional input exceeds its file-size limit: ' + str(path))
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('Traditional input changed while opening it')
        blocks, count = [], 0
        while True:
            check()
            block = stream.read(1024**2)
            if not block:
                break
            count += len(block)
            if count > limit:
                raise ValueError('Traditional input exceeds its file-size limit')
            blocks.append(block)
        after = os.fstat(stream.fileno())
        if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or count != opened.st_size:
            raise ValueError('Traditional input changed while reading it')
    return b''.join(blocks)


def _sha(path, check=lambda: None, limit=MAX_FILE_BYTES):
    return hashlib.sha256(_read(path, limit, check)).hexdigest()


def _json(path, limit=2 * 1024**2):
    value = json.loads(_read(path, limit).decode('utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Invalid Traditional build receipt')
    return value


def _atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.new-' + secrets.token_hex(8))
    try:
        with temporary.open('xb') as stream:
            stream.write(_canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _recipe_identity():
    helper = Path(__file__).with_name('traditional_verify.py')
    return _digest({'recipe': RECIPE, 'adapter': _sha(Path(__file__)), 'verifier': _sha(helper),
                    'websocket': WEBSOCKET_TREE_SHA256})


def _guard_source(engine):
    if engine.profile != 'traditional':
        raise ValueError('This build recipe belongs to the Traditional profile')
    root = _confined(engine, engine.source_root())
    if root != engine.work / 'sources/current':
        raise ValueError('Import the selected Traditional server source tree')
    _regular(root, True)
    marker = root / 'trasc-source.json'
    provenance = _json(marker, 64 * 1024)
    imported = provenance.get('imported')
    if not isinstance(imported, (int, float)) or isinstance(imported, bool) or not 0 < imported < 10**12:
        raise ValueError('Reimport the Traditional source to record its provenance')
    if not re.fullmatch(r'[0-9a-f]{64}', str(provenance.get('archive_sha256', ''))):
        raise ValueError('Reimport the Traditional source to record its archive SHA256')
    kind = provenance.get('type')
    if kind == 'github':
        if str(provenance.get('repo', '')).rstrip('/').removesuffix('.git').lower() != REPOSITORY.lower() or provenance.get('commit') != REVISION:
            raise ValueError('Pull ' + REPOSITORY + ' at the qualified commit ' + REVISION)
    elif kind != 'archive':
        raise ValueError('Unrecognized Traditional source provenance')
    # Whitelist fields; imports cannot inject paths or command arguments here.
    provenance = {key: provenance[key] for key in ('type', 'imported', 'archive_sha256', 'repo', 'ref', 'commit') if key in provenance}
    hashes = {}
    for name, expected in SOURCE_HASHES.items():
        path = _confined(engine, root / name)
        hashes[name] = _sha(path, limit=4 * 1024**2)
        if hashes[name] != expected:
            raise ValueError('Traditional source is not qualified for ' + RECIPE + ': ' + name)
    identity = _digest({'provenance': provenance, 'critical': hashes, 'recipe': _recipe_identity()})
    return root, provenance, identity


def _inventory(root, check=lambda: None, source=False, maximum_files=MAX_SOURCE_FILES, maximum_bytes=MAX_SOURCE_BYTES, contents=True):
    """Bounded sorted inventory. No source/header symlink is ever followed."""
    root = Path(root)
    _regular(root, True)
    entries, total = {}, 0
    def walk(directory, prefix=''):
        nonlocal total
        check()
        with os.scandir(directory) as stream:
            children = sorted(stream, key=lambda entry: entry.name)
        for child in children:
            check()
            name = prefix + child.name
            if '\\' in name or '\x00' in name or '\n' in name or '\r' in name:
                raise ValueError('Invalid Traditional source filename')
            info = child.stat(follow_symlinks=False)
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError('Traditional source contains a symlink or special file: ' + name)
            if child.name == '.git' or (source and (name in ('submodules/vcpkg', 'submodules/websocketpp', 'trasc-source.json'))):
                continue
            if stat.S_ISDIR(info.st_mode):
                walk(Path(child.path), name + '/')
                continue
            if info.st_size > MAX_FILE_BYTES:
                raise ValueError('Traditional source exceeds its file-size limit')
            total += info.st_size
            if total > maximum_bytes or len(entries) >= maximum_files:
                raise ValueError('Traditional source exceeds its supported size')
            if contents:
                entries[name] = {'bytes': info.st_size, 'sha256': _sha(child.path, check)}
            else:
                entries[name] = {'bytes': info.st_size, 'stat': (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)}
    walk(root)
    if not entries:
        raise ValueError('Traditional source tree is empty')
    return dict(sorted(entries.items()))


def _tree_sha(entries):
    digest = hashlib.sha256()
    for name, item in sorted(entries.items()):
        digest.update(name.encode() + b'\0' + str(item['bytes']).encode() + b'\0' + item['sha256'].encode() + b'\n')
    return digest.hexdigest()


def _source_sha_cached(engine, root):
    signature = _digest(_inventory(root, source=True, contents=False))
    cached = getattr(engine, '_traditional_source_cache', None)
    if cached and cached[0] == signature:
        return cached[1]
    fingerprint = _tree_sha(_inventory(root, source=True))
    if _digest(_inventory(root, source=True, contents=False)) != signature:
        raise ValueError('Traditional source changed during staged-build qualification')
    engine._traditional_source_cache = (signature, fingerprint)
    return fingerprint


def _copy_tree(engine, root, destination, entries):
    _mkdir(engine, destination)
    for name, expected in entries.items():
        engine.check_cancel()
        source = _confined(engine, Path(root) / name)
        data = _read(source, check=engine.check_cancel)
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError('Traditional source changed while preparing the overlay')
        target = _confined(engine, Path(destination) / name)
        _mkdir(engine, target.parent)
        with target.open('xb') as stream:
            stream.write(data)
        target.chmod(0o755 if _regular(source).st_mode & 0o111 else 0o644)


def _patch_outputs(root):
    # Compute every result before writing the first one. The caller also checks
    # all full-file SHA guards before it copies the pristine source.
    outputs = {}
    for name, edits in SOURCE_PATCHES.items():
        text = _read(Path(root) / name, 4 * 1024**2).decode('utf-8')
        for before, after in edits:
            if text.count(before) != 1:
                raise ValueError('Traditional source patch anchor changed: ' + name)
            text = text.replace(before, after, 1)
        outputs[name] = text
    return outputs


def _apply_patches(root):
    outputs = _patch_outputs(root)
    for name, text in outputs.items():
        (Path(root) / name).write_text(text, encoding='utf-8')
    shim = Path(root) / 'cmake/trasc-system-dependencies.cmake'
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(SYSTEM_SHIM, encoding='utf-8')


def _expected_overlay(root, entries):
    expected = dict(entries)
    for name, text in _patch_outputs(root).items():
        data = text.encode('utf-8')
        expected[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    data = SYSTEM_SHIM.encode('utf-8')
    expected['cmake/trasc-system-dependencies.cmake'] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    return expected


def _overlay_valid(actual, expected):
    prefix = 'submodules/websocketpp/'
    websocket = {name[len(prefix):]: item for name, item in actual.items() if name.startswith(prefix)}
    ordinary = {name: item for name, item in actual.items() if not name.startswith(prefix)}
    return (ordinary == expected and len(websocket) == WEBSOCKET_FILES
            and sum(item['bytes'] for item in websocket.values()) == WEBSOCKET_BYTES
            and _tree_sha(websocket) == WEBSOCKET_TREE_SHA256
            and 'websocketpp/config/core.hpp' in websocket and 'websocketpp/server.hpp' in websocket)


def _qualified_websocket(root, check=lambda: None):
    entries = _inventory(root, check, maximum_files=WEBSOCKET_FILES, maximum_bytes=WEBSOCKET_BYTES)
    if (len(entries) != WEBSOCKET_FILES or sum(item['bytes'] for item in entries.values()) != WEBSOCKET_BYTES
            or _tree_sha(entries) != WEBSOCKET_TREE_SHA256
            or 'websocketpp/config/core.hpp' not in entries or 'websocketpp/server.hpp' not in entries):
        raise ValueError('The pinned websocketpp tree does not match its qualified SHA256')
    return entries


def _fetch_websocket(engine, archive):
    """The only network hydration supported by this recipe; bound even chunked responses."""
    temporary = archive.with_name(archive.name + '.part')
    try:
        request = urllib.request.Request(WEBSOCKET_URL, headers={'User-Agent': 'TRASC-Traditional/1'})
        with urllib.request.urlopen(request, timeout=30) as response, temporary.open('xb') as stream:
            if response.url != WEBSOCKET_URL:
                raise ValueError('Unexpected pinned websocketpp download redirect')
            declared = int(response.headers.get('Content-Length', '0'))
            if declared > MAX_WEBSOCKET_DOWNLOAD:
                raise ValueError('Pinned websocketpp download exceeds its size limit')
            size = 0
            while True:
                engine.check_cancel()
                block = response.read(min(1024**2, MAX_WEBSOCKET_DOWNLOAD - size + 1))
                if not block:
                    break
                size += len(block)
                if size > MAX_WEBSOCKET_DOWNLOAD:
                    raise ValueError('Pinned websocketpp download exceeds its size limit')
                stream.write(block)
        engine.check_cancel()
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)


def _extract_websocket(engine, archive, destination):
    wrapper = 'websocketpp-' + WEBSOCKET_REVISION
    _mkdir(engine, destination)
    seen, count, total = set(), 0, 0
    with tarfile.open(archive, 'r:gz') as stream:
        for member in stream:
            engine.check_cancel()
            name = member.name.rstrip('/')
            parts = PurePosixPath(name).parts
            if (not parts or parts[0] != wrapper or '..' in parts or '\\' in name or '\x00' in name
                    or PurePosixPath(name).is_absolute() or not (member.isfile() or member.isdir())):
                raise ValueError('Invalid pinned websocketpp archive member')
            if name in seen:
                raise ValueError('Duplicate pinned websocketpp archive member')
            seen.add(name)
            if len(seen) > 600:
                raise ValueError('Pinned websocketpp archive has too many entries')
            if len(parts) == 1:
                if not member.isdir():
                    raise ValueError('Invalid pinned websocketpp archive wrapper')
                continue
            relative = '/'.join(parts[1:])
            if '.git' in parts:
                raise ValueError('Pinned websocketpp archive contains unexpected Git metadata')
            target = _confined(engine, destination / relative)
            if member.isdir():
                _mkdir(engine, target)
                continue
            count += 1
            total += member.size
            if member.size < 0 or count > WEBSOCKET_FILES or total > WEBSOCKET_BYTES:
                raise ValueError('Pinned websocketpp archive exceeds its expanded size limit')
            _mkdir(engine, target.parent)
            extracted = stream.extractfile(member)
            if extracted is None:
                raise ValueError('Incomplete pinned websocketpp archive')
            with extracted, target.open('xb') as output:
                remaining = member.size
                while remaining:
                    engine.check_cancel()
                    data = extracted.read(min(1024**2, remaining))
                    if not data:
                        raise ValueError('Truncated pinned websocketpp archive')
                    remaining -= len(data)
                    output.write(data)
            target.chmod(0o644)
    _qualified_websocket(destination, engine.check_cancel)


def _hydrate_websocket(engine, original, overlay, base):
    destination = overlay / 'submodules/websocketpp'
    imported = original / 'submodules/websocketpp'
    try:
        _confined(engine, imported)
        entries = _qualified_websocket(imported, engine.check_cancel)
    except (OSError, ValueError):
        engine.check_cancel()
        entries = None
    if entries is not None:
        _copy_tree(engine, imported, destination, entries)
        return
    archive = base / ('websocket-' + secrets.token_hex(8) + '.tar.gz')
    try:
        engine.log('Fetching the qualified websocketpp dependency at ' + WEBSOCKET_REVISION)
        _fetch_websocket(engine, archive)
        _extract_websocket(engine, archive, destination)
    finally:
        archive.unlink(missing_ok=True)


def _tool(args):
    env = {key: value for key, value in os.environ.items() if not key.startswith(('LD_', 'OPENSSL_', 'CMAKE_')) and key not in ('CC', 'CXX', 'CPATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'PKG_CONFIG_PATH')}
    env['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=15, env=env, text=True)
    if result.returncode:
        raise ValueError('Traditional runtime prerequisite failed: ' + args[0])
    if len(result.stdout) > 256 * 1024:
        raise ValueError('Traditional runtime prerequisite returned too much output')
    return result.stdout.strip()


def _runtime(engine):
    """Read-only, cached qualification. Never apt-install or hydrate from status."""
    marker_sha = None
    try:
        marker = _read(RUNTIME_MARKER, 64 * 1024)
        marker_sha = hashlib.sha256(marker).hexdigest()
        marker_content_sha = marker_sha
        tracked = ('/usr/bin/g++', '/usr/bin/cmake', '/usr/bin/pkg-config', '/usr/bin/perl', '/usr/bin/openssl',
                   '/usr/lib/aarch64-linux-gnu/libcrypto.so.3', '/usr/lib/aarch64-linux-gnu/ossl-modules/legacy.so',
                   '/usr/lib/aarch64-linux-gnu/libluajit-5.1.so.2', '/usr/lib/aarch64-linux-gnu/libperl.so.5.36',
                   '/var/lib/dpkg/status', '/usr/include/boost/version.hpp', '/usr/include/cereal/cereal.hpp',
                   '/usr/include/rapidjson/document.h', '/usr/include/fmt/format.h', '/usr/include/glm/glm.hpp',
                   '/usr/include/luajit-2.1/lua.h', '/usr/include/recastnavigation/DetourNavMesh.h', '/usr/include/uv.h',
                   '/usr/include/mariadb/mysql.h', '/usr/include/openssl/evp.h', '/usr/include/sodium.h', '/usr/include/zlib.h')
        metadata = []
        for path in tracked:
            try:
                info = Path(path).stat()
                metadata.append((path, info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns))
            except FileNotFoundError:
                metadata.append((path, None))
        marker_sha = _digest({'marker_sha256': marker_sha, 'runtime_files': metadata})
        cached = getattr(engine, '_traditional_runtime_cache', None)
        if cached and cached['marker_sha256'] == marker_sha:
            return cached['result']
        value = json.loads(marker)
        if (not isinstance(value, dict) or value.get('format') != 1 or value.get('architecture') != 'arm64'
                or value.get('profile') != 'traditional' or value.get('runtime') != 'traditional-1.0' or value.get('build_adapter') != 1):
            raise ValueError('Install the Traditional 1.0 build runtime; the existing runtime supports preparation only')
        if _tool(['/usr/bin/uname', '-m']) != 'aarch64' or 'aarch64' not in _tool(['/usr/bin/g++', '-dumpmachine']):
            raise ValueError('Traditional compilation requires the app-owned ARM64 runtime')
        compiler = _tool(['/usr/bin/g++', '-dumpfullversion'])
        if not re.match(r'^12\.', compiler):
            raise ValueError('Traditional 1.0 requires its qualified Bookworm GCC 12 toolchain')
        headers = ('boost/version.hpp', 'cereal/cereal.hpp', 'rapidjson/document.h', 'fmt/format.h', 'glm/glm.hpp',
                   'luajit-2.1/lua.h', 'recastnavigation/DetourNavMesh.h', 'uv.h', 'mariadb/mysql.h',
                   'openssl/evp.h', 'sodium.h', 'zlib.h')
        for name in headers:
            if not (Path('/usr/include') / name).is_file():
                raise ValueError('Traditional build runtime is missing ' + name)
        for name in ('ninja', 'pkg-config', 'readelf', 'ldd', 'python3', 'perl', 'openssl'):
            if not Path('/usr/bin', name).is_file():
                raise ValueError('Traditional build runtime is missing ' + name)
        cmake = _tool(['/usr/bin/cmake', '--version']).splitlines()[0]
        if not re.match(r'cmake version 3\.25\.', cmake):
            raise ValueError('Traditional 1.0 requires its qualified Bookworm CMake 3.25 toolchain')
        pkg = _tool(['/usr/bin/pkg-config', '--modversion', 'libmariadb', 'libuv', 'libsodium', 'openssl', 'luajit', 'zlib'])
        providers = _tool(['/usr/bin/openssl', 'list', '-providers', '-provider', 'default', '-provider', 'legacy'])
        ciphers = _tool(['/usr/bin/openssl', 'list', '-cipher-algorithms', '-provider', 'default', '-provider', 'legacy'])
        if not all(re.search(r'^\s*' + name + r'\s*$', providers, re.M) for name in ('default', 'legacy')) or 'DES-CBC' not in ciphers:
            raise ValueError('Traditional build runtime needs OpenSSL 3 default and legacy DES providers')
        packages = _tool(['/usr/bin/dpkg-query', '-W', '-f=${Package}=${Version}\n', 'g++', 'cmake', 'ninja-build', 'libboost-dev',
                          'libcereal-dev', 'rapidjson-dev', 'libfmt-dev', 'libglm-dev', 'libluajit-5.1-dev', 'librecast-dev',
                          'libuv1-dev', 'libmariadb-dev', 'libssl-dev', 'libsodium-dev', 'zlib1g-dev', 'libperl-dev'])
        result = {'ready': True, 'message': 'Traditional ARM64 build runtime is qualified',
                  'identity': _digest({'marker': marker_content_sha, 'compiler': compiler, 'cmake': cmake, 'packages': packages, 'pkg': pkg})}
        engine._traditional_runtime_cache = {'marker_sha256': marker_sha, 'result': result}
        return result
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result = {'ready': False, 'message': str(error), 'identity': None}
        if marker_sha:
            engine._traditional_runtime_cache = {'marker_sha256': marker_sha, 'result': result}
        return result


def _prepare_overlay(engine, root, provenance, source_identity, entries, runtime_identity):
    base = _mkdir(engine, engine.work / 'builds/traditional')
    source, receipt = base / 'source', base / 'overlay-receipt.json'
    identity = _digest({'source': source_identity, 'inputs': _tree_sha(entries), 'runtime': runtime_identity,
                        'recipe': _recipe_identity(), 'source_location': str(source), 'objects_location': str(base / 'objects')})
    expected = _expected_overlay(root, entries)
    try:
        stored = _json(_confined(engine, receipt))
        if stored.get('format') == 1 and stored.get('identity') == identity:
            _confined(engine, source)
            actual = _inventory(source, engine.check_cancel)
            if _tree_sha(actual) == stored.get('overlay_sha256') and _overlay_valid(actual, expected):
                engine.log('Reusing the verified Traditional build overlay')
                return source, identity
    except (OSError, ValueError):
        engine.check_cancel()
    temporary = base / ('source-preparing-' + secrets.token_hex(8))
    try:
        engine.log('Preparing the pristine Traditional source overlay')
        _copy_tree(engine, root, temporary, entries)
        # Recheck copied critical bytes before the first guarded edit.
        for name, guard_sha in SOURCE_HASHES.items():
            engine.check_cancel()
            if _sha(temporary / name) != guard_sha:
                raise ValueError('Traditional source changed before applying its build recipe: ' + name)
        _apply_patches(temporary)
        _hydrate_websocket(engine, root, temporary, base)
        actual = _inventory(temporary, engine.check_cancel)
        if not _overlay_valid(actual, expected):
            raise ValueError('Traditional patched overlay failed its complete expected-input validation')
        overlay_sha = _tree_sha(actual)
        engine.check_cancel()
        _remove(engine, base / 'objects')
        _remove(engine, source)
        os.replace(temporary, source)
        _atomic_json(receipt, {'format': 1, 'recipe': RECIPE, 'identity': identity,
                              'overlay_sha256': overlay_sha, 'source': provenance, 'created': time.time()})
        return source, identity
    finally:
        _remove(engine, temporary)


def _elf(path):
    _regular(path)
    with Path(path).open('rb') as stream:
        header = stream.read(20)
    if len(header) != 20 or header[:4] != b'\x7fELF' or header[4:6] != b'\x02\x01' or int.from_bytes(header[18:20], 'little') != 183:
        raise ValueError('Traditional staged binary is not an ARM64 little-endian ELF: ' + Path(path).name)


def _verification(report, stage, check=lambda: None):
    if (report.get('format') != 1 or report.get('architecture') != 'arm64'
            or set(report.get('binaries', {})) != set(BINARIES)
            or report.get('providers') != {'default': True, 'legacy': True, 'des_cbc': True}):
        raise ValueError('Incomplete Traditional binary verification report')
    abi = report.get('abi_libraries', {})
    zone, login = abi.get('zone', {}), abi.get('loginserver', {})
    if (zone.get('luajit') != 'libluajit-5.1.so.2' or not re.fullmatch(r'libperl\.so\.5\.[0-9]+', str(zone.get('perl', '')))
            or login.get('crypto') != 'libcrypto.so.3'):
        raise ValueError('Traditional binaries lack the qualified quest/login runtime ABI')
    for name in BINARIES:
        check()
        info = report['binaries'][name]
        if (not isinstance(info, dict) or info.get('architecture') != 'arm64'
                or info.get('interpreter') != '/lib/ld-linux-aarch64.so.1'
                or info.get('loader_dependencies') != 'resolved'
                or not isinstance(info.get('bytes'), int) or isinstance(info.get('bytes'), bool)
                or not 20 <= info['bytes'] <= 1024**3
                or not re.fullmatch(r'[0-9a-f]{64}', str(info.get('sha256', '')))):
            raise ValueError('Invalid Traditional binary verification: ' + name)
        path = Path(stage) / name
        _elf(path)
        if _regular(path).st_size != info['bytes'] or _sha(path, check, 1024**3) != info['sha256']:
            raise ValueError('Traditional staged binary changed after verification: ' + name)


def _stat_signature(path):
    value = _regular(path)
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _staged(engine, source_identity, runtime_identity):
    stage = _confined(engine, engine.work / 'server/bin.staged')
    try:
        _regular(stage, True)
        info_path, report_path = stage / 'build-info.json', stage / 'verification.json'
        info, report = _json(info_path), _json(report_path)
        if (info.get('format') != 1 or info.get('recipe') != RECIPE or info.get('recipe_identity') != _recipe_identity()
                or info.get('source_identity') != source_identity or info.get('runtime_identity') != runtime_identity
                or info.get('verification_sha256') != _digest(report) or info.get('compile_only') is not True):
            return False, 'The staged Traditional build belongs to an earlier source or runtime; build again'
        root = _confined(engine, engine.source_root())
        if info.get('input_sha256') != _source_sha_cached(engine, root):
            return False, 'The Traditional source changed since compilation; the previous staged build is preserved'
        signature = (_stat_signature(info_path), _stat_signature(report_path),
                     tuple((name, _stat_signature(stage / name)) for name in BINARIES), source_identity, runtime_identity)
        cached = getattr(engine, '_traditional_stage_cache', None)
        if cached and cached[0] == signature:
            return cached[1]
        _verification(report, stage)
        result = (True, 'Nine Traditional ARM64 binaries compiled and staged; deployment is the next milestone')
        engine._traditional_stage_cache = (signature, result)
        return result
    except (OSError, ValueError, KeyError, TypeError) as error:
        return False, 'No verified Traditional staged build: ' + str(error)


def status(engine):
    supported, source_message, identity = False, 'Pull the qualified Traditional source first', None
    try:
        _, provenance, identity = _guard_source(engine)
        supported = True
        source_message = ('Qualified GitHub source' if provenance['type'] == 'github' else 'Recipe-matched source archive') + ' at ' + REVISION
    except (OSError, ValueError, KeyError, TypeError) as error:
        source_message = str(error)
    runtime = _runtime(engine)
    staged_valid, staged_message = False, 'Compile the Traditional source to stage its nine binaries'
    if supported and runtime['ready']:
        staged_valid, staged_message = _staged(engine, identity, runtime['identity'])
    elif (engine.work / 'server/bin.staged').exists():
        staged_message = 'The previous staged build is preserved; qualify this source and runtime before using it'
    recovery = getattr(engine, 'traditional_recovery_error', '')
    return {'recipe': RECIPE, 'source_supported': supported, 'source_message': source_message,
            'runtime_ready': runtime['ready'], 'runtime_message': str(recovery) if recovery else runtime['message'],
            'build_allowed': supported and runtime['ready'] and not recovery, 'staged_valid': staged_valid,
            'staged_message': staged_message, 'compile_only': True}


def _promote_stage(engine, stage):
    current = _confined(engine, engine.work / 'server/bin.staged')
    previous = _confined(engine, engine.work / 'server/bin.traditional-previous')
    journal = _confined(engine, engine.work / 'run/traditional-stage.json')
    _remove(engine, previous)
    existed = current.exists()
    if existed:
        _regular(current, True)
    _atomic_json(journal, {'format': 1, 'recipe': RECIPE, 'stage': stage.name, 'previous': existed})
    try:
        if existed:
            os.replace(current, previous)
        os.replace(stage, current)
        journal.unlink()
    except BaseException:
        if previous.exists():
            if current.exists():
                os.replace(current, stage)
            os.replace(previous, current)
        elif not existed and current.exists() and not stage.exists():
            os.replace(current, stage)
        journal.unlink(missing_ok=True)
        raise
    try:
        _remove(engine, previous)
    except OSError as error:
        engine.log('Traditional build staged; obsolete previous-stage cleanup will retry on restart: ' + str(error))
    engine._traditional_stage_cache = None


def recover(engine):
    """Restore an interrupted stage replacement before the control service opens."""
    if engine.profile != 'traditional':
        return
    current = _confined(engine, engine.work / 'server/bin.staged')
    previous = _confined(engine, engine.work / 'server/bin.traditional-previous')
    journal = _confined(engine, engine.work / 'run/traditional-stage.json')
    if journal.exists():
        value = _json(journal, 16 * 1024)
        name = value.get('stage', '')
        if (value.get('format') != 1 or value.get('recipe') != RECIPE or not isinstance(value.get('previous'), bool)
                or not re.fullmatch(r'bin\.traditional-preparing-[0-9a-f]{16}', str(name))):
            raise ValueError('Invalid Traditional stage recovery journal; preserve this workspace for repair')
        temporary = _confined(engine, engine.work / 'server' / name)
        if previous.exists():
            _remove(engine, current)
            _regular(previous, True)
            os.replace(previous, current)
        elif value['previous'] and not current.exists():
            raise ValueError('Traditional stage recovery cannot locate the previous binaries')
        elif not value['previous'] and current.exists() and temporary.exists():
            raise ValueError('Ambiguous Traditional stage recovery state')
        _remove(engine, temporary)
        journal.unlink()
    elif previous.exists():
        if current.exists():
            _remove(engine, previous)
        else:
            _regular(previous, True)
            os.replace(previous, current)
    for parent, pattern in ((engine.work / 'server', r'bin\.traditional-preparing-[0-9a-f]{16}'),
                            (engine.work / 'builds/traditional', r'source-preparing-[0-9a-f]{16}')):
        parent = _confined(engine, parent)
        if parent.exists():
            _regular(parent, True)
            for child in parent.iterdir():
                if re.fullmatch(pattern, child.name):
                    _remove(engine, child)
    engine._traditional_stage_cache = None


def _cmake(engine, args, timeout):
    # The app's rootfs is fixed, but explicitly neutralize inherited compiler,
    # toolchain and search overrides so retrying cannot select a stale vcpkg/NDK.
    unset = ('CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS', 'CMAKE_TOOLCHAIN_FILE', 'CMAKE_PREFIX_PATH', 'CPATH', 'CPLUS_INCLUDE_PATH',
             'LIBRARY_PATH', 'PKG_CONFIG_PATH', 'PKG_CONFIG_SYSROOT_DIR', 'PKG_CONFIG_LIBDIR', 'VCPKG_ROOT', 'LD_LIBRARY_PATH', 'LD_PRELOAD')
    engine.run(['/usr/bin/env', *[part for name in unset for part in ('-u', name)], '/usr/bin/cmake', *args], timeout=timeout)


def _memory_jobs(jobs):
    try:
        with MEMORY_INFO.open() as stream:
            data = stream.read(64 * 1024 + 1)
        if len(data) > 64 * 1024:
            raise ValueError('Invalid runtime memory information')
        match = re.search(r'^MemAvailable:\s+([0-9]+) kB\s*$', data, re.M)
        if not match:
            raise ValueError('Runtime memory availability is unknown')
        available = int(match.group(1)) * 1024
    except (OSError, ValueError):
        if jobs == 2:
            raise ValueError('Choose 1 Traditional build job when available memory cannot be measured') from None
        return
    required = (3 if jobs == 1 else 6) * 1024**3
    if available < required:
        if jobs == 2:
            raise ValueError('Two Traditional build jobs need at least 6 GiB available RAM; choose 1 job')
        raise ValueError('Traditional compilation needs at least 3 GiB available RAM; close the game/client and other apps first')


def build(engine, args):
    recover(engine)
    engine.traditional_recovery_error = ''
    root, provenance, source_identity = _guard_source(engine)
    if hasattr(engine, '_traditional_runtime_cache'):
        del engine._traditional_runtime_cache
    runtime = _runtime(engine)
    if not runtime['ready']:
        raise ValueError(runtime['message'])
    jobs = args.get('jobs', 1)
    if isinstance(jobs, bool) or not re.fullmatch(r'[12]', str(jobs)):
        raise ValueError('Choose 1 or 2 Traditional build jobs; 1 is recommended for this device')
    jobs = int(jobs)
    _memory_jobs(jobs)
    engine.check_cancel()
    base = _mkdir(engine, engine.work / 'builds/traditional')
    if shutil.disk_usage(base).free < MIN_FREE:
        raise ValueError('Keep at least 3 GiB free before compiling the Traditional server')
    engine.log('Fingerprinting the complete Traditional source before compilation')
    entries = _inventory(root, engine.check_cancel, source=True)
    input_sha = _tree_sha(entries)
    overlay, build_identity = _prepare_overlay(engine, root, provenance, source_identity, entries, runtime['identity'])
    objects = _mkdir(engine, base / 'objects')
    stage = engine.work / 'server' / ('bin.traditional-preparing-' + secrets.token_hex(8))
    evidence = base / ('evidence-preparing-' + secrets.token_hex(8))
    _mkdir(engine, evidence)
    try:
        engine.log('Configuring Traditional ARM64 with LuaJIT, Perl and both client-file utilities')
        _cmake(engine, ['-S', str(overlay), '-B', str(objects), '-G', 'Ninja',
                       '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_COMPILER=/usr/bin/g++', '-DCMAKE_C_COMPILER=/usr/bin/gcc',
                       '-DCMAKE_TOOLCHAIN_FILE=', '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG -fno-strict-aliasing',
                       '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', '-DEQEMU_USE_SYSTEM_DEPENDENCIES=ON',
                       '-DTRASC_WEBSOCKETPP_INCLUDE_DIR=' + str(overlay / 'submodules/websocketpp'),
                       '-DLUAJIT_INCLUDE_DIR=/usr/include/luajit-2.1', '-DLUAJIT_LIBRARY=/usr/lib/aarch64-linux-gnu/libluajit-5.1.so',
                       '-DEQEMU_BUILD_PCH=ON', '-DEQEMU_BUILD_SERVER=ON', '-DEQEMU_BUILD_LOGIN=ON',
                       '-DEQEMU_BUILD_CLIENT_FILES=ON', '-DEQEMU_BUILD_PERL=ON', '-DEQEMU_BUILD_LUA=ON',
                       '-DEQEMU_BUILD_TESTS=OFF', '-DEQEMU_ADD_PROFILER=OFF'], 600)
        _cmake(engine, ['--build', str(objects), '--parallel', str(jobs), '--target', *BINARIES], 24 * 3600)
        engine.check_cancel()
        _mkdir(engine, stage)
        for name in BINARIES:
            source = _confined(engine, objects / 'bin' / name)
            _elf(source)
            data = _read(source, 1024**3, engine.check_cancel)
            target = stage / name
            with target.open('xb') as stream:
                stream.write(data)
            target.chmod(0o755)
        engine.log('Validating all nine ARM64 executables, dynamic loader and OpenSSL providers')
        helper = Path(__file__).with_name('traditional_verify.py')
        engine.run([sys.executable, str(helper), str(stage), str(evidence)], timeout=180)
        report = _json(evidence / 'binary-verification.json')
        _verification(report, stage, engine.check_cancel)
        # A source import/edit during a long compile must not label old outputs
        # as belonging to the newly selected source.
        _, current_provenance, current_identity = _guard_source(engine)
        if current_identity != source_identity or current_provenance != provenance or _tree_sha(_inventory(root, engine.check_cancel, source=True)) != input_sha:
            raise ValueError('Traditional source changed during compilation; the previous staged build is preserved')
        if hasattr(engine, '_traditional_runtime_cache'):
            del engine._traditional_runtime_cache
        current_runtime = _runtime(engine)
        if not current_runtime['ready'] or current_runtime['identity'] != runtime['identity']:
            raise ValueError('Traditional runtime changed during compilation; the previous staged build is preserved')
        engine.check_cancel()
        _atomic_json(stage / 'verification.json', report)
        _atomic_json(stage / 'build-info.json', {'format': 1, 'recipe': RECIPE, 'recipe_identity': _recipe_identity(),
                     'source': provenance, 'source_identity': source_identity, 'input_sha256': input_sha,
                     'build_identity': build_identity, 'runtime_identity': runtime['identity'], 'built': time.time(),
                     'verification_sha256': _digest(report), 'compile_only': True})
        engine.check_cancel()
        _promote_stage(engine, stage)
        engine.config['jobs'] = jobs
        engine.save()
        return {'message': 'Nine Traditional ARM64 binaries compiled and staged. Deployment is the next milestone.',
                'staged': True, 'compile_only': True, 'recipe': RECIPE}
    finally:
        _remove(engine, stage)
        if evidence.exists():
            last = base / 'last-evidence'
            _remove(engine, last)
            os.replace(evidence, last)
