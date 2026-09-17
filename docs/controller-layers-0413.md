# 0.4.13: controller layers, optional DXVK HUD and batched presentation

The user authorized these changes after confirming that 0.4.12 Native Surface looked correct and the presets worked. Native/60 showed higher DXVK FPS, but perceived smoothness was between Current/30 and Current/60. The earlier log comparison measured delivery at about 25 Surface posts/sec; game FPS and display delivery are different measurements. Camp remains parked.

## Controller setup

New installations use **Thor defaults / cycling**. Existing saved mappings are preserved and migrated, including the old held modifier and alternate bindings. To use the requested new layout on an existing installation, open **Client → Controller mappings**, or **in-game gear → Controller mappings**, choose **Thor defaults / cycling → Apply preset → Save**. Applying a preset replaces the editor draft; Save commits it.

The Main layer is exactly:

| Controller | Keyboard/mouse |
| --- | --- |
| A | F |
| X / Y / B | 1 / 2 / 3 |
| RB / LB | Left click / Right click |
| LT | Next layer |
| RT | Tab |
| D-pad Up / Right / Down / Left | 4 / 5 / 6 / 7 |
| Left stick | W / A / S / D |
| Right stick | Mouse movement |
| Select / Start | Esc / I |
| Left / Right stick press | Home / C |

Tap LT to cycle **Main → Hotbar 2 → Spells → Inventory → Main**. Releasing LT keeps the selected layer; holding it does not repeatedly advance. The selected layer is retained when opening/closing the gear menu and resets to Main when the controller profile is reloaded or the client screen is reopened.

All four layers keep movement, pointer and LT cycling through inheritance. Hotbar 2 changes X/Y/B to 8/9/0 and D-pad Up/Right to minus/equals. Spells changes X/Y/B and D-pad Up/Right/Down/Left to Alt+1 through Alt+7. Inventory changes X to Shift+B, Y to I, B to Esc and D-pad Up/Down to scrolling. These are editable starting points; the game must have corresponding keyboard bindings.

Both editors support **one to six named layers**, add/remove/rename, and independent bindings. Inherit means use the first layer's binding. The first layer cannot be removed. Bind **Next layer**, **Previous layer**, **Go to: [name]** or **Hold: [name]** to any button. Cycling wraps. A held override returns to the selected layer on release; with multiple held overrides, the most recently pressed is active and releasing it restores the previous held override. Changing the selected layer during an override takes effect when that override is released.

Layer changes release the old keyboard/mouse outputs before applying held inputs in the new layer. A translucent, non-interactive top-center label shows the layer number/name for 1.5 seconds, then fades over 0.25 seconds. Its background is about 16% opaque and its text about 70% opaque. The gear menu also shows the active layer.

## DXVK HUD

**Client → Graphics → Show DXVK FPS / stats** controls the next Turnip/DXVK launch and is saved with launch options. Stop and relaunch the client after changing it. Default remains on; off sets `DXVK_HUD=0`.

DXVK 2.5.3 reads `DXVK_HUD` in the `HudItemSet` constructor; the normal update loop does not reload it. This was checked against the [bundled version's source](https://github.com/doitsujin/dxvk/blob/v2.5.3/src/dxvk/hud/dxvk_hud_item.cpp). There is no misleading live gear toggle. The user explicitly accepted launcher-only if changing it in-game was unavailable. This does not control the launcher's separate display-metrics gear overlay.

## Presentation changes and limits

Current/30 remains the shipped default. Native Surface remains optional, with the existing fallback. The X11 helper now sends a packed 720p frame as one payload instead of 720 row sends. Partial writes and interruptions are handled. Padded rows use one reusable packing buffer; ordinary packed rows require no new pixel copy. The frame protocol and color format are unchanged. X11 readback and Android Surface copying remain: this is not zero-copy.

The helper records capture, send and pacing time, actual send-call count and bytes/frame every five seconds and on consumer disconnect. It also logs why MIT-SHM was unavailable. A diagnostic `--no-shm` flag forces XGetImage for integration tests; normal device launches still try SHM first. The previous Thor comparison used XGetImage throughout, so testing only CI's successful SHM path was insufficient.

The real Wine integration gate now tests both capture modes, color correctness, 1280×720 fullscreen coverage, private socket permissions and reconnect, including direct and PRoot Software/DXVK/VirGL runs. The forced XGetImage case checks transfer statistics and batched send calls. DXVK integration also launches with the HUD off. These CI software-rendering checks cannot prove Android Surface appearance, Thor performance, heat or controller feel.

Local validation: 119 Python tests; host JVM controller/RFB/management checks; strict C frame/color and transfer tests including padded rows, short writes, EINTR and EPIPE; JavaScript syntax checks. Full Android/browser/native integration and release validation are pending until recorded in HANDOFF.

## Device check

Update in place with client/runtime stopped, reopen the runtime and apply/save the new Thor preset once. No server/DLL rebuild, database change, client reimport, prefix repair or Mac tooling is required.

Check Main controls, cycle all four layers, edit/save one mapping, and check the top-center label. If using held overrides, check release restores the prior selection. Turn the DXVK HUD off in Client and relaunch to verify it disappears.

For the next performance comparison, use the same warmed-up scene/settings at **Current/60** and **Native Surface/60**, approximately one minute each. Keep the HUD setting identical for both (on if reading game FPS), close the gear overlay, and export Logs afterward. Report visual smoothness as well as game FPS. Batching is implemented, but a Thor improvement is not yet established.
