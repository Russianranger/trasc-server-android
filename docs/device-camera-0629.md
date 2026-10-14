# 0.6.29 Thor camera evidence — October 14 morning

Physical camera acceptance **failed**: the user reports “mouse still weird
movement.” The read-only window probe identifies the exact game-title mismatch
that prevented the 0.6.28 focus companion from making any request. Focus repair
has still not been attempted on this physical game; collection success does
not establish a camera fix.

`logs-214347772381917203.zip` was exported at **14:42:48.486879 UTC /
09:42:48.486879 Chicago, October 14, 2026**. Its 742,058 bytes have SHA-256
`9c46b6b579eae944a027787b5b78fbdc4c0cab6498a559ca725a375e388e49f7`.
Exact hashes, rows, counts and scope are recorded in
[device-camera-evidence-0629.json](device-camera-evidence-0629.json).

## The real game window is named Client1

The device reports 0.6.29 on AYN Thor/Android 13. The unchanged qualified focus
companion runs as PID 8016 with SHA-256
`90dda77cb0b0fe1d18d4fa7b39bedda7dad67af6c342d7b23c74d0129f666865`.
The new read-only inspector runs as PID 8017 with SHA-256
`e1df07509f870d35f8feea87e64f20101597bd14dbc5ed0632335906b312d21c`.

The first held snapshot is inspector `t_ms=87154`; its window records begin
at 87158. The real game ancestor is window **20971521**. Its properties are:

| Property | Type / format | Count / bytes after | Exact value |
| --- | --- | --- | --- |
| `WM_NAME` | `STRING` / 8 | 7 / 0 | `Client1` |
| `WM_CLASS` | `STRING` / 8 | 22 / 0 | `eqgame.exe\0eqgame.exe\0` |
| `_NET_WM_NAME` | `UTF8_STRING` / 8 | 7 / 0 | `Client1` |

The title has no terminal NUL. Its hex bytes are `436c69656e7431`. The class
bytes are exactly `657167616d652e65786500657167616d652e65786500`, so the existing
class predicate passes. The game is an InputOutput window, IsViewable
(`map_state=2`), at `(0,0)`, 1280×720. Its `_NET_WM_PID` is **8047**, independently
corroborated by the `eqgame.exe` main thread in `client-threads.log`.

The held pointer's descendant path is root **1305** → Wine desktop
**14680068** → game **20971521** → render child **18874978**. All four windows
are viewable and 1280×720 at `(0,0)`. The desktop has title
`TRASC - Wine Desktop`, class `explorer.exe\0explorer.exe\0`, PID 8031.
The render child has no title, class or PID property; its outer game ancestor
carries the identity. No global search or desktop target is required.

There are **20 held game/window samples**, all with the same game identity
and native focus PointerRoot. Nineteen pointer paths complete normally with
four windows; the final path is truncated only by the log byte cap. The
one bounded candidate scan reads all 19 tree nodes, below its 128-node bound.
It finds the game and two other `eqgame.exe` class windows: an unmapped 1×1
`Default IME` window and an unmapped 1×1 empty-title window. Neither is eligible
for the visible game predicate.

The focus helper requires exact `WM_NAME=EqW-TAKP`. Actual `WM_NAME=Client1`
is therefore the rejecting predicate. Both held periods still log
`no_exact_visible_game_under_pointer`, focus=1, Button3Mask=1024, candidate=0.
The terminal receipt is **attempts=0, successes=0, xerrors=0**.

The smallest supported correction is to accept the exact additional
**`Client1`** title while retaining exact `eqgame.exe` class, viewability,
Button3, actual pointer-descendant path, missing native focus and immediate
pre-request rechecks. Retain exact legacy `EqW-TAKP`. The physical evidence
does not justify arbitrary `Client*` matching, class-only selection, a global
focus search, a desktop focus target or overriding another concrete focus.
The observed PID corroborates ownership; the current helper does not enforce
a PID predicate. A newly qualified helper still requires physical validation.

## Fresh signed native input still diverges at the game

The sender records **1,404 held Android motion packets**, at most two pixels
per axis, selected queue delay at most 8 ms, and zero input drops. All **130
sampled held XI2 events** match their corresponding signed Android packets,
with 0–5 ms timestamp differences. All **35 held native snapshots** show
PointerRoot focus, x=523…757 and y=275…419; none has an X error.

