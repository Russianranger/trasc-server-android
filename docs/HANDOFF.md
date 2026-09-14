# Development handoff — 2026-09-14

## Published: 0.3.4 model helper compatibility fix

- Device bundle `logs-3194322454755682154.zip`: app 0.3.3 on Android 13 / AYN Thor, 800x600, native and system DirectInput loaded, quiet Wine logging. User reached character selection and Greater Faydark with invisible models, limited movement and responsive UI.
- Global asset initialization improved from 53m11s to 9m14s (19:44:48–19:54:02 UTC). Character selection 19:54:07; gfaydark main loop ready 19:58:39; normal camp 20:01:51 and quit 20:02:42. Latest Wine log 31,746 bytes. Server accepted/saved the character and saved 404 zone spawns on shutdown; this alone does not verify later state restoration.
- Game log contains 573 HMD/model initialization failures. Wine loads built-in d3dx9_30/35. Previous verbose bundle includes repeated RegisterAnimationSRTKeys, Compress and ConvertToIndexedBlendedMesh stubs. Wine 10 source returns E_NOTIMPL: https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/d3dx9_36/animation.c and https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/d3dx9_36/skin.c. Native-model tests reproduce this failure with built-ins and pass with Microsoft libraries. Actual ROF2 model rendering remains pending device verification.
- Graphics remains llvmpipe LLVM 15 / Mesa 22.3.6, Accelerated:no. This update provides model compatibility, not hardware acceleration or promised playable FPS. A few texture/framebuffer errors remain in the device log. Movement hold/release passes open-fixture tests; verify the game's own movement bindings and performance on device before diagnosing further.
- APK-only installer: official Microsoft June 2010 DirectX redist 100,275,120 bytes / SHA256 `053f76dcbb28802e23341b6a787e3b0791c0fa5c8d4d011b1044172dbf89c73b`. Client tab supports online installation or picking the matching offline EXE. Original source installer retained; only app cache copy removed. Microsoft DLLs are not included in the APK, Git repository, runtime image or published artifacts.
- Native Android cabextract 1.11 source SHA256 `b5546db1155e4c718ff3d4b278573604f30dd64c3c5bfd4657cd089b823a3ac6`, downloaded from Debian's mirror of the same upstream tarball after the upstream host returned 403 on an x64 CI runner. Source/build recipe accompanies APK in launcher-sources.tar.gz. Built ARM64 PIE with /system/bin/linker64 and 16 KiB alignment. Android SDK setup requests platform-tools explicitly; obsolete SDK tools package caused the initial CI setup failure.
- Portable Java installer verifies the entire redist, extracts only x86 D3DX30/35, verifies PE32 headers, stages both files and a hash manifest, preserves previous install, and recovers interrupted directory swaps. Helper source directory work/client/directx; previous generation work/client/directx-previous. Runner validates both files before replacing only prefix/drive_c/windows/syswow64/D3DX30/35, snapshots originals under prefix/trasc-directx-originals, and rolls back partial-copy failure.
- Verified library hashes: d3dx9_30.dll 2,388,176 bytes `5edeed79f2359527a55b8189cfa8b9b121cd608d44eead905a0f3436938ad532`; d3dx9_35.dll 3,727,720 bytes `2198022938156b790e9cfb0f7997494b66a11a1ad49b395be58251d635b66b26`.
- Native helpers default on for client launch (installation required), off for Wine desktop. Disable model helpers explicitly for built-in comparison. Actual native/builtin model-load evidence is recorded separately from DirectInput and retained across log rotation. Preserve patchme, dinput8=n,b, quiet logs, CPU translation settings, existing client/prefix/server data and both runtime recipes.
- Tested code commit `af45c8af790aa143fa43fcf1cc6202dab7d2b2e3`. Branch Android/UI/database https://github.com/Russianranger/trasc-server-android/actions/runs/34893658488 and ARM64 client https://github.com/Russianranger/trasc-server-android/actions/runs/34893658055 passed. 44 Python tests, native session/controller/RFB tests, browser management flows, full seed/database backup+restore, APK compilation/lint, native Android extractor/source packaging all passed.
- Production Java extraction test downloaded the official package, extracted both correct 32-bit DLLs, rejected a corrupt same-size archive before extraction, retained existing installation, and recovered an interrupted swap. Full client runtime extraction/backup/restore with all hashes passed.
- Direct ARM64 and pinned PRoot both passed: real PE32 launch, native proxy/system DirectInput forwarding and its native-only negative control; W held/release in polled DirectInput state; native D3DX30/35 registration, sampling, compression, indexed skinning and visible animated model pixels over private RFB. Built-in negative control exits 31 on E_NOTIMPL. Test code uses C vtables for MinGW D3DX interfaces and DIDFT_OPTIONAL for standard 256-key format; initial fixture failures were corrected without changing user input settings.
- Local exec workspace disconnected during implementation. Logs were read and upstream downloads verified before disconnect; source changes continued through the GitHub plugin, with CI providing compile/runtime validation. No claim of testing the modified APK directly on Thor.

