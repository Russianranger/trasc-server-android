TRASC Server Android **0.3.3** removes the diagnostic logging flood found in the first successful embedded ROF2 launch.

- Normal launches retain Wine errors and DLL-load confirmation while disabling verbose exception/module traces and repetitive fixme messages. The reported session wrote 1,059,025,481 bytes / 9,258,244 lines; global asset initialization took 53 minutes 11 seconds.
- **Verbose Wine diagnostics (slower)** is off by default. Enable it only for a requested diagnostic comparison. The launch status and exported state record the selected mode.
- Wine output is drained independently and rotated into two segments of at most 8 MiB each. One previous session is kept, capped at 8 MiB with startup/final excerpts; this also trims old 0.3.2 traces on the next launch. Load evidence and fatal errors are captured before rotation.
- Keep `eqgame.exe patchme`, native-first/system-fallback DirectInput, the existing prefix and conservative CPU translation settings.

**Stop both runtimes, install this APK over Preview 0.3.2, start the server, and Launch ROF2 at the same 800x600 with native dinput8 on and verbose diagnostics off.** No runtime download, prefix repair, Prepare, server rebuild or client/database reimport is required. Export Logs and report time to character selection and responsiveness there. The previous run reached character selection; playable frame rates and world entry are still unverified. Graphics still use CPU llvmpipe: this update does not enable the Thor GPU.

Previous updates follow for reference.

TRASC Server Android **0.3.2** fixes the system DirectInput load behind the imported native client DLL.

- Use native-first, built-in fallback (`dinput8=n,b`): load your imported DLL, then allow its absolute system DLL request to reach Wine's implementation.
- Report native DLL and system DirectInput loading separately, based on actual Wine traces.
- Include the game's startup diagnostics and the add-on's `dinput8.log` in native log viewing/export. Client settings, binaries and character chat logs are excluded.
- Record session start/end times and stop reasons; retain exception traces.
- Test an open PE32 proxy that forwards to system DirectInput and creates keyboard/mouse devices. A negative control reproduces failure under the old native-only override.

**Update in place, keep your current prefix/runtime/client, start the server, and Launch ROF2 with the native DLL option enabled.** No prefix repair, runtime redownload, server rebuild or reimport is needed. Export Logs after the attempt. The earlier kernel32 failure is cleared in the latest device run; actual ROF2 login/world entry still require device verification.

Previous updates follow for reference.

TRASC Server Android **0.3.1** adds recovery and diagnostics for the reported ROF2 black screen.

- Verify Wine's 32-bit core files and run its 32-bit command interpreter before ROF2.
- Report fatal Windows loader/dependency errors visibly, with separate prefix logs.
- **Repair Wine prefix** preserves the previous prefix in `client/prefix-backups/`, then initializes a fresh Windows environment. Game files, controller bindings and server data are retained.
- Keep the required `eqgame.exe patchme` launch command and native dinput8 override.
- Verify the installed runtime through pinned PRoot, including a large legacy PE32 test program.

Stop runtimes and install over Preview 0.3.0. No server rebuild, database/client import or runtime redownload is needed. For this device pass: **Stop client → Repair Wine prefix → wait for the Wine desktop → Stop client → start server → Launch ROF2**. Export Logs afterwards.

The fatal error in the device bundle is `could not load kernel32.dll, status c0000135`. Fresh-prefix infrastructure tests cannot establish the exact cause on Android; this pass provides a preserved-prefix recovery path and verifies 32-bit Wine before attempting the modified client. Actual ROF2 login/world entry remain unverified. Software graphics only; sound and hardware acceleration remain later work.

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

For the current device pass, use the 0.3.3 sequence at the top of these notes. Export Logs after the attempt.

Backups contain accounts, credentials and client files and are not encrypted. Save them privately outside the app. Only the private temporary copy of an imported session/client ZIP is removed; the selected source document remains intact.

**Older 0.1.0/0.1.1 installations:** their signing key was lost before 0.1.2, so this Preview application installs alongside them. Their data is not transferred automatically. Export the database, source/maps archives and edited files, stop the old runtime, and import into Preview. Do not uninstall the old app until migration is verified. Only run one runtime at a time because the ports are shared.

`preview-build.json` identifies the exact commit, APK checksum, application ID and signing certificate. Publication requires backend/JVM tests, ARM64 database integration, the Windows/DLL/Direct3D/input probe, full client-runtime archive roundtrip, APK compilation and lint. New Android management workflows still require the user's device acceptance tests.
