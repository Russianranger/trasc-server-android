# 0.4.7 device follow-up: verified export, unresolved spell effects and labels

Input: `logs-6881254485975500908.zip`, uploaded September 16, 2026. The user confirms spell sounds and the name fault still fail after automatic local export. Filtering remains paused. No launcher/native code or client files were changed during this investigation; no new APK is warranted before the targeted evidence below.

## What this device run establishes

- App0.4.7/code24; Turnip24.3.4/DXVK2.5.3 on Adreno740; Balanced; exact0.4.2 NPC settings; native dinput8 and native D3DX30/35 loaded; sound diagnostics enabled.
- `control.log` records `/work/server/bin/export_client_files` at15:29:50 and successful eight-file overwrite at15:29:55. `operation.log` records both DB connections to `triune` at127.0.0.1:13306,40,922 spells,124,880 multiclass skill caps,1,600 base-data entries and44,686 database strings. The exporter queries the live configured databases and applies upstream multiclass rules; it does not generate sound or particle assets.
- Exported spells SHA256 `4762679840e788b016d83b6651866690dd344b119ff49cc4d953b292e06d7110` independently matches both installed root and Resources spell-table hashes at client launch. This rules out missed/stale spell-file copying in this run. The sync report records completion for all four files in both folders; independent installed hash comparison is available for the spell table specifically.
- Both installed spell tables contain40,922 rows/237 fields and IDs50000–50007. Filtering was not applied. `removed_rows:8` in read-only diagnostics is a hypothetical compatibility count, not evidence of eight rows actually being removed. The old logs did not capture installed spell-table IDs; this is the first direct installed-table evidence.
- Skin like Wood26 retains casting_animation42,spell_affect_index2,spell_animation216. Minor Healing200 retains43,1,278. The reviewed multiclass exporter adjusts target/class-related settings and timing fields, not these effect columns.
- ShowSpellEffects1, particle opacity1 and density1 are recorded; these alone do not prove successful effect loading. CastFilter24 is recorded but its exact semantics were not independently established, so do not rewrite it based on guesswork.
- The reader indexes all17 sound archives with no reported parse errors;1,400 references resolve in packed assets,92 remain unresolved after that scan. Six classic casting/spell WAV headers are PCM16/mono/11025 in snd2.pfs. Their presence does not establish the actual resources requested by animations216/278.
- `spellsnew.edd`1,072,040bytes, `spellsnew.eff`180,900bytes, `soundassets.txt`60,332bytes and Miles/graphics libraries are present. The log bundle contains presence/sizes, not these file contents. It also lacks the actual imported dinput8.dll binary. Do not claim to have parsed those assets or verified the installed add-on against repository source.
- Android finishes with8,134,656 frames written,8,132,736 played and3,053,372 nonzero samples. Forty underruns stabilize after loading. Retained Wine traces show a shared PCM16/stereo/22050 secondary DirectSound buffer. Counters cannot identify a spell sample within Miles' shared mix. Warnings include priority-level support, a mixer underrun and short wait/overwrite events; none establishes the selective spell failure's root cause.

## Focused source review

At server/client reference18141ae0c9a11813733f08fa77db986951b853d6:

- `client_files/export/main.cpp` reads EQEmuConfig and connects both database/content_db, then exports the four text files. `spells_new_repository.h` serializes explicit spell columns from the DB. This matches the device's exporter log and expected multiclass behavior.
- `eqgame_dll/EQData.h` defines TOTAL_SPELL_COUNT0xAFC9 (45,001 pointer slots). No expansion was found in the reviewed initialization/patch/hook files. This is a source clue, not proof of the actual installed DLL's build or the exact proprietary loader's behavior.
- `MQ2Spawns.cpp` detours SetNameSpriteState/SetNameSpriteTint, but delegates to the original functions outside GAMESTATE_INGAME. `RenderHooks.h` also intercepts frame rendering in all states. The presence of hooks warrants an add-on bypass comparison; it does not prove they are faulty. No demonstrated selection-label defect was found in the reviewed source.
- `WINEDLLOVERRIDES` already selects `dinput8=b` when the UI's imported-native-DLL checkbox is off. The file is retained. Existing normal diagnostics record requested state and native/system load evidence, so no new build is needed to verify this comparison.

Independent EQEmu developer reports describe high spell IDs exhausting client allocation and disabling particles/sounds. The actual installed high IDs make this a strong remaining hypothesis. Physical recovery is still unproven. Preserve the user's pause on filtering; do not remove/remap server spells or silently re-enable it.

## Next device evidence, using existing0.4.7

1. Stop the client. Keep Turnip/Balanced/exact0.4.2 NPC mode and native model helpers unchanged. In Client, temporarily uncheck **Load the imported native dinput8.dll**.
2. Launch only as far as character selection/creation where the name glitch is visible. Observe for10–15seconds and capture a short video. Do not enter the world for this comparison, since the add-on supplies required custom behavior. If selection cannot be reached, report that and stop.
3. Stop the client, export Logs immediately, then restore the native-DLL checkbox before normal play. A clean name with a verified bypass implicates the add-on/hook interaction; continued corruption with a verified bypass shifts investigation to the underlying client/runtime/data. Inability to reach selection is inconclusive for the name fault.
4. Attach the actual `dinput8.dll`, `spellsnew.edd`, `spellsnew.eff` and `soundassets.txt` from the imported client/original import ZIP. The Files tab can browse `client/current` and export a selected regular file; note that the current folder view returns only the first2,000 sorted entries, so files not shown can be taken from the original ZIP instead. These four files were not modified by the launcher. No full client/runtime upload is needed. Keep user-provided proprietary files out of the public repository.

The assets will allow tracing the two animation definitions and their sound references and identifying the actual add-on binary. Do not replace Miles DLLs, remove particle assets, reset the prefix, repeat failed CPU/direct-buffer experiments or claim a fix from synthetic API tests alone.

## Primary references

- [Exporter](https://github.com/Russianranger/Triptych-Triumvirate/blob/18141ae0c9a11813733f08fa77db986951b853d6/Release-NMS-Server/client_files/export/main.cpp)
- [Multiclass spell serialization](https://github.com/Russianranger/Triptych-Triumvirate/blob/18141ae0c9a11813733f08fa77db986951b853d6/Release-NMS-Server/common/repositories/spells_new_repository.h)
- [Client spell allocation declaration](https://github.com/Russianranger/Triptych-Triumvirate/blob/18141ae0c9a11813733f08fa77db986951b853d6/Release-NMS-Client/eqgame_dll/EQData.h)
- [Name hooks](https://github.com/Russianranger/Triptych-Triumvirate/blob/18141ae0c9a11813733f08fa77db986951b853d6/Release-NMS-Client/eqgame_dll/MQ2Spawns.cpp)
- [Frame hooks](https://github.com/Russianranger/Triptych-Triumvirate/blob/18141ae0c9a11813733f08fa77db986951b853d6/Release-NMS-Client/eqgame_dll/RenderHooks.h)
- [EQEmu developer reproduction](https://www.eqemulator.org/forums/showthread.php?t=40999)
- [EQEmu developer allocation explanation](https://www.eqemulator.org/forums/showthread.php?t=43069)
