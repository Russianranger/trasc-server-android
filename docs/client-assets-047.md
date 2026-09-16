# 0.4.7 supplied client assets: spell definitions and actual add-on

**Update:** the subsequent Winlator test also has silent spells, and the user explicitly authorized the eight-ID exclusion comparison. Follow the 0.4.8 instructions in [preview-notes.md](preview-notes.md); the pause below is historical.

Input: `trasc_launcher.zip`, supplied September 16, 2026 after the completed native-DLL bypass. It contains exactly the four requested files. Analysis was read-only. No client asset, database, launcher or native runtime was modified; no new APK was built. The user's pause on filtering remains in force.

## File identities

| File | Bytes | SHA256 |
| --- | ---: | --- |
| dinput8.dll | 3,445,760 | `0a59be5dbd0c746ecd4168d3628b056dc490e0eabbaa6050c3d533802b13465b` |
| spellsnew.edd | 1,072,040 | `db678ea0c6a444ffd3c9eb33f64182e0e1e6f88dc188b668cab90a296f081577` |
| spellsnew.eff | 180,900 | `e61694a8e11189c8ef0bb20da9665b37979ac867bb5f8a97d9fc6562eacbc873` |
| soundassets.txt | 60,332 | `cff621177d9a9e8b525e663a364370dae87990eca34e9f4384aa4d9e33dd5f6b` |

The three asset sizes match the earlier device inventories. Those inventories did not hash these assets, so matching sizes alone do not independently prove the uploaded originals equal the currently installed files. Do not commit the uploaded files or disassembly to the public repository.

## Effect records are present and references are consistent

