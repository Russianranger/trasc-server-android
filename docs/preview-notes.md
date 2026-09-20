# 0.5.6 — Erudin departure and diagnostic log cleanup

The Thor test confirmed outbound zone transfers. This update moves the Erudin departure offshore before the rocky shoreline where the rider detached. South Qeynos and Erudin port stops are now 180 seconds; Erud’s Crossing remains 60 seconds. Ferry speed is 0.60, with the existing harbor/open-water movement modes retained.

Erudin version-zero skiff-only spawns are disabled while the managed route is installed. Their previous settings are recorded and restored when the route is removed. Saved Erudin skiff state is cleared so old copies cannot respawn; other zones’ skiffs and NPCs remain.

## Update your installed route

1. Park on shore, stop the client, server and runtime, and install this APK over the existing app.
2. Start the existing runtime with the game server stopped. Keep the server binaries built with 0.5.5 and the existing client DLL; neither needs recompilation for this update.
3. Open **Spire → Qeynos–Erudin ferry → Preview route update → Save reviewed route change**. A full database backup and quest backup are created first. The existing route IDs and passenger recovery tickets are retained.
4. Start the server. The ship begins at South Qeynos. Use Boat investigation recording for the journey; focus on Erudin’s dock, 180-second pause and new offshore departure. Confirm skiffs are absent and you remain on deck until the return crossing into Erud’s Crossing.
5. Export Logs before resetting. The native Android export now refreshes ferry-state.json when the server runtime is available, retaining an offline copy afterward.

For a first installation, complete the one-time server Build/Deploy and remove the old single-zone trial before Preview installation.

## Log cleanup

In **Logs → Clear diagnostic logs**, stop the client and server runtime, then choose:

- **Clear files older than 2 days:** empties diagnostic text files whose last modification was more than 48 hours ago. It does not trim dated lines within recently modified files.
- **Reset all diagnostic logs:** truncates diagnostic text logs to 0 bytes, retaining the files.

Settings, build/deploy records, character chat, saved exports and backups remain. New activity writes fresh logs. Existing count-based history retention remains available.

The revised departure still needs physical Thor acceptance. Automated geometry/protocol checks do not prove client collision behavior.
