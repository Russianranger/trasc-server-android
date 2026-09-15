# 0.4.0 Thor Turnip acceptance (2026-09-15)

User reports a substantial improvement, with the second run feeling slower. Evidence: `logs-4814310534970933887.zip` and a 10.62-second 1920×1080 video of the first run. Both use DXVK 2.5.3, real Turnip Adreno 740 (driver 18, Qualcomm 20803, software=false), three verified preflight presents, native D3DX30/35 and native/system DirectInput. Both game logs say `Quitting normally`. No fatal Vulkan/device-lost error or model initialization failure was found.

| Measurement | First run | Second run |
| --- | ---: | ---: |
| Prefix preparation | 45.334 s (update) | 5.426 s (reuse) |
| Until launch requested | 47.135 s | 6.730 s |
| Global data initialization | 18 s | 15 s |
| Game UI initialization | 13 s | 10 s |
| Display updates/s, selected world window median | 30.18 | 30.27 |
| Decode/apply ms/update, same window median | 0.86 | 1.08 |
| Receive ms/update, same window median | 3.13 | 6.56 |

Selected windows are 19:12:40–19:13:30 and 19:16:40–19:17:30 UTC, ten five-second samples each. Routes/frames are not controlled. Receive time includes waiting/transport and is not isolated CPU processing. First-run video at ~1 s shows DXVK 54.9 FPS with Android display ~30.2 updates/s. The configured Xtigervnc FrameRate is 30, so the display rates cannot rule out different game rendering rates above that cap. DXVK HUD FPS is not retained as a timestamped series in these logs.

First-window sampled game main-thread masks are 0–7; second-window masks vary (0–4,6–7; 0–5; 0–6). Main-thread CPU utilization medians are about 79% and 61% of one core, respectively. The game is no longer restricted to CPU 0. Android's available masks vary; this does not prove thermal throttling or a scheduling bug. No device thermal/power-status samples are present. 0.4.1 adds those readings to the existing five-second display log without changing power or affinity policy.

Both runs retain nonfatal unknown-world-message/GlobalLoad_chr warnings and DXVK gamma-ramp/unhandled-state warnings, and both progress to world entry and normal quit. MIDI synthesizer output is unavailable. These do not establish the cause of the subjective second-run slowdown. Keep future diagnosis separate from fullscreen/resolution acceptance. 1280×720 has 1.92 times the pixels of 800×600; compare at the same resolution before attributing a frame-rate change to fullscreen.

---

# Turnip/DXVK release: 0.4.0 (2026-09-15)

The 0.3.10 device comparison (`logs-5171237087911039269.zip`) does not support a benefit from the OpenGL worker. Selected world movement windows show Single median Wine/display 6.46/6.77 per second and worker 6.10/6.47; routes and timings differ, so these are observations rather than a controlled regression measurement. Both prefixes reuse in about 5.43 seconds. Both retained game logs show similar global-asset times (40/38 seconds) and zone-UI times (51/52 seconds).

Thread observations now establish that the main game thread changes from a multi-core mask to CPU 0 only, as do its graphics worker threads. The main thread consumes about 79%/75% of one CPU in the selected Single/worker windows. This is a concrete restriction, not proof that a specific INI field or DLL caused it. The new available-core option restores only this launch's game threads to the supervisor's current allowed mask, after rechecking owner, launch marker and thread lifetime. Android still enforces its CPU policy. No INI or server changes; choosing Game preserves previous behavior on the next launch.

The new graphics path is **ROF2 D3D9 → DXVK 2.5.3 → native ARM64 Turnip 24.3.4/KGSL → X11 CPU-copy presentation → existing in-app RFB display**. Turnip and the device/presentation probe are built from pinned sources for Debian Bookworm's glibc and bundled in the APK, alongside upstream's checksum-pinned x86 DXVK D3D9 module. The existing runtime's Vulkan loader and Box64 bridge are retained. This replaces WineD3D/VirGL rendering but still copies completed frames; a native presentation integration remains a later milestone.

