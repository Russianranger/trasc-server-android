# Embedded client milestone

Preview 0.3.0 introduces an experimental in-app Wine display and ROF2 launch path. The user confirmed 0.2.1 session backup/restore, controller bindings and the input diagnostic on the Thor before authorizing this phase. The 0.3.2 Thor logs now confirm startup through character selection. Playable performance, full plugin behavior and world entry require device verification.

## Current 0.3.3 device pass: remove the tracing bottleneck

The 0.3.2 log bundle confirms both native and system DirectInput loading, then game asset initialization from 17:42:54 to 18:36:05 UTC and character selection at 18:36:11. Its Wine log contains 9,258,244 lines (1,059,025,481 bytes), dominated by routine debug-string exception dispatch/unwind traces and D3DX fixme messages. These diagnostic exceptions are not evidence of millions of game crashes. Wine 10's [OutputDebugString implementation](https://github.com/wine-mirror/wine/blob/wine-10.0/dlls/kernelbase/debug.c) raises a debug-print exception for each message; tracing expands that work into repeated output. Disabling tracing does not remove the underlying debug-string calls.

0.3.3 uses `WINEDEBUG=-all,+timestamp,+pid,err+all,trace+loaddll` by default. The optional **Verbose Wine diagnostics (slower)** checkbox restores detailed exception/module/fixme reporting. Errors and real native/system DLL load traces remain available in normal mode. Output is parsed continuously before bounded rotation: `client-wine.log` and `client-wine.overflow.log` retain the latest two segments (8 MiB each); `client-wine.previous.log` retains up to 8 MiB of the previous session. Oversized old logs retain startup and final excerpts with a truncation notice. State records diagnostic mode, total emitted Wine bytes and rotation count. These are not frame-rate measurements.

Stop both runtimes and update in place. Keep the current runtime, prefix, client and database. Start the server and launch at the **same 800x600**, native DLL enabled, **verbose diagnostics off**, for a useful comparison. No repair/reimport/preparation is needed. Export Logs and note time to character selection, responsiveness there, and whether entering the world succeeds.

The graphics log explicitly reports `Accelerated: no`, llvmpipe LLVM 15 / Mesa 22.3.6. Software rendering remains a performance limit after tracing is removed. This pass leaves rendering/Box64 safety settings unchanged; it does not provide Turnip/DXVK acceleration or claim a playable ROF2 frame rate. RFB update counts include idle periods and are not game FPS. The next graphics phase needs a tested Android GPU/presentation path, not just removal of `LIBGL_ALWAYS_SOFTWARE`.

## Previous 0.3.2 device pass: system DirectInput forwarding

The 0.3.1 device logs confirm 32-bit Wine and native `D:\DINPUT8.dll` loading, followed by a failed absolute system `dinput8.dll` load. The add-on source forwards input calls to that system library. The former `dinput8=n` policy blocked Wine's built-in implementation; 0.3.2 uses `dinput8=n,b` and reports both load traces separately. Loading evidence does not by itself establish successful gameplay.

Stop both runtimes, update the APK in place, keep the existing prefix/client/runtime, start the server, then **Launch ROF2** with native dinput8 enabled. No additional prefix repair is indicated for the reported run. Export Logs afterwards: native exports now include selected client startup files such as `client/current/Logs/dbg.txt` and `client/current/dinput8.log` when present. Logs remain readable with both runtimes closed. Session timestamps/stop reasons separate current attempts from historical runtime errors.

The later WineD3D back-buffer diagnostic in the same run is not sufficient to establish a fatal graphics error. Renderer changes are deferred until input forwarding is retested and the game's own log is available.

## Recovery from the 0.3.0 black screen

Preview 0.3.1 checks the 32-bit Windows system files and executes `C:\windows\syswow64\cmd.exe` before launching the game. The device log confirmed `eqgame.exe patchme` was passed correctly, followed by Wine's fatal kernel32.dll loader error; it did not reach native dinput8 loading.

After updating, stop the client and select **Repair Wine prefix**. The existing prefix is moved to `client/prefix-backups/` before a fresh Windows environment is created. Wait for Wine desktop, then stop the client, start your server and Launch ROF2. This preserves imported client files, controller mappings and server data. Keep the current client runtime; no redownload is needed for 0.3.1.

If it fails, the display shows a failure dialog and Logs includes `client-prefix.log`, `client-prefix.json`, `client-prefix-repair.json` and `client-wine.log`. The prefix inventory distinguishes missing runtime files from an incomplete prefix. Native DLL confirmation still requires an actual Wine load trace.

## First installation sequence

