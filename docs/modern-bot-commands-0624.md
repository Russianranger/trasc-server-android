# Custom and Traditional bot command export

Custom and Traditional now use the same command-selection workflow as TAKP:
choose an owner, select saved companions, choose several command actions,
preview the exact socials, and explicitly place each social on a free hotbar
slot or leave it in Socials only. The file-changing install makes a byte-exact
backup and atomically replaces the reviewed character INI. Saving these buttons
does not execute commands or create bots.

The existing TAKP catalogue still contains its 39 commands. The modern catalogue
contains 23 actions verified against both exact server pins:

- Custom: [Triptych-Triumvirate at 8f6ca079](https://github.com/Russianranger/Triptych-Triumvirate/tree/8f6ca0795f424a7b4eab750ff38fc6473d48375c/Release-NMS-Server/zone/bot_commands).
- Traditional: [Server at 4aceae18](https://github.com/Russianranger/Server/tree/4aceae18b94ffaafc08e2b17bc41cd72c77f795d/zone/bot_commands).

The concrete handlers are byte-identical between these pins; their filenames
differ. Custom uses `bot.cpp`, `attack.cpp`, `follow.cpp`, `guard.cpp`,
`hold.cpp`, `release.cpp`, `suspend.cpp` and `taunt.cpp`. Traditional prefixes
those filenames with `bot_`. The canonical registration tables are
`zone/bot_command.cpp` under each source root. `ActionableBots::PopulateSBL`
and `MyBots::PopulateSBL_ByNamedBot` in `bot_command.h` establish the named-bot
ownership boundary.

## Spawn and grouping

**Spawn and group** is selected by default in Custom and Traditional. It keeps
one guarded button per selected companion, with the same existing commands:

```text
/pause 20, /say ^botspawn Name
/target Owner
/pause 5, /target Name
/invite
```

Targeting the owner before targeting the bot keeps a refused or slow spawn from
inviting a previously selected unrelated target. Server grouping limits and
client targeting timing still apply. Exact launcher-recorded legacy per-bot
socials are reused only if their current label, color and commands still match.
Modified personal socials remain untouched.

**Spawn only** is a separate combined action: each line is `/say ^botspawn Name`.
It contains no invitations. Five selected names fit in one native social;
larger selections, up to 20, produce numbered buttons without dropping names.
All other listed actions also use one named command per line and the same
five-line chunking. Spawn and group retains one four-line social per companion.
Every label fits the native 15-byte ASCII limit. Insufficient empty social slots
or more than 120 required socials is refused before any INI write.

## Verified modern actions

Every command below is prefixed with `/say ` in the exported social. `Name`
is always an explicitly selected owned companion. `byname` selects only the
issuing character's spawned bot with that case-insensitive exact name. A missing
name returns no match; it does not fall back to all spawned bots.

| Action | Native command |
| --- | --- |
| Spawn only | `^botspawn Name` |
| Follow owner | `^follow reset byname Name` |
| Follow friendly target | `^follow byname Name` |
| Guard position / stop guarding | `^guard byname Name` / `^guard clear byname Name` |
| Attack target | `^attack byname Name` |
| Gather party | `^botsummon byname Name` |
| Camp party | `^botcamp byname Name` |
| Hold / resume attacks | `^hold byname Name` / `^hold clear byname Name` |
| Suspend / resume AI | `^suspend byname Name` / `^release byname Name` |
| Taunt on / off | `^taunt on byname Name` / `^taunt off byname Name` |
| Pet taunt on / off | `^taunt on pet byname Name` / `^taunt off pet byname Name` |
| Ranged on / off | `^bottoggleranged 1 byname Name` / `^bottoggleranged 0 byname Name` |
| Show / hide helm | `^bottogglehelm 1 byname Name` / `^bottogglehelm 0 byname Name` |
| Readiness report | `^botreport byname Name` |
| Follow status | `^follow current byname Name` |

Attack needs the current enemy target. Follow requires the relevant group/raid
membership; Follow owner clears hate and resets manual following. Resume AI
releases suspension and clears hate; it differs from Resume attacks. Taunt and
ranged commands retain native class, pet and equipment restrictions. Native
permissions and command aliases remain server controlled.

Neither modern pin registers a TAKP-style fallen-bot revive, sit or stand
command. Those are not copied into the modern picker. Stance changes are also
omitted because these handlers reset stance-specific bot settings.

The server source pins, offline creation bridge, database schema and native
runtime receipts remain unchanged. These are exports of existing native
commands, so this feature does not add a new server rebuild prerequisite.

## Preservation and acceptance

Modern and TAKP records retain separate profile, database/deployment and owner
identities. Each selected action has its own deterministic social identity, so
multiple actions for one companion cannot alias a placement. Current-file
revision checks, free-slot checks, named-owner checks, install retries, original
backups and refusal to restore over later personal/game changes remain active.
Legacy 0.6.22 per-bot and 0.6.23 TAKP receipts remain readable and restorable
under their original safeguards.

Test each modern profile with two selected companions: preview the default
Spawn and group action, also select Follow owner and Report party, and confirm
that the preview has two guarded spawn buttons plus combined follow/report
buttons. Install into distinct free positions with the client/server stopped,
then enter the world and check native execution. Test Spawn only separately to
confirm it does not invite. Camp and reopen normally to verify persistence.
After six selected names, combined actions should display numbered five-line
and one-line socials rather than dropping a companion.

Restore immediately after a stopped-client installation and confirm exact
round-trip settings. After a later client save or personal edit, an old restore
must refuse to overwrite the changed file. Full session backups remain the
checkpoint for databases plus client settings; command exports affect only
the selected character settings file.
