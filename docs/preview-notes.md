# TRASC Android 0.6.37 — official 4 GB patch download

[Download the Android APK](https://github.com/Russianranger/trasc-server-android/releases/download/v0.6.37/trasc-server-android-0.6.37.apk)

Install over your existing TRASC app. This release is marked Latest on GitHub.

In the **Custom** profile, import your client, stop it if it is running, and open **Client → Custom client · 4 GB patch**. **Download NTCore 4 GB Patch** saves the official Windows patcher as `4gb_patch.exe` in that profile's imported client folder. The launcher checks the download against the pinned official archive and executable checksums before saving it. Downloading does not run the patcher or alter `eqgame.exe`.

The existing **Apply 4 GB patch** action enables the same Large Address Aware flag directly from Android and retains a protected original for **Restore original executable**. The separate download makes the official Windows tool available inside the client folder when needed.

Includes the database sort dropdown across all three profiles, per-profile `eqhost.txt` IP controls with protected originals, and default controller menu navigation. Existing application identity and signing certificate support an in-place update.

The official tool is downloaded on request from [NTCore](https://ntcore.com/4gb-patch/); it is not bundled in the APK. Automated regression and APK verification evidence is recorded in the release workflow. Physical Android device acceptance remains pending.
