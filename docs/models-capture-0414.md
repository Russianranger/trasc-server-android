# 0.4.14: game settings, classic NPC shortcut, capture and relative input

The user authorized this milestone after staging an eqclient.ini and reporting power drain and mouse-look stopping at desktop boundaries. Camp remains parked. Uploaded INI is a schema/reference only; it is not shipped or copied over the installed client.

## Game settings

Client → Game settings · eqclient.ini reads the installed file. Open the server runtime to load/save. Classic and Luclin presets modify only player model flags; individual race/gender, elementals, armor and social-animation controls are available. The advanced sections expose existing INI values, with a search. Launcher-controlled fullscreen/resolution fields are read-only. Existing CPU-affinity overrides still apply. Stop the game before saving; model changes require relaunch.

Only edited values change. A SHA256 revision rejects stale edits. Unknown added keys, repeated keys, multiline values, unsafe paths and UTF-16 files are rejected. BOM/legacy bytes and unrelated lines are preserved. Original and previous files are retained under backups/client-settings and included in complete session backups. Vah Shir has no pre-Luclin player model; that race is retained in the classic preset.

Gear → Toggle classic NPC models (#tim) opens command entry with slash, selects its contents, types exactly #tim and submits. It cancels if focus/menu state changes before submission and suspends controller input while doing so. Use in world, with game chat available; the game response determines whether the server accepted it. No automatic login command or server/database rule change.

## Presentation and input

The device's 0.4.13 log bundle logs-284004282866526252.zip confirms Native/60 delivered 59.7 Surface submissions/sec in Greater Faydark versus25.1 previously. Batching uses2 sends/frame. Capture remained XGetImage because shmget returned ENOSYS38. These are display submissions, not unique rendered game frames.

Client PRoot now enables its bundled System V IPC emulation via --sysvipc. The pinned allocator is patched to prefer memfd on both Android and Linux, retaining ashmem/temporary-file fallbacks. CI uses a short private helper directory to respect the 108-byte Unix socket path limit; the Android app-private temporary path already fits. Real Wine integration runs also enable it and require successful shared-memory capture under PRoot. XGetImage remains a tested fallback. XDamage/cursor events prevent captures when unchanged; a2-second capture backstop preserves recovery. Exact pixel comparison suppresses identical images even when a game keeps presenting them. An unchanged32-byte response retains the current Android Surface without allocating/copying/posting pixels. Capture/skip/duplicate counters distinguish reduced work from a stopped game. DXVK HUD updates and animated scenes legitimately produce new frames; turn HUD off for idle-power comparisons. Native remains optional, Current/30 remains default.

A private XTest input channel carries relative mouse deltas and held buttons; RFB continues to carry keyboard input and display fallback. Controller movement no longer accumulates an absolute position that clamps at screen edges. Touch remains absolute. Gear → Capture external mouse requests Android pointer capture for a physical mouse; Android Back releases it. A missing relative helper falls back to the existing absolute path. The test probe exercises actual polled Windows DirectInput movement while the OS cursor is clipped to a single pixel, not merely Java-side counters.

## Validation and delivery

Local:124 Python tests, JVM archive/controller/relative input checks, strict C frame/transfer tests and JavaScript syntax checks pass. Local Chromium is unavailable; browser coverage runs in CI. Full native helper build, real Wine direct/PRoot tests, Android lint/signing and APK verification are pending. No Thor shared-memory, power or physical mouse-look improvement is claimed before device testing.

Update in place after stopping game/runtime; no compiler/server rebuild, runtime reinstall or client reimport is intended. Keep the existing installed runtimes. Prior0.4.13 GitHub publication was blocked by repeated HTTP500 archive uploads; do not assume public preview is current. Preserve signing identity and all existing release gates.
