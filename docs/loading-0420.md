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

## Released and verified

Implementation: `6276054d2d0d62b9a6f85afe519269d61e842a59`, version 0.4.20/code37, [release run 35362750049](https://github.com/Russianranger/trasc-server-android/actions/runs/35362750049). All seven jobs completed successfully: database, WineD3D, Vulkan, Microsoft DLL, APK, full ARM64 runtime and preview publication. No failed gate was waived.

All 135 Python tests and local native/JVM checks pass. Microsoft v142 builds the real pinned add-on and runs the x86 fixtures. The downloaded ARM64 Wine/Box64 fixture confirms UI/model ABI and boolean passthrough, actual patched Sleep instruction execution, original import preservation, layout rejection and thread/scope exclusions. Its isolated 128-wait sample is **136,892µs original / 211µs yield**. That only measures the sleep mechanism; it neither includes asset loading nor predicts the Thor's total gain. Existing checksum and camera fixtures remain passing. All 30 call sites, nine import operands and 18 wait sites were independently checked against the supplied executable; no proprietary executable/SDK was uploaded.

Independent candidate verification: APK v2 RSA/SHA256 signature and complete signed-content digest, unchanged signing certificate, manifest, all **39** Python/header/UI assets and **33** corresponding native source/build recipe files verified. Browser flows and the 412px phone options screenshot pass review.

- Candidate artifact `10555329784`, ZIP SHA256 `d750766420231de4455150a2ffafc94b662d447db3ccb2288d5ecf9a968e3766`.
- APK: 10,532,759 bytes; SHA256 `c129d3fc46ad5fad8d1f6238606c494f9d3e796630902667b2db2544e20d06fc`.
- Native source archive: 114,558,331 bytes; SHA256 `90c7f61631939df76d8873cf05253a8a10b73e8f3af6cfb71ff4b1b8bed781f4`.
- Certificate: `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`; app ID `io.github.russianranger.trasc.preview`.

Ignored local evidence is under runtime-work, including the candidate ZIP, APK/source, verification utility/report, browser screenshots and downloaded fixture logs. Device loading improvement and particle-rendering cause remain unconfirmed.

The full suite also passed direct/PRoot Software, DXVK and VirGL graphics/audio/model/input/restart checks, Android lint, preserved signing, database/session roundtrips and native idle/SHM capture. Downloaded DXVK evidence confirms free menu pointing and continued camera movement after recentering in both runtime modes; both idle tests report shared memory and correct pixels after resuming. These are hosted checks, not a physical Thor acceptance test.

Public preview tag points to the implementation above. Public APK/native-source asset digests and sizes match the downloaded candidate; build-manifest digest is `ea77ab04b1b621e6fd90dd0e6dc8bdb49067c327170907b543f105ccd553074b`. Runtime publication succeeded. Release verification used the downloaded Actions candidate and public release metadata rather than downloading the public APK again. This final evidence update is documentation only with `[skip ci]`.
