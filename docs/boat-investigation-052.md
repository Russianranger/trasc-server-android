# Boat investigation and merchant picker — 0.5.2

The user reports Spire working and authorizes easier merchant additions and reopening boats. This supersedes the older boat deferral. Version 0.5.2/code 42 adds merchant selection helpers and a read-only boat diagnostic candidate. **It does not claim to fix boat collision or sliding yet.**

## Merchant workflow

Open an NPC in Spire and choose **Add item to this merchant**, or follow its merchant inventory and choose **Add item to merchant**. An existing stock record also offers **Add another item to this merchant**. Search for the item by name or ID and tap it. The merchant ID and first free positive slot are suggested automatically. Preview and save through the existing backup, stopped-server and audit checks.

From an unfiltered merchant list, enter the inventory ID once and use **Use next free slot**. Selecting an item never saves immediately. A suggestion is not a reservation: a concurrent insertion is rejected, never overwritten. Inventories can be shared by multiple NPCs; the form warns that all users of that inventory see the edit. Numeric/manual editing remains available. Item creation and automatic assignment of a new inventory to an NPC remain outside this helper.

## Verified client evidence

Private executable: SHA256 `4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3`, 8,774,656 bytes. Public layout reference: [eqlib emu-rof2](https://github.com/macroquest/eqlib/tree/3eafc8217e690b3c93201a17ec205410db1cac82). Server reference: [Triptych client movement](https://github.com/Russianranger/Triptych-Triumvirate/blob/4c653ca2d16aaede33b7011d07254c520ac5f5df/Release-NMS-Server/zone/client_packet.cpp). Private inputs and full disassembly are not committed.

| Routine, preferred VA | Observed behavior |
| --- | --- |
| `0x59E530`, player vtable `0x9D71F0 + 0x50` | Tests bit 0 in race/gender flags, via player `+0x234`, flags `+0x2C` |
| `0x475F40` | Collision callback accepts an actor classified as a vehicle and calls the original setter for the colliding player |
| `0x8CFCE0`, `0x8CFD10` | Get/set player vehicle pointer at `+0x150`; setter takes one stack argument, `ret 4` |
| `0x507230` | Floor query caches stable unattached positions; attached passengers force the fresh-query path |
| `0x8D1C50` | Begins world-to-vehicle coordinate conversion using the attached vehicle (traced; not covered as a whole by the fixture) |

Executing the original collision callback with synthetic graphics/application-data objects successfully attaches flags 1, 3, 11 and 27; flags 0, 2 and 8 are rejected. Only the passenger vehicle pointer changes in that fixture. Original getter/detach and both floor-cache branches also pass. Original race-registration calls show SHIP/PRE (72), LAUNCH (73), GSP (114) and SHP (404) already have flag 3; BOAT (141) has flag 1. There is no basis for blindly rewriting all ship race flags.

Run `tools/verify-client-boats.py /private/path/eqgame.exe` with pefile and Unicorn to repeat the ten original-code checks. It checks the complete executable identity and calling convention/register preservation. This is **not** a full rendered-client or live server reproduction. The original server already converts vehicle-relative client coordinates; inspecting that source does not establish that a failing client is actually sending them.

These findings do not support a general forced-attachment, teleport or collision patch. First collect the failure at the collision/attachment boundary. Missing ship collision meshes, client state, movement and rotation, and cross-zone handoff remain distinct possibilities.

## Diagnostic implementation

Client → Graphics, audio & launch options → **Boat investigation → Record collision and passenger state**. Default off. Launcher requires the exact executable and the new native dinput8 marker. The compiled adapter also checks PE identity, original vehicle getter and vehicle-predicate vtable entry. It samples after the normal, exact mouse-buffer DirectInput read, in any camera view; it does not require mouse-look/recentering or the particle repair to be enabled.

`client-boats.log` records local and selected/attached-boat IDs, zone, positions, headings, movement, floor/cache, actor presence, race flags and vehicle pointer. Known ship races remain observable when flags are missing. `passenger` is a layout observation, not by itself proof of a valid attachment; use the vehicle pointer/ID and positions. Off/nonclient/unsupported modes remain inactive. Reads reject invalid objects, nonfinite position, stale local-player pointers and menus. Logs are bounded by 512 samples and 256 KiB; active boat samples are at most twice per second, idle heartbeat at most once per five seconds. Logs rotate on launch and are included in Export Logs.

There are no memory writes to client state, hooks replacing game functions, coordinate changes, new server rules or modified assets. Preserve existing camera/loading/particle/controller/rendering settings.

## Thor acceptance

1. Install 0.5.2 in place after stopping the client, server and runtime. Start the existing runtime. No runtime reinstall, server rebuild or client/source reimport is required.
2. In Spire, search a merchant NPC and use **Add item to this merchant**. Search/select an item without looking up its ID; verify inventory/slot/item in Preview, then Save. Confirm the audit/backup and inspect stock after restarting the server. Remove the test entry through a removal preview. Test a merchant with an empty linked inventory if available.
3. For boats only, compile and deploy dinput8.dll once with this version using the already imported Microsoft toolchain/source. Merchant improvements do not require this rebuild. Keep native dinput8 enabled and all working client settings.
4. Enable boat diagnostics and launch. Use **one named ship in one zone** first, preferably the Qeynos/Erudin transport if available. Select the ship and keep it targeted. Observe for 10 seconds beside the dock, then walk aboard. If collision allows boarding, stand still for 20–30 seconds during straight movement and a turn, then walk/jump off. Keep the run about 1–2 minutes. Avoid zoning in this first run.
5. Stop the client and export logs. Report the ship/NPC name, zone, whether stationary boarding worked, whether the player fell through or slid, and when it happened (a short video is useful). If the ship cannot be targeted, report that; an existing vehicle attachment is still recorded, but missing-collision diagnosis needs a selected ship.

If geometry contact occurs but attachment drops, instrument the original attach/detach call sites next. If attachment persists while position drifts, verify coordinate transforms and movement packet handling. If the actor has no usable deck collision, inspect that ship's model/collision assets and graphics collision query before adding carry behavior. Full routes and zoning follow a successful single-zone test.

## Verification status

Local: ten original executable checks pass; Python suite, JavaScript syntax and whitespace checks run. CI must validate the real MariaDB draft/save/concurrency cases, UI picker/pagination/context, MSVC x86 read-only snapshot fixture, actual DLL build and every existing Android/ARM64 gate before release. Physical merchant-picker and boat diagnostics acceptance remains pending.