1. Keep the working Preview and external session backup. Stop the runtimes and update the APK in place.
2. Open **Client → Download client runtime**, or select the release's `client-runtime-arm64.tar.gz` with **Choose offline runtime archive**. This installs a separate client environment; server runtime 1.1 and the database are retained.
3. Choose **800x600 → Try Wine desktop**. First startup creates a Wine prefix and can take a minute. The display opens inside this app. Try touch/mouse and the saved controller mappings. Android Back returns to management; **Return to client** reconnects to the running display.
4. **Stop client**. The imported client ZIP from 0.2.x is already in `client/current`; do not reimport it unless replacing it.
5. Open the server runtime, then **Client → Prepare client for this server**. This generates and installs the four handshake files in the root and Resources, writes the configured login endpoint to eqhost.txt, and enables windowed mode at the chosen resolution. Original files are retained in `backups/client-setup/` with a manifest; errors roll back files already changed. Other INI settings and the imported DLL are retained.
6. Start the server. Select **Launch ROF2** with **Load the imported native dinput8.dll** checked. The command uses `eqgame.exe patchme` inside a Wine virtual desktop. The supervisor verifies matching PE32 executable/DLL architecture before starting.
7. Use the display's **Keyboard** button for text: **Type** inserts text into the focused field; **Send + Enter** inserts it and sends Enter for chat. Physical keyboard/mouse and saved gamepad bindings also feed the display. Focus loss releases held inputs.
8. If startup fails or shows a black display, return with Android Back, stop the client and export Logs. Include `client-runtime.log`, `client-wine.log`, `client-display.log`, `client-graphics.log` and `client-state.json`. The native DLL status requires Wine's actual `loaddll` native-load trace. File presence or an override alone is not confirmation. Disabling the native-DLL option is a comparison run using Wine's built-in dinput8, not a claim that the modification works.

## Architecture and boundaries

- The existing Android-packaged PRoot loader starts a second Debian Bookworm ARM64 rootfs under `work/client/runtime`.
- Wine **10.0 WoW64** runs the 32-bit Windows client through **Box64 0.4.4**. Native ARM64 libraries handle wrapped platform calls; x86 libgcc/libstdc++/libunwind are also included for Wine's Unix loader.
- Mesa **llvmpipe** and WineD3D provide software Direct3D/OpenGL for this compatibility milestone. Hardware Turnip/DXVK acceleration, sound output and further performance tuning remain later work. This is not yet a production gaming build.
- TigerVNC provides the X display. RFB listens only on an app-private Unix socket with mode 0600; TCP RFB and X11 listeners are disabled. X11 connections use a random authorization cookie.
- A native Android display implements bounded RFB raw/copy/resize decoding and sends keyboard/mouse events. There is no external VNC app, browser service or Winlator handoff in this path.
- `work/client/prefix` preserves the Wine registry and drive state. The imported client remains in `work/client/current`, mapped as Wine drive D:. Runtime installation does not replace the prefix or imported game.
- Client sockets, Xauthority and process state live under the app's temporary home directory, outside complete session archives. The client runtime, prefix, client files and controller profile are included through the existing client archive component. Complete backup/restore stops the client first.

## Verification

The repository supplies its own 32-bit Windows test EXE and a test DLL named dinput8.dll. These contain no EverQuest code. ARM64 integration launches the EXE through the same Wine/Box64 supervisor, requires the native DLL export, creates a Direct3D9 device, checks rendered pixels through the private display socket, and verifies mouse/keyboard delivery. An additional 512-call OutputDebugString workload compares normal/verbose output volume and records timings directly and through pinned PRoot; timings are informational, not a ROF2 benchmark. This validates infrastructure; it cannot establish compatibility with the user's modified ROF2 DLL without device evidence.

Host JVM checks exercise the production RFB parser, malformed/truncated frames, event wire format, overlapping gamepad/physical/touch holds, shifted key release and text plus Enter. Python checks cover PE32 matching, truthful DLL evidence, client file preparation/rollback and preservation of INI values. Browser tests cover desktop/game launch options, return/stop flows and native-DLL status wording. The actual client runtime archive is extracted and roundtripped through the production Android archive classes, checking executable permissions and every restored file hash. Android compilation/lint and the existing server/session tests remain release gates.

Upstream references: [Box64's WoW64 support](https://github.com/ptitSeb/box64), [Wine build architecture/dependencies](https://github.com/Kron4ek/Wine-Builds), [TigerVNC socket options](https://tigervnc.org/doc/Xvnc.html), [RFB protocol](https://www.rfc-editor.org/rfc/rfc6143.html).
