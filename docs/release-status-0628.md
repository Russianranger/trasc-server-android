# Published 0.6.28 — scoped TAKP native focus recovery

Published October13 at21:38:02 Chicago (2026-10-14T02:38:02Z).
[Download 0.6.28/code77](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?v=0.6.28) —
18,936,371 bytes, SHA-256:
`0073d46cc5b58c2a7f27c68d11e5fd3cc58a0b6afb8f208d19c7615bbba02859`.

The physical 0.6.27 logs identify missing native X focus: Android's signed
stick packets reach XI2 correctly, but X remains on PointerRoot while Wine
reports foreground. Fresh (-1,0) becomes game (+16,-96), matching the escaped
cursor offset. 0.6.28 repairs only missing focus during a physical right-mouse
gesture over the exact visible TAKP game window. It preserves concrete foreign
focus, existing capture configuration and all prefix settings. Physical Thor
camera usability remains unaccepted until the device test passes.

[Exact ARM runtime run 38500575431](https://github.com/Russianranger/trasc-server-android/actions/runs/38500575431)
passed at `d0bd98e387727a7eae14a728eea4541c05610674`. The unchanged published runtime/input bridge/
wineserver/observer reproduced the fault with wrong fresh reversal input,
then passed actual focus and physical confinement, ten exact signed segments
through both DirectInput APIs, zero idle drift, menu/RMB release, six refusal
guards and None-focus recovery after resume. Actual bounded logs ended with
zero drops/X errors. This is an open PE32 fixture, not Android or physical Thor.

[Release run 38501118405](https://github.com/Russianranger/trasc-server-android/actions/runs/38501118405)
passed all five jobs, 562 Python tests with zero skips, management JVM/C/browser
checks, assembly/lint/signing and all three server-profile gates.
Qualified source `8d650b2537acbb2ca3a05b34e5a98e9c2e9a7225`, tree `589bf58ce3f5cdd4c3b1554b554c0aac724f3ed3`.
[PR #35](https://github.com/Russianranger/trasc-server-android/pull/35) merged as `42781b8d1799c88110a92a9f5f2203830d93d579` with the exact tree.
Preview stays on the qualified source; this documentation receipt does not
rebuild or replace the published payload.

Independent public downloads cryptographically verified the existing v2
signature (Google apksig8.8.2; no errors/warnings), all128 bundled source assets,
all582 archived Git files and all four asset digests. All21 existing native
components, V3 helper, prior TAKP assets and observer are byte-equal to actual
0.6.27. New focus ELF is72,232 bytes, SHA-256
`90dda77cb0b0fe1d18d4fa7b39bedda7dad67af6c342d7b23c74d0129f666865`.
Its build/proof bytes match actual successful CI artifacts; all eight repair
rows, six refusal outcomes and producer counts pass strict independent checks.
Exact receipts: [release-proof-0628.json](release-proof-0628.json).

Install as an Android update without uninstalling. Keep the working server/
Yaulp, databases/characters/bots, client files, Wine prefixes, installed
runtimes and settings. No new server source/build/deployment, database import,
client reimport or prefix reset is required. Read
[takp-camera-focus-0628.md](takp-camera-focus-0628.md) for the short Thor test.
Camera, NPC visibility, Traditional StoneUI and remaining all-profile backup/
persistence/model restore/physical object-reuse gates remain separate.
