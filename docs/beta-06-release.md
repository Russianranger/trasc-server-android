# Beta version 0.6

Repairs server and client runtime installation when Android rejects hard links with **`link failed: EACCES (Permission denied)`**. This was reported on a Samsung Galaxy Z Fold6 running Android 16 with the official Beta 0.5 release. The supplied logs confirm six failures in hard-link extraction after successful download and checksum verification; one earlier download separately suffered a connection abort.

The shared installer now expands archive hard links into independent regular files, preserving executable permissions and guest symbolic links. Expanded copies count toward the extraction size limit and available-space checks. Online and offline installs both use the corrected path. The runtime archives and their Linux packages do not need to change.

## Install and test

1. Download **trasc-server-android-beta-0.6.apk** from this release. Stop the game and runtimes, then install over the existing app. **Do not uninstall or clear app storage.** Android and the launcher both identify this build as **0.6 (version code 49)**, with the existing app ID and signing certificate. It updates both official Beta 0.5 and the later previews.
2. On the affected Fold6, open **Setup → Download runtime** once. The runtime should finish unpacking and open successfully. For a fresh custom-server setup, leave **TRASC Custom** selected.
3. If downloading itself fails, save the project's `runtime-arm64.tar.gz` from the [server runtime release](https://github.com/Russianranger/trasc-server-android/releases/tag/runtime-v1) and choose **Setup → Choose runtime .tar.gz**. Select the intact archive; do not unpack it in Android Files. Both install methods benefit from the fix.
4. If the client runtime is needed, use **Client → Client runtime → Download client runtime**, or **Choose offline runtime archive** with `client-runtime-arm64.tar.gz` from the [client runtime release](https://github.com/Russianranger/trasc-server-android/releases/tag/client-runtime-v1). The two archives are different and must be selected in their matching installers.
5. Report whether the server reaches **Runtime ready**. If any stage fails, stop repeating the operation and use **Logs → Export log bundle**, including the displayed error and last action. This export works without an installed/running runtime. Passing extraction does not yet establish that every later Android 16 runtime/client operation is compatible.

Existing working installations need only the APK update for this repair. Their source, database, characters, server binaries, client import, DLL and settings remain in place; no server/DLL rebuild, runtime reinstall, database reimport or repeat boat test is required for the installer change. A fresh setup still needs the usual server source, database, maps and user-supplied client.

## Included since official Beta 0.5

- Spire content browsing/editing and merchant tools; a designated Fixes tab and illustrated tabs.
- Shared server controls/status, accepted Qeynos–Erudin ferry work and log cleanup controls.
- Separate Custom and Traditional EQEmu profiles with classic 16-bit scenes and quest/plugin/Lua/assets imports.

**Traditional remains a preparation workspace.** Its Build/Deploy/Start and generated client exports are pending the chosen fork's Android compilation milestone. Era presets and Ocean of Tears/Overthere route work remain deferred. The separate large-backup/provider-loss issue is not part of this repair; retain existing successful backups.

## Verification and remaining acceptance

Regression coverage simulates Android's hard-link denial, verifies file contents and executable/data permissions, preserves guest symlinks, and rejects invalid targets, traversal, replacement and expanded-size overflow. The real server and client archive gates use the same restrictive host adapter, alongside the existing build/lint/signature, database and client runtime checks. Physical acceptance of this repair on Fold6/Android 16 remains pending user testing.

`beta-build.json` records the exact source commit, build run, APK checksum, preserved signing certificate and corresponding source archive checksum. `launcher-sources.tar.gz` accompanies the APK. Beta 0.5 remains available at its original tag; this is a new named release.
