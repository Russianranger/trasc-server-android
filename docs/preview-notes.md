# 0.6.2 — Client display startup on devices that deny hard links

The app now writes a fresh private X11 authorization file directly for both the
game/desktop display and the DLL compiler display. This removes xauth's hard-link
lock dependency and avoids putting its cookie in error messages. The private
display server also skips its hard-link PID lock. Cookie authentication, disabled
TCP listeners and the private display socket remain enabled.

This addresses the reproducible hard-link-denial failure behind a possible
`xauth ... returned non-zero exit status 1` during client startup. The supplied
Fold6 screenshot identifies the failing command but does not include its stderr;
device acceptance is still required to confirm this user's exact cause.

Stop the client and runtimes, then install over the existing app without clearing
storage. Start the server and try **Client → Start ROF2** with the same client and
graphics settings. No runtime/client reimport, server rebuild or DLL rebuild is
required for this repair. If it fails again, export Logs immediately after the
attempt so the underlying error and startup stage are available.

The 0.6.1 Microsoft toolchain download button and Beta 0.6 runtime-install repair
remain included. This release does not enable global PRoot hard-link emulation.

---

# 0.6.1 — Download the Microsoft toolchain in the app

Client → Build dinput8.dll on this device now offers **Download Microsoft toolchain**.
Review the Microsoft license and explicitly accept before downloads start. The app
prepares and imports the matched v142/14.29 compiler and Windows SDK, with progress,
cancellation, verified-download reuse, and preservation of the existing compiler
on failure. A Windows computer, Termux and manual ZIP preparation are no longer
required. Offline toolchain ZIP import remains available.

Install this APK over the existing app after stopping the client and runtimes.
Keep the same package, signing key, worlds and client settings. Open the server
runtime, keep the server/game stopped, and allow at least 8 GiB of free internal
storage before downloading. The separate client runtime is needed for compilation.
Compile and Deploy staged DLL remain separate steps. No automatic server or DLL
rebuild is performed. Existing working compilers can simply be retained.

The extraction helper is downloaded and unpacked privately from authenticated Debian
packages; no Linux package installation or upgrade is performed. Microsoft SDK
payloads are downloaded directly to the device and are not redistributed with TRASC.
See [toolchain preparation and manual alternatives](toolchain-without-windows.md).

Beta 0.6's runtime hard-link repair remains included. The supplied Fold6/Android 16
logs now confirm runtime startup, source/database/maps import, server compilation,
deployment and three zone workers. That bundle did not yet test the client runtime
or in-zone maps. The new toolchain button still needs physical device acceptance.
The reported maps input/archive-validation failures remain a separate follow-up.

---

# Beta 0.6 — runtime installation repair

Server and client runtime installation now expands hard links into regular file copies, preserving executable bits and guest symlinks. This addresses the confirmed `link failed: EACCES (Permission denied)` extraction failure reported on Fold6/Android 16. Both online and offline installers are covered. Runtime archive contents/packages are unchanged.

Install over the existing app without uninstalling or clearing storage. On the affected fresh setup, leave TRASC Custom selected and try Setup → Download runtime once; confirm Runtime ready. Install the separate Client runtime if needed. If either fails, export Logs and report the stage. Existing working worlds need no runtime/server/DLL reinstallation for this repair. Device acceptance is still pending.

[Beta 0.6 release notes, offline links and complete test instructions](beta-06-release.md). Traditional compilation, era presets, shelved routes and backup-provider resilience retain their previous scope.

---

# 0.5.8 — Custom and Traditional EQEmu profiles

Choose **TRASC Custom** or **Traditional EQEmu** at the top, then **Switch world**. Stop the client and server runtime and finish file transfers first. The selected world retains its own source, database, maps, quests, client, controller settings, logs and backups. The existing Custom installation stays in place.

Traditional uses unique 16-bit adventure art on all ten shared tabs and adds explicit quests, Perl plugins, Lua modules and server-assets imports, plus ordered split-PEQ-seed import. Use a separate clean ROF2 ZIP for this profile; custom DLL hooks are disabled. No era preset is applied.

**Traditional Build, Deploy, Start server and generated client preparation/export are intentionally pending the next Android fork milestone.** This APK prepares and manages that profile; it does not yet run an unmodified upstream EQEmu server.

## Update and check

1. Stop the client/runtime and install over the existing app. Keep Custom's current runtime, server, client DLL and working route. No Custom rebuild or reimport is required.
2. Confirm the app opens in TRASC Custom with your existing files/settings. Stop its runtimes, then switch to Traditional. Confirm the profile label and pixel-art backgrounds change and all ten tabs remain available.
3. Install the server runtime in Traditional. Import your traditional source and compatible PEQ database/maps. Use the extra content panel for quests, plugins, Lua modules and assets. ProjectEQ's repository can supply its separate quests/plugins/Lua folders. For split seeds, add SQL files in the distribution's prescribed order and import the bundle once.
4. Import your separate clean ROF2 client through Client if ready. Traditional's first server login waits for the next milestone; keep Custom's client intact.
5. Stop Traditional's runtimes, switch back to Custom, and confirm its saved source/client/settings are still present. Start the existing world normally. No repeat ferry journey is requested.
6. If a switch/import fails, export Logs from the affected profile and report the selected profile and last action. Complete-session archives restore only to their matching profile; older archives belong to Custom.

[Full component checklist, storage/backups and next fork-compilation plan](traditional-profiles.md). Ocean of Tears/Overthere and era presets remain shelved. The prior large-export/provider failure remains separate unresolved work; preserve the successful backup and use the existing ZIP for retries.

---

# 0.5.7 — Fixes, illustrated tabs and shared session controls

World and client repairs now live in **Fixes**: the Qeynos–Erudin route, Nektulos maps, spell compatibility and Wine prefix recovery. Spire focuses on content browsing/editing. The retired single-zone ferry trial has a cleanup-only panel; its old installation/reset controls are gone. Existing route data and settings are retained.

Each of the ten tabs has a distinct bundled fantasy scene, with seven new illustrations in the existing green/gold theme. Artwork works offline.

The shared runtime panel now includes **Start server, Stop server and Restart**, with server and client indicators at its top right. Client activity is checked on every tab, including when the server runtime is closed. “Running in background” requires a recent observation of a live eqgame.exe in this launch; “Runtime open” means Wine/display is open without that recent game observation. Wine desktop and DLL compilation are identified separately. Game-process observations refresh about every ten seconds; the management screen polls about every 2.5 seconds. A failed status check is shown as unavailable.

## Install and check

1. Camp out, stop the client and runtime, then install the APK over the existing app. Keep your installed server and dinput8.dll; no rebuild, route reinstall, client reimport or runtime download is required.
2. Start the runtime, then start the server using the same top panel. Check that the server indicator changes to Running and that duplicate start controls are disabled during startup.
3. Launch ROF2 and enter the world. Press Android Back to return to management. Visit another tab and confirm the client indicator says Running in background after its next observation. Return through Client → Return to client.
4. Review the tab artwork and Fixes layout. Open Qeynos–Erudin ferry and Refresh route if desired; do not reinstall or change the accepted working route. The retired-trial panel should offer cleanup only if a trial remains installed. No additional ferry journey is requested.
5. After camping and stopping the client, stop the server from the top panel. The runtime remains available for editing. Stop runtime when finished. Export Logs if a status remains wrong or a control fails.

Traditional EQEmu/era profiles, Ocean of Tears transit and Overthere barge work remain deferred.
