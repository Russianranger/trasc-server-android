# AYN Thor acceptance: 0.6.24

This is a device checklist, not a publication or camera-fix claim. Use the
qualified release receipt for the exact APK, signing certificate, source and
native server/helper revisions. Physical camera veering remains unresolved;
this pass adds evidence collection. Keep separate results for each world.

## Preserve the installation

Install the verified APK as an update without uninstalling. Preserve databases,
saved bots, compiled servers, imported clients, Wine prefixes, installed
runtimes, profiles, controller bindings, renderer/CPU options and themes. Record
the current owner/roster, important inventory/bank items, hotbars, personal
socials and per-world settings before testing.

Camp/exit normally, stop the client/server, and save a checkpoint outside the
app. **Server → Session backups → Export selected profile** retains the existing
single-profile format. The all-profile procedure below covers all worlds plus
device control/theme preferences. Keep the checkpoint private: it contains
accounts and credentials. Changing profiles requires stopped client/runtime
and no active operation: **World profile → Switch world → Start runtime**.

## TAKP camera reproduction and controls

Use the same renderer, resolution, CPU math accuracy, sensitivity and inversion
that produced veering. Start the existing TAKP client with the managed qualified
helper; retain original EQW backups. No prefix reset or server rebuild is needed
for camera diagnostics. A custom-helper refusal is evidence to retain, not a
reason to overwrite it.

1. Enter a quiet area in first person. With **Look off**, check free pointer
   movement and harmless menu clicks. Tap the tile for **Look on**. Immediately
   test the following sequences with touch, then the Thor right stick. For
   touch, keep one finger down through the reversal. For the stick, hold the
   first direction about two seconds and reverse for about one second.

   | Axis | First direction | Smaller reversal | Acceptance observation |
   | --- | --- | --- | --- |
   | X | Left | Right | Turns right promptly |
   | X | Right | Left | Turns left promptly |
   | Y | Up | Down | Reverses vertically promptly |
   | Y | Down | Up | Reverses vertically promptly |

   Preserve vertical inversion: the criterion is immediate reversal. Record
   intended and observed direction, unexpected cross-axis motion and motion
   after neutral. Repeat quick reversals and long movements past screen edges.
   A successful open Wine fixture does not establish this game result.
2. Stop the client after the short reproduction and use **Logs → Export log
   bundle**, ideally within the first minute. The managed helper automatically
   writes bounded Wine-only `eqw-camera-diagnostics.log`, with marker
   `TRASC_TAKP_CAMERA_TRACE_V1`. Retain input source, Look/RMB state, exact
   sequence, occurrence after focus/zoning and a short video if possible. Its
   format, polled/buffered input, game-consumer and capture observations are
   diagnostic evidence; the marker alone is not camera acceptance. Report a
   missing trace with the helper receipt rather than assuming a good result.
3. In a second session test Look off/on, ordinary pointer clicks, chat,
   inventory, keyboard, controller mappings, background/resume and a normal
   zone transition. Interruptions must release look; deliberately re-enable
   after returning. If available, repeat with an external mouse/RMB and record
   it separately from touch/controller.
4. Drag the **gear** clear of a game window. Gear and Look tile move together.
   The drag must release captured input without a game click or opening the
   menu; a short tap afterward must open it. **Move client controls** offers
   **Upper left**, **Upper right**, **Lower left**, **Lower right**, **Center**.
   Test corners and reopening the display. **Reset controls position** returns
   to upper right. A different location in another world must remain separate.
5. Enable Look, then open gear: opening the menu releases Look. Uncheck **Show
   mouse look tile**; the checkbox changes visibility, not the look mode.
   Hidden state persists after reopening. Resetting position must not show it.
   While hidden, gear → **Enable mouse look** remains available. Assign
   **Toggle mouse look** to a chosen spare controller button under **Controller
   mappings**, save, and press twice to test on/off while hidden. Restore the
   prior binding. Layer changes release look. Show the tile again and verify
   its taps. Position/visibility persist per world; Look on/off is transient.

## Native server prerequisites and cleric Yaulp

The new autonomous Yaulp policy requires the qualified updated TAKP server
source to be built and deployed. Installing the APK or camera helper alone
does not replace a working deployed server. Preserve its build/runtime receipts
and checkpoint; compare **Builds → Source revision** with the qualified TAKP
pin `03e934d0fdf460e2e6ce34c0a25a3e05d9f7e167`. If an older source is installed,
stop the server and use **Setup → Download
TAKP world files**, then **Builds → Build imported source**. Use one compiler
job initially, power the Thor, wait for successful staging, and select **Deploy
successful build** once. Keep the existing database, account, content and bots;
do not initialize a fresh database. Save the new source/build/deploy receipt
alongside the previous one. Do not queue competing builds.

