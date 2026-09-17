# Controller and presentation milestone — 0.4.12

Camp investigation is shelved at the user's request. This change does not change server camp logic or database rules.

## Controller

The in-game gear menu now opens the controller editor. The Client tab and native editor share `client/controller.json`; returning from the game reloads the saved profile. Existing bindings stay intact. Applying an EQ preset fills the editor; Save persists it and Cancel leaves the saved profile intact.

Presets are Previous bindings, EQ adventure/hotbars, EQ spell gems, and EQ inventory/cursor. EQ presets use L1 as a held alternate layer. Adventure uses D-pad for hotbuttons 1–4, L1+A/B/X/Y for 5–8 and L1+D-pad for 9–12. Spell preset uses Alt+number for spell gems 1–8. Right stick moves the pointer; hold R2 for right-mouse camera steering. L2 clicks, Y targets nearest NPC (F8), R1 cycles targets (Tab), L3 toggles autorun (NumLock), R3 changes camera (F9), Select opens inventory, Start opens the gear controls. L1+R3 targets self, L1+R1 reverses target cycling, and L1+Select opens bags. Inventory preset prioritizes cursor clicks and slower pointer speed.

These are editable EQ default-key assumptions, not a parser for custom eqclient.ini binds. Layer choice and every normal/alternate binding are editable. Shift/Ctrl/Alt combinations are available. Layer transitions and overlapping chords reference-count their keyboard modifiers. Focus loss, dialog opening, controller removal and profile changes release held input. No game commands are automated.

## Existing device baseline

Read-only analysis of `logs-4182792564389881283.zip`, current session: 87 five-second samples, 58 with controls closed and more than 5 updates/s. Medians: 30.312 RFB updates/s, 30.306 new bitmap draws/s, 3.235 ms receive/update, 0.518 ms decode+apply/update, 0.058 ms Canvas submit/draw. This session includes loading and character selection; it is not a controlled gameplay benchmark. Canvas submission is not GPU completion or screen latency. The existing Xvnc cap was 30.

## Optional presentation prototype

Default remains Current display/RFB at 30 updates/s. Launch options add Native Surface and a separate 30/60 updates/s limit. All choices require relaunch and persist with the other client launch options. Existing Turnip drivers, DXVK, NPC compatibility and CPU settings are preserved.

Prototype path: X11 root image via MIT-SHM (XGetImage fallback) → private request-driven Unix socket → native RGBA conversion → ANativeWindow/SurfaceView. The XFixes cursor is composited into the image. Android does not request RFB pixel updates in this mode; its original RFB connection carries input only. Helper and Android transport failures return to the current RFB display. Surface destruction stops its reader; reconnecting does not rebuild the Wine prefix or restart the server.

This bypasses RFB pixel encoding/decoding and Java Bitmap/Canvas frame upload, **not X11 or Vulkan-to-CPU readback**. It is not zero-copy GPU presentation. Full-frame delivery may cost more bandwidth/power than RFB's changed rectangles, especially in static scenes. Keep it optional until Thor comparison establishes a benefit. One frame is requested at a time; there is no accumulating frame queue. Dimensions, stride, payload size, pixel format and alpha are checked. Socket mode is 0600; no new network listener is exposed. Linux helper is bundled with the APK, so no runtime reinstall or server/DLL rebuild is required.

Measurements remain in `logs/client-presentation.log` and exports. Current display adds separate pixel-conversion and Bitmap-apply times and raw bytes/s. Native Surface reports X capture time, request/receive elapsed time (includes pacing), Surface lock wait, native copy, Surface post, bytes/s, shared-memory usage, dimensions and post rate. Neither RFB update counts nor Surface posts measure game FPS or physical display completion. DXVK's FPS HUD remains the game-rendering comparison.

