# 0.5.5 — Qeynos–Erudin ferry

One managed ferry now travels South Qeynos ↔ Erud’s Crossing ↔ Erudin. It prepares the destination ship before each zone crossing, transfers attached passengers at their deck positions, and waits while they load. Interrupted crossings recover passengers to a dock.

The accepted solid ship model and deck height are retained. Berths are aligned from dock geometry, harbor speed increases modestly, and open-water legs run. Other ferry routes remain unchanged.

## Update and setup

1. Park the character on shore at the South Qeynos dock. Stop the client, game server and runtime. Install this APK over the existing app, then start the existing runtime.
2. With the server stopped, remove the completed Erud’s Crossing ferry trial through its Preview removal / Save controls.
3. Build the existing server source and **Deploy build once** with this app. This adds the scoped server support required for passenger transfers. Keep your existing client DLL and runtime.
4. In **Spire → Qeynos–Erudin ferry**, refresh, Preview installation, and Save reviewed route change. A full database backup is created first.
5. Start the server and board **TRASC_Voyager** at South Qeynos. Ports pause for 90 seconds; the island stop pauses for 60 seconds. The three route zones stay active.

## Crossing test

Enable **Boat investigation → Record collision and passenger state**. Remain aboard through Qeynos → Erud’s Crossing → Erudin, allowing 20–25 minutes outbound. Confirm each loading screen returns you to the deck, the ship resumes, and you can disembark at Erudin. Export Logs at Erudin, then test the return journey and export again.

Use **Refresh route** to see its current phase. Export Logs after the journey, or immediately if a crossing fails; the export includes ferry handoff history. If you miss the initial departure, the ship returns on its circuit; restarting the game server places it back at Qeynos. Do not repeat the old manual model tests or rebuild dinput8.dll for this update.

Automated protocol, real-database, native-server and interface tests cover this candidate. Physical berth clearance and RoF2 reattachment after a loading screen still require device acceptance.

[Detailed route setup and test](https://github.com/Russianranger/trasc-server-android/blob/main/docs/qeynos-erudin-055.md).
