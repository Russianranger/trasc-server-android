#include <boost/dynamic_bitset.hpp>
#include <cereal/archives/json.hpp>
#include <fmt/format.h>
#include <glm/vec3.hpp>
#include <DetourNavMesh.h>
#include <openssl/evp.h>
#include <openssl/provider.h>
#include <mysql.h>
#include <sodium.h>
#include <uv.h>
#include <zlib.h>
#include <cstdlib>
#include <iostream>
#include <sstream>
extern "C" {
#include <luajit.h>
#include <lauxlib.h>
#include <EXTERN.h>
#include <perl.h>
}
static_assert(OPENSSL_VERSION_MAJOR >= 3);
static_assert(LUAJIT_VERSION_NUM >= 20100);
static int perl_probe(int argc, char **argv, char **env) {
    PERL_SYS_INIT3(&argc, &argv, &env);
    PerlInterpreter *my_perl = perl_alloc();
    if (!my_perl) return 1;
    perl_construct(my_perl);
    char empty[] = ""; char flag[] = "-e"; char expr[] = "exit(0)";
    char *args[] = {empty, flag, expr, nullptr};
    int result = perl_parse(my_perl, nullptr, 3, args, nullptr);
    if (!result) result = perl_run(my_perl);
    perl_destruct(my_perl); perl_free(my_perl); PERL_SYS_TERM();
    return result;
}
int main(int argc, char **argv, char **env) {
    if (perl_probe(argc, argv, env)) return 1;
    boost::dynamic_bitset<> bits(4); bits.set(3);
    glm::vec3 position(1, 2, 3);
    std::stringstream archive;
    { cereal::JSONOutputArchive out(archive); out(cereal::make_nvp("bits", bits.count())); }
    lua_State *lua = luaL_newstate(); if (!lua) return 2;
    if (!luaJIT_setmode(lua, 0, LUAJIT_MODE_ENGINE | LUAJIT_MODE_ON)) return 3;
    if (luaL_dostring(lua, "local sum=0; for i=1,1000 do sum=sum+i end; return sum") ||
        lua_tonumber(lua, -1) != 500500) { lua_close(lua); return 3; }
    lua_close(lua);
    dtNavMesh *mesh = dtAllocNavMesh(); if (!mesh) return 4; dtFreeNavMesh(mesh);
    uv_loop_t loop; if (uv_loop_init(&loop)) return 5; if (uv_loop_close(&loop)) return 6;
    if (sodium_init() < 0) return 7;
    OSSL_PROVIDER *normal = OSSL_PROVIDER_load(nullptr, "default");
    OSSL_PROVIDER *legacy = OSSL_PROVIDER_load(nullptr, "legacy");
    EVP_CIPHER *des = EVP_CIPHER_fetch(nullptr, "DES-CBC", "provider=legacy");
    if (!normal || !legacy || !des) return 8;
    EVP_CIPHER_free(des); OSSL_PROVIDER_unload(legacy); OSSL_PROVIDER_unload(normal);
    std::cout << fmt::format("C++20 native dependencies passed: LuaJIT {}; Perl {}; UV {}; MariaDB {}; zlib {}; GLM {}\n",
        LUAJIT_VERSION, PERL_REVISION * 10000 + PERL_VERSION * 100 + PERL_SUBVERSION,
        uv_version_string(), mysql_get_client_info(), zlibVersion(), position.z);
}
