# TRASC Android 0.6.38 — client patch download availability fix

[Download the Android APK](https://github.com/Russianranger/trasc-server-android/releases/download/v0.6.38/trasc-server-android-0.6.38.apk)

Install over your existing TRASC app. This release is marked Latest on GitHub.

Fixes the client status loading problem that could leave **Download NTCore 4 GB Patch** disabled at “Waiting for this world’s client status…” even when the Custom client was stopped. Native client status now identifies its current world, allowing the launcher to inspect client files and enable the controls when that world’s client is imported and stopped. Strict profile checks remain in place.

In the **Custom** profile, open **Client → Custom client · 4 GB patch → Download NTCore 4 GB Patch**. The launcher verifies and saves the official `4gb_patch.exe` beside the imported `eqgame.exe`. Downloading does not run the patcher or change the game executable. **Apply 4 GB patch** remains available to patch the executable directly from Android with a protected original for Restore.

Also fixes the Custom DLL compiler worker’s missing-profile error by validating the current compiler request before starting Wine.

Includes the database sort dropdown across all three profiles, per-profile `eqhost.txt` IP controls with protected originals, and default controller menu navigation. The application identity, signing certificate and native components are preserved for an in-place update.

The official tool is downloaded on request from [NTCore](https://ntcore.com/4gb-patch/); it is not bundled in the APK. Automated regression and APK verification evidence is recorded in the release workflow. Physical Android device acceptance remains pending.
