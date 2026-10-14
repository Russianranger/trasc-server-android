# 0.6.30: recognize the physical TAKP game window

Source candidate 0.6.30/code79. Native and APK qualification are pending.
Physical camera usability remains unaccepted.

The 0.6.29 Thor diagnostic capture identifies the exact rejected predicate.
Its visible 1280×720 whole game window is titled `Client1`, with XA_STRING,
format8 and exactly seven bytes, no terminal NUL or trailing data. Its
`WM_CLASS` is the exact22-byte `eqgame.exe\0eqgame.exe\0` pair. The path is
X root → Wine desktop → game whole window → propertyless render child.
The game PID agrees with the sampled `eqgame.exe` process. The previous
helper accepted only `EqW-TAKP`, so it made zero repair requests even during
held Look with native focus at PointerRoot.

See [device-camera-0629.md](device-camera-0629.md) and the exact source hashes
and measurements in [device-camera-evidence-0629.json](device-camera-evidence-0629.json).
Native sampled motion remains signed and timely. Fresh incorrect game deltas
instead follow escaped cursor position relative to screen center. This is
not evidence for increasing stick gain or draining an old input queue.

The V2 focus companion adds only exact `Client1` alongside legacy `EqW-TAKP`.
It retains the exact process class, visible InputOutput geometry, physical
RMB, unique matching ancestor in the pointer's actual path, and native focus
None/PointerRoot guards. It rechecks those conditions immediately before
changing focus. Concrete foreign focus, obscured/hidden windows, unrelated
titles/classes, prefixes, case differences, optional NULs, type/format
mismatches and duplicate matching ancestors remain refused. It never searches
globally for a focus target, warps, grabs, injects input or writes properties.
Disabled or unknown Wine capture settings still prevent companion startup.

The existing V3 cursor DLL, runtime, input transport, observer, read-only window
inspector, all21 native launcher components and camera/input settings remain.
The unchanged inspector's `exact_identity` flag describes its historical
EqW-only diagnosis; a false flag for `Client1` is expected. V2 focus repair
receipts are the evidence for the new matcher. Its128KiB bounded window log
may finish before five minutes if full; that cap is separate from input loss.

## Physical acceptance

1. Camp and stop clients/servers normally. Install the signed APK in place
   without uninstalling. Preserve all three profiles, data, saved characters,
   bots, client files, prefixes, runtimes and settings. Reopen TAKP with the
   working Yaulp server deployment; no source update/build/deploy/import or
   prefix reset is needed for this launcher correction.
2. Enter the saved character promptly. Within the first five minutes of
   client launch, enable Look and test short right/left and up/down reversals,
   diagonal input and neutral for about ten seconds. Keep the same settings.
3. Turn Look off and verify the free menu pointer. Test Look on again and
   background/resume. Camp and stop normally, wait for stopped status, then
   Logs → Export log bundle. Provide the fresh bundle and whether reversing
   the stick immediately reverses the camera and neutral stops movement.

Expected objective evidence: V2 marker and exact qualified hash, at least one
successful scoped `focus_repair` from None/PointerRoot, a concrete game focus
after repair, actual cursor confinement during Look, signed packets/native
motion/game deltas that agree on reversals, zero neutral drift, free pointer
after Look release and no foreign-focus takeover. A successful X request or
controlled runtime test alone is not physical camera acceptance.

Keep server/Yaulp completion separate. NPC visibility, Traditional StoneUI,
the separate post-camp expired session-key observation, all-profile external
backup/restore, saved-bot/full-character persistence, classic skeleton visual
acceptance/exact restore and physical incremental/no-work build receipts are
separate checks.
