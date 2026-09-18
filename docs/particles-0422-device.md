# 0.4.22 device confirmation: first-person particle repair works

September 18, 2026. The user reports that the fix worked. The two supplied Thor bundles independently show the missing particle-permission state in diagnostics mode and a successful one-time correction in repair mode. This confirms the targeted fault state and repair on this device, beyond the earlier controlled fixtures.

## Evidence

Both exports report app 0.4.22 and the same successfully compiled/deployed 1,716,224-byte native DLL, SHA256 `a5bda1fe2af6367e8fbeacc3054bb8089fbb33681d5c8b61eb73f869a73a6566`. All six recorded adapter-header hashes match the released source, including `eq_first_person_particles.h` SHA256 `ee8e3f66e26343b5b417fbf520bbc3ae3af9d48cf4e14baccf3a962acee05a67`. Native/system DirectInput loading is confirmed in both client states.

| Bundle | Export time, UTC | Mode | Native observation |
| --- | --- | --- | --- |
| `logs-1107241098681185606.zip` | 20:31:04 | Diagnostics only | `install=ready`; hidden root actor, permission `0 → 0`, `missing_permission`, zero repair attempts |
| `logs-8361952957421422627.zip` | 20:41:06 | Repair + diagnostics | `install=ready`; hidden root actor, permission `0 → 1`, `repaired`, one attempt; following sample remains `permitted`, `1 → 1`, still one attempt |

Bundle SHA256 values are respectively `afb653f370ba98f73d0e5df01a49fe0f1b794910b587168bb53cf51f843c629b` and `d74b26ab10774c18dc96fbcc0d543a1df28674018ae13876cf3c54194fbd76af`. The later archive's `client-particles.previous.log` exactly preserves the first archive's diagnostics log, tying the comparison together.

The repair sample occurs at game tick `362281138`; the next observed update at `362281688` confirms permission remains enabled. Both samples reference the same actor, with `parent=00000000` and `hidden=1`. The game therefore retains first-person body hiding while permitting particles. There is no retry loop: `attempts=1` in both samples. The diagnostic and repair logs contain only 221 and 379 bytes respectively.

Together with the user's visible result, this supports the missing hidden-actor permission as the cause of the reported first-person failure. The exact earlier initialization/actor-replacement sequence that left the flag unset was not traced; do not claim that upstream sequence has been established.

## Regression review and scope

- Both sessions retain faster spell loading, reduced model-loading pauses, the camera adapter, Turnip 26.0.0, Native Surface and native DirectInput. Sound and verbose Wine diagnostics are off.
- Spell loading succeeds in 1,752 ms (diagnostics) and 2,067 ms (repair), with identical 40,914 records, 40,916 fast checksums, 79,627,413 checksum bytes and zero parser/checksum fallbacks. Server-selected to first character-select initialization is 31 s and 27 s respectively. These single samples show the working loading path remains active; they are not evidence of a particle-related speedup.
- No `repair_failed`, `attempt_limit` or rejected installation is present. Current Wine/game logs contain no unhandled-exception, stack-overflow or segmentation-fault signature. Both supervisors record an explicit stop request; the diagnostic launch exit is 0, while the repair launcher exit is unrecorded/null and must not be described as a measured clean process exit.
- Both game logs still contain the disconnect-to-character-select behavior: 20:30:21 and 20:40:24 UTC, each followed by successful character-select initialization. This occurs with repair disabled as well as enabled. It remains separate from the particle fix; camp work stays parked.
- Existing compatibility warnings remain, including the skin-effect load warning, gamma-ramp warning, MIDI support and world-authentication message. The repair session also records a RpcSs startup warning before entering the world. These are not adapter failure evidence. The identical retained `client-runtime.log` contains older startup-cancellation history, and `app.log` contains earlier busy-operation errors; neither establishes a new crash in this pair. Android exit history does not add a crash for these runs.

The captured pair contains one in-world actor observation per mode, followed by return to character select. It does not independently demonstrate a second in-world login or a zone-to-zone transition with repair. Do not turn the user's successful report into a claim that every lifecycle scenario has been exercised, or ask them to repeat the completed baseline merely to reconfirm this fix.

## Current action

Keep **First-person spell particles → Repair + diagnostics (experimental)** enabled. Its diagnostic output is bounded and was minimal in this pair. Turning the option off restores the original behavior; it is not necessary to disable it after this successful test. Keep the working loading/controller settings and native DLL. No APK update, DLL rebuild, runtime reinstall or asset reimport is required.

Record 0.4.22 as device-confirmed for the reported first-person particle problem. Preserve the opt-out and guards. Further loading optimization is separate work and should use the existing UI/XML/global-model timings; do not broaden the particle patch or resume camp changes as part of this acceptance update. This commit is documentation only with `[skip ci]`; the released APK and implementation remain unchanged.
