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
