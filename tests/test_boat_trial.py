"""Scope and fail-closed boundaries for the managed ferry trial."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
import boat_trial as boats


class BoatTrialTests(unittest.TestCase):
    def test_route_uses_confirmed_model_and_fixed_height(self):
        spec = boats.content(dict(npc=100, group=200, spawn=300, grid=400))
        npc = spec['npc_types'][0]
        self.assertEqual((npc['race'], npc['gender'], npc['bodytype'], npc['size'], npc['flymode']), (72, 0, 1, 0, 0))
        self.assertEqual(spec['spawn2'][0]['z'], -39.5)
        self.assertEqual({r['z'] for r in spec['grid_entries']}, {-39.5})
        self.assertEqual([r['pause'] for r in spec['grid_entries']], [90, 15])
        self.assertEqual((spec['grid'][0]['type'], spec['grid'][0]['type2']), (0, 1))
        self.assertEqual(nc := npc['name'], boats.NAME)
        self.assertFalse(any(c.isdigit() for c in nc))
        self.assertFalse(set(spec) & {'account', 'character_data', 'rule_values', 'command_settings', 'spawn2_disabled'})

    def test_requires_stopped_server_before_token_or_backup(self):
        e = Mock(); e.server_running.return_value = True
        with self.assertRaisesRegex(ValueError, 'Stop the server'):
            boats.apply(e, {'token': 'a'*48})
        e.backup_database.assert_not_called(); e.mysql.assert_not_called()

    def test_invalid_or_missing_preview_cannot_mutate(self):
        with tempfile.TemporaryDirectory() as temp:
            e = Mock(); e.work = Path(temp); e.config = {'database_imported': True}
            e.server_running.return_value = False
            for token in ('../outside', '', 5, 'a'*48):
                with self.assertRaises(ValueError): boats.apply(e, {'token': token})
            e.backup_database.assert_not_called(); e.mysql.assert_not_called()


if __name__ == '__main__': unittest.main()
