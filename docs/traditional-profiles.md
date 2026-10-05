# Traditional EQEmu profiles — 0.6.7

This milestone adds two independent worlds to the app: **TRASC Custom** and **Traditional EQEmu**. The existing installation remains Custom in its original location. Traditional starts empty, uses a separate clean ROF2 import, and has a distinct 16-bit adventure background for each of the same ten tabs.

**Traditional now compiles and stages the selected server fork.** Source/content imports and management remain available. The build adapter supports `Russianranger/Server` at commit `4aceae18b94ffaafc08e2b17bc41cd72c77f795d`, applies checked changes in a separate build copy and verifies all nine Linux ARM64 executables. Deploy, binary rollback, Start and generated client-data preparation/export remain blocked until database/configuration/login qualification is complete. A successful compile does not yet make the world playable.

## Switching worlds

1. Camp out and stop the client. Return from the client display to management with Android Back.
2. Stop the server runtime and finish any import, export or file picker.
3. At the top, choose **Traditional EQEmu → Switch world**. The screen reloads, the artwork changes and the runtime panel names the selected world.
4. Install the separate Traditional build runtime. Existing Traditional preparation runtimes must be shut down and refreshed with **Setup → Download/refresh build runtime**; imported files and settings remain in the workspace. The app rejects a Custom runtime archive in the Traditional installer.
5. To return, stop Traditional's runtimes, choose **TRASC Custom → Switch world**, and start the existing runtime/server normally.

Switching discards unsaved form edits. Only one profile can run at a time. The selected profile persists across app restarts. The native bridge rejects requests from a stale screen; active imports, exports and client displays prevent switching.

Each world owns its source, build cache, binaries, MariaDB files and credentials, maps, quests, configuration, client import, Wine runtime/prefix, DirectX helpers, controller mappings, logs, incoming files and backups. Nothing is automatically copied between them. The APK's tools and artwork are shared. First setup requires additional storage for the second runtime and client; immutable-file sharing is deferred.

Custom remains at the existing app-private `files/work` and `files/rootfs`. Traditional uses `files/profiles/traditional/work` and its own `rootfs`. The selector is outside both workspaces. The Files tab always shows paths relative to the selected world's work directory.

## Traditional imports and additional components

| Component | Where to import | Purpose / remaining validation |
| --- | --- | --- |
| Selected server source | Setup → Import server | New profiles default to `Russianranger/Server` and the tested commit above. Existing URLs are retained: choose **Use tested Server source**, then import from GitHub. The adapter verifies source guards and hydrates the exact websocket header revision omitted from GitHub ZIPs. Other revisions remain importable but cannot use this build recipe. |
| PEQ world, player/system and local-login database tables | Setup → Choose database file | Select `peq-latest.zip`; the complete five-part PEQ seed is selected automatically. Review content/login/player/state/system, then choose **Import complete PEQ database**. Other split distributions can use the advanced manual bundle. The importer targets this profile's `peq` database. Exact schema and login compatibility remain to be verified. |
| Server geometry, navigation and water maps | Setup → Import maps | The default is `https://github.com/Russianranger/eqemu-maps`; leave the branch blank to use its default branch. Import base/nav/water/legacy map directories. These are server data, separate from ROF2's installed zone assets. |
| Zone/global quest scripts | Setup → Traditional world content → Quests | Installs `server/quests`. ProjectEQ's quest repository is provided as an editable starting URL. |
| Perl quest plugins | Setup → Perl plugins | Defaults to `ProjectEQ/projecteqquests`; imports only `plugins/` into `server/plugins`. Repository/revision and ZIP controls are separate from quests. Perl and any additional Perl modules remain runtime dependencies. |
| Lua quest modules | Setup → Lua modules | Defaults to `ProjectEQ/projecteqquests`; imports only `lua_modules/` into `server/lua_modules`. Use the same revision as your quests. |
| Server assets / opcode files | Setup → Server assets | Defaults to `EQEmu/EQEmu` at the qualified server revision. Selectively installs client patch configurations in `server/assets/patches` and general/mail/login opcodes in `server/assets/opcodes`; source and SQL are excluded. Deployment must activate these paths in the next milestone. |
| A separate clean, supported ROF2 client | Client → Import your ROF2 client | User-supplied ZIP; no proprietary client is distributed. Native custom `dinput8.dll` loading and custom hooks are disabled in Traditional. Importing a modified client does not turn its other files into a clean installation. |
| Client UI skins in either world | Client → Import a client UI skin → Choose UI ZIP | Adds named skins to that profile’s client `uifiles` directory. Replacements retain backups; built-in default skins are protected. Use the displayed `/loadskin` command in game. |
| Wine/Box64, graphics and DirectX model helpers | Client runtime / DirectX model helpers | Install per profile. Existing display, controller, audio and graphics controls cross over. First login against the traditional server is still pending. |
| Local login service, server config, shared memory and generated client data | Next Android deployment milestone | Qualify the compiled loginserver against its account schema, generate profile-local credentials/configuration and shared data, check ROF2 opcodes and export matching spells/strings/skills/base data. Do not reuse Custom's binaries or config. |

