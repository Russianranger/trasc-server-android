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
