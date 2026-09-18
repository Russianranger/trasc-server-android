# 0.4.22 — Optional first-person particle repair

September 18, 2026. Implementation follows the [verified graphics mechanism](particles-graphics-0421.md). Version 0.4.22/code39 adds **First-person spell particles** with Original behavior (default), Diagnostics only, and Repair + diagnostics (experimental). The live Thor startup sequence and visible result still require the comparison below.

## What changes

The add-on wraps the exact client's first-person camera update, vtable VA `0x9D0F88`, original function VA `0x797160`. The call at `0x796E0C` passes the player as one stack argument and the camera in ECX; the original returns with `ret 4`. The wrapper calls the original first on its existing thread. It checks the current local actor afterward, including actors created or replaced during that update. It preserves the original call's LastError.

Only in-world first person, with a matching local player/camera, a verified root hierarchical actor, the body hidden and particle permission false, repair mode invokes the original graphics method `ShowParticlesWhenInvisible(true)` and confirms through its getter. It does not change the view, recreate actors or modify body visibility. Original view leave and particle disabled-state checks remain in place. An actor with a parent is skipped.

The launcher requires the complete SHA256 of both supplied binaries and the new add-on marker `TRASC_EQ_PARTICLES_V1`. Native installation also checks PE identities, original update bytes/slot, the graphics setter/getter bytes, vtable methods and visibility mask. It only loads under Wine. The graphics module must be beside the executable and is pinned for callback lifetime. Unsupported pointers/layouts, read-only actor memory, other players/views, non-owner update threads and reentry are skipped. Repaired actors receive at most one attempt per observed player/actor or camera-entry episode, with a process cap of 128 attempts.

Diagnostics only runs the same observation without setting permission. Original behavior does not install this adapter. Options take effect on the next client launch. Existing loading and camera adapters retain their code and independent settings. Native dinput8 remains required. The new header is included in both build-source overlay and Android runtime deployment; a regression checks every required header against the deployment list.

`client-particles.log` records installation and actor/status transitions, hidden state, permission before/after, actor/player identity, thread and attempt count. Records are limited to 512 transitions plus installation, with the existing 256 KiB file cap; normal launch rotation and Export Logs include it. Launcher status reports the requested mode, not a claim that the native hook ran. `install=ready` and native samples establish that separately.

## Verification

Before CI: 138 Python tests, native/JVM management checks, JavaScript syntax, x86 C++ fixture compilation, and all 11 original-code two-binary reproduction checks pass. The hook/update/setter/getter instruction signatures match the supplied files. Local browser installation could not reach its CDN; the required CI browser gate subsequently passed, and its portrait/landscape screenshots were reviewed.

The new x86 fixture invokes the real adapter through its patched virtual slot with an original callback of the same ABI and the verified setter/getter instructions. It checks original-first ordering, late/replaced actors, profile/off/repair behavior, hidden-body preservation, scopes, thread exclusion, unreadable/read-only memory, byte/layout rejection, LastError preservation, retry and log bounds. It is included in both the Microsoft v142 Windows gate and the ARM64 Wine/Box64 runtime gate. The complete existing graphics/audio/input/model/restart, database, Android lint/signing and release gates remain required. Both the Microsoft v142 fixture/production add-on build and the ARM64 Wine/Box64 particle fixture passed. The latter artifact contains the fixture PASS line and native profile/repair/skip/attempt-limit transitions. All seven release jobs completed successfully, including the complete direct/PRoot Software/DXVK/VirGL graphics, audio, model, input, restart, database, session, Android lint/signing and publication gates. No failed gate was waived.

These are controlled code/ABI tests, not a rendered game or proof of the device's startup ordering. If the first failing cast already has permission enabled, this hypothesis does not explain that failure; inspect emitter ownership/state next instead of broadening the visibility override.

## Published release verification

Implementation commit: `dde9476e9a82950bf497a0082fbb94579cdb2db6`; [release workflow 35385991190](https://github.com/Russianranger/trasc-server-android/actions/runs/35385991190).

The downloaded candidate passes independent APK v2 RSA/SHA256 signature and content verification. The binary manifest is 0.4.22/code39 with package `io.github.russianranger.trasc.preview`. All 26 backend Python/header assets and the UI assets match this source; the compiled Java includes the new header deployment and option literals. All 33 corresponding native source/recipe files match. The workflow artifact ZIP matches GitHub's recorded SHA256.

| Published asset | Bytes | SHA256 |
| --- | --- | --- |
| APK | 10,537,055 | `5b7ec5d94dbe5afb2678b8dab6a42987df2f7a6b4805a5e3e1d61b31fb794cdc` |
| Corresponding native source archive | 114,558,421 | `29fe73561a1f48e3210cdb6fb6b6ed935e4194ea7544d8d8203a4eee2442e1f0` |

Signing certificate SHA256 remains `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`. Evidence and independent verifiers are under ignored `runtime-work/0422`; no private client binaries or Microsoft SDK files were committed. The public preview tag resolves to the implementation commit and the published APK/native-source asset sizes and SHA256 digests match the verified downloads. The deterministic build-manifest JSON was reconstructed from the release workflow; its complete SHA256 matches the published 368-byte asset (`1ba3507d658a15cebcd7e203a95982d772b446efb999cb82fc33f24c09e1067e`). The build manifest and binary APK manifest agree. Physical Thor compilation, login ordering and visible particles remain device acceptance work.

## Install and compare on Thor

1. Stop the client and game server, then stop the server runtime. Update the APK in place and start the existing server runtime with the game server stopped.
2. **Compile dinput8.dll → Deploy staged DLL** once, using the existing imported SDK/source. Wait for a successful compile before deployment. Keep native dinput8 enabled. No runtime/SDK/source reinstall or client reimport is needed; failed builds preserve the installed DLL.
3. Start the game server. Under Client → Graphics, audio & launch options → First-person spell particles, select **Diagnostics only**. Keep your working loading, renderer and controller settings. Leave Sound diagnostics and verbose Wine diagnostics off.
4. Fresh-launch/login directly into first person. Cast Minor Healing once before switching views; note whether particles appear. Export Logs after this short run, so the baseline cannot be lost to retention settings.
5. Stop the client, select **Repair + diagnostics (experimental)**, then fresh-launch/login and repeat the first cast before any view switch. Repeat with a relog and a zone transition. Also check normal third-person particles, camera transitions, input and reconnect. Export Logs and report which casts showed particles.
6. To undo the adapter, select **Original behavior** and stop/relaunch the client. There is no persistent modification to the game files.

A native `repaired hidden=1 before=0 after=1` sample together with restored first-cast particles supports the diagnosis on this device. A `permitted` baseline with missing effects means investigation must continue elsewhere. `unsupported_*`, `no_actor` or no `install=ready` points to a skipped or absent hook, not a successful repair. Keep camp work parked.
