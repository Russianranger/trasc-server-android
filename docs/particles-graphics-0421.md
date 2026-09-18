# Graphics DLL confirms the first-person particle visibility mechanism

September 18, 2026. Follow-up to [the executable's view routines](particles-view-routine-0421.md). The user supplied the installed `EQGraphicsDX9.dll`. It exactly matches the size and hash from the device report. Its original code confirms that a new actor starts with `ShowParticlesWhenInvisible` disabled, and particle processing suppresses effects for a hidden actor unless that flag is enabled.

Executing the original executable and DLL together against controlled objects reproduces both a late-created-actor failure and recovery from the view-only roundtrip. Original actor replacement also leaves the replacement's flag disabled. A single call to the original particle-permission setter restores the tested visibility path without changing camera mode or making the body visible.

**This confirms the mechanism and a narrowly scoped correction candidate. It does not establish which initialization/reset sequence occurs on the Thor.** No live actor/flag trace has been collected, no complete spell was rendered in this fixture, and no product repair or new APK is claimed. No more game files are needed for the next targeted development step.

## Exact binary identities

| Input | Bytes | SHA256 |
| --- | --- | --- |
| Previously supplied `eqgame.exe` | 8,774,656 | `4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3` |
| Supplied `EQGraphicsDX9.dll` | 1,604,608 | `164fc072547aab752567ba88bf6936d0e328c44a16a1480f340d27aef0ba6290` |

The graphics DLL is x86, timestamp `0x518DE5B6`, preferred image base `0x10000000`, image size `0x1E6000`. DLL addresses below are preferred VAs; a running process must use the loaded module base plus RVA. Both private binaries remain outside the repository and were read without modification.

The public RoF2 interface names cited in the earlier note now match the supplied DLL's actual method implementations and RTTI/vtable layout. They are no longer the only evidence for the setter/getter offsets.

## Verified routines and state

| Role | DLL VA | RVA | Verified behavior |
| --- | --- | --- | --- |
| `CActor` base constructor | `0x1003AB80` | `0x3AB80` | Clears actor byte `+0x5C` at instruction `0x1003ABFB` |
| `ShowParticlesWhenInvisible(bool)` | `0x1003B1A0` | `0x3B1A0` | Stores its boolean argument at actor `+0x5C`; returns with `ret 4` |
| `ShouldShowParticlesWhenInvisible()` | `0x1003B190` | `0x3B190` | Returns actor byte `+0x5C` in AL; plain `ret` |
| Hierarchical actor `SetInvisible(bool)` | `0x10046F10` | `0x46F10` | Forwards to visibility flags at actor `+0xE0` |
| Hierarchical actor `IsInvisible()` | `0x10046F20` | `0x46F20` | Reads the corresponding visibility bit |
| Emitter owner invisibility query | `0x1006EB20` | `0x6EB20` | Resolves attachment/actor ownership and queries root actor invisibility |
| Emitter owner particle-permission query | `0x1006EBB0` | `0x6EBB0` | Resolves ownership/root actor and calls vtable `+0x240` |
| Particle processing routine containing the gate | `0x10072160` | `0x72160` | Includes direct actor and attachment/owner visibility paths |
| Direct actor visibility block used in the fixture | `0x100726E4` | `0x726E4` | Tests invisibility, particle permission, and separate disabled state |

The actual DLL has five vtables using this same setter/getter pair:

| RTTI class | Vtable VA |
| --- | --- |
| `CActor` | `0x10136824` |
| `CHierarchicalActor` | `0x10137074` |
| `CHierarchicalAttachedActor` | `0x101373B4` |
| `CParticleActor` | `0x1013802C` |
| `CSimpleActor` | `0x1013841C` |

Each has the setter at byte slot `+0x23C` and getter at `+0x240`. The base `CActor` has abstract visibility methods; the fixture supplies the verified hierarchical vtable and controlled backing state rather than calling those abstract entries.

The verified setter changes only the permission byte. It does not load textures, create emitters, initialize model resources, alter camera state, or make the actor visible. The original camera entry call therefore has a precise state effect independent of third-person casting.

## How the particle path uses the flag

The actor-backed block at `0x100726E4` checks `IsInvisible()`. If true, it calls `ShouldShowParticlesWhenInvisible()` at `0x100726FB`. A false result reaches `0x100727F4`. When effect field `+0x98` is `-1`, that path sets a local suppression byte at stack `+0x1B`. The same routine later tests this byte, advances the active particle buffer through its end (`0x10072A7C`–`0x10072AA5`), and skips the generation section at `0x10072AB5`/`0x10072ABA`.

For the tested effect sentinel (`-1`) and a separately enabled actor:

| Actor hidden | Particle permission | Visibility suppression |
| --- | --- | --- |
| No | Off | No |
| No | On | No |
| Yes | Off | **Yes** |
| Yes | On | No |

A separate disabled-actor check can still suppress particles when permission is on. A non-`-1` effect sentinel bypasses this particular suppression assignment. These are real conditions, not a universal claim about every effect. Attachment paths also resolve ownership/root actors; mounted or other special views require their own live-state confirmation.

The public `CParticleSystem::Render` reference at `0x10072110` is a separate routine that calls a helper for four batches. Do not label the inspected `0x10072160` processing routine as that entry point or treat its visibility block as a complete D3D render test.

## Original-code reproduction

[tools/verify-client-particles.py](../tools/verify-client-particles.py) extends the earlier view verifier. It requires the two exact private inputs, checks both complete SHA256 values, maps their PE images in Unicorn, and executes original code. Dependencies used: `pefile==2024.8.26`, `unicorn==2.1.4`.

```sh
python tools/verify-client-particles.py /path/to/eqgame.exe /path/to/EQGraphicsDX9.dll
```

All **11 checks passed**:

1. Actual base constructor clears an initially nonzero permission byte.
2. Visible actor, permission off: no visibility suppression.
3. Visible actor, permission on: no visibility suppression.
4. Hidden actor, permission off: suppression.
5. Hidden actor, permission on: no visibility suppression.
6. Enter first person while actor pointer is absent; assign the actor through original `eqgame.exe` routine `0x40C000`; hide it through the original DLL method: suppression. Execute original first-person → other view → first-person dispatcher calls: permission becomes true and suppression clears while the actor remains hidden.
7. Replace a permitted actor through original `0x40C000`: application data/type transfer correctly, but the replacement keeps its constructor's false permission. Original first-person entry reapplication restores the path.
8. Call only the original setter on the replacement: exactly byte `+0x5C` changes, the camera objects/mode remain unchanged, the unrelated old actor retains its state, and suppression clears.
9. Separate disabled-actor state still suppresses even with permission enabled.
10. Original first-person leave clears permission; a subsequently visible actor still passes the visibility gate.
11. The original non-`-1` effect-sentinel exception remains intact.

Function calls also check stack cleanup and EBP/EBX/ESI/EDI preservation. The original camera restriction/free-camera numeric reset retain the earlier controlled stubs. The actor constructor, assignment, permission methods and all virtual methods reached by the tested visibility block execute original instructions. The derived actor's vtable/backing state and the effect are synthetic; the full derived constructor, entire frame, Direct3D, emitter creation and live login are not emulated. No private instruction bytes are embedded in the committed verifier.

## Smallest next development change and device acceptance

The next test build should combine bounded state diagnostics with a **default-off first-person particle repair**. It can use the game's existing first-person update callback (vtable VA `0x9D0F80`, slot `+0x08`, original target `eqgame.exe` VA `0x797160`) as a candidate point to check the local actor after the normal update. This hook has not been implemented or validated in the live client; verify thread, ordering and call convention before shipping it.

For that implementation:

1. Require the exact executable/DLL identities and expected original method/vtable values. Preserve the original update and restrict repair to in-world first person, the current local player, and a valid graphics actor. Confirm attachment/root ownership; skip special-view cases that do not match those conditions.
2. Record only actor/mode/permission transitions and repair attempts in a bounded log. Include actor identity, whether it is invisible, permission before/after, and whether the actor was newly observed/replaced. A profile-only mode should read without changing state.
3. When the verified local actor is hidden and permission is false, call its verified `ShowParticlesWhenInvisible(true)` once for that observed missing state, then confirm through the getter. Use the original method instead of writing a field or switching camera modes. Retain original first-person leave behavior and all other visibility/disabled-state checks. Avoid repeated log output or a busy repair loop.
4. A false → true transition that restores the first cast would support the diagnosis on the device. If the flag is already true during the initial failure, leave it unchanged and trace emitter ownership/attachments next; the present evidence does not justify a broader visibility override.

Device acceptance for that future build: launch directly into first person with repair off and then on in separate fresh sessions; cast Minor Healing once before any view switch. With repair on, the first cast should show particles. Repeat after relogging and zoning, then check ordinary third-person effects and camera transitions, controller input, loading and reconnect. Compare the bounded state log to the visible result. There is no useful new device test on the unchanged 0.4.21 build beyond the already completed sequence.

Current APK/DLL remain 0.4.21. Preserve the working loading options and controller/reconnect fixes; camp remains parked. This commit adds the analysis and read-only verifier only, with `[skip ci]`; any future APK must pass all existing release gates. No subagents used.
