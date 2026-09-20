# 0.5.4 device result: ferry carrying and turning accepted

The user reports that the ferry works, its height is correct, its horizontal placement is off, and it is slightly slow. The four supplied screenshots show the wooden hull overlapping the Erud's Crossing pier. This accepts boarding, moving passenger support and turning for the managed single-zone ferry. Dock clearance and speed refinement remain open, as does full Qeynos–Erudin cross-zone service. Do not repeat the rejected unchanged gender-2/PRE collision test or request another unchanged carrying test.

## Evidence

Inspected all four screenshots (`20260919-210135`, `210117`, `204659`, `204644`) and `logs-5331243628418525720.zip`, SHA256 `8310ee93e15ff59cc67b8403997d6d7c5941dafe5261f3fea4b4e9556bf9ca70`. Despite the attachment-path error text in the conversation, the local files were readable. The export was created at `2026-09-20T02:02:48.564835Z` on 0.5.4. Raw logs and images remain private and uncommitted.

The current capture consists of `client-boats-rollover.log` plus `client-boats.log`; the previous capture is `client-boats.previous.log`. Treat these as separate client launches. The older `previous.2` file belongs to the earlier stationary test and is excluded.

| Measurement | Current launch | Previous launch |
| --- | ---: | ---: |
| V2 samples | 790 | 391 |
| Selected `TRASC_Ferry000` samples | 784 | 386 |
| Attached samples, matching valid vehicle and target IDs | 650 | 377 |
| Longest consecutive attachment | 649 samples / 331.365 s | 304 samples / 154.928 s |
| Straight-travel sample pairs with zero movement input | 87 | 53 |
| Maximum difference between player and boat XY displacement | 0.121 units | 0.156 units |
| Turns with zero movement input | 5 | 3 |
| Maximum change in passenger radius during those turns | 0.094 units | 0.118 units |

Straight-travel comparisons require both samples attached, less than 1.1 seconds apart, boat XY movement above 0.1 units, and heading change below 0.1 of the client's 512 heading units. Turn comparisons require stationary boat XY within 0.1 units and heading change above one heading unit. During all eight turns the passenger's offset bearing changes with the boat heading, accounting for the coordinate convention's opposite sign. This is actual translation and rotation while aboard, with reported movement speed zero, not merely a visible moving NPC.

The current continuous attachment runs from tick 318473 to 649838: over 5½ minutes. Every attached sample has `wet=0`. The separately logged `passenger` byte remains zero and is not the acceptance criterion. The valid vehicle pointer/ID, displacement and rotation establish attachment. Rollover and continuation of V2 capture are also observed on-device in this export.

All selected ferry samples have client Z `-39.375`. The configured database Z is `-39.5`; preserve that working value. Do not change it to compensate for the representation difference. The current dock is X `607.125`, Y `-1782`, heading `308.5` (approximately `308` after a return). The far stop is observed at X `625.25`, Y `-1939.75`, with the same Z. Logs print Y,X,Z; database fields and the coordinates here use X,Y,Z.

Travel from the last dock sample to the first far-stop sample, or vice versa, takes approximately 38 seconds for the roughly 159-unit leg. Use elapsed endpoint-to-endpoint time: averaging only samples with coordinate jumps overestimates speed because position updates arrive in steps. Full dock pauses are approximately 90 seconds; the configured far pause is 15 seconds, with turning and sampled arrival/departure adding time to the observed stationary interval.

Native dinput8 is loaded in both launches. The deployed DLL remains SHA256 `836a538a05391286406989ef97ac310a3d0410cd63369e209238bb7762241930` (1,720,832 bytes); all seven recorded adapter-header hashes match the repository. No client/DLL fix is indicated by this result.

## Remaining tuning

1. **Dock XY and heading:** the screenshots establish hull/pier overlap. The dock pose was copied from the successful manual boarding spawn, so it was a boarding reference, not a surveyed berth for this hull. Evaluate horizontal offset and orientation together. The later shore viewpoint in the log is not a desired ship origin. No exact corrected XY or heading can be established from these screenshots alone; obtain dock/model geometry or a deliberate berth reference before assigning replacement coordinates. Check departure and return clearance as well as the stationary berth. Preserve Z `-39.5`, race 72/gender 0, size and flymode.
2. **Small speed increase:** the source-supported next candidate is `runspeed=0.55`, from `0.50`. The pinned server derives integer walking speed as `int(runspeed * 40) * 100 / 265`: this raises the ferry's base walking speed from 7 to 8, about **14.3%**, suggesting roughly 33–34 seconds for the unchanged leg. This is a prediction, not a measurement of a deployed change. `0.60` would yield 9, about 28.6% faster, which is a larger step than the user's feedback warrants. The NPC constructor passes runspeed to `Mob`; editing the database walkspeed field alone does not implement this adjustment in the pinned constructor path. Keep the boarding pauses unchanged unless the user asks to shorten the waits.
3. **Managed update:** direct SQL or general Spire edits to the ferry's owned rows would invalidate the full-row manifest and block reset/removal. Any tuning must update content and ownership together through a supported operation, or use the existing backed-up removal and reinstall with revised defaults. Preserve scoped saved-state cleanup and the successful working height. Another APK should include a concrete placement correction and the modest speed change, with the normal release gates retained.

Speed behavior was checked against the pinned [Mob constructor and walking-speed calculation](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/mob.cpp), [NPC constructor](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/npc.cpp) and [movement manager](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/mob_movement_manager.cpp).

This follow-up records device acceptance and prepares the next tuning decision; it changes documentation only. No coordinates, speed, database content or product code have been changed. The signed [0.5.4 APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?build=b45a028) and deployed DLL remain current. Preserve all closed controller, camera, particle, loading, camping and player-restoration milestones. No subagents used.
