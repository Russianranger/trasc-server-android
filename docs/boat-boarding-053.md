# Stationary ship boarding confirmed — 2026-09-19

The user reports that the gender-0 ship has collision and was boardable after spawning it lower. The new video shows movement aboard the wooden ship, and the V2 log independently records the player's vehicle pointer resolving to that ship. **Stationary boarding and vehicle attachment now work on the existing 0.5.3 build.** No collision patch was needed for this result.

This supersedes the blanket unresolved-attachment wording in [the previous TBT report](boat-tbt-053.md). The user subsequently clarified that the higher spawn of the working variant already had solid collision that prevented entry, while the original gender-2 model allows pass-through. Accept this distinction. **The proposed repeat of the gender-2 collision test is withdrawn at the user's direction.** Moving passenger transport and route handoff remain untested.

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

The second ship is 19.125 units lower, and X/Y/heading also changed. The initial interpretation incorrectly treated the missing attachment on the higher spawn as grounds to repeat the old model's collision test. The user clarified the physical observations:

- The higher spawn of the gender-0 working variant had collision and blocked boarding even when the player was level with its deck.
- The lower gender-0 ship had solid sides and allowed boarding; the existing log independently confirms 63 attached samples.
- The original gender-2 variant being proposed for another test does not have collision in the user's current client setup. Repeating that unchanged test is rejected by the user.

Record the gender-2 failure as user-confirmed, with its earlier no-attachment trace as supporting evidence. Do not reopen a height-only explanation as a reason to ask for the same failed test. The precise cause inside the model assets or client collision setup is still unknown; this does not establish that every installation's `PRE` asset is defective. Further testing of that variant requires a concrete change that addresses the observed failure, not another unchanged spawn command.

The original client registration maps race 72/gender 0 to `SHIP`, and genders 1/2 to `PRE`, all with race flags 3. The previously saved offline verifier establishes this mapping. The pinned seed's race-72 route NPCs 24301, 98053 and 98054 use gender 2, size 6 and body type 11; the synthetic tests use body type 1. The fourth disabled route NPC, Qeynos Golden_Maiden 1173, uses race 533. Preserve those differences when designing the route test. The existing installed screenshot and pinned seed show all four route spawns disabled; their nonarrival is still a separate server-data issue.

Use the known solid **race 72 / gender 0 (`SHIP`)** for the next controlled single-zone rotation and passenger-carrying investigation. Its successful placement was X 607.125, Y -1782.000, Z -39.500, heading 308.500; the logger prints **Y,X,Z**. This is a local reference, not a database-wide Z correction. Keep the existing 0.5.3 APK, DLL and working settings. Both previous cleanup commands are already recorded.

The source review identifies a distinct next test: the existing `#movement rotate` command turns the selected NPC toward the player's X/Y using the ordinary movement manager. A player standing aboard and off to one side can therefore exercise rotation and attachment without changing the ship's height. The manager updates the authoritative heading and sends rotation/start-stop packets; this is more useful than a visual-only packet injection. A zero-angle request does not rotate, so a trace with no heading change would not test carrying.

Before issuing executable device instructions, establish access to that command: its compiled default is `AccountStatus::GMMgmt`, whereas `#spawn` defaults to `Steward`, and installed `command_settings` can override either. Existing spawn access alone does not establish movement-command access. No account permissions or command access were changed in this follow-up. Do not silently raise the user's account status or ask for another collision capture to work around this setup issue.

Rotation acceptance requires an actual ship-heading change while the player remains attached and is carried relative to the deck with movement input released. Continue to use `vehicle_valid`/vehicle ID and positions, not the separately logged `passenger` byte. Translation then needs a fixed endpoint at the ship's proper Z; the existing `#movement walk`/`run` commands target the player's current X/Y/Z, so using them while aboard would mix deck height into the destination. Prepare the controlled transport setup before asking for that test. Full route enablement and model replacement remain separate changes, to be limited to the tested route/model rather than all boats at once.

## Source and verification record

The pinned server's [spawn command](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/gm_commands/spawn.cpp) confirms argument order, numeric-name stripping and use of the player's current position. The [pinned seed](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/database/release-peq.zip) is the source of the route NPC values above, not proof that every field is unchanged on the device.

Rotation/translation preparation was checked against the pinned [movement command](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/gm_commands/movement.cpp), [movement manager](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/mob_movement_manager.cpp) and [command registration](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/command.cpp). This is source inspection, not device acceptance of movement or a completed transport helper.

This follow-up changes documentation only. Parsed every current V2 sample, compared both spawn commands and cleanup commands, inspected video frames, checked deployed header hashes and ran `git diff --check`. No product code, database, client asset or settings were modified; no APK was built. The signed 0.5.3 release remains current. Preserve all closed controller, camera, loading, particle, camping and player-restoration milestones.
