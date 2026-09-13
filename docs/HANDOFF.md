# Development handoff — 2026-09-13

## Current request

Latest device report: Preview 0.2.0 session export fails with `Unsafe session path: runtime/var/lib/dpkg/info/binutils-common:arm64.conffiles`. Log export then fails with `Failed to connect to /127.0.0.1:18775`, because backup preparation closed the runtime. Fix both and publish an in-place APK update; preserve the existing world and signing key.

### 0.2.1 fix in progress

- Base: `fe84687345bcb4328ec6ab85a71c453829bd2073` (handoff after the published 0.2.0 code).
- `SessionArchive.confined` accepts ordinary Linux colons and still rejects drive prefixes, traversal, absolute paths, backslashes and NULs. Both export and restore share the fix.
- New platform-independent `LocalLogs` reads/lists/zips app and nested server logs without a backend; checks symlink parents/leaves, tails 64 KB for viewing and streams full snapshot lengths into bundles. Native status is included without loading credentials/settings/API tokens.
- MainActivity routes logs/export_logs directly to Android. Both UI log export buttons now consume the direct result instead of polling Python jobs. Backup failure persists to app.log and explicitly reports stopped-runtime recovery. The game server is not automatically restarted.
- Version 0.2.1 / code 5, same application ID and pinned certificate. No new runtime or server rebuild required.
- Local checks: 29 Python tests passed; native host-JVM roundtrip/log regressions passed; JavaScript syntax and whitespace checks passed. CI now also backs up/restores the complete published Debian ARM64 runtime, verifying every file hash; UI regression simulates backup failure with backend unavailable and tests both log buttons and readers.
- Publication and CI outcome will be recorded below after the build. Physical Thor acceptance is pending.

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

## Progress

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