- Published Preview 0.3.4 / version code 10 from `af45c8af790aa143fa43fcf1cc6202dab7d2b2e3` on main: https://github.com/Russianranger/trasc-server-android/actions/runs/34894293758 passed APK, database, full ARM64/PRoot and publication jobs. Pinned preview signing identity was reused and verified by apksigner; application ID remains `io.github.russianranger.trasc.preview`, certificate SHA256 `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`.
- Published APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 298,346 bytes, SHA256 `b784e444b23b1fc1e9a0fa555cb4caea497d6a1538d9aa7ec375c51950753d41`. Launcher source archive 1,499,943 bytes, SHA256 `a113082ac8fc944a1470e5567e831cc42e7363ef4c8db89edc3d25d1be0a6328`; includes cabextract source/build recipe.
- Repacked client runtime 1.0: 353,710,669 bytes, SHA256 `5248e5d3720881b8d8c1fbaea10667b944a28f86e2fcd78ca75c349a7a3d736f`. Runtime recipe/image unchanged; existing device installations need only the APK and one-time DirectX helper installation. Both published tags point to tested code `af45c8af790aa143fa43fcf1cc6202dab7d2b2e3`.
- Verification read back release tags, versioned release notes and GitHub asset digests, plus successful CI signing/build gates. Local execution remained unavailable; a local APK download/hash computation was not performed. The connector/browser could not fetch the release JSON asset bodies. Do not describe those as independently downloaded/verified.
- Next user test: stop both runtimes, install APK in place, Client → Install DirectX model helpers (or matching offline Microsoft EXE), keep current runtime/prefix/imported client, start server, launch 800x600 with native dinput8 and model helpers on, verbose off. Verify character models, world rendering and movement, then export Logs. Check `native_d3dx_requested`, both native `model_libraries_loaded` entries and game HMD errors. Preserve user movement bindings; compare with the game's configured movement keys if movement still fails. No Prepare, prefix repair, runtime redownload, server rebuild or client/database import is required.
- After device model validation, major next work is a feasible hardware graphics path for the Thor's Adreno GPU; llvmpipe is still CPU-only. Audio remains later work. This documentation follow-up does not change the published APK.

## Previous release: 0.3.3 client logging performance fix published

