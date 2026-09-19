"""Focused content tools. Database names describe EQEmu's public schema.

This is a native TRASC implementation, not a bundled Spire service or UI.
Only listed fields can be edited; installed columns and bounds are authoritative.
"""


def entity(label, fields, summary, *, add=False, remove=False, export=False):
    return dict(label=label, fields=fields.split(), summary=summary.split(),
                add=add, remove=remove, export=export)


CATALOG = {
    'items': entity('Items', 'Name lore idfile icon itemtype slots classes races deity '
        'weight size ac hp mana endur astr asta aagi adex awis aint acha mr fr cr dr pr '
        'damage delay range price nodrop norent stackable stacksize reqlevel reclevel '
        'click_effect proc_effect worn_effect focus_effect scrolleffect', 'id Name icon itemtype'),
    'npc_types': entity('NPCs', 'name lastname level race class bodytype hp mana gender '
        'texture helmtexture size runspeed walkspeed AC STR STA DEX AGI INT WIS CHA '
        'MR CR DR FR PR mindmg maxdmg attack_count attack_delay accuracy avoidance '
        'loottable_id merchant_id npc_spells_id npc_faction_id aggroradius assistradius',
        'id name level race loottable_id merchant_id'),
    'loottable': entity('Loot tables', 'name mincash maxcash avgcoin', 'id name mincash maxcash', add=True),
    'loottable_entries': entity('Loot table drops', 'loottable_id lootdrop_id multiplier droplimit mindrop probability',
        'loottable_id lootdrop_id probability multiplier', add=True, remove=True),
    'lootdrop': entity('Loot drops', 'name', 'id name', add=True),
    'lootdrop_entries': entity('Loot drop items', 'lootdrop_id item_id item_charges equip_item chance disabled_chance '
        'trivial_min_level trivial_max_level multiplier npc_min_level npc_max_level',
        'lootdrop_id item_id chance item_charges', add=True, remove=True),
    'merchantlist': entity('Merchant inventory', 'merchantid slot item faction_required level_required '
        'min_status max_status alt_currency_cost classes_required probability',
        'merchantid slot item probability', add=True, remove=True),
    'spells_new': entity('Spells', 'name player_1 teleport_zone you_cast other_casts cast_on_you cast_on_other '
        'spell_fades range aoerange pushback pushup cast_time recovery_time recast_time '
        'buffdurationformula buffduration AE_duration mana targettype resisttype goodEffect '
        'activated skill zone_type EnvironmentType TimeOfDay '
        + ' '.join(f'{prefix}{i}' for prefix in ('effect_base_value', 'effect_limit_value',
                 'max', 'formula', 'effectid') for i in range(1, 13)) + ' '
        + ' '.join(f'classes{i}' for i in range(1, 17)), 'id name mana targettype', export=True),
    'db_str': entity('Database strings', 'value', 'id type value', add=True, export=True),
    'aa_ability': entity('AA abilities', 'name category classes races drakkin_heritage deities status type '
        'charges grant_only first_rank_id enabled reset_on_death auto_grant_enabled',
        'id name first_rank_id enabled', export=True),
    'aa_ranks': entity('AA ranks', 'upper_hotkey_sid lower_hotkey_sid title_sid desc_sid cost level_req '
        'spell spell_type recast_time expansion', 'id title_sid cost level_req spell', export=True),
    'aa_rank_effects': entity('AA rank effects', 'rank_id slot effect_id base1 base2',
        'rank_id slot effect_id base1 base2', add=True, remove=True, export=True),
}

# source table, source column, target table, target column, accepted empty IDs
REFERENCES = [
    ('npc_types', 'loottable_id', 'loottable', 'id', (0,)),
    ('npc_types', 'merchant_id', 'merchantlist', 'merchantid', (0,)),
    ('npc_types', 'npc_spells_id', 'npc_spells', 'id', (0,)),
    ('npc_types', 'npc_faction_id', 'npc_faction', 'id', (0,)),
    ('loottable_entries', 'loottable_id', 'loottable', 'id', ()),
    ('loottable_entries', 'lootdrop_id', 'lootdrop', 'id', ()),
    ('lootdrop_entries', 'lootdrop_id', 'lootdrop', 'id', ()),
    ('lootdrop_entries', 'item_id', 'items', 'id', ()),
    ('merchantlist', 'item', 'items', 'id', ()),
    ('aa_ability', 'first_rank_id', 'aa_ranks', 'id', (0, -1)),
    ('aa_ranks', 'spell', 'spells_new', 'id', (0, -1, 65535)),
    ('aa_ranks', 'prev_id', 'aa_ranks', 'id', (0, -1)),
    ('aa_ranks', 'next_id', 'aa_ranks', 'id', (0, -1)),
    ('aa_rank_effects', 'rank_id', 'aa_ranks', 'id', ()),
] + [('items', c, 'spells_new', 'id', (0, -1, 65535)) for c in
     ('click_effect', 'proc_effect', 'worn_effect', 'focus_effect', 'scrolleffect')] + [
    ('aa_ranks', c, 'db_str', 'id', (0, -1)) for c in
    ('upper_hotkey_sid', 'lower_hotkey_sid', 'title_sid', 'desc_sid')]

PAIRS = [('mincash', 'maxcash'), ('mindmg', 'maxdmg'), ('min_status', 'max_status'),
         ('trivial_min_level', 'trivial_max_level'), ('npc_min_level', 'npc_max_level')]

AA_STRING_TYPES = {'title_sid': 1, 'lower_hotkey_sid': 2, 'upper_hotkey_sid': 3, 'desc_sid': 4}

# Friendly names for entry tables without their own name column.
RELATED_NAMES = {
    'merchantlist': [('item_name', 'item', 'items', 'id', 'Name')],
    'lootdrop_entries': [('item_name', 'item_id', 'items', 'id', 'Name'),
                         ('drop_name', 'lootdrop_id', 'lootdrop', 'id', 'name')],
    'loottable_entries': [('table_name', 'loottable_id', 'loottable', 'id', 'name'),
                          ('drop_name', 'lootdrop_id', 'lootdrop', 'id', 'name')],
}


def bounds(table, name):
    if table == 'items' and name == 'mana': return (None, None)
    if name in ('chance', 'disabled_chance', 'probability'): return ('0', '100')
    if name in ('mincash', 'maxcash', 'avgcoin', 'cost', 'mana', 'cast_time', 'recast_time',
                'recovery_time', 'level_req', 'level_required', 'multiplier', 'mindrop', 'droplimit'):
        return ('0', None)
    if name in ('enabled', 'grant_only', 'reset_on_death', 'auto_grant_enabled', 'equip_item'):
        return ('0', '1')
    if table == 'merchantlist' and name == 'slot': return ('1', None)
    return (None, None)


def impact(table):
    if table == 'spells_new':
        return 'Export & sync client data, then restart the server and relaunch the client. Saved RoF2 filtering remains active; IDs 45000 and above are not made compatible by editing.'
    if table in ('db_str', 'aa_ability', 'aa_ranks', 'aa_rank_effects'):
        return 'Export & sync client data for database strings and spells. AA definitions/effects are sent by the server; restart it and relog to refresh them. Existing character AA progression is not edited.'
    return 'Restart the server to load the saved content consistently. Existing characters, inventories and progression are not edited.'
