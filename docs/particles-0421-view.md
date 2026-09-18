# 0.4.21 particle follow-up: third-person casting is not required

**Investigation update:** the original executable has now been recovered and its camera dispatcher/first-person callbacks verified. Entry calls `ShowParticlesWhenInvisible(true)` only if the local graphics actor already exists. See [exact-client view routines](particles-view-routine-0421.md) for addresses, six original-code emulator checks, and the next targeted graphics-DLL analysis. The historical recovery step below is complete; the live cause remains unproven.

September 18, 2026. The user completed the discriminating test from [the loading/device review](loading-0421-device.md):

1. Cast Minor Healing once in first person: no particles.
2. Switched to third person for a few seconds, without casting.
3. Returned to first person and cast: particles appeared.

This is a user-observed result, not a new log bundle or an instrumented camera trace. Earlier tests also showed the initial failure returning after logging out and back in.

## What the result establishes

A third-person spell cast is **not required** for recovery. The view-only excursion is a working recovery sequence in this test. The next investigation should focus on state updated when the local character becomes visible or the view changes: actor/attachment initialization, visibility flags and render resources are candidates. None is yet a proven faulty function.

Because first-person effects work after returning, a permanently disabled first-person effect setting alone does not explain the sequence. It also does not establish that every texture is valid, rule out resource retries, or identify a Wine/DXVK fault. There is no matched first-person-only wait control, so elapsed time/deferred work has not been independently excluded. Do not turn this into another broad user test cycle; capture that distinction in targeted development diagnostics if needed.

The prior `zapmuze.dds` warnings are still a separate unresolved observation. The previously inspected Minor Healing definition uses other textures, and the last diagnostic session had no recorded texture-load failure. See the linked device review for the asset provenance and limits.

## Bounded source review

Reviewed the add-on source at the revision pinned by the DLL workflow, `4c653ca2d16aaede33b7011d07254c520ac5f5df`. The five files below are byte-identical to the older `18141ae0c9a11813733f08fa77db986951b853d6` snapshot checked during this review. This comparison is between public source snapshots, not a new verification of the device's imported source archive.

- [EQClasses.h](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Client/eqgame_dll/EQClasses.h) declares `CDisplay::ToggleView`, `UpdateCameraAfterModeSwitch`, `SetViewActor` and `CreatePlayerActor`.
- [EQClasses.cpp](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Client/eqgame_dll/EQClasses.cpp) provides conditional `FUNCTION_AT_ADDRESS` forwarding stubs, not those engine implementations. The inspected public [eqgame.h](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Client/eqgame_dll/eqgame.h) does not define their address macros. Names alone are insufficient to choose a hook or call signature for the exact executable.
- [EQData.h](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Client/eqgame_dll/EQData.h) describes actor-related fields in the player layout, but their runtime meaning and relevant transitions still require verification against the supplied client. Do not infer a live pointer's validity from a field name.
- [eqgame.cpp](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Client/eqgame_dll/eqgame.cpp) contains a `SetCCreateCameraHook` with character-select-specific behavior and commented-out installation sites. It is not evidence of an active in-world particle repair.

The header also describes `EqMobileEmitter` with an `EqSoundManager` constructor. Do not mistake an audio emitter declaration for the spell-particle renderer merely because the name contains “emitter.”

The launcher's current [camera adapter](../backend/eq_camera_mouse.h) reads game state and recenters the OS cursor after input delivery. It does not initialize actors or switch the first/third-person view. This source inspection provides investigation targets, not evidence that the adapter causes or fixes this symptom.

## Next development work and acceptance

1. **Executable recovery and view-callback trace completed:** the previously supplied exact `eqgame.exe` (SHA256 `4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3`) was recovered from the earlier workspace. The relevant actor call enters `eqgraphicsdx9.dll`; the [new routine note](particles-view-routine-0421.md) records verified addresses and the exact graphics file still needed. Do not request another executable upload or substitute another client's offsets.
2. Add bounded, exact-client diagnostics for viewpoint and verified actor/attachment state before/after the view-only recovery. Prefer transition/cast events over per-frame or audio trace spam. Verify calling conventions, thread/lifetime constraints and read safety before adding any hook.
3. Once a missing/stale state transition is identified, implement the smallest guarded correction and retain opt-out. Do not call `CreatePlayerActor` blindly, fabricate an actor pointer, or silently perform automatic camera toggles as though that proved an initialization fix.
4. Acceptance should start with a fresh login directly into first person: the first Minor Healing cast must show particles without changing views. Repeat after relogging and zoning, and check ordinary third-person effects, controller input, loading and reconnect behavior.

For current play, the tested workaround is a brief third-person view followed by first person when the symptom occurs; no third-person cast is necessary. Keep the current APK/DLL and working loading options. No additional audio log, repeated version install, SDK import or DLL compilation is needed to establish this result.

This update records evidence and development steps only. No product change or new APK is claimed. Camp remains parked; preserve the confirmed controller/reconnect fixes and loading improvements. No subagents used.