- Latest device evidence: `logs-547215203498946041.zip`, Android 13 / AYN Thor, app 0.3.2, native and system dinput8 loaded, 800x600 llvmpipe. User confirms client boots but is abysmally slow. `patchme` is present. No prefix repair needed.
- Full new bundle read from scratch. Wine trace: 1,059,025,481 bytes / 9,258,244 lines. Most output is routine DBG_PRINTEXCEPTION_C / unwind tracing plus 240,177 D3DX RegisterAnimationSRTKeys fixme lines. Do not misdiagnose debug-print exceptions as crashes. Game dbg.txt: initialization starts 17:38:02 UTC, global data 17:42:54–18:36:05 (53m11s), character selection 18:36:11. Session stopped explicitly at 18:51:59.
- Graphics reports llvmpipe LLVM15 / Mesa22.3.6, Accelerated:no. Software GPU emulation is a remaining limit. Xvnc's 3,230 updates across the long session include idle time; not an FPS benchmark. Box64's Cortex-A510 banner does not establish forced CPU affinity. No unsupported CPU/GPU tuning in this pass.
- Implemented normal WINEDEBUG `-all,+timestamp,+pid,err+all,trace+loaddll`; removed always-on module/seh/fixme output. Explicit verbose checkbox defaults off and records mode in state. Kept patchme, dinput8=n,b, conservative dynarec flags and current images. Source reference: Wine 10 dlls/kernelbase/debug.c (OutputDebugString still raises a debug exception even with tracing off).
- Wine output uses a dedicated pipe drain/rotation thread, captures DLL/fatal evidence before rotation, retains two 8MiB segments plus one capped previous session. Old huge logs are shortened to start/final excerpts on next launch, avoiding another gigabyte export. State includes emitted byte/rotation counts, not inferred FPS. Module events cannot evict actual DLL-load proof.
- App version 0.3.3/code9; application ID, pinned certificate, server runtime1.1 and client runtime1.0 unchanged. User only needs APK update; no runtime download, prefix repair, Prepare or data import.
- Local 41 Python tests passed, including rotation, early-load evidence, fragmented fatal messages and oversized previous-log migration. Host JVM/native input/archive checks run. ARM64 CI adds a 512-call OutputDebugString comparison with output-volume assertions and informational timings; DirectInput negative/positive controls, D3D pixels and controller input remain required.
- Tested code commit: `321d42103336b2a5a41d3a1fa47aa31149283634`. Branch APK/UI/database https://github.com/Russianranger/trasc-server-android/actions/runs/34884617744 and ARM64 client https://github.com/Russianranger/trasc-server-android/actions/runs/34884617402 passed all checks. APK compilation/lint, 41 Python tests, native archive/input, browser flows and database seed/cold migration passed. Native/system forwarding, D3D visible pixels and mouse/keyboard passed both directly and through PRoot. Full runtime extraction/backup/hash roundtrip passed.
- 512-call OutputDebugString workload, including process startup: direct ARM64 normal 0.365s / 8,389 bytes; verbose 0.577s / 2,396,722 bytes. PRoot normal 1.573s / 8,471 bytes; verbose 2.638s / 2,396,804 bytes. This confirms suppression and reduced overhead in that fixture; do not extrapolate to ROF2 FPS or the whole 53-minute asset load. Wine still handles debug-string exceptions with tracing off.
- Main release https://github.com/Russianranger/trasc-server-android/actions/runs/34885237951 passed all jobs and published both assets. Main PRoot comparison repeated successfully: normal 1.522s / 8,471 bytes; verbose 2.486s / 2,396,804 bytes. Pinned-certificate verification and Android lint passed. Both release tags point to `321d42103336b2a5a41d3a1fa47aa31149283634`; this follow-up changes only the handoff.
- APK 0.3.3/code9: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 256,626 bytes, SHA-256 `65e8ec0ebfca100999dc61afe973b39ad99652b3d92f01146dc83ab7f2e082e9`. Preview manifest confirms commit, version, application ID and the preserved pinned certificate.
- Repacked client-1.0 archive: 353,710,659 bytes, SHA-256 `b370ec771fb4d6d9b2b6ff6ae6af2efebc1e731007284cb623d462af96078250`. Runtime recipe/image unchanged; existing installations need only the APK.
- Publication verified by reading back both tags/release asset digests, downloading the APK, matching its SHA-256/size, inspecting its packaged supervisor/UI fixes, and checking both release manifests.
- Device retest at same 800x600 with verbose diagnostics off, native DLL on; report time to character select/responsiveness, then attempt world entry if practical and export Logs. No device speedup/playable FPS is claimed before retest.

## Previous release: 0.3.2 system DirectInput fix published

