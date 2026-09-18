# 0.4.21 Thor result: DLL build repaired, faster sample, camera-dependent particles

**Follow-up completed:** the user confirms a third-person view **without casting** restores subsequent first-person Minor Healing particles. See [the view-only result and source review](particles-0421-view.md). The device test below is historical and should not be requested again.

Input: `logs-7280042745619990780.zip`, exported September 18, 2026 at 18:13:39 UTC, and the user's accompanying Minor Healing observations. This review changes documentation only. Keep the published 0.4.21 APK and current DLL; another compile, deployment or runtime install is unnecessary for the next test.

## DLL compilation is confirmed on the device

The build and deployment records agree on the newly compiled DLL: 1,710,592 bytes, SHA256 `1be0374b5c8d323057ba6c665203309645f8a0d71c27780158e3677da53ef96e`. The build includes `TRASC_EQ_CAMERA_MOUSE_V2`, `TRASC_EQ_LOAD_V2` and `TRASC_EQ_DISPLAY_V1`. Its `eq_display_loading.h` hash is `8e4c5279c7b778fe3f7033ae643fd38b8e0b57aab264efed58853c9c76fdc7a3`. All three fresh client sessions record the display adapter active. This confirms that [the omitted-header repair](dll-header-0421.md) works through the actual Android-to-compiler deployment path.

## Loading comparison

Faster spell loading remains enabled in all three sessions. The mode below is **Reduce model-loading pauses (experimental)**. Times run from the first `Server selected` to `Initializing character select UI` in each fresh process; they are engine landmarks, not physical-button-to-visible-frame measurements.

| Model pauses | Log suffix | Server selected | Loading screen | Character UI | Before screen | After screen | Total |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| Off | `.previous.2` | 17:56:47 | 17:57:05 | 17:57:19 | 18s | 14s | 32s |
| On | `.previous` | 17:59:28 | 17:59:45 | 17:59:57 | 17s | 12s | 29s |
| On, Sound diagnostics enabled | current | 18:05:15 | 18:05:33 | 18:05:45 | 18s | 12s | 30s |

Sources: the corresponding `logs/client-game*.log`, current `client/current/Logs/dbg.txt`, and `logs/client-loading*.log`. The last session has different logging overhead and should not be treated as an equivalent repeated benchmark.

| Measured stage | Off | On | On with diagnostics |
| --- | ---: | ---: | ---: |
| Whole spell loader | 2.788s | 2.085s | 2.786s |
| Initial UI scope | 5.328s | 5.893s | 5.976s |
| XML composite, within UI/XML read | 3.185s | 2.895s | 2.977s |
| UI data, within UI | 1.831s | 2.596s | 2.596s |
| Global-model scope | 12.214s | 10.189s | 9.801s |
| Model-loading calls, within global scope | 6.047s | 5.885s | 5.850s |
| Model waits, within global scope | 95.077ms | 0.554ms | 0.523ms |

The paired total improves by **3 seconds**, consistent with the user's impression. The wait adapter performs 89 yields instead of the 89 requested one-millisecond sleeps, with no reported call failures. The directly measured wait saving is only **94.523ms**. Do not credit the entire three-second total or two-second global-scope difference to this change: cache/order/run variation and any downstream scheduling effects have not been isolated. These are single samples, not averages. The UI scope actually grows in the paired sample.

All three runs construct the same 40,914 spell records, process 8,960,166 fast integer fields and 40,916 fast checksums over 79,627,413 bytes, with zero fallbacks. The installed root/Resources spell files retain SHA256 `034b5635049a9ef6e549f3f7d5b32f265a386d82a3fd3e8286b04d44b58a5e77`. Preserve the working checksum optimization.

The remaining larger performance targets are UI/XML and global model work. Nested/inclusive timings must not be added twice. XML composite takes approximately three seconds, UI data up to 2.6 seconds, and model-loading calls about 5.9 seconds. Several seconds of the outer global scope are not attributed by these calls; further source-backed profiling should identify them before choosing a patch. The remaining half-millisecond of yielded waits is not a useful next target.

## Minor Healing and camera state

The user reports three first-person casts without particles, successful particles after going to third person, and the same initial failure after logging out/back in. After third-person casting, first-person casts work. This is repeatable visual evidence of camera-dependent behavior. It suggests per-character model/effect setup or visibility/culling, but the logs do not identify which mechanism is responsible. The current camera log measures mouse-look recentering, not viewpoint changes or emitter state.

The earlier enabled session records three `zapmuze.dds` texture-load failures at 18:01:52–18:01:54. The latest diagnostic session has **no recorded texture-load failure**. The asset report finds `SpellEffects/zapmuze.dds`, 87,536 bytes, with a readable 256×256 DXT3 DDS header and nine mipmaps. File/header presence does not prove successful GPU loading.

More specifically, [the previously inspected effect definitions](client-assets-047.md) map `zapmuze.dds` to Skin like Wood's animation 216. Minor Healing's animation 278 uses `fire_missle.dds`, `zapmuzc.dds` and `blueglobesp501.dds`. The current diagnostics do not inspect those three texture payloads. Current spell animation IDs and EFF/EDD sizes match the prior evidence, but the installed EFF/EDD files were not rehashed. Do not attribute Minor Healing's symptom to the earlier `zapmuze.dds` warning or declare all effect assets valid/missing.

The off-mode session stops at character select without entering the world, so this bundle does not provide a particles-off/on comparison for the loading option. It establishes neither a particle regression from that option nor a rendering fix. Keep particle/filter/near-clip settings unchanged pending a discriminating test.

## Next device test

Keep the current build and working settings fixed, including Faster spell loading and the enabled model-pause option. Turn **Sound diagnostics off**: the last session generated 61,625,181 cumulative Wine log bytes and seven rotations; repeating that audio trace does not record camera/emitter state.

1. Log back into the same character, remain in first person and cast Minor Healing to confirm the initial absence.
2. Let that cast/effect finish. Switch to third person for a few seconds **without casting**, then return to first person.
3. Cast Minor Healing in first person and report whether particles now appear.
4. If they still do not, cast once in third person, let it finish, return to first person and cast again.

The useful distinction is whether merely displaying the character in third person restores subsequent first-person particles, or whether creating an effect while in third person is required. This guides the next code inspection; it does not by itself prove a particular engine function is faulty. A forced camera switch or speculative texture/setting replacement is premature.

Both enabled sessions enter the world; the diagnostic session also returns to character select and re-enters. Retained Wine logs contain no recorded stack overflow or unhandled exception. The existing camp/disconnect messages remain and are outside this investigation. Preserve the confirmed controller/source-DLL reconnect fixes and shared-memory capture. No new APK, gameplay fix or subagents are part of this evidence update.
