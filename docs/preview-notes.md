# TRASC Android 0.6.22 / code 71

The **Bots** tab is available in TRASC Custom, Traditional and TAKP. Stop the
server and client, keep the runtime open, and select **Refresh roster**. Select
an existing owner character, choose names and valid race/class/gender
combinations, review the batch, then generate it. Existing bots are preserved.
Committed request receipts recover the original batch after a lost response.

TAKP uses its native owner-linked records and eleven installed playerbot
migrations. Custom and Traditional use a qualified one-shot command in the zone
server that calls their normal bot creation helper, including appearance,
starting items, rules and creation quests. **Rebuild and deploy the modern world
server** to enable generation; an older deployment can still show its roster.
Unsupported pristine Custom source still compiles normally with offline
creation unavailable. No database is reinitialized.

If modern bot storage is not transactional, use **Review storage**, inspect the
exact table list, then **Back up & enable**. This opt-in action completes a full
database backup before converting only the required player/bot state tables to
InnoDB. DDL is not an atomic batch: a failure reports completed and remaining
tables with the backup, and a fresh review can continue. Generation itself never
silently converts tables. TAKP's existing migration path remains separate.

Select up to five saved bots and preview their summon commands. Choose free
social and hotbar slots in the matching character INI. Occupied buttons are
preserved; every installation has a revision-checked backup and restore action.
TAKP's spawn command automatically groups the bot. Modern clients use native
spawn, target and invite commands with pauses and the server's invite rule.
Summoning and joining a group happen in game, separately from offline creation.
Log into the client once if it has not written a matching character INI.

TAKP's EQW helper now forces Wine to recenter the cursor after each captured
input. An open Wine 10/Xvnc fixture reproduces the cached-center offset that
caused motion to continue in the previous direction and verifies immediate
reversal after the repair. Camera feel on Thor remains a device check. The
previous 15% look-motion gain and transient **Look off / Look on** toggle remain.
Look starts off and releases when opening launcher menus/keyboard, losing
focus/capture, pausing or leaving the client.

Drag the gear to move the gear and Look tile together. Positions are saved per
world and clamped to the safe screen area. The gear menu has **Show mouse look
tile**, movement presets and **Reset controls position**. Hiding the tile keeps
the optional controller **Toggle mouse look** action available. A tap still
opens the menu; a drag releases captured input.

Install as an APK update. Keep **Accurate / Legacy math accuracy** selected for
the confirmed TAKP NPC-model fix and start the existing imported client. The
exact previous managed EQW helper is upgraded on launch, with its original kept
in a separate backup. Custom or modified helpers are refused with a clear error.
No client reimport, prefix reset or database reset is required. The other TAKP
DLLs, imported game files, runtime and existing TAKP server remain in place.
All 21 native launcher components are reused from verified 0.6.21 with the same
preview signing certificate.

Grouped Runtime, Server and Client controls remain aligned across all worlds
and themes. TAKP retains its original `spells_en.txt`; separate server exports
remain `spells_us.txt` and `SkillCaps.txt`. RoF2 DLL hooks, launcher skin
activation, Spire editing and PEQ era presets remain unavailable in TAKP.

Publication requires the complete Python suite with real MariaDB cases,
launcher browser programs, JVM/native checks, DirectX verification, Android
assembly/lint, signing/native reuse, TAKP ARM64 qualification and native
offline bot creation qualification for both modern server pins. See the
[0.6.22 verification report](https://github.com/Russianranger/trasc-server-android/blob/main/docs/release-status-0622.md)
and [Bots guide](https://github.com/Russianranger/trasc-server-android/blob/main/docs/bot-manager-0622.md).

On Thor, check immediate camera reversal on both axes, hide/show the Look tile,
drag the gear away from game windows and reopen the client. For each world,
create a small batch, install its buttons, then log into the owner and test
spawning/group invites and backup restore. INI round trips and in-game timing
remain device acceptance work; qualification fixtures are not a Thor session.
