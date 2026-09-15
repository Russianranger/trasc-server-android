TRASC Server Android **0.4.0** adds **Turnip + DXVK (experimental)** and addresses the observed game CPU restriction.

- Turnip's Qualcomm driver, Vulkan presentation probe and DXVK D3D9 module are bundled with the APK. The first launch checks actual hardware and presentation. If the check fails, select VirGL and export logs.
- CPU affinity → Allow available cores removes the game's observed CPU 0 restriction within Android's currently allowed cores. Choose Let the game choose to restore previous behavior on the next launch. No client INI edits.
- The new path still copies frames into the existing in-app display. It is not yet Winlator's direct presentation path; physical-device rendering and performance need testing.
- DXVK shows FPS and device identity inside the game. WineD3D's graphics-threading option does not apply to this renderer. Existing native dinput8, model helpers, controls, prefix and server data are retained.

**Device test:** stop both runtimes and update in place. Choose **Turnip + DXVK / 800×600 / Balanced CPU / Automatic runtime / Allow available cores**, with native DLL/model helpers on and verbose diagnostics and shadows off. Launch twice to separate one-time setup/shader compilation from a warm comparison. Check menus, character models, world movement and the DXVK FPS/device HUD; export logs after the second run. If launch or graphics fail, stop, return to VirGL and export the failure logs before further launches. No runtime download, client reimport, prefix repair or server rebuild is required. Hardware success and better FPS are not assumed before the Thor test.

---

TRASC Server Android **0.3.10** adds **Single + OpenGL worker (experimental)** to Graphics threading.

- Wine stays single-threaded while Mesa 22.3 batches GL commands on its native worker (`mesa_glthread=true`). Existing Multithreaded and Single thread explicitly keep this worker off. Switching modes does not repair or change the prefix.
- Exported state distinguishes requested batching from a worker actually observed in the current Wine launch. `client-threads.log` samples bounded thread CPU ticks, last CPU and available CPU masks every ten seconds. It does not log command lines, environments or unrelated processes, and does not change CPU affinity or Android policy.
- Preserve a bounded copy of ROF2's previous `dbg.txt` as `client-game.previous.log` before a new client launch, and preserve `client-state.previous.json`. Current startup diagnostics stay in their original location. This fixes the missing first-run loading evidence in the latest comparison.
- Latest 0.3.9 movement samples: Wine median approximately 6.0 presents/s with Multithreaded and 7.7 with Single thread. Android bitmap delivery generally tracked these rates; decode/apply was about 1–1.5 ms per update. These are separate scene samples, not identical-path benchmarks. The previous run's game startup log was not retained, so its asset/UI durations cannot be reconstructed precisely.

**Device comparison:** stop both runtimes and update in place. Keep **VirGL / 800×600 / Balanced CPU / Automatic runtime**, native DLL/model helpers on, shadows and verbose diagnostics off. First use **Single thread** for 30–60 seconds of movement in the same scene; stop, select **Single + OpenGL worker**, and repeat the route. Export logs after the second run. Return to Single thread if batching is worse or affects graphics. The first launch after the APK update can refresh the Wine prefix once; a repeat launch avoids comparing that one-time setup with a warm launch. No runtime download, client reimport or server rebuild is needed. Turnip/DXVK is still not included, and Thor FPS improvement from this option requires device testing.

---

TRASC Server Android **0.3.9** adds a graphics-threading comparison and measures the remaining frame-rate bottleneck.

- Display decoding and CopyRect reuse bounded buffers, reducing repeated allocations while preserving the current graphics path.
- **Graphics threading → Multithreaded** retains Wine's previous default. **Single thread** uses Wine 10's supported per-launch setting to remove the graphics command queue. Compare both; single threading is not assumed to be faster. No prefix registry changes or runtime reimport.
- The client bar shows **Wine** presentations per second and **Display** new bitmap draws per second separately. Wine uses its aggregate fps channel, about one line per 1.5 seconds, with the first incomplete interval discarded. A dash means no recent sample. Display measurements include transfer/decoding/Canvas submission timings in `client-presentation.log`, sampled every five seconds and bounded with rotation. Canvas submission is not a GPU timing; neither counter measures physical monitor refresh.
- Device 0.3.8 evidence: acceleration actually enabled, repeat startup 18.138 → 8.175 seconds, global assets 102 → 46 seconds, game UI 48 → 35 seconds. Graphics remained correct; frame rate is still unacceptable. These are separate user runs, not a controlled benchmark.

