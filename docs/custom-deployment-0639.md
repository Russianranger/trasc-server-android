# Custom deployment in TRASC 0.6.39

Implementation and host evidence are recorded below. Clean release CI, publication and physical AYN Thor acceptance remain pending at this checkpoint. See [release notes](release-0639-notes.md) for the device checklist.

## Import Legends of Norrath data

Open the **Custom** runtime. In **Setup → Legends of Norrath Data**, use the imported client or Android **Choose folder** / **Choose client ZIP**. A folder may be the client, `LegendsOfNorrath`, or `data`; a ZIP may contain wrapper folders such as `EverQuest_RoF2PT/LegendsOfNorrath/data`. Only the discovered data subtree is copied. Its contents land directly in the resolved destination, without an extra `data/` level. All supporting files and empty folders are retained; no card assets are bundled in the APK.

**Preview data import** validates actual card records and displays New, Changed, Matching, Runtime Only, Errors and local conflicts, with files/bytes to transfer. Expand the file list to inspect every replacement. Stop the server and client, approve changed files and any local conflicts, then choose **Import / repair card data**. New and changed card files are repaired together so the archetype index and storage stay consistent. Runtime-only content is retained.

The validator follows Triptych `Release-NMS-Server/world/lon_service.cpp` (`Reader`, `ParseArchetype`, `LoadData`). It reads `archetypes/index.dat`, checks compressed-record offsets/lengths in `archetypes/storage.dat`, inflates bounded records, parses card properties, and requires readable archetypes plus a usable booster set. It reports unreadable records and optional `campaign.dat` / `decks/` omissions. Merely finding these directories does not count as valid card data.

After deployment, **Start server to validate deployment**, then select **Verify data & card service**. Data hashes/loader validation and live service status are separate:

| Status | Meaning |
|---|---|
| Confirmed | The running world started after deployment and its fresh log contains `[LoN] card service listening on port`. |
| Failed | Current startup evidence reports missing card data or `[LoN] card service NOT started`. Inspect the reported evidence and validation errors. |
| Pending restart | A fresh live startup cannot yet be established. A stopped server or old successful log does not qualify. |
| Disabled | The active `Custom:LoNEnabled` rule disables the service. Import/verify does not change this rule. |

Valid files alone cannot establish compatible server binaries, the required existing LoN schema/rules, an available listening port, or client/DLL compatibility. Thor service initialization must be confirmed from a fresh device restart/report.

## How destinations are resolved

The launcher mirrors the deployed server's configuration lookup: check `server/eqemu_config.json`, then its parent `eqemu_config.json`. The selected configuration's parent becomes the effective server working directory. Relative paths resolve there; absolute paths must still remain safely inside this Custom world's workspace. Symlink ancestors, protected runtime areas and escaping paths are refused.

| Content | Active configuration / rule |
|---|---|
| LoN card data | Read-only lookup of `variables.RuleSet`, named `rule_sets`, default-rule overlay, then selected-rule overlay for `Custom:LoNDataPath` and `Custom:LoNEnabled`. Relative `LoNDataPath` uses the effective working directory; its compiled fallback is `lon_data`. Missing/unreadable required rulesets fail closed instead of guessing. |
| Quests | `server.directories.quest_paths` takes precedence over scalar `quests`; sync uses the first configured quest root, normally `quests`. |
| Perl plugins | `server.directories.plugin_paths` takes precedence over scalar `plugins`; sync uses the first configured plugin root. Launcher-generated configuration normally uses `quests/plugins`. |
| Lua modules | `server.directories.lua_module_paths` takes precedence over scalar `lua_modules`. The source `Release-NMS-Quests/lua_modules` is copied to every distinct configured Lua module path and the canonical `<quest-root>/lua_modules` path. Duplicate paths are collapsed. |

The database lookup opens the existing Custom database when needed and issues SELECT queries. It performs no seed import or database migration. A stopped MariaDB process is different from a stopped world server; the existing database may be started for this read-only lookup.

## Review and synchronize quests

**Setup → Quest & Plugin Sync → Scan for Changes** compares the currently installed source's `Release-NMS-Quests` and `Release-NMS-Plugins` against the resolved destinations using SHA-256. The source commit, last successful synchronization commit/date and freshness are shown. Archive imports without recorded commit provenance are labelled accordingly. **Refresh Source** invokes the existing source-update flow; scan/sync never silently fetches another revision.

