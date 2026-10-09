# TRASC 0.6.18 / code 67 — TAKP login configuration and crash reporting

The supplied device logs show an unhandled page fault at `0x8076F72C` inside `eqmain.dll` before the local login server received a client login. Wine stopped the game, but the launcher kept its display session open. The prepared login file used `[RegistrationServers]` and `[LoginServers]`; the legacy TAKP configuration requires `[Registration Servers]` and `[Login Servers]`.

## Published build

- [PR #24](https://github.com/Russianranger/trasc-server-android/pull/24), merged at `c75af5560767444ce253486929f47bd11a98cc93`.
- Built source: `71f00f1ec05bca80b1cda3c6e04205b243ffedcf`.
- [Build and server qualification](https://github.com/Russianranger/trasc-server-android/actions/runs/37997885892).
- [Published preview](https://github.com/Russianranger/trasc-server-android/releases/tag/preview).
- Package: `io.github.russianranger.trasc.preview`; version `0.6.18`; code `67`.
- APK: 18757780 bytes; SHA-256 `223b79712fbca7187cb078c279b4c6cbaf413667aec7fc2863ed675c83e81799`; release asset `626334127`.
- Update certificate SHA-256: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.
- Source archive SHA-256: `3f1224aaea65d8cd11b2bbcb6577b8084fa90d8e91f81f86ef02e6732828fb47`.
- Native reuse receipt SHA-256: `4e830f75e7927653741018dc66ca02a441e5bae418a6be349d272ff59b1805da`.
- ARM64 evidence artifact: `11648242853, takp-bookworm-arm64-verification`.

## Resulting behavior

Prepare writes the exact spaced registration and login section names. Game launch repairs the malformed headers in prepared 0.6.16/0.6.17 clients without changing their endpoints or other file bytes. Repair is case-aware, validates ordinary files and exactly one of each section, and is idempotent. Originals remain in the TAKP Wine prefix at `client/prefix/trasc-takp-login-originals/eqhost.txt`, with the previous repaired original in `eqhost.previous.txt`.

Explicit Wine unhandled game faults now end the display session and preserve the failure cause in launcher status and exported logs. Handled SEH traces, optional module warnings and Windows desktop application crashes do not trigger this game-only failure handling.

All 21 native launcher components are byte-identical to the published 0.6.17 APK. The update retains the existing renderer, client runtime, server/quests/maps pins and database. The 0.6.17 `spells_en.txt` import and checksum preservation fix remains in place.

## Verification

CI passed all **406 Python tests with no skips**, all **13 browser programs**, management JVM/native checks, actual Microsoft DirectX extraction, Android assembly/lint, update-certificate verification, the exact TAKP compatibility DLLs and all 21 reused native launcher components. The separate storage and ferry workflows passed on their first attempts.

ARM64 Bookworm qualification compiled all nine server binaries and passed all **11** checks: pinned source/dependencies and content, ELF/runtime dependencies, complete four-part seed and eleven bot migrations, repeat-initialization refusal without replacing existing data, salted local account, local login/world/dynamic zone startup, Qeynos map/Lua boot without SQL schema errors, actual two-file unfiltered data export, clean shutdown and Custom workspace preservation. Evidence artifact `11648242853` has SHA-256 `859517d032b181c8cf1c9b5e622bb06d47d352d52c7ecb540cb8a22a43082484`.

The downloaded artifact ZIP digest matches GitHub. APK, source archive, manifest and native receipt hashes match both the build manifest and published asset digests. Packaged backend and UI bytes match the reviewed source; the preview tag points to the built source commit. Local Python verification passed 406 tests with eight environment-dependent skips; CI ran those checks successfully.

The malformed login configuration is a confirmed defect. This APK has not been tested on the user's Android device; successful login, character selection and gameplay require a fresh device test.

## Device handoff

1. Stop the existing client and server runtime, then install 0.6.18 as an APK update.
2. Select TAKP World and start the server and client normally. The next game launch automatically repairs the existing login file.
3. Test login and character selection using the local TAKP account.
4. If startup still fails, export fresh logs and include the last visible screen and elapsed time.

No client reimport, prefix reset, repeated Prepare, server rebuild or database reinitialization is required for an already prepared 0.6.17 installation. See the [TAKP setup guide](takp-world-0616.md) for fresh installation and gameplay acceptance.
