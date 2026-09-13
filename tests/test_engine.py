import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from engine import Engine, extract_archive, safe_path, github_parts, validate_rule

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def archive(self, entries):
        p=self.root/'input.zip'
        with zipfile.ZipFile(p,'w') as z:
            for name,data in entries:z.writestr(name,data)
        return p
    def test_zip_traversal_never_writes_outside(self):
        p=self.archive([('../outside','bad')])
        with self.assertRaises(ValueError):extract_archive(p,self.root/'out')
        self.assertFalse((self.root/'outside').exists())
    def test_symlink_zip_rejected(self):
        p=self.root/'input.zip'
        with zipfile.ZipFile(p,'w') as z:
            info=zipfile.ZipInfo('escape');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(info,'../../outside')
        with self.assertRaises(ValueError):extract_archive(p,self.root/'out')
    def test_expansion_limit(self):
        p=self.archive([('large','a'*100)])
        with self.assertRaises(ValueError):extract_archive(p,self.root/'out',limit=50)
    def test_symlink_path_escape(self):
        (self.root/'out').mkdir();(self.root/'out/link').symlink_to(self.root)
        with self.assertRaises(ValueError):safe_path(self.root/'out','link/escape')
    def test_valid_tar(self):
        p=self.root/'input.tar.gz'
        with tarfile.open(p,'w:gz') as t:
            info=tarfile.TarInfo('maps/base/nektulos.map');info.size=3;t.addfile(info,io.BytesIO(b'map'))
        extract_archive(p,self.root/'out')
        self.assertEqual((self.root/'out/maps/base/nektulos.map').read_bytes(),b'map')
    def test_tar_link_rejected(self):
        p=self.root/'input.tar'
        with tarfile.open(p,'w') as t:
            info=tarfile.TarInfo('escape');info.type=tarfile.SYMTYPE;info.linkname='/etc';t.addfile(info)
        with self.assertRaises(ValueError):extract_archive(p,self.root/'out')

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.engine=Engine(self.root)
    def tearDown(self):self.tmp.cleanup()
    def zipped(self,name,entries):
        p=self.root/'incoming'/name
        with zipfile.ZipFile(p,'w') as z:
            for path,data in entries:z.writestr(path,data)
        return p
    def test_maps_wrapper_and_replacement_backup(self):
        self.zipped('maps.zip',[('maps/base/nektulos.map','old')])
        self.engine.import_maps({'file':'maps.zip'})
        self.zipped('maps2.zip',[('repo-main/maps/base/nektulos.map','new')])
        self.engine.import_maps({'file':'maps2.zip'})
        self.assertEqual((self.root/'maps/base/nektulos.map').read_text(),'new')
        self.assertEqual((self.root/'backups/maps-before-import/base/nektulos.map').read_text(),'old')
    def test_nested_seed_discovery_and_source_updates_preserve_runtime(self):
        inner=io.BytesIO()
        with zipfile.ZipFile(inner,'w') as z:z.writestr('release-peq.sql','CREATE TABLE example (id int);')
        entries=[('fork-main/Release-NMS-Server/CMakeLists.txt','project(test)'),('fork-main/Release-NMS-Server/database/release-peq.zip',inner.getvalue())]
        self.zipped('source.zip',entries)
        self.engine.import_source({'file':'source.zip'})
        self.assertTrue(any('release-peq.zip!release-peq.sql' in c['id'] for c in self.engine.database_candidates()))
        (self.root/'server/local-change.txt').write_text('keep')
        self.engine.import_source({'file':'source.zip'})
        self.assertTrue((self.root/'sources/previous/trasc-source.json').is_file())
        self.assertEqual((self.root/'server/local-change.txt').read_text(),'keep')
    def test_invalid_source_does_not_replace_current(self):
        (self.root/'sources/current').mkdir();(self.root/'sources/current/keep').write_text('yes')
        self.zipped('invalid.zip',[('readme.txt','not source')])
        with self.assertRaises(ValueError):self.engine.import_source({'file':'invalid.zip'})
        self.assertEqual((self.root/'sources/current/keep').read_text(),'yes')
    def test_network_config_keeps_database_local(self):
        self.engine.network({'ip':'192.168.1.34'})
        cfg=json.loads((self.root/'server/eqemu_config.json').read_text())['server']
        self.assertEqual(cfg['world']['address'],'192.168.1.34')
        self.assertEqual(cfg['database']['host'],'127.0.0.1')
        self.assertEqual(cfg['database']['port'],13306)
        self.assertNotIn('db_password',self.engine.state()['settings'])
        self.assertNotIn('root_password',self.engine.state()['settings'])
    def test_move_cannot_overwrite_or_escape(self):
        (self.root/'maps/a').write_text('a');(self.root/'maps/b').write_text('b')
        with self.assertRaises(ValueError):self.engine.edit_file({'path':'maps/a','destination':'maps/b'})
        with self.assertRaises(ValueError):self.engine.edit_file({'path':'maps/a','destination':'../escape'})
        self.engine.edit_file({'action':'move','path':'maps/a','destination':'backups/a'})
        self.assertEqual((self.root/'backups/a').read_text(),'a')
    def test_large_stderr_does_not_deadlock_dump(self):
        self.engine.run([sys.executable,'-c',"import sys;sys.stderr.write('x'*1000000);print('dump')"],output_file=self.root/'backups/test.sql',timeout=10)
        self.assertEqual((self.root/'backups/test.sql').read_text(),'dump\n')
    def test_arbitrary_writes_require_server_stopped(self):
        with patch.object(self.engine,'ensure_db'),patch.object(self.engine,'server_running',return_value=True),patch.object(self.engine,'mysql') as mysql:
            with self.assertRaises(ValueError):self.engine.sql({'query':'DELETE FROM account','write':True})
            mysql.assert_not_called()
    def test_read_sql_uses_database_read_only_transaction(self):
        with patch.object(self.engine,'ensure_db'),patch.object(self.engine,'mysql',return_value='ok') as mysql:
            self.engine.sql({'query':'SELECT 1;'})
            self.assertTrue(mysql.call_args.args[0].startswith('START TRANSACTION READ ONLY;'))
            with self.assertRaises(ValueError):self.engine.sql({'query':'SELECT 1; DELETE FROM account;'})
    def test_cancellation_stops_subprocess(self):
        self.engine.cancel.set()
        with self.assertRaisesRegex(ValueError,'cancelled'):self.engine.run([sys.executable,'-c','raise Exception("should not run")'])

class InputTests(unittest.TestCase):
    def test_github_url(self):
        self.assertEqual(github_parts('https://github.com/Russianranger/Triptych-Triumvirate/tree/main'),('Russianranger','Triptych-Triumvirate','main'))
        with self.assertRaises(ValueError):github_parts('https://github.com.evil.test/owner/repo')
        with self.assertRaises(ValueError):github_parts('http://github.com/owner/repo')
    def test_rules_preserve_tiny_multiplier(self):
        self.assertEqual(float(validate_rule('Character:FinalRaidExpMultiplier','0.0000000000001')),1e-13)
        self.assertEqual(validate_rule('Zone:StateSavingOnShutdown',False),'false')
        for value in ('nan','inf','-1','1.01'):
            with self.assertRaises(ValueError):validate_rule('Character:RaidExpMultiplier',value)

if __name__=='__main__':unittest.main()
