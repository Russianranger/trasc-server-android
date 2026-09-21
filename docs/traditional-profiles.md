# Traditional EQEmu profiles — 0.5.8

This milestone adds two independent worlds to the app: **TRASC Custom** and **Traditional EQEmu**. The existing installation remains Custom in its original location. Traditional starts empty, uses a separate clean ROF2 import, and has a distinct 16-bit adventure background for each of the same ten tabs.

**Traditional is a preparation workspace in this release.** Source/content imports and management are available. Traditional server Build, Deploy, binary rollback, Start and generated client-data preparation/export are blocked in both the UI and control daemon until the chosen fork passes the next Android compilation milestone. This release does not make an unmodified upstream download playable on Android.

## Switching worlds

1. Camp out and stop the client. Return from the client display to management with Android Back.
2. Stop the server runtime and finish any import, export or file picker.
3. At the top, choose **Traditional EQEmu → Switch world**. The screen reloads, the artwork changes and the runtime panel names the selected world.
4. Install the server runtime in Traditional, then import its source and content. The existing runtime supports this preparation work; it is not yet a verified upstream build environment.
5. To return, stop Traditional's runtimes, choose **TRASC Custom → Switch world**, and start the existing runtime/server normally.

Switching discards unsaved form edits. Only one profile can run at a time. The selected profile persists across app restarts. The native bridge rejects requests from a stale screen; active imports, exports and client displays prevent switching.

Each world owns its source, build cache, binaries, MariaDB files and credentials, maps, quests, configuration, client import, Wine runtime/prefix, DirectX helpers, controller mappings, logs, incoming files and backups. Nothing is automatically copied between them. The APK's tools and artwork are shared. First setup requires additional storage for the second runtime and client; immutable-file sharing is deferred.

Custom remains at the existing app-private `files/work` and `files/rootfs`. Traditional uses `files/profiles/traditional/work` and its own `rootfs`. The selector is outside both workspaces. The Files tab always shows paths relative to the selected world's work directory.

## Traditional imports and additional components

| Component | Where to import | Purpose / remaining validation |
| --- | --- | --- |
| EQEmu server source or your fork | Setup → Import server | Defaults to `EQEmu/EQEmu`, `master`; change to the chosen fork/ref. GitHub downloads record the resolved commit. GitHub ZIPs omit submodule contents; the build milestone must fetch and pin them. |
| PEQ world, player/system and local-login database tables | Setup → Select database | Use a complete seed, or add each SQL/SQL.GZ/ZIP member to the split-seed bundle in the distribution's required order and import once. The importer targets this profile's `peq` database. Exact schema and login compatibility remain to be verified. |
| Server geometry, navigation and water maps | Setup → Import maps | Import base/nav/water/legacy map directories. These are server data, separate from ROF2's installed zone assets. |
| Zone/global quest scripts | Setup → Traditional world content → Quests | Installs `server/quests`. ProjectEQ's quest repository is provided as an editable starting URL. |
| Perl quest plugins | Same panel → Perl plugins | Installs `server/plugins`. ProjectEQ includes a `plugins` directory; importing quests does not silently merge it into the quest tree. Perl itself and any additional Perl modules are runtime dependencies. |
| Lua quest modules | Same panel → Lua modules | Installs `server/lua_modules`. ProjectEQ includes this directory too. Match these modules to the quest revision. |
| Server assets / opcode files | Same panel → Server assets | Installs `server/assets`; requires `patch_RoF2.conf` in the selected asset package. Supply the package/repository matching the chosen server revision. Activation of its config/opcode paths is part of deployment in the next milestone. |
| A separate clean, supported ROF2 client | Client → Import your ROF2 client | User-supplied ZIP; no proprietary client is distributed. Native custom `dinput8.dll` loading and custom hooks are disabled in Traditional. Importing a modified client does not turn its other files into a clean installation. |
| Wine/Box64, graphics and DirectX model helpers | Client runtime / DirectX model helpers | Install per profile. Existing display, controller, audio and graphics controls cross over. First login against the traditional server is still pending. |
| Local login service, server config, shared memory and generated client data | Next Android deployment milestone | Build/verify loginserver and its account schema, generate profile-local credentials/configuration and shared data, check ROF2 opcodes and export matching spells/strings/skills/base data. Do not reuse Custom's binaries or config. |

