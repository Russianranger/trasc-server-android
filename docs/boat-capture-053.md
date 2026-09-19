# Boat capture follow-up — 0.5.3

**Subsequent device result:** [TBT capture and next comparison](boat-tbt-053.md) records a successful V2 capture of the selected ship, with race flags 3 and no sampled attachment. The earlier missing-target capture below is historical. Do not repeat its completed compile/deploy steps for that device.

The user can now target the temporary ship but reports walking through it. This confirms a failed solid-collision test, not a successful boarding or passenger test. Collision, attachment, movement and route handoff remain unresolved.

## Device and source findings, 2026-09-19

- The installed-database screenshot shows all four Qeynos/Erudin transport spawns disabled. The pinned Triptych seed agrees; `zone/spawn2.cpp` honors the disabled state. Waiting at these docks cannot test their scheduled arrivals while disabled. Do not enable entire routes yet.
- `#spawn TRASCBoatTest 72 1 0 10000 2 1 0 0 0 11` was an incorrect targeting test: the last argument selects body type 11, Untargetable. The screenshot confirms that type; the earlier video shows a visible ship model but does not establish collision. This instruction was corrected to body type 1 below. `IsBoat` uses the race classification, independently of that body type.
- The user reports successful targeting with the corrected test, but can only pass through the ship. A synthetic NPC with body type 1 does not establish behavior of the original body-type-11 route boats. Preserve that distinction.
- Latest supplied export: `logs-904919649256838973.zip`, status version 0.5.2, created `2026-09-19T18:59:57.180565Z`; native DLL loaded and boat mode `profile`.
- Its current `client-boats.log` has exactly 512 samples, 255,169 bytes, from ticks 395933816 to 398516326 (43.04 minutes). Every sample has `target_valid=0`, `vehicle_valid=0`, `vehicle_ptr=00000000`. Two samples are outside valid world state, 40 are Erudin (24), 470 are Erud's Crossing (98); the final 200 repeat the same position. These are idle/earlier observations, not a trace of the reported targeted ship.
- Server logs place the player in Erudin at 18:03:53, Crossing at 18:07:35, idle at 18:42:27, then active again at 18:54:15 and leaving at 18:59:30. The boat recorder exhausted its quota before that late activity. There is no evidence here to assign the failure to ship flags, collision assets, server packets or the graphics driver.
- The original adapter had two independent permanent stops: 512 reports and the shared logger's 256 KiB ceiling. Removing only one would still lose later evidence. Client logs do not enumerate all zone entities; absence of a selected/attached ship is not proof that none spawned. The server's `Loaded [n] spawn2 entries` message counts its respawn-timer list in this fork, not total live NPCs.

| Zone | Ship | NPC type | Spawn | Grid | Disabled |
| --- | --- | ---: | ---: | ---: | ---: |
| qeynos | Golden_Maiden | 1173 | 21341 | 0 | 1 |
| erudnext | Sea_King | 24301 | 58420 | 0 | 1 |
| erudsxing | Golden_Maiden | 98054 | 58419 | 59 | 1 |
| erudsxing | Sea_King | 98053 | 58421 | 61 | 1 |

The Qeynos Golden_Maiden uses race 533 in this seed; the other three use race 72. Source: [pinned Triptych server](https://github.com/Russianranger/Triptych-Triumvirate/tree/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server), including `database/release-peq.zip`, `zone/spawn2.cpp`, `zone/gm_commands/spawn.cpp`, `zone/npc.cpp`, `zone/gm_commands/list.cpp`, `zone/gm_commands/kill.cpp`, `zone/gm_commands/depop.cpp` and `common/bodytypes.h`.

## Capture correction

0.5.3/code 43 replaces the boat recorder's finite quota with continuous bounded rotation. `client-boats.log` and `client-boats-rollover.log` each hold at most 256 KiB; the rollover file precedes the current file. Old segments are overwritten as needed. Export promptly after a test, because these files intentionally retain only recent history. Both are archived by the existing retention policy on the next launch and included by Export Logs.

The rate remains at most two selected/attached-ship records per second and one idle heartbeat per five seconds. State inspection itself is now limited to twice per second, including idle periods. Tick wrap is handled by unsigned subtraction. Failed I/O drops a sample and retries on later scheduled samples, without growing past the limit.

`TRASC_EQ_BOATS_V2` and `boats=v2` distinguish the corrected build. The launcher requires the V2 DLL marker; an older V1 DLL reports `needs_dll`. Both inherited V1/V2 enablement variables are reset before validated configuration. No client memory writes, collision overrides, forced attachment, server rules or asset replacements were added. The shared camera/particle log behavior is unchanged.

## Next device test

1. Stop ROF2, the game server and runtime. Install the signed 0.5.3 preview over the existing app, then start the existing runtime. Keep the working settings. No server build, runtime reinstall, toolchain/source refresh or client reimport is needed.
2. With the server stopped, compile and deploy `dinput8.dll` once using this app and the existing imported source/SDK. An APK update alone does not replace the previously deployed DLL. Start the server.
3. Enable **Boat investigation → Record collision and passenger state**, leave native dinput8 enabled, then launch the client. Confirm the launcher says boat diagnostics are active, with no compile/deploy warning.
4. Use the same zone and dock where the pass-through was reproduced. Reuse the test ship if present. Otherwise spawn exactly one temporary, targetable race-72 ship:

   ```text
   #spawn TRASCBoatTarget 72 1 0 10000 2 1 0 0 0 1
   /target TRASCBoatTarget
   ```

   The final argument is **1**, not 11. The command spawns at the player's position, so step away to view it. Keep it selected for 10 seconds; approach and try to board/walk through it for 20–30 seconds. Record zone/name and approximate time. A short video helps correlate visible contact with snapshots. Do not wait for the disabled route boats or change zones during this test.
5. With only the temporary test ship selected, use `#depop` to remove it, then stop the client and Export Logs immediately. If an earlier untargetable test ship remains, `#list npcs TRASCBoatTest` gives its live entity ID; `#kill ID` operates on that ID without a target. Do not use the database NPC type or spawn ID there. Temporary NPCs have no new database spawn/grid row, but zone-state saving can preserve dynamic NPCs, so remove the test entity explicitly.
6. If the earlier test temporarily raised the account containing Fiweo from status 0 to 50, restore status 0 after testing with the server stopped and existing SQL backup/write controls. Do not change an account that already had another status. No additional GM privilege change is needed if the commands already work.

A useful new log has `boats=v2`, `target_valid=1`, `target_name=TRASCBoatTarget...`, `target_race=72` while approaching the ship. Check actor/flags, player/ship heights, floor/wet state and the vehicle pointer across contact before selecting the next code or asset investigation. A continuing null attachment does not by itself prove why collision was missed. The private graphics/client binaries and original-code verifier described in [the 0.5.2 investigation](boat-investigation-052.md) remain relevant; do not invent a forced-attachment fix.

## Verification

Local Python regression suite: 147 tests pass, including old-DLL rejection and inherited-mode clearing. JavaScript syntax and whitespace checks pass. The Microsoft x86 fixture now covers two idle hours followed by ship capture, another active hour, tick wrap, repeated log rollover, exact segment bounds, a locked rollover file and recovery, alongside existing read-only snapshot and client-identity checks. Full CI and publication status are recorded in [HANDOFF.md](HANDOFF.md). Subsequent TBT evidence accepts selected-ship V2 capture on the device; on-device long-session rollover and the collision repair remain unproven.
