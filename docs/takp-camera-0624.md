# TAKP camera: 0.6.24 investigation and bounded diagnostics

The Thor report after 0.6.23 is still unresolved: sustained look needs extra opposite movement before reversal. This continuation adds observation and broader open-fixture qualification. It does not claim another camera repair or device acceptance, and does not alter the V2 cursor-capture policy, 15% look gain, controller mapping, renderer, prefix, or game settings.

## Evidence recovered from the 0.6.23 device export

The latest `client-state.json` records the official V2 helper, SHA-256 `c103e024f1cde7829603475e1532d3baabd0764280c63ca2797e7e72569554f4`, automatically upgraded from the official 0.6.22 helper. Wine's module evidence shows `D:\eqw.dll` loaded natively, with builtin DirectInput. This rules out simply assuming the previous camera helper was absent or not upgraded.

The actual session used Wine 10 with Box64, Accurate CPU, the native surface, relative XTest transport, fullscreen 1280×720, DXVK 2.5.3 and Turnip 26.0.0. The device X server was TigerVNC 1.12.0. The latest input-session counters were 1,556 relative packets, zero absolute packets and 24 button packets. These aggregate counters cannot establish the signs, age, producer cadence or latency of individual events. They provide no evidence of an absolute Android pointer fighting camera capture in that session.

The export did not include the imported executable, the game's actual DirectInput format or axis mode, successful input samples, the opaque game consumer's intermediate state, or sustained clip-gate evidence. Normal EQW logging was disabled. Installation and module loading alone cannot prove that the helper continuously entered its clipped input path during the reported symptom.

## Gaps in the prior open fixture

The 0.6.23 fixture selected `c_dfDIMouse2` relative axes, drained up to 256 buffered events every five milliseconds, and synchronized each injected XTest event with `XSync`. Production sends `TRASCIN1` packets to the unchanged parser, which uses `XFlush`, and a default controller produces roughly one or two scaled pixels every 16 milliseconds, including zero-delta packets.

Wine's absolute-axis mode exposes cumulative values. A bounded buffered consumer can also encounter earlier positive events after opposite input is submitted, and `DIGDD_PEEK` preserves those events for another read. These are distinct possible mechanisms; neither is established as the Thor cause. The actual game function is proprietary and was not available for disassembly. EQW's existing hook restores its internal absolute state and accumulators to the saved right-click location after the original consumer returns. The new trace records both sides of that reset and the game's delta shorts so a future device sample can determine the real contract.

## New diagnostic helper

The helper retains behavior identity `TRASC_TAKP_WINE_RAW_LOOK_V2` and adds diagnostic identity `TRASC_TAKP_CAMERA_TRACE_V1`. Its Wine-only trace is `D:\eqw-camera-diagnostics.log`, beside the imported executable, and is included in the profile log export as `client/current/eqw-camera-diagnostics.log`.

The file contains tick timestamps, thread IDs, successful format flags and axis offsets, axis-mode/buffer-size property requests, successful polled samples, buffered request/return counts and flags, bounded event values with timestamps/sequences, observed event age, consumer values before/after/reset, and physical/focus/clip gates. Buffered offsets come from the application's successful format, including custom layouts. Failed calls never cause their output buffers to be read. The trace does not record chat, character names, credentials, or client assets.

Buffered descriptions cover the first 32 returned events on sampled calls. In ABS mode, `sum_values` sums cumulative axis values and must not be interpreted as relative travel. `oldest_age_ms` measures DirectInput timestamp age, not Android producer latency. `win_clip` and `win_cursor` describe Wine API snapshots; they do not independently establish physical X-server confinement.

Logging uses a separate lock, never holds the camera clip lock while writing, never holds a diagnostic lock across an original COM call, and never performs extra acquisition, state reads, queue drains, mode changes or value conversion. It samples ordinary frames and retains sign/gate transitions, with a 128 KiB per-process ceiling. A fresh process rotates only a file carrying this trace's exact ownership marker; a nonempty unrelated file or Windows reparse point is preserved. Native Windows does not create the file. The imported game's effective DirectInput contract remains unknown until its actual trace is received.

Automatic upgrade recognizes only the original managed helper and the official 0.6.22/0.6.23 hashes. It preserves the first available `eqw.original.dll`, the existing `eqw.0622.dll`, and saves the exact previous 0.6.23 helper as `eqw.0623.dll`. A modified or linked backup prevents helper replacement. Custom DLLs still require the existing explicit preparation flow.

## Qualification and limits

The extended fixture uses the actual production packet parser and `XFlush` pipeline over its private socket. It retains all previous relative-axis/lifecycle assertions and adds controller cadence, zero packets, immediate pipelined reversals, fragmented writes, stop-and-idle behavior, absolute format and relative-axis property requests, a saved-state reset model, buffered peek/consume behavior, bounded old-event consumption, and a custom X/Y/Z layout at offsets 8/0/4. The diagnostic writer is checked for its ceiling, owned-session rotation and foreign-file preservation. Submitted packet counts must match the parser's decoded counts.

The saved-state reset model deliberately demonstrates positive cumulative ABS values after negative input. It is a model of a possible consumer, not a reconstruction of the actual game. Qualification runs on pinned Wine 10 and the CI host's Xvnc, without Box64, the Thor GPU, or the imported game. It cannot establish device camera acceptance. Actual DLL/hash/run information is appended only after the coordinated native qualification succeeds.

The coordinated qualification succeeded on [run 38102758503](https://github.com/Russianranger/trasc-server-android/actions/runs/38102758503), source commit `f6f354b41d41cf93fc4d2d0672c183771856083f`. The actual Windows DLL is 93,696 bytes, SHA-256 `495d6e1711e21f012d1f8c9581af74fdbdccac5f45e2e93508e40b4bd3dbca1d`. The production parser decoded exactly 1,886 relative packets, four free-UI absolute packets and ten button packets, matching submission counts. Three 360-packet pipelined reversal bursts, including fragmented writes, matched their signed totals in both native APIs. The original 12 signed sequences, 6,400-pixel excursion, idle and lifecycle assertions also passed.

The ABS mode baseline was `[400,300]`, then `[480,340]` after `[80,40]`, and `[460,330]` after `[-20,-10]`; resetting a model consumer's previous state to the baseline therefore produced `[60,30]`. Relative mode returned `[40,0]` then zero on the next state read. Repeated PEEK returned the same queued events; a one-event read returned an earlier positive value after negative events had been submitted. Custom-format memory was `[-5,0,9]`, while the observer correctly labeled X/Y as `[9,-5]`. The trace was 44,444 bytes; cap, foreign-file preservation and owned-session rotation passed. These observations narrow the diagnostic distinctions without identifying the proprietary client's actual mode or asserting a camera repair.

## Next Thor sample

Restart the TAKP client without rebuilding its server or resetting its prefix. In a quiet area, enter first person and start this short test promptly: turn left for two seconds then right for one second; repeat in the opposite order; repeat up/down and down/up; stop input and check for drift. Repeat separately with touch and controller, noting which input, Look-toggle state, and direction produced overcorrection. Export logs within the first minute while retaining the exact movement order. A missing diagnostic file is a collection/write-path problem to investigate, not evidence that capture or the camera passed.

The resulting trace should distinguish cumulative axis values, buffered backlog/peek, stale failed state, consumer reset, and fallback clip gating before selecting any new delivery fix. TAKP NPC visibility and Traditional StoneUI remain separate concerns.