Spawn the existing cleric and record level/rank. Remain idle for at least two
minutes: it must not repeatedly maintain Yaulp, and ordinary resting/support
buffs must still work. Test permitted melee, then combat outside melee range.
Yaulp may support permitted melee; it must not cast automatically while idle,
passive/suspended or outside melee range. Healing, curing and crowd control
keep priority. At levels 56/65 retain the useful mana/haste ranks. An active
Yaulp must not be repeatedly reapplied; refresh follows native stacking/recast
gates. Manual spell commands remain available. Camp/restart/respawn the same
cleric and verify roster/settings, without recreating it. Report a remaining
loop with level, rank, elapsed time, combat state, deployed source receipt and
fresh logs; the original bundle did not contain this cast telemetry.

Custom/Traditional offline creation requires their existing qualified native
utility. Rebuild only if **Bots → Refresh roster** says generation is unavailable
because it is absent; roster display alone is not proof of capability.

| World | Source | Qualified revision |
| --- | --- | --- |
| TRASC Custom | `Russianranger/Triptych-Triumvirate` | `8f6ca0795f424a7b4eab750ff38fc6473d48375c` |
| Traditional EQEmu | `Russianranger/Server` | `4aceae18b94ffaafc08e2b17bc41cd72c77f795d` |

Reuse matching source; otherwise **Setup → Import server** at the exact revision
(Traditional: **Use tested Server source → Import from GitHub**). **Builds →
Parallel compiler jobs → 1 · lowest memory use → Build imported source → Deploy
successful build**. Keep database/runtime/imports. Modern command export uses
existing native commands and adds no further server rebuild requirement.

## Offline creation and command exports in every world

Repeat in Custom, Traditional and TAKP using that world's existing owner.

1. Stop client/server, leave runtime open, **Bots → Refresh roster**, search
   character/account and choose the owner. Record existing **Saved companions**.
   If modern **Enable bot storage** appears, **Review storage**, inspect the
   listed table changes, then **Back up & enable**. A full database backup must
   complete before conversion; retain it with **Save database backup**. On a
   partial failure, keep the converted/remaining lists and backup path, then
   refresh/review. Do not rewrite schema versions or reinitialize the database.
2. Add one or two unique companions with 4–15-letter names and allowed
   race/class/gender. **Review generation → Generate bots** once. Refresh and
   restart runtime: new bots appear once and previous bots remain. Check owner
   inventory/bank/progression. Creation must not require logging into the game
   or starting a world population. After a lost response, inspect the committed
   roster before submitting a new review/request.
3. Select two owned bots and their **Character settings file**. If absent, log
   in once and camp normally first. Under **Commands to export**, TAKP: select
   **Spawn party**, **Revive party**, **Follow**, **Report party**. Modern: retain
   **Spawn and group**, add **Follow owner**, **Report party**. **Preview buttons**
   must show each selected name and exact native lines. Modern gets one guarded
   spawn/target/invite social per bot plus combined follow/report buttons.
4. Choose distinct free hotbar slots or **Socials only**. Occupied personal
   slots must stay unavailable. Temporarily choose the same free placement
   twice: installation must be disabled. Correct it and **Install buttons**.
   Insufficient social space or stale previews must refuse before file change.
5. Test restore immediately, **before launching the client**: expand **Restore
   previous character buttons**, choose the newest restorable backup and
   **Restore selected backup**. Former complete settings must return exactly;
   bots remain saved. Preview/install again, start server/client and test the
   buttons. TAKP spawn auto-groups; modern spawn targets owner, then bot, then
   invites. Check correct membership and save native chat refusals for full
   groups, spawn limits or timing failures. Test modern **Spawn only** separately:
   it must contain no invite. Follow/Gather/Report must affect selected owned
   bots; native group, class, target and equipment limits still apply.
6. TAKP revive is out of combat, fallen/inactive, at least 60 seconds after the
   fall; use **Revive party**, then **Spawn party**. Revival gives 1 HP/0 mana.
   Modern servers have no TAKP-style revive/sit/stand actions. Six selected
   names must split combined actions into five-line and one-line numbered
   socials, with no silent omissions; native party limits remain.
