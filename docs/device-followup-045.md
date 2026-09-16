> Historical investigation: **0.4.7 pauses spell filtering at the user’s request** and automatically copies the complete export into both local client folders. Follow [current testing instructions](preview-notes.md), not the earlier filtering/Prepare guidance below. The earlier installed table contents were not captured.

# 0.4.5 device results: shared name fault and missing spell sounds

## Evidence and conclusions

Inputs: `logs-3290383914200270430.zip` (Turnip) and `logs-4791697682659155649.zip` (VirGL), September 16, 2026. Extracted locally under `../analysis-045/a` and `b`. Do not commit the uploaded logs or proprietary client files.

The user reports corrupted character-selection names in both backends, footsteps in VirGL, apparently lower VirGL performance, and silent **Skin Like Wood** and **Minor Healing**. During investigation the user additionally confirmed that both spells are missing visual particles. Earlier tests established audible music, sit/stand and swinging. Both current sessions use Balanced, native dinput8 and native D3DX30/35 at 1280×720 fullscreen. Turnip uses exact `compatibility_042`. No controlled FPS comparison is claimed.

**Reject a DXVK-only explanation for the name defect.** Both backends reproduce it. This does not identify the shared fault: client code/data, add-on hooks, native helpers, Wine and CPU translation remain candidates. The previously rejected direct-buffer and Legacy math experiments must not be repeated as proposed fixes. Keep Turnip + Balanced + exact 0.4.2 NPC compatibility for normal play.

The new packed inventory works on the real installation. All 17 `snd<number>.pfs` archives were indexed without truncation or parse errors. Of 1492 references unresolved as loose files, **1400 resolve inside archives**; 92 remain unresolved. Neither count identifies which resource these two spells request. `spelcast.wav` and `spell_1.wav` through `spell_5.wav` are all present in `snd2.pfs`, with PCM format tag 1, mono, 11025 Hz, 16-bit headers. They are not among the float-format loose files seen in earlier generic samples. This validates the index and header reader, not full sample integrity or ROF2 event-to-resource mapping. `spellsnew.edd`, `spellsnew.eff`, `spells_us.txt`, Miles libraries and `eqgraphicsdx9.dll` are present. Do not extract/replace sounds or download unrelated Miles DLLs on this evidence.

The separately retained lifecycle traces now capture startup. Each game session creates one secondary DirectSound buffer: **PCM16 stereo, 22050 Hz, 69120 bytes**, with GLOBALFOCUS and GETCURRENTPOSITION2, without CTRL3D. The game/Miles keeps filling that shared buffer; the retained lifecycle record does not show separate spell buffers. The earlier synthetic positional-buffer fixture therefore does not reproduce this game path.

| Session | Submitted frames at final stop | Played frames | Nonzero samples | Underruns |
| --- | ---: | ---: | ---: | ---: |
| Turnip | 10,953,120 | 10,953,120 | 1,657,019 | 14 |
| VirGL | 10,665,696 | 10,665,696 | 2,659,714 | 3 |

The Android stream advances through silence and drains at stop. No audio-device failure or rejected buffer format is identified. Startup/loading warnings include probable underruns and a mixing-position overwrite; these do not identify the silent casts. Working unrelated effects plus the single stereo mix point toward game/Miles resource selection or mixing upstream of Android, without proving a root cause. Pre-launch SoundVolume20 is not evidence that the user's later in-game volume was low.

## Source review and remaining boundary

Reviewed the custom client at upstream commit `4c653ca2d16aaede33b7011d07254c520ac5f5df`:

- [MQ2Spawns.cpp](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Client/eqgame_dll/MQ2Spawns.cpp) installs name-sprite hooks, whose detours call the original functions outside the in-game state. This is a reason to isolate add-on involvement, not proof those hooks are faulty. The installed DLL has not been established to match this source commit.
- [RenderHooks.h](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Client/eqgame_dll/RenderHooks.h) intercepts frame rendering; FloatingTextManager draws damage text. No demonstrated defect in the actual selection-label path was found.
- The launcher delegates spell-file generation to the upstream exporter. The reviewed repository serializes explicit spell columns and applies multiclass adjustments; the uploaded diagnostics contain file presence/size, not the actual two spell rows or effect mappings. No export corruption has been established.

At this point the audio/renderer logs alone did not justify a playback/rendering correction. The later particle confirmation led to the concrete out-of-range spell-table defect and the 0.4.6 client-data correction in [spell-effects-046.md](spell-effects-046.md). The preceding verified release is 0.4.5/code22, source `49e26507c6b04968bdcf2b4fd999f8b5f5717a3f`, SHA256 `93f29605c371309d0ce61643542145fca83385d98c2f8945dc71d3c02ba319fb`.

## Follow-up after particle confirmation

The question about particles is answered: **they are absent too**. Do not ask it again or repeat the completed renderer/CPU tests. The original pinned seed and device export both contain40,922 rows; seed analysis finds eight unsupported IDs50000–50007. Proceed with the 0.4.6 export correction and Prepare instructions in [preview-notes.md](preview-notes.md). Keep the add-on enabled for that comparison to isolate the data change.

If the name remains corrupted after applying the corrected table, stop the client, keep Turnip/Balanced/NPC compatibility/model helpers, and temporarily uncheck **Load the imported native dinput8.dll** only for a ten-second selection-label comparison. Stop/export and restore the checkbox before normal play. If selection cannot be reached, report that result and restore it. This remains a separate add-on isolation test, not an established fix or a playable configuration.