- Workspace access recovered. Full `logs-5544659252330987853.zip`, client-runtime.log, client-state.json and client-wine.log have now been read. Earlier text-only notes below are historical.
- Device is Preview 0.3.1, Android 13 / AYN Thor, 800x600 software graphics. Prefix repair completed at 12:13:54 UTC; subsequent 32-bit preflight passes and native DINPUT8 loads.
- Confirmed configuration defect: during native DLL process attach, `C:\windows\system32\dinput8.dll` resolves to syswow64 and Wine reports environment override `n`, then status c0000135. The add-on's `Release-NMS-Client/eqgame_dll/dllmain.cpp` loads that absolute system path and returns E_FAIL from DirectInput8Create if its function pointer is missing. This is an input initialization blocker, not another missing kernel32 failure.
- The later `wined3d_swapchain_resize_buffers` back-buffer diagnostic occurs before teardown. Wine 10 source logs that error and continues to return WINED3D_OK in that path; it does not alone establish the game's exit cause. No unsupported renderer/DXVK changes in this pass. Original game exit code remains uncaptured: launcher_exit is Explorer's result.
- Fix: `dinput8=n,b`, separate native-imported and built-in-system load evidence, sticky evidence across log tail windows, +seh exception traces, timestamped session boundaries and stop_request/signal reasons. Do not equate two load traces with successful plugin functionality.
- Native log inventory/export now includes selected root client and Logs/logs startup diagnostics, with case-insensitive names and symlink/traversal checks. Settings, game binaries and character chat are excluded. This addresses the missing dbg.txt / dinput8.log evidence in the old bundle.
- Expanded open fixture matches the add-on's GetSystemDirectory + LoadLibrary pattern and creates DirectInput keyboard/mouse devices. ARM64 tests must pass native forwarding plus D3D/display input, with negative control native-only exit 23 and fixed n,b exit 0, directly and through production archive extraction + pinned PRoot. No proprietary client files in CI.
- Verified code commit: `52d3a1b6d0187eb9e47517f180ea79e12c0e44d1`. Branch APK/UI/database checks passed: https://github.com/Russianranger/trasc-server-android/actions/runs/34868688109 . ARM64 runtime/PRoot checks passed: https://github.com/Russianranger/trasc-server-android/actions/runs/34868687404 . Both environments reproduced native-only exit 23 and corrected n,b exit 0; keyboard/mouse device creation, D3D rendering and display input passed. 38 Python tests and JVM archive/log/input/prefix checks passed. APK 0.3.2 / version code 8 keeps the application ID and signing certificate. Runtime images are unchanged; no runtime download or prefix repair required.
- Main release workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34869328238 — all jobs passed, including both DirectInput controls in PRoot, preserved certificate verification, database/session tests, browser flows and APK compilation/lint. Both release tags point to `52d3a1b6d0187eb9e47517f180ea79e12c0e44d1`. This handoff follow-up changes no packaged code.
- Published APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 254,894 bytes, SHA-256 `7ea59d659b483f999772772548db73f9372468b9db3175628801b0e129745d66`.
- Repacked client-1.0 archive: 353,710,716 bytes, SHA-256 `3d9a423f750c00fcdb72545690cb07f6b5850ff6b580b58465ab0924a9f1a2cb`. Both runtime images remain unchanged; existing users only need the APK.
- Publication verified: release tags and asset digests read back; downloaded APK matches the published SHA-256 and size. Preview manifest confirms 0.3.2, the expected commit/application ID and pinned certificate; client manifest matches the same commit and published archive hash.
- Next device pass: stop runtimes, update in place, keep current prefix, start server, launch native ROF2, export logs. Preserve server/client data. No new physical ROF2 acceptance is claimed.
- Primary diagnosis references: https://github.com/Russianranger/Triptych-Triumvirate/blob/main/Release-NMS-Client/eqgame_dll/dllmain.cpp and https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/wined3d/swapchain.c .

## Previous text-only device follow-up: 32-bit Wine and native dinput8 confirmed

- Following the 0.3.1 update, the user reports that the ROF2 window appeared for approximately ten seconds before disappearing. Latest bundle is `logs-5544659252330987853.zip`; individual client-runtime.log, client-state.json and client-wine.log were also attached. The analysis workspace failed to initialize, so these attachments have NOT been read. Evidence below comes only from text pasted by the user.
- Pasted client-state.json reports `prefix_files_ready: true`, `wine32_ready: true`, `native_loaded: true`, mode client, resolution 800x600, launcher_exit 0, final phase stopped, and no error field. Wine's actual native-load trace identifies `D:\\DINPUT8.dll` at 7AE60000 in process 0194. This confirms imported native DLL loading, not successful plugin behavior or game acceptance.
- The pasted Wine tail contains process-detach/shutdown traces at approximately 146758–146759. It does not include the reason for shutdown. Do not diagnose a missing dependency, graphics failure, plugin failure, or clean game exit from this tail alone.
- Code review confirms `launcher_exit` is the return code of Wine Explorer, not a captured eqgame.exe exit code. The final supervisor phase stopped can follow a stop request/signal and cleanup; it does not identify why the earlier game window disappeared.
- Next evidence needed: client-runtime.log and the earlier client-wine.log section immediately preceding the first shutdown/detach sequence, including any errors/exceptions. Clarify whether the user pressed Stop after the window disappeared to distinguish later supervisor cleanup from the original game exit. Preserve the working prefix; no further repair/reimport is indicated by the pasted state.
- No new APK or runtime change has been made for this follow-up. Keep 0.3.1 and the existing published artifact hashes below.

## Previous milestone: ROF2 black-screen recovery, Preview 0.3.1 published