Counts are separate for quests, plugins and Lua placements, plus a combined total. Additional Lua mirrors are shown separately and contribute actual destination copies to the transfer count. Expand **Inspect files and proposed replacements** for 40-file pages, classification/path filters, filename/size/modified sorting, source/runtime metadata and bounded text diffs for changed supported scripts/configuration. Choose new files, changed files or both. Changed replacements require preview approval; files that differ from the last manifest are local conflicts and require separate approval. Runtime-only files are never automatically deleted.

Both deployment flows use an exclusive Custom deployment lease and existing launcher transfer/profile guards. Each replacement has a protected original, temporary file, SHA-256 verification, atomic rename and durable write-ahead recovery. The result reports copied files/bytes and the backup destination under `backups/custom-deployment/history/<token>`. Manifests record provenance, timestamps, hashes, destinations and results. Cancellation/failure rolls back modified files; an interrupted process is recovered before new deployment/server startup. Recovery refuses to overwrite unexpected later edits: resolve the reported conflict and retry **Recover interrupted deployment**, keeping its protected backup.

No `release-peq.zip` reimport, player reset, database migration, server rebuild or client executable patch occurs in either content action. The existing database migration version 160 is not changed by these tools. Traditional and TAKP destinations are not touched.

## Storage and bounded transfers

Android SAF supports document providers and external SD without raw filesystem paths or Termux. Folder discovery copies only LoN data; ZIP selection streams the selected archive to private disk, then extracts only that data. Free private space is required for staging, replacements and rollback copies, plus a 64 MiB reserve. Original selected documents stay unchanged.

The native transport uses a 256 KiB copy buffer, accepts at most 200,000 files / 20,000 directories, searches up to 10 folder levels for `LegendsOfNorrath/data`, and limits the data subtree to 64 levels. Backend LoN validation/extraction limits data to 16 GiB total and 8 GiB per file, with at most 200,000 archive entries and a 64 MiB ZIP central directory. The shared deployment preview additionally limits the compared transfer tree to 100,000 files. These are safety ceilings, not preallocated memory; oversized input reports an error and users can choose the data folder directly. Backend file copying/hashing is streamed in 64 KiB chunks; card records are limited to 8 MiB.

## October update witnesses

The following exact source filenames come from `backend/quest_sync.py`'s witness catalogue. The post-sync report compares deployed script hashes, rather than treating an existing folder as evidence. Code witnesses establish source presence only; their presence does not prove database migration or deployed binary behavior.

### October 9 — Cake Defense baking and shroud mission

- `Release-NMS-Quests/bazaar/Wendel_Sweetcrumb.lua`
- `Release-NMS-Quests/rivervale/#Cake_Defense_Baker.lua`
- `Release-NMS-Quests/rivervale/player.lua`
- `Release-NMS-Quests/global/global_player.pl`

Quest deployment does not install its database content or rebuild the shroud engine.

### October 9 — Deity rank 2 quests

- `Release-NMS-Plugins/deity_blessings.pl`
- `Release-NMS-Quests/bazaar/Blessing_of_the_Gods.pl`
- `Release-NMS-Quests/potranquility/Blessing_of_the_Gods.pl`
- `Release-NMS-Quests/eastkarana/Avatar_of_Bertoxxulous.pl`
- `Release-NMS-Quests/butcher/Roderik_High_Priest_of_Brell.pl`
- `Release-NMS-Quests/feerrott/Avatar_of_Cazic-Thule.pl`
- `Release-NMS-Quests/southro/an_Aspect_of_Erollisi_Marr.pl`
- `Release-NMS-Quests/poknowledge/Fizzlethorpe_Bristlebanes_Image.pl`
- `Release-NMS-Quests/innothule/an_evil_little_imp.pl`
- `Release-NMS-Quests/southkarana/Avatar_of_Karana.pl`
- `Release-NMS-Quests/potranquility/Avatar_of_Mithaniel_Marr.pl`
- `Release-NMS-Quests/erudsxing/Primate_of_Prexus.pl`
- `Release-NMS-Quests/potranquility/Avatar_of_Quellious_the_Tranquil.pl`
- `Release-NMS-Quests/potranquility/Avatar_of_Rallos_Zek.pl`
- `Release-NMS-Quests/qeynos2/Helera_Garet.pl`
- `Release-NMS-Quests/northro/Avatar_of_Solusek_Ro.pl`
- `Release-NMS-Quests/potranquility/Herald_of_Justice_Due.pl`
- `Release-NMS-Quests/gfaydark/Avatar_of_Tunare.pl`
- `Release-NMS-Quests/poknowledge/a_crystalline_avatar.pl`