**Device comparison:** stop both runtimes and update in place. Keep **VirGL / 800×600 / Balanced CPU / Automatic runtime**, native DLL/model helpers on and verbose diagnostics off. Leave shadows off. First check **Multithreaded** in the same scene for 30–60 seconds, then stop the client, select **Single thread**, and repeat. Export logs after the second run; both current and previous sessions are retained. Note each Wine/Display counter while turning or moving. If single threading regresses, return to Multithreaded. The first APK launch may refresh the Wine prefix once. No server rebuild, client move, prefix repair or runtime download is required. Turnip/DXVK is not included yet; actual device FPS improvement from this release remains unverified.

---

TRASC Server Android **0.3.8** enables a verified PRoot syscall accelerator for the client.

- **Runtime mode → Automatic** runs an isolated file/socket/child-process check and requires actual accelerator activation before starting Wine. An unsupported or failed check selects Compatibility. A hung check aborts startup and offers the manual Compatibility path.
- **Runtime mode → Compatibility** uses the previous tracing mode. CPU profile and graphics selection remain independent.
- Client files already live in app-private internal storage. `D:` is a Wine mapping to those files, not an SD card or shared-storage mount; no file migration or drive-letter workaround is needed.
- Exported state records storage mapping and actual acceleration evidence. `client-runtime-probe.log` records the preflight; `client-proot.log` records the current launcher/session, with one previous log retained.
- Existing prefix reuse, graphics fixes, native DLLs and controller settings are retained. Server runtime mode is unchanged.

**Device test:** stop both runtimes, update in place, and retain all installed files. Use **VirGL / Balanced / Automatic**, 800×600, native DLL/model helpers on and verbose diagnostics off. After the first post-update launch, stop and launch again; enter the same zone and export Logs. If launch or behavior regresses, use **Runtime mode → Compatibility** and repeat with the other settings unchanged. No runtime download or server rebuild is needed. Device FPS remains unverified.

TRASC Server Android **0.3.7** adds a Balanced CPU profile and reuses verified Wine prefixes to reduce repeated startup work.

- **CPU profile → Balanced** uses larger Box64 translation blocks and default flag handling, retains x86 memory-order barriers, and reports the actual CPU count instead of the bundled 64-core Wine override. **Compatibility** restores the previous CPU settings. Neither option changes the graphics fixes.
- A completed Wine prefix is reused on later launches. Runtime/graphics-module changes, missing system files or interrupted checks trigger a full update. The first launch after installing 0.3.7 still performs one update; compare the **second** launch as well.
- Exported client state includes startup-stage durations, CPU settings and inherited CPU affinity. Selected ROF2 launch options are remembered and included in session backups.
- Turnip is not installed by this update. A direct Turnip/DXVK path is a separate implementation milestone; see [performance findings and integration plan](client-performance.md).

**Device test:** stop both runtimes, update the APK in place, and retain the installed client/runtime/prefix/model helpers. Start the server. Select **Android GPU / VirGL**, **Balanced**, **800×600**, native dinput8 and model helpers enabled, diagnostics off. Launch, visit the same character/zone, stop the client, and repeat once. Export Logs after the second attempt. If behavior regresses, select Compatibility and repeat at the same resolution. No runtime download or server rebuild is required. This build does not claim a measured Android FPS improvement before device testing.

TRASC Server Android **0.3.6** corrects texture storage and legacy Wine shaders in the experimental Android GPU path.

- DXT1/3/5 artwork now uses consistent RGBA host storage. Uploads preserve texture subregions, mip levels, alpha and sRGB; other compressed formats keep their own paths.
- The APK includes a matching Wine 10 graphics module with the GLSL 1.20 specular/fog variable correction. It applies at launch to the installed runtime; no client/runtime reimport or prefix repair is needed.
- GPU startup now samples compressed texture pixels instead of accepting a plain color clear alone. CI additionally exercises OpenGL 2.1 and compares unpatched/patched Wine with our own shader fixture.

**Device test:** stop both runtimes, install this APK over the existing preview, and reopen the app. Start the server, choose **Client → Graphics → Android GPU / VirGL (experimental)** at **800×600**, retain native dinput8/model helpers and leave verbose logging off. Check menu backgrounds, loading artwork, character/model textures, then enter the same zone and check movement. Export Logs afterward. Software remains the recovery option. Actual Adreno rendering and performance still require your device test.

