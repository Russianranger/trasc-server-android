# Camera-only recentering, 0.4.17

The September 18 device bundle `logs-4844374177188300957.zip` confirms `mouse_warp=force` with the working source-built DLL, normal logging, and only startup in the latest game log. The user reports a centered but immovable menu pointer. This is a different failure from the patcher DLL's earlier reconnect overflow: always-on Wine warping is unsuitable for EQ's menus.

## Immediate recovery

In 0.4.16, turn off Client → Graphics, audio & launch options → Recenter mouse for camera look, stop the client, and launch it again. No prefix repair or runtime reinstall is needed.

## Replacement

0.4.17 resets the game's per-application Wine `MouseWarpOverride` to `default` on every launch, even if the saved checkbox is still on. The checkbox now enables an optional adapter in a newly compiled source DLL. An older DLL or an unrecognized executable retains normal pointing and the launcher explains why the adapter is inactive.

The adapter runs after a successful relative mouse `GetDeviceState` call. It leaves returned deltas, buttons, acquisition, cooperative level, visibility and clipping alone. It recenters only with in-world state, held or toggled camera look, a hidden cursor, and a foreground window owned by the game process. It stops immediately when those conditions cease. It calls Wine's Win32 cursor API inside the game process; there is no external warp loop or game window-procedure hook.

The launcher requires the supplied executable's complete SHA256:
`4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3` (8,774,656 bytes).
The DLL also checks PE32, timestamp `0x518de58f` and image size `0x12c3000`. Other executables are intentionally unsupported pending inspection. No uploaded game binary is committed or redistributed.

Static inspection establishes the relevant paths for this exact binary:

- `0x5f9e30` reads buffered DirectInput, then `DIMOUSESTATE2`; relative X/Y feed the camera at `0x517f50` and related handlers.
- RVA `0x9df702` is the toggle flag. The alternate camera object at RVA `0xa63980` has its held-look flag at offset 8 (`0x556d70`).
- The game object at RVA `0xa67ccc` has game state at offset `0x5c8`; camera handlers test state 5 before hiding/restoring the cursor.
- Pointer reads fail closed if objects are absent or unreadable. No game memory is written.

The compiler overlays only the two ANSI/Unicode DirectInput forwarding source files in its build directory. Imported source stays intact; existing build/deploy backup behavior remains. The output records adapter identity and header checksum. Compilation rejects a changed wrapper instead of guessing where to inject code.

## Installation and device checks

After the release passes its gates, update the APK in place with game and server stopped. Open the server runtime, compile `dinput8.dll` with the already imported source/SDK, then deploy it using the existing separate Deploy action. Leave the installed runtimes and imported client files in place. Enable camera-only recentering and relaunch.

Check free pointing at startup/server/character selection, held and toggled camera turns past a full revolution, return to inventory pointing, focus loss, and another server-select reconnect. If camera behavior is unsuitable, turn the checkbox off and relaunch; the adapter becomes inactive without reverting the confirmed reconnect fix.

## Validation status

Local Python and native/JVM checks pass. Cloud validation is pending at this commit. Added checks cover saved force-setting reset, old/new DLL and executable gating, unchanged source overlays, Microsoft-compiled held/toggled/game-state handling, plus real Wine relative movement and free menu pointing before/after camera recentering. These fixtures cannot establish actual EQ/Thor camera feel; device acceptance remains required.

## Loading investigation

The latest session never reaches server selection. Earlier retained timings remain 69/88/86 seconds, dominated by 41/62/60 seconds of single-thread CPU work before display initialization. The supplied executable locates the `Check 1sa.` file-check/report sequence and following load paths, but a nearby log message does not identify which function consumes that whole interval. No loading speedup, checksum bypass, or speculative executable patch is part of this update. Runtime profiling of that interval remains the next performance step.