The corresponding deity and NPC database content must already be installed.

### October 9 — Halloween and Nights of the Dead quests

- `Release-NMS-Quests/lua_modules/halloween.lua`
- `Release-NMS-Quests/poknowledge/Edmund_Strangeways.pl`
- `Release-NMS-Quests/poknowledge/Illis_Taberish.pl`
- `Release-NMS-Quests/poknowledge/Rhaeda_Evel.pl`
- `Release-NMS-Quests/crescent/Jilian_Florantine.pl`
- `Release-NMS-Quests/gfaydark/Elder_Ritualist_Longshadow.pl`
- `Release-NMS-Quests/gfaydark/Skinwalker.pl`
- `Release-NMS-Quests/gfaydark/a_revealed_skinwalker1.pl`
- `Release-NMS-Quests/gfaydark/a_revealed_skinwalker2.pl`
- `Release-NMS-Quests/gfaydark/a_revealed_skinwalker3.pl`

Seasonal event activation and associated NPC database setup are separate.

### October 9 — Shroud quest support

- `Release-NMS-Quests/bazaar/Wendel_Sweetcrumb.lua`
- `Release-NMS-Quests/rivervale/#Cake_Defense_Baker.lua`
- `Release-NMS-Quests/rivervale/player.lua`
- `Release-NMS-Quests/global/global_player.pl`
- `Release-NMS-Server/zone/shroud.cpp`

Shroud support also needs the matching built server and database migration; this scan only deploys scripts.

### October 16 — Legends of Norrath support

- `Release-NMS-Quests/global/items/script_8884.pl`
- `Release-NMS-Server/world/lon_service.cpp`
- `Release-NMS-Server/zone/nms_lon_session.cpp`

The item script is the Fang of Chalandria click handler. Import client card data separately; LoN also requires matching server binaries, client DLL and database. Service initialization must be checked after restart.

### October 16 — Native achievements

- `Release-NMS-Server/zone/achievement_manager.cpp`
- `Release-NMS-Server/zone/client_achievements.cpp`
- `Release-NMS-Server/common/achievements.cpp`
- `Release-NMS-Server/common/database/database_update_manifest.cpp`

The native achievement feature is server code and database content, not proof supplied by the older Aurelian Stoneward reward quest. No migration or rebuild is performed.

### October 16 — Mercenary support

- `Release-NMS-Plugins/NMS_sod_utils.pl`
- `Release-NMS-Server/zone/merc.cpp`

The plugin supplies tier and task support. Mercenary engine changes and database setup require the corresponding server build and existing migrations.

## Host evidence and remaining qualification

The real Triptych checkout at `38a4f2ad03203cb2f12dbff26fd613cc47efba0a` contained 10,424 unique deployable source files / 19,119,637 bytes: 10,317 quest files, 64 plugin files and 43 Lua module files. A matching host runtime scanned as 10,424 Matching with zero New, Changed or Errors. Removing one source destination, editing another and adding a runtime-only file produced 1 New / 1 Changed / 10,422 Matching / 1 Runtime Only; synchronization transferred two files / 41,239 bytes and preserved the runtime-only file. A later local edit was detected as one local conflict. These are controlled host results, not predicted counts for the user's installation.

Host validation of real LoN card data parsed 6,027 archetypes with zero unreadable records and 16 booster sets. The reference loader/parser parity check uses the actual Triptych parsing behavior. This establishes readable data, not a running Thor card service. Client assets used during host inspection are not redistributed.

At this checkpoint, the final exact-source clean CI, Android assembly/lint/signature/native-payload verification, downloadable release and physical Thor SAF/card-service acceptance remain pending. Publication proof and workflow totals must be added after the actual release passes; do not infer those results from these host examples.
