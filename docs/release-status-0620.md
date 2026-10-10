# TRASC 0.6.20 / code 69 — Grouped controls and ARM64 spawn qualification

Seven launch buttons now align in labeled Runtime, Server and Client groups. On landscape/wide screens they share one row; narrow phones use compact grouped rows. Stacked labels, equal button heights and dividers distinguish the groups across all worlds and themes.

The latest Thor logs record all 156 Paineel NPC creations. The user reports NPC dialogue and doors opening while models remain invisible. These observations establish server-side activity, but do not prove that NPC spawn packets reached the client. **NPC visibility remains unresolved; this release does not include an NPC visibility fix.**

## Published build

- [PR #26](https://github.com/Russianranger/trasc-server-android/pull/26), merged at `f5c89b34d79d8a26647099cb2da2c37e4cddabdd`.
- Built source: `a993bdc57882cc805d046567f2eac634b4bbc0db`.
- [Build and ARM64 server qualification](https://github.com/Russianranger/trasc-server-android/actions/runs/38023308319).
- [Published preview](https://github.com/Russianranger/trasc-server-android/releases/tag/preview).
- Package: `io.github.russianranger.trasc.preview`; version `0.6.20`; code `69`.
- Update certificate SHA-256: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.

| Published file | Bytes | Release asset | SHA-256 |
| --- | ---: | --- | --- |
| `trasc-server-android-preview.apk` | 18758916 | `626984091` | `391a145377731a5819ee280a320269a0664dc28e29e4d43dbf5e94d5bc491034` |
| `launcher-sources.tar.gz` | 198471916 | `626984090` | `c4c61cff60aa4c73222ceb7c2964e1462c68892dc5d1511804bdfd9e6f533deb` |
| `native-reuse.json` | 4817 | `626984089` | `8bdf2ed016a70e3862bda1b50f10786b7f0f556f7cfb335239d68576cf0a2b7e` |
| `preview-build.json` | 765 | `626984088` | `a4f59a05fb26050a6f7d9ea0b1caf9c5dde415cd1d6a74d34c9b0064de29b704` |

ARM64 evidence artifact: `11659881101`, `takp-bookworm-arm64-verification`; SHA-256 `a61d53fe4183f0453eb1a7a02ad2af4d8604c8e9fc2723a6e5c2a65a8a989de6`.

## Resulting behavior

The shared toolbar keeps Runtime Start/Stop, Server Start/Stop/Restart and Client Start/Stop aligned and visibly grouped on every tab. The client start label follows the selected world. Stop client remains available during server work, while retaining client-busy, session-transfer and profile guards.

The 0.6.19 TAKP right-button camera adjustment remains included at 15% relative motion, preserving signed fractional deltas. Menu input and the other worlds retain their previous behavior. The latest device report did not reassess the camera rate, so device confirmation remains pending.

The existing Spawns/Netcode logs record actual NPC creation coordinates and reported packet errors. No live-count, player-position or nearest-NPC snapshots are included. The original `spells_en.txt` remains preserved separately from server exports `spells_us.txt` and `SkillCaps.txt`.

The server/quests/maps pins, deployed server build, database, client assets and Wine prefix remain in place. Server and renderer behavior are unchanged. All 21 native launcher components are byte-identical to the verified 0.6.19 APK.

## Verification

All three main CI jobs passed: APK, ARM64 server qualification and preview publication. Checks passed **408 Python tests with no skips**, all **13 browser programs**, four native fixtures and twelve management JVM checks, actual Microsoft DirectX extraction, Android assembly/lint, signing and all 21 native reuse checks. The storage and ferry workflows passed on their first attempts.

Toolbar checks cover **54 world/theme/viewport combinations**, including narrow-phone grouped rows and independent Stop client during server work.

ARM64 Bookworm qualification compiled all nine production server binaries and passed all **13** integration checks. The pinned Paineel content produced actual creation events for all 156 enabled seeded NPC spawn points. Existing checks verify source/dependencies, ELF/runtime dependencies, the four-part seed and eleven bot migrations, repeat-initialization refusal, salted local account, local services, Qeynos startup, unfiltered exports, shutdown and Custom workspace preservation.

The added native wire check exercises the production Mac opcode translator, encryption and literal 224-byte client spawn layout. It encodes bulk packets of 1, 56 and 100 NPCs and 156 individual `NewSpawn` packets, then independently decrypts/decompresses and validates their fields. Bulk wire sizes are 78, 1021 and 1700 bytes respectively; individual encrypted packets total 12791 bytes. The ARM64 results match the isolated x86_64 probe. This validates the encoding paths, not client packet delivery or model rendering on the Thor.

Downloaded artifacts match the published APK, source, receipt and manifest digests. APK v2 signature, content digest and actual Android manifest were independently verified. All 39 packaged backend modules, 49 UI files and 21 native components match the reviewed build; all 13 changed source files and 97 archived source files checked match the built commit. The preview tag points to that commit.

## Device handoff

1. Camp out, stop the client and runtime, then install 0.6.20 as an APK update.
2. Start the existing TAKP runtime, server and client. Check the grouped toolbar in each world/theme and its alignment in landscape.
3. Near the Paineel gate, enter `/target Tormented`. Report whether the Target window shows a name and HP while the model remains invisible. The original TAKP client supports this command; no Zeal or other client mod is needed.
4. Camp and export fresh logs, noting the target-window result. Separately compare right-button camera look with normal menu motion after releasing the button.

No client reimport, prefix reset, repeated Prepare, server rebuild or database reinitialization is required. NPC visibility and the camera rate still require device testing; zoning and playerbot gameplay remain separate acceptance work.
