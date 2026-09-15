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
