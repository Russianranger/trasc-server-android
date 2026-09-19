# Beta version 0.5

Official release of the verified TRASC Server Android launcher APK.

## Changes

- Complete border and solid background around the Server runtime panel.
- Clear startup messages: “Starting server…” followed by “Server started” after success.
- Compact Gameplay and launch settings, with dropdowns and checkboxes grouped together and expandable help.
- Existing first-person particle, camera, controller, reconnect and loading improvements retained.
- Handoff records successful player/account restoration and the confirmed camping fix. The three selected Spire features remain future development.

## Install

Download **trasc-server-android-beta-0.5.apk** from this release. Stop the game and runtime, install over the existing app, then reopen it. Keep your current game/server files and settings. This release requires no DLL/server rebuild or runtime reinstallation.

**Beta 0.5 is the release label.** This is the identical signed APK already verified as **0.4.23 (version code 40)**; Android and the launcher still display that internal version. If you already installed that APK, no reinstall is needed. The existing application ID and signing certificate are preserved.

## Verification

All seven jobs passed in [the source build](https://github.com/Russianranger/trasc-server-android/actions/runs/35410359686), including Android build/lint/signing, Python/JVM/browser checks, database/player migration, Microsoft add-on compilation and the existing ARM64 runtime compatibility gates. Phone, landscape and wide browser screenshots were reviewed; physical-device acceptance of the new layout remains a follow-up.

- Source commit: `095fcc9137f2d671986b90718dde975cd7c58a51`.
- APK SHA256: `f6c27a924033d435dae5c88eff0436508d8bb1357486e5ec8ebf681b3bcc1c9f`.
- Corresponding native sources are attached as `launcher-sources.tar.gz`.
- `beta-build.json` records the release label, internal version, source build, signing certificate and file checksums.

Existing high-ID spell compatibility, intermittent cold-start name corruption, zone-state persistence acceptance and longer background/power testing remain tracked in the handoff. This publication does not claim those milestones are complete.
