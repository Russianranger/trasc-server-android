# TAKP World and client profile — 0.6.19

Version **0.6.19 / code 68** groups server/client launch controls, reduces TAKP camera-look motion and enables spawn/packet diagnostic logging. **TAKP World**, introduced in 0.6.16, sits beside **TRASC Custom** and **Traditional EQEmu**. TAKP uses the selected server fork with playerbots, matching quests and maps, an independent database and local login, and a separate Windows TAKP client installation. Default, Necromancer and Monk launcher themes remain available across all three worlds.

On 0.6.18, the user confirmed Android login, character creation, entry into Paineel, four stable minutes in the world and camp. The server accepted both the executable and original spell-file checksums. NPC visibility remains unresolved, and camera behavior, graphics/audio, zoning and playerbots need further device testing. The APK includes three compatibility DLLs and their provenance; the full game installation is imported by the player.

## World isolation and updates

Install the APK as an update. Camp out, stop the client and server runtime, and finish any file picker or transfer. Choose **World profile → TAKP World → Switch world**. The selection persists across app restarts. Requests from a stale profile screen are rejected.

For an existing prepared client, install 0.6.19, open the TAKP runtime, start the server and select **Start TAKP**. Keep the existing client, Wine prefix, database and deployed server build; no reimport, reset, repeated **Prepare client** or server rebuild is needed. This update preserves the preview signing certificate and reuses all 21 native launcher components from 0.6.18; the pinned server binaries, runtimes and renderer remain unchanged.

The 0.6.18 startup repair remains included for prepared 0.6.16/0.6.17 clients. The next launch repairs only the old unspaced `eqhost.txt` section headers to the exact `[Registration Servers]` and `[Login Servers]` names. Registration/login endpoints and all other file bytes are preserved. Originals are saved in the TAKP Wine prefix at `client/prefix/trasc-takp-login-originals/eqhost.txt`, with the last repaired original in `eqhost.previous.txt`.

