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

    def test_source_line_endings_and_original_bytes_are_preserved(self):
        for source_eol, waypoint_eol in (('\n','\n'), ('\r\n','\n'), ('\n','\r\n'), ('\r\n','\r\n')):
            with self.subTest(source_eol=source_eol, waypoint_eol=waypoint_eol), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'zone').mkdir()
                source=root/'zone/client_packet.cpp';waypoints=root/'zone/waypoints.cpp'
                before=(server_ferry.INCLUDE+'void handler() {\n'+server_ferry.ANCHOR+
                        '\tOriginalVehicleConversion();\n}\n').replace('\n',source_eol).encode()
                before_waypoints=('void waypoint() {\n'+server_ferry.Z_ANCHOR+'\n}\n').replace('\n',waypoint_eol).encode()
                source.write_bytes(before);waypoints.write_bytes(before_waypoints)
                result=server_ferry.prepare(root)
                self.assertEqual(source.with_name(source.name+'.trasc-ferry-original').read_bytes(),before)
                self.assertEqual(waypoints.with_name(waypoints.name+'.trasc-ferry-original').read_bytes(),before_waypoints)
                # Removing only the two additions must recover every original source byte.
                patched=source.read_bytes()
                restored=patched.replace(server_ferry.ADDED_INCLUDE.replace('\n',source_eol).encode(),b'',1)
                restored=restored.replace(server_ferry.CALL.replace('\n',source_eol).encode(),b'',1)
                self.assertEqual(restored,before)
                self.assertLess(patched.index(b'TrascFerry::RecordPassenger'),patched.index(b'OriginalVehicleConversion'))
                restored_waypoints=waypoints.read_bytes().replace(server_ferry.Z_FIXED.replace('\n',waypoint_eol).encode(),server_ferry.Z_ANCHOR.encode(),1)
                self.assertEqual(restored_waypoints,before_waypoints)
                self.assertEqual(server_ferry.prepare(root),result)

    def test_mixed_endings_are_preserved_per_anchor(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'zone').mkdir()
            source=root/'zone/client_packet.cpp';waypoints=root/'zone/waypoints.cpp'
            before=(server_ferry.INCLUDE.replace('\n','\r\n')+'void handler() {\n'+
                    server_ferry.ANCHOR+'\tOriginalVehicleConversion();\r\n}\n').encode()
            source.write_bytes(before);waypoints.write_bytes(server_ferry.Z_ANCHOR.encode())
            server_ferry.prepare(root)
            restored=source.read_bytes().replace(server_ferry.ADDED_INCLUDE.replace('\n','\r\n').encode(),b'',1)
            restored=restored.replace(server_ferry.CALL.encode(),b'',1)
            self.assertEqual(restored,before)
            self.assertEqual(waypoints.read_bytes(),server_ferry.Z_FIXED.encode())

    def test_unknown_or_duplicate_lines_leave_source_untouched(self):
        valid=server_ferry.INCLUDE+'void handler() {\n'+server_ferry.ANCHOR+'}\n'
        variants=(valid+server_ferry.INCLUDE.replace('\n','\r\n'),
                  valid+server_ferry.ANCHOR.replace('\n','\r\n'),
                  valid.replace('vehicle_id != 0','vehicle_id > 1'),
                  valid.replace(server_ferry.ANCHOR,'// '+server_ferry.ANCHOR))
        cases=[(code,server_ferry.Z_ANCHOR) for code in variants]
        cases.extend(((valid,server_ferry.Z_ANCHOR+'\r\n'+server_ferry.Z_ANCHOR),
                      (valid,server_ferry.Z_ANCHOR+' // changed')))
        for code,waypoint_code in cases:
            with self.subTest(code=code,waypoint_code=waypoint_code), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'zone').mkdir()
                source=root/'zone/client_packet.cpp';waypoints=root/'zone/waypoints.cpp'
                source.write_bytes(code.encode());waypoints.write_bytes(waypoint_code.encode())
                before={p.name:p.read_bytes() for p in (root/'zone').iterdir()}
                with self.assertRaisesRegex(ValueError,'unsupported'):server_ferry.prepare(root)
                self.assertEqual({p.name:p.read_bytes() for p in (root/'zone').iterdir()},before)

    def test_partial_include_is_rejected_for_all_line_endings(self):
        for ending in ('\n','\r\n',''):
            with self.subTest(ending=ending), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'zone').mkdir()
                code=server_ferry.INCLUDE+server_ferry.ANCHOR+server_ferry.ADDED_INCLUDE.rstrip('\n')+ending
                (root/'zone/client_packet.cpp').write_bytes(code.encode())
                (root/'zone/waypoints.cpp').write_bytes(server_ferry.Z_ANCHOR.encode())
                before={p.name:p.read_bytes() for p in (root/'zone').iterdir()}
                with self.assertRaisesRegex(ValueError,'interrupted'):server_ferry.prepare(root)
                self.assertEqual({p.name:p.read_bytes() for p in (root/'zone').iterdir()},before)

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
