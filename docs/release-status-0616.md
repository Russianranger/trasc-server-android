# TRASC Android 0.6.16 publication verification

Published October 9, 2026. TAKP World is the third independent world and client
profile beside TRASC Custom and Traditional EQEmu.

- Version: **0.6.16 / code 65**
- Package: `io.github.russianranger.trasc.preview`
- Published APK: `trasc-server-android-preview.apk` (18,756,620 bytes)
- APK SHA-256: `8f5d4375f9426811d4451214053e01f14085e00dfa1683df5bedf8858cf138f4`
- Built source commit: `23df44aae50ab8e638d0ec9f5e87e4714ceac646`
- Merge commit: `a0b87033e7c5b92cf7fe995dc0c48aa90136d346`
- [Merged PR #22](https://github.com/Russianranger/trasc-server-android/pull/22)
- [Successful build, server qualification and publication](https://github.com/Russianranger/trasc-server-android/actions/runs/37982334780)
- [Published preview](https://github.com/Russianranger/trasc-server-android/releases/tag/preview)
- [Setup and device acceptance guide](takp-world-0616.md)

The downloaded final CI APK matches its build manifest and the published GitHub
asset digest. Its embedded signing certificate was independently extracted and
matches the existing preview certificate:
`ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.
CI also passed `apksigner` verification, Android assembly and lint. All 21 native
launcher components match 0.6.15. The exact TAKP patch DLLs, licenses and current
backend files in the downloaded APK match the repository.

All 397 Python tests passed without skips, including the isolated MariaDB era
fixture. All 13 browser suites, management JVM/native checks and real Microsoft
DirectX extraction/recovery checks passed. Browser checks cover three-profile
selection, busy/stale guards, TAKP setup/accounts/client readiness, hidden
unsupported controls, theme persistence and phone layouts.

Native ARM64 Debian Bookworm qualification passed all eleven integration checks:
the pinned complete source and dependencies; matching quests, flat maps and
opcodes; production compilation and verification of nine binaries; the four-part
seed, schema fixes and eleven bot migrations; refusal to replace an existing
database; salted local account creation; local login/world/dynamic-zone startup;
Qeynos map/Lua boot without SQL schema errors; the actual two-file unfiltered
export; clean shutdown; and preservation of Custom files and credentials.
Evidence is retained in artifact `takp-bookworm-arm64-verification` (11641422379).

The source archive digest is
`0ace85a26fd5d89a3e6eaf7ee0225ec5a32009b49e1652141fbc0f95d2be0165`.
The native-reuse receipt digest is
`afb4fb9c322e7df289db4333c9febebf52aa33425eaaf90b303b3e73ce5312bc`.

Install as an update. TAKP creates separate server/client installations and
requires a complete Windows TAKP game ZIP. Existing Custom and Traditional
files and the Monk/Necromancer themes are preserved. Physical Android client
authentication, graphics/audio/input, zoning and bot behavior still require
device testing; native server qualification does not establish those results.
