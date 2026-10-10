# TAKP camera input follow-up for 0.6.23

The Thor 0.6.22 test confirmed the managed v1 EQW helper was installed and
loaded (`b739dfe64b7f69be2ffebf13a1cf794bcfd9e37fe143a75134ca6359e60ef584`).
The latest input connection recorded 767 relative events, zero absolute events
and 47 button packets. The reported veering therefore has no evidenced competing
Android absolute-pointer path. Signed Android/controller/touch deltas and the
existing 15% TAKP camera gain are retained.

## Root-cause refinement

The 0.6.22 fixture proved the X cursor actually reached center after the cache
race. It did not measure the resulting polled/buffered DirectInput motion while
EQW's input and window threads run concurrently. A centered X cursor is
insufficient to prove correct camera deltas.

Wine 10 changes its shared cached cursor before the X11 warp. Its X11
`MotionNotify` handler suppresses stale warp motion only for events without an
HWND, while late events for the game window are still forwarded. Its server
converts core absolute motion into raw deltas against the now-centered cache.
That permits artificial motion or miscounting while repeatedly recentering.
Wine's later [upstream fix 65dc513](https://github.com/wine-mirror/wine/commit/65dc51308ac719153b2f2a685c43562cfabf1bf0)
explicitly removes that HWND suppression exception.

Primary source:

- [Wine 10 cursor-cache update](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/win32u/input.c)
- [Wine 10 warp serial, MotionNotify and clipping/raw-motion paths](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/mouse.c)
- [Wine 10 absolute-event raw delta conversion](https://github.com/wine-mirror/wine/blob/wine-10.0/server/queue.c)
- [XTest emits raw input before cursor confinement](https://github.com/mirror/xserver/blob/master/Xext/xtest.c)

## Narrow helper change

Inside EQW's existing Wine-only look gate, capture the prior clipping rectangle
and clip the pointer to one screen pixel at the client center. Wine's existing
clip-window XI2 raw-input path receives signed XTest deltas before confinement.
Active camera frames no longer perform repeated one-pixel nudge/center warps.
Native Windows still performs the original single `SetCursorPos` operation.

Restore the exact prior clipping rectangle when look ends, focus is lost, the
window is minimized or closed, or the right button is released. Explicit window
release matters when the game input hook is paused while dead, stunned or zoning.
The small state machine is locked across the EQW game-input/window threads,
retains its saved rectangle on API failure, and does not overwrite a clipping
rectangle changed by another owner. Normal cursor restoration remains upstream.
Acquisition also requires the physical look button to remain held, respecting
EQW's existing button-swap setting. This prevents a stale game look flag from
reacquiring the clip after release while game input is paused; no game flag is
changed from the window thread.
Release stamps a generation under the same lock. A physical-button query
overtaken by a lifecycle release cannot re-acquire that clip; the query stays
outside the lock because Wine may pump window messages from it. Foreground,
visibility and minimize checks are refreshed while acquisition is serialized.
Loading `eqmain.dll` explicitly releases the clip before the login UI takes
over the shared window and game-input polling stops.

The upstream source pin remains EQW 1.0.2 commit
`3b4d43562c9dacc89349185684bb0bf0b01f9d06`; the recipe hashes all three modified
upstream files before patching. The marker is `TRASC_TAKP_WINE_RAW_LOOK_V2`.
No Android input/native presentation payload or server rebuild is required.

## Qualification and device checks

The portable C++ fixture covers rectangle bounds, exact prior-clip restoration,
zero repeated clip/warp calls on idle frames, failed APIs, lifecycle retries and
external ownership changes. The expanded Windows open fixture measures both
`GetDeviceState` and buffered `GetDeviceData` in the real pinned Wine 10/Xvnc
runtime, including cardinal/diagonal reversals, 6400 pixels of travel beyond the
desktop, zero idle drift, right-button release, minimize/restore and free menu
pointing. It records the v1 helper comparison without treating timing-dependent
v1 losses as a deterministic assertion.
After focus restoration it repeats a signed native motion check and verifies
physical capture again; it also measures swapped-button look, physical release
without reacquisition and free-pointer movement against its observed position.

The fixture launches through `wine explorer /desktop=TRASC,800x600`, matching
the real launcher's virtual desktop. This matters: a standalone managed Wine
popup on headless Xvnc can report Windows foreground/focus success while actual
X focus stays on `PointerRoot`. Wine then caches the requested clip rectangle
but silently skips the driver grab. That standalone fixture did not qualify the
new input path. The production-matching fixture records independent X focus,
Windows focus and physical X pointer state, and requires actual confinement
before checking signed relative input. Diagnostics include Wine cursor, event
and DirectInput traces. The proof receipt binds the exact native probe, shared
camera header and integration script hashes to its CI run and source commit.
Free UI checks first set a known absolute XTest position and require that exact
physical point, then verify a signed relative delta. This proves release without
misreading X's retained unconstrained position as its displayed clipped point;
all captured camera motion remains entirely relative.

The exact helper and native qualification both passed in
[run 38081609076](https://github.com/Russianranger/trasc-server-android/actions/runs/38081609076)
at recipe commit `202ff0d995b45302d8cfb6a78e47ceea87a5b965`. The pinned x86 DLL
is 87,552 bytes with SHA256
`c103e024f1cde7829603475e1532d3baabd0764280c63ca2797e7e72569554f4`.
Its build receipt, compiled source and independently hashed fixture proof are
included with the backend helper bundle.

All twelve cardinal/diagonal signed sequences arrived exactly once in both
native DirectInput APIs; the 6,400/-6,400 pixel excursion also matched exactly,
with zero idle drift. Focus loss/restoration, physical release without
reacquisition, swapped-button look and free menu pointing passed. In that open
fixture the prior v1 helper delivered +5,531 horizontal pixels for an injected
-200 pixel reversal; an injected vertical +400 also produced +3,582 horizontal
pixels. This supports the warp-event mechanism behind the reported veer. The
timing-dependent v1 result is evidence, not a deterministic test assertion.

The managed upgrade accepts either the official pre-0.6.22 or 0.6.22 helper,
preserves an existing first `eqw.original.dll` backup and saves the exact
0.6.22 helper separately as `eqw.0622.dll`. Twenty-two TAKP backend tests pass,
including original/previous backup protection and refusal of custom helpers or
damaged/symlink backups before replacement. Other client DLLs, licenses, runtime
and server payloads are preserved.

Physical TAKP camera feel remains a Thor acceptance check. Test touch and right-stick
both axes, unequal reversal distances, diagonal input, leaving look for UI and
chat, focus switches, death/stun recovery and zoning. Export fresh logs for any
remaining veer and state the input device/movement sequence.
