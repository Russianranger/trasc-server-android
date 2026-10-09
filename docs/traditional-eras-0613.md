# Traditional era presets and launcher themes — 0.6.13

The launcher adds reviewed **Velious**, **Luclin**, **Planes of Power** and
**Default** ruleset switching for the existing qualified Traditional server.
These are PEQ-compatible era approximations. TAKP's database and engine are
research references; neither is imported over the working installation.

## What each era selects

| Setting | Velious | Luclin | Planes of Power |
| --- | --- | --- | --- |
| Level / experience / skill ceiling | 60 | 60 | 65 |
| EQEmu current expansion | 2 | 3 | 4 |
| RoF2 expansion mask | 3 | 7 | 15 |
| Expansion-tagged AA ranks | Through Velious; pre-Luclin limitations below | Through Luclin | Through PoP |
| Worn spell focus effects | Disabled | Enabled | Enabled |

All three presets request older HP/mana formulas, normal regeneration without
later rest regeneration, classic bind-wound/con/taunt/Harm Touch/Master Wu options,
item and naked corpses, seven-day corpse decay and three-hour resurrection eligibility.
Death XP begins at level 11 and corpse item loss at level 10. Later tutorial,
return-home, extended-target, aggro-meter, mercenary, bard-melody, parcel and
bazaar warp conveniences are disabled. Item-click casts do not receive focus bonuses.

There are **47 source-supported rule values per era**. The complete exact values,
per-rule reason and pinned primary-source links are bundled in
[era_presets.json](../backend/era_presets.json). Existing over-cap characters keep
their level; the presets do not delete characters, inventory, learned spells,
purchased AA, unspent AA points or stored experience.

Existing XP multipliers, race/class XP curves, group/raid rewards and unrelated
zone settings remain inherited. TAKP's XP algorithms and Al'Kabor-specific bonuses
are not copied into PEQ: upstream uses different formulas, and changing a stored-XP
level curve can recalculate existing characters when they next gain or lose XP.

## Why the attached PEQ needs more than a global dropdown

The supplied `peq-latest(1).zip` contains PEQ system/content dumps dated
September 28, 2025, `db_version=9328`. Its default set is **ID 1**, and it has
no `variables.RuleSet` row. The default expansion is 9 and maximum level is 70.

**590 of 618 zone records have explicit rulesets**: 359 use `pop+`, 217 use
`default`, and 14 use other sets. A global named ruleset alone would miss these
zones. The launcher creates owned era rulesets and composite sets that retain
each original zone set's unrelated overrides, then routes all existing zone
records to the appropriate era set. It never replaces the original sets.

The pinned engine also calls `SetExpansionContext()` during world, zone and
shared-memory startup; that call reloads the set named `default`. While an era
is selected, the launcher therefore temporarily mirrors only its 47 managed
keys into the real default set and saves every original row, notes and absence.
Returning to Default restores those values and all original zone routing.
Other default rule values are untouched. The next normal server start reruns
the existing compiled shared-memory helper, so cached item-focus settings follow
the new selection. No server compilation or runtime replacement is needed.

The ruleset IDs are allocated from available unsigned-tinyint IDs; nothing
assumes `default` is 0 or 1. Era ownership and the exact baseline are stored
transactionally inside the same database so session/database backups carry them.
A full database backup precedes mutations. The supplied target tables are InnoDB;
unsupported storage engines, source versions, duplicate identities, ownership
conflicts or stale previews are rejected before data changes.

## Accuracy boundaries

Normal-player access to later zones follows the engine's `zone.expansion` gate.
GM characters and the database's 24 `bypass_expansion_check` rows are exceptions.
Content carrying accurate minimum/maximum expansion tags is filtered. However,
162,341 of 165,711 spawns, 63,123 of 64,260 merchant entries and 482,562 of
482,577 loot entries have an unrestricted minimum expansion in this attachment.
Items, NPC stats and spells lack equivalent filters. Modern content inside an
older zone may consequently remain. Era-specific NPC tuning, loot, merchants,
quests, spell progression and raid flagging require separate reviewed data work.

TAKP uses a different client, schema and mechanics. Its charm/resist behavior,
monk AC, pet/group XP, required-level/bane behavior and XP smoothing have no
complete equivalent in these rule values. The RoF2 masks influence creation
choices; the pinned server's combination validation is not a complete
server-side expansion restriction. Existing Beastlords and Vah Shir remain.

