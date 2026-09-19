# TBT device capture — 2026-09-19

**Subsequent result and user clarification:** [Stationary ship boarding confirmed](boat-boarding-053.md). Gender 0 has solid sides and attaches the player after lower placement (63 samples). The user confirms the original gender-2 model allows pass-through and explicitly rejects repeating that unchanged failed collision test. The earlier height-comparison proposal is withdrawn. Use the working gender-0 model for the next movement/carrying investigation; the source of the original model's failure still needs investigation.

The user's TBT video shows a visible, selected ship and movement through its wooden model. The accompanying 0.5.3 capture records that exact target with working vehicle classification and no sampled passenger attachment. Boat collision remains unresolved. This supersedes the missing-target evidence in [boat-capture-053.md](boat-capture-053.md).

## Confirmed evidence

Inputs were the user-supplied `logs-1735854186408412618.zip` and `TRASC Server Preview_2026-09-19 15_52_31.mp4`. The export was created at `2026-09-19T20:54:06.294541Z`; the 10.734-second video has creation metadata `2026-09-19T20:52:31Z`. Do not treat that metadata as a frame-to-log synchronization measurement. Private inputs are not committed.

The app reports 0.5.3, native dinput8 loaded and boat mode `profile`. The deployed DLL is 1,720,832 bytes, SHA256 `836a538a05391286406989ef97ac310a3d0410cd63369e209238bb7762241930`; its seven injected header hashes match the released source. The V2 recorder captured 198 samples over 516.214 seconds. Twenty are outside the world and 178 are in Erud's Crossing, zone 98.

| Selected-ship evidence | Value |
| --- | --- |
| Name / entity ID | `TBT000` / 107 |
| Samples / interval | 112 / ticks 403326254–403382849, 56.595 seconds |
| Race / known race flags | 72 / 3 in every selected sample |
| Graphics actor pointer | `1d5ab960`, nonzero and unchanged |
| Ship Y, X, Z / heading | -1766.750, 636.125, -20.625 / 237.500 |
| Player vehicle pointer / valid / passenger | Zero / false / zero throughout |
| Player movement | 77 distinct positions; wet field 5 in 36 selected samples and 0 in 76 |

The server log independently records `#spawn TBT 72 1 0 10000 2 1 0 0 0 1`, `Hail, TBT`, and `#depop`. The screenshot/video confirms the targetable body type 1. The final cleanup command was issued; do not ask the user to remove this same entity again without evidence it survived.

This accepts **V2 capture of the selected test ship on the device**. This short capture did not exercise on-device log rollover or a long idle period; those remain covered by the existing synthetic tests. A nonzero actor pointer does not prove a collision mesh exists, and 500 ms samples cannot exclude a brief attachment between samples. Passing through a hull also does not independently establish that the character approached the deck from above.

## Original-client checks and remaining unknowns

The exact private executable and graphics DLL were recovered and checked against the existing pinned identities:

- `eqgame.exe`: SHA256 `4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3`.
- `EQGraphicsDX9.dll`: SHA256 `164fc072547aab752567ba88bf6936d0e328c44a16a1480f340d27aef0ba6290`.

The original floor-query actor filter at preferred executable address `0x476280` rejects an actor when bit 0 of its **graphics collision restriction mask** is set. This mask is separate from the race flags in the current log. With a model collision volume, masks 0, 2 and 128 pass this filter; masks 1, 3 and 129 fail. For the accepted synthetic actors, the original attachment callback at `0x475f40` attaches the player with race flags 3. All six combinations execute in the offline verifier; they do not establish the live ship's mask.

The floor routine at `0x507230` clears the old vehicle pointer before making a fresh collision query with that filter and callback. A sampled null pointer therefore cannot distinguish a rejected/missed collision from a short-lived attachment.

Actual graphics accessors in the pinned DLL confirm actor-relative collision mask `+0x148` and collision-volume type `+0x164` for its hierarchical/simple actor implementations. These values are **not recorded by V2**. Do not use public structure comments blindly: some offsets differ from this DLL. Public interface reference: [pinned eqlib graphics Actors.h](https://github.com/macroquest/eqlib/blob/3eafc8217e690b3c93201a17ec205410db1cac82/include/eqlib/graphics/Actors.h). Any future recorder extension must validate the exact graphics image and actor implementation before reading these fields; a pointer alone is insufficient. No such extension or memory patch has been shipped.

The executable's original race-table registration also gives a useful controlled model comparison:

| Race | Gender argument | Registered model tag | Race flags |
| --- | ---: | --- | ---: |
| 72 | 0 | `SHIP` | 3 |
| 72 | 1 | `PRE` | 3 |
| 72 | 2 | `PRE` | 3 |

TBT used gender 2. The verifier executes the three original registration call sites with a recording substitute for table insertion and checks all arguments. This proves the built-in mapping, not which assets the live client eventually resolves or whether either model is solid. The custom client source's model-loading overrides remain a possible influence. The available export does not contain the model archives or a live collision-mask dump.

## Next single comparison on the existing APK

Keep 0.5.3, the deployed DLL and the working settings. No APK/DLL rebuild, server rebuild, runtime reinstall or route enablement is needed. Use the same Erud's Crossing dock and spawn point, with native dinput8 and boat recording enabled:

```text
#spawn TBT0 72 1 0 10000 0 1 0 0 0 1
/target TBT0
```

The argument immediately after `10000` changes from **2 to 0**, selecting the other built-in model; the final body-type argument stays **1**. Spawn only one test ship, step away, and keep it selected while attempting to board for 20–30 seconds. Where the dock geometry permits, try stepping or jumping down onto the deck; distinguish standing on the deck from simply walking through a side. Record whether it renders as a ship, supports the player, or still permits pass-through. If it does not render as a ship, report that instead of treating it as a collision result. Remove the selected temporary ship with `#depop`, stop the client and export logs promptly.

If this variant is solid, compare the resolved `PRE`/`SHIP` model assets and definitions. If both fail a deck approach, the next useful recorder change is guarded actor type/volume/mask/model information at contact. Repeating the unchanged V2 test or forcing the already-present race flag cannot distinguish those possibilities. Do not enable the four disabled route spawns until single-zone collision and passenger carrying are demonstrated.

## Repository changes and validation

This follow-up changes only investigation documentation and the private-input offline verifier, `tools/verify-client-boats.py`. All 17 original-code cases pass against the pinned executable, including the previous ten cases, six mask-filter cases and model-registration case. Python syntax and `git diff --check` pass. No application, runtime, server, graphics, input or packaged header changes were made; no new APK or collision repair is claimed. The signed 0.5.3 release identity remains the one recorded in [HANDOFF.md](HANDOFF.md).
