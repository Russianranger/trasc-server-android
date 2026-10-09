# TRASC 0.6.19 / code 68 — Shared launch controls and TAKP camera input

The 0.6.18 device test confirmed login, character creation, entry into Paineel and a stable session ending in camp. The remaining reports concern missing NPCs and rapid camera movement. The server accepted the executable and original spell-file checksums.

## Published build

- [PR #25](https://github.com/Russianranger/trasc-server-android/pull/25), merged at `8c7dc6ef5f85a10f564beeb1bd3539398df127b4`.
- Built source: `20cecc90015b7073b5978f9a346bada4a76580fc`.
- [Build and server qualification](https://github.com/Russianranger/trasc-server-android/actions/runs/38002126538).
- [Published preview](https://github.com/Russianranger/trasc-server-android/releases/tag/preview).
- Package: `io.github.russianranger.trasc.preview`; version `0.6.19`; code `68`.
- APK: 18758712 bytes; SHA-256 `54fe6f5ec6c05442c0991545ce580739afe423f3de3e64f491ccc8ed2147f23d`; release asset `626427108`.
- Update certificate SHA-256: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.
- Source archive SHA-256: `e4b1331251e0f5a5d21811c9c3c252f5e86ac33d08d6f1a5c671d5836e44f6dd`.
- Native reuse receipt SHA-256: `38be72bfb457df1efda3bf3d9fda9660854e29496ce2ba14c3ec6515195106f8`.
- Build manifest SHA-256: `dcc319b01cf1dc3605e3aef2dcc96793488d7da1ab54120ef0e00fb2b8d70b2a`.
- ARM64 evidence artifact: `11649108869, takp-bookworm-arm64-verification`; SHA-256 `b1b2f562103d549dcf2967a341e3c660cac9a708d24892077e095ae68af74afc`.

## Resulting behavior

Server Start/Stop/Restart and client Start/Stop share the centered top toolbar on every tab, across all three worlds and themes. Stop client stays available during server builds and restarts, while retaining client-busy, session-transfer and profile guards.

TAKP relative input uses 15% gain while the right mouse button is held. Signed fractional motion is retained, and fractional leftovers clear when entering or leaving camera look. Menu movement, absolute touch input and the other worlds retain their existing behavior. This is a sensitivity adjustment; the supplied logs do not establish cursor-warp feedback as the cause.

Client help and preparation/export messages distinguish server exports `spells_us.txt` and `SkillCaps.txt` from the original `spells_en.txt`, which remains preserved for the legacy checksum. Export behavior and filenames are unchanged.

Server startup safely enables the existing general Spawns/Netcode file logs and preserves higher verbosity. These record actual NPC creation coordinates and reported packet errors. NPC visibility remains unresolved; no live-count, player-position or nearest-NPC snapshots are included, and no NPC visibility fix is claimed.

The existing server/quests/maps pins, deployed server build, database and client Wine prefix remain in place. All 21 native launcher components are byte-identical to the verified 0.6.18 APK.

## Verification

All three main CI jobs passed: APK, ARM64 server qualification and preview publication. CI passed **408 Python tests with no skips**, all **13 browser programs**, management JVM/native tests, actual Microsoft DirectX extraction, Android assembly/lint, signing and all 21 native reuse checks. The storage and ferry workflows also passed on their first attempts.

The toolbar checks cover all three worlds, all three themes and five viewport widths, including independent Stop client during server operations. Input checks cover signed fractional motion, overlapping right-button holds, menu recovery, absolute touch and unchanged Custom/Traditional behavior.

ARM64 Bookworm qualification compiled all nine server binaries and passed all **12** integration checks. The new Paineel check uses pinned content and requires actual creation events for every one of the 156 enabled seeded spawn points. It verifies zone boot and server-side creation, rather than client delivery or visibility. Existing checks verify source/dependencies, ELF/runtime dependencies, the four-part seed and eleven bot migrations, repeat-initialization refusal, salted local account, local services, Qeynos startup, unfiltered exports, shutdown and Custom workspace preservation.

The downloaded artifact ZIP digest matches GitHub. APK, source, manifest and native receipt hashes match their published asset digests. Packaged backend/UI and all 18 changed source files match the reviewed commit; the preview tag points to that built commit. Local management/native, DirectX, all 13 browser programs and 11 focused server tests also passed.

An additional isolated x86_64 native probe created all 156 Paineel NPCs with production file logging. A scratch-only bulk encoder probe independently recovered all fields from 100 encoded Mac NPC records. Neither establishes ARM client delivery or rendering on the Thor. The uploaded logs contain no character coordinates for a nearest-NPC comparison.

## Device handoff

1. Camp out, stop the client and server runtime, then install 0.6.19 as an APK update.
2. Open TAKP runtime and start the server. Startup enables the new diagnostic logs.
3. Start TAKP from the centered toolbar. Compare camera motion while holding the right mouse button, then release it and check menu movement.
4. Visit the area where NPCs appeared absent, camp and export fresh logs if they remain missing.

No client reimport, prefix reset, repeated Prepare, server rebuild or database reinitialization is required. The new camera rate and NPC visibility require device testing; zoning and playerbot gameplay remain separate acceptance work.