AA filtering depends on the PEQ `aa_ranks.expansion` tags. Velious does not erase
existing AA or forcibly change a character's AA-XP allocation. Set allocation
to ordinary XP when using a pre-AA character; the preset does not manufacture
a TAKP-only `Character:DisableAAs` rule. Existing passive AA effects can remain.

## Use and revert on the existing installation

1. Update the APK in place. Camp in a zone available in the target era, then
   stop the client and server. Keep the Traditional runtime open.
2. Open **Gameplay → Expansion era**. Choose **Velious**, **Luclin** or
   **Planes of Power**. Read the rule changes, zone routing and limitations.
3. Choose **Apply chosen era**, then **Start server** and reopen the client.
   Keep the existing compiled server, database, client, prefix, DirectX helpers,
   runtime and controller settings. Do not reimport the attached PEQ ZIP.
4. To revert, stop the client and server, choose **Default**, review, then
   **Apply database default**. Start the server again. Original default rows
   and zone ruleset assignments are restored; player progress is retained.
5. The manual rule editor remains available. Returning to a previously created
   era preserves manual edits to its owned sets; presets are not silently
   regenerated. Save or discard pending editor changes before an era switch.

Switching requires a current reviewed preview. Changes made meanwhile invalidate
it; choose the era again to review fresh values. The feature is isolated from
TRASC Custom and does not auto-start, compile or replace anything.

For a focused device check, first confirm the displayed active era and normal
login, then check an appropriate later-expansion zone with a non-GM character,
its class/AA options, and one ordinary zone using an earlier explicit ruleset.
Stop/start once to verify persistence. Return to Default and verify the previous
rules and zone routing. Export fresh logs if the launcher refuses a switch or
server behavior disagrees with the reviewed rules.

## Launcher appearance

The **Launcher theme** selector above the shared tabs offers **Default**,
**Necromancer** and **Monk**. Default retains the current launcher appearance.
Necromancer uses a violet crypt, bone sigil and soul-fire accents; Monk uses
jade/gold, a mountain training hall and fist banner. Artwork is original offline
vector content. The device-local choice persists across reloads and world-profile
switches. Choosing Default restores the original palette and scenes.

Themes do not change server rules, character INIs, StoneUI or game models.
The existing camera, name/sky comparison, viewport gear actions and
**Return to Launcher** remain available.

## Primary research

- [Official TAKP server and rule catalogue](https://github.com/EQMacEmu/Server/blob/d8d589a0ce486ee47ec990d3c3bbbf604b2572a1/common/ruletypes.h).
- [Official TAKP database archive](https://github.com/EQMacEmu/Server/blob/d8d589a0ce486ee47ec990d3c3bbbf604b2572a1/utils/sql/database_full/alkabor_latest.zip), export `alkabor_2026-09-08-19_10`.
- [Qualified Traditional rule catalogue](https://github.com/Russianranger/Server/blob/4aceae18b94ffaafc08e2b17bc41cd72c77f795d/common/ruletypes.h).
- [Content expansion initialization](https://github.com/Russianranger/Server/blob/4aceae18b94ffaafc08e2b17bc41cd72c77f795d/common/content/world_content_service.cpp).
- [Ordinary-player zone expansion checks](https://github.com/Russianranger/Server/blob/4aceae18b94ffaafc08e2b17bc41cd72c77f795d/zone/zoning.cpp).
- [AA rank expansion validation](https://github.com/Russianranger/Server/blob/4aceae18b94ffaafc08e2b17bc41cd72c77f795d/zone/aa.cpp).
- [Stored-XP and level-cap behavior](https://github.com/Russianranger/Server/blob/4aceae18b94ffaafc08e2b17bc41cd72c77f795d/zone/exp.cpp).
- [Daybreak Luclin primer](https://www.everquest.com/news/eq-shadows-of-luclin-progression-primer) and [Planes of Power primer](https://www.everquest.com/news/eq-planes-of-power-progression-primer), confirming the era additions and PoP level-65 ceiling.
- [EQEmuTools expansion switcher](https://github.com/EQEmuTools/eq-expansion-switcher/tree/55fa9e12937d69a2cf0be073a494d783d2f54aa1): reviewed as another approach, but it replaces client zone assets. It is excluded here to preserve the imported RoF2 client.
- [Bounded attached-PEQ audit](peq-era-audit-0613.json).

Automated configuration, transaction, rollback, routing, preference and browser
checks validate the launcher implementation. Physical era behavior on Thor
remains an acceptance test, not a claim of complete historical fidelity.
