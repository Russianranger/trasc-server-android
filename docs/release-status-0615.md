# TRASC Android 0.6.15 publication verification

Published October 9, 2026. This update gives the Monk launcher theme four original offline paintings, sea blue surfaces and light red accents. Choose **Launcher theme → Monk** beside **World profile**.

- Version: **0.6.15 / code 64**
- Package: `io.github.russianranger.trasc.preview`
- Published APK: `trasc-server-android-preview.apk` (18,521,695 bytes)
- APK SHA-256: `535263ab190c91818a7fe9d6b8370829d66e73496704e99a69ebf1c8a842441f`
- Source commit: `b1d57d3830920d2494cb4bd65499a176e8647a98`
- [Successful build and publication](https://github.com/Russianranger/trasc-server-android/actions/runs/37976864079)
- [Published preview](https://github.com/Russianranger/trasc-server-android/releases/tag/preview)
- [Artwork, tab mapping and prompts](launcher-themes-0615.md)

The published APK was downloaded independently and checked against its build manifest. Its binary Android manifest confirms the package, version and code. Its APK signing certificate remains `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; the build also passed `apksigner` verification.

All 21 native components match the verified 0.6.14 APK byte for byte, including the Traditional camera adapter. All 105 other existing assets also match. The only existing asset changes are the launcher theme CSS, footer version and backend version constant; four Monk WebP paintings were added. Those seven updated/new assets match the source repository exactly.

All four browser suites passed, covering both world profiles, every launcher tab, decoded artwork, shared profile/theme selector bar, theme persistence, contrast and phone layouts. Native reuse tests and the management checks passed. Android assembly and lint passed. The final temple, meditation, dojo and combat crops were visually reviewed at desktop and phone sizes.

Install as an update. The compiled Traditional server, imported RoF2 client, Wine prefix, runtime, DirectX helpers, controller bindings, character preferences and era rules are preserved. No native/server/runtime rebuild or client reimport is needed. Choose **Default** or **Necromancer** in the same selector to change the launcher appearance.

The source archive SHA-256 recorded by the successful build is `cf63685fb68c1323b0462f70589ebe1ed0c9f5edc092562e1fffbff37885f4de`. The native-reuse receipt was downloaded and verified against manifest SHA-256 `d22b0fef6dd28d4ba516fbdd8d5c1c43e64bba04f2adbc8bf0a1d0e8b9943663`.
