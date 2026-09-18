# Compiled DLL resolves tested reconnect; loading and mouse look next (2026-09-18)

Latest user feedback supersedes the unresolved reconnect status in the previous notes. The user says deploying the compiled DLL fixed the character-select → server-select → Play failure. The previous add-on came from the NMS / Project Triune patcher; its newer features were exclusive to Triune development and not usable in this local setup. Its `nms_crash.txt` exists but is zero bytes, so do not request that file again or assume it contains a recoverable backtrace.

The new device bundle is `logs-4436019274023234972.zip`, exported at 2026-09-18 00:55:14 UTC. It was read from the supplied scratch copy and extracted to ignored `runtime-work/logs-0416-compiled-dll`. No product code, runtime, database or client files were changed in this investigation; app remains 0.4.16.

## Deployment and reconnect evidence

`logs/client-dll-deploy.json` confirms the successfully compiled DLL was deployed: SHA256 `556ead4699b1af797eb2c676ef40dacc92ade932526ebe551f36382de7424c28`, 1,695,232 bytes. The prior DLL backup is `backups/client-setup/20260918-004503-d062b1`. Native DINPUT8 loads in the latest session. `dbg.txt` records three server selections and successful character-select UI initialization after each, including two repeat selections in the same game process. The retained current Wine segments show no recurrence of the prior `c00000fd` stack overflow. Logs are bounded, so this is not a claim that every line from the launch remains available. User confirmation supplies the direct acceptance evidence.

The latest session ended with an explicit stop request and launcher exit 0. Android exit records contain force-stop/user-requested and isolated-renderer cleanup records, not a new recorded native application crash. Do not describe all historical shutdown problems as fully tested/resolved.

## Server-select to character-select timings

These are timestamped game log markers, not a video measurement of the instant the screen becomes interactive. Accuracy is approximately one second.

| Attempt | Server selected | Authentication granted | Display initialization begins | Character-select UI begins | Total |
| --- | --- | --- | --- | --- | --- |
| First | 00:48:15 | 00:48:18 | 00:49:01 | 00:49:24 | 69 s |
| Reconnect | 00:49:38 | 00:49:41 | 00:50:46 | 00:51:06 | 88 s |
| Reconnect | 00:53:05 | 00:53:09 | 00:54:12 | 00:54:31 | 86 s |

The largest individual gaps follow `Check 1sa. 0xf0df437f`: 00:48:20→00:49:01 (41 s), 00:49:44→00:50:46 (62 s), and 00:53:12→00:54:12 (60 s). The next logged messages concern race/player-animation data and display initialization. These message boundaries do not identify which function consumed the gap; do not call it a checksum, model parsing, network timeout or specific file defect without more evidence.

Ten-second Linux thread samples identify `eqgame.exe` PID/TID 612 as consuming approximately 99.6–99.9% of one CPU during the interior of these gaps. CPU is calculated from the change in `cpu_ticks` divided by `clock_ticks_per_second` and elapsed sample time. The main thread's sampled CPU is 7. It is no longer stuck on CPU 0; current configuration permits available cores. Other helper threads are much less busy. This points to CPU-heavy single-threaded client work (possibly including a busy wait); it does not identify the guest instruction or prove a specific optimization is safe.

The last retained third-attempt trace before the quiet interval is Wine time 319538.927, `GetModuleFileNameW` for `D:\eqgame.exe`; the next timed trace is 319602.365, roughly 63.4 seconds later. The interval itself is not a Wine trace flood. Authentication is granted within 3–4 seconds of server selection, and the world log records the matching local connection/checksum exchange promptly. There is no evidence here that a server/network delay is the dominant cause.

After the gap, display/UI/global-model work takes 19–23 seconds. XML parsing alone occupies about 5–6 seconds. Game logs continue to report some missing/invalid optional assets, but do not delete or rewrite loading lists speculatively.

## Existing diagnostics and display costs

`diagnostic_logging` remains true. This launch produced 47,264,662 bytes of Wine logging and five rotations. Disable **Client → Graphics, audio & launch options → Verbose Wine diagnostics** and relaunch before collecting a representative loading-speed comparison. Normal exports still include `dbg.txt`, thread samples, state and presentation measurements. Reducing diagnostic output removes avoidable overhead, but is not established as a fix for the long, trace-quiet CPU interval.

The current Native Surface capture path still uses MIT-SHM: all 4,775 sampled full frames are marked shared-memory. Median capture time across nonempty five-second report windows is approximately 0.974 ms per frame (median of window averages, not a raw frame latency percentile). Many loading-period reports have no full frames and nearly 300 unchanged responses per five seconds. Therefore, pursuing faster frame copying alone is unlikely to recover the primary 41–62 second loading delay. Keep the working shared-memory/unchanged-frame path intact.

Wine-prefix preparation separately took 28.56 seconds before the game was launched. This is not part of the server-select timings and must not be conflated with them.

## Next concrete evidence / device checks

1. Export the actual `client/current/eqgame.exe` via Files search → Select → Export file. The main executable is not in the diagnostic ZIP or available source checkout. Inspect it read-only to locate the code around the loading markers; do not publish the game binary or claim that disassembly alone establishes the running hotspot. More targeted runtime sampling may still be needed. No Mac tooling is needed.
2. With the compiled DLL retained and verbose diagnostics off, collect a baseline server-select→character-select run. Compare the same markers and first-versus-repeat selections.
3. Separately, retry **Recenter mouse for camera look (experimental)** with the compiled DLL, stopping and relaunching to apply it. Test held-right-click, toggled look and ordinary inventory pointing. If it still freezes or disrupts the cursor, disable it and relaunch. Previous force-mode failure used the different patcher DLL; the current successful session still has `MouseWarpOverride=default` and does not test the force option. This is a controlled device comparison, not a claim that mouse look is fixed or that the previous force failure was caused by ImGui.

Wine's own recenter option remains preferable to an invented X11 warp loop because Wine tracks its input state; see [Wine 10 mouse implementation](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/dinput/mouse.c). The helper delivered 1,030 relative events and 36 button-only events during the current consumer session. This confirms transport activity, not unbounded camera rotation. Do not change the default or add another cursor-warp implementation without the new-DLL comparison.

Preserve the user-confirmed #tim command, working compiled add-on and all release/test gates. Camp/database investigation remains parked. No new APK is warranted solely to run these existing controls or export the executable.
