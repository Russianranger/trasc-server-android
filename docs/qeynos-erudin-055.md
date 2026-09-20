# Qeynos–Erudin service, 0.5.5 candidate

Status: signed 0.5.5/code45 is published after all PR and main release gates passed. Real RoF2 crossing and berth acceptance remain required. [Download APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?build=652f898).

All 163 Python tests, eight Lua protocol scenarios, both patched pinned-server translation units, real MariaDB install/reset/removal and rollback, and phone/Thor browser checks pass. The [focused run](https://github.com/Russianranger/trasc-server-android/actions/runs/35485802194) verified code commit `9b4a60266d8a68bdf2897d27c9c4c210aa2d8ac4`; its screenshots were inspected. Database state-key comparisons use exact bytes to work across imported collations.

This route is limited to South Qeynos (1), Erud’s Crossing (98), and Erudin (24), in both directions. The accepted race 72 / gender 0 ship, relative deck height, and existing client DLL stay in use. Other boat routes and ordinary walking zone points are preserved.

The previous quests teleport nearby players to shore. This service instead creates the destination ship before a solicited zone transfer, transforms each attached passenger’s relative position and heading into the destination pose, and holds the ship while the client loads and reports attachment. A scoped native observer records actual vehicle IDs from movement packets. It does not infer boarding from proximity or the controllable-boat API. A second scoped patch prevents NPC MoveTo from snapping this managed ship to terrain.

Each boundary uses prepare / ready / receiving states with one zone writing each stage. A missing destination holds the source. Loading has a 180-second limit; failed attachment returns the passenger to the arrival dock and records failure. Disconnected passengers retain recovery tickets. Server restart returns the service to Qeynos and recovers interrupted passengers to their local dock. Removal requires clearing saved passenger positions first.

The installer allocates new ship/controller IDs, owns complete rows and five new quest files, requires a stopped server and backup, journals database/file changes, rejects intervening edits, and restores prior launcher/zone-idle settings on removal. The three route zones remain active for handoffs. Existing boat rows are untouched. The completed single-zone trial must be removed through its existing preview/removal flow first.

## Candidate setup and test

1. Park the character on shore at the South Qeynos dock, then stop the client, server and runtime and update the app. Start the existing runtime; keep the server stopped. Remove the completed Erud’s Crossing trial through its Preview removal / Save controls.
2. Build the existing pinned server source with this app and Deploy build. The app applies and records the two scoped source changes. An APK update alone cannot add native server support.
3. In Spire → Qeynos–Erudin ferry, refresh, Preview installation, then Save. Start the server. The ferry begins at South Qeynos for a 90-second boarding pause.
4. Board TRASC_Voyager at the South Qeynos docks. Verify hull/pier clearance, then remain on deck without input across Qeynos → Erud’s Crossing and Erud’s Crossing → Erudin. Allow 20–25 minutes outbound including the island stop, turns and loading; actual travel time needs device measurement. The path/speed calculation is about 18.4 minutes before initial boarding wait, turns and variable loading.
5. Verify zone loading returns you to the deck, the boat waits and resumes, and you can disembark at Erudin. Export logs upon arrival at Erudin, then test the return journey and export again; ferry-state.json contains bounded handoff history even if the native log rotates.

Keep the existing client DLL. Do not use the rejected gender-2 model test or manually edit managed SQL rows. If a crossing fails, note departure/destination zones and export logs before reset. The app status distinguishes sailing, preparing the next zone, waiting for passengers, and route faults.

Berth centers use map geometry to provide approximately 75 units between the ship origin and pier edge, with the ship parallel to the pier. Qeynos/Crossing origins are Z=-39.5; Erudin is Z=-19.5 because its pier is 20 units higher. Physical boarding clearance and RoF2 reattachment after loading remain device acceptance checks. Harbor walking speed rises from 0.5 to 0.55; open-water legs run.