- Published code commit: `01138918df6d9a68a45af8f36a3860be3b4771b5`. Both `preview` and `client-runtime-v1` tags point to this commit. This handoff-only follow-up changes no APK/runtime code.
- Main release workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34800190134 — database, APK, client runtime and publication jobs all passed. Includes 36 Python tests, JVM archive/input/prefix preservation, browser management flows, Android compile/lint, preserved signing certificate, full server database/runtime integration, client archive roundtrip and PE32/DLL/Direct3D/input probes both directly and through pinned PRoot.
- APK 0.3.1 / version code 7: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 253,622 bytes; SHA-256 `f81d0d826ec3883ee904de5b01f3d96ce1647e9ac7f7f2020fda09003548966c`. Application ID and certificate remain the pinned values documented below.
- Repacked client-1.0 archive: 353,710,662 bytes; SHA-256 `e1f37b8b29f47ded4eb859d6b7cd8add86b113843a3aec06933be309fbf3bece`. The Wine/Box64 image and recipe are unchanged; no client runtime redownload is required. Server runtime remains 1.1.
- Publication verification: both tags and release asset digests read back from GitHub; downloaded APK hash/size and preview/client manifests match the code commit, version and preserved application identity.

- Previous 0.3.0 failure bundle: `logs-8799882545351199396.zip`, user confirms right-stick mouse input but black display on ROF2 launch.
- Device evidence: VNC frames/input and llvmpipe OpenGL 4.5 initialize. `eqgame.exe patchme` is correctly passed and the PE32 EXE loads. Wine then reports `could not load kernel32.dll, status c0000135`; native dinput8 is not reached. Explorer returns 0 and the old supervisor continues presenting an empty display. First prefix setup was interrupted by Stop. This suggests a prefix or Android loader problem; do not claim the exact underlying cause is established from these logs alone.
- Existing optional libXcomposite/codec/Bluetooth and CPU-info warnings are separate from the confirmed fatal loader error. No runtime dependency upgrade is required for this APK checkpoint. `/sys` is now bound for CPU discovery.
- Working branch `codex/client-loader-fix`, base main `662b24f8a2fdbcb4fd73828909fa1e284c22af85`. Baseline commit `80663be45652a436b2c9e37e577ec747e19159c6` added real production archive extraction followed by the same pinned PRoot code compiled for Linux ARM64. Baseline PRoot probe passed: https://github.com/Russianranger/trasc-server-android/actions/runs/34799154722 . This narrows the failure but does not reproduce Android SELinux/kernel behavior.
- Shipped changes: 32-bit runtime/prefix core-file inventory (`client-prefix.json`), actual SysWOW64 cmd.exe bootstrap before launching ROF2, separate prefix logs, fatal-loader/dependency detection and visible failure dialog, normal Stop handled without a spurious failure traceback, backed-up Repair Wine prefix action, and launch `patchme` retained.
- Repair moves only `client/prefix` to a unique `client/prefix-backups/` directory and starts a fresh prefix/Wine desktop. Game files, controller profile and server data remain intact. Host JVM regression verifies settings/drive symlinks preserved and game untouched.
- ARM64 tests passed with a non-large-address-aware PE32 fixture with a 20 MiB image and 32-bit preflight enabled, both directly in the runtime and through PRoot: https://github.com/Russianranger/trasc-server-android/actions/runs/34799675371 . This remains an infrastructure test, not actual ROF2 acceptance.
- APK/UI/database gates also passed for `7641d28e6196a77ffad3b4ff28f8465fb76ba59a`: https://github.com/Russianranger/trasc-server-android/actions/runs/34799675523 . Final refinements disable duplicate launch controls and require a terminating loader error before treating optional missing dependencies as fatal; the main release gates passed with these refinements included.
- Next device sequence: update in place, stop the client, Repair Wine prefix, wait for desktop and 32-bit check, stop, start server and Launch ROF2. No reimport/recompile/runtime redownload is needed. Export logs after the attempt, including client-prefix.log/json and client-wine.log.


## Previous milestone: embedded client 0.3.0

The user confirmed: “Session backup and restore worked perfectly. control inputs work, client input works. Lets move to the next step with the client.” Latest bundle `logs-338733800756477711.zip` reports 0.2.1 on Thor Android 13, completed client ZIP import, and no current runtime-start failure. The confirmation concerns the previous input diagnostic; actual ROF2 execution inside this app remains the next physical test. Do not redo server/database installation.

### Code and verification

