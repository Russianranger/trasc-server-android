# 0.6.26 Thor camera evidence — October 13 evening

The new bundle `logs-836710138545428717.zip` was exported at
23:12:54 UTC / 18:12:54 Chicago. Exact metadata and scope are in
[device-camera-evidence-0626.json](device-camera-evidence-0626.json).

## Confirmed device results

0.6.26/code75 and the intended V3 helper actually ran. The client reports an
upgrade from the official prior helper to SHA-256
`875056a62d2df3c7434bf05d23d73186d6565d2bd5a14f2f53a58fa7d015bab3`;
native module loading and the V3 trace agree. The Wine prefix was reused.
Retained DLL originals are reported, but their bytes are not in this bundle.

The existing server started successfully, and the previously saved character's
world entry appears in the current session. No new source/build/deploy,
database initialization or client reimport appears after this start.
This supports continued startup/character retention; complete inventory, bots
and all-profile reopen acceptance are not established.

## Camera confinement remains unresolved

The recovery code ran **48 times**, with every call reporting `ok=1`, over
20.36 seconds. Retries respected the 250 ms lower bound. Nevertheless,
**36 of 60 held samples** placed the queried cursor outside the reported
`(640,360)-(641,361)` clip, while foreground, visibility and physical Look
remained active. Some escaped positions persisted across multiple accepted
requests. API success therefore does not establish physical confinement.

DirectInput remains REL (flags2/axis_mode1). During Look, 35 nonempty sampled
buffer reads consumed events without PEEK; oldest ages were 1–25 ms. Large
individual offsets remain: 34 of those reads include a last axis value over
19 pixels, with a maximum of 92. These are individual event values, not just
multi-event sums. A 19.238-second old event occurred during startup with Look
off and does not establish held-look backlog. Releasing Look restores the
full clip.

The user supplied logs without a description of the new camera behavior.
Recorded input signs change, but intended stick directions and camera frames
are absent. Keep actual reversal acceptance unconfirmed. The confinement
invariant failed on this device; do not label 0.6.26 camera acceptance passed
because the host fixture or `ClipCursor` calls succeeded.

## What the next investigation must distinguish

Wine's shared cursor can stay clamped while a later graphics-driver query
returns the actual escaped X pointer. Wine's core absolute MotionNotify path
can also produce REL cursor-to-center offsets, so REL format alone does not
prove true signed XInput2 movement. Accepted clipping can hide disabled
GrabPointer, a skipped/refused X grab, wrong master pointer or missing usable
XI2 raw events. These remain hypotheses, not an identified complete root cause.

Primary Wine10 sources:
[shared cursor and clipping](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/win32u/input.c),
[X pointer/raw events](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/mouse.c),
[core-to-raw conversion](https://github.com/wine-mirror/wine/blob/wine-10.0/server/queue.c).

Read the preserved global/per-eqgame.exe GrabPointer values before changing
them. Pair short known signed XTest movements with X focus/window ownership,
XI2 client/master/source IDs and valuators, core and raw events, XQueryPointer
and DirectInput output. Qualify against the actual Box64/Bookworm/TigerVNC
runtime path as well as native-host Wine. Device display is TigerVNC1.12.0;
the previous host fixture is a separate environment.

Do not respond with another blind same-rectangle retry, ABS conversion or
queue draining. Retain the working server and Yaulp deployment. NPC visibility,
Traditional StoneUI, full bot/character persistence, external checkpoint,
classic model restoration and physical no-work rebuild remain separate checks.
This follow-up changes documentation only; no new APK/native build or runtime
replacement is needed to record the evidence.
