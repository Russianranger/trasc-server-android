import hashlib
import json
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
