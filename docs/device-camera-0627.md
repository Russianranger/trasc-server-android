# 0.6.27 Thor camera evidence — October 13 evening

Physical camera acceptance **failed**: the user reports mouse look remains
weird/unwieldy. The diagnostic update did not change the V3 camera helper.
This report records an identified X focus mismatch and a supported next
candidate; it does not claim a completed camera correction.

`logs-6791455423678849935.zip` was exported at 02:04:06 UTC October 14 /
21:04:06 Chicago October 13. Its 757,059 bytes have SHA-256
`104bf1e57cad56f6d9e5dfcaaf51beff4128e44c10c05687f915d1b213cceda6`.
Exact logfile hashes, counts, timestamps and limitations are in
[device-camera-evidence-0627.json](device-camera-evidence-0627.json).

## Confirmed input path

The device reports 0.6.27/code76, the native V3 EQW helper with SHA-256
`875056a62d2df3c7434bf05d23d73186d6565d2bd5a14f2f53a58fa7d015bab3`,
a reused Wine prefix, 1280×720, Accurate CPU mode and Turnip 26.0.0.
The read-only registry report finds no capture override: GrabPointer uses
Wine's enabled default. XI2 2.2 is available with relative axes, master
pointer 2 and XTEST source pointer 4.

There are **754 held-look Android motion packets**, with a maximum of two
pixels per axis. All **71 sampled held XI2 records** exactly match the nearest
sent Android packet, with timestamp differences of 0–2 ms. The selected
sender rows have at most 7 ms queue delay, and zero queue/byte-limit drops.
This rules out accumulating Android-to-XTest delivery in the measured scope.

## X focus and Wine input disagree

All **40 native held-button pointer snapshots** show X focus **PointerRoot**
(X constant 1), rather than a Wine-owned X window. The physical pointer moves
through x=593–690 and y=264–423. Meanwhile EQW reports foreground, visible and
physical Look active, with cached clip `(640,360)-(641,361)`.

Wine 10's `is_current_process_focused()` requires an X focus window registered
in the current Wine process. PointerRoot fails that test.
`grab_clipping_window()` then returns success without grabbing. This explains
why **111 accepted clip repairs** over 39.918 seconds leave **61 of 94** sampled
held cursor positions escaped. Additional identical ClipCursor requests cannot
repair the observed native focus condition.

The direction error is measurable before the camera renderer. Android packet
306 sends **(-1,0)** at uptime 198566745 ms. The escaped pointer is `(657,264)`
and the cached center `(640,360)`. A fresh buffered event at 198566746 ms, read
11 ms later, yields **(+16,-96)**; polled state and the game's consumer agree.
That result equals `(657-1,264)-(640,360)`: requested left movement became
right movement plus unrequested vertical movement.

Wine's core absolute MotionNotify path converts to raw REL movement against
the shared clipped cursor. It can therefore feed cursor-to-center offsets to
DirectInput even though the device format correctly reports REL. Held buffer
event ages are 0–27 ms, with no PEEK; individual last-axis values reach
x=-48…51 and y=-96…45 despite Android's two-pixel maximum. The old 19.108-second
startup event has Look off and is outside this reproduction.

## Supported next candidate and acceptance

Restore native X focus to the verified active Wine game window within the
foreground client lifecycle. Respect backgrounding, menus, Look release and
window ownership. Then verify actual pointer confinement and exact signed
input, including the PointerRoot failure control, in the pinned ARM64
Box64/Wine/TigerVNC runtime before the next physical Thor test. Do not claim
success from a focus API or cached clip alone.

Native XI events are sampled, and there is no synchronized camera video or
complete dump of Wine's internal raw-event selection and core MotionNotify.
The native observer has no terminal end row, but covers the held reproduction.
The final saved-position restoration is not a 657-pixel camera movement.
Actual visual reversal latency and the proposed correction's physical success
remain unmeasured.

Primary Wine 10 sources:
[native X focus gate](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/event.c),
[grab and motion paths](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/mouse.c),
[shared cursor and clipping](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/win32u/input.c),
[core-to-raw conversion](https://github.com/wine-mirror/wine/blob/wine-10.0/server/queue.c).

Retain the working TAKP server/Yaulp deployment, databases, characters, bots,
client assets, Wine prefixes, installed runtimes and settings. NPC visibility,
Traditional StoneUI, all-profile reopening, external backup/model restoration
and physical no-work/object-retention measurements remain separate checks.
