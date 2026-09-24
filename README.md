# TRASC Server for Android

**Russianranger foreword;**

This app is vibe coded utilizing ChatGPT's Codex with Astra "Extra High" thinking model. As of the time of this foreword (9/18/26) I have been working on this for about 1 week. This app is a way for me to easily replicate what I was doing manually in Termux with server compilation/running and then running the client in Winlator/GameNative and tinkering with those settings. I just wanted an easier, and more intuitive way to pull the custom Triune fork (forked off Saltmontes5k fork) that had ascendant and other custom additions and integrate it into the server. This project turned out to be a lot more lucrative than just that. So what does this app do, and what was it meant for?

**This app allows you to do the following;**
- Pull my server fork which is geared for Arm64 architecture and has all the toolchains needed to compile a server on Android ARM
- Pull a map repository
- Import a database from the server repo
- Build the server *in the app*
- Backup/export server/database
- Deploy a server on the device
- Import your legally obtained ROF2 client *to play inside the app*
- Controller support with mapping layers (you can change mappings at the click of a button)
- Has an SQL editor to alter the database
- Has a GUI for all the server rules that you can change in the app

**What was it meant for?**
- A device running Android, with at least 8gb of RAM, and a Snapdragon 8 Gen 2 SOC
- I play this on my AYN Thor Max (16gb of RAM) with *no* issues in terms of FPS and stability* (*still have to stress test this more)
- Someone with a little bit of knowledge into the workings of server, its not idiot proof

Hopefully someone else out there, with the same niche interest as me can find value in this and enjoy it too.

**AI Description Below**

