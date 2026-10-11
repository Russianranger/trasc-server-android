# 0.6.24 release and continuation

Status: **0.6.24 / code 73 is qualified, merged and independently verified as published** on October 11, 2026 at 02:08 UTC. Camera reversal is still unresolved on physical Thor; this release adds diagnostics, not a claimed camera fix. This document and `release-proof-0624.json` take precedence over older entries for this continuation.

[Download the verified APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk) — 18,866,614 bytes; SHA-256 `df748f8794aae4e33afe73c3c2eef6018ef77b2c3995112962f6304a37874feb`.

Qualified source: `02a1af7aa8d7a808aafcf4421971a15e9110a8cc`, tree `cef59fa3bd5a1b9f655b9a2d48eec02ec6a53531`, on both `codex/takp-world` and `codex/takp-input-bots-backup-0624`. Preview points to that exact source. [PR #30](https://github.com/Russianranger/trasc-server-android/pull/30) merged as `dab13281d191e94ea06c3e8ad1fcf1f28f08dc6e` with the exact qualified tree. Main subsequently receives these documentation receipts without rebuilding or republishing the APK.

## Recovered state

The repository main at recovery was `a029afaecd6567cfd8309418f0e7c86b7afb9f69`. The qualified 0.6.23 source was `cf6bec71d6f3171de27851d7df625cf84da096f8`; PR #29 was merged as `342efe9d93a577fc91f1a85461a12c3369962ba7`. App qualification run `38081870434` succeeded. The existing preview APK SHA-256 was `0bd0081eefeb44eeb72a2f54491355409d79eb9cbbbd8f8e24a8dd530feefe57`, with the established signing certificate unchanged. See `release-status-0623.md` and `release-proof-0623.json`.

The current accessible launcher checkout had no unfinished changes or active build at the start of this continuation. The earlier native workspace `/workspace/scratch/68f7303215aa` was unavailable; its possible unpublished work cannot be recovered or assumed. The accessible 0.6.23 release artifacts, qualification records and source history were recovered. A fresh isolated TAKP native checkout was based on the exact deployed server revision.

The uploaded 0.6.23 device log bundle confirms native-surface relative input and V2 helper installation/loading. It records aggregate input counts, but neither the game consumer's actual DirectInput contract nor Yaulp casting state. It does not establish a camera root cause or prove a missing unpublished APK.

## Completed implementation

- Camera reversal remains unresolved on the physical Thor. Keep V2 delivery unchanged and add bounded Wine-only diagnostics for actual format/axis mode, state and buffered reads, queue age, clip/focus/button gates and game-consumer fields. Qualify the actual production TRASCIN1/XFlush input path, both axis modes, custom formats, bounded/peek consumers and controller cadence. These are diagnostic changes, not an asserted camera fix.
- Correct the proven TAKP idle-Yaulp scheduling defect in native server source `03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167`, Servertakp PR #2. All six seed ranks become combat buffs attempted during permitted melee after higher-priority healing, curing and crowd control. Existing data and manual casts are preserved. The new recipe requires explicit source update, build and deployment; no automatic replacement of existing compiled servers.
- Expose 23 supported native bot actions in both Custom and Traditional with multi-select character/social/hotbar export. Keep TAKP's 39 actions. Modern spawn-and-group remains the default; combined spawn-only is an additional choice. Native modern profiles do not expose a revive command, so none is invented. See `modern-bot-commands-0624.md`.
- Add a single streaming, ZIP64 backup for all three profile snapshots plus device controls, overlay positions, appearance and active profile. Choose the SAF destination before export. Import verifies included data in staging before an all-component journaled activation; omitted profiles/runtime/work trees are kept, and replaced trees are retained under a transaction recovery directory. Support cancellation before activation, operation exclusion, foreground lifecycle protection and explicit space/error reporting.

## Preservation and acceptance

Re-use the independently verified 0.6.23 native launcher payload and signing identity. Preserve runtime installations, databases/bots/characters, server binaries and receipts, imported clients/Wine prefixes, controller mappings, renderer options and personal settings. No destructive fresh installation, schema conversion or speculative NPC/StoneUI repair is part of this update.

`device-acceptance-0624.md` contains the exact device checklist and deployment prerequisites. TAKP NPC visibility and Traditional StoneUI remain separate tracked concerns. Do not claim physical camera or large-archive Android acceptance from host tests.

## Qualification / publication

The single coordinated EQW helper run `38102758503` succeeded on exact recipe `f6f354b41d41cf93fc4d2d0672c183771856083f`. The integrated 93,696-byte DLL SHA-256 is `495d6e1711e21f012d1f8c9581af74fdbdccac5f45e2e93508e40b4bd3dbca1d`; see `takp-camera-0624.md` and the preserved receipts. Local Python run completed 505 tests with 22 database fixtures skipped because this host lacks MariaDB. Coordinated CI ran all 505 successfully with zero skips. DirectX extraction/preservation qualification passed.

Native server PR qualification `38102400606` succeeded, including full x86_64 and AArch64 builds, standalone player-bot/Yaulp regressions and disposable MariaDB migrations. Production Bookworm integration also passed in the coordinated app run. [Servertakp PR #2](https://github.com/Russianranger/Servertakp/pull/2) merged as `b28b529e857784def1671b3d2759d0a7ac6c0084`, retaining exact source tree `1785e3039a216cd8a220de26c51aaefc73101e2d`. The launcher stays pinned to the qualified source commit, not an unverified moving branch.

Final all-profile host qualification passed on the exact sources recorded in `all-session-qualification-0624.json`: 190,000 real-file round trip, 87,000 long-name/link records with a 58,256,144-byte index, and a payload larger than 4 GiB all completed under a 96 MiB Java heap. The normal management suite, legacy single-profile round trip, staged verification and transaction recovery checks also passed. Physical Android SAF/lifecycle testing remains outstanding.

All five jobs in [38103647834](https://github.com/Russianranger/trasc-server-android/actions/runs/38103647834) passed: APK, TAKP production, Custom native bots, Traditional native bots and preview publication. Android assembly, JVM and every browser fixture passed. Lint had zero errors and 37 warnings. New all-profile and modern-command flows passed at 1280 and 393 pixels, including picker cancellation, 64-bit progress, operation exclusion, restore receipts and persistence after later theme edits; screenshots were visually reviewed.

TAKP production qualification passed all 14 checks, including actual imported standalone bot/Yaulp tests (six seed ranks, 18 scheduling/gate/priority checks), full Bookworm build, nine ELF dependency checks, migrations, login/world/dynamic-zone startup, client exports and shutdown. Both modern profiles passed 28 native preservation/creation/retry/rollback checks and reused their existing qualified compiler/recipe caches. No competing app job was launched.

The actual published APK, source archive, build manifest and native receipt were independently downloaded. Verification passed package `io.github.russianranger.trasc.preview`, version/code, APK CRC and signature, unchanged certificate `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`, all 112 bundled source assets, all 522 exact archived source files, the actual diagnostic DLL and all 21 native components equal to the verified 0.6.23 APK. The source archive is 237,596,196 bytes, SHA-256 `8dcb8138f21c80c0056e2734d97952834e2c3a9a17f92a9c3997d8ad69f5a5d9`; it preserves the exact 0.6.23 source archive inside. `release-proof-0624.json` records asset IDs, public digests, commits, merges, CI jobs, receipts and verification.

## Remaining work

Move directly to `device-acceptance-0624.md`. Install as an update without uninstalling, checkpoint all worlds externally, collect a short fresh Thor camera trace, explicitly update/build/deploy TAKP for the Yaulp policy, then qualify all-world command execution/persistence and real large SAF export/import. Host tests and server NPC/wire evidence do not prove physical camera, Android provider/memory behavior or NPC rendering. Keep TAKP NPC visibility and Traditional StoneUI separate; no speculative changes were made.

The inherited launcher footer still displays Preview 0.6.23. Android package metadata independently verifies 0.6.24/code73; use Android app information and the release digest for identification. This cosmetic label was retained without an additional rebuild and should be corrected during the next necessary code change.

No unfinished implementation or active owned build/test process remains. The current release needs no repeat build. Repository-backed receipts are durable; previous inaccessible scratch work remains unknown.
