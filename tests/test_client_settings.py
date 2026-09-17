import hashlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import client_settings

class ClientSettingsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.engine=types.SimpleNamespace(work=Path(self.temp.name))
        self.path=self.engine.work/'client/current/EQCLIENT.INI';self.path.parent.mkdir(parents=True)
        self.raw=b'\xef\xbb\xbf; caf\xe9\r\n[Defaults]\r\nUseLuclinHumanMale=TRUE\r\nWindowedMode=FALSE\r\n[Options]\r\nMaxFPS=100\r\n[KeyMaps]\r\nKEYMAPPING_HAIL_2=200\r\n'
        self.path.write_bytes(self.raw)
    def save(self, changes):
        return client_settings.save(self.engine,{'revision':client_settings.inspect(self.engine)['revision'],'changes':changes})
    def test_models_and_existing_settings_preserve_unrelated_bytes(self):
        r=self.save([{'section':'Defaults','key':'UseLuclinHumanMale','value':'FALSE'}, {'section':'Defaults','key':'AllLuclinPcModelsOff','value':'TRUE'}, {'section':'Options','key':'MaxFPS','value':'60'}])
        out=self.path.read_bytes()
        self.assertTrue(out.startswith(b'\xef\xbb\xbf; caf\xe9\r\n'))
        self.assertIn(b'[Defaults]\r\nAllLuclinPcModelsOff=TRUE\r\n',out)
        self.assertIn(b'UseLuclinHumanMale=FALSE\r\n',out)
        self.assertIn(b'MaxFPS=60\r\n[KeyMaps]\r\nKEYMAPPING_HAIL_2=200\r\n',out)
        self.assertEqual((self.engine.work/'backups/client-settings/eqclient.previous.ini').read_bytes(),self.raw)
        self.assertNotEqual(r['revision'],hashlib.sha256(self.raw).hexdigest())
    def test_stale_snapshot_and_validation_leave_original(self):
        with self.assertRaises(ValueError):client_settings.save(self.engine,{'revision':'stale','changes':[]})
        for change in [dict(section='Defaults',key='WindowedMode',value='TRUE'),dict(section='Options',key='Unknown',value='1'),dict(section='Options',key='MaxFPS',value='60\nInjected=1'),dict(section='Defaults',key='UseLuclinHumanMale',value='maybe')]:
            with self.assertRaises(ValueError):self.save([change])
            self.assertEqual(self.path.read_bytes(),self.raw)
    def test_original_backup_survives_later_edits(self):
        self.save([dict(section='Options',key='MaxFPS',value='60')]);first=self.path.read_bytes()
        self.save([dict(section='Options',key='MaxFPS',value='30')])
        self.assertEqual((self.engine.work/'backups/client-settings/eqclient.original.ini').read_bytes(),self.raw)
        self.assertEqual((self.engine.work/'backups/client-settings/eqclient.previous.ini').read_bytes(),first)
    def test_rejects_ambiguous_and_linked_files(self):
        self.path.with_name('eqclient.ini').write_bytes(self.raw)
        with self.assertRaises(ValueError):client_settings.inspect(self.engine)
        self.path.with_name('eqclient.ini').unlink();self.path.unlink();self.path.symlink_to(self.engine.work/'outside.ini')
        with self.assertRaises(ValueError):client_settings.inspect(self.engine)
    def test_duplicates_rejected_and_noop_byte_exact(self):
        self.save([]);self.assertEqual(self.path.read_bytes(),self.raw)
        self.path.write_bytes(self.raw+b'[Options]\r\nMaxFPS=70\r\n')
        with self.assertRaises(ValueError):client_settings.inspect(self.engine)
