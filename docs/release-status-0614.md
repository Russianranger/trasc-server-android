# TRASC Android 0.6.14 publication

Published October 9, 2026. Install as an update to the existing preview app.

- Version: **0.6.14 / code 63**
- APK: `trasc-server-android-preview.apk`
- Application ID: `io.github.russianranger.trasc.preview`
- SHA-256: `9a1b3f1974bf832b84de1452b796005bb2d96f02ead6748ce671dc7dfd10656c`
- Build commit: `1835c74bdd34adba45a275ffc3f067fe008f0884`
- [Passed build and publication run](https://github.com/Russianranger/trasc-server-android/actions/runs/37973617484)
- [Release](https://github.com/Russianranger/trasc-server-android/releases/tag/preview)

Necromancer now has a gritty black/charcoal and dark red palette, ivory text,
red actions and four distinct original offline backgrounds: crypt, ritual chamber,
forbidden grimoire and ossuary. Launcher theme shares the World profile bar.
Choose **Launcher theme → Necromancer** there. Default and Monk retain their
existing palette and artwork. Theme choices persist across reloads and both worlds.

[Artwork paths, original generation prompts and focused checks](launcher-themes-0614.md).

## Verification

Four browser suites, management checks, three native reuse tests and Android build
and lint passed. Theme checks cover actual image decoding, both world profiles,
all ten tabs, persistence, Default restoration, blocked storage, text contrast,
shared-bar desktop placement and 320/375px touch geometry. Desktop 1280×720 and
phone 390×844 screenshots were visually reviewed using the final artwork.

The published APK was downloaded and checked independently against its manifest,
binary Android version, expected certificate and repository assets. All 21 native
payload files were compared byte for byte against verified 0.6.13. The other 101
existing assets remained identical; the seven updated/new assets match the
repository. Android signing was verified with apksigner during the build.

The compiled Traditional server, imported RoF2 client, Wine prefix, runtime,
DirectX helpers, era settings, character UI/preferences and controller bindings
are retained. No server, runtime or native payload compilation or reset is needed.
