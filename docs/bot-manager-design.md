# Proposed Bots manager

Proposal only: this release does not implement a Bots editor, creation bridge or social installer. Version one would manage names, race/class/gender, ownership and summon/group socials, without a launcher equipment generator.

## Proposed flow

Add a **Bots** tab with world and searchable active-character filters (name/account/level). World switching clears drafts; requests carry profile/deployment identity.

Separate saved roster from creation draft. Rows contain name, database-derived race/class and Male/Female gender. Race changes clear invalid classes. **Generate bots** previews/creates a validated batch; **Preview socials / Install socials** shows commands, character file and free slots for selected bots.

Roster size and party size differ. A standard summon set has at most five bots and respects spawn rules. TAKP permits five owned spawned bots; modern creation/spawn limits depend on total/class rules and owner overrides.

## Separate server adapters

| World | Ownership/schema | Creation and command strategy |
| --- | --- | --- |
| TAKP | `takp_bot_data.id`, `owner_character_id = character_data.id`; eleven bot migrations | Offline insertion can match `#bot create Name Class Race Gender`. Summon with `#bot spawn Name`. Spawn automatically joins or creates the owner's group; no extra invite command. |
| Traditional | `bot_data.bot_id`, `owner_id = character_data.id`, plus state tables | Proposed server creation bridge; current commands are `^botcreate Name Class Race Gender`, `^botspawn Name`, then the verified group-invite flow. |
| TRASC Custom | Modern bot tables with fork-specific hooks/rules | Separate adapter qualified against installed provenance/schema; shared table names do not establish compatibility. |

TAKP uses `char_create_combinations`: classes 1–15, races 1–12/128/130, 86 seed pairs. Modern adapters decode `bot_create_combinations` class bitmasks and server/content restrictions. Use labels, never raw SQL/command fragments.

TAKP inserts only owner/name/class/race/gender. Leave runtime/inventory/spell rows absent; spawn computes stats/spells/AAs. HP/mana default to -1; HP 0 means fallen. Do not pre-set active status or spell IDs.

Modern minimal SQL skips appearance, creation saves/hooks and starting items; loading regenerates some defaults, not creation. A proposed headless bridge would reuse server logic and return IDs. Existing helpers require `Client*` and zone/quest/content context; design offline owner context and hook semantics first. Qualify transactions because `Bot::Save` tolerates some ancillary failures. Online creation socials are an alternative, not offline creation. Starting-item hooks remain server-owned.

## Safe creation and retries

Stop client/world/zone services; MariaDB may run. Verify deployment/schema. TAKP needs eleven migrations, 24 InnoDB tables and six name triggers; Generate bots never installs migrations.

Lock/revalidate character ID/account/name/active status (`is_deleted=0` on TAKP), rows and limits. Owner keys are `character_data.id`; TAKP has no owner foreign key. Shared UI policy: 4–15 ASCII letters, profile case rules, repeat-letter restrictions and database name filters. Check player/bot collisions including deleted names; TAKP triggers remain authoritative.

One transaction should commit TAKP batch/IDs/idempotency receipt or roll back; modern bridges need equivalent guards. Receipt: token, draft hash, profile/database identity and IDs. Retry returns the same result; reject another owner's name and pre-restore receipts. Select existing owned bots explicitly.

Stage socials, commit creation, then install; SQL/file writes cannot share a transaction. File failure retains bots and offers **Socials pending → Retry**; SQL failure installs nothing. Retry rechecks ownership/file revision without creating again.

## Per-character socials

Match the selected character's actual INI, never guess its server suffix or edit `eqclient.ini`/`UI_...ini`. ROF2 fixtures use `Character_Server.ini`, `[Socials]`, `PageNButtonMName/Color/Line1..5`; social index is `(N-1)*12+(M-1)`. Qualify each imported client with an exported file and round trip. TAKP filename/keys remain unverified; its installer stays gated. Preserve sections/encoding/newlines; ambiguous files are preview-only.

Socials have five lines. TAKP `/say #bot spawn Name` auto-groups with owner leadership/space. Modern `/say ^botspawn Name` requires grouping: `/invite Name` when `Character:GroupInvitesRequireTarget=false`, otherwise `/target Name` then `/invite`. Preserve that rule. Spawn delivery is asynchronous: qualify pauses before targeting/inviting. Propose per-bot spawn/target/invite socials or a previewed multi-social sequence. Five bots cannot fit spawn/target/invite into five lines; promise no one-button team until a group-spawn path is verified.

Use slots only when name and all five lines are empty, with page/button labels, backups and revision checks before atomic replacement. Preserve literal `#bot` text; comment-stripping INI parsers are unsuitable. Reinstall only owned/identical socials. Keep the client stopped: it rewrites INIs on exit. Offer restore; version one preserves personal socials/hotbars.

Offer **Place on hotbar** with an explicitly selected empty bar/page/button, alongside the social-slot preview. The reviewed ROF2 generator writes `[HotButtons]` for bar one and `[HotButtons2]` through `[HotButtons10]` for later bars, with `PageNButtonM=E<social-index>,@-1,0000000000000000,0,<label>`. For example, social page two/button one has index 12. Qualify that binding by loading and saving it in the imported client before enabling installation; preserve occupied and non-social bindings. TAKP placement remains gated on its own verified fixture. Social installation and visible hotbar placement are separate steps in the preview, with one backed-up file update where they share a file.

## Reviewed sources and qualification

- [TAKP creation, 25bf70a](https://github.com/Russianranger/Servertakp/blob/25bf70acb6bd24853cf09e447ddd62b96a4491a4/zone/gm_commands/bot.cpp); also `zone/player_bot.cpp`, `zone/player_bot_roster.inc`, `zone/player_bot_schema.h`, `common/database.cpp`, migrations 001–011 and `alkabor_latest.zip`.
- [Traditional helper, 4aceae1](https://github.com/Russianranger/Server/blob/4aceae18b94ffaafc08e2b17bc41cd72c77f795d/zone/bot_command.cpp), qualified launcher pin; also `zone/bot_commands/bot_bot.cpp`, `zone/bot.cpp`, `zone/bot_database.cpp`, `zone/client_packet.cpp` and bot repositories.
- [Custom helper, 8f6ca07](https://github.com/Russianranger/Triptych-Triumvirate/blob/8f6ca0795f424a7b4eab750ff38fc6473d48375c/Release-NMS-Server/zone/bot_command.cpp), reviewed main; corresponding files under `Release-NMS-Server`. Qualify installed `trasc-source.json`/`bin/build-info.json`; Custom has no universal build pin.
- [ROF2 INI generator, 5954f35](https://github.com/pronym-inc/eq-config-generator/blob/5954f357bd9d92ad9b94cd571c1c95f54cfc6eef/ini.py), corroborated by [character fixture, 0316267](https://github.com/Findarato/eqconfigs/blob/0316267109fd3069f6a301923c142e98ce7d1220/thj/Puen_thj.ini). These establish external format, not acceptance of the imported client.

Acceptance needs real database transaction/trigger, collision/limit, retry, stale-identity, stopped-process and file-failure cases. Device checks must summon/group a new roster and retain IDs through camp/relogin/restart. This release provides the proposal only.
