# Stationary ship boarding confirmed — 2026-09-19

The user reports that the gender-0 ship has collision and was boardable after spawning it lower. The new video shows movement aboard the wooden ship, and the V2 log independently records the player's vehicle pointer resolving to that ship. **Stationary boarding and vehicle attachment now work on the existing 0.5.3 build.** No collision patch was needed for this result.

This supersedes the blanket unresolved-attachment wording in [the previous TBT report](boat-tbt-053.md). The original gender-2 model, moving passenger transport and route handoff still require separate evidence.

## Device evidence

Inputs: `logs-642380592878288980.zip`, exported at `2026-09-19T21:23:51.593423Z`, and `TRASC Server Preview_2026-09-19 16_22_30.mp4`, duration 10.763 seconds with creation metadata `2026-09-19T21:22:30Z`. The video was visually inspected; its metadata is not treated as an exact frame-to-log clock alignment. Private attachments are not committed.

The app is 0.5.3, native dinput8 is loaded, and boat mode is `profile`. Deployed DLL SHA256 remains `836a538a05391286406989ef97ac310a3d0410cd63369e209238bb7762241930` (1,720,832 bytes); all seven adapter-header hashes match the existing release source. No intervening APK/DLL change explains the result.

There are 283 V2 samples in the 145,571-byte current log, ticks 404858398–405222467 (364.069 seconds): 280 valid-world samples in Erud's Crossing (98), three outside the world. The server's `zone-dynamic_02.log` records two identical `#spawn TBT0 72 1 0 10000 0 1 0 0 0 1` commands, with `#depop` between them, then a hail and final `#depop`.

| Observation | First ship | Lower replacement |
| --- | ---: | ---: |
| Live entity ID | 107 | 108 |
| Selected samples | 146 | 93 |
| X | 627.375 | 607.125 |
| Y | -1763.250 | -1782.000 |
| Z | -20.375 | -39.500 |
| Heading | 240.500 | 308.500 |
| Samples attached to that entity | 0 | **63** |

Both targets are logged as `TBT000`, race 72, known race flags 3, graphics actor pointer `1c1aee38`. Numeric characters are stripped from spawn names by the server, so `TBT0` is not a distinct displayed name. Use alphabetic suffixes in future comparisons. The repeated actor address does not establish continuity across the two different entity IDs; it can reflect memory reuse.

For all 63 attached samples, `vehicle_ptr=29397458`, `vehicle_valid=1`, `vehicle_id=108`, and `vehicle_flags=3`. The first and last attached samples are ticks 405139186 and 405173916, with intervening detachments; the longest uninterrupted sampled attachment lasts 22.926 seconds (46 samples). All attached samples have `wet=0`. The player moves while the vehicle position and heading remain fixed. This is evidence of standing/walking on a stationary ship and attachment; it is not a moving-passenger test.

The separately logged byte `passenger` remains zero even during these confirmed attachments. Do not require `passenger=1` as a boarding acceptance criterion or treat its zero as overriding the valid vehicle pointer. The original attachment callback already verified offline changes the vehicle pointer alone. Do not repurpose that byte without tracing its separate meaning.

## Interpretation and next decision

The second ship is 19.125 units lower, and X/Y/heading also changed. The user's boarding report and the trace support placement as an important factor, but this was not a height-only experiment. The earlier gender-2 `PRE` attempt was around Z -20.625; it has not been retested at the successful lower placement. Therefore this capture does not prove `PRE` lacks collision or justify replacing every route boat with gender 0.

The original client registration maps race 72/gender 0 to `SHIP`, and genders 1/2 to `PRE`, all with race flags 3. The previously saved offline verifier establishes this mapping. The pinned seed's race-72 route NPCs 24301, 98053 and 98054 use gender 2, size 6 and body type 11; the synthetic tests use body type 1. The fourth disabled route NPC, Qeynos Golden_Maiden 1173, uses race 533. Preserve those differences when designing the route test. The existing installed screenshot and pinned seed show all four route spawns disabled; their nonarrival is still a separate server-data issue.

The next narrow check uses the original model at the lower location, without changing the application or race flags. Keep native dinput8 and boat recording on. In Erud's Crossing, return to the **same lower spawn point and facing used for the successful second ship**, then run:

```text
#spawn TBTLow 72 1 0 10000 2 1 0 0 0 1
/target TBTLow
```

Only the gender/model argument after `10000` changes back to **2**; the final body-type argument remains **1**. The alphabetic name distinguishes it in the log. The successful placement to aim for is X 607.125, Y -1782.000, Z -39.500, heading 308.500; the boat recorder prints coordinates in **Y,X,Z** order. Do not automatically set a database-wide Z offset from this one test. The spawn command uses the player's position at execution, so the subsequent capture must confirm the actual ship position.

Try reaching the deck from the dock/above for 20–30 seconds while selected. The model shapes differ, so the same origin does not guarantee identical deck height or boarding geometry. Record actual support versus side pass-through. Remove only the selected test ship with `#depop`, stop the client and export logs. Both earlier cleanup commands are already in the supplied server log; do not ask to clean up those same entities again absent evidence they survived.

If the original model supports and attaches the player, proceed to a controlled single-zone movement/rotation test with a temporary ship. If it still cannot be boarded, inspect model collision data and deck placement before changing route NPC definitions. The now-confirmed gender-0 ship is a positive control for future diagnostics. Do not force attachment, rewrite already-correct race flags, or require another diagnostic APK for this placement comparison.

## Source and verification record

The pinned server's [spawn command](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/gm_commands/spawn.cpp) confirms argument order, numeric-name stripping and use of the player's current position. The [pinned seed](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/database/release-peq.zip) is the source of the route NPC values above, not proof that every field is unchanged on the device.

This follow-up changes documentation only. Parsed every current V2 sample, compared both spawn commands and cleanup commands, inspected video frames, checked deployed header hashes and ran `git diff --check`. No product code, database, client asset or settings were modified; no APK was built. The signed 0.5.3 release remains current. Preserve all closed controller, camera, loading, particle, camping and player-restoration milestones.
