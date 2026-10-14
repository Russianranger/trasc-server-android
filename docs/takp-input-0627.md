# 0.6.27: measure the remaining Thor capture failure

Package: 0.6.27/code76. APK assembly/signing/publication are pending until the
release gate completes; do not describe this source draft as a published APK.

The user confirmed 0.6.26 slightly improved mouse look but remains unusable,
with the previous delayed-reversal behavior. Its V3 helper loaded correctly;
48 accepted capture-recovery requests still left 36/60 sampled cursors outside
the reported one-pixel clip. During Look, events were 1–25 ms old. Neither
another blind clip retry, ABS conversion nor queue draining is supported.

## Qualification through the published runtime

[Run 38489151047](https://github.com/Russianranger/trasc-server-android/actions/runs/38489151047)
passed both native-host and actual published ARM64-path jobs at source
3511ce6260ccef33478983d79356a205b8b43c5d. The ARM job reused the exact original
client-1.0 archive (353,710,680 bytes; SHA-256
2f130c07683e50bc606af111d5c35c4f503c1427772c1f9b0f45e1e4b75c76c4),
the published 0.6.26 input bridge and patched wineserver. Runtime and input
bridge were not rebuilt. The open PE32 consumer runs through Box64 with the
accurate CPU profile, production authenticated TigerVNC1.12 startup flags and
TRASCIN1 input. Its fixture geometry is 800x600; Thor uses 1280x720.

Five disposable-prefix cases passed their expected assertions. Default,
global GrabPointer=Y and per-app Y overriding global N delivered exact signed
movement and reversals. Global N and per-app N overriding global Y reproduced
accepted cached one-pixel capture with a physically escaped pointer and
inflated relative values. These controls do not identify the user's actual
registry setting. This is a production-runtime fixture, not the proprietary
game, Android/PRoot/GPU or physical Thor acceptance.

The new native observer actually captured clock anchors, XI2.2 negotiation,
device/valuator inventory, signed raw events while Look was held, focus/pointer
snapshots and bounded completion in all five cases. Observer logs were
9,992–28,866 bytes, below the 128 KiB bound. Read-only observer SHA-256:
5f5cf7e8f8d2d3df475284f72fa0f2944e1cadb9ba334927021799615b35744b.
Build/source, ARM runtime and observer evidence receipts are bundled in the APK.
The earlier run 38488885066 stopped before camera measurement because the test
harness assumed a standalone libXtst package; the published bridge links it
statically. The corrected harness reused the original bridge and runtime.

## What this APK records

The existing V3 EQW helper and mouse delivery remain. A separate native X
connection observes without XTest injection, focus changes, grabs or warps.
It records physical pointer/buttons, actual focus ancestors/PIDs, client/master
pointer IDs, devices/relative valuators, sampled core and XI2 raw motion with
both cooked/raw values. It uses at most 128 KiB and 300 seconds, with clock
anchors, sampling/drop counts and a reserved end receipt. Core delivery may be
absent while another client owns a grab; sampled records are not complete totals.

The prefix inspector reads only short named global/per-eqgame.exe Wine input
settings from existing user.reg, including GrabPointer, UseXInput2, UseTakeFocus
and MouseWarpOverride. It reports missing/unsupported values and source SHA;
it never invokes reg.exe or changes the prefix. A reported default is Wine's
configuration default, not independently measured driver state.

Android records successfully sent pointer packets, signed deltas, button mask,
enqueue/send uptime and epoch time. No keys/chat are recorded. A daemon writer
owns disk I/O; the input thread only offers to a bounded 256-row queue. Output
is capped at 128 KiB, flushes within one second under healthy storage, retains
configured log histories and records drops/sequence gaps. Logging failures do
not block input. Blocked-storage, queue-drop/drain, live export, cap and path
refusal tests passed. This adds observation overhead; it does not change gain,
inversion, renderer, bindings or the camera implementation.

## One short Thor test

1. Stop the TAKP client; install the signed APK as an Android update without
   uninstalling. Retain the working server and its Yaulp fix. Restart the
   client, keeping sensitivity/inversion/renderer/CPU settings constant.
2. Enter the saved character and start the test promptly after world entry so
   the native observer's first-five-minute window includes it. Enable Look.
   Use only the Thor right stick: right for about two seconds, shorter left,
   neutral; left then shorter right, neutral; up/down both ways and diagonals.
   This is a manual test, with no automatic movement or countdown.
3. Turn Look off, check inventory/chat pointing, then stop the client normally
   and choose Logs → Export log bundle. Send the fresh bundle and the actual
   behavior. A short video is useful if direction timing remains ambiguous.

Needed evidence is collected automatically:

- logs/client-pointer-packets.log: sent/queued signed Android packets.
- logs/client-xinput.log: native XI2/core/focus/pointer evidence and clock anchors.
- logs/client-state.json: takp_input_settings and takp_xinput_observer identity.
- client/current/eqw-camera-diagnostics.log: V3's actual DirectInput/game consumer.
- logs/client-input.log and client-wine.log: original transport/module context.

Look for native marker TRASC_TAKP_XINPUT_OBSERVE_V1 and producer marker
TRASC_POINTER_PACKETS_V1. Missing/expired/capped/drop-bearing telemetry must be
reported, not treated as a pass. The comparison should identify whether signed
input changes before injection, in X cooked/raw events, in Wine/DirectInput or
in the game. Camera remains unaccepted until physical behavior is usable.

No server recipe/source, database, character/bot store, runtime, client asset,
Wine-prefix setting, backup/update path or other-profile control changed.
The same 21 native launcher components and exact V3 helper are reused. NPC
visibility and Traditional StoneUI remain separate; full three-profile bot/
character reopening, external checkpoint/model restore and physical no-work
object/receipt acceptance remain their own checks.
