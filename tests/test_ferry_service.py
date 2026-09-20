import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import server_ferry
import ferry_service as service
import ferry_route


class ServerFerryTests(unittest.TestCase):
    def test_patch_preserves_original_conversion_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'zone').mkdir()
            source=root/'zone/client_packet.cpp';waypoints=root/'zone/waypoints.cpp'
            original=server_ferry.INCLUDE+'void handler() {\n'+server_ferry.ANCHOR+'\tOriginalVehicleConversion();\n}\n'
            source.write_text(original);waypoints.write_text(server_ferry.Z_ANCHOR+'\n')
            result=server_ferry.prepare(root)
            self.assertEqual(result['original'],hashlib.sha256(original.encode()).hexdigest())
            self.assertIn('OriginalVehicleConversion();',source.read_text())
            self.assertIn('trasc_ferry_managed',waypoints.read_text())
            self.assertEqual(server_ferry.prepare(root),result)
            source.write_text(source.read_text()+'// intervening edit\n')
            with self.assertRaisesRegex(ValueError,'source changed'):server_ferry.prepare(root)

    def test_unknown_source_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'zone').mkdir()
            (root/'zone/client_packet.cpp').write_text('unsupported')
            (root/'zone/waypoints.cpp').write_text(server_ferry.Z_ANCHOR)
            with self.assertRaisesRegex(ValueError,'unsupported'):server_ferry.prepare(root)
            self.assertEqual(list((root/'zone').iterdir()).__len__(),2)

    def test_route_is_limited_and_preserves_waterline(self):
        phases=ferry_route.phases()
        self.assertEqual([p['zone'] for p in phases],[1,98,24,98])
        for phase in phases:
            self.assertEqual({p['z'] for p in phase['points']},{ferry_route.DOCKS[phase['zone']][2]})
        self.assertEqual(ferry_route.DOCKS[98][2],-39.5)
        self.assertEqual(service.initial_state('a'*24)['point'],8)

    def test_writes_require_stopped_server_before_backup(self):
        e=Mock();e.server_running.return_value=True
        with self.assertRaisesRegex(ValueError,'Stop the server'):service.apply(e,{'token':'a'*48})
        e.backup_database.assert_not_called();e.mysql.assert_not_called()

    def test_failed_file_half_rolls_back_without_touching_other_quests(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            e=Mock();e.work=Path(temp);(e.work/'run').mkdir()
            p=e.work/'server/quests/lua_modules/trasc_ferry.lua';p.parent.mkdir(parents=True)
            p.write_text('original');other=p.with_name('player.lua');other.write_text('keep')
            name=str(p.relative_to(e.work));before={name:service.digest(p)}
            service.change_files(e,'a'*48,before,{name:'replacement'})
            with patch.object(service.trial,'tables',return_value=set()):service.recover(e)
            self.assertEqual(p.read_text(),'original');self.assertEqual(other.read_text(),'keep')
            self.assertFalse((e.work/'run/ferry-change.json').exists())

if __name__=='__main__':unittest.main()
