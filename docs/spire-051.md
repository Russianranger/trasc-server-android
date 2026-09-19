# Spire content workspace — 0.5.1 preview

[Download the signed 0.5.1 APK](https://github.com/Russianranger/trasc-server-android/releases/download/preview/trasc-server-android-preview.apk?build=c2a35e0). [PR #3](https://github.com/Russianranger/trasc-server-android/pull/3) is merged and the preview is published.

The user authorized the three previously selected Spire milestones and a dedicated Spire tab. This implements focused content tools inside the existing Android launcher and Python daemon. It does not require a separate Go/Vue service, Internet connection, additional runtime or Spire account. Public Spire model definitions informed the relationships; implementation is native TRASC code.

## Included

- Search and paginate items, NPCs, loot tables, loot drops, both loot-entry tables, merchant inventories, spells, database strings, AA abilities, AA ranks and rank effects.
- Merchant inventories also search by item/NPC name; loot-entry lists show related item/drop/table names.
- Open related records in either direction: NPC → loot/merchant, table → drop → item, item → merchant/loot, AA → rank → spell/strings/effects. Composite database keys are preserved. AA string links and validation include the title/hotkey/description type.
- Edit common item/NPC fields and the supported loot, merchant, spell, string and AA fields. Other installed fields are displayed read-only and preserved. Record IDs cannot be changed.
- Add loot tables/drops, merchant slots, loot entries, database strings and AA effects using explicit keys. Remove merchant slots, loot entries and AA effects through a removal preview. Existing item/NPC/spell/AA base records are edited in place; creating/deleting those entities and rewriting AA rank chains are outside this focused editor.
- Preview before/after values, validate supported fields against the live schema and references, require a stopped server for saving, back up the full database first, then commit the edit and durable change-history entry together. Stale records/previews fail without overwriting later edits.
- Export & sync uses the original four-file client export. The saved RoF2 spell policy remains authoritative: when enabled, IDs >=45000 stay in the server database and are excluded from client spell files. Restore full spell files still restores the latest complete generation. AA definitions/effects are server-delivered, while their strings and referenced spells use client export.

## Storage and limits

Editing requires InnoDB with a non-null primary/unique key. Unsupported schemas remain browsable and explain why editing is disabled. No schema conversion or automatic migration of content/player tables occurs. Unknown custom fields are never assigned by the editor, and every original column participates in the optimistic concurrency check.

Content history lives in `_trasc_spire_changes` in the active database, with a unique save ID, UTC time, before/after data, backup path and export marker. It is created on the first save and included in full database/session backups. It is world-content history, not player progression; replacing the world database does not transplant it through player-only snapshots. Full backups retain earlier history. There is no one-click partial undo: use the existing database restore with its stated scope.

Save previews expire after 30 minutes, are confined to the app workspace, and cannot supply raw SQL. Lists use 50 rows/page; history uses 20 entries/page. Values use hex-encoded SQL literals and JSON/hex result transport so names, apostrophes, NULLs, composite keys and large integer IDs survive correctly. Client-export text fields reject delimiters and embedded line breaks. Chance/probability, numeric storage bounds, references and supported min/max relationships are checked before save. Existing malformed references in untouched fields are not silently rewritten.

## Thor acceptance test

1. Stop ROF2, stop the game server, then stop the runtime. Install the signed APK over the current app, start the existing runtime and confirm version 0.5.1. Leave the game server stopped while testing saves. No server/DLL rebuild, SDK refresh, game reimport or runtime reinstall is needed for this UI/backend change. Keep the working particle, camera, controller, reconnect and loading settings.
2. Open Spire. Search a known item/NPC; follow its merchant/loot relationships and return to related records. Try search by ID, paging and portrait/landscape layout.
3. With the server stopped, make a small reversible item/NPC edit. Preview first and confirm the database is unchanged until Save. Save, inspect change history and its backup path, then restore the original value through another preview/save.
4. Add/change/remove a merchant slot or loot entry with a known item. Try an invalid item ID or probability; neither should save. Preview a record, change it through SQL, then attempt Save; the stale preview should be rejected.
5. Edit a known low-ID spell/string and an existing AA field. Export & sync, restart the server and relaunch ROF2. Confirm spell/string changes and AA refresh. With compatibility on, a high-ID edit must remain excluded from the client; this does not solve high-ID spell support.
6. Verify ordinary play and existing player inventory/progression. Account/player tables are not Spire edit targets. Physical Thor acceptance is separate from automated checks.

## Deferred boats (historical; reopened in 0.5.2)

The latest user request reopens boat investigation. See [0.5.2 investigation and merchant picker](boat-investigation-052.md); the original deferral below describes the 0.5.1 scope.

Boat repair is explicitly shelved. Future work should separate deck collision, passenger attachment, movement/rotation and cross-zone handoff. Reuse the exact RoF2 executable/graphics references from the particle investigation; begin with one named ship inside one zone before attempting whole routes. Existing client vehicle/passenger definitions and server vehicle-relative coordinate handling are investigation leads, not a proven diagnosis. Do not implement boat hooks as part of Spire.

## Verification record

The user approved review, merge and APK delivery. PR #3 merged at `c2a35e0acfccef1d3114093c78d4718bbc583e63`. [Final focused checks](https://github.com/Russianranger/trasc-server-android/actions/runs/35439132450), all six [PR verification jobs](https://github.com/Russianranger/trasc-server-android/actions/runs/35439134250), and all seven [main release jobs](https://github.com/Russianranger/trasc-server-android/actions/runs/35440858451) passed. This includes the standard item/NPC/spell field-name corrections, all 145 Python tests, actual seed schemas, database edits/rollback/audit/export, browser/JVM tests, Android build/lint and preserved signing, and existing ARM64 client graphics/input/audio/session gates.

The public APK is 10,555,909 bytes, SHA256 `cce4c7f60d1b296a4858cb3dd5647260db83d0e0bbaed75e947673cd47b51477`. Its APK v2 signature/content, 0.5.1/code 41 manifest, existing package ID, pinned certificate and packaged sources were independently checked. All 28 backend/header assets and UI assets match the merged source, and the compiled deployment code includes both Spire modules. Public APK/source/manifest digests and the preview tag match the verified release. The certificate matches the existing preview/Beta 0.5 app, supporting an in-place update. Physical Thor acceptance remains outstanding.

### Earlier development verification

[Focused verification run 35437991661](https://github.com/Russianranger/trasc-server-android/actions/runs/35437991661) passed on implementation commit `0c98032`: all 145 Python tests, real MariaDB saves, backup/error paths, concurrency rollback, audit, composite keys, character isolation and filtered/full client exports. All twelve tables in the published seed support the editors. The final schema review added coverage for the standard item spell-effect field names as well as custom-fork underscore aliases; final branch checks validate that correction. Browser checks passed for existing management flows plus preview invalidation, failed saves, linked records, composite insertion, history, export and responsive Spire layouts. Phone, Thor-landscape and wide screenshots were reviewed. The full Android/ARM64 database, DLL and graphics regressions remain required; their current results are attached to PR #3. Physical device acceptance remains outstanding.

The earlier PR artifacts used a CI debug certificate. Use the published signed APK linked above for an in-place update; do not uninstall the existing app to install a PR artifact.

The existing official Beta version 0.5 remains the verified 0.4.23/code 40 APK. The preview now supplies 0.5.1/code 41.
