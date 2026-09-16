# 0.4.6: correct the ROF2 client spell export

## Cause found in the project data

The user's September 16 clarification is decisive: **Skin Like Wood and Minor Healing have no visual particles as well as no sounds**. Working music, sit/stand, swinging and VirGL footsteps establish other audible paths. Both new logs show continuous shared stereo playback; the archive inventory finds the six classic spell WAVs as ordinary PCM16. This shifts investigation from audio output to the spell-effect loader.

The upstream project's original pinned seed at `18141ae0c9a11813733f08fa77db986951b853d6` has **40,922 spell rows**, matching `ExportSpells Exported [40922] Spells` in the uploaded operation log. It includes eight IDs **50000–50007** (Dire Charm and Edict of Command entries). The current upstream seed at `4c653ca2d16aaede33b7011d07254c520ac5f5df` contains15 IDs50000–50014, so updating the seed would not remove the compatibility problem. Neither source contains the user's private database modifications.

ROF2's upstream limit is45,000; EQEmu's developers report that loading high IDs causes particles and sounds to disappear, including a reproduction fixed by removing ID45000 rows. The existing exporter serialized every row without a client limit. The Android launcher copied that complete table into both the client root and Resources. This is a concrete export compatibility defect, although the exact installed rows were not captured by0.4.5 and physical recovery remains to be verified.

The original seed ZIP was downloaded from its pinned commit and checked:55,923,202bytes, SHA256 `1c962747e97af14a58ca4d0bae3848b4935f15d1ede92e1d5cb9b8bd558047b7`. A derived237-column table validates the new filter:40,922 input rows,8 excluded,40,914 retained,max supported ID43019. Spell26 (Skin like Wood) retains spell_animation216, SpellAffectIndex2 and casting_animation42; spell200 (Minor Healing) retains278,1 and43. The six classic WAVs previously inspected are not proof of the sound mapping for those specific animation IDs.

## Change and boundaries

`backend/client_spells.py` validates every row and excludes IDs >=45000 from **generated client exports only**. It preserves all retained bytes, including field data, encoding bytes, line endings and optional UTF-8 BOM. It rejects invalid/duplicate IDs, inconsistent/short rows, NUL data, symlinks, oversized files/rows and tables without any supported spells before replacing the generated file. Limits:64MiB/table,128KiB/row,100,000rows; removed-ID diagnostics are capped at64 entries.

The most recent full export remains in `server/export/spells_us.unfiltered.txt`. The server database is never filtered, and no gameplay rows or spell mappings are rewritten. Both paths in the exported ZIP use the compatible table and include a small `rof2-spell-compatibility.json` report. The ordinary **Prepare client for this server** action applies the corrected export to root and Resources with its existing original-file backups and rollback. The Android bridge already prevents Prepare while the client is running. **Installing alone does not alter the imported spell files: Prepare must run once.**

`logs/client-spell-export.json` records counts, bounded excluded IDs, hashes and numeric effect fields for spells26/200. When Sound diagnostics is enabled, the read-only inventory inspects both actual installed spell tables and allowlists ShowSpellEffects plus spell particle opacity/density/clip/filter settings. It never changes particle settings. This can verify that Prepare actually applied the corrected table and reveal remaining disabled-particle settings if necessary.

No native sound, renderer, CPU, dinput8 or model-library source changes. Keep the confirmed0.4.2 NPC settings and Balanced/Turnip. The name fault crosses both renderers and remains unresolved; do not claim this patch fixes it. No server rebuild, new seed, runtime download, prefix repair or client reimport is needed.

## Validation and release status

77 local backend tests pass. New regression coverage exercises the45000 boundary, byte preservation/BOM/non-ASCII text/mixed line endings, malformed and duplicate rows, symlink rejection, bounded reporting, idempotence, actual Engine export/Prepare/ZIP paths, original-file backups, full export retention, read-only installed-table/particle inventory and privacy exclusions. Existing prepare rollback tests remain strict.

The ARM64 offline database integration test now additionally serializes the actual pinned seed through MariaDB CONCAT_WS and requires exactly8 removals,40,914 retained rows,max43019,correct spell26/200 effect fields,unchanged full-export bytes and an unchanged40,922-row server table with max50007. It does not rely on a fake audio or graphics fixture to prove spell data correctness. Existing full APK/browser/signing/database/native and direct/PRoot Software/VirGL/DXVK gates still run.

Version0.4.6/code23 is prepared; publication and downloaded-APK verification are pending. Follow [preview-notes.md](preview-notes.md) for the one-time Prepare and physical spell/name checks. Preserve the existing signing identity/cache.

## Primary sources

- [EQEmu developer diagnosis and ROF2 reproduction](https://www.eqemulator.org/forums/showthread.php?t=40999).
- [ROF2 limits](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/common/patches/rof2_limits.h).
- [Original pinned seed](https://github.com/Russianranger/Triptych-Triumvirate/blob/18141ae0c9a11813733f08fa77db986951b853d6/Release-NMS-Server/database/release-peq.zip).
- [Exporter and repository serialization](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/common/repositories/spells_new_repository.h).