7. Camp/reopen and verify socials, hotbars, personal settings and roster. Make
   a harmless personal social edit, camp again, stop client/server and refresh.
   An older installed-file backup must refuse to overwrite this changed file.
   Switching owner/profile, database or deployment must invalidate old
   previews. Preserve the edit and use a matching full checkpoint when needed.

## Large all-profile SAF backup and restore

Use a real large installation and a local SD/USB/document destination with
enough space and support for files larger than 4 GiB. Record archive size,
provider, elapsed time and free internal/destination storage. An individual
large client file is useful for ZIP64 acceptance. Included uncompressed data is
capped at 256 GiB and the inventory at 200,000 records, with ZIP overhead allowed
separately. Metadata and available app-memory checks can reject a backup with a
clear error before changing worlds. These steps do not require compiling servers
or downloading runtimes.

1. With the game stopped, **Server → Session backups → Create & export all
   profiles**. Cancel the Android destination picker once: no backup work or
   settings change should follow. Repeat and choose a fresh destination. Expect
   clean database snapshots, all installed worlds, SQL backups, current/staged/
   previous binaries, maps/source/logs, clients/prefixes, build/runtime receipts,
   controller/overlay preferences and launcher theme. Temporary imports,
   previous exports and process files are excluded.
2. Watch **Complete session transfer** progress. Profile switches and competing
   runtime/build/import operations must be blocked. Export streams directly to
   the selected document; it must not consume internal space for a second
   complete ZIP. Use **Cancel operation** during archive transfer, wait for
   cleanup, and confirm existing worlds/settings remain; the cancelled partial
   destination should be removed where the document provider permits deletion.
   Retry to a fresh destination and retain the completed archive externally.
3. **Setup → Restore all profiles → Choose all-profile backup**. Without checking
   **Replace the profiles included in the backup after every profile is
   verified**, restoring over installed included profiles must refuse. Check
   it explicitly and retry. Local seekable providers verify directly; providers
   offering a pipe need an internal archive copy. Internal free space must cover
   extracted included contents, metadata overhead, any fallback copy and the
   128 MiB reserve while originals remain.
   Insufficient space, truncated/corrupt/unsupported ZIP or mismatched world
   data must refuse before activation, preserving worlds and preferences.
4. Cancel during copy/verification. After cleanup, confirm prior selected world,
   theme, controls, bots and settings. Retry normally. Once **Activating verified
   worlds…** begins, cancellation is hidden; wait for completion. Every included
   world is verified before activation. Absent profiles retain existing trees.
   For a partial backup, only included components are replaced: client/work-only
   restores preserve the destination runtime; runtime-only restores preserve
   destination work. Replacement is a snapshot, not a file merge. Confirm these
   cases on a spare installation if partial-world portability is needed.
   A successful replacement retains the previous session set as recovery copies
   under `all-session-recovery/<restore UUID>` in app-private storage.
   The restore receipt identifies that copy; this does not offer a GUI recovery
   restore button.
   Failed/interrupted activation recovers the complete previous set rather than
   leaving mixed old/new profiles. Test forced interruption/reopen on a spare
   restored test installation, not the only copy of a live session.
5. After successful restore, reopen the app twice, check selected world/theme,
   each world's gear/Look visibility and controller bindings, then **Start
   runtime → Bots → Refresh roster**. Verify databases, owner inventory/bank,
   existing/new bots, social/hotbar settings, clients/prefixes, renderer options
   and build/deploy receipts. Review login IP before server/client startup,
   especially on another device. Later personal changes must survive another
   app reopen; restored preferences are applied once per restore receipt.

Selected-profile session and database-only restores remain separate checks.
An earlier snapshot correctly returns its earlier roster. Database-only restore
is **Database → Restore a backup → List local backups → Restore selected
snapshot**; it does not restore clients/hotbars/runtimes. Refresh bot identities
and generate fresh previews after any restore.

## Separate unresolved concerns and result record

TAKP NPC visibility and Traditional StoneUI remain independently tracked. Keep
the established CPU/renderer/UI baseline; this pass makes no speculative fix.
For visibility, record zone/NPC, screenshots, settings and server/client logs.
For StoneUI, retain the exact chat response, screenshot, `UIErrors.txt` and the
saved UI INI after normal exit. Neither server NPC-creation evidence nor a camera
trace proves those concerns resolved.

For each section record pass/fail/not tested, world/owner, source/deployment
receipt, steps, visible/chat errors and exported log bundle. Distinguish camera
observations, Yaulp behavior after the new deployment, command file round trips
and archive transport results. Leave untested physical checks open.
