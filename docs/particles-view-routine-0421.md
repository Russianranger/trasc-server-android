# Exact-client view routines and first-person particle state

September 18, 2026. Follow-up to [the user's view-only recovery test](particles-0421-view.md). The normal camera-mode dispatcher and its first-person callbacks have now been identified in the previously supplied executable. The first-person entry callback calls the graphics actor method named **`ShowParticlesWhenInvisible(true)`** by the matching RoF2 interface definitions. It skips this call if the local player or its graphics actor is absent.

This is a concrete mechanism consistent with the reported recovery: first-person camera updates hide the player model, while re-entering first person enables particles on that hidden actor. A skipped entry call, a subsequently replaced actor, or a later reset of its flag could leave the initial actor state wrong. **The device's actual flag and initialization order have not been captured, so the root cause and a repair are not yet proven.** No product code, APK or installed DLL changed in this investigation.

## Binary and source provenance

Recovered the original private executable from the earlier local workspace; another `eqgame.exe` upload is unnecessary. SHA256:

```text
4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3
```

It is an x86 PE with preferred image base `0x00400000`. Addresses below are preferred virtual addresses (VA); use module base plus RVA when reasoning about a relocated image. No executable, SDK, or full private disassembly is included in the repository.

Public naming/layout evidence comes from **macroquest/eqlib, emu-rof2**, pinned at commit `3eafc8217e690b3c93201a17ec205410db1cac82`:

- [eqgame offsets](https://github.com/macroquest/eqlib/blob/3eafc8217e690b3c93201a17ec205410db1cac82/include/eqlib/offsets/eqgame.h): camera array `0xDE0D64`, current mode `0xD1FD9C`, and `CDisplay::SetViewActor` at `0x48F030` independently match the executable.
- [Actor interface](https://github.com/macroquest/eqlib/blob/3eafc8217e690b3c93201a17ec205410db1cac82/include/eqlib/graphics/Actors.h): vtable byte offsets `+0x034` = `SetInvisible(bool)`, `+0x038` = `IsInvisible()`, `+0x098` = `SetPitch(float)`, `+0x10C` = `SetInvisibleAsAttachment(bool)`, `+0x23C` = `ShowParticlesWhenInvisible(bool)`, and `+0x240` = `ShouldShowParticlesWhenInvisible()`.
- [Graphics offsets](https://github.com/macroquest/eqlib/blob/3eafc8217e690b3c93201a17ec205410db1cac82/include/eqlib/offsets/eqgraphics.h): particle creation/render reference addresses for the next DLL analysis. These have **not** been verified against the installed graphics DLL.

The proprietary implementation has no recovered symbols. Function labels below describe verified behavior; the public interface supplies the graphics method names, not proof of their internal implementation in the device DLL.

## Located routines

| Role | VA | RVA | Evidence |
| --- | --- | --- | --- |
| Camera-mode dispatcher | `0x0048ADF0` | `0x0008ADF0` | Invokes old-camera leave and new-camera enter, then stores mode |
| Cycle-view handler | `0x00494160` | `0x00094160` | Selects the next mode and calls the dispatcher; input call at `0x004D91B5` |
| Restore remembered mode | `0x0048F1E0` | `0x0008F1E0` | Reads `0xD1F3CC` and calls the dispatcher |
| `SetViewActor` | `0x0048F030` | `0x0008F030` | Matching public offset and embedded `SetViewActor` diagnostic |
| First-person enter | `0x00797220` | `0x00397220` | Actor virtual call `+0x23C` with `true` |
| First-person leave | `0x007971B0` | `0x003971B0` | Actor virtual call `+0x23C` with `false`; remembered actor pitch cleanup |
| First-person update dispatcher | `0x00797160` | `0x00397160` | Selects frame implementation at vtable `+0x40` or `+0x44` |
| Player actor-assignment thunk | `0x0059E3F0` | `0x0019E3F0` | Adds `0xEA4` to the player pointer, jumps to actor-client setter |
| Actor-client setter | `0x0040C000` | `0x0000C000` | Transfers application data/type and assigns actor pointer |

`SetViewActor` changes the viewed actor and has additional target/camera side effects. It is not a substitute for the normal mode dispatcher and should not be invoked speculatively as a particle fix.

## Transition order and calling convention

`0x48ADF0` takes one stack argument, the requested mode, and returns with `ret 4`. It reads its objects from globals and does not use the incoming `ECX` as an object pointer. Its camera callbacks use `ECX = camera`, take the other camera as one stack argument, and return with `ret 4`.

The dispatcher first preserves the original character restriction: a query through `0x7BED30` returning at least 70 blocks a requested nonzero mode. For an allowed transition:

1. Read the old mode at `0xD1FD9C` and camera pointers from `0xDE0D64`.
2. Call old camera vtable `+0x3C` (leave), passing the new camera.
3. Call new camera vtable `+0x38` (enter), passing the old camera.
4. Perform the existing mode-6 numeric reset when appropriate.
5. Store the new mode at `0xD1FD9C`.

**Both callbacks run while the global mode still contains the old value.** Any future diagnostics or correction must account for that ordering.

Mode 0 uses first-person vtable `0x9D0F80`. Inspected camera objects for modes 1–6 use a shared `ret 4` no-op at `0x5D7540` for these two transition slots. Their frame updates still have their own behavior; empty enter/leave callbacks do not establish that third-person rendering performs no other initialization.

## The particle-related state change

The first-person entry callback does the following, expressed as behavioral pseudocode:

```cpp
player = *localPlayer;                      // global VA 0xDD2630
if (player != nullptr) {
    actor = *(player + 0x101C);
    if (actor != nullptr) {
        actor->ShowParticlesWhenInvisible(true); // vtable byte offset 0x23C
    }
}
camera->needsUpdate = true;                 // byte at camera + 0x4C
```

The graphics call instruction is at `0x797240`; no deferred retry is installed by this callback. Leaving first person makes the corresponding call with `false` at `0x7971D2`. The leave routine may also call `SetPitch(0.0f)` on its remembered actor before clearing the camera's remembered-player pointer at `+0x48`. That slot is a pitch setter, not opacity.

The inspected first-person frame paths beginning at `0x797250` and `0x797550` call `SetInvisible`, including a `true` call at `0x7974A5`. They do not directly call vtable `+0x23C` to repeat the particle permission. This is a bounded inspection, not proof that no transitive graphics helper can change the flag.

The actor assignment at `0x40C000` moves application data/type and writes actor-client `+0x178`, equivalent to player `+0x101C`. It contains no direct call to the particle-permission slot or the camera entry routine. The creation path calls this setter at `0x48FECC`. This makes actor lifetime/replacement a relevant diagnostic target; it does not establish which path runs first on the Thor or what all graphics constructor/helper calls do.

The public `CActor` layout also names a backing flag, but **do not write a guessed field offset**. Verify the actual DLL's setter, getter, constructors and render tests before introducing any runtime access.

## Reproducible verification

[tools/verify-client-view.py](../tools/verify-client-view.py) checks the complete executable hash, loads its PE image into a 32-bit Unicorn emulator, and executes the original dispatcher and first-person callback instructions against synthetic objects. Graphics calls and the unrelated character query/free-camera reset are controlled stubs. The input file is read only.

Run with Python, `pefile==2024.8.26` and `unicorn==2.1.4` installed in a local development environment:

```sh
python tools/verify-client-view.py /path/to/the/supplied/eqgame.exe
```

All six scenarios passed on September 18, 2026:

| Scenario | Observed original-code behavior |
| --- | --- |
| Enter first person before graphics actor exists | Mode changes to 0; particle setter is skipped |
| Invoke first-person entry once actor exists | Particle setter receives `true` |
| First person → another camera → first person | Setter receives `false`, optional pitch resets to zero, then setter receives `true` |
| Null local player | Both callbacks return without actor calls |
| Another camera → another camera | No first-person particle setter call |
| Original character restriction blocks a transition | Mode stays 0; neither callback changes actor state |

The roundtrip also verifies that callbacks see the old global mode. Calls return to the expected sentinel, remove one argument from the stack, and preserve EBP/EBX/ESI/EDI. A wrong executable hash is rejected, and running Python with `-O` is rejected so assertions cannot be disabled. This confirms the tested x86 control flow and ABI properties. It does not emulate the graphics DLL, render a spell, reproduce live login ordering, or prove the proposed cause on the device.

## Next targeted step

The exact `eqgraphicsdx9.dll` implementation was not located among available prior artifacts. `logs/client-sound-assets.json` in `logs-7280042745619990780.zip` identifies it as **1,604,608 bytes**, SHA256:

```text
164fc072547aab752567ba88bf6936d0e328c44a16a1480f340d27aef0ba6290
```

Obtain this installed file using the existing app: **Files → Folder path `client/current` → Open folder → search `eqgraphicsdx9.dll` → Search → select the match → Export file**, then attach it. Filename search ignores capitalization. No new APK, compiler import, DLL build, audio trace, or repeated spell test is needed for this step.

Then:

1. Verify its hash; resolve the actual `+0x23C` setter and `+0x240` getter, initialization/reset sites, and the particle renderer's visibility gate. Public reference RVAs for `CParticleSystem::CreateSpellEmitter` (`0x70580`) and `Render` (`0x72110`) are leads only until verified.
2. Add bounded diagnostics on the game's existing update thread for local actor creation/replacement, first-person entry, and the relevant flag. Capture whether the actor's flag is false before recovery and true afterward. Avoid high-volume per-frame logs. Verify module identity, original bytes, object lifetime and call signatures before installing hooks.
3. If confirmed, apply the missing particle permission when the local actor becomes ready in first person, retaining the normal leave behavior and opt-out. Do not force view toggles or recreate the player actor. If the flag is already correct, continue into emitter/visibility state instead of calling this a flag repair.
4. Acceptance: fresh login directly into first person, first Minor Healing cast visible without a view change; repeat after relog and zoning. Check ordinary third-person effects, normal camera transitions, controller input, loading and reconnect. Keep all existing release gates if a product build is made.

The current workaround remains a brief third-person view and return; casting in third person is unnecessary. Keep 0.4.21 and its deployed DLL, the working loading options, and the confirmed controller/reconnect improvements. Camp remains parked. This commit contains analysis and a read-only verification tool only; no particle fix or device acceptance is claimed. No subagents used.