TRASC Server Android **0.3.5** adds an experimental Android GPU path for the next performance test.

The 0.3.4 device pass confirms working models, animations and movement. Its logs show zero HMD/model failures and global asset initialization in 1m58s. Rendering still uses CPU llvmpipe, which remains a major performance limit.

- **Client → Graphics → Android GPU / VirGL (experimental)** forwards WineD3D rendering through the packaged native Android GLES helper. Software remains the default and recovery option.
- Verify a mapped GLX drawable and rendered pixel before Wine starts. Record actual guest and Android driver identity in exported logs/state.
- Own the GPU helper for the client session, stop it during cleanup and backups, report driver failures, and bound its diagnostic logs.
- Retain `eqgame.exe patchme`, native/system DirectInput, installed Microsoft model helpers, quiet logging and existing runtime/prefix/controller data.

**Device test:** stop both runtimes and update this APK in place. Keep the existing runtime and prefix; no server build, download, helper reinstall, Prepare or reimport is needed. Start the server, choose **Android GPU / VirGL (experimental)** at **800×600**, keep native dinput8/model helpers enabled and verbose diagnostics off, then launch ROF2. Check models, animation and movement in the same zone. Export Logs after the test. If GPU setup or graphics fails, stop the client and select **Software** for comparison.

ARM64 tests exercise real Windows Direct3D9 output, native animated models and held movement input over the GLES bridge, including PRoot. The CI host uses a software GLES driver; physical Adreno compatibility and playable ROF2 performance require this device test. GPU mode adds no Termux dependency and retains the embedded display. CPU translation and display transfer costs remain.

Previous updates follow for reference.

TRASC Server Android **0.3.4** adds DirectX model helper installation for the invisible-character problem after the first successful world entry.

- Install the two Microsoft x86 D3DX libraries used by ROF2 from the official June 2010 redistributable. Choose **Install DirectX model helpers**, or select the matching offline `directx_Jun2010_redist.exe`.
- Verify the entire download before extraction, stage and verify both Windows DLLs, preserve the previous helper installation, and remove only the app's temporary installer copy. Existing client, Wine prefix and server data are retained.
- **Use installed DirectX model helpers** enables native-first loading for d3dx9_30/35. Wine's original prefix files are retained in `client/prefix/trasc-directx-originals`. Disable the option for a built-in Wine comparison. Actual native model-library loading appears separately from DirectInput.
- Keep normal logging, `eqgame.exe patchme` and native/system DirectInput forwarding. The Linux runtime images are unchanged.

**Device test:** stop both runtimes, install this APK in place, then open **Client → Install DirectX model helpers**. Keep the existing client runtime and prefix. Start the server and launch at **800×600**, with native dinput8 and model helpers enabled, verbose diagnostics off. Check models at character selection, enter Greater Faydark, try movement, then export Logs. No client reimport, server rebuild or prefix repair is needed.

The last session reached the game world and camped normally. It still reported 573 model initialization failures while using Wine's built-in D3DX functions; the relevant animation/skinning APIs return E_NOTIMPL in Wine10. This change targets that compatibility gap. Rendering still uses CPU llvmpipe; it does not enable the Thor GPU or promise playable FPS. Successful device model rendering remains to be confirmed.

Previous updates follow for reference.

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

For the current device pass, use the comparison sequence at the top of these notes. Export Logs after the attempt.

Backups contain accounts, credentials and client files and are not encrypted. Save them privately outside the app. Only the private temporary copy of an imported session/client ZIP is removed; the selected source document remains intact.

**Older 0.1.0/0.1.1 installations:** their signing key was lost before 0.1.2, so this Preview application installs alongside them. Their data is not transferred automatically. Export the database, source/maps archives and edited files, stop the old runtime, and import into Preview. Do not uninstall the old app until migration is verified. Only run one runtime at a time because the ports are shared.

`preview-build.json` identifies the exact commit, APK checksum, application ID and signing certificate. Publication requires backend/JVM tests, ARM64 database integration, the Windows/DLL/Direct3D/input probe, full client-runtime archive roundtrip, APK compilation and lint. New Android management workflows still require the user's device acceptance tests.
