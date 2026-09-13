# Development handoff — 2026-09-13

## Current request: embedded client (0.3.0 in progress)

The user confirmed: “Session backup and restore worked perfectly. control inputs work, client input works. Lets move to the next step with the client.” Latest bundle `logs-338733800756477711.zip` reports 0.2.1 on Thor Android 13, completed client ZIP import, and no current runtime-start failure. Do not redo server/database installation.

- Working branch: `codex/client-bootstrap`; main remains the tested 0.2.1 handoff commit `23f8421f59b37254a602464157d081cf43372b2c` until gates pass.
- Client runtime: separate Debian rootfs in `work/client/runtime`, Wine 10.0 WoW64 + Box64 0.4.4, WineD3D/llvmpipe baseline, TigerVNC display over private Unix socket. No TCP VNC listener; X11 cookie authentication.
- New files: `ClientRuntime`, `ClientActivity`, `RfbConnection`, `DisplayInput`, `backend/client_runner.py`, `client-runtime/Dockerfile`, client runtime build workflow/script and native Windows probe/integration tests.
- Existing controller profile reaches actual native display; physical keyboard/mouse/touch also wired. Dialog Type/Send + Enter, focus-release and combined-input reference counts implemented. Client runtime/prefix are included by existing complete-session client component; temporary sockets live outside the archive. Backup/restore stops client first.
- Client GUI includes online/offline runtime setup, Wine desktop, ROF2 launch, return/stop and server-data preparation. Preparation preserves original handshake/INI files and imported DLL; native trace is required to claim DLL load.
- Runtime CI first failed on missing x86 `libgcc_s.so.1`; graphics/display already passed startup. Added Debian amd64 libgcc/libstdc++/libunwind plus Box64 library path. Run 34787655979 now executes PE32, loads the native test DLL and creates a D3D9 device. Corrected the display test to wait for successful Present and ignore the undefined RGB888 padding byte. Full feature checkpoint `38906ea34ce84fcd1f79477b55557f6d7088f3a4` passed real PE32/native-DLL/D3D9 pixels/input in ARM64 run 34788312176. APK/UI/database run 34788312260 is pending; the following checkpoint also adds full client-runtime archive roundtrip verification before publication.
- Initial local validation: 34 Python tests passed, native JVM archive/RFB/input tests passed, JS syntax passed. APK/UI/ARM64 full client probe checks still pending for the complete feature checkpoint.
- Client documentation: `docs/client-runtime.md`; first physical goal Wine desktop, then ROF2 startup/login with native dinput8 trace. Software graphics only; sound and hardware acceleration remain later work. Do not claim actual ROF2 acceptance until user reports it.
- Preserve the existing application ID and pinned signing certificate. Target APK 0.3.0 / version code 6. Server runtime remains 1.1. Update this section with final code/run/artifact identifiers once published.

## Previous request: 0.2.1 export fixes

Latest device report: Preview 0.2.0 session export fails with `Unsafe session path: runtime/var/lib/dpkg/info/binutils-common:arm64.conffiles`. Log export then fails with `Failed to connect to /127.0.0.1:18775`, because backup preparation closed the runtime. Fix both and publish an in-place APK update; preserve the existing world and signing key.

### 0.2.1 fixes published

