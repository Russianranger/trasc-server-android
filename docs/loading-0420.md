# 0.4.20: model-loading wait experiment and display-stage measurements

## Evidence and scope

The 0.4.19 Thor comparison reduced server-selected → character-select UI from 73s to 31s, mainly by reducing spell checksum work. See [the device evidence](loading-0419-device.md). Preserve Faster spell loading and the working camera V2 adapter.

The remaining enabled run contains 12s of display initialization and 10s of global data initialization. The 7s UI XML/default-resource landmark interval includes file parsing, several validation passes and UI-object construction; it is not an exclusive file-I/O measurement.

Read-only inspection of the supplied exact executable found 18 explicit `Sleep(1)` sites in global model loading, after model requests and before the next graphics-manager service call. Six call through the Sleep import directly; twelve use registers loaded from that same import at three verified instructions (including register-to-register propagation). A short timed wait can accumulate across model loads. Its actual contribution on the Thor was **not measured** in the previous logs.

The optional **Reduce model-loading pauses (experimental)** mode changes only these scoped one-millisecond waits to `Sleep(0)`, which still yields to runnable threads ([Microsoft Sleep documentation](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-sleep)). It is default-off and independent of Faster spell loading. This is a candidate optimization, not a claim that waits account for the full remaining delay or that a hosted benchmark predicts device speed.

No model request, texture, validation pass, graphics-manager service call or other game timeout is removed. Timers elsewhere and the import table itself are unchanged. No game files are patched on disk.

## Implementation and guardrails

- Separate `TRASC_EQ_DISPLAY_V1` adapter in `eq_display_loading.h`; existing camera V2 and spell loader V2 headers unchanged. Older deployed DLLs keep their existing camera/spell capability until recompiled.
- Launch requires the existing exact SHA256/size guard for the supplied 2013 PE32 executable and the new marker in the deployed DLL. Installation additionally requires Wine, supported PE layout, all 30 expected relative CALL targets, nine Sleep instruction operands, all 18 `push 1 / call` sites and the actual resolved Sleep import. Validate everything before changing executable memory.
- The six CALL operands and three register-load operands point to an adapter-owned function-pointer slot. The game Sleep IAT entry is never modified. The wrapper preserves other delays and calls from other threads/outside the global-model scope.
- `client-loading.log` adds microsecond QPC measurements with a sequence number, total UI/global-model durations, inclusive XML subpass/UI-data/resolve/model-request durations, calls/failures, actual time in model waits, requested wait milliseconds and waits converted to yields. Measurements are collected in memory and written after each outer loading stage, not once per model/frame.
- XML routines use the four-stack-argument ABI proven by the supplied binary; the older upstream three-argument XMLRead declaration is not used. All functions/results are forwarded. Passes whose exact semantic names remain uncertain are labeled by RVA.
- Scope/thread bookkeeping uses RAII and Interlocked ownership. This does not add gameplay polling, alter the display transport or change shared-memory idle skipping.

For analysis, stage times are **inclusive**. Do not sum nested XML stages into the UI total. `model_wait` is distinct from `model_load`; compare both and the outer total in off/on runs. The difference between outer total and the measured stages includes uninstrumented work and measurement overhead; do not label it all disk I/O or GPU work.

## Particle report

The user reports missing effects during the first two or three first-person self-casts, followed by working effects in third person and continued effects after returning to first person. The previous log names `zapmuze.dds` in three failed particle texture loads. This pattern suggests camera-dependent emitter/visibility or resource initialization, but does not establish which one or link it to the checksum optimization.

The existing bounded read-only asset report now checks that exact texture in the root, SpellEffects and Resources directories, including case collisions/symlinks, size and DDS header fields. Sound diagnostics additionally checks four explicitly named spell archives and records the graphics DLL hash. These checks do not extract/replace assets. A readable header is not proof of successful D3D loading, and failure to locate it in these paths is not proof it is absent from all archives/search paths. No particle-rendering fix, forced camera switch, shader replacement or particle-setting change is included.

## Verification and device comparison

New PE32 fixtures execute relocated production wrappers under Windows/MSVC and ARM64 Wine/Box64. They check UI and model ABIs, boolean success/failure forwarding, all guarded sites, unchanged import table, real patched Sleep instruction forms, opt-out, non-one-millisecond waits and thread/scope exclusion. Existing checksum/camera and all seven release gates remain required. A 128-wait component sample reports timings without enforcing a flaky speed threshold.

1. Stop the client/runtime, update the APK in place, and compile/deploy dinput8.dll once with the already imported SDK/source. No work-Mac tools or runtime/server rebuild are needed.
2. Keep Faster spell loading and your other working settings fixed. Start fresh with Reduce model-loading pauses **off**, connect to the same character screen, then stop the client.
3. Enable Reduce model-loading pauses, relaunch, and repeat. Check models, input and normal entry into the world. Export Logs after the pair. If loading/rendering regresses, switch this option off and relaunch.
4. For a separate short particle check, enable Sound diagnostics before a fresh launch. Cast the same self-spell a few times in first person, switch to third person and cast, return to first person and cast again. Note the spell name and whether the transition fixes it; export logs, then disable diagnostics. Keep that diagnostic setting the same in both loading comparisons, or do the particle test separately.

Device gain and particle cause remain unconfirmed until that evidence is available. Camp remains parked.
