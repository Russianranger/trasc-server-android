# 0.6.29: identify the real TAKP window before changing recovery scope

Published 0.6.29/code78. Native qualification passed
[run 38505023364](https://github.com/Russianranger/trasc-server-android/actions/runs/38505023364).
All five release gates and independent public signature/source/asset audit passed.
See [release-status-0629.md](release-status-0629.md) and
[release-proof-0629.json](release-proof-0629.json).
This is a diagnostic update; it does not claim another camera correction.

The latest Thor test failed. The 0.6.28 focus companion started correctly but
made zero repair attempts: held RMB and PointerRoot passed the first gates,
then game-window discovery rejected the real pointer path. The log does not
identify whether title/type/length, class, visibility or layout caused it.
The open consumer used for prior qualification did not model this real layout.
See [device-camera-0628.md](device-camera-0628.md) and its exact evidence JSON.

Android-to-native delivery remains signed and timely. All 113 sampled held XI2
events match packets within 0–3 ms. Seven leftward pixels instead produce
game (+72,-34), exactly the escaped cursor's offset from center. Another clip
retry or sensitivity adjustment does not resolve window discovery.

A separate read-only native inspector records bounded pointer-path window IDs,
parents, geometry/mapping and short title/class property values, types, sizes
and exact-match flags. It distinguishes actual Wine whole windows from render
children and nearby matching candidates without changing focus or properties.
It records clocks, sampling limits, truncation/drop counts and normal completion;
the observer window is the first five minutes after client launch. Inspector
failure does not block the client. Existing focus/clip behavior is unchanged.
Process state also refreshes after teardown so ended helpers do not remain
labelled running in final status.

The inspector ran through the exact published ARM64 Wine/Box64/TigerVNC path
with original focus/observer/input bridge/wineserver bytes. Fourteen property
and layout cases passed, including actual Wine identity, optional NULs, missing
properties, UTF8 type mismatch, formats16/32, bounded high-byte values, render
children and candidates outside the pointer path. Actual focus/pointer/buttons
stayed unchanged; logs completed normally with zero drops/X errors, at most
15,928 bytes. Invalid CLI and normal SIGTERM checks passed. These tests qualify
the read-only collection, not the proprietary game's actual window identity
or physical camera usability. Exact build/runtime receipts ship with the ELF.

## One short device capture

1. Camp and stop clients/servers normally before installing the signed update
   in place without uninstalling. Reopen TAKP normally. Keep the server's
   Yaulp deployment, database, client
   assets, prefix, runtimes and settings; no rebuild/import/reset is needed.
2. Enter the saved character promptly within five minutes of client launch.
   Enable Look and reproduce right-stick right/left/up/down for about ten
   seconds, then turn Look off. Keep the same input and graphics settings.
3. Camp normally, stop the client, wait for stopped status and choose
   Logs → Export log bundle. Upload
   that fresh bundle with the observed behavior. It includes the new
   `logs/client-takp-windows.log`, marker `TRASC_TAKP_WINDOW_INSPECT_V1`, plus
   existing focus/native/packet/state/game traces.

The required result is actual rejected window/path information. Use those
measurements to implement the smallest ownership-preserving matcher correction;
do not infer physical camera success from a diagnostic capture. Camera remains
unaccepted. NPC visibility, Traditional StoneUI, the separate expired post-camp
session key observation, and backup/bot/skeleton/object-reuse checks remain
separate from this input investigation.
