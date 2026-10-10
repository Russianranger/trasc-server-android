import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import modern_bot_bridge as bridge


class ModernBotBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def response(self, text):
        path = self.root / 'response.json'
        path.write_text(text)
        return bridge._json_output(path)

    def test_bootstrap_logs_do_not_corrupt_anchored_response(self):
        result = {'format': 1, 'ok': True, 'owner': {'id': 12}, 'bots': []}
        self.assertEqual(result, self.response('[Info] Booting\nTRASC_BOT_RESULT ' + json.dumps(result) + '\n'))
        self.assertEqual(result, self.response(json.dumps(result)))

    def test_multiple_frames_and_unframed_noise_fail(self):
        for data in ('TRASC_BOT_RESULT {"format":1}\nTRASC_BOT_RESULT {"format":1}',
                     '[Info] Booting\n{"format":1}', 'TRASC_BOT_RESULT []',
                     'TRASC_BOT_RESULT {"format":2}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.response(data)

    def test_unsupported_source_is_only_a_pristine_hash_mismatch(self):
        source = self.root / 'zone/main.cpp'
        source.parent.mkdir()
        source.write_text('unknown source')
        guards = {'custom': {'zone/main.cpp': 'a' * 64}}
        with patch.object(bridge, 'GUARDS', guards):
            with self.assertRaises(bridge.UnsupportedSource):
                bridge.prepare(self.root, 'custom')
            self.assertEqual('unknown source', source.read_text())
            self.assertFalse((self.root / 'zone/trasc-bot-bridge.json').exists())
            source.unlink()
            with self.assertRaises(ValueError) as caught:
                bridge.prepare(self.root, 'custom')
            self.assertNotIsInstance(caught.exception, bridge.UnsupportedSource)

    def test_symlink_source_cannot_fall_back_to_unsupported(self):
        target = self.root / 'outside'
        target.write_text('unknown source')
        (self.root / 'zone').mkdir()
        (self.root / 'zone/main.cpp').symlink_to(target)
        with patch.object(bridge, 'GUARDS', {'custom': {'zone/main.cpp': 'a' * 64}}):
            with self.assertRaises(ValueError) as caught:
                bridge.prepare(self.root, 'custom')
            self.assertNotIsInstance(caught.exception, bridge.UnsupportedSource)

    def test_forged_patched_marker_cannot_qualify_changed_source(self):
        (self.root / 'zone').mkdir()
        outputs = {name: b'forged' for name in (*bridge.PATCHED, 'zone/trasc_bot_bridge.h')}
        for name, data in outputs.items():
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
        marker = {'metadata': bridge.metadata('custom'),
                  'outputs': {name: hashlib.sha256(data).hexdigest() for name, data in outputs.items()}}
        (self.root / 'zone/trasc-bot-bridge.json').write_text(json.dumps(marker))
        with self.assertRaisesRegex(ValueError, 'receipt'):
            bridge.prepare(self.root, 'custom')

    def test_deployment_requires_actual_zone_bytes_and_current_recipe(self):
        zone = self.root / 'server/bin/zone'
        zone.parent.mkdir(parents=True)
        zone.write_bytes(b'actual zone')
        ctx = {'profile': 'traditional', 'deployment': {
            'bot_creation_bridge': bridge.metadata('traditional'), 'zone_sha256': bridge.digest(zone)}}
        engine = SimpleNamespace(work=self.root)
        self.assertEqual(zone, bridge._deployed(engine, ctx)[0])
        zone.write_bytes(b'replaced zone')
        with self.assertRaisesRegex(ValueError, 'binary changed'):
            bridge._deployed(engine, ctx)
        ctx['deployment']['bot_creation_bridge'] = {'format': 1}
        with self.assertRaisesRegex(ValueError, 'Rebuild'):
            bridge._deployed(engine, ctx)

    def test_optional_unqualified_custom_reports_reason(self):
        ctx = {'profile': 'custom', 'deployment': {
            'bot_creation_bridge_unavailable': 'Imported custom bot source has changed'}}
        result = bridge.capabilities(SimpleNamespace(work=self.root), ctx)
        self.assertFalse(result['offline_create'])
        self.assertEqual('Imported custom bot source has changed', result['reason'])

    def test_binary_symlinks_are_rejected(self):
        target = self.root / 'target'
        target.write_bytes(b'zone')
        path = self.root / 'zone'
        path.symlink_to(target)
        with self.assertRaises(ValueError):
            bridge.digest(path)

    @unittest.skipUnless(shutil.which('g++'), 'Native teardown regression requires g++')
    def test_offline_zone_teardown_does_not_reinitialize_quests(self):
        # Exercise the production transformation as C++, including the
        # unchanged default constructor argument for ordinary zone contexts.
        sources = {
            'zone/zone.h': 'class Zone { public:\n'
                'Zone(uint32 in_zoneid, uint32 in_instanceid, const char *in_short_name);\n'
                '~Zone();\nprivate: int default_ruleset = 0; uint32 zoneid = 0;\n};\n',
            'zone/zone.cpp': 'Zone::Zone(uint32 in_zoneid, uint32 in_instanceid, const char* in_short_name) {\n'
                '\tzoneid = in_zoneid;\n\tdatabase.QGlobalPurge();\n}\n'
                'Zone::~Zone() {\n\tentity_list.Clear();\n\tparse->ReloadQuests();\n}\n',
        }
        for name, data in sources.items():
            destination = self.root / name
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(data)
        guards = {name: hashlib.sha256(data.encode()).hexdigest() for name, data in sources.items()}
        with patch.object(bridge, 'GUARDS', {'custom': guards}), \
                patch.object(bridge, 'PATCHED', tuple(sources)), \
                patch.object(bridge, 'PATCHED_GUARDS', {'custom': {}}):
            outputs = bridge.output_files(self.root, 'custom')
        test = self.root / 'teardown.cpp'
        test.write_text('#include <cassert>\n#include <memory>\nusing uint32 = unsigned;\n'
                        'class Zone; Zone* zone = nullptr; int reloads = 0; int purges = 0;\n'
                        'struct Database { void QGlobalPurge() { ++purges; } } database;\n'
                        'struct Entities { void Clear() { assert(zone); } } entity_list;\n'
                        'struct Parser { void ReloadQuests() { assert(zone); ++reloads; } } parser;\n'
                        'Parser* parse = &parser;\n' + outputs['zone/zone.h'].decode()
                        + outputs['zone/zone.cpp'].decode() + '\nint main() {\n'
                        '  auto normal = std::make_unique<Zone>(1, 0, "qeynos");\n'
                        '  zone = normal.get(); normal.reset(); zone = nullptr;\n'
                        '  assert(reloads == 1 && purges == 1);\n'
                        '  auto offline = std::make_unique<Zone>(1, 0, "qeynos", true);\n'
                        '  zone = offline.get(); offline.reset(); zone = nullptr;\n'
                        '  assert(reloads == 1 && purges == 1);\n}\n')
        binary = self.root / 'teardown'
        subprocess.run(['g++', '-std=c++17', str(test), '-o', str(binary)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run([str(binary)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


if __name__ == '__main__':
    unittest.main()
