# TRASC Server for Android

A standalone Android control app for [Russianranger/Triptych-Triumvirate](https://github.com/Russianranger/Triptych-Triumvirate), initially targeting the AYN Thor's ARM64 Android environment. The app owns its runtime, database, source, builds and server files. It does **not** require installing Termux, root, a PC-hosted server or a web service.

**Status: first implementation / device testing preview.** The code includes the management flows below. Physical Thor execution and full server/client gameplay have not yet been validated. Android restrictions, PRoot compatibility, server dependencies and thermal limits must be checked with the device test plan before calling it a working replacement for your current setup.

## Downloads and first setup

**App 0.1.2:** fixes MariaDB initialization failing to resolve `localhost` and the seed's nonzero default ruleset. The original preview signing key was not preserved. This build installs alongside it as **TRASC Server Preview**, keeping the old app and data intact. Export the original source/maps ZIPs, shut down the old runtime, and import them into the new preview after its runtime setup. [Migration and update details](docs/preview-notes.md).

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

| Area | Controls |
| --- | --- |
| Runtime | Online download or offline archive install, open, graceful shutdown, runtime log |
| Source | GitHub link + branch/tag/commit; offline ZIP; exact commit recorded; preserve previous source |
| Maps | GitHub/direct archive or offline ZIP; wrapper detection; backup replaced maps |
| Database | Select discovered seed; compressed import; SQL editor; consistent snapshot backup; export/restore |
| Gameplay | Rule-set selection; XP, AA, group and raid multipliers; zone state persistence; dynamic worker count |
| Server | Start, stop, restart; process status; advertised login/world/UCS IPv4 address |
| Builds | Local CMake/Ninja compilation; staged deployment; previous binary rollback |
| Files | Browse, import, copy, move/rename and export, including individual Nektulos map corrections |
| Client data | Generate/export `spells_us.txt`, `dbstr_us.txt`, `SkillCaps.txt`, `BaseData.txt` as a ZIP |
| Diagnostics | Live command/process logs; export log bundle and sanitized management status |

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

The modified ROF2 client, `dinput8.dll`, Wine/Winlator integration and AYN controller mapping are deliberately deferred to the client phase. The first acceptance target is the standalone server and management GUI, connected to your current client. No EverQuest client assets or maps are distributed in this repository.

See [third-party notices](THIRD_PARTY_NOTICES.md) for runtime component sources and licenses.
