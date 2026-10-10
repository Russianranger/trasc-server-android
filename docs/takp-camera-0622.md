# TAKP camera reversal repair

The reported camera behavior matches accumulated cursor displacement: after a
rightward movement, a smaller leftward movement still leaves the pointer to the
right of the client center. The same mechanism applies vertically. Android
already sends signed relative motion, and its fractional rounding residue is
less than one pixel. Reducing sensitivity does not remove the accumulated
displacement.

## Source diagnosis

EQW 1.0.2, pinned to upstream commit
`3b4d43562c9dacc89349185684bb0bf0b01f9d06`, forces foreground, nonexclusive
DirectInput and recenters the Windows pointer while its existing right-button
look state is active. Its input/frame and window-message processing can run on
different threads. Wine 10's `NtUserSetCursorPos` only calls the display driver
when its cached previous position differs from the requested position. If the
input thread asks for the center before the window thread consumes XTEST motion,
Wine can still consider the pointer centered, so the Xvnc pointer remains offset.

Relevant primary sources:

- [EQW game input](https://github.com/CoastalRedwood/eqw_takp/blob/v1.0.2/eqw_takp/game_input.cpp)
- [EQW DirectInput configuration](https://github.com/CoastalRedwood/eqw_takp/blob/v1.0.2/eqw_takp/dinput_manager.cpp)
- [Wine 10 cursor cache gate](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/win32u/input.c)
- [Wine 10 X11 warp and serial suppression](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/mouse.c)
- [Wine 10 server cursor update](https://github.com/wine-mirror/wine/blob/wine-10.0/server/queue.c)

The repair changes only EQW's existing center call under Wine: request a bounded
one-pixel intermediate position, then the actual center. This forces the final
display-driver warp through Wine's own path. The nudge uses final screen
coordinates after EQW's scaling and offsets; a right-edge center nudges left,
and tiny or out-of-bounds rectangles retain the original single call.

Wine grabs its root pointer with `owner_events=False` during the warp and tracks
the X request serial to discard warp motion. Its server cursor setter queues
the synthesized window movement directly, bypassing the low-level hardware-hook
path used by nonexclusive DirectInput. Original focus/right-button gates,
cursor restoration, signed Android deltas and the existing 15% TAKP gain remain
unchanged. Native Windows retains the original single `SetCursorPos` call.

## Verification

[Build run 38029612146](https://github.com/Russianranger/trasc-server-android/actions/runs/38029612146)
passed the open cursor fixture against the same SHA256-pinned Wine 10 WoW64 build
used by the client runtime and real Xvnc/XTEST input. The fixture deliberately
pauses the window pump to exercise the cache race; it contains no game code or
assets.

| Input sequence | Original actual X pointer offsets after center requests | Repaired behavior |
| --- | --- | --- |
| +20, +20, +20, −10 pixels horizontally | +20, +40, +60, +50 | Each request returns to center; −10 immediately produces a leftward offset. |
| Six mixed horizontal/vertical reversals | Not part of the baseline sequence | Every input produces its own signed offset, then returns to (400, 300). |

The C++ fixture also verifies both axes, native Windows passthrough, rectangle
bounds and final-call failure. Nineteen TAKP backend tests passed, including
case-preserving automatic upgrade, original backup preservation, idempotent
retry and refusal to replace custom helpers or damaged backups.

These establish the Wine/Xvnc failure mechanism and the repair in the open
fixture. Actual TAKP camera feel and rendering still require a Thor session.

## Build and upgrade

`scripts/prepare-takp-eqw.py` refuses any different upstream commit or original
`game_input.cpp` hash before applying the narrow patch. The Windows workflow
builds the original Release x86 solution. `scripts/record-takp-eqw.py` verifies
the resulting PE32 architecture and repair marker, then records the DLL hash,
source pin, patch hashes, patched source hash, build run and license hash. The
artifact includes the patched source and upstream license. The reviewed DLL
and receipt must be pinned in the client bundle before packaging the APK.

The Windows job in that run passed with no compiler warnings or errors. Its
compiled DLL SHA256 is
`b739dfe64b7f69be2ffebf13a1cf794bcfd9e37fe143a75134ca6359e60ef584`, from
launcher build recipe commit `f8fb21396f1b28a21dd6d0ae1bc120b85b6619db`.
The actual compiled bytes are pinned; deterministic rebuild identity has not
been established.

Before starting Wine, an existing managed TAKP client with the exact previous
official EQW helper is upgraded atomically. Its first original is saved at
`client/prefix/trasc-takp-camera-originals/eqw.original.dll`; repeated launches
leave that backup in place. A modified/custom EQW helper requires the explicit
Prepare transaction. Import and Prepare use the same pinned new helper.

This repair replaces the Windows EQW helper. The Android/native ARM components
and other TAKP helpers do not require rebuilding for this camera change.

## Device acceptance

Update the APK with the client stopped, then launch the existing TAKP client.
Check Look on with touch, controller and any external mouse: make a larger
movement right and a small movement left, then repeat vertically. The camera
should change direction with the reversed input. Check ordinary pointer input,
in-game menus, right-button drag, look-off restoration, focus changes and zoning.
If direction still persists, export fresh client logs and capture the input
device, look state and movement sequence. The helper logs
`TRASC_TAKP_WINE_RECENTER_V1` on its first Wine camera recenter.
