"""Era planning invariants independent of SQL transport."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import era_rules as era
from rule_catalog import metadata


def fixture_state():
    presets = era.manifest()
    catalog = {}
    for preset in presets['presets'].values():
        for name, spec in preset['rules'].items():
            value = spec['value']
            kind = 'bool' if value in ('true', 'false') else ('int' if value.lstrip('-').isdigit() else 'real')
            catalog[name] = metadata(name, kind, default=value)
    columns = {'rule_sets': ['ruleset_id', 'name'], 'rule_values': ['ruleset_id', 'rule_name', 'rule_value', 'notes'],
               'variables': ['id', 'varname', 'value', 'information', 'ts'], 'zone': list(era.ZONE_COLUMNS)}
    default = {'ruleset_id': '1', 'rule_name': 'Character:MaxLevel', 'rule_value': '65', 'notes': None}
    extra = {'ruleset_id': '2', 'rule_name': 'Character:ExpMultiplier', 'rule_value': '2.25', 'notes': 'Keep me'}
    zones = [dict(zip(era.ZONE_COLUMNS, map(str, row))) for row in ((9, 'qeynos', 1, 0, 0), (10, 'velketor', 112, 0, 1), (11, 'vexthal', 158, 0, 2), (12, 'vexthal', 158, 0, 20))]
    data = {'rule_sets': [{'ruleset_id': '1', 'name': 'default'}, {'ruleset_id': '2', 'name': 'pop+'}, {'ruleset_id': '20', 'name': 'fix_pathing_z'}],
            'rule_values': [default, extra], 'variables': [], 'zone': zones}
    raw = {table: sorted(era.encoded(row, columns[table]) for row in values) for table, values in data.items()}
    shape = {'engines': {t: 'InnoDB' for t in era.TABLES}, 'columns': {}, 'keys': {}, 'column_rows': [], 'key_rows': []}
    return {'presets': presets, 'catalog': catalog, 'columns': columns, 'shape': shape, 'data': data, 'raw': raw,
            'sets': {1: 'default', 2: 'pop+', 20: 'fix_pathing_z'}, 'rule_map': {1: {'Character:MaxLevel': default}, 2: {'Character:ExpMultiplier': extra}},
            'default_id': 1, 'active_id': 1, 'active_row': None, 'own': None, 'revision': 'a' * 64, 'source_hash': 'b' * 64}


class EraPlanTests(unittest.TestCase):
    def test_all_startup_keys_and_all_zone_variants_are_managed(self):
        state = fixture_state()
        result = era.plan(state, 'velious')
        self.assertEqual(len(result['next_default_rules']), 47)
        self.assertEqual(len(result['zone_changes']), 4)
        self.assertEqual(result['zone_changes'][0]['before'], 0)
        self.assertEqual(result['zone_changes'][0]['after'], result['ruleset_id'])
        self.assertEqual(result['next_default_rules']['Character:MaxLevel']['notes'], None)
        original = result['ownership']['baseline']['default_rules']
        self.assertIsNone(original[era.CONTENT_RULE])
        self.assertEqual(original['Character:MaxLevel']['rule_value'], '65')

    def test_zone_composite_preserves_original_unrelated_rule_and_notes(self):
        result = era.plan(fixture_state(), 'luclin')
        target = result['ownership']['sets']['luclin']['composites']['2']
        rows = [r for r in result['new_rules'] if int(r['ruleset_id']) == target]
        kept = next(r for r in rows if r['rule_name'] == 'Character:ExpMultiplier')
        self.assertEqual((kept['rule_value'], kept['notes']), ('2.25', 'Keep me'))
        self.assertEqual(len(rows), 48)

    def test_main_preserves_original_active_nondefault_rules(self):
        state = fixture_state()
        state['active_id'] = 2
        state['active_row'] = {'id': '4', 'varname': 'RuleSet', 'value': 'pop+', 'information': 'custom', 'ts': '2005-01-01 00:00:00'}
        result = era.plan(state, 'pop')
        kept = next(r for r in result['new_rules'] if int(r['ruleset_id']) == result['ruleset_id'] and r['rule_name'] == 'Character:ExpMultiplier')
        self.assertEqual(kept['rule_value'], '2.25')

    def test_plan_token_is_stable_when_original_variable_is_absent(self):
        state = fixture_state()
        with patch.object(era.time, 'time', return_value=1):
            first = era.plan(state, 'pop')
        with patch.object(era.time, 'time', return_value=100):
            second = era.plan(state, 'pop')
        self.assertEqual(first['review_token'], second['review_token'])
        self.assertNotIn('next_default_rules', era.public_plan(first))

    def test_allocator_never_uses_unowned_reserved_ids_or_overflows(self):
        state = fixture_state()
        state['sets'] = {i: ('default' if i == 1 else 'set' + str(i)) for i in range(1, 255)}
        with self.assertRaisesRegex(ValueError, 'Not enough free'):
            era.plan(state, 'pop')
        state = fixture_state()
        state['sets'][9] = 'TRASC_Era_PoP'
        with self.assertRaisesRegex(ValueError, 'unowned'):
            era.plan(state, 'pop')

    def test_required_unsupported_rule_rejects_and_optional_omission_is_listed(self):
        state = fixture_state()
        del state['catalog']['Character:MaxLevel']
        with self.assertRaisesRegex(ValueError, 'required era rule'):
            era.plan(state, 'pop')
        state['presets']['presets']['pop']['rules']['Character:MaxLevel']['required'] = False
        result = era.plan(state, 'pop')
        self.assertEqual(result['omissions'][0]['rule'], 'Character:MaxLevel')

    def test_literal_never_depends_on_sql_backslash_escaping(self):
        text = "O'Brien\\x\n\x00"
        self.assertEqual(era.literal(text), "CONVERT(X'" + text.encode().hex() + "' USING utf8mb4)")
        self.assertEqual(era.decoded(['N', 'H' + text.encode().hex()], ['none', 'text']), {'none': None, 'text': text})

    def test_transaction_guards_precede_writes_and_commit_is_last(self):
        state = fixture_state()
        sql = era.transaction(state, era.plan(state, 'velious'))
        self.assertIn('SERIALIZABLE; START TRANSACTION;', sql)
        self.assertLess(sql.index('information_schema.TRIGGERS'), sql.index('INSERT INTO rule_sets'))
        self.assertLess(sql.index('information_schema.KEY_COLUMN_USAGE'), sql.index('INSERT INTO rule_sets'))
        self.assertTrue(sql.endswith('COMMIT;'))
        self.assertNotIn('ON DUPLICATE KEY UPDATE', sql)

    def test_profile_and_stopped_guards_fail_before_database_access(self):
        class Fake:
            profile = 'custom'
            config = {'database_imported': True}
            def server_running(self): return False
        with self.assertRaisesRegex(ValueError, 'Traditional'):
            era.require_stopped(Fake())
        Fake.profile = 'traditional'
        Fake.server_running = lambda self: True
        with self.assertRaisesRegex(ValueError, 'Stop the server'):
            era.require_stopped(Fake())

    def test_preset_caps_masks_and_xp_preservation(self):
        presets = era.manifest()
        for key, level, expansion, mask in (('velious', '60', '2', '3'), ('luclin', '60', '3', '7'), ('pop', '65', '4', '15')):
            rules = presets['presets'][key]['rules']
            self.assertEqual(rules['Character:MaxLevel']['value'], level)
            self.assertEqual(rules['Character:MaxExpLevel']['value'], level)
            self.assertEqual(rules[era.CONTENT_RULE]['value'], expansion)
            self.assertEqual(rules['World:ExpansionSettings']['value'], mask)
            self.assertEqual(rules['Character:KeepLevelOverMax']['value'], 'true')
            for name in ('Character:ExpMultiplier', 'Character:AAExpMultiplier', 'Character:UseOldRaceExpPenalties', 'Character:UseOldClassExpPenalties', 'Zone:StateSavingOnShutdown'):
                self.assertNotIn(name, rules)


if __name__ == '__main__':
    unittest.main()
