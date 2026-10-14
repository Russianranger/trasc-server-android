# 0.6.28: recover the missing native TAKP focus

Source candidate 0.6.28/code77. Exact published-runtime qualification passed
[run 38500575431](https://github.com/Russianranger/trasc-server-android/actions/runs/38500575431).
APK qualification and publication must finish before installing this candidate
as a verified release.

The runtime fixture uses the original published ARM64 client-1.0 archive
(353,710,680 bytes; SHA-256
`2f130c07683e50bc606af111d5c35c4f503c1427772c1f9b0f45e1e4b75c76c4`)
and actual 0.6.27 APK input bridge/patched wineserver. Original V3 and observer
bytes remain. Its open PE32 window supplies the exact EqW title/Wine class at
800×600, while Thor is 1280×720. A native PointerRoot fault after RMB hold
preserves Windows foreground and cached clip; fresh (-1,0) instead becomes
(+2,0) through both DirectInput paths. The companion then restores actual focus
and pointer confinement; ten signed segments, neutral, menu release, six
refusal guards and None-focus recovery after resume pass. This fixture does
not run proprietary game code or Android/PRoot/GPU and is not Thor acceptance.
Qualified focus ELF: 72,232 bytes, SHA-256
`90dda77cb0b0fe1d18d4fa7b39bedda7dad67af6c342d7b23c74d0129f666865`.
Exact build/source/runtime receipts ship in the APK.

The physical 0.6.27 trace identified a specific failure: all 40 held-look native
snapshots leave X focus on PointerRoot, while Wine reports the game active.
All 71 sampled native XI2 events preserve Android's signed packets. A leftward
packet (-1,0) instead becomes (+16,-96) inside Wine/game input, matching the
escaped physical cursor's offset from the cached clip center. The measured
input ages are short, not a held queue backlog. See
[device-camera-0627.md](device-camera-0627.md) and its exact evidence receipt.

## Scoped repair

A separate native companion restores missing X focus only while physical right
mouse is held and the pointer's actual descendant path contains the visible
TAKP window with exact WM_NAME `EqW-TAKP` and Wine WM_CLASS `eqgame.exe`.
Both class strings must match. Missing properties, hidden/unmapped windows,
another concrete focused window, pointer outside the game and released RMB
deny recovery. The candidate and physical gate are checked again before the
focus request. No global window search, warps, grabs, injected movement,
property writes or prefix-setting changes occur.

The existing V3 EQW helper then performs its existing owned clip recovery.
Native focus success alone does not prove capture or camera acceptance.
The companion runs for the supervised client lifetime, with bounded retries,
two-second native-request timeouts and a 128 KiB log. Log saturation does not
disable recovery. Failure is reported without blocking the client; deliberately
disabled or unknown existing capture configuration prevents activation.

The original read-only native observer remains unchanged and runs for its
first five minutes. Android sent-packet observations and existing game trace
remain. Renderer, CPU, sensitivity, controller mappings, input transport,
server source and binaries, databases, characters, bots, client assets, Wine
prefixes, installed runtimes and backup/update controls remain preserved.

## Thor acceptance

1. Stop only the TAKP client. Install the signed APK as an Android update,
   without uninstalling, importing the database/client or rebuilding the server.
2. Enter the existing character and keep all input/renderer settings constant.
   Start testing promptly within the observer's first five minutes.
3. Enable Look and use only the Thor right stick: right for two seconds,
   briefly left, neutral; then left, briefly right, neutral. Repeat vertically
   and diagonally. Each reversal should follow the new direction promptly;
   neutral should stop rotation, without unrequested motion on another axis.
4. Turn Look off and confirm free menu/inventory pointing. Background/resume
   once and repeat a short reversal; camp/reopen the saved character normally.
5. Stop the client normally and choose Logs → Export log bundle. Send the
   fresh bundle with actual behavior; a brief video can measure visual latency.

Required logs: `logs/client-takp-focus.log` (marker
`TRASC_TAKP_X_FOCUS_RECOVERY_V1`, guarded repair/result),
`logs/client-xinput.log` (actual focus and pointer),
`logs/client-pointer-packets.log` (sent signed deltas),
`logs/client-state.json` (`takp_focus_recovery` identity/liveness and preserved
settings), `client/current/eqw-camera-diagnostics.log` (clip and game input),
and original input/Wine transport context. No repair is expected if correct
native focus already exists. Verify actual pointer confinement and signed
consumer movement; disclose expired/capped/missing/dropped/sampled telemetry.

Physical usability remains open until the Thor test passes. NPC visibility and
Traditional StoneUI remain separate. All-profile bot/character reopening,
external backup/model restore and physical incremental/no-work object receipts
remain separate acceptance gates.
