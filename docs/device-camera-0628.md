# 0.6.28 Thor camera evidence — October 13 evening

Physical camera acceptance **failed**: the user still reports weird,
incorrect mouse-look behavior. The qualified focus companion ran, but its
discovery guard blocked every repair before an XSetInputFocus request.
This is not evidence that an attempted focus request failed.

`logs-6030031043376332005.zip` was exported at 02:51:10 UTC October 14 /
21:51:10 Chicago October 13. Its 732,562 bytes have SHA-256
`5a36f20480340a0c0beb1143002c70a9dc51879a3e875d2aef9825d754da1fed`.
Exact logfile hashes, timestamps and counts are recorded in
[device-camera-evidence-0628.json](device-camera-evidence-0628.json).

## What actually ran

The device reports 0.6.28/code77, the unchanged native V3 EQW helper, a reused
Wine prefix and the expected qualified focus companion SHA-256
`90dda77cb0b0fe1d18d4fa7b39bedda7dad67af6c342d7b23c74d0129f666865`.
Its terminal receipt is **attempts=0, successes=0, xerrors=0**. During both
held-Look periods it reports `no_exact_visible_game_under_pointer`, with
**candidate=0**, physical right button held and native focus PointerRoot.
The log does not identify which exact title, class, visibility or hierarchy
requirement rejected the real game. That guard mismatch remains unknown;
do not disable or broaden known strict checks based on a guessed identity.

The registry report still finds no capture override: GrabPointer uses Wine's
enabled default. XI2 2.2, master pointer 2, XTEST source 4 and relative valuators
remain valid. All **31 held native snapshots** retain PointerRoot focus.

## The input divergence is still downstream of native delivery

There are **1,230 held Android motion packets**, at most three pixels per axis.
All **113 sampled held XI2 records** match their sent Android packet exactly,
with timestamp differences of 0–3 ms. The selected sender rows have at most
5 ms queue delay and zero queue/byte-limit drops.

At uptime **200808140 ms**, the native pointer is `(719,326)` and the cached
Wine clip center is `(640,360)`. Packets 426–430 send leftward movements
`(-1,0), (-1,0), (-2,0), (-1,0), (-2,0)`, totaling **(-7,0)**. The sampled
native event for packet 426 preserves `(-1,0)`. A buffered game event stamped
200808217 ms, read 10 ms later, instead yields **(+72,-34)**:

`(719 - 7, 326) - (640, 360) = (72, -34)`

The next two packets move three pixels further left; the game consumer at
200808259 ms yields **(+69,-34)**. Requested left movement remains rightward
and contains unrequested vertical movement. Fresh values equal the escaped
cursor-to-center offset, consistent with Wine's core MotionNotify-to-REL path.

EQW records **52 accepted clip retries** over 34.010 seconds, but **24 of 83**
sampled held cursor positions escape. All held samples report foreground,
visible and physical Look active. The 78 nonempty held buffer reads have
event ages **0–21 ms**, flags 0/no PEEK, with individual values x=-78…102 and
y=-52…250. The old 19.033-second startup event has Look off and is outside this
reproduction. ABS conversion, queue draining and another identical clip retry
do not address the measured failure.

## Lifecycle and scope

The existing TAKP server starts in six seconds without another source update,
build, deployment or database initialization. The existing character enters
Paineel and the zone logs a camp at 02:50:57 UTC after a 109-second connection.
No current native client crash record was identified. Recorded Android app
exits precede this launch; the input trace ends with device unacquire.
This supports character continuity, not full inventory, bot or all-profile
reopen acceptance.

The native observer ends by signal with zero log drops. Its five X errors are
recorded around final window teardown; held snapshots and the focus companion
show zero X errors. Native raw events are sampled, and there is no synchronized
camera video or rejected-window identity/path dump. Actual visual reversal
latency remains unmeasured.

## Next measurement

The planned **0.6.29 read-only window-layout probe** will record the rejected
pointer path, bounded title/class properties, map state, geometry and ownership
evidence. It retains strict focus checks. This is a diagnostic update, not a
claimed camera fix; a later correction must be qualified and tested on Thor.

Primary Wine 10 sources:
[native X focus gate](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/event.c),
[grab and motion paths](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/winex11.drv/mouse.c),
[core-to-raw conversion](https://github.com/wine-mirror/wine/blob/wine-10.0/server/queue.c).

Retain the working server/Yaulp deployment, databases, characters, bots,
client assets, Wine prefixes, installed runtimes and settings. NPC visibility,
Traditional StoneUI, all-profile reopening, external backup/model restoration
and physical no-work/object-retention measurements remain separate checks.
