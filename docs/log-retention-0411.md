# Log retention and camp investigation — 0.4.11

## Log storage

Logs → Log storage defaults to **5 older logs per process**, with **2, 3, 4, 5** available. Save & clean older logs persists the choice and immediately removes excess history. Automatic cleanup runs every minute while the app process is alive, including when the Linux runtime is closed.

- Existing EQEmu PID logs are grouped as login, world, UCS, query server, and zone. All zone startup and named-zone PID logs share one zone quota, rather than accumulating a separate quota for every zone or PID. Newest files are selected by modification time. Logs whose PID still exists are kept in addition to the quota; unknown/inaccessible process state is treated conservatively.
- Launcher/client logs rotate into `.previous.log`, then `.previous.2.log` through the chosen count. This includes Wine, prefix, display, GPU/audio/presentation, PRoot, compiler, server stdout, MariaDB, and operation output. Existing `.previous.log` remains the newest historical name. Server stdout rotates on process start, operation output on job start, and control/app logs at their existing/new 8 MiB threshold.
- Each newly archived launcher/client log keeps at most 8 MiB, retaining startup and final output when shortened. Wine keeps its existing two live bounded segments. This is a history limit, not a total disk quota: active server logs, saved export ZIPs, database/session backups, imported chat logs and unknown filenames are not deleted or truncated.
- Symlink files/directories are not followed. No runtime download, source import, database replacement or DLL compilation is required for the app update.

## Camp disconnect evidence

Bundle `logs-6442597055042792067.zip` records the ROF2 disconnect at **2026-09-17 13:15:53** with `DisconnectReasonOtherSideTerminated`. The zone logged three character saves at that same second, then went idle at 13:16:53. The user stopped the server at 13:17:24. Wine continued presenting frames and has no stack overflow or process crash at the disconnect. This is different from the older graphics exception investigated in 0.4.9.

The imported server source at `4c653ca2d16aaede33b7011d07254c520ac5f5df` defaults **Custom:CampTimerMs to 100**. `Handle_OP_Camp` sets `fast_camp` for values below 29000. On expiry, `Client::Process` saves the character, calls `OnDisconnect(false)` and removes the client. That path sends `OP_LogoutReply` and closes the stream, whereas `Handle_OP_Logout` also calls `SendLogoutPackets()` (including `OP_PreLogoutReply`). The immediate server-driven path is the leading explanation for ROF2 showing disconnected instead of its normal countdown/return. The bundle does not contain the live rules table or packet capture, so the active rule value and exact packet cause are not proven.

**Existing-app recovery/test:** Gameplay → Load settings → search `CampTimerMs` → change `Custom:CampTimerMs` to **29000** in the active ruleset → Save → stop/start the server. On a normal non-GM character outside the Bazaar/East Commonlands special path, use ordinary `/camp`, wait for the countdown, and verify character selection/relogin. No server/DLL rebuild is needed. Export logs if it still disconnects. GM and Bazaar/EC paths are separate; do not claim this setting fixes every logout route.

No server protocol patch or silent database rule override is included. The app's existing rule editor already provides this reversible configuration change. A correct instant-camp protocol change would need separate client/server testing; the source comment claiming an immediate character-select transition is not accepted as runtime proof.

## Verification

Python history tests cover all four limits, ordering, invalid settings, bounded startup/tail capture and symlink rejection. Native JVM tests cover existing PID collections, active PID exclusion, the shared zone quota, settings persistence/reduction, unknown files, backups/chat files, symlink isolation and bounded archives. Browser regression covers all four selections while the runtime is stopped and reloading the selection after changing tabs. All seven jobs passed in [release run 35229662711](https://github.com/Russianranger/trasc-server-android/actions/runs/35229662711), including 115 Python tests, native JVM checks, browser regression, Android lint/signing, database integration, Windows source compilation and the existing runtime/graphics gates. The browser initially caught a stale settings-read race; the released picker prevents editing during loading and waits for pending saves before rereading. The original regression now passes. Device confirmation of normal camp and new retention remains outstanding.