API references: [Android Native Window](https://developer.android.com/ndk/reference/group/a-native-window), [X11 MIT-SHM](https://xorg.freedesktop.org/archive/X11R7.7/doc/xextproto/shm.html).

## Validation and device comparison

Local checks: 118 Python tests, JVM controller/transport/session/audio tests, strict C frame bounds/color conversion checks, and JavaScript syntax. All seven jobs passed in [run35237303372](https://github.com/Russianranger/trasc-server-android/actions/runs/35237303372) for source `1bf596e7ac8d3ad50bd2b9640fa153adae794367`: native Linux/Android compilation, APK/lint/preserved signing, browser persistence/layers/presets, and real Wine software/DXVK/VirGL pixels through both transports under direct Linux and PRoot. All existing release gates passed. Independent APK signature/content verification and public release digest comparison are recorded in the handoff. Physical Thor Surface presentation, gamepad feel, overlays/touch, thermal behavior and speed remain device acceptance; do not claim them from host tests.

After updating in place, select an EQ preset, Save, and check walking, camera, target cycling, hotbuttons/spell gems and inventory. Open/cancel/save mappings from the gear menu while moving to verify inputs release. Close/reopen the display and verify saved bindings.

For performance, keep resolution, Turnip driver, CPU settings, scene and camera consistent. Allow shaders/loading to settle. Compare (1) Current display / 30, (2) Current display / 60, (3) Native Surface / 60 for around one minute each. Observe DXVK FPS, movement, colors, names, cursor, touch alignment, camera and inventory. Export Logs after the comparisons. Current/30 is the fallback. Return to it if native output or pacing is worse. Changing a display path requires only stopping/relaunching the client.

## Thor comparison — September 17, 2026

Read-only inspection of `logs-2976453518264923596.zip` confirms 0.4.12 and all three requested runs at 1280×720, fullscreen, Turnip 26.0.0, DXVK 2.5.3, Balanced, available CPU affinity, exact 0.4.2 NPC compatibility and native helpers. Native Surface remained active throughout all 79 samples with no presentation fallback. Xvnc reports zero RFB framebuffer updates in that run, confirming the input-only RFB connection. Android reported thermal status 0 and power saving off throughout all three sessions; this does not prove the absence of all clock or scheduler restrictions.

For a gameplay comparison, use each game log's completed `ReadyEnterWorld` marker plus ten seconds through the first disconnect, retaining five-second presentation samples with controls closed and the window focused. This excludes loading/character selection and menu use. All runs reached Greater Faydark; the logs do not establish identical movement or camera views. Values below are medians of those samples, not game FPS or physical screen-completion measurements.

| Run | UTC interval | Samples | New Bitmap draws / Surface posts per second | Pixel payload MB/s |
| --- | --- | ---: | ---: | ---: |
| Current / 30 | 15:36:39–15:38:09 | 18 | 30.13 | 61.47 |
| Current / 60 | 15:42:25–15:44:54 | 29 | 40.72 | 62.42 |
| Native Surface / 60 | 15:48:58–15:50:59 | 24 | 25.13 | 92.65 |

Current/60 received 47.89 RFB updates/s, with some updates coalesced before Bitmap drawing. Its median conversion/apply costs were 0.827/0.578 ms per update and Canvas submission 0.039 ms per draw. Native reported 5.289 ms X capture, 38.486 ms request/receive (including capture and any pacing), 0.407 ms Surface lock, 0.439 ms conversion/copy and 0.452 ms Surface post per frame. These independently calculated medians are not additive component percentiles. Native posts can repeat an unchanged game image; neither transport reveals actual DXVK game FPS in these logs.

Every native sample reported zero shared-memory frames, so this Thor run used XGetImage rather than the MIT-SHM capture exercised by CI. The current helper does not log why SHM setup was unavailable; do not claim a specific kernel/PRoot failure without further evidence. Source inspection identifies **720 payload send calls per 720p frame**, plus its header, before any partial-send retries. Gameplay thread deltas show the helper at a median **50.5% of one CPU core**, Xvnc at 14.9%; Current/60 Xvnc was 23.5% with no helper. These process samples exclude Android presentation and the external PRoot tracer, so they are not whole-device CPU totals. The timing, traffic and helper CPU cost make batched payload writes a concrete next experiment, not a proven fix yet.

**Conclusion and next work:** keep this device on Current display / 60 if it feels smoother; keep the shipped default at Current/30 and Native Surface experimental. Before another native comparison, batch contiguous frame payloads, add transfer/pacing/send-call and SHM-fallback diagnostics, and explicitly exercise the non-SHM capture path in real integration tests. Preserve the existing pixel/color/fullscreen/reconnect and direct/PRoot gates. No performance code change or new APK was made for this analysis.

All three game logs end with normal quits; no unhandled exception, stack overflow or renderer crash signature appeared, and the current/previous supervisor states end with `stop_request`. Existing libXcomposite, MIDI, gamma-ramp and Wine shutdown warnings recur across modes; the audio logs show playback and 2–4 cumulative underruns, not a new native-only audio failure. Historical app/runtime errors from earlier dates must not be presented as new 0.4.12 failures. The previously parked camp disconnect occurs in the comparison logs but was not reopened or patched. No controller profile or input trace is exported, so visual correctness and controller usability still need the user's observation.