Upstream [Mesa 24.3.4 device definitions](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-24.3.4/src/freedreno/common/freedreno_devices.py) include the A740 KGSL chip ID. Its [WSI initialization](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-24.3.4/src/vulkan/wsi/wsi_common.c) supports explicit CPU-image presentation using `MESA_VK_WSI_DEBUG=sw`; this flag selects how frames reach X11, not a software rendering driver. The exact sources were inspected from the official release archive. [DXVK's versioned instructions](https://github.com/doitsujin/dxvk/blob/v2.5.3/README.md) specify x86 d3d9.dll in the WoW64 directory with a native override. Imported d3d9.dll files that would shadow the bundle are rejected without modification. Native dinput8 and D3DX helpers remain active. Selecting VirGL/Software forces built-in D3D9, without registry changes or prefix repair.

Production preflight requires Vulkan 1.3, Mesa Turnip driver ID 18, Qualcomm vendor 0x5143, a non-CPU device and three successful swapchain presentations. Failing hardware/device access is reported; it never silently calls Lavapipe accelerated. The DXVK HUD shows device/FPS/compiler activity. Logs retain device evidence, DXVK load evidence, previous Vulkan/DXVK output, native thread masks and both game startup logs. Shader caches live in the backed-up private prefix.

Published **0.4.0/code17** from `25d541a0baf36d82c0797126c0e536a775c37f4a`; all six jobs passed in [run 35005200443](https://github.com/Russianranger/trasc-server-android/actions/runs/35005200443). Released APK and corresponding sources match the tested candidates and asset digests. Checks include 59 backend tests, browser/JVM flows, Android compile/lint/signing, database/runtime backup and restore, and real ARM64 direct/PRoot rendering, animated models and input. The new Vulkan checks verify actual DXVK loading, three swapchain presents, artwork/shader pixels and recovery to WineD3D using the same prefix. A separate negative control loads Turnip in the unchanged runtime and verifies that missing KGSL access is rejected.

CI uses an explicitly separate Lavapipe runtime for Vulkan/Wine/Box64 integration tests; it cannot test the Thor's Adreno or establish a hardware speedup. One earlier candidate failed an expected diagnostic-string assertion on the GPU-less host; preflight now reports actual KGSL access errors. A later candidate repeated the older PRoot compatibility fixture SIGKILL after passing pixel checks. Focused teardown/process diagnostics were added, exit-zero assertions retained, and the final run passed all fixtures. The prior termination's cause remains unproven. Full release hashes and CI history are in [HANDOFF.md](HANDOFF.md).

Device test: update in place and select Turnip + DXVK, 800×600, Balanced CPU, Automatic runtime, Allow available cores, native helpers on, shadows/verbose logging off. Check menus/models/movement and the DXVK HUD, then repeat the launch and export logs. On failure, preserve logs before further launches and return to VirGL. No runtime download or reimport is required. This first Turnip path retains frame copies; improved game FPS is still a device-test question.

---

# New evidence and change: 0.3.10 (2026-09-15)

Bundle `logs-5272698694105119380.zip` contains the user's Multithreaded-first / Single-thread-second 0.3.9 comparison. Actual Wine settings confirm `csmt=1` then `csmt=0`; native/system DirectInput, native D3DX30/35, patched graphics, Adreno 740 and PRoot acceleration remain active. The second client quits normally and is explicitly stopped. Startup Wine address-map retries and isolated graphics/audio/RpcSs warnings remain, without evidence of a new fatal client failure or log flood.

| Measurement in movement windows | Multithreaded | Single thread |
| --- | ---: | ---: |
| Window, UTC | 15:20:07–15:21:17 | 15:27:30–15:29:10 |
| Five-second samples | 15 | 21 |
| Wine presents/s, median | 5.99 | 7.73 |
| New bitmap draws/s, median | 6.17 | 8.78 |
| Decode/apply ms per update, median | 1.50 | 1.21 |
| Receive/assembly ms per update, median | 12.70 | 25.70 |
| Canvas CPU submission ms per draw, median | 0.086 | 0.068 |

Windows select the sustained large-pixel-update portions rather than loading/menus/camping. Different movement/camera paths, sampling intervals and session order prevent interpreting this as a controlled speedup. Display tracks the low Wine rate; decoding alone is too short to explain it. Receive/assembly includes socket waits and is not pure bandwidth or GPU time. This narrows the next work upstream of bitmap decoding, but does not establish CPU versus GPU dominance or rule out presentation/readback overhead within Wine Present.

The first run's prefix took 33.211 seconds because the rebuilt Wine module required a refresh; the second reused the prefix in 6.648 seconds (8.295 until launch requested). The only retained ROF2 `dbg.txt` belongs to Single thread: global assets **39 seconds**, zone UI **53 seconds**, main loop 15:27:14 UTC, camp complete 15:29:54 and normal quit 15:30:14. The multithreaded game's startup log was overwritten, so do not claim an exact per-mode asset/UI comparison or attribute the perceived longer loading to threading. The new snapshot preserves this evidence before the next launch without altering imported client files.

## Implemented in 0.3.10

A third existing-selector choice, `opengl_worker`, combines Wine `WINE_D3D_CONFIG=csmt=0` with Mesa `mesa_glthread=true`. Both old choices explicitly disable this Mesa experiment, and Single thread remains a direct recovery comparison. Wine logging, shader/native model fixes, `eqgame.exe patchme`, DLL overrides, display protocol, runtime images and CPU memory-ordering settings are unchanged. No CPU placement or priority changes.

Upstream Mesa 22.3.6 [GL command batching](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-22.3.6/src/mesa/main/glthread.c) queues GL calls for a worker to overlap application and driver CPU work. The [DRI context setup](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-22.3.6/src/gallium/frontends/dri/dri_context.c) honors the `mesa_glthread` option only with a safe loader, and the [software DRI front end](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-22.3.6/src/gallium/frontends/dri/drisw.c) synchronizes this worker before shared pipe-context access. These exact sources were inspected from the official archive. Mesa's queue names the worker `<process>:gl0`; the supervisor samples threads carrying this launch’s inherited marker to distinguish observed work from a requested option. An observed worker in another Wine descendant is not proof of the game's CPU/GPU bottleneck. Missing/denied proc access is reported as incomplete rather than failed rendering.

`client-threads.log` retains bounded, ten-second CPU-tick/last-CPU/mask observations for processes carrying the launch marker only, with collection duration. `client-state.json` carries the latest observation and requested/observed worker flags. No command lines, environments or unrelated processes are collected. The process-tree limits and racing exits are tested. Previous game startup evidence is copied with bounded head/tail excerpts and no symlinks/INI/chat files. Existing native log export and session backup include these app log files.

Published **0.3.10 / code 16** from `9974560e8562119f1d036745f964b770b1f14a61`; [run 34991355081, attempt 2](https://github.com/Russianranger/trasc-server-android/actions/runs/34991355081/attempts/2) passed all release gates. Checks cover 54 backend tests, JVM/browser management flows, APK build/lint/signing, database/runtime roundtrips and real ARM64 direct/PRoot Software/VirGL worker observation, all three threading modes, artwork/shaders, animated native models and input. Published APK/source hashes match the tested candidates; full provenance is in `HANDOFF.md`. First candidate 1ad450e failed worker discovery because Wine detached from its launcher; the corrected exact per-launch marker finds those processes without logging environment content. The corrected commit's first attempt later returned SIGKILL (-9) after the Compatibility CPU texture fixture printed correct pixels and PASS; one unchanged retry passed every assertion. Cause remains unproven, with no matching fatal failure in the latest device logs. Preserve this caveat and investigate process exits if it recurs. Actual Thor speedup is not assumed. Compare Single thread with Single + OpenGL worker at the same settings and route, with warm-prefix timing kept separate.

---

# New evidence and change: 0.3.9 (2026-09-15)

Bundle `logs-7195588022919037426.zip`, screenshot and 10.68-second screen recording confirm 0.3.8 loads faster but world movement remains uneven with shadows disabled. Actual Adreno 740, native/system DirectInput and D3DX30/35, patched Wine shaders and PRoot acceleration remain verified. The client camps and quits normally; no repeat of the earlier CI SIGKILL was observed in these device logs.

| Device stage | Prior 0.3.7 | Latest 0.3.8 |
| --- | ---: | ---: |
| Repeat Wine prefix | 15.697 s | 6.642 s |
| Repeat total to launch request | 18.138 s | 8.175 s |
| Global assets | 102 s | 46 s (13:10:49–13:11:35 UTC) |
| In-zone UI | 48 s | 35 s (13:12:20–13:12:55 UTC) |

These are different sessions, not controlled FPS benchmarks. The recording's encoded frame rate and the VNC session's 3,432 updates include duplicated/partial frames and idle periods; neither is game FPS. Approximate free physical memory at world initialization is 8.9 GB, so this log does not establish memory exhaustion. Remaining one-off invalid-size/framebuffer and insufficient-uniform messages merit follow-up, but there is no repeating graphics/log flood explaining the full slowdown.

The decoder allocated a new int array per raw rectangle (1.83 MiB for a full 800×600 update) plus row buffers and CopyRect arrays. It now reuses bounded storage and decodes in up-to-64-KiB blocks. This removes avoidable allocation pressure; current evidence does not establish that decoding is the dominant cost. No pixel-format, display protocol or shader-capability change.

Wine 10 already provides [aggregate presentation counters in cs.c](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/wined3d/cs.c) and [WINE_D3D_CONFIG=csmt=0/1 in wined3d_main.c](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/wined3d/wined3d_main.c). The release uses these existing mechanisms: explicit default multi threading, optional single threading, no registry edits. Aggregate `trace+fps` is enabled alongside quiet default errors/DLL evidence; per-frame and D3D tracing stay off. The first sample for each process/swapchain is excluded, values carry timestamps and actual mode comes from Wine's own initialization message.

Android records RFB updates, new bitmap draw submissions (coalescing repeated invalidations), transfer/decode and Canvas submission durations every five seconds in `client-presentation.log`. It retains a previous session and bounded overflow segment. `client-state.json` records the latest `wine_present` and `graphics_threading_observed`. Low Wine and Display rates suggest upstream game/translation/render/presentation work; much higher Wine rate than new bitmap draws while moving points toward delivery/readback/display work. Neither observation alone separates CPU from GPU execution, and Canvas CPU submission time is not GPU completion time. The next test compares both threading modes in the same scene before choosing a new backend.

Published **0.3.9 / code 15** from `d41468a32f2330becc3052d10c1e38079e117e01`; all five jobs passed on the first attempt in [run 34975546828](https://github.com/Russianranger/trasc-server-android/actions/runs/34975546828). Checks cover 51 backend tests, JVM buffer reuse/counter semantics and existing management checks, browser flows, Android build/lint/signing, database and runtime archive roundtrips. Direct ARM64 and accelerated PRoot, each with Software and VirGL, passed real Wine aggregate counter/configuration and texture/shader checks in both threading modes, plus native animated models in single mode. Existing input and shader negative controls passed. The aggregate counter fixture deliberately sleeps between presents and is not a performance benchmark.

Published APK/source downloads match the tested candidates and GitHub digests; APK SHA256 `9adf3df5c29781cd503ee98884c08c30a5f890f2c4f6dd2c1ee76526cb863dfb`. Same signing identity, application ID and runtime images. See `HANDOFF.md` for full provenance. Device comparison remains necessary to measure any FPS improvement. Retain VirGL/Software, CPU and runtime Compatibility, native helpers, patchme and all server data. Turnip/DXVK remains the separate architecture milestone below.

---

# New evidence and change: 0.3.8 (2026-09-15)

Bundle `logs-2383206107737699672.zip` confirms the 0.3.7 repeat launch reused its Wine prefix: initial prefix update 102.731 seconds, repeat 15.697 seconds, total until launch requested 18.138 seconds. Global assets took 102 seconds (previous 121); in-zone UI initialization 48 seconds (previous 63). These stage reductions do not establish playable FPS. The user still reports unacceptable performance.

Both `C:` (Wine prefix) and `D:` (imported client) are subdirectories of Android `Context.getFilesDir()`. `D:` maps `/client` to `files/work/client/current`, not `/sdcard`, `/storage/emulated` or a SAF stream. The ZIP's selected document is used only during import. Android documents [shared-storage FUSE overhead](https://source.android.com/docs/core/storage/scoped); the existing internal-storage layout avoids that layer. Merely changing the Wine drive letter would keep the same underlying files and PRoot overhead.

The launcher was explicitly setting `PROOT_NO_SECCOMP=1`, forcing PRoot to stop on all syscalls. The pinned upstream [PRoot event loop](https://github.com/termux/proot/blob/7266fb3e8516535682f5a9c8f3a7e70f6506eddb/src/tracee/event.c) and [filter implementation](https://github.com/termux/proot/blob/7266fb3e8516535682f5a9c8f3a7e70f6506eddb/src/syscall/seccomp.c) provide an optional accelerator which traces calls needed for path/ABI handling while allowing other calls to proceed without tracer round trips. This enables an additional filter; it does not remove Android's security policy. Setting the variable to `0` still disables the feature because upstream checks its presence.

0.3.8 adds Automatic/Compatibility runtime modes. Automatic tests the same installed runtime and bindings using a small temporary-file read/seek/stat, socket and child-process workload before Wine touches the prefix. Only a successful exit plus an actual PRoot acceleration event enables accelerated launching. Unsupported/failed checks fall back; a hung or unkillable preflight aborts rather than starting another runtime alongside it. Compatibility retains the old mode. The server is unchanged. A tiny native patch emits one opt-in acceleration observation, without verbose syscall tracing; it is included in corresponding launcher sources.

New logs: `client-runtime-probe.log`, `client-proot.log` (and `.previous.log`), plus storage and accelerator fields in `client-state.json`. Native helper activation is checked independently of the selected option. No client files are moved or rewritten by the preflight. The latest inherited CPU mask is 0–5; this does not establish which cores the later Wine/game threads can use. No affinity or Android scheduling controls were changed.

Published as 0.3.8 from `45311704d0f03f6004d7abe0f9866831b3a7d9f5`; [CI attempt 2](https://github.com/Russianranger/trasc-server-android/actions/runs/34915871917/attempts/2) passed all release gates, including actual native acceleration events in both PRoot renderers. Same underlying runtime images and signing certificate; APK update only.

| PRoot test, successful 0.3.8 run | Full-update prefix | Repeat prefix | Repeat total until launch request |
| --- | ---: | ---: | ---: |
| Software | 28.054 s | 3.007 s | 3.640 s |
| VirGL GLES | 27.252 s | 3.006 s | 3.840 s |

Previous 0.3.7 PRoot/VirGL values were 89.356 / 6.415 / 7.974 seconds. These are separate CI observations, not a controlled device benchmark; host graphics uses llvmpipe GLES, not the Thor's Adreno. Actual game performance remains pending.

The first CI attempt had one SIGKILL (`-9`) in the intentionally native-only DirectInput negative control after successful rendering/input. An unchanged retry passed that exact assertion (23), the corrected control (0), models, shaders and all remaining gates. Cause is not established; no assertion was weakened. Preserve this diagnostic if termination recurs (details in HANDOFF).

Device comparison: keep VirGL/800×600/Balanced constant, use Automatic runtime, launch twice to account for the one-time prefix update, then compare Runtime Compatibility if needed. Export logs with actual acceleration evidence. Turnip remains a separate graphics milestone below.

---

# Client performance and Turnip

## Device evidence: 0.3.6

Bundle: `logs-810542259983773733.zip`, last launch 2026-09-14 23:39:24 UTC.

- Host: Qualcomm Adreno 740, OpenGL ES 3.2. Guest: VirGL OpenGL 2.1 / Mesa 22.3.6. All eight compressed-texture startup checks pass. WineD3D patch `legacy-specular-fog-v1` is verified, as are native DINPUT8/system forwarding and native D3DX30/35. User confirms correct graphics.
- Display starts 23:39:25; EverQuest's first log entry is 23:41:18 (113 seconds later). Old logs do not separate Wine update, loader and graphics-probe durations, so the entire delay must not be attributed to one stage.
- Global asset initialization: 23:46:08–23:48:09 (121 seconds). In-zone UI initialization: 23:49:53–23:50:56 (63 seconds), including 41 seconds after “Loading Icons.” Full initialization completes 23:51:15. Time before these stages includes user interaction and is not a loading benchmark.
- Wine output is only 31,975 bytes, not the earlier multi-gigabyte debug flood. Residual invalid-size/framebuffer and insufficient-uniform messages exist, but not the previous repeating texture corruption or undeclared specular shader error.
- Box64 records BIGBLOCK=0, SAFEFLAGS=2, STRONGMEM=1 and a bundled Wine override exposing 64 CPUs on the eight-core device. Its Cortex-A510 banner alone does not prove threads are pinned to little cores.
- VNC framebuffer updates are not game FPS. Neither these logs nor CI establish the dominant in-game bottleneck. PRoot syscall interception, CPU translation, WineD3D/VirGL command traffic and GPU readback/display copies remain possible costs.

## Implemented in 0.3.7

Balanced uses Box64 BIGBLOCK=2 / SAFEFLAGS=1, keeps STRONGMEM=1, and uses a private app-specific rcfile to remove the stock 64-core Wine override while retaining the explorer small-block workaround. Compatibility retains the previous configuration. No unsafe floating-point or dirty/self-modifying-code optimizations were enabled. Settings follow the [pinned Box64 documentation](https://github.com/ptitSeb/box64/blob/2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a/docs/USAGE.md) and [stock rcfile](https://github.com/ptitSeb/box64/blob/2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a/system/box64.box64rc).

A successful Wine prefix gets a content-based runtime/graphics signature. Repeat starts use `wineboot -i` instead of forcing `-u` on every launch. Wine still boots services and checks its own update timestamp. The marker is invalidated before setup and committed only after valid PE32 system files and a real 32-bit cmd launch succeed; runtime changes and interrupted checks take the full update path. This follows [Wine 10 wineboot's init/update behavior](https://gitlab.winehq.org/wine/wine/-/blob/wine-10.0/programs/wineboot/wineboot.c). The first post-update launch still initializes the marker.

State now records startup-stage durations and CPU settings/affinity. ROF2 launch options persist under `client/launch-options.json`, already covered by complete session backups. Existing graphics, server, input and model-helper behavior is retained.

## Validation measurements

Run [34911899931](https://github.com/Russianranger/trasc-server-android/actions/runs/34911899931) exercises a real second supervisor launch against the same prefix, verifies a working PE32 loader, and checks that kernel32.dll was not rewritten.

| ARM64 test environment | Full-update Wine prefix setup | Repeat prefix setup | Repeat total until launch request |
| --- | ---: | ---: | ---: |
| Direct runtime, Software | 13.212 s | 1.402 s | 1.817 s |
| Installed runtime through PRoot, Software | 86.748 s | 6.415 s | 7.774 s |
| Direct runtime, VirGL GLES | 13.016 s | 1.402 s | 2.017 s |
| Installed runtime through PRoot, VirGL GLES | 89.356 s | 6.415 s | 7.974 s |

The VirGL host is CI Mesa llvmpipe GLES, not Adreno. These are single CI observations from our test client, not Android ROF2 benchmarks or game FPS. They establish that repeat launches avoid the expensive forced-update path. Device acceptance still needs same-zone/resolution comparisons and a second launch.

## Turnip assessment and next implementation milestone

Turnip is Mesa's Vulkan driver for supported Adreno devices; see [Mesa's Freedreno/Turnip documentation](https://docs.mesa3d.org/drivers/freedreno.html). [DXVK](https://github.com/doitsujin/dxvk) translates Direct3D 9 to Vulkan. Winlator uses these components alongside Wine/Box64, as its [official project](https://github.com/brunodev85/winlator) documents. A direct DXVK → Turnip path is a credible candidate for this Adreno device, but better performance in this app is an inference to test, not a guarantee.

The inspected [Winlator display setup](https://github.com/brunodev85/winlator-app/blob/a030f552f452158a2db64fdb32b490fa19c0b48d/app/src/main/java/com/winlator/XServerDisplayActivity.java) installs the Vulkan ICD separately from its OpenGL/DXVK components. Its [guest launcher](https://github.com/brunodev85/winlator-app/blob/a030f552f452158a2db64fdb32b490fa19c0b48d/app/src/main/java/com/winlator/xenvironment/components/GuestProgramLauncherComponent.java) and in-app X server use a different runtime/presentation arrangement. This is why a driver-only swap is insufficient here.

The current app exposes GL through a native Android GLES VirGL server and presents through TigerVNC/RFB. That server is built without Venus/Vulkan. Replacing a GLES library with a Turnip driver ZIP would not create a Vulkan device for Wine. Installing DXVK alone would likewise not provide the required driver or presentation transport.

The next implementation needs:

1. A pinned ARM64 glibc-compatible Turnip build with Qualcomm KGSL support (or an explicit native Vulkan bridge), matching Vulkan loader and Box64 wrapping. Validate device access and enumerate the actual Adreno device from inside the app; do not silently accept Lavapipe as acceleration.
2. Vulkan presentation compatible with the app's display path. Prove surface creation/presentation on the real device; assess a native X11/presentation integration to avoid the current readback/copy bottleneck. Driver import alone does not solve this.
3. A pinned x86 D3D9 DXVK module whose requirements match that driver, isolated prefix/override selection and shader cache, retaining `eqgame.exe patchme`, native/system dinput8 and native D3DX helpers. Select this only as an additional experimental graphics option; retain VirGL/Software recovery.
4. Own-source Vulkan/D3D9 tests covering textures, shader pixels, models, animation, input, process lifetime and backup/restore; then Thor comparisons using the same character, zone and resolution. Publish driver/module sources and licenses with the binaries.

0.3.7 does not ship Turnip, DXVK or a fake selector for an unimplemented path. It provides a bounded performance test while preserving the first visually correct GPU backend.
