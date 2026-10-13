# TAKP right-stick capture recovery: 0.6.26

The 0.6.25 AYN Thor test confirmed existing-server startup, successful source
update/build/deployment and removal of the cleric's idle Yaulp loop. Its real
incremental build compiled only `player_bot.cpp.o`, then linked `zone`; the
operation took 55 seconds with two jobs, deployment 21 seconds and server
startup six seconds. Those startup seconds exclude client login/world entry.
Repeat no-work rebuilding and all-profile backup/model restoration remain
separate device acceptance checks.

## Actual camera evidence

The user identified the failed reproduction as the Thor right stick. The fresh
0.6.25 trace contains 57 game-consumer samples across approximately 14.3 seconds
of held Look. It shows relative format (flags 2 / axis mode 1), successful reads,
no buffered PEEK, event ages 3-34 ms and unchanged physical/focus gates. The
official diagnostic helper loaded natively. Twenty of 50 held clip snapshots
place the cursor outside Wine's reported one-pixel center rectangle.

Both buffered and polled values reach the game as repeated offsets, including
individual 77/78-pixel events. The Android controller caps ticks at 50 ms,
sensitivity at 2500 pixels/s and TAKP Look gain at 0.15; including fractional
remainder, its integer packet cannot exceed 19 pixels per axis. This supports
an offset introduced after normal stick generation, although packet-correlated
hardware telemetry is still absent.

Wine 10 `NtUserClipCursor` updates a cached server rectangle asynchronously.
Its X11 driver may acknowledge without grabbing when actual X focus is outside
the process, and virtual-desktop focus transitions can release a physical grab
without clearing the rectangle. The old `LookClip` trusts an unchanged cached
rectangle indefinitely. Core absolute MotionNotify may then be converted into
relative offsets against the cached center.

Primary source: [Wine cached clip](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/win32u/input.c),
[X11 capture](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/mouse.c),
[focus transitions](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/event.c),
[raw conversion](https://github.com/wine-mirror/wine/blob/wine-10.0/server/queue.c).

## Narrow correction

V3 observes `GetCursorPos` outside the clip lock, then checks the lifecycle
generation, physical button, foreground, visibility and existing ownership.
Only an observed escaped cursor permits a same-rectangle `ClipCursor` retry,
at most once per 250 ms. Initial asynchronous acquisition gets the same grace.
Failed retries are throttled and retain logical ownership rather than causing
a `SetCursorPos` fallback. Healthy capture introduces no repeated requests.

There is no focus stealing, release/reacquire cycle, ABS-mode conversion,
DirectInput draining, sensitivity change, renderer change or new server code.
Prior clipping and release/focus safeguards remain. Diagnostics add
`clip_repair count=... ok=...`; the helper marker is
`TRASC_TAKP_WINE_RAW_LOOK_V3`.

## Qualification

[Run 38349508008](https://github.com/Russianranger/trasc-server-android/actions/runs/38349508008)
passed both the MSVC x86 helper build and the pinned Wine 10/TigerVNC fixture.
The actual helper SHA-256 is
`875056a62d2df3c7434bf05d23d73186d6565d2bd5a14f2f53a58fa7d015bab3`.
Exact build/source and cursor receipts are bundled beside it.

The new fixture deliberately unmaps the physical one-pixel X confine window
without changing focus, RMB, cached rectangle or logical held state. Old
behavior stays escaped at `(401,300)` while claiming capture. V3 reasserts the
same rectangle once and restores `(400,300)`. Separate positive and negative
1/2-pixel axis/diagonal segments arrive exactly in both native DirectInput APIs;
idle drift is zero. Existing edge, cadence, burst, swapped-button and lifecycle
gates also passed. This qualifies that lost-capture recovery mechanism, not
the proprietary game's physical Thor camera result.

## Thor acceptance

Install the qualified 0.6.26/code75 APK as an update. Stop/relaunch the TAKP
client; the known 0.6.24/0.6.25 helper is upgraded automatically, preserving it
as `client/prefix/trasc-takp-camera-originals/eqw.0624.dll` and retaining earlier
originals. Changed/custom helpers refuse automatic replacement. No server
source update, compilation, database initialization, client reimport or prefix
reset is required for this camera pass. Retain the already working Yaulp server.

Keep renderer, CPU accuracy, inversion and sensitivity fixed. In first person,
enable Look and use only the right stick: right then a shorter left reversal;
left then right; up/down in both orders; diagonal reversals. Release the stick
to neutral and check drift. Test Look off/on, inventory/chat pointing and a
normal background/resume. Use manual start/stop, with no test countdown.

After a short reproduction, stop the client and export logs. Confirm the V3
helper hash/marker; retain `eqw-camera-diagnostics.log`, any `clip_repair` rows,
input directions, Look state and a short video if useful. If capture is healthy
there may be no repair rows. Missing rows alone do not establish success.
Persistent incorrect native X focus can still prevent recovery, and no device
camera success is claimed before this acceptance.

NPC visibility and Traditional StoneUI remain separate unresolved concerns.