The centered top toolbar groups server **Start server**, **Stop server** and **Restart** with client **Start TAKP**/**Stop client**. It appears on every tab across all three worlds and launcher themes; other worlds show their own client name. Stopping the client remains available while a server operation is busy.

TAKP owns `files/profiles/takp/rootfs` and `files/profiles/takp/work`. Its source, build cache, deployed binaries, database files and credentials, maps, quests, client import, Wine runtime/prefix, DirectX helpers, controller mappings, logs and backups stay there. Custom retains its original home; Traditional retains `profiles/traditional`. Download caches are profile-specific. Short disposable client paths are `c`, `t` and `k`; independent server PRoot paths are `sc`, `st` and `sk`. Starting one runtime does not reset the other runtime's helpers.

TAKP installs its own copy of the published [Traditional ARM64 Debian Bookworm dependency image](https://github.com/Russianranger/trasc-server-android/releases/tag/traditional-runtime-v1). Its installed marker records `profile=takp`, `runtime=takp-1.0`, and the original dependency image identity. It does not use Traditional's installed rootfs or work directory. Complete session backups record TAKP identity; Custom, Traditional and legacy Custom backups cannot be restored into TAKP.

Each additional world requires space for its runtimes, game installation, maps, database, source and build cache. Compilation requires at least 3 GiB free according to the build adapter, plus space for the other components and retained backups.

## First server setup

1. In TAKP's **Setup**, install/download its runtime or choose the matching offline `runtime-arm64.tar.gz` from the dependency image release, then **Open runtime**.
2. Select **Download TAKP world files**. This fetches the pinned server, quests and maps below, then installs the matching Mac-client patch, general/chat opcodes and legacy-login opcode files. Repeating setup checks the imported source and already installed content.
3. Select **Initialize fresh TAKP database**. The importer verifies the bundled September 8, 2026 seed archive, imports its four mandatory world/player/login/data SQL parts into a new staging database, applies the two missing official player-event updates and all eleven playerbot migrations, and verifies the result before selecting it. It does not execute `drop_system.sql` or replace an existing world database. Failure leaves the previous selection intact.
4. Enter a username and password and select **Create local TAKP account**. Names accept 1–19 letters, digits or underscores; passwords accept 1–19 printable ASCII characters without spaces. Existing account passwords are preserved if the name already exists. Credentials are stored using the TAKP login server's salted password format.
5. In **Builds**, select **Build imported source**. Start with one compiler job. The build recipe uses Bookworm GCC 12, CMake 3.25, Ninja, LuaJIT and the source's vendored libraries. It stages and verifies all nine ARM64 binaries before deployment.
6. Select **Deploy successful build**, then use the shared **Start server** control. Deployment verifies the database, playerbot schema, content and binary identities, writes TAKP configuration, and prepares shared memory. The client-facing legacy login listens on **UDP 6000**; server registration uses the separate local port 5998.

The setup checklist shows source, quests, maps, database, bots, account and build/deployment status. Server/client tools operate only on the selected world. Existing Custom/Traditional server builds do not need recompilation for this APK update.

## Import and prepare the client

1. In **Client**, install TAKP's separate client runtime using **Download client runtime** or its matching offline runtime archive.
2. Use **Import your TAKP client** to choose a complete supported Windows TAKP 2.1/2.2 client ZIP. Obtain the full installation using the [TAKP setup guide](https://wiki.takp.info/wiki/Getting_Started_on_Windows). The three uploaded DLLs alone are not a game installation.
3. Install **DirectX helpers** from Microsoft's June 2010 redistributable. TAKP requires its x86 `d3dx9_43.dll` for the D3D8 wrapper. Online and offline installers verify the pinned package. Custom/Traditional retain their existing two model-helper requirements.
4. For this new import, select **Prepare client** while the server runtime is open and the game is stopped. This exports `spells_us.txt` and `SkillCaps.txt`, copies them to the client root, writes the legacy registration/login form of `eqhost.txt` using the exact `[Registration Servers]` and `[Login Servers]` headers, applies the selected display settings, and installs the three pinned compatibility DLLs. Original changed files are backed up. The Windows TAKP client's supplied `spells_en.txt` is preserved: the pinned server validates its checksum during login. The database exporter uses the separate `spells_us.txt` name; replacing the client's actual spell file requires a separately qualified checksum policy.
5. Start the TAKP server if it is stopped, choose a renderer/resolution, then select **Start TAKP**. The launcher runs Windows **`eqgame.exe` with no `patchme` argument**. Sign in using the local account and select **TAKP World on Android**.

The client importer requires ordinary PE32 x86 `eqgame.exe`, `eqmain.dll` and `eqgfx_dx8.dll`; it also requires `eqmac.exe`, `spells_en.txt`, `eqstr_en.txt` and nonempty `.s3d` game assets. The **0.6.17 / code 66** update fixes the 0.6.16 importer, which incorrectly required the server-side name `spells_us.txt`. Import the original TAKP 2.1c ZIP without renaming its spell file. Legacy packages containing only `spells_us.txt` remain accepted for compatibility with the previous importer. When both names exist, validation records `spells_en.txt`. **`eqmac.exe` is a checksum resource used by the TAKP modification and is never launched.** A RoF2 ZIP or DLL-only ZIP is rejected.

Preparation and launch use the supported `EqwGeneral` fullscreen setting and a 32-bit display mode. The client FPS limiter uses foreground 60, background 30 and mouselook 60; this is a configured limit, not a measured Android frame rate. Resolution/display choices and unrelated client INI settings are retained through bounded updates.

Version 0.6.19 applies a 0.15 gain to TAKP relative motion only while the right mouse button is held for camera look. Signed fractional motion is carried forward so small movements remain responsive. At the configured 700-pixel/second controller baseline, camera look sends 105 pixels/second. Menu movement and Custom/Traditional keep their existing rates. This is a scoped sensitivity adjustment that still needs a Thor test; cursor-warp feedback has not been established as the cause of the fast camera.

The rendering path is **D3D8 → bundled d3d8to9 → D3D9 → DXVK/Turnip** when Turnip is selected, or the WineD3D path for Software/VirGL. The UI retains those renderer choices. Compatibility and performance must be measured on the Thor. The initial launch preflight checks the architecture of Wine's x86 `msvcp140.dll`, `vcruntime140.dll` and `ucrtbase.dll`; loader tracing records actual DLL-loading evidence separately.

TAKP disables the RoF2 `dinput8.dll`, camera adapter, NPC render overrides, fast-loading, particle, boat and spell-filter hooks. Its client data exporter produces two files without RoF2 filtering. RoF2 UI-skin import/activation is unavailable in TAKP; use the supported TAKP game's built-in UI facilities. The saved launcher controller layers and keyboard remain available in the embedded display.

## Sources and bundled client updates

| Component | Qualified source / revision |
| --- | --- |
| Playerbot server | [Russianranger/Servertakp](https://github.com/Russianranger/Servertakp/tree/25bf70acb6bd24853cf09e447ddd62b96a4491a4) — `25bf70acb6bd24853cf09e447ddd62b96a4491a4` |
| Quests | [Russianranger/queststakp](https://github.com/Russianranger/queststakp/tree/f43d4fcfa89fecd76b5ac3fb5096f8d658a6c65f) — `f43d4fcfa89fecd76b5ac3fb5096f8d658a6c65f` |
| Server maps | [Russianranger/Mapstakp](https://github.com/Russianranger/Mapstakp/tree/95cb9322b853e7ec2f67158b87442286315042eb) — `95cb9322b853e7ec2f67158b87442286315042eb` |
| Database seed | Server's `utils/sql/database_full/alkabor_latest.zip`, SHA-256 `6f5a61206b22d3d70c20ece7fb8c617bbe0849d286b2cb48279841f4c6103433` |
| Build recipe | `eqmac-bookworm-arm64-luajit-v1`, `backend/takp_build.py` |

The server content is pinned by a complete source-tree digest; changed or incomplete source cannot silently build under this qualification. Source updates need a new qualified recipe. Runtime and staged/deployed binary identities and checksums are verified before activation.

| Bundled file | Version | SHA-256 |
| --- | --- | --- |
| `eqgame.dll` | EQMacEmu v0.0.0.3 | `f0ca8e4bdcf3875419ecb1067a95bd6dbf8197e564f9d51ff4dec98a30f14b97` |
| `eqw.dll` | CoastalRedwood v1.0.2 | `dffb97ac1f47d41f450614c8d6d4da30f3f47b7ed5046dbdbd111b3ba1fbe5ba` |
| `d3d8.dll` | d3d8to9 v1.16.0 | `122928cfe225c25d30decf7184a5d37e490cecf3b58256ba3206c7e1853f8ab8` |

Their original source links and licenses/provenance are recorded in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and `backend/takp-client/bundle.json`. No game executable, game asset, uploaded debug PDB or Microsoft runtime library is bundled in the APK.

## Device acceptance and remaining work

The 0.6.18 device pass established login, character creation, Paineel entry and camp. For 0.6.19, confirm that the shared launch controls work across all three worlds and themes, and that **Stop client** works during a server operation. In TAKP, compare camera motion with the right mouse button held and ordinary menu motion with it released. Start the server after updating, move through the area where NPCs appeared absent, camp and export logs. Then test casting, trading, two adjacent zones and relogin persistence.

A host probe using the same database seed recorded 156 NPC creation events in Paineel with clean zone startup. That result does not establish which NPCs were visible on the Thor. Version 0.6.19 enables the server's existing Spawns/Netcode log categories. Fresh exported zone logs record actual spawn creations and coordinates, plus packet errors where reported. Live NPC counts, player-position snapshots and nearest-NPC distances are unavailable in this release. The logs provide evidence for investigating spawn creation and delivery; NPC visibility remains unresolved, and no NPC fix is claimed.

Then run `#bot help`, create a first companion with `#bot create Mercy 2 1 1`, and spawn it with `#bot spawn Mercy`. This is a female human cleric; the server supports ordinary players owning their own bots. Confirm following, assistance/healing, equipment exchange, dismissal, zoning, camp/relogin and server-restart persistence. See the [server's playerbot guide](https://github.com/Russianranger/Servertakp/tree/25bf70acb6bd24853cf09e447ddd62b96a4491a4/docs/player-bots) for its full command reference.

Version 0.6.18 detects explicit Wine game crashes, closes the embedded display and preserves the failure cause in launcher status and exported logs. On a failure, use **Export logs**. Keep the launch's renderer, resolution, elapsed startup time and last visible screen with the report. Native logs remain available even if the server runtime cannot start.

The 0.6.18 update passed all 406 Python tests with no skips, thirteen browser programs, management checks, DirectX extraction/recovery, Android assembly/lint and APK signing/packaging checks. Native ARM64 Bookworm qualification passed all eleven integration checks, including the production nine-binary build, seed/bot/account setup, local services, Qeynos map/Lua boot, unfiltered exports and clean shutdown. The published APK and source hashes match the verified build. See [0.6.18 release verification](release-status-0618.md) for its hashes, source commit, build evidence and device handoff.

Version 0.6.19 automation remains pending until its build completes. NPC visibility, the new camera rate, graphics/audio, zoning and bots still need device verification. This version initializes a fresh TAKP database for new installations; migration of an existing external TAKP world is not exposed. Custom ferry and RoF2-specific patch/era tools are disabled in TAKP. Broad TAKP schema editing and client-skin import require separate support; the profile focuses on setup, play and diagnostics.