- Client milestone merged into main: `a472dea0d914f6279a2d4179920d0b050823ec07`, developed on `codex/client-bootstrap`. APK 0.3.0 / version code 6. Server runtime stays 1.1.
- Final branch APK/UI/database workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34788669730 — passed.
- Final branch ARM64 client workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34788669699 — passed.
- Main release workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34788877454 — all jobs passed; signed APK and client runtime published. Both release tags point to the code commit above. This handoff-only follow-up changes no APK/runtime code.
- 34 Python tests passed; host JVM archive/RFB/input tests passed; management browser flows passed; Android compilation/lint passed. Existing full server-runtime archive, offline seed import, SQL/rules and cold database migration checks passed.
- Real ARM64 probe passed: Box64/Wine executes our own PE32 Windows EXE, loads our native test dinput8 DLL, presents Direct3D9 pixels through the private RFB socket, and receives mouse/keyboard events. The probe contains no EverQuest code. This does not establish compatibility with the user's modified ROF2 client.
- The actual client runtime archive passed production TarExtractor/SessionArchive extraction and full roundtrip: executable permissions, multiarch paths, file inventory and all restored hashes verified. Existing full server runtime has its own separate gate.
- Development issues resolved: missing emulated x86 libgcc/libstdc++/libunwind; display test waited too early and assumed a value for RGB888's undefined padding byte; client-only archive fixture needed the required server marker. Do not weaken production archive checks to accommodate test fixtures.

### Published artifacts

- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — 250,918 bytes; SHA-256 `e96e53c6347470ea3f19f7be1edb67e64004fec0ed6bc6310eda859e0f9381df`.
- Client runtime: https://github.com/Russianranger/trasc-server-android/releases/download/client-runtime-v1/client-runtime-arm64.tar.gz — 353,710,645 bytes; SHA-256 `31fa8092b9679d861e853542d0ee05a7762c5740398b5efe8271486b64a98e18`.
- `preview-build.json` identifies 0.3.0 / code commit above / the preserved application ID and certificate. `client-runtime-manifest.json` identifies client-1.0 / the same source commit / matching archive hash and bytes. Both tags and asset digests were read back from GitHub; the downloaded APK hash and manifest contents were independently checked.
- Main release gates passed: 34 Python tests, host JVM, browser flows, APK compile/lint/preserved signing certificate, full server database/runtime integration, actual ARM64 Windows/DLL/Direct3D/input probe, actual client-runtime archive roundtrip.
- Reuse the existing server runtime and imported game. Only the separate client runtime is new. Actual Thor Wine/ROF2 acceptance remains pending.

### Implementation

- Separate Debian rootfs in `work/client/runtime`, Wine 10.0 WoW64 + pinned Box64 0.4.4, WineD3D/llvmpipe baseline. Existing server rootfs/database is retained.
- `ClientRuntime` uses the packaged PRoot loader for the second environment; it installs the release runtime online with checksum validation or from an offline archive, and preserves the prefix/game during replacement.
- `backend/client_runner.py` supervises Wine and TigerVNC. RFB listens only on a private Unix socket, mode 0600; no TCP RFB/X11 listeners, random X11 authorization cookie. Prefix initialization is bounded and supports stopping.
- `ClientActivity`, `RfbConnection`, `DisplayInput` implement native display, saved controller mappings, touch, physical keyboard/mouse, text Type/Send + Enter, focus releases and combined input reference counts. Android Back returns to management without stopping the client.
- Client tab offers runtime setup, Wine desktop, resolution, ROF2 launch, return/stop and preparation. Preparation generates the four handshake files into the root/Resources, writes login endpoint and windowed resolution, preserves unrelated INI settings/DLL, and retains originals in `backups/client-setup/` with rollback on errors.
- Native dinput8 is the default request (`dinput8=n`); PE32 executable/DLL architecture must match. Only Wine's actual native loaddll trace marks it confirmed. Built-in mode is an explicit diagnostic comparison. Desktop mode does not claim DLL loading.
- Client start is coordinated with queued/running import/preparation jobs. Rejecting a second launch does not kill the current client. Stopping the server runtime retains the foreground service while the client is active; notification Shut down stops both.
- Client runtime, imported files, controller profile and Wine prefix are part of the complete session client component. Temporary sockets/auth/process state stay under home/tmp outside archives. Complete backup/restore stops the client first. Prefix D: maps to `/client`.
- Logs include client-runtime.log, client-wine.log, client-display.log, client-graphics.log and client-state.json; native log export remains usable with the server closed.
- Build recipes/workflow live in `client-runtime/`, `scripts/build-client-runtime.sh`, `.github/workflows/client-runtime.yml`. Main preview publication is gated on the client workflow as well as APK/database jobs. Sources accompany runtime binaries.

### Next device pass

Follow `docs/client-runtime.md`: update in place, download the separate client runtime, try Wine desktop at 800x600, stop, prepare the already imported client, start the server, then launch ROF2 with native dinput8 enabled. Return and export Logs after the attempt, reporting visible screen/error and native DLL status. No server rebuild, seed import or client ZIP reimport is needed for the update.