Spire, Gameplay rules, Database, Files, Logs and the other tabs remain available. Schema-dependent actions report actual missing tables rather than inventing support. The Fixes tab retains Wine recovery; Custom ferry/map/spell repairs and modified-client addon tools remain in Custom. Pixel artwork changes presentation only; no historical rules, zone versions, spawn restrictions or era preset is applied.

The component importer accepts ZIP/tar archives through the picker or public HTTPS GitHub repositories. It rejects path escapes and archive links, checks the selected component's file shape, records archive SHA-256 and GitHub revision where available, and never runs installation scripts. Replacing a component requires its checkbox, replaces that entire directory and retains the old directory under `backups/content`. An interrupted directory swap is recovered when the control service next opens. Source updates leave live content directories alone. Local edits can be restored from the retained directory through Files.

The checklist reports imports, not compatibility certification. While the runtime is closed it asks you to reopen it to inspect content. Keep quests/plugins/Lua modules pinned to a compatible revision and review local edits before replacement.

## Backups

Complete-session ZIPs are per profile and record the profile identity. Restore into the matching selected profile. Older archives without a profile marker belong to Custom. Both the archive marker and restored settings are checked before activation; a Traditional archive cannot replace Custom through the restore flow. A complete session still requires an installed server runtime.

The earlier Android Downloads-provider failure and management-renderer loss remain separate unresolved resilience work. Preserve the user's successful external backup. If another save fails, reuse the already-created ZIP in that profile's `exports` folder instead of creating a new archive repeatedly. This profile work does not claim to fix provider death.

## Compile the selected server

1. Select Traditional, stop the client and refresh its build runtime as described above. Custom continues to use its existing runtime.
2. Choose **Use tested Server source**, then **Import from GitHub**. This selects the exact tested commit without silently changing saved settings. A matching pristine ZIP can also be imported; it must pass the recipe guards and records its archive checksum.
3. Open **Builds → Build imported source** with **one compiler job**. Connect power and keep several GiB free. Two jobs are available with more memory; three/four are disabled for this adapter. Compilation does not require a database, maps or client import.
4. Follow `operation.log`. The original import stays unchanged; patched source, pinned websocket headers and CMake objects live under `builds/traditional/`. Failed or cancelled builds retain the previous complete staged build.
5. Success stages `world`, `zone`, `shared_memory`, `eqlaunch`, `ucs`, `queryserv`, `loginserver`, `export_client_files` and `import_client_files` under `server/bin.staged/`. Its manifest records the source fingerprint, recipe, runtime, options and verified binary hashes. Changed source or runtime invalidates the readiness indicator.

The compiler uses Debian ARM64 GCC, C++20, LuaJIT and Perl with OpenSSL 3's default/legacy providers. PCH is enabled, problematic unity batches are explicitly disabled and Release uses `-O2 -DNDEBUG -fno-strict-aliasing`. This is Linux/glibc inside PRoot. See [the research, patches and complete CMake arguments](traditional-arm-build.md).

Verification uses ELF/loader/dependency checks and stateless toolchain fixtures. It does not run server or import/export mains: several of these tools can connect to or modify a database even when given an apparent help argument. Physical Thor compilation and first login require device acceptance.

## Next milestone: deployment and first login

1. Pin the PEQ seed, maps, quests/modules, assets/opcodes and clean ROF2 version to this server revision.
2. Qualify database and local-login schemas against a disposable profile, migrations, account setup and advertised server address.
3. Implement deployment/configuration with stable quest/plugin/module/map/asset paths, shared-memory creation, matching client-data exports and staged activation/rollback. Enable Deploy/Start only after these checks pass.
4. Test on Thor: clean client login, character creation, zoning, one Perl and one Lua quest, rules edits, restart/state persistence, backup/restore and switching back to Custom.
5. Then implement one tested Luclin-era preset, followed by other eras and optional storage optimization. Era rules/content remain separate from solo/quality-of-life choices.

Artwork was generated with the built-in image tool. All ten saved paths and exact prompts are recorded in [tab-artwork-058.json](tab-artwork-058.json).

See [content downloads and UI ZIP test steps](content-import-067.md) for 0.6.7.