- Base: `fe84687345bcb4328ec6ab85a71c453829bd2073` (handoff after the published 0.2.0 code).
- `SessionArchive.confined` accepts ordinary Linux colons and still rejects drive prefixes, traversal, absolute paths, backslashes and NULs. Both export and restore share the fix.
- New platform-independent `LocalLogs` reads/lists/zips app and nested server logs without a backend; checks symlink parents/leaves, tails 64 KB for viewing and streams full snapshot lengths into bundles. Native status is included without loading credentials/settings/API tokens.
- MainActivity routes logs/export_logs directly to Android. Both UI log export buttons now consume the direct result instead of polling Python jobs. Backup failure persists to app.log and explicitly reports stopped-runtime recovery. The game server is not automatically restarted.
- Version 0.2.1 / code 5, same application ID and pinned certificate. No new runtime or server rebuild required.
- Local checks: 29 Python tests passed; native host-JVM roundtrip/log regressions passed; JavaScript syntax and whitespace checks passed. CI now also backs up/restores the complete published Debian ARM64 runtime, verifying every file hash; UI regression simulates backup failure with backend unavailable and tests both log buttons and readers.
- Published code commit / preview tag: `e61761bd0ea725061ffcd2305ff82edd158b1cdc`. This handoff-only follow-up changes no APK code.
- Successful workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34780884423 — database, APK and preview jobs all passed.
- Actual runtime roundtrip passed using the production TarExtractor/SessionArchive classes: more than 28,000 regular files restored with SHA-256 verification, plus inventory counts and executable-mode checks. The exact `binutils-common:arm64.conffiles` path roundtripped.
- ARM64 full seed import, rules/SQL checks and cold database migration passed. Browser tests passed both native log export buttons and nested log reading after a simulated session failure with the backend unavailable. APK compilation, Android lint and the pinned-certificate check passed.
- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — **225,637 bytes**, SHA-256 `5667d5fc697cc48f347b2952b5065c8405083c3ad0aeae652a7fffa66136a2aa`. Release asset and preview tag were read back from GitHub after publication.
- Runtime 1.1 and the pinned signing certificate remain unchanged. Physical Thor acceptance is pending; ask the user to start with log export while closed, then complete session export/restore. No reset, recompile or database reimport is required for this APK update.

## Previous feature request (retained context)

Implement in `Russianranger/trasc-server-android`:

1. All database rules in searchable, collapsible categories, with typed controls and field-specific validation for established limits.
2. Setup actions to back up and replace `maps/base/nektulos.map` and `maps/nav/nektulos.nav` from their matching `maps/legacy/` paths, and revert the pair.
3. Complete session ZIP export/import, usable by a fresh app before runtime installation. Include runtime, database, binaries, maps, logs, source, settings and client files. Preserve permissions/symlinks and validate before replacement.
4. Client tab, client ZIP import with removal of only the app's temporary ZIP copy, and configurable gamepad-to-keyboard/mouse input groundwork. Client execution/Wine/dinput8 loading is a later phase, not an acceptance claim for this build.
5. Publish a test APK and keep this handoff current.

The user explicitly declined any faction/deity change. Yukovis was a disposable Iksar beastlord testing login/persistence; Prexus (209) explained Cabilis hostility. Do not change the server fork or seed for that issue.

## Starting state and verified device progress

- Main starts at `f9dfa3ee14c7f0d4655780743a4967e24911c0d2`, app 0.1.2 / runtime 1.1.
- User confirmed on-device compilation, connection and character testing on AYN Thor Max, Android 13 ARM64.
- Runtime 1.1 includes uuid-dev. APK 0.1.2 fixes offline MariaDB initialization and nonzero default ruleset IDs.
- Current server source: `Russianranger/Triptych-Triumvirate` commit `18141ae0c9a11813733f08fa77db986951b853d6`.
- Preview application ID must stay `io.github.russianranger.trasc.preview` for in-place updates.
- Preserve the signing certificate pinned in `docs/preview-signing.sha256`. GitHub Actions cache `trasc-preview-signing-v2` contains `runtime-work/signing/preview.keystore`. Never generate a replacement key if the cache is missing.
- Main's Android workflow tests ARM64 MariaDB, builds/lints APK and publishes the preview release automatically after all gates pass.

## Implementation decisions

- Read every applicable `rule_values` row and source `common/ruletypes.h`; do not infer numeric bounds merely from a name containing Min/Max. Preserve sentinel negatives and very small XP multipliers.
- Nektulos layout comes from the server README: legacy/base → base, legacy/nav → nav. Do not copy files directly into the maps root or change water files.
- Native Android session archive is needed because a new installation has no Python/runtime yet. Stop server/database cleanly; stage and verify all files before swapping app data. No source ZIP deletion outside the app's private staging copy.
- Input mappings belong only to a focused client surface. Release held inputs on focus loss/tab change, disconnection or profile change. The initial surface is an input diagnostic; no game launch is advertised.