Software graphics only. Hardware acceleration, sound, performance tuning and actual ROF2 login/world entry remain unverified/later work. Keep the existing Winlator fallback. Preserve application ID `io.github.russianranger.trasc.preview` and pinned certificate `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; never regenerate a lost preview key.

## Previous request: 0.2.1 export fixes

Latest device report: Preview 0.2.0 session export fails with `Unsafe session path: runtime/var/lib/dpkg/info/binutils-common:arm64.conffiles`. Log export then fails with `Failed to connect to /127.0.0.1:18775`, because backup preparation closed the runtime. Fix both and publish an in-place APK update; preserve the existing world and signing key.

### 0.2.1 fixes published

- Base: `fe84687345bcb4328ec6ab85a71c453829bd2073` (handoff after the published 0.2.0 code).
- `SessionArchive.confined` accepts ordinary Linux colons and still rejects drive prefixes, traversal, absolute paths, backslashes and NULs. Both export and restore share the fix.
- New platform-independent `LocalLogs` reads/lists/zips app and nested server logs without a backend; checks symlink parents/leaves, tails 64 KB for viewing and streams full snapshot lengths into bundles. Native status is included without loading credentials/settings/API tokens.
- MainActivity routes logs/export_logs directly to Android. Both UI log export buttons now consume the direct result instead of polling Python jobs. Backup failure persists to app.log and explicitly reports stopped-runtime recovery. The game server is not automatically restarted.
- Version 0.2.1 / code 5, same application ID and pinned certificate. No new runtime or server rebuild required.
- Local checks: 29 Python tests passed; native host-JVM roundtrip/log regressions passed; JavaScript syntax and whitespace checks passed. CI now also backs up/restores the complete published Debian ARM64 runtime, verifying every file hash; UI regression simulates backup failure with backend unavailable and tests both log buttons and readers.
- Published code commit / preview tag: `e61761bd0ea725061ffcd2305ff82edd158b1cdc`. This handoff-only follow-up changes no APK code.
- Successful workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34780884423 — database, APK and preview jobs all passed.
- Actual runtime roundtrip passed using the production TarExtractor/SessionArchive classes: more than 28,000 regular files restored with SHA-256 verification, plus inventory counts and executable-mode checks. The exact `binutils-common:arm64.conffiles` path roundtripped.
- ARM64 full seed import, rules/SQL checks and cold database migration passed. Browser tests passed both native log export buttons and nested log reading after a simulated session failure with the backend unavailable. APK compilation, Android lint and the pinned-certificate check passed.
- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk — **225,637 bytes**, SHA-256 `5667d5fc697cc48f347b2952b5065c8405083c3ad0aeae652a7fffa66136a2aa`. Release asset and preview tag were read back from GitHub after publication.
- Runtime 1.1 and the pinned signing certificate remain unchanged. The user subsequently confirmed session backup/restore and input on Thor; preserve those working paths. No reset, recompile or database reimport is required for this APK update.

## Previous feature request (retained context)

Implement in `Russianranger/trasc-server-android`:

1. All database rules in searchable, collapsible categories, with typed controls and field-specific validation for established limits.
2. Setup actions to back up and replace `maps/base/nektulos.map` and `maps/nav/nektulos.nav` from their matching `maps/legacy/` paths, and revert the pair.
3. Complete session ZIP export/import, usable by a fresh app before runtime installation. Include runtime, database, binaries, maps, logs, source, settings and client files. Preserve permissions/symlinks and validate before replacement.
4. Client tab, client ZIP import with removal of only the app's temporary ZIP copy, and configurable gamepad-to-keyboard/mouse input groundwork. Client execution/Wine/dinput8 loading is a later phase, not an acceptance claim for this build.
5. Publish a test APK and keep this handoff current.

The user explicitly declined any faction/deity change. Yukovis was a disposable Iksar beastlord testing login/persistence; Prexus (209) explained Cabilis hostility. Do not change the server fork or seed for that issue.

## Starting state and verified device progress

- Main starts at `f9dfa3ee14c7f0d4655780743a4967e24911c0d2`, app 0.1.2 / runtime 1.1.
- User confirmed on-device compilation, connection and character testing on AYN Thor Max, Android 13 ARM64.
- Runtime 1.1 includes uuid-dev. APK 0.1.2 fixes offline MariaDB initialization and nonzero default ruleset IDs.
- Current server source: `Russianranger/Triptych-Triumvirate` commit `18141ae0c9a11813733f08fa77db986951b853d6`.
- Preview application ID must stay `io.github.russianranger.trasc.preview` for in-place updates.
- Preserve the signing certificate pinned in `docs/preview-signing.sha256`. GitHub Actions cache `trasc-preview-signing-v2` contains `runtime-work/signing/preview.keystore`. Never generate a replacement key if the cache is missing.
- Main's Android workflow tests ARM64 MariaDB, builds/lints APK and publishes the preview release automatically after all gates pass.

## Implementation decisions

- Read every applicable `rule_values` row and source `common/ruletypes.h`; do not infer numeric bounds merely from a name containing Min/Max. Preserve sentinel negatives and very small XP multipliers.
- Nektulos layout comes from the server README: legacy/base → base, legacy/nav → nav. Do not copy files directly into the maps root or change water files.
- Native Android session archive is needed because a new installation has no Python/runtime yet. Stop server/database cleanly; stage and verify all files before swapping app data. No source ZIP deletion outside the app's private staging copy.
- Input mappings belong only to a focused client surface. Release held inputs on focus loss/tab change, disconnection or profile change. The initial surface is an input diagnostic; no game launch is advertised.

## Previous feature implementation: 0.2.0

- Feature implementation is committed and published: `rule_catalog.py`, `managed_content.py`, expanded Engine; native `SessionArchive`, `ControllerInput`, `ControllerManager`; RuntimeManager/MainActivity integration; rules/client UI and docs.
- APK version 0.2.0 / code 4; application ID/signing unchanged. Runtime 1.1 remains compatible.
- Local Python: 29 tests passed (including detection of map edits/imports after Apply). Host JVM archive/input tests passed (the local javac launcher is missing, but `java -m jdk.compiler/com.sun.tools.javac.Main` works; script includes fallback).
- Source parsing found all 1,122 active rules, 47 categories; no definitions missed. Static JS syntax and HTML-ID checks passed.
- Expanded ARM64 integration now checks all-rule visibility, escaped values, invalid-batch atomicity, clean snapshot/shutdown and cold physical database migration. The ARM64 job in workflow 34770980656 passed these checks, including the actual full seed import and cold database restore.
- Final workflow **34771227274** passed all gates and published the APK from **bf9c8d718f177c08af6c0bd1036c9e4d249a85c8**. This includes detection of map edits/imports after Apply: revert first, preserving intervening files. No new device acceptance claimed.
- Browser tests ran successfully in CI with Playwright 1.55.0. They cover 1,105 fixture rules, collapsed/lazy categories, tiny/negative values, bounds errors, changed-only saves, controller binding save and capture release, and mobile horizontal overflow. UI screenshots are in the workflow artifact `management-ui-reports`; downloading its temporary file URL locally returned HTTP 403, so do not claim manual screenshot inspection.
- Session archive excludes incoming/exports/run; includes rootfs, database, binaries, maps, logs, server data, source, builds, backups, configuration and client. Native restore works without Python and stages/validates before swapping. Previous session stays in work-session-previous/rootfs-session-previous.
- Physical Android acceptance still pending: in-place update, rule editing, Nektulos apply/revert and complete session migration. Client execution remains unimplemented by design; controller input is a diagnostic/future injection boundary.

## Previous release: 0.2.0

Published **0.2.0**, version code **4**, on 2026-09-13.

- Code commit / preview tag: `bf9c8d718f177c08af6c0bd1036c9e4d249a85c8`. This handoff-only update follows it; no APK code changes accompany these notes.
- Final successful workflow: https://github.com/Russianranger/trasc-server-android/actions/runs/34771227274
- APK: https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk
- APK size: **221,721 bytes**. GitHub release asset SHA-256: `1627425c11235269cbf629fc1107ddc4d349afe2e2ccb8a1c21480c93d351a98`.
- Pinned certificate: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; APK verification passed in CI before publication.
- `python3 -m unittest discover -s tests -v`: **29 passed**.
- `bash scripts/check-management.sh`: passed JVM archive/input checks.
- `node tests/ui_management.cjs`: passed browser management-flow checks in CI.
- ARM64 database job: reproduced original hostname failure, imported the full pinned seed offline, then passed rule inheritance/editor validation, SQL/backup/restore and cold physical database migration.
- `gradle --no-daemon :app:assembleDebug :app:lintDebug`: passed; stable-signature verification and preview publication passed.
- Preview tag and final APK release asset were read back from GitHub to verify the published commit and checksum.

## Current device follow-up

The 0.2.1 backup/restore and input pass is confirmed by the user. Continue with the 0.3.0 client sequence at the top of this file and in `docs/client-runtime.md`. Retain `docs/device-tests.md` for server regressions if a later support bundle indicates one. Do not claim actual ROF2 device acceptance until the user reports results.
