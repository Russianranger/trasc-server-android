# Published 0.6.30 — Client1 recognition and V4 capture recovery

Version **0.6.30 / code 79** was published and independently verified on
October 14, 2026, at **16:03:22 UTC / 11:03:22 Chicago**.

[Download the APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?v=0.6.30)
(18,959,432 bytes). SHA-256:

`ef0237e0d0d767f7a6e0e37403803b5de0b7bc1d765e496930d422a57fd9fb31`

The Thor's 0.6.29 logs identify the exact game title as `Client1`; the previous
EqW-only helper made no focus-repair requests. This release accepts that exact
title alongside `EqW-TAKP`, retaining the process-class, visibility, pointer-path,
physical Look and absent-native-focus guards. V4 also refreshes the same
already-owned capture rectangle once after a verified native focus repair.
The stricter runtime test reproduced why this is needed: Wine's logical cursor
could remain centered while physical capture was lost, turning twelve fresh
+1 movements into a total of 78.

All five [release jobs](https://github.com/Russianranger/trasc-server-android/actions/runs/38593150423)
passed: 569 Python tests with zero skips, management JVM/C and launcher browser/
controller checks, APK assembly/lint/signing, and Custom, Traditional and TAKP
production qualification. Independent actual public-download verification
checked all four asset digests, the original certificate and cryptographic
v2 signature with no errors or warnings, 132 APK source assets, 610 archived
Git files, the exact successful CI helpers/proofs and all 21 retained native
launcher components.

[Native qualification](https://github.com/Russianranger/trasc-server-android/actions/runs/38590631222)
passed three scoped repair/notification/refresh sequences, 24 exact signed
segments including centered restore, 32 focus refusals and nine reader
refusals. Both bounded observer phases ended normally with zero drops. One
first-phase startup X error occurred with RMB up before the helper; none
occurred during focus actions or resume. The actual MSVC V4 EQW DLL is
95,232 bytes, SHA-256
`ae556d045a0b64586b1e4f0c0957a75c99626f9f149f8e95b7bb99ed7a738fc8`.
The ARM64 V2 focus helper is 72,744 bytes, SHA-256
`fcec1f6a4f0d1101efef56f58671b47944fd19219f0eeb3a4591a66607f5b364`.

The published source/tag is `875e9dcc68f7aae10cc372077d00b3da2c7e84a3`,
tree `0ad1ca75e76d9fbb000c95c0b2d5fc75a067ddff`.
[PR 37](https://github.com/Russianranger/trasc-server-android/pull/37) merged as
`e0da75f45dbdc3882212ec564c82224b53a3b5d9` with that exact qualified tree.
Main adds documentation receipts afterward; the preview tag retains the
qualified source. Full evidence is in [release-proof-0630.json](release-proof-0630.json).

**Physical TAKP mouse-look acceptance passed on the tested AYN Thor right-stick
configuration on October 14, 2026.** The user reports: “That worked!! It's perfect
now.” The fresh device bundle confirms one guarded focus repair followed by
a matching capture refresh 23 ms later, 125 exact signed native samples and
67 exact signed game-consumer matches. See [device-camera-0630.md](device-camera-0630.md)
and [device-camera-evidence-0630.json](device-camera-evidence-0630.json).

The controlled open PE32 qualification remains separate from this actual
proprietary-game device evidence. The publication-time
[release-proof-0630.json](release-proof-0630.json) records camera acceptance as
pending at publication; the later physical receipt above supersedes that
pending status for the tested configuration.

Camp and stop normally, install in place without uninstalling, then reopen
TAKP with the working Yaulp server. The known official V3 helper upgrades
with an exact backup and preserves earlier originals. No server source update,
build/deploy, database import, client reimport, Prepare or prefix/runtime reset
is needed. Existing profiles, characters, bots, client assets, runtimes and
settings must be retained.

Use [takp-camera-client1-0630.md](takp-camera-client1-0630.md) for the retained
installation/regression procedure and exact log evidence. Keep NPC visibility, Traditional
StoneUI and the separate backup/bot/model/physical incremental-build acceptance
checks separate from the confirmed server/update/Yaulp results.
