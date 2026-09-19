# 0.4.23 launcher layout and status wording

Requested from the September 18 Thor screenshots: close the Server runtime panel's sides, correct “start started,” and condense Gameplay and client launch options.

The runtime toolbar has a complete gold border, internal padding, rounded corners and an opaque background. Its sticky position leaves a small top gap; scroll/focus positioning accounts for its changing height in portrait and landscape.

The startup notice and activity title say “Starting server…” while the operation runs. Only a completed successful job produces “Server started. Verify zone readiness in server logs.” Stop uses “Stopping server”; backend errors remain visible.

All eleven launch dropdowns are grouped in a responsive grid (one column on narrow screens, two on landscape/tablet widths, three on wide screens). All ten checkboxes form a separate group with at least44px touch rows. Detailed option explanations and preparation/recovery help are collapsed by default. Every control ID, option value, default, saved-setting path and action is retained. Gameplay's ruleset/worker controls and zone checkbox are condensed; the full rule editor and validation remain available.

Version0.4.23/code40 retains the existing application ID and pinned signing certificate. Update in place after stopping the client/runtime, then reopen the installed runtime. No DLL/server rebuild, runtime reinstall, SDK/source refresh, client import or database change is needed.

The latest handoff also closes user-confirmed player/account migration and camping (CampTimerMs2900→30000), and records Spire content browsing, focused content editing and spell/string/AA editing as future planning only.

## Verification and publication

The user explicitly approved merging PR #1 and publishing 0.4.23. All six PR verification jobs passed on [run 35408972837](https://github.com/Russianranger/trasc-server-android/actions/runs/35408972837). The documentation follow-up changed no implementation. [PR #1](https://github.com/Russianranger/trasc-server-android/pull/1) merged at `095fcc9137f2d671986b90718dde975cd7c58a51`.

[Main release run 35410359686](https://github.com/Russianranger/trasc-server-android/actions/runs/35410359686) passed all seven jobs, including publication: 138 Python tests, host/JVM and browser flows, Android build/lint/preserved signing, database and player migration checks, real Microsoft add-on compilation, and all existing ARM64 direct/PRoot client compatibility gates. No gate was waived.

Reviewed phone 412×915, Thor landscape 854×480 and wide 1280×720 screenshots. Runtime borders are enclosed, dropdowns use the intended one/two/three-column layout, and checkbox labels fit. One early phone checkbox capture had incomplete paint; the later full-page capture shows every checkbox correctly. UI artifact 10574100251 matches SHA256 `c92a33b92523832a908d149211b21f0fce87fdc05396738c343c072d5c6e301b`. Actual Thor layout acceptance remains a device follow-up.

Downloaded main candidate artifact 10574102684, ZIP SHA256 `758d8271f3c4dc95d878bb3468137a92f549e0d950c2f55502f2ab68d01d829c`. Independently verified APK v2 signature/content, version 0.4.23/code 40, application ID, preserved certificate, 26 packaged backend/header assets and all UI assets against the merged source. The APK is 10,538,843 bytes, SHA256 `f6c27a924033d435dae5c88eff0436508d8bb1357486e5ec8ebf681b3bcc1c9f`.

The public preview tag matches the merge commit. Public APK and native-source archive digests match the downloaded main candidate, and deterministic reconstruction of preview-build.json matches its published digest `8cf6a4c53d07e8cd13c5cf41357f8ace3c9425cc49f779e822e09308946e15eb`. The corresponding source archive is 114,558,375 bytes, SHA256 `21f985bdea5b8b55213d805f8d1acdbb61b6b448b87a3361d81200d4de714d78`. Client-runtime assets also published successfully. Existing installations do not need a runtime download.

[Download 0.4.23 preview](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?build=095fcc9). Stop ROF2/runtime, install over the current app and reopen. The earlier publication block is resolved; the released APK uses the preserved preview signing key. Keep the working DLL and settings.
