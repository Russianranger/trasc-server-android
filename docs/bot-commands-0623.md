# TAKP bot command buttons in 0.6.23

The user confirmed that TAKP bot creation and spawning work with 0.6.22. This
update extends character button export; it does not recreate bots, migrate the
database, or change the pinned TAKP server.

## Export combined command buttons

Stop the client and server, leave the TAKP runtime open, and open **Bots**.
Refresh the roster and choose the owner character. Select the saved companions
to include, then choose the command actions to export. Spawn is selected by
default. Select Revive as a separate action to produce a separate revive button.

Choose **Preview buttons** to discover the matching character settings file.
If several files match, select the correct file and preview again. A combined
Spawn button contains one native `/say #bot spawn Name` line per selected bot.
Revive similarly contains `/say #bot revive Name` lines. The commands run when
the player presses the exported social in game; saving the INI executes none
of them.

A native social can contain five lines. Up to five selected bots fit in one
button for each action. Larger selections are split into numbered buttons,
without dropping names. Server spawn/group limits still apply. More than 120
required social slots or insufficient empty slots is refused before editing.

The pinned server has `#bot spawn all`, but that command chooses bots by roster
ID order and stops at its active limit. Explicit names preserve the selection
made in the launcher. There is no native `#bot revive all`, so the launcher
generates the equivalent named lines for the selected companions.

Revive requires the owner to be out of combat, the bot to be fallen and not
already active, and at least 60 seconds since its recorded fall. It restores
one HP and zero mana. Revive, then spawn; it is not a full heal or automatic
spawn. A premature attempt should display the server's normal refusal.

## Additional actions

The action catalogue follows `HandlePlayerBotCommand` in the pinned
`Russianranger/Servertakp` source, revision
`25bf70acb6bd24853cf09e447ddd62b96a4491a4`:

https://github.com/Russianranger/Servertakp/blob/25bf70acb6bd24853cf09e447ddd62b96a4491a4/zone/player_bot.cpp

Actions include movement and combat behaviors, assistance, bot summon and
dismissal, sit/stand, casting/taunt/ranged/pet toggles, AI suspend/resume,
supported utility casts, and reports. Each exported line names a selected
owned bot. Read the action description for target, combat and class
requirements; availability in the picker does not override the server's
checks. Destructive roster/group/inventory management is not included.

After preview, explicitly choose free hotbar placements or **Socials only**,
then **Install buttons**. Existing occupied social/hotbar slots, unrelated INI
settings, comments and encoding are preserved. Every file-changing install makes a backup
and atomically replaces only the reviewed current file.

The existing Custom and Traditional per-bot spawn/group export remains
available. The additional TAKP catalogue is not advertised as compatible with
those different servers.

## Acceptance and restore

Test two or more selected bots with one Spawn button and a separate Revive
button. Check a combined Follow or Report action and multiple actions in one
export. Camp/exit normally, reopen the client and confirm that the social names,
lines and chosen hotbar placements persist.

Test a successful **Restore selected backup** immediately after installation,
before the client saves the file, then install the desired buttons again.
After a later client save or personal edit changes the installed file revision,
an old restore must refuse to overwrite it. Existing 0.6.22 per-bot backups stay
readable with their original safeguards. Database restore does not restore
character hotbars; a complete session checkpoint includes the client files.

On a problem, export the log bundle and report the selected owner/bots/actions,
the previewed lines, the visible in-game response and whether the failure
occurred during preview, install, activation, normal save or restore.
