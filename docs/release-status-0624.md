# 0.6.24 qualification and continuation

Status: implementation and qualification in progress; the latest independently verified published APK is still **0.6.23 / code 72**. Do not describe this draft as a published release. This document and the eventual 0.6.24 proof take precedence over older handoff entries only for the work described here.

## Recovered state

The repository main at recovery was `a029afaecd6567cfd8309418f0e7c86b7afb9f69`. The qualified 0.6.23 source was `cf6bec71d6f3171de27851d7df625cf84da096f8`; PR #29 was merged as `342efe9d93a577fc91f1a85461a12c3369962ba7`. App qualification run `38081870434` succeeded. The existing preview APK SHA-256 was `0bd0081eefeb44eeb72a2f54491355409d79eb9cbbbd8f8e24a8dd530feefe57`, with the established signing certificate unchanged. See `release-status-0623.md` and `release-proof-0623.json`.

The current accessible launcher checkout had no unfinished changes or active build at the start of this continuation. The earlier native workspace `/workspace/scratch/68f7303215aa` was unavailable; its possible unpublished work cannot be recovered or assumed. The accessible 0.6.23 release artifacts, qualification records and source history were recovered. A fresh isolated TAKP native checkout was based on the exact deployed server revision.

The uploaded 0.6.23 device log bundle confirms native-surface relative input and V2 helper installation/loading. It records aggregate input counts, but neither the game consumer's actual DirectInput contract nor Yaulp casting state. It does not establish a camera root cause or prove a missing unpublished APK.

## Current scope

- Camera reversal remains unresolved on the physical Thor. Keep V2 delivery unchanged and add bounded Wine-only diagnostics for actual format/axis mode, state and buffered reads, queue age, clip/focus/button gates and game-consumer fields. Qualify the actual production TRASCIN1/XFlush input path, both axis modes, custom formats, bounded/peek consumers and controller cadence. These are diagnostic changes, not an asserted camera fix.
- Correct the proven TAKP idle-Yaulp scheduling defect in native server source `03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167`, Servertakp PR #2. All six seed ranks become combat buffs attempted during permitted melee after higher-priority healing, curing and crowd control. Existing data and manual casts are preserved. The new recipe requires explicit source update, build and deployment; no automatic replacement of existing compiled servers.
- Expose 23 supported native bot actions in both Custom and Traditional with multi-select character/social/hotbar export. Keep TAKP's 39 actions. Modern spawn-and-group remains the default; combined spawn-only is an additional choice. Native modern profiles do not expose a revive command, so none is invented. See `modern-bot-commands-0624.md`.
- Add a single streaming, ZIP64 backup for all three profile snapshots plus device controls, overlay positions, appearance and active profile. Choose the SAF destination before export. Import verifies included data in staging before an all-component journaled activation; omitted profiles/runtime/work trees are kept, and replaced trees are retained under a transaction recovery directory. Support cancellation before activation, operation exclusion, foreground lifecycle protection and explicit space/error reporting.

## Preservation and acceptance

Re-use the independently verified 0.6.23 native launcher payload and signing identity. Preserve runtime installations, databases/bots/characters, server binaries and receipts, imported clients/Wine prefixes, controller mappings, renderer options and personal settings. No destructive fresh installation, schema conversion or speculative NPC/StoneUI repair is part of this update.

`device-acceptance-0624.md` contains the exact device checklist and deployment prerequisites. TAKP NPC visibility and Traditional StoneUI remain separate tracked concerns. Do not claim physical camera or large-archive Android acceptance from host tests.

## Qualification / publication

The single coordinated EQW helper run `38102758503` succeeded on exact recipe `f6f354b41d41cf93fc4d2d0672c183771856083f`. The integrated 93,696-byte DLL SHA-256 is `495d6e1711e21f012d1f8c9581af74fdbdccac5f45e2e93508e40b4bd3dbca1d`; see `takp-camera-0624.md` and the preserved receipts. Local Python regressions: 505 passed with 22 database fixtures skipped because this host lacks MariaDB; the coordinated CI must run those fixtures. DirectX extraction/preservation qualification passed.

Native server PR qualification `38102400606` succeeded, including full x86_64 and AArch64 builds, standalone player-bot/Yaulp regressions and disposable MariaDB migrations. The PR remains open pending the production Bookworm integration.

Final all-profile host qualification passed on the exact sources recorded in `all-session-qualification-0624.json`: 190,000 real-file round trip, 87,000 long-name/link records with a 58,256,144-byte index, and a payload larger than 4 GiB all completed under a 96 MiB Java heap. The normal management suite, legacy single-profile round trip, staged verification and transaction recovery checks also passed. Physical Android SAF/lifecycle testing remains outstanding.

Complete production native integration and Android packaging/signature verification are pending. Do not merge or republish on the basis of this draft. Update this section and add an exact release proof after successful qualification and independent download verification.
