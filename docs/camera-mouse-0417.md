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

Update the verified APK in place with game and server stopped. Open the server runtime, compile `dinput8.dll` with the already imported source/SDK, then deploy it using the existing separate Deploy action. Leave the installed runtimes and imported client files in place. Enable camera-only recentering and relaunch.

Check free pointing at startup/server/character selection, held and toggled camera turns past a full revolution, return to inventory pointing, focus loss, and another server-select reconnect. If camera behavior is unsuitable, turn the checkbox off and relaunch; the adapter becomes inactive without reverting the confirmed reconnect fix.

## Validation status

Implementation commit `4d03e4c95cf17499cc5c508b265fe6a1527b0f9c`, workflow run `35332966690`. All 131 local Python tests and native/JVM checks pass. Microsoft v142 builds the actual patched upstream DLL and passes allocated-state checks. Android compilation, lint, preserved signing and browser tests pass. Direct ARM64 Wine, DXVK and PRoot fixtures verify relative movement plus free menu pointing before/after camera look. All seven jobs succeeded, including runtime/session roundtrips, direct/PRoot Software/DXVK/VirGL checks and preview publication. The public preview tag points to the tested implementation, and both release asset digests match the downloaded candidate.

Fixture polled movement with a one-pixel clip: 6,400 (software), 6,280 (DXVK), 6,320 (DXVK/PRoot) pixels. During camera recentering, another 1,480 / 1,440 / 1,360 pixels accumulate; menu-pointer recovery passes for all three. These are open fixtures, not actual EQ/Thor camera acceptance.

Released APK: 10,518,492 bytes, SHA256 `f27d9c7ede46db38694b11bec5ebff6171f228c61bbabd2d572de3817555fcd2`. APK v2 signature and content digest were independently verified; certificate remains `ff9c09cdc3e2404d1d7f72d61ce2f8651464f5e03dff340f70bd4df28c70e869`. All 35 bundled Python/header/UI assets match the tested sources. Phone options layout reviewed. Corresponding native source archive: 114,558,375 bytes, SHA256 `6fb4380f8b48a86326717b0af8912289123002f7f6331beb8a30f6d41e1431db`.

## Loading investigation

The latest session never reaches server selection. Earlier retained timings remain 69/88/86 seconds, dominated by 41/62/60 seconds of single-thread CPU work before display initialization. The supplied executable locates the `Check 1sa.` file-check/report sequence and following load paths, but a nearby log message does not identify which function consumes that whole interval. No loading speedup, checksum bypass, or speculative executable patch is part of this update. Runtime profiling of that interval remains the next performance step.

Static loading landmarks for later profiling: `0x561e50` authenticates; `0x51c2d0` calls it and then loads `spells_%s.txt` (`0x467190` constructor, virtual loader), `Resources\SpellRequirementAssociations.txt`, `racedata.txt`, and `AnimationSounds.txt` (`0x407c10`) before display init. These are candidate measurement boundaries, not measured hotspots.
