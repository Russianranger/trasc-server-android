# Development handoff — 2026-09-13

## Current request

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

- Feature implementation is present locally: `rule_catalog.py`, `managed_content.py`, expanded Engine; native `SessionArchive`, `ControllerInput`, `ControllerManager`; RuntimeManager/MainActivity integration; rules/client UI and docs.
- APK version 0.2.0 / code 4; application ID/signing unchanged. Runtime 1.1 remains compatible.
- Local Python: 29 tests passed (including detection of map edits/imports after Apply). Host JVM archive/input tests passed (the local javac launcher is missing, but `java -m jdk.compiler/com.sun.tools.javac.Main` works; script includes fallback).
- Source parsing found all 1,122 active rules, 47 categories; no definitions missed. Static JS syntax and HTML-ID checks passed.
- Expanded ARM64 integration now checks all-rule visibility, escaped values, invalid-batch atomicity, clean snapshot/shutdown and cold physical database migration. The ARM64 job in workflow 34770980656 passed these checks, including the actual full seed import and cold database restore.
- Workflow 34770980656 passed backend tests, host JVM session/input tests, browser UI checks, ARM64 integration, APK compilation/lint and the pinned signing check. Its feature commit is `0eef6dcef9278d4881071d2681af1dd7fe9c8fd3`. A small follow-up adds explicit detection of maps changed since Apply; its final build/release still needs verification. No new device acceptance claimed.
- Browser tests ran successfully in CI with Playwright 1.55.0. They cover 1,105 fixture rules, collapsed/lazy categories, tiny/negative values, bounds errors, changed-only saves, controller binding save and capture release, and mobile horizontal overflow. UI screenshots are in the workflow artifact `management-ui-reports`; downloading its temporary file URL locally returned HTTP 403, so do not claim manual screenshot inspection.
- Session archive excludes incoming/exports/run; includes rootfs, database, binaries, maps, logs, server data, source, builds, backups, configuration and client. Native restore works without Python and stages/validates before swapping. Previous session stays in work-session-previous/rootfs-session-previous.
- Physical Android acceptance still pending: in-place update, rule editing, Nektulos apply/revert and complete session migration. Client execution remains unimplemented by design; controller input is a diagnostic/future injection boundary.

## Verification and release

Update this section with actual commands/results and final commit/workflow/APK details before handoff. Device tests for the new features remain pending until the user reports results.
