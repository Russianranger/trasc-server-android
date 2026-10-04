# Traditional EQEmu ARM64 build investigation

The supported source is [Russianranger/Server](https://github.com/Russianranger/Server) at
`4aceae18b94ffaafc08e2b17bc41cd72c77f795d`. The investigation ran for the requested
60 minutes on 2026-10-04, from 02:28:20 to 03:29:16 UTC (60.94 minutes).
Its resulting adapter is
`eqemu-bookworm-arm64-v1` in `backend/traditional_build.py`.

## What the investigation established

Native ARM64 Debian Bookworm compilation is viable. During the research hour,
the system-dependency trial compiled and linked eight executables: `world`,
`shared_memory`, `eqlaunch`, `ucs`, `queryserv`, `loginserver`, `export_client_files`
and `import_client_files`. Their downloaded ELF headers identify little-endian
AArch64 executables using `/lib/ld-linux-aarch64.so.1`; none contains a build
RPATH or RUNPATH. The login server requires `libcrypto.so.3`.

The remaining `zone` link was blocked by missing includes and declarations
exposed when unity builds and precompiled headers were disabled. The ARM
compiler failures matched independently reproduced source failures on x86.
No additional ARM instruction or Bookworm dependency API failure appeared in
the completed native sweep. All reported source failures were repaired and
their affected translation units replayed successfully on x86.
An early native API phase also successfully compiled the actual Lua client
and parser, Perl client and embedding code, Detour pathfinder and login
encryption objects. It completed during the research window in 78.51 seconds,
with a largest-child RSS of 1,789,068 KiB.

The qualified recipe retains PCH enabled. A later complete x86 PCH-disabled
link exposed one additional guard-order issue in `zone/embparser_api.cpp`:
`common/features.h` must precede the Perl XS conditional, otherwise the object
omits `perl_register_quest`. The forced zone PCH supplies those definitions in
the selected recipe. A fully qualified PCH-disabled fallback would require
that additional patch and its own complete build; it is not an app option.

The first production app-route qualification subsequently compiled and staged
all nine native ARM64 executables in 35 minutes 36 seconds using two jobs.
[Run 37175261183](https://github.com/Russianranger/trasc-server-android/actions/runs/37175261183)
verified their ELF architecture, loader dependencies, LuaJIT/Perl ABI and
OpenSSL default/legacy DES providers. Artifact `11293028564` has ZIP SHA256
`1fbf46c98023ae70ac8e1d211c971bc7cda92076b1ff978272e0d199aa76434d`.

Its following PRoot check stopped while moving the Docker-created, root-owned
build tree. The qualification container now runs with the host runner UID/GID,
matching the app's shared ownership of runtime/work files. The signed main run
must repeat native compilation, extracted-runtime PRoot verification and the
session round-trip before publishing either the runtime or APK. Physical Thor
compilation and first login remain device acceptance work.

| Existing build assumption | Selected fork requirement | Adaptation |
|---|---|---|
| Bundled fmt and libuv CMake directories | vcpkg packages by default | Use qualified Bookworm development packages and preserve upstream imported target names. |
| Lua 5.1 and `EQEMU_PREFER_LUA` | Mandatory LuaJIT discovery; C++20 | Supply native LuaJIT 2.1 and explicit LuaJIT cache paths. The old Lua arguments are unused. |
| Unversioned OpenSSL discovery | Provider API and `EVP_CipherInit_ex2` | Require OpenSSL 3 plus the matching default and legacy providers. DES-CBC must be available. |
| Cereal bundles RapidJSON headers | Debian cereal uses standalone RapidJSON | Replace five vendored include paths and the custom assertion macro. |
| `CMAKE_UNITY_BUILD=OFF` controls every target | Lua/Perl/GM unity is explicitly enabled upstream | Disable unity on all three targets and repair their hidden include dependencies. |
| An ordinary source ZIP includes submodules | Websocket headers are a Git submodule | Hydrate and verify the exact C++20-compatible websocketpp tree. |

## Source and dependency changes

The source overlay changes 37 existing files: three CMake files, two files
that use Debian's unbundled RapidJSON, and 32 files needing explicit includes,
forward declarations or include ordering. These edits do not change gameplay.
The importer retains the original source bytes. The adapter checks pristine
file hashes before patching a separate overlay and records the complete source,
recipe, runtime and staged-binary hashes.

The dependency shim supplies Boost's three header-only imported targets and
the upstream MariaDB, libuv, libsodium and Detour target names. It requires
OpenSSL 3 and Perl development support. Lua and Perl remain enabled together.

The required websocketpp commit is
`b9aeec6eaf3d5610503439b4fae3581d9aff08e8`. Its verified source tree contains
272 files, 3,566,324 bytes, with digest
`049b0323ca61bd4eaa1c0420bf842235c974517aa90cdb07873e24ecbf3c792f`.
Bookworm's older websocketpp package does not contain the selected C++20 fix.

The separate Traditional runtime adds `libcereal-dev`, `rapidjson-dev`,
`libfmt-dev`, `libglm-dev`, `libluajit-5.1-dev`, `luajit`, `librecast-dev`,
`libuv1-dev`, `binutils`, `file` and `openssl` to the app's normal Debian
compiler/database packages. LuaJIT's `lua.h` reports Lua API version 5.1.4;
that number must not be mistaken for its actual LuaJIT 2.1 version.

The observed native package versions were GCC 12.2, CMake 3.25.1, Boost 1.74,
fmt 9.1, cereal 1.3.2, RapidJSON 1.1, GLM 0.9.9.8, LuaJIT 2.1, Detour 1.5.1,
libuv 1.44.2, MariaDB 10.11, libsodium 1.0.18, Perl 5.36 and OpenSSL 3.0.22.

The original vcpkg route also configured after adding `autoconf`, `automake`,
`libtool` and `libtool-bin`; its recorded vcpkg commit is
`d1ff36c6520ee43f1a656c03cd6425c2974a449e`. It builds a larger independent
dependency tree and requires careful OpenSSL provider packaging. The system
route makes compiler and runtime library identities consistent inside the
Bookworm PRoot image.

## Configure and build arguments

For an already patched source overlay, the effective native configure recipe is:

```sh
cmake -S "$patched_source" -B "$build_dir" -G Ninja \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_TOOLCHAIN_FILE= \
  -DCMAKE_BUILD_TYPE=Release \
  '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG -fno-strict-aliasing' \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DEQEMU_USE_SYSTEM_DEPENDENCIES=ON \
  -DTRASC_WEBSOCKETPP_INCLUDE_DIR="$patched_source/submodules/websocketpp" \
  -DLUAJIT_INCLUDE_DIR=/usr/include/luajit-2.1 \
  -DLUAJIT_LIBRARY=/usr/lib/aarch64-linux-gnu/libluajit-5.1.so \
  -DEQEMU_BUILD_PCH=ON \
  -DEQEMU_BUILD_SERVER=ON -DEQEMU_BUILD_LOGIN=ON \
  -DEQEMU_BUILD_CLIENT_FILES=ON \
  -DEQEMU_BUILD_LUA=ON -DEQEMU_BUILD_PERL=ON \
  -DEQEMU_BUILD_TESTS=OFF -DEQEMU_ADD_PROFILER=OFF
cmake --build "$build_dir" --parallel 1 --target \
  world zone shared_memory eqlaunch ucs queryserv loginserver \
  export_client_files import_client_files
```

No x86, Android NDK or strict-alignment compiler flags are needed. The
`-fno-strict-aliasing` flag is a conservative mitigation for the existing
serialization casts; it does not establish that all unaligned casts are free
of undefined behavior. Independent alignment hardening and gameplay runtime
testing remain separate work.

## Resource measurements

The native ARM two-job, PCH-disabled sweep took 38 minutes 47.98 seconds and
finished with source errors, rather than timing out. GNU `time -v` recorded a
largest-child RSS of 2,246,324 KiB, approximately 2.14 GiB, with no swap. This
is not the combined memory of both compiler jobs.

The separate ARM precompiled-header trial succeeded with one job:

| PCH | Creation time | Maximum RSS | File size |
|---|---:|---:|---:|
| Common | 2.46 s | 287,468 KiB | 95,566,044 bytes |
| Zone | 13.36 s | 1,010,324 KiB | 382,689,036 bytes |

One job is the conservative device build setting. Successful PCH creation
proves feasibility, while complete compilation and Android device memory
pressure still need their own evidence. The larger translation units make
an unrestricted CPU-count-based job default unsuitable.

The app defaults to one job and permits an explicit two-job setting only with
adequate available memory. Production CI uses two jobs on its larger ARM64
runner; the stateless PRoot compiler fixture uses one. CI parallelism changes
the resource envelope, while retaining the same compiler, source and flags.
An earlier full single-job PCH trial reached 530 of 768 Ninja steps before its
45-minute investigation timeout. That timeout does not establish a compiler
failure; a complete device build can take substantially longer. Production
qualification therefore has a larger time allowance.

## Final qualification and staged results

`backend/traditional_verify.py` validates exactly nine staged executables. It
checks ELF64 little-endian AArch64 metadata and the Bookworm interpreter before
using `ldd` and `readelf`. The zone must resolve LuaJIT and Perl libraries, and
the login server must resolve OpenSSL 3's crypto library. The helper rejects
unresolved dependencies and source/build directory RPATHs, verifies active
default/legacy providers and DES-CBC, and writes its manifest only after all
checks succeed. The adapter rehashes that result before atomically replacing
the staged build.

`scripts/check-traditional-proot.sh` extracts the archive with the APK's Java
extractor, builds the same pinned PRoot source and patches used by the app,
and uses the app's compatibility-mode bindings and environment. It hides the
compilation directory, compiles and runs a stateless C++20 dependency fixture,
tests child processes plus regular-file mmap/locking, and verifies the same
staged binaries through the extracted root filesystem.
It also records first and cached adapter-status timings and requires that the
qualified staged build is recognized with the compilation tree hidden. The
initial timing measurement records latency without imposing an unmeasured
performance threshold.

Server executables are never invoked with generic `--help` or `--version`
arguments: several ignore those arguments and import database data or start
services. Compilation qualification does not initialize a server database.

Traditional deployment, first startup, schema migration and player/client
export remain guarded until a separate integration verifies content paths,
opcodes, login/account configuration and current database expectations.
The Custom source/build/runtime route remains independent.

## Investigation evidence

- [Completed native PCH-disabled sweep](https://github.com/Russianranger/trasc-server-android/actions/runs/37172166296), artifact `11292776810`, ZIP SHA-256 `8117d5a1a87fbe19db23c5427cc2c7c2e78d4ac0984253343b089868da2223f4`.
- [Successful native PCH resource trial](https://github.com/Russianranger/trasc-server-android/actions/runs/37172273829), artifact `11291633940`, ZIP SHA-256 `544c66d92c431fa637484842334ad8d2f925f47c056fdc32c1cd5219313ec96d`.
- [Successful native dependency-API phase](https://github.com/Russianranger/trasc-server-android/actions/runs/37173282093), artifact `11292664955`, ZIP SHA-256 `38596512d2de0fe2dd699d92665378eabf1dc1f9f4f8a5f743c1c7b5e3da454f`. Its subsequent single-job full build reached 530 of 761 remaining Ninja steps without source errors before the 45-minute timeout.
- [Full patched native retry](https://github.com/Russianranger/trasc-server-android/actions/runs/37173915902), artifact `11293930792`, ZIP SHA-256 `7bc68c34b089dd4c9952ac0a7fb75b50ba738349f244ee90f28186f3b59703e9`. Its final 37-file patch set compiled the early dependency objects successfully and reached 508 of 761 remaining steps without source errors before the same 45-minute single-job timeout. Largest-child RSS was 2,245,204 KiB, with no swap. Final production qualification is performed separately by `traditional-runtime.yml`.
