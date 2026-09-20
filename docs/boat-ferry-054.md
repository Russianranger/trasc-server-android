# 0.5.4: solid ferry and controlled passenger route

**Published:** [signed 0.5.4/code 44 APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?build=b45a028), merge `b45a02831f74cb14ad7f57c15ec3e963d5e27986`. All [main release checks](https://github.com/Russianranger/trasc-server-android/actions/runs/35473487713) passed. APK SHA256: `c5d0d6e2680039dcc1e035b2adb93b4569a1da5d8d2f0ec3c4646b2e793673aa`. The existing signing certificate is preserved.

This build adds a reversible **Erud’s Crossing ferry trial** in Spire. It uses the race-72/gender-0 `SHIP` model that the user boarded successfully, at the recorded successful origin and heading. A two-stop route exercises translation, return travel and turning through the server’s existing boat movement manager. **Passenger carrying and turning are now accepted on-device:** the user reports success and the latest capture includes over 5½ minutes of continuous attachment. Height is correct; dock XY/heading alignment and a modest speed increase remain to be tuned. Read [the device result and next tuning constraints](boat-ride-054.md). This is not a completed Qeynos–Erudin cross-zone service.

The user’s observed collision distinction is accepted: the original gender-2 `PRE` ship allowed pass-through; the higher gender-0 ship was solid but blocked boarding; the lower gender-0 ship was solid and boardable. Do not repeat the withdrawn unchanged gender-2 test. See [the boarding evidence](boat-boarding-053.md), including 63 valid vehicle-attachment samples. Race flags were already correct; no client flag override, forced attachment or graphics/DLL patch is introduced.

## Original device procedure (completed)

The user's supplied ride completes this validation. The steps below document installation and the completed test; they are not a request to repeat it. Continue using the installed ferry while the horizontal placement and speed refinement are prepared.

1. Stop ROF2, the game server and the runtime. Install the signed 0.5.4 APK over the existing app, then start the existing runtime. No runtime reinstall, source/client reimport, server build or DLL recompile is required. Keep the working client settings and deployed 0.5.3 DLL.
2. Keep the game server stopped. Open **Spire → Erud’s Crossing ferry trial → Preview installation → Save reviewed ferry change**. The app creates a full database backup and installs the ferry. The save result shows the backup path.
3. Start the server. Keep native dinput8 enabled and choose **Client settings → Boat investigation → Record collision and passenger state**. Enter **Erud’s Crossing (`erudsxing`)**, at the same dock used for the successful lower ship. Select the ferry using `/target TRASC_Ferry` and keep it selected during the ride so the capture also records any failed attachment. Do not manually spawn another ship.
4. Board during its 90-second dock pause. Release movement controls and ride through departure, the 15-second far-stop pause and return to the dock. Capture a short video covering departure and the turn if possible. If it has left, wait for its return; arrival starts another 90-second boarding pause. If it has not appeared within three minutes at the dock, stop and export logs. Do not test in Qeynos or Erudin for this build.
5. Stop the client and **Export Logs** promptly. Report whether it carries you while moving, whether turning leaves you on the deck, and whether you slide off or fall through. A visible moving ship alone is not a passenger-carrying pass.

If the ferry starts away from the dock after a previous session, stop the server and use **Preview reset to dock → Save reviewed ferry change**, then restart. Reset clears only this ferry’s saved spawn/respawn state and starts its dock pause on the next zone load. To clean up, stop the server and use **Preview removal → Save reviewed ferry change**. Do not use `#depop` as permanent cleanup for this managed spawn; it respawns. Installation, reset and removal are explicit previewed actions.

## Exact configuration

Coordinates in this table are **X, Y, Z**. The client diagnostic log prints **Y, X, Z**.

| Parameter | Value |
| --- | --- |
| Zone / ID | `erudsxing` / 98 |
| NPC name | `TRASC_Ferry` |
| Model | race 72, gender 0, texture 0, body type 1 |
| Size / flymode | 0 / 0, matching the successful `#spawn` initialization |
| Dock origin / heading | 607.125, -1782.000, -39.500 / 308.500 |
| Far origin / heading | 625.304, -1939.820, -39.500 / -1 (travel heading) |
| Route / pause type | circular / full pause |
| Dock / far pause | 90 / 15 seconds |
| Run / walk speed | 0.5 / 0.5 |

The server resolves size zero to its race/gender default, as it did for the successful command; this is not a zero-sized rendered model. Fixed waypoint Z avoids accidentally using the passenger’s deck height as the ship’s destination. The dock heading restores the successful boarding orientation; departure and return exercise ordinary boat rotation. The far point uses the pinned seed’s existing grid-59 waypoint-2 X/Y, following its dock departure corridor while retaining the lower Z. Device evidence now accepts deck support through this roughly 159-unit leg and its turns, with approximately 38 seconds of travel per leg. Dock clearance is not accepted: screenshots show hull/pier overlap. The configuration table above records the published values; proposed tuning has not been applied.

## Implementation and safeguards

The app allocates one NPC, one spawn group/entry, one spawn and a two-point grid. It does not enable or modify the four original disabled route spawns. It does not alter quests, accounts, command access, characters, client assets or closed controller/camera/particle/loading/camping/player-restoration behavior.

Previews validate the installed schema and require transactional tables. Saving requires the server stopped, a successful full backup and an unchanged preview. Content, its full-row ownership manifest and an audit record commit together. Removal/reset rejects edited owned content or unexpected additional references. Reset/removal clears only records referencing the owned spawn/group/NPC in saved zone state, respawn timers and spawn-disable state, including instances. It preserves other saved zone entities. Lost responses after commit are resolved from the transaction’s audit entry; duplicate and stale previews are rejected.

The pinned server’s [NPC constructor and spawn command implementation](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/npc.cpp), [waypoint handling](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/waypoints.cpp), [boat movement manager](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/mob_movement_manager.cpp) and [saved-state loader](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/zone_save_state.cpp) were inspected. Newly added spawn records are loaded alongside saved zone state, so installing this ferry does not require clearing the zone’s other saved entities.

Tests include a real-seed-schema MariaDB lifecycle with backup failure, stale/edited content, external references, transactional rollback, scoped saved-state cleanup, duplicate operations and lost-response recovery. Browser checks cover preview/save, the running-server guard, invalidation, errors and phone/Thor layouts. These supplement all existing release gates. Automated database and browser checks do not establish physical client collision, carrying or cross-zone handoff.
