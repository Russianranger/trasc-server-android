# TRASC Android 0.6.13 publication and acceptance

Published October 9, 2026. Update the existing preview installation in place.

- APK: `trasc-server-android-preview.apk`
- Version: **0.6.13 / code 62**
- Application ID: `io.github.russianranger.trasc.preview`
- SHA-256: `8d9a718f0a71a9ffb40973f80b716ebcf7fc60fb9d1d68d0a7cdeaaf659d54a1`
- Build commit: `9b27e2ed4c8a036bc4596db24e82bb4ded34e201`
- [Release](https://github.com/Russianranger/trasc-server-android/releases/tag/preview)
- [Passed build, database and publication run](https://github.com/Russianranger/trasc-server-android/actions/runs/37873835903)
- Signing certificate SHA-256: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`

The downloaded published APK was checked independently against its release manifest,
binary Android manifest, signing certificate and repository assets. All 21 reused
native payload files were compared byte for byte with the verified 0.6.12 APK.
The build verified the Android signature with apksigner. Server, runtime and native
components were reused; none was recompiled for this release.

## Validation

All three Actions jobs passed: APK, era-database and preview publication.
The Android build and lint passed, along with four browser suites for profile
isolation, management, era review/restore and themes. Ten era unit tests and eight
real MariaDB integration tests passed. The database checks cover all three era
presets, exact Default restoration, per-zone composites, preserved customization,
NULL metadata and absent rows, stale previews, conflicting identities, unsupported
storage engines and rollback after an injected partial-write failure. The actual
MariaDB dump backup path was exercised.

The attached PEQ database was audited without importing it over the working
installation. [Research, compatibility limits and acceptance procedure](traditional-eras-0613.md)
explain the 47 era values and sparse content-tag limitations. The presets are
compatible approximations; this is not a TAKP data or engine conversion.

## Existing Traditional installation

1. Install the APK as an update. Camp in a zone available in the selected era.
2. Stop the client and server. Keep the Traditional runtime open.
3. Open **Gameplay → Expansion era** and select **Velious**, **Luclin** or
   **Planes of Power**. Review the proposed changes, then choose **Apply chosen era**.
4. Start the existing server and reopen the client. Check the active era, ordinary
   zone login, relevant level/AA limits and later-zone restriction with a non-GM
   character. Stop/start once to check persistence.
5. To revert, stop the client and server, select **Default**, review, then choose
   **Apply database default** and start the server again. Original Default rule rows
   and zone routing are restored; character progress is retained.
6. Use **Launcher theme** above the tabs to select **Default**, **Necromancer**
   or **Monk**. Check that the selection persists after reload and profile switching.

No server compilation, client reimport, prefix reset, runtime reinstall or DirectX
helper installation is required. Character INIs, StoneUI, existing XP curves/rates
and controller preferences remain. Device gameplay acceptance on Thor is pending.
