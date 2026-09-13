TRASC Server Android **0.3.0** starts the embedded ROF2 client milestone. The user confirmed session backup/restore and input on 0.2.1.

- Download the separate client runtime in Client, with an offline archive option.
- Try Wine desktop, launch the imported ROF2 client, return to the display or stop it.
- Saved controllers, touch and physical keyboard/mouse feed the native display. Its Keyboard dialog supports Type and Send + Enter.
- Prepare client data/login/windowed resolution with original-file backups.
- Require matching PE32 DLL architecture and report native dinput8 loading only from Wine's actual trace.

This is an experimental software-graphics compatibility pass. ROF2/device/plugin behavior is not yet verified; sound, hardware acceleration and performance tuning remain later work. [Device sequence](https://github.com/Russianranger/trasc-server-android/blob/main/docs/client-runtime.md).

The following server/export fixes remain included:

Install this APK over **TRASC Server Preview 0.1.2, 0.2.0 or 0.2.1**. It uses the same application ID and pinned signing certificate. Stop the client and server runtime before updating. Your existing runtime 1.1, source, maps, database and binaries are retained; this APK update needs no server recompile.

- **Session export/import:** accept valid Debian `:arm64` filenames while retaining path traversal and drive-prefix checks.
- **Logs:** native Android listing, viewing and ZIP export work with the runtime closed, including after a failed session backup. Both log export buttons work without the localhost control service.
- **Recovery:** backup failures are recorded in `app.log` and explain whether the runtime is stopped. No game processes restart automatically.
- **Regression checks:** exact reported filename, full published-runtime backup/restore, native log bundles without Python, and the failed-backup/closed-runtime UI flow.

All 0.2.0 management features remain included:

- **Gameplay:** all database/source rules in searchable, collapsible categories; types and established bounds checked with field names in errors; save only modified rules.
- **Setup:** apply the legacy Nektulos map/nav pair with original-file backups, and revert it.
- **Server:** create and export a complete session ZIP. It stops the session cleanly and includes runtime, database, SQL snapshot, binaries, maps, logs, sources/builds, configuration, backups and imported client.
- **Setup:** restore that ZIP into a fresh app without downloading a runtime or recompiling. Checksums, modes and symlinks are verified/restored before activation. Existing sessions have a recovery generation.
- **Client:** ZIP import, private temporary-ZIP cleanup, DLL inventory, saved controller-to-keyboard/mouse bindings and a focused input diagnostic. The separate client runtime adds an experimental launch/display/DLL-loading path.
- **Continuity:** implementation decisions, validation and remaining work are recorded in `docs/HANDOFF.md`.

For this device pass, follow `docs/client-runtime.md`: install the client runtime, try Wine desktop, stop, prepare the imported client, start the server and attempt ROF2. Export Logs after the attempt.

Backups contain accounts, credentials and client files and are not encrypted. Save them privately outside the app. Only the private temporary copy of an imported session/client ZIP is removed; the selected source document remains intact.

**Older 0.1.0/0.1.1 installations:** their signing key was lost before 0.1.2, so this Preview application installs alongside them. Their data is not transferred automatically. Export the database, source/maps archives and edited files, stop the old runtime, and import into Preview. Do not uninstall the old app until migration is verified. Only run one runtime at a time because the ports are shared.

`preview-build.json` identifies the exact commit, APK checksum, application ID and signing certificate. Publication requires backend/JVM tests, ARM64 database integration, APK compilation and lint. New Android management workflows still require the user's device acceptance tests.