Spire, Gameplay rules, Database, Files, Logs and the other tabs remain available. Schema-dependent actions report actual missing tables rather than inventing support. The Fixes tab retains Wine recovery; Custom ferry/map/spell repairs and modified-client addon tools remain in Custom. Pixel artwork changes presentation only; no historical rules, zone versions, spawn restrictions or era preset is applied.

The component importer accepts ZIP/tar archives through the picker or public HTTPS GitHub repositories. It rejects path escapes and archive links, checks the selected component's file shape, records archive SHA-256 and GitHub revision where available, and never runs installation scripts. Replacing a component requires its checkbox, replaces that entire directory and retains the old directory under `backups/content`. An interrupted directory swap is recovered when the control service next opens. Source updates leave live content directories alone. Local edits can be restored from the retained directory through Files.

The checklist reports imports, not compatibility certification. While the runtime is closed it asks you to reopen it to inspect content. Keep quests/plugins/Lua modules pinned to a compatible revision and review local edits before replacement.

## Backups

Complete-session ZIPs are per profile and record the profile identity. Restore into the matching selected profile. Older archives without a profile marker belong to Custom. Both the archive marker and restored settings are checked before activation; a Traditional archive cannot replace Custom through the restore flow. A complete session still requires an installed server runtime.

The earlier Android Downloads-provider failure and management-renderer loss remain separate unresolved resilience work. Preserve the user's successful external backup. If another save fails, reuse the already-created ZIP in that profile's `exports` folder instead of creating a new archive repeatedly. This profile work does not claim to fix provider death.

## Next milestone: make the chosen fork Android-ready

Confirm the exact repository and commit first. No traditional fork was modified as part of this app release. The default upstream link is a starting source, not confirmation that it is the user's intended fork.

1. Pin fork, PEQ seed, maps, quests/modules, assets and clean ROF2 version. Fetch recursive source submodules at their pinned commits. Retain the existing Custom build adapter separately.
2. Audit the ARM64 Debian/PRoot build environment and add a reproducible traditional runtime/toolchain manifest. Current upstream CMake requires CMake 3.20+, C++20 and a vcpkg toolchain. Its manifest lists Boost components, MariaDB client, zlib, OpenSSL, LuaJIT, cereal, fmt, glm, libuv, recastnavigation and libsodium; Perl support is conditional on Perl libraries. The existing Custom flags point to Lua 5.1 and are not an upstream build recipe.
3. Compile world, zone, loginserver, shared_memory, eqlaunch, UCS, queryserv and client import/export tools for Linux ARM64 under PRoot; verify ELF architecture, dynamic dependencies, Perl/Lua quest loading and migrations against a disposable database. This is Linux/glibc under Android PRoot, not an Android NDK/Bionic conversion.
4. Implement and verify traditional deployment/configuration: stable quest/plugin/module/map/asset paths, login account schema, ROF2 opcodes, shared-memory creation, matching client-data exports and fail-safe staged activation/rollback. Enable the profile's Build/Deploy/Start controls only after these gates pass.
5. Test on Thor: clean client login, character creation, zoning, one Perl and one Lua quest, rules edits, restart/state persistence, backup/restore and switching back to the untouched Custom world.
6. Only then implement one tested Luclin-era preset, followed by other eras and optional storage optimization. Keep era rules/content separate from solo/quality-of-life choices.

Primary references inspected for this milestone: [EQEmu standard directories and installation components](https://docs.eqemu.dev/server/installation/server-installation-windows/), [ProjectEQ quests, plugins and Lua modules](https://github.com/ProjectEQ/projecteqquests), [upstream CMake](https://github.com/EQEmu/EQEmu/blob/master/CMakeLists.txt), [dependency manifest](https://github.com/EQEmu/EQEmu/blob/master/vcpkg.json), and [source submodules](https://github.com/EQEmu/EQEmu/blob/master/.gitmodules). Recheck against the chosen fork's pinned revision.

Artwork was generated with the built-in image tool. All ten saved paths and exact prompts are recorded in [tab-artwork-058.json](tab-artwork-058.json).
