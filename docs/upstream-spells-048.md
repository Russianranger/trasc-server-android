# Spell recovery and upstream history — September 16, 2026

## Device result

User reports that the 0.4.8 exclusion fixed spell effects and that the name glitch remains. New inputs: `logs-7096767172731379028.zip` and `TRASC Server Preview_2026-09-16 14_14_26.mp4`.

The launch evidence independently verifies both `spells_us.txt` and `Resources/spells_us.txt`: 40,914 rows each, maximum ID 43,019, SHA256 `034b5635049a9ef6e549f3f7d5b32f265a386d82a3fd3e8286b04d44b58a5e77`. The applied journal records exactly IDs 50000–50007 excluded from the original 40,922-row table, SHA256 `4762679840e788b016d83b6651866690dd344b119ff49cc4d953b292e06d7110`. This is actual installed-file evidence, not the earlier hypothetical diagnostic count.

The same session has native dinput8 and both native D3DX helpers loaded, Turnip/DXVK, Balanced CPU, exact 0.4.2 NPC compatibility and sound diagnostics enabled. Android audio records 15,635,424 written frames and 4,178,866 nonzero samples before stream closure. Those counters establish output activity, not which individual sound the user heard. The user's recovery report establishes the device result. The 10.704-second video shows in-world casting attempts, including fizzles; it does not show the character-selection screen. Do not claim an independently observed name improvement or independently auditioned audio from frame sampling.

This confirms the high-ID exclusion as an effective workaround for this installation. It does not establish which of the eight IDs individually triggers failure or make those custom abilities safe to use while absent from the client table. Names remain unresolved after successful spell recovery.

## Which source is installed and which was merged?

The new `control.log` retains the source import at **18141ae0c9a11813733f08fa77db986951b853d6**, matching the prior installation. Its server database is byte-identical to the September 9 upstream release. That fork commit also includes later client-source and local Android changes; describing its entire tree simply as September 9 would be imprecise.