At uptime **203416271 ms**, the native pointer is `(609,323)` and the cached
Wine clip center is `(640,360)`. Packet 272 sends rightward `(+1,0)` at
203416533 ms; sampled XI2 preserves `(+1,0)` at 203416534 ms. The game consumer
seven milliseconds later yields **(-30,-37)**:

`(609 + 1, 323) - (640, 360) = (-30, -37)`

Packets 272–280 through 203416662 ms total **(+14,-2)**. A buffered event
stamped 203416663 ms, read three milliseconds later, instead reports
**(-17,-39)**:

`(609 + 14, 323 - 2) - (640, 360) = (-17, -39)`

Fresh rightward movement becomes larger leftward cursor-to-center offsets,
with unrequested vertical movement. Of 67 fresh paired-axis DI buffers with
same-timestamp Android correspondence, 66 have a preceding native snapshot in
the same continuous hold. All 66 equal pointer position plus intervening
packets minus clip center; 32 oppose signed input on at least one axis. The
excluded event at 203444813 ms crosses release/repress, when saved-pointer
restoration changes the origin. This is not a complete motion capture.

EQW records **60 accepted clip retries** over 37.006 seconds, but **32 of 93**
held clip samples escape. There are 122 held buffer samples, 92 nonempty;
event ages are 1–20 ms and flags are 0/no PEEK. The observer's raw sampling
and lack of synchronized video limit the analysis: actual visible reversal
latency remains unmeasured. Increasing controller sensitivity or draining an
old input queue does not address these measured fresh offset values.

## Bounds, teardown and preservation

The inspector ends normally at **106.500 seconds** because it reaches its
128 KiB byte budget. The complete file is 129,113 bytes, has zero X errors and
reports **two dropped diagnostic records**. These are bounded output records,
not dropped pointer packets. Twenty `WM_NAME`/`WM_CLASS` samples and nineteen
`_NET_WM_NAME` samples identify the target sufficiently; the later held phase
starting around 116 seconds is absent from this inspector log.

The native observer ends by signal at 198.775 seconds with zero drops. Its
five X errors occur after game teardown (first affected snapshot at
196.547 seconds); held snapshots and the focus helper remain error-free.
The export occurs while status says “Stopping Wine and the client display…”.
It still contains `launch_requested` and a running focus-child state, although
the focus end record precedes export by about 1.3 seconds. This transitional
snapshot does not prove final state refresh failed.

The existing TAKP server starts in **six seconds**, with no new source update,
build, deployment or database initialization in this launch. The same saved
character ID 4 enters Paineel at 14:40:28 UTC and camps at 14:42:14 UTC after a
106-second connection. The transport receipt records `ServerCloseRequested`
and disposition `camp`. Prefix state is `reuse`; the V3 EQW helper remains
current, unchanged and loaded native. Registry capture settings are empty,
so GrabPointer uses Wine's enabled default. Recorded Android exits precede
this launch; no current native client crash record is identified.

This supports character continuity and normal camp, not a complete inventory,
saved-bot, later-reopen or all-profile acceptance. Retain the previously
user-confirmed working Yaulp deployment; this camera correction requires no
server source rebuild, deployment, database replacement or runtime reset.
No new Yaulp qualification, external all-profile backup/restore, classic
skeleton enable/revert checksum verification or physical no-work/object-retention
measurement is established by this camera bundle.

## Required next physical gate

The qualified correction must identify the exact `Client1` game ancestor and
record a successful `focus_repair` while Look is held. Fresh native snapshots
must then show concrete game focus and its client pointer. Test right-stick
left/right/up/down reversals, return to neutral, Look off/menu behavior and
normal camp/reopen. Compare signed Android packets, XI2 samples, fresh game
deltas, cursor containment and clip-retry counts; a successful software fixture
cannot establish a usable physical camera.

Keep **camera acceptance pending** for the next release until those measurements
and the user's visual result agree. NPC visibility and Traditional StoneUI
remain separate unresolved physical checks. Preserve databases, characters,
bots, client assets, Wine prefixes, installed runtimes and settings throughout.
