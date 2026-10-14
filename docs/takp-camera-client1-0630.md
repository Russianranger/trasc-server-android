# 0.6.30: exact Client1 recognition and focus-driven capture recovery

Published **0.6.30 / code 79** passed
[all five release gates](https://github.com/Russianranger/trasc-server-android/actions/runs/38593150423)
and independent verification of the actual public APK, signature, source
archive and native payload. See [release-status-0630.md](release-status-0630.md)
and [release-proof-0630.json](release-proof-0630.json) for hashes and receipts.
**Physical Thor camera usability remains unaccepted until a device retest.**

The 0.6.29 Thor capture identifies the exact rejected predicate. Its visible
1280×720 whole game window is titled `Client1`: XA_STRING, format 8, exactly
seven bytes, no terminal NUL or trailing data. Its `WM_CLASS` is the exact
22-byte `eqgame.exe\0eqgame.exe\0` pair. The pointer path is X root → Wine
desktop → game whole window → propertyless render child. The game PID agrees
with the sampled `eqgame.exe` process. The previous helper accepted only
`EqW-TAKP`, so it made zero repair requests even during held Look with native
focus at PointerRoot.

See [device-camera-0629.md](device-camera-0629.md) and its
[exact evidence JSON](device-camera-evidence-0629.json). Sampled native motion
remains signed and timely. Fresh incorrect game deltas instead follow escaped
cursor position relative to screen center. These observations do not justify
increasing stick sensitivity or draining an old input queue.

## Qualified correction and its limits

The V2 focus companion accepts only exact `EqW-TAKP` or `Client1` with the
exact process class, visible InputOutput geometry, physical RMB, a unique
matching ancestor in the pointer's actual path, and native focus None/
PointerRoot. It immediately rechecks those guards before changing focus.
Concrete foreign focus, hidden windows, unrelated titles/classes, case/
prefix/suffix/NUL/type/format differences and duplicate matching ancestors
remain refused. Disabled or unknown Wine capture settings prevent startup.
The companion never warps, grabs, injects input or writes X properties.

The stricter centered-focus test also exposed a capture gap. FocusOut
ungrabs the native pointer, while FocusIn alone need not restore it. Twelve
fresh +1 packets became +1 through +12, totaling 78. During continuous motion,
Wine 10 returns its shared cached cursor and queries the graphics driver's
physical pointer only after over 100 ms idle. A centered logical cursor can
therefore mask physical capture loss.

V4 reads a bounded private per-launch focus-success notification and submits
the SAME already-owned capture rectangle once. The event reader accepts only
an ordinary one-link file of at most 96 bytes, a current 32-hex launch token
and a fresh positive sequence, at most once per 20 ms. A refresh requires
physical Look, game foreground/visibility, the original clip generation
and continued ownership of the current rectangle. It adds no warp, input
drain, axis conversion, registry change or periodic forced reclip.
Sequence freshness is not event-age freshness: a paused hook can later
consume a same-launch event and refresh its currently owned clip once;
it cannot acquire a new or foreign clip.

[Native run 38590631222](https://github.com/Russianranger/trasc-server-android/actions/runs/38590631222)
passed three repair/notification/refresh sequences, 24 exact signed segments
including centered restore, 32 focus refusals and nine event-reader refusals.
The actual MSVC DLL, shared headers and successful CI artifacts match the APK.
The open PE32 consumer exercises those shared headers on the published ARM
runtime; the fixed-address proprietary game DLL cannot run in that fixture.
This is controlled qualification, not Thor camera acceptance.

## Installation and physical acceptance

1. Camp and stop clients/servers normally. Install the signed 0.6.30 APK in
   place without uninstalling. Reopen TAKP with the working Yaulp server
   deployment and the same input/graphics settings. No server source update,
   compilation/deployment, database import, client reimport, Prepare or
   prefix/runtime reset is needed.
2. Enter the saved character promptly. Within the first five minutes of
   client launch, enable Look. For about ten seconds, test short right/left,
   up/down and diagonal reversals, then return the stick to neutral. Reversal
   must change camera direction immediately; neutral must stop movement.
3. Turn Look off and check that the menu pointer moves freely. Turn Look on
   again, then background/resume and repeat the short reversal/neutral test.
4. Camp and stop normally, wait for stopped status, then use
   **Logs → Export log bundle**. Provide the fresh bundle and the observed
   reversal, neutral, menu-pointer and resume behavior.

Normal TAKP launch upgrades a known official V3 EQW helper. Its exact bytes
are saved as `client/prefix/trasc-takp-camera-originals/eqw.0626.dll`; the first
original and earlier backups remain. Changed/custom helpers and corrupt or
linked backups refuse replacement before any writes. Independent actual
old/new-DLL transaction checks cover successful upgrade, repeat no-work and
those refusal cases. All other client and registry files remain intact.
Existing profiles, character/bot data, client assets, Wine prefixes, installed
runtimes and settings must be preserved.

## Evidence needed from the fresh device bundle

| Bundle file | Measurement |
| --- | --- |
| `status.json`, `logs/client-state.json` | Actual app version, current helper hashes/state, launch identity, capture settings and final stopped child status. |
| `logs/client-takp-focus.log` | V2 marker; guarded focus before/candidate/after; repair success and `event_written`, sequence, errors and completion counts. |
| `client/current/eqw-camera-diagnostics.log` | V4 marker; matching `focus_clip_refresh` sequence/success/generation; physical Look/foreground/visibility, clip ownership, signed state/buffered deltas and ages. |
| `logs/client-pointer-packets.log` | Right-stick packet sequence, uptime, signed dx/dy, Look/button state, queue latency, drops and neutral input. |
| `logs/client-xinput.log` | Sampled XI2 signed motion, native focus, physical pointer position, RMB, time alignment and completion/drop counters. |
| `logs/client-takp-windows.log` | Exact title/class/property bytes, visibility, geometry and the actual pointer ancestry. |
| `logs/control.log`, `logs/world.log`, zone logs | Retained server start, saved-character entry/camp/reopen and absence of an unintended build/import/reset. |

If absent native focus occurs during held Look, expect a scoped V2
`focus_repair` with `event_written=true`, then one successful V4
`focus_clip_refresh` with the same sequence. Confirm actual cursor confinement,
matching signed input/game reversals, zero neutral drift, free menu pointer
after Look release and no foreign-focus takeover. A successful X request
alone does not establish usable physical camera movement.

The unchanged inspector's `exact_identity` field still describes its
historical EqW-only diagnostic matcher; false for `Client1` is expected.
Its 128 KiB bounded window log may end before five minutes. That diagnostic
cap is separate from input loss. Keep the test short and export after stopped
status so final helper exits are recorded.

Keep confirmed server/update/Yaulp results separate. NPC visibility,
Traditional StoneUI, the separate post-camp expired session key, external
all-profile backup/restore, saved-bot/full-character persistence, classic
skeleton visual acceptance/exact restoration and physical incremental/
no-work build receipts remain separate checks.
