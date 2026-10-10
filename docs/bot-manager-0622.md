# Bots manager — 0.6.22

## Create a roster

1. Stop the server and client; keep this world's runtime running.
2. Open **Bots** and select **Refresh roster**. If modern storage needs enabling, select **Review storage**, inspect its table list and choose **Back up & enable**; a full backup completes before conversion. Search by character/account and select the owner.
3. Add up to 20 named companions. The database supplies allowed race/class combinations. Choose Male or Female and use 4–15 letters per name.
4. Select **Review generation**, check the owner/draft, then **Generate**. Existing bots remain. Repeating Generate after a lost response loads the committed receipt; Review again creates a new request.

TAKP requires its pinned deployed server and migrations 001–011. Its minimal
records use native bot defaults; runtime/inventory records are created by normal
gameplay. Shared-name triggers remain the authority for player/bot reservations.

Custom and Traditional require a newly built/deployed zone server containing
the qualified offline creation utility. Current pins are Custom
`8f6ca0795f424a7b4eab750ff38fc6473d48375c` and Traditional
`4aceae18b94ffaafc08e2b17bc41cd72c77f795d`. The utility calls the normal helper,
preserving rules, appearance, starting items and `EVENT_BOT_CREATE`. It does not
open a listener, connect to world, log in the owner or boot an NPC population.
One transaction contains bot saves, transactional quest writes and the receipt.
Failures roll back the batch. Separate content/data databases and
nontransactional write tables are rejected by generation. The separate reviewed
storage action backs up the full database before converting the listed required
player/bot state tables to InnoDB. It preserves rows and leaves content tables
alone. DDL does not roll back as a batch: a failure reports converted and
remaining tables and the backup path. Review again to continue. No conversion
happens merely by opening the tab or generating bots.
Other pristine Custom source still builds without offline creation; the tab
explains the missing capability.

## Save summon buttons

Select one to five owned bots, choose the matching character settings file and
select **Preview buttons**. The launcher identifies free social slots and offers
explicit free hotbar placements. **Socials only** saves the social without
changing the hotbar. Existing occupied slots, comments, encoding and unrelated
INI values are preserved.

TAKP stores its native five-line social format and bare `E<social index>` hotbar
binding. Its command is `/say #bot spawn Name`; the server groups spawned bots.
RoF2 uses its native social/hotbar format. With target-required invitations,
a modern button spawns the bot, targets the owner as a guard, targets the bot
and invites with pauses. If targeting the bot fails, targeting the owner first
avoids inviting the previous unrelated target. Server rules decide spawn/group
limits. A full group, failed spawn or timing can require another in-game attempt.

Log into the character once if no matching INI exists. Choose explicitly when
more than one matching file exists. Unsupported formats and stale previews are
refused. **Install buttons** creates a backup, then atomically replaces the
reviewed file. Restore requires the same character/world and exact installed
file revision. New user edits are never overwritten by a stale restore.
Creation and file editing are separate, so file failure cannot undo or
duplicate committed bots.

Database import, full database/session restore, portable player restore,
profile switch or deployment changes invalidate old previews. Refresh obtains
the current identity. The editor adds bots and explicitly chosen buttons.

## Source qualification and device check

TAKP's native social keys, host-tagged filename and ten-button pages are checked
against [Zeal](https://github.com/CoastalRedwood/Zeal/tree/50dc9a41738034a56f3de3d34902e20000c34072)
and a [real TAKP INI fixture](https://github.com/davehess/QuarmBossTracker/blob/c96db65aff3496cf3c4da18dfa6267d15f65311d/test/buff-blocks.test.js).
RoF2's complete binding format is checked against its
[configuration generator](https://github.com/pronym-inc/eq-config-generator/blob/5954f357bd9d92ad9b94cd571c1c95f54cfc6eef/ini.py).
Combined pause/command execution follows the
[official EverQuest social explanation](https://www.everquest.com/news/imported-eq-enus-51004).
These fixtures establish supported file formats. Device testing still needs
to confirm proprietary clients load/save the buttons and that spawn/target/
invite timing works on Thor.
