# 0.6.23 release recovery and continuation

## Recovery and scope

The recovery independently verified the published 0.6.22 / code 71 APK, source
manifest, signing certificate, all 21 reused native payloads and managed EQW
helper. Main was d749e82c3e017c87f6e3cd3470861237389c27a6, the qualified
feature/tag was 25fb54cf86d9b4b15b121bc199b44375a6810e74, PR #28 was merged
and run 38039299622 succeeded. No unfinished launcher checkout, stash or active
local build was found in the accessible workspace. The older related Servertakp
checkout was clean and preserved. An inaccessible previous-agent private
workspace could not be recovered and is not evidence of an unpublished build.

The user's Thor test confirmed TAKP bots worked and supplied new evidence of
camera veering plus a request for combined spawn/revive buttons and additional
command export. These changes justified 0.6.23. Existing 0.6.22 bot generation,
storage safeguards, overlay controls and installed data were not reimplemented.

## Qualified source and publication

- Version: 0.6.23 / code 72; app package io.github.russianranger.trasc.preview.
- Release source: cf6bec71d6f3171de27851d7df625cf84da096f8.
- Feature branches: codex/takp-world and codex/takp-controls-socials-0623.
- PR: https://github.com/Russianranger/trasc-server-android/pull/29.
- PR #29 merged at 2026-10-10 20:10:19 UTC; release merge
  342efe9d93a577fc91f1a85461a12c3369962ba7 has the exact qualified source tree.
- Android qualification: https://github.com/Russianranger/trasc-server-android/actions/runs/38081870434.
- All five jobs succeeded: APK, TAKP production integration, Custom native bots,
  Traditional native bots, and preview publication. No duplicate app build ran.
- Preview tag points to cf6bec71d6f3171de27851d7df625cf84da096f8.
- Published APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk.
- APK asset 628886437: 18,833,650 bytes, uploaded 2026-10-10 20:08:27 UTC,
  SHA-256 0bd0081eefeb44eeb72a2f54491355409d79eb9cbbbd8f8e24a8dd530feefe57.
- Update certificate SHA-256: ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869.

The public APK was downloaded independently: its signature verifies, aapt reports
the expected package/version/code, all 112 bundled source assets match, and the
camera helper and provenance checks pass. All 21 reused native components equal
the independently verified 0.6.22 APK byte for byte. The public source archive
contains all 504 exact qualified source files and the exact preserved 0.6.22
source archive. Full asset metadata is in docs/release-proof-0623.json.

Public launcher-sources.tar.gz asset 628886445 is 227,707,998 bytes with SHA-256
941374d293e92d3a31b0eccc6fdeb09143294266ab2338ea15fc049de19ceaeb.
Native reuse asset 628886436 has SHA-256
201b1d7c40864490e4eb48ce463e195cbf3effddecf262ff95f4db7bcf23241e.
Build manifest asset 628886446 has SHA-256
8ceccfb74c20f3b441f3f5948086c850de39b6447b0189576a9da5a8dc4c0076.

Main's post-release handoff commit changes documentation and restores the
verifier script's existing executable bit; its script content is unchanged.
It does not require another APK build. Read this release-specific report and
the 0.6.23 guides before older HANDOFF entries. Keep preview on the qualified
source, rather than moving it to a documentation commit.

## Camera evidence

Qualified camera recipe: 202ff0d995b45302d8cfb6a78e47ceea87a5b965 on
codex/takp-eqw-0623. Final Windows build and real Wine10/Xvnc fixture both
succeeded in https://github.com/Russianranger/trasc-server-android/actions/runs/38081609076.
The actual EQW DLL is 87,552 bytes with SHA-256
c103e024f1cde7829603475e1532d3baabd0764280c63ca2797e7e72569554f4.
Upstream EQW stays pinned to 3b4d43562c9dacc89349185684bb0bf0b01f9d06.

The old helper produced positive polled/buffered X motion while the fixture
injected negative X motion, and unintended X motion during pure Y input. The
new helper matched all 12 cardinal/diagonal reversal sequences exactly in both
DirectInput APIs, including 6,400 pixels beyond desktop edges, zero idle drift,
focus re-entry, swapped buttons and physical release without reacquisition.
The fixture uses the production Wine virtual desktop and independently checks
Windows/X focus and physical confinement. Initial standalone/incorrect release
coordinate fixtures failed; none of those candidates was packaged or published.

Exact compiled source, patch hashes, actual DLL receipt and fixture/run hashes
are preserved in the repository and packaged for verification. Clipping is
limited to Wine mouse look and restores prior ownership on release, focus or
login transitions. Native Windows, Android gain/mappings and other helper DLLs
are preserved. Managed original/V1 upgrades retain the first available original
backup and separately retain the official 0.6.22 helper. Custom helpers or
changed/symlink backups are refused before replacement.

## Bot command export

The GUI offers 39 commands from the pinned TAKP native implementation, grouped
under Party, Behavior, Magic and Reports. Default Spawn party and separate
Revive party buttons name every selected owned companion. Five names fit in
one native social; selections up to 20 split explicitly into numbered socials.
No names are silently dropped and the server's active/group cap remains.
There is no native revive-all command; named lines implement the selected party.

Revive is out-of-combat, fallen/inactive, at least 60 seconds after the recorded
fall, one HP and zero mana. Revive then spawn. It is separate from resurrection
of a player corpse. Target/class restrictions remain native server checks.

INI export is previewed, revision checked and atomic. File-changing installs
make backups; occupied socials/hotbars, personal settings, encoding/comments,
legacy receipts and restore protections are retained. Modern world export and
offline creation are unchanged. The working TAKP server needs no rebuild.

## Qualification and next work

Local Python ran 495 cases with 30 dependency/database cases skipped. CI ran and
passed all 495 with no skips. Native/JVM management checks, 36 focused social
cases, all browser suites and Android build/lint/signing passed. Phone and
landscape command-export screenshots were independently reviewed without
blocking issues. Android lint has no errors; existing warnings remain.

TAKP production integration passed all 13 checks, including the complete seed,
11 bot migrations, accounts, real zone startup, native spawn wire layout, client
exports and preservation of an existing database/custom workspace. Both modern
native fixtures passed real creation, database restart/reload/idempotent retry,
and 17 refusal/rollback cases per profile. Owner inventories, shared banks,
native starting items/stats, quest hooks and command settings were preserved.
Traditional's necessary schema repair retained legacy bot rows after a complete
backup. Their native build caches reported no work to do; server pins and
installed-device build/runtime receipts remain unchanged.

Physical Thor acceptance is outstanding. Follow docs/device-acceptance-0623.md
for camera axes/reversals/touch/controller, gear/tile placement, selected-party
spawn/revive, multi-command export, hotbar persistence and backup/refusal checks.
Custom/Traditional offline generation still needs their qualified server utility
if it is absent from the installed deployment; preserve databases and runtime.
Use full-backup storage review before necessary conversion, per the 0.6.22 guide.

TAKP NPC visibility and Traditional StoneUI remain separate tracked concerns.
No speculative changes were made for either. Do not reset imports, prefixes,
servers, profiles, controller mappings, renderer settings or existing bots.
Do not start a new build unless fresh device evidence identifies a defect.