[PR #2](https://github.com/Russianranger/Triptych-Triumvirate/pull/2) merged upstream through **a6a11bb725f56820bb0e28b373bfcfd02c2d2e3d** into the user's fork at **4c653ca2d16aaede33b7011d07254c520ac5f5df**. The upstream content/database change is **b14a1e71690778a53fe1c59ab617fb613f62b10b**, committed September 14 (its author timestamp is September 13). The later a6a11bb commit updates README. Upstream main still points to a6a11bb at this investigation. Merging source did not deploy the app's server or database.

## Database history

All five revisions of `Release-NMS-Server/database/release-peq.zip` in the upstream branch were inspected. Dates below use UTC commit dates; the August 31 snapshot was committed late August 30 in US time zones. These establish first appearances in the published database snapshots, not the date the author originally created each spell in a private working database.

| Snapshot | Total spell rows | IDs at or above 45,000 |
| --- | ---: | --- |
| [August 4 initial import](https://github.com/saltamontes5k/Triptych-Triumvirate/commit/fedaa3c5a8a3e90c87e1ea2a5776ccec2ad018ee) | 40,914 | None |
| [August 31 release](https://github.com/saltamontes5k/Triptych-Triumvirate/commit/9bb92d29e322830e0d02cdf2a24472b9c8aeca63) | 40,921 | 50001–50007: Edict of Command |
| [September 3 release](https://github.com/saltamontes5k/Triptych-Triumvirate/commit/11e5b5c79051eda3f89293a326277fd6ba1556dc) | 40,922 | Adds 50000: Dire Charm; retains the seven Edict entries |
| [September 9 release](https://github.com/saltamontes5k/Triptych-Triumvirate/commit/ae3af6dd3e7aa679a7165e89aeb9a97535bec70b) | 40,922 | Same eight IDs |
| [September 14 release](https://github.com/saltamontes5k/Triptych-Triumvirate/commit/b14a1e71690778a53fe1c59ab617fb613f62b10b) | 40,929 | Retains 50000–50007 and adds 50008–50014 |

The seven September 14 additions are 50008 **Sunrise Hills Key Echo**, and 50009–50014 **Breath of Atathus**, **Breath of Draton'ra**, **Breath of Osh'vir**, **Breath of Venesh**, **Breath of Mysaphar**, **Breath of Keikolin**.

The September 3 and September 9 spell-data sections are identical. Comparing all September 9 and September 14 spell rows shows **seven additions, zero deletions and zero changed existing rows**. Skin Like Wood (26), Minor Healing (200) and the original eight high-ID rows are unchanged.

Archive identity checks matched local ZIP bytes to the Git blob objects at both the upstream release and corresponding fork commits:

| Snapshot | ZIP SHA256 | Git blob |
| --- | --- | --- |
| August 4 | `a516fae09e7b2c4e346810dcba3ce7bce8c719756dd5c2591056474dcae672dd` | Archived from fedaa3c |
| August 31 | `daf4898521d5c73748e5f47b7af36ea4b7bba0df08539c7319247cd9f9f11dcd` | Archived from 9bb92d2 |
| September 3 | `e787bfc5c3974939cdbe8a5a58c174fef3d8a611e4d6d99874cc43411d704a56` | Archived from 11e5b5c |
| September 9 / installed source | `1c962747e97af14a58ca4d0bae3848b4935f15d1ede92e1d5cb9b8bd558047b7` | `7ff510d2c985762058e206ae7ea7c7ed8bbc70f7` |
| September 14 / merged source | `ad165b85b5fb3e36e65d871088c7bcc3de34bca1063d2fe32e4ff22fa5cc4207` | `422b07a9cc84bbb07df8d2d8c66308c4858fd2e8` |

Only public seed data was inspected. No live database, character data or imported game files were changed.

## Does September 14 fix it?

**No compatible spell export or client capacity fix was found in the merged update.**

- [ExportSpells](https://github.com/saltamontes5k/Triptych-Triumvirate/blob/b14a1e71690778a53fe1c59ab617fb613f62b10b/Release-NMS-Server/client_files/export/main.cpp) and [SpellsNewRepository](https://github.com/saltamontes5k/Triptych-Triumvirate/blob/b14a1e71690778a53fe1c59ab617fb613f62b10b/Release-NMS-Server/common/repositories/spells_new_repository.h) are unchanged. Both normal and multiclass export queries read all spell rows ordered by ID without a range filter.
- [ROF2 limits](https://github.com/saltamontes5k/Triptych-Triumvirate/blob/b14a1e71690778a53fe1c59ab617fb613f62b10b/Release-NMS-Server/common/patches/rof2_limits.h) retain `SPELL_ID_MAX = 45000`; the client add-on's [EQData.h](https://github.com/saltamontes5k/Triptych-Triumvirate/blob/b14a1e71690778a53fe1c59ab617fb613f62b10b/Release-NMS-Client/eqgame_dll/EQData.h) retains `TOTAL_SPELL_COUNT = 0xAFC9`. Neither changed in this update. The actual uploaded DLL's bounded lookups were separately established in [the asset investigation](client-assets-047.md); source constants alone are not proof of proprietary loader internals.
- The entire client delta between installed source and merged source comprises the inventory currency label rename, a comment in MQ2Labels, enabling old-model horse support, and build libraries/logs. There is no spell-loader expansion, effect-file replacement, or character-selection rendering fix in that delta.
- The custom database migration manifest is unchanged; no migration remapping these IDs was added. A source rebuild does not automatically replace content with the new bundled seed.

Re-exporting an unfiltered table containing these IDs is expected to reintroduce the recovered failure for this client. The September 14 seed contains fifteen such IDs, while the explicit **0.4.8 comparison intentionally accepts exactly eight**. Applying that comparison to a freshly exported fifteen-ID table fails without replacing files. Do not claim 0.4.8 already supports the new seed.

For current play, retain or reapply the working exclusion on the existing eight-ID installation. Before exporting a changed database into the client, implement and validate a durable compatibility policy. Filtering keeps the rest of the client usable but leaves the excluded custom abilities unavailable in its spell table. Preserving those abilities requires a consistent remap into verified unused client-compatible IDs, including server/database/quest/AA/item references; that migration has not been designed or applied here. Do not delete rows from the server or replace the live database with a seed to address this symptom.

## Remaining name glitch

The user explicitly reports it persists. Spell recovery therefore does not resolve the character-selection label problem. `EQUI_CharacterSelect.xml` is unchanged in the merged update, MQ2Labels has only a currency comment change, and the reviewed ROF2 encoder changes concern shrouds. World character-set changes rename currency fields/rules without changing their field type or wire size. No upstream name-rendering fix was identified.

The new client log still reports the known missing `SkinMeshCBS1_VSB.fxo`; that warning predates this test and is not a demonstrated name-glitch cause. There is no new font-load failure identifying a root cause. Previous native-DLL bypass, CPU accuracy and renderer comparisons remain completed, unsuccessful investigations; do not repeat them indiscriminately.

The supplied Winlator video shows in-world play only. The remaining useful comparison is whether the **same character-selection name/class/zone labels** also glitch in Winlator with the same client files. That observation is still missing and would narrow the next investigation. It would not by itself identify a specific graphics or translation component.

## Scope

Documentation-only investigation. Published APK remains verified **0.4.8/code25**. No server deployment, seed import, app/native change, new APK or confirmed name fix is claimed. Preserve signing identity, working NPC settings, current spell backups and all existing build gates.