## Previous feature implementation: 0.2.0

- Feature implementation is committed and published: `rule_catalog.py`, `managed_content.py`, expanded Engine; native `SessionArchive`, `ControllerInput`, `ControllerManager`; RuntimeManager/MainActivity integration; rules/client UI and docs.
- APK version 0.2.0 / code 4; application ID/signing unchanged. Runtime 1.1 remains compatible.
- Local Python: 29 tests passed (including detection of map edits/imports after Apply). Host JVM archive/input tests passed (the local javac launcher is missing, but `java -m jdk.compiler/com.sun.tools.javac.Main` works; script includes fallback).
- Source parsing found all 1,122 active rules, 47 categories; no definitions missed. Static JS syntax and HTML-ID checks passed.
- Expanded ARM64 integration now checks all-rule visibility, escaped values, invalid-batch atomicity, clean snapshot/shutdown and cold physical database migration. The ARM64 job in workflow 34770980656 passed these checks, including the actual full seed import and cold database restore.
- Final workflow **34771227274** passed all gates and published the APK from **bf9c8d718f177c08af6c0bd1036c9e4d249a85c8**. This includes detection of map edits/imports after Apply: revert first, preserving intervening files. No new device acceptance claimed.
- Browser tests ran successfully in CI with Playwright 1.55.0. They cover 1,105 fixture rules, collapsed/lazy categories, tiny/negative values, bounds errors, changed-only saves, controller binding save and capture release, and mobile horizontal overflow. UI screenshots are in the workflow artifact `management-ui-reports`; downloading its temporary file URL locally returned HTTP 403, so do not claim manual screenshot inspection.
- Session archive excludes incoming/exports/run; includes rootfs, database, binaries, maps, logs, server data, source, builds, backups, configuration and client. Native restore works without Python and stages/validates before swapping. Previous session stays in work-session-previous/rootfs-session-previous.
- Physical Android acceptance still pending: in-place update, rule editing, Nektulos apply/revert and complete session migration. Client execution remains unimplemented by design; controller input is a diagnostic/future injection boundary.

## Previous release: 0.2.0

Published **0.2.0**, version code **4**, on 2026-09-13.

- Code commit / preview tag: `bf9c8d718f177c08af6c0bd1036c9e4d249a85c8`. This handoff-only update follows it; no APK code changes accompany these notes.
- Final successful workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34771227274
- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk
- APK size: **221,721 bytes**. GitHub release asset SHA-256: `1627425c11235269cbf629fc1107ddc4d349afe2e2ccb8a1c21480c93d351a98`.
- Pinned certificate: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; APK verification passed in CI before publication.
- `python3 -m unittest discover -s tests -v`: **29 passed**.
- `bash scripts/check-management.sh`: passed JVM archive/input checks.
- `node tests/ui_management.cjs`: passed browser management-flow checks in CI.
- ARM64 database job: reproduced original hostname failure, imported the full pinned seed offline, then passed rule inheritance/editor validation, SQL/backup/restore and cold physical database migration.
- `gradle --no-daemon :app:assembleDebug :app:lintDebug`: passed; stable-signature verification and preview publication passed.
- Preview tag and final APK release asset were read back from GitHub to verify the published commit and checksum.

## Next user/device pass

1. Install 0.2.1 over the existing Preview; follow the export regression pass in `docs/device-tests.md` first, starting with logs while the runtime is closed. No server rebuild/database reimport is needed.
2. Test categorized rules, field validation and value persistence.
3. Stop the server; test Nektulos Apply/Revert (then Apply again if desired).
4. Create and externally save a complete session ZIP, then test restoration while retaining the working installation/external backup. Review login IP and check the character/world through the existing Winlator client.
5. Investigate any returned support bundle against `docs/device-tests.md`.
6. Client import/input groundwork is delivered; user explicitly deferred client tests. Actual Windows client execution, rendering and dinput8 loading remain the next development phase.

Do not claim the new features have passed physical-device acceptance until the user reports results.