EFF has exactly 675 records of 268 bytes, with no trailing partial record. Each record consists of a 64-byte name and three 68-byte stages; each stage has a signed 32-bit sound ID and four 16-byte emitter records (`EmitterType`, `MinLevel`, `AttachType`, `DAGnum`). This matches [Evie's parser](https://github.com/solar984/evie-spells/blob/4b5998dc5daacbf370e3fc9c265115fa3306f6ff/EQSpellEffectsNew.cs). Its [spell detail implementation](https://github.com/solar984/evie-spells/blob/4b5998dc5daacbf370e3fc9c265115fa3306f6ff/Template/SpellDetailModel.cs) indexes these records directly by spell animation, with stage 0 for caster sound and stage 2 for target sound.

EDD begins with `EDD\0` + `110\0`, then exactly 2,577 records of 416 bytes. The first two 64-byte fields contain the emitter label and texture name. This layout agrees with the EDD reader in [willeq](https://github.com/wcassis/willeq/blob/7a8162a932d8eae81f1b5cc2f7d7a0210f268225/tools/model_viewer_spell_bar.h) and the recurring record boundaries in this file. Use only that source's EDD layout: its separate 256-byte EFF approximation does **not** fit this upload. Preserve physical EDD indices, including empty and duplicate labels; sorting by label or dropping empty labels breaks references. The remaining emitter-property semantics were not fully validated.

Across all 675 EFF records, all 2,928 nonzero emitter references are within the EDD table and lead to nonempty texture names. All nonzero sound references resolve in the supplied `soundassets.txt`; there are no duplicate numeric sound IDs. This is a structural/reference check, not proof that the game loads every effect or that every referenced texture/WAV exists on disk.

The installed spell-table diagnostics from the preceding run report animation 216 for Skin like Wood (spell 26) and animation 278 for Minor Healing (spell 200). Looking up those exact indices gives:

| Spell | Animation / EFF label | Casting sound | Landing sound | Nonzero emitter indices: casting; landing |
| --- | --- | --- | --- | --- |
| Skin like Wood | 216 / Malaise | 108 / SpelCast.WAV | 109 / SpelGdHt.WAV | 1284, 1284, 1285; 1280, 1281, 1282, 1283 |
| Minor Healing | 278 / Ethereal_Remedy | 108 / SpelCast.WAV | 109 / SpelGdHt.WAV | 1514, 1514; 1685, 1686 |

Both records have an empty middle stage. Every nonzero emitter in these two records has `MinLevel=0`; neither record's declared emitter slots are all disabled by a higher minimum level. The internal label `Malaise` does not itself prove the Skin like Wood mapping is wrong: record labels are descriptive strings, and effects can be shared. Do not substitute an animation based only on its name.

| Emitter | Texture |
| ---: | --- |
| 1280 | leafa.dds |
| 1281 | zapmuza.dds |
| 1282, 1283, 1284, 1285 | zapmuze.dds |
| 1514 | fire_missle.dds |
| 1685 | zapmuzc.dds |
| 1686 | blueglobesp501.dds |

Several emitter labels are `Blank Emitter Definition`; index 1514 has an empty label. Their actual records contain textures and nonzero properties. A blank label is not an empty record or evidence to delete it. No speculative particle-file replacement is justified by this inspection.

The preceding device log explicitly finds `spelcast.wav` in `snd2.pfs` as PCM16/mono/11025. This now connects a reported spell's actual sound reference to an inventoried packed asset. The log's six-file detailed sample omitted `spelgdht.wav`; aggregate archive counts do not prove that particular landing WAV is present. The submitted ZIP contains definitions, not WAV or DDS payloads. Their runtime lookup/playback and the target particle textures remain unverified.

## The actual DLL also uses the older spell range

The supplied DLL is PE32/x86, with PE timestamp `2026-08-12T02:54:30Z`; metadata is not independent proof of the build date or exact source revision. It contains the expected-client date string `May 10 2013`. Its import table includes `d3dx9_35.dll` (font/sprite/matrix helpers), explaining why that dependency can disappear in the native-DLL-off launch without indicating a failed model-helper install.

Read-only disassembly finds nine lookup-helper copies with a `0xAFC9` (45,001) upper-bound comparison. For example, image-base address `0x100F9470` rejects zero and IDs >=45,001; accepted values index a pointer table at offset `0x2C180`. It reads the exported `ppSpellMgr` at `0x1035BCD0`. A loop at `0x10106DE3` also stops at 45,001 and calls another such helper. These offsets and bounds agree with the [reference SPELLMGR declaration](https://github.com/Russianranger/Triptych-Triumvirate/blob/18141ae0c9a11813733f08fa77db986951b853d6/Release-NMS-Client/eqgame_dll/EQData.h).

This strengthens the range hypothesis using the actual supplied binary rather than just current source. It does **not** prove the proprietary client's effect-loader allocation, that every add-on path bounds-checks, or that filtering will repair this device. No full binary-to-source revision match or exhaustive patch audit was established. Do not patch a comparison constant to 50,008: changing a bound would not enlarge the underlying allocation.

## Conclusion and proposed controlled test

The evidence now rules out absent effect records, zero sound IDs, out-of-range emitter references, and unmet emitter minimum levels in the two inspected definitions. It does not rule out missing texture/landing-sound payloads or failures loading otherwise valid assets. Combined with verified installed spell IDs 50000-50007 and the actual DLL's older-range lookups, the high-ID incompatibility remains the strongest supported next test. [EQEmu developers describe the same particles/sounds failure with high ROF2 spell IDs](https://www.eqemulator.org/forums/showthread.php?t=40999).

The user paused filtering to verify export/copy first. That check is complete, but the pause has not been lifted. Ask whether to resume **one reversible client-only comparison**, with this concrete scope:

1. Retain the complete live database export and all server rows. Keep full export-and-sync behavior as the normal action.
2. While the client is stopped, back up the currently installed spell file in both root and Resources, then omit only IDs outside the existing ROF2 limit from the two test copies. Based on the captured table, that means exactly 50000-50007: 40,922 rows become 40,914. Every retained row, including spells 26/200, stays byte-identical. Do not edit other data or effect files.
3. Require both test copies to match the expected compatible SHA256 `034b5635049a9ef6e549f3f7d5b32f265a386d82a3fd3e8286b04d44b58a5e77` for this exact captured full table; a new full table must be separately inspected rather than assumed identical. Record installed counts and hashes at launch.
4. Keep native dinput8/model helpers, Turnip/DXVK, Balanced, exact 0.4.2 NPC compatibility and 1280x720 fullscreen. Check character-selection labels, then cast Skin like Wood and Minor Healing; capture particles and sounds separately. Do not test the omitted high-ID abilities in this comparison.
5. Restore the backed-up full spell files after the comparison and verify both hashes. Record whether effects and/or labels changed. A recovery would support the range cause; unchanged symptoms would require actual resource-loading/rendering evidence next.

The dormant `client_spells.py` validator/filter and previous tests provide implementation groundwork, but no active 0.4.7 UI action performs this comparison. Do not instruct the user to downgrade, run Prepare expecting filtering, or import this four-file ZIP as a complete client. No additional upload is needed before deciding on this test. No fix to name rendering is claimed; the earlier native-DLL bypass already failed and must not be repeated.