A standalone Android control app for [Russianranger/Triptych-Triumvirate](https://github.com/Russianranger/Triptych-Triumvirate), initially targeting the AYN Thor's ARM64 Android environment. The app owns its runtime, database, source, builds and server files. It does **not** require installing Termux, root, a PC-hosted server or a web service.

**Status: device testing preview.** On the AYN Thor, the user has confirmed compilation, database import and connection from the existing client. The user has also confirmed complete session backup/restore, controller bindings and client input on 0.2.1. On 0.3.4, the user confirms visible character models, animations and movement inside embedded ROF2. The 0.3.6 device pass confirms correct graphics using the Adreno 740 through VirGL; performance and loading remain poor. Version 0.3.7 improved repeat startup and asset loading on-device, but performance remains inadequate. Version 0.3.8 substantially improved loading on the Thor with verified PRoot acceleration, but world FPS is still poor. Version 0.3.9 added display-buffer reuse and separate Wine/display measurements; the first device comparison favors Single thread, but FPS remains poor. Version 0.3.10 adds an experimental native OpenGL worker alongside Single thread, records its activity and preserves both runs' startup logs for the next comparison. The 0.3.10 worker comparison did not improve performance and revealed game threads restricted to CPU 0. Version 0.4.0 adds Turnip/DXVK and a reversible available-core affinity option. Playable performance and zone-state restoration still require verification.

## Downloads and first setup

**Beta 0.6 — runtime installation repair:** expands hard links into regular files when installing server/client runtimes, avoiding the `link failed: EACCES` failure reported on Fold6/Android 16. Existing working installations need only the APK update. [Release and testing instructions](docs/beta-06-release.md).

**App 0.5.8 — independent world profiles:** switch between the existing TRASC Custom world and a separate Traditional EQEmu preparation workspace. All ten tabs cross over; Traditional has ten bundled 16-bit adventure scenes, quests/plugins/Lua/assets imports, split PEQ seed bundles and a clean-client baseline. Traditional Android compilation/deployment is the next milestone. [Profile guide and component checklist](docs/traditional-profiles.md).

**App 0.5.7 — Fixes and shared session controls:** the runtime panel includes server Start/Stop/Restart and separate server/client activity indicators on every tab. **Fixes** contains ferry management, retired-trial cleanup, Nektulos maps, spell compatibility and Wine prefix recovery. Each tab has a distinct offline fantasy illustration. Existing server binaries, client DLL and accepted ferry installation remain compatible. [Update and testing instructions](docs/preview-notes.md).

**Runtime 1.1 update:** fixes the missing `uuid/uuid.h` compilation error by including `uuid-dev`. Existing users can select **Setup → Shut down runtime → Download runtime**, then retry **Build imported source**. This preserves imported files and the build cache; no APK reinstall is needed. [Runtime update details](docs/runtime-release-notes.md).

- [Android preview release](https://github.com/Russianranger/trasc-server-android/releases/tag/preview): install the APK once the Android workflow succeeds.
- [ARM64 runtime release](https://github.com/Russianranger/trasc-server-android/releases/tag/runtime-v1): the app downloads this automatically, or you can transfer `runtime-arm64.tar.gz` for offline installation.
- [Build status](https://github.com/Russianranger/trasc-server-android/actions).

1. Install the APK on an ARM64 Android device (Android 8/API 26 or newer; primary target Android 13 Thor).
2. Open **Setup → Install runtime**. Download it, or select the offline `.tar.gz`. Online downloads verify the release SHA-256 manifest. Offline archives should come from this project's runtime release.
3. **Import server**: the default link is your Triptych fork. Enter a branch, tag or commit and download it. Alternatively choose a complete source ZIP. Public GitHub repositories are supported; private repository authentication is not included in this preview.
4. **Import maps**: enter the actual maps repository/direct HTTPS archive link, or choose its ZIP. No maps are bundled. Archives can contain `base/`, `nav/`, `water/`, `legacy/`, a containing `maps/` directory, and one GitHub wrapper directory. Import the complete maps set before starting. Replaced files are copied to `backups/maps-before-import/`.
5. **Select database**: scan the imported files and choose the full seed. The scanner recognizes `.sql`, `.sql.gz` and SQL members of ZIP files, including `Release-NMS-Server/database/release-peq.zip`. Individual migrations are also visible: choose the **full database**, not one migration. Separate database file uploads use Android's file picker. Replacement requires the explicit replacement checkbox and backs up the old database first.
6. **Builds → Build imported source**. Start with two compiler jobs, connect power and inspect `operation.log`. Deploy the successful build. Builds happen locally and may take considerable time.
7. **Server → Start server**. The initial start creates a backup before upstream schema migrations. Export client data, then use the matching files in your existing modified ROF2/Winlator client.

Reserve at least **12 GB free**, with additional space for large map sets, SQL dumps, preserved source, staged binaries and backups. The app reports available storage and refuses archive entries that will not fit. Uninstalling or clearing app storage removes the local world: export important data first.

## Implemented management flows

The server build/start/export flows below describe the verified **Custom** adapter. Traditional keeps the tabs and management/import controls; its compilation and first-login gates remain pending as described in the profile guide.

| Area | Controls |
| --- | --- |
| Runtime | Online download or offline archive install, open, graceful shutdown, runtime log |
| Source | GitHub link + branch/tag/commit; offline ZIP; exact commit recorded; preserve previous source |
| Maps | GitHub/direct archive or offline ZIP; wrapper detection; backup replaced maps; reversible legacy Nektulos pair |
| Database | Select discovered seed; compressed import; SQL editor; consistent snapshot backup; export/restore |
| Gameplay | All rules in collapsible, searchable categories; source types/descriptions/defaults; field-specific validation; changed-values-only saves; dynamic worker count |
| Server | Start, stop, restart; process status; advertised login/world/UCS IPv4 address |
| Builds | Local CMake/Ninja compilation; staged deployment; previous binary rollback |
| Files | Browse, import, copy, move/rename and export, including individual Nektulos map corrections |
| Client data | Generate/export `spells_us.txt`, `dbstr_us.txt`, `SkillCaps.txt`, `BaseData.txt` as a ZIP |
| Diagnostics | Live command/process logs; export log bundle and sanitized management status |
| Complete sessions | Segmented ZIP with runtime, cold database + SQL snapshot, binaries, maps, logs, source, builds, settings, backups and client; restore before runtime installation |
| Client preparation | ZIP extraction with temporary-copy cleanup; DLL presence/hash; saved gamepad keyboard/mouse bindings and focused input diagnostic |

The gameplay GUI changes SQL rule values. Save settings, then restart so every process reads the same rules. Zone-specific rule overrides still apply. `Zone:StateSavingOnShutdown` gates both saving and loading in this fork; disabling it does not erase saved rows. `Character:RaidExpMultiplier` is a penalty fraction, and the final raid multiplier is separate. The UI preserves tiny values such as the fork's `1e-13` final raid multiplier.

Dynamic **zone worker processes** are configured using the `trasc` launcher and the worker count. Gameplay instances/dynamic-zone records are a separate database concept; the SQL workspace offers table discovery and queries for those records. Missing tables produce a real database error rather than fabricated settings.

## Runtime and storage design

The APK contains the Android Java interface and a pinned ARM64 Android build of PRoot and its loader. Android extracts these packaged executables into the APK's native library directory. A separately downloaded, app-owned Debian Bookworm ARM64 filesystem supplies MariaDB, Python, Git, CMake, Ninja, GCC and the server's development libraries. PRoot translates filesystem access so the glibc server and compiler run within that filesystem without root.

The foreground service and partial wake lock keep normal background imports/builds/server sessions active. Android/OEM force-stop, memory pressure, thermal behavior and filesystem execution restrictions still require device verification. This is a sideloaded preview; no Play Store distribution is claimed.

The WebView loads only APK assets through a blocked-by-default asset handler. It has no general network or filesystem access. A Java bridge talks to an authenticated loopback control daemon. MariaDB uses a separate local port, `13306`, and generated database credentials; the public server address never changes the database host. Credentials and API tokens stay in app-private files. Import only source and SQL you trust: builds run imported code and SQL imports intentionally execute the selected database dump.

The file manager shows paths relative to the private workspace:

```text
sources/current/       imported source + recorded revision
sources/previous/      source before the last update
builds/current/        CMake/Ninja build cache
server/bin/            deployed binaries
server/bin.staged/     successful build waiting for deployment
server/bin.previous/   binary rollback
server/quests/         editable live quests/plugins
maps/                  large map data, separate from source
database/              MariaDB data (use backup/restore)
incoming/              imported archives and files
backups/               database snapshots and map backups
exports/               generated client and log ZIPs
logs/                  runtime, build and process logs
```

Updating source does not overwrite the live quests or database. Copy selected new quest files into `server/quests/` using Files. Replacing a file is explicit: move the old file to a backup path, then copy in the replacement. Database migrations are not reversed by binary rollback; restore the matching database snapshot if necessary. Backups lock database tables while dumping to obtain a consistent snapshot, which can briefly pause gameplay.

The launcher in this fork has a short forced-shutdown path. The manager pauses its restart loop, signals its zone children and allows up to 90 seconds for them to save before shutting down the launcher, world and other processes. Timeout is logged. Test actual zone state survival on the Thor; app force-stop cannot guarantee a save.

## Build configuration

The local server build retains your Lua include/library paths:

```sh
cmake -S Release-NMS-Server -B /work/builds/current -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DEQEMU_BUILD_LOGIN=ON -DEQEMU_BUILD_SERVER=ON \
  -DEQEMU_BUILD_CLIENT_FILES=ON -DEQEMU_PREFER_LUA=ON \
  -DLUA_INCLUDE_DIR=/usr/include/lua5.1 \
  -DLUA_LIBRARY=/usr/lib/aarch64-linux-gnu/liblua5.1.so
```

These are **Debian ARM64 paths inside the app's runtime**, not Android NDK paths. Your server fork supplies `target_include_directories(lua_zone PRIVATE ${LUA_INCLUDE_DIR})`. The imported source must include its bundled dependencies and quests. Arbitrary upstream revisions can introduce incompatible dependencies; failed builds leave current binaries available.

To build the APK on Linux: install JDK 17, Gradle 8.11.1, Android SDK 35/build tools 35.0.0 and NDK 27.2.12479018, then:

```sh
export ANDROID_HOME=/path/to/android-sdk
bash scripts/build-proot.sh
python3 -m unittest discover -s tests -v
gradle :app:assembleDebug :app:lintDebug
```

Build the runtime on an ARM64 Docker host with `bash scripts/build-runtime.sh`. `tests/integration_runtime.py` checks real MariaDB import, rules, SQL and backup/restore inside that image. GitHub workflows build and publish both deliverables. Since 0.1.2, main builds explicitly select and cache the preview key before compiling; the pinned public certificate stops publication if that key is lost or changes. Production signing remains a later release-management step. Release manifests identify each artifact's source commit, checksum and signing certificate, and preview tags follow the published builds.

## Tests and scope

See [device test sequence](docs/device-tests.md). Automated tests cover hostile archive paths, symlink rejection, size limits, nested database discovery, map replacement backups, preservation of runtime edits, rule validation, SQL restrictions and process cancellation. They do not replace physical Android testing.

The Client tab imports an owned ROF2 client and can launch it through the optional client runtime. Configurable AYN gamepad mappings, touch and physical keyboard/mouse reach the embedded display. Native DLL loading is reported only after Wine logs confirm it. ROF2 has reached the world with working models, animations and movement. The optional VirGL path forwards graphics to Android; device GPU behavior, playable performance and sound remain under development. See [client setup and tests](docs/client-runtime.md). No EverQuest client assets or maps are distributed in this repository.

See [third-party notices](THIRD_PARTY_NOTICES.md) for runtime component sources and licenses.

## Complete session backup and restore

Use **Server → Create & export complete session**. The manager stops the embedded client and game server processes, makes a SQL snapshot, stops MariaDB cleanly, closes the runtime and streams a ZIP64 archive. Choose an Android document destination to save it outside the app. The local ZIP remains in `exports/`; the server stays stopped until you open the runtime and start it again.

Preview **0.2.1** fixes backup/restore of Debian multiarch filenames such as `binutils-common:arm64.conffiles`. If a backup fails after shutdown, its error is saved in `logs/app.log` and the runtime stays stopped. Open it again when ready to continue; no database reimport or server recompile is needed.

**Logs → Export log bundle** and the Server tab's log export work even with the runtime closed or unable to start. Log listing and viewing also run directly in Android. Bundles contain complete regular files from `logs/` and `server/logs/`, plus selected imported-client startup diagnostics (`dinput8.log`, `dbg.txt`, and `Logs/dbg.txt`, `dbg.log`, `UIErrors.txt`, `crash.log`, with case-insensitive selection) and native app/device/runtime status; the viewer shows the latest 64 KB per file. Symlinks, settings and API-token files are excluded. A fresh app with no logs can still export its native status. Save the ZIP with Android's document picker.

The ZIP has separate `runtime`, `database`, `binaries`, `maps`, `logs`, `server`, `sources`, `builds`, `backups`, `configuration` and `client` sections. It includes the active runtime and current/previous/staged binaries, live quests, physical database files, the SQL snapshot, source/build caches, Nektulos recovery files and controller profile. It excludes transient `incoming/`, `exports/`, `run/`, host temporary files and the previous session recovery directories. A manifest records the format/architecture and a per-file index records SHA-256 hashes, permissions and symlinks. No client assets are distributed by the project.

On a new compatible ARM64 installation, choose **Setup → Choose complete session ZIP**. Runtime installation is unnecessary. To replace an existing session, enable the replacement checkbox. All files are extracted into a staging directory and verified before activation. The previous work/runtime directories remain as one recovery generation; the next successful restore replaces that generation. Interrupted activation rolls back at the next app launch. The original selected ZIP is untouched; its temporary app copy is deleted after the attempt.

Keep enough space for the imported ZIP, the full extracted session and the existing session. Archives support up to 256 GB unpacked and 200,000 entries. Large map/client/build trees take time. The backup is not encrypted and contains database accounts, credentials and client files: keep it private. Review the advertised login IP after moving devices. Only one TRASC runtime can occupy the local ports.

## Full rule editor

**Gameplay → Load database settings** loads the selected ruleset, inherited default rules and the imported source definitions. Categories are collapsed and fields are created when opened. Search matches names and descriptions. The current pinned server source defines 1,122 rules in 47 categories, including Custom. Definitions from a newly imported revision may differ from still-deployed binaries; build/deploy the matching source when testing newly introduced rules.

The editor enforces boolean/integer/real types, SQL field length, server numeric representation, the XP penalty fraction, documented constraints such as the 2.5 tradeskill minimum, and the source-documented death-loss table index. It does not invent a universal range for every percentage, level or setting containing Min/Max. Source-unknown database rules remain editable text, with their notes shown. Negative disable sentinels and the tiny final raid multiplier are retained. Only modified values are written to the selected ruleset; inherited values are not silently materialized as overrides. Invalid batches list field names and save nothing. A SQL snapshot precedes valid rule writes.

## Reversible Nektulos repair

After importing the complete maps, stop the server and select **Fixes → Nektulos map fix → Apply legacy Nektulos maps**. Both `maps/legacy/base/nektulos.map` and `maps/legacy/nav/nektulos.nav` must exist and be nonempty. Original active files are preserved under `backups/nektulos/<timestamp>/`, then the legacy pair replaces `maps/base/nektulos.map` and `maps/nav/nektulos.nav`. Applying twice retains the original backup. **Revert Nektulos** restores the pair (or removes a destination that was originally absent), preserving intervening edits in another backup. Restart the server after either action. Water files and database spawn elevations are unchanged.

## Client groundwork

Open the runtime, then use **Client → Choose client ZIP**. The archive must contain one Windows `eqgame.exe`; wrapper folders and case variations are recognized. `dinput8.dll` presence/hash is recorded without claiming that it loads. The imported client lives in `client/current`, with one previous client retained. The app deletes only its temporary incoming ZIP after the import attempt; Android's source document is never deleted.

Bindings work without a running Linux runtime. Each gamepad button, trigger, D-pad and stick direction can target a keyboard key, mouse button, pointer direction or wheel step. Profiles include stick deadzone and pointer speed. Two physical inputs sharing a key keep it held until both release. Capture is limited to the client input area; focus loss, leaving Client, disconnection or changing profiles releases held inputs. The same profile also feeds the native Wine display. The diagnostic canvas remains available for checking bindings separately. See [embedded client milestone](docs/client-runtime.md) for setup, launch, diagnostics and current limitations.

Development continuation: [handoff](docs/HANDOFF.md).
