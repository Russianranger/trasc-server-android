# 0.4.19 device result: spell loading 43.3s to 2.1s

The user reports that loading is much faster with the option enabled. Bundle `logs-3472540275696201050.zip` confirms a large improvement on the Thor in a paired off/on test. Both sessions use app 0.4.19, loading adapter V2, 1280×720, Turnip 26.0.0, Native Surface/60, balanced CPU settings, available-core affinity, camera V2 and non-verbose Wine logging. This review changes documentation only; the published APK remains 0.4.19.

## Initial server-to-character loading

Use the first connection in each fresh client process. Landmarks start at `Server selected`, not the unlogged physical button press. The loading-screen event is `Activating Load Screen`, and the endpoint is `Initializing character select UI`; these are engine events, not measurements of the exact frame seen on the device.

| Mode | Server selected | Loading-screen activation | Character UI | Before screen | After screen | Total |
| --- | --- | --- | --- | ---: | ---: | ---: |
| Off / profile | 14:45:30 | 14:46:28 | 14:46:43 | 58s | 15s | 73s |
| On / fast | 14:49:27 | 14:49:45 | 14:49:58 | 18s | 13s | 31s |

Sources are `logs/client-game.previous.log` and `client/current/Logs/dbg.txt`. World access is granted four seconds after server selection in both. The total recorded wait falls by **42 seconds, about 58%**. There is one sample per mode, so do not present these as multi-run averages or a guarantee for every launch. The direct stage measurements below independently locate the major improvement.

## Spell-loader stages

Sources are `logs/client-loading.previous.log` (V2 profile) and `logs/client-loading.log` (V2 fast). The retained `.previous.2` file is the older V1 run and is not the current off-mode baseline.

| Measurement | Off | On |
| --- | ---: | ---: |
| Whole spell loader | 43,296ms | 2,107ms |
| Text and associations | 28,926ms | 1,948ms |
| Original line-reading subtotal | 674ms | 712ms |
| Record-construction subtotal | 1,609ms | 896ms |
| Per-record checksum subtotal | 26,546ms | 232ms |
| Associations, included in text stage | 18ms | 9ms |
| Spell-file checksum | 14,339ms | 135ms |
| Association-file checksum | 17ms | 10ms |
| Post-load mapping | 1ms | 1ms |

The whole loader saves **41.189 seconds (95.13%)**, approximately 20.55 times faster for this measured stage. Per-record and spell-file checksums together save 40.518 seconds. This explains almost all of the improvement; the original line reader is not the former 40-second bottleneck. Subtotals are millisecond-resolution diagnostics, and nested stages must not be added twice.

Both modes return success and construct/checksum **40,914 spell records**, with 40,915 line reads and 370 associations / 371 association lines. The enabled run reports 8,960,166 fast integer fields, **40,916 fast checksum calls over 79,627,413 bytes**, and zero integer/checksum fallbacks. The two installed spell-file hashes are unchanged between runs: `034b5635049a9ef6e549f3f7d5b32f265a386d82a3fd3e8286b04d44b58a5e77`. The existing compatibility setting still excludes the same 15 spell IDs (50000–50014); this optimization did not add exclusions. These counters prove that the new path is active with the same recorded input and record counts; checksum equivalence itself is established by the source logic and release differential tests, rather than by these timing logs.

The deployed DLL is 1,705,472 bytes, SHA256 `1083365ea7c14c50671ecef554a36b936f0fa32a3ca1e9c01491f165212d787d`, built using the existing Microsoft v142 toolchain and carrying `TRASC_EQ_CAMERA_MOUSE_V2` and `TRASC_EQ_LOAD_V2`. No further compile/deploy or runtime replacement is needed for this review.

## Stability and remaining warnings

Both sessions enter the world and later reach character-select initialization again (14:48:15 off, 14:52:52 on). Neither Wine log records the prior stack overflow or an unhandled exception. Both client state records end with `stop_request`. Android exit records predate these tests and describe app stops / isolated-process cleanup, not a new crash during the comparison.

Existing client/runtime diagnostics remain: the skin-effect load failure, an unknown world-authentication message despite successful access, XComposite/MIDI/gamma warnings, occasional audio warnings and cleanup-time critical-section warnings. These should not be described as a completely warning-free run. The enabled gameplay log also reports three failed loads of particle texture `zapmuze.dds` at 14:52:03–14:52:06, followed by continued execution. This is an asset-load warning worth tracking; the logs do not establish whether the file is absent, unusable, or exercised only in this run. They do not establish that the loading optimization caused it. The enabled run also has a startup RpcSs warning and an additional unhandled render-state warning without stopping startup.

The familiar server-terminated/disconnected messages occur in both sessions before the later successful character-select transitions. Camp/disconnect remains parked, not fixed by this change. These logs do not establish a fresh character-select → server-select → Play test after the last UI cleanup, so preserve the earlier reconnect confirmation without claiming a new full-cycle test here.

Camera V2 remains enabled in both sessions. Off-mode records 434 recenter warps and subsequent menu gating. On-mode has zero look polls/warps, so this particular enabled session does not independently exercise recentering; do not mistake that for a regression or claim it tested full rotations. The user previously confirmed the unchanged controller adapter works.

Native Surface retains shared-memory capture: all 2,372 recorded off-mode frames and all 4,721 on-mode frames are SHM frames, with no presentation fallback. There are 20 and 8 five-second idle windows respectively with zero new frames and unchanged responses. Android thermal status remains 0 in sampled windows. Workloads differ during gameplay, so these totals are not an FPS, power or efficiency comparison.

## Next performance target

Keep Faster spell loading enabled on this device. The major checksum bottleneck is resolved in this comparison. Preserve the checksum semantics, camera adapter and existing source-DLL reconnect fix.

Remaining enabled-run landmarks are:

- Server selection to display initialization begins: 8s, including authentication and the now-2.1s spell loader.
- Display initialization begins to `Display initialized`: 12s; the UI XML/default-resource landmark interval alone is 7s (5s in the off run).
- Global data/model loading: 10s (13s off).
- Final character-select setup after global data: approximately 1s.

These point to display/UI initialization and global models as the next areas to profile. The 7-second UI interval is only a coarse landmark and does not prove XML parsing alone owns all of it. Optimizing the remaining 712ms of line reading would offer much less benefit than the solved checksum issue. Do not remove client assets or model data without explicit intent and rendering validation.

Wine-prefix preparation before the game launches also differs (38.083s off versus 5.635s on); it is outside the server-selection interval and must not be credited to this spell-loading optimization. No additional product changes or APK are part of this evidence review. No subagents were used.
