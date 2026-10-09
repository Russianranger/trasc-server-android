# TRASC 0.6.17 / code 66 — TAKP client import fix

The complete TAKP PC V2.1c client contains `spells_en.txt`. Version 0.6.16 incorrectly required the server exporter’s `spells_us.txt`, so import rejected a valid client before installing it.

## Published build

- [PR #23](https://github.com/Russianranger/trasc-server-android/pull/23) merged at `4ba7e89661157ac867e654b706225bfec65ce8d5`.
- Built source: `25d462ffc53ec0a3dc587dd0168e544425313ee6`.
- [Successful build and qualification run](https://github.com/Russianranger/trasc-server-android/actions/runs/37988675391).
- [Published preview](https://github.com/Russianranger/trasc-server-android/releases/tag/preview).
- Package: `io.github.russianranger.trasc.preview`; version `0.6.17`; code `66`.
- APK: 18,756,760 bytes; SHA-256 `93a632cfd713a64cd23a8a8d27f37ed9fea1f4acc97178c40d45c1fb071fe776`.
- APK asset: `626146940`.
- Update certificate SHA-256: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.
- Source archive SHA-256: `f02f5d1d24d97906102bc79a6c7a4a41c61de11183606e9d4f2c897444bf4457`.
- Native reuse receipt SHA-256: `ec458dc929ae03289eb627bb7d1e3b74724be58eb0070a38a13fdd02fa1446bc`.
- ARM64 evidence artifact: `11645041046`, `takp-bookworm-arm64-verification`.

## Resulting behavior

Import accepts the client’s `spells_en.txt` and retains legacy `spells_us.txt` compatibility. When both exist, validation records the actual `spells_en.txt` name, including its casing. Missing or empty spell files still reject import without replacing an existing client.

Prepare and Export & sync preserve the supplied `spells_en.txt`. The pinned server’s `world/client.cpp::HandleChecksumPacket` validates Windows spell checksums during login; the database exporter produces a different file under `spells_us.txt`. Those exports remain separate until a replacement spell-file/checksum policy is qualified. Skill caps, pinned compatibility DLLs, login and display preparation keep their existing behavior.

All 21 native launcher components are byte-identical to the verified 0.6.16 APK. Custom and Traditional profiles, launcher themes, the pinned TAKP server/quests/maps and all existing databases retain their existing paths and settings.

## Verification

CI passed all **400 Python tests with no skips**, management JVM/native checks, actual Microsoft DirectX extraction, all **13 browser programs**, APK assembly and lint, update certificate verification, native payload verification and TAKP helper verification. Local Python checks passed with eight environment-dependent checks skipped; CI executed those checks successfully.

The ARM64 server job compiled all nine binaries from the unchanged pinned server source and passed all **11** qualification checks: source/dependencies, content, ELF/runtime dependencies, four-part database seed, eleven bot migrations, repeat-initialization refusal, salted local account, server/zone startup, Qeynos map/Lua boot without SQL schema errors, unfiltered data export and clean shutdown/profile preservation.

The separate storage browser workflow initially hit a pre-existing startup timing assertion: an initial read could arrive before the profile script loaded and lacked a profile tag. The main browser suite passed on its first run; the separate workflow passed on a same-commit retry. A delayed-script diagnostic reproduced the untagged initial read and showed subsequent requests correctly tagged to Custom. This hotfix does not change polling or profile switching.

Downloaded APK, source archive and native receipt hashes match the build manifest and published release asset digests. The APK contains the reviewed import fix and launcher help.

Android login, rendering, audio, input, zoning and bot behavior still require device testing with the complete client.

## Device handoff

1. Install 0.6.17 as an update to the existing app.
2. Select TAKP World and reimport the original `TAKP_PC_V2.1c.zip`. Keep `spells_en.txt` unchanged; no manual rename is needed.
3. Install this world’s client runtime and DirectX helpers. Complete the server build/deployment if still pending, then use Prepare client with the server runtime open and the game stopped.
4. Start the TAKP server and client, then sign in with the local account already created.

The failed import removed only the app’s temporary incoming copy and staging directory. The original user ZIP and existing world/database setup remain available. Database initialization does not need to be repeated.

See the [TAKP setup guide](takp-world-0616.md) for the full setup and device acceptance sequence.
