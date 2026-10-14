# 0.6.29: identify the real TAKP window before changing recovery scope

Source candidate 0.6.29/code78. Qualification and publication are pending.
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

## One short device capture

1. Stop the TAKP client and install the signed update in place without
   uninstalling. Keep the existing server, Yaulp deployment, database, client
   assets, prefix, runtimes and settings; no rebuild/import/reset is needed.
2. Enter the saved character promptly within five minutes of client launch.
   Enable Look and reproduce right-stick right/left/up/down for about ten
   seconds, then turn Look off. Keep the same input and graphics settings.
3. Camp normally, stop the client and choose Logs → Export log bundle. Upload
   that fresh bundle with the observed behavior. It includes the new
   `logs/client-takp-windows.log`, marker `TRASC_TAKP_WINDOW_INSPECT_V1`, plus
   existing focus/native/packet/state/game traces.

The required result is actual rejected window/path information. Use those
measurements to implement the smallest ownership-preserving matcher correction;
do not infer physical camera success from a diagnostic capture. Camera remains
unaccepted. NPC visibility, Traditional StoneUI, the separate expired post-camp
session key observation, and backup/bot/skeleton/object-reuse checks remain
separate from this input investigation.
