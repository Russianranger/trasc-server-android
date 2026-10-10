"""Bot ownership/preview boundaries and real TAKP migration transactions.

ERARULES_MARIADB=1 uses the existing isolated MariaDB harness. The fixture
contains the exact eleven qualified TAKP migrations, including real shared
player/bot name triggers; no installed world or client is used.
"""
import copy
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import bots
import test_era_rules_mariadb as era_fixture


class BotBoundaryTests(unittest.TestCase):
    def ctx(self,profile='takp',camel=False):
        return {'profile':profile,'rules':{'Bots:AllowCamelCaseNames':str(camel).lower()},'combinations':[(1,1),(1,2),(128,7)]}

    def test_names_combinations_and_gender_are_validated(self):
        ctx=self.ctx()
        draft={'name':'aLeXiS','race':1,'class':2,'gender':1}
        self.assertEqual(bots.normalize_drafts(ctx,[draft]),[dict(draft,name='Alexis')])
        self.assertEqual(bots.normalize_drafts(self.ctx('custom',True),[draft])[0]['name'],'ALeXiS')
        for change in ({'name':'x'},{'name':'Zoëbot'},{'name':'Abbbot'},{'name':'Zelda;DROP'},{'race':128,'class':2},{'gender':2},{'gender':True},{'race':'1'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                bots.normalize_drafts(ctx,[dict(draft,**change)])
        with self.assertRaisesRegex(ValueError,'unique'): bots.normalize_drafts(ctx,[draft,dict(draft,name='alexis')])

    def test_request_tokens_and_ids_do_not_accept_fragments(self):
        self.assertEqual(bots.request_id({'request_id':'creation-request-123'}),'creation-request-123')
        for token in ('', '../x'*8, 'a'*65, "z'*16"):
            with self.assertRaises(ValueError): bots.request_id({'request_id':token})
        for value in (True,'1',-1,0,4294967296):
            with self.assertRaises(ValueError): bots.positive(value)

    def test_modern_deleted_characters_are_excluded(self):
        ctx={'profile':'custom','shape':{'column_names':{'character_data':['id','deleted_at']}}}
        self.assertIn('c.deleted_at IS NULL',bots._owner_query(ctx,'c.id=3'))
        ctx={'profile':'takp','shape':{'column_names':{'character_data':['id','is_deleted']}}}
        self.assertIn('c.is_deleted=0',bots._owner_query(ctx,'c.id=3'))

    def test_all_write_routes_require_identity_before_database(self):
        class Engine:
            profile='takp'
            def ensure_db(self): raise AssertionError('Database must not be reached')
        for operation in ('bots_generate','bots_preview','bots_roster','bots_socials_install','bots_socials_restore'):
            with self.subTest(operation=operation),self.assertRaisesRegex(ValueError,'Refresh Bots'):
                bots.dispatch(Engine(),operation,{})

    def test_running_server_is_rejected_before_database(self):
        class Engine:
            def server_running(self): return True
        with self.assertRaisesRegex(ValueError,'Stop the server'): bots.require_stopped(Engine())

    def test_native_deploys_all_bot_modules_and_serializes_mutations(self):
        root=Path(__file__).resolve().parents[1]
        code=(root/'app/src/main/java/io/github/russianranger/trasc/RuntimeManager.java').read_text()
        for name in ('bots.py','bot_socials.py','modern_bot_bridge.py','modern_bot_bridge.h'): self.assertIn('"'+name+'"',code)
        code=(root/'app/src/main/java/io/github/russianranger/trasc/ClientRuntime.java').read_text()
        for operation in ('bots_generate','bots_socials_install','bots_socials_restore'): self.assertIn('"'+operation+'"',code)


class BotFixtureEngine(era_fixture.FixtureEngine):
    profile='takp'
    def __init__(self,case):
        super().__init__(case)
        self.config['bot_database_epoch']='a'*32
    def log(self,message): pass


class BotBuildCompatibilityTests(unittest.TestCase):
    def setUp(self):
        import engine
        self.module=engine
        self.tmp=tempfile.TemporaryDirectory()
        self.work=Path(self.tmp.name)
        self.source=self.work/'sources/current'
        for name in ('libs/luabind/CMakeLists.txt','submodules/fmt/CMakeLists.txt','submodules/libuv/CMakeLists.txt'):
            path=self.source/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('fixture')
        (self.source/'zone').mkdir()
        (self.source/'trasc-source.json').write_text(json.dumps({'repo':'Custom fork','ref':'other-pristine-revision'}))
        build=self.work/'builds/current'; build.mkdir(parents=True)
        header=bytearray(20); header[:4]=b'\x7fELF'; header[4]=2; header[18:20]=(183).to_bytes(2,'little')
        for name in engine.BINARIES: (build/name).write_bytes(header)
        (self.work/'server').mkdir()
        class Harness:
            profile='custom'
            def __init__(inner): inner.work=self.work; inner.config={'jobs':1}; inner.commands=[]
            def source_root(inner): return self.source
            def save(inner): pass
            def log(inner,message): pass
            def run(inner,command,**kwargs): inner.commands.append(command)
        self.engine=Harness()
    def tearDown(self): self.tmp.cleanup()

    def test_pristine_unqualified_custom_source_still_builds_without_bot_bridge(self):
        import modern_bot_bridge
        with patch.object(self.module.server_ferry,'prepare',return_value={'feature':'existing-ferry'}),patch.object(modern_bot_bridge,'prepare',side_effect=modern_bot_bridge.UnsupportedSource('Custom revision does not match the reviewed offline creation inputs')):
            result=self.module.Engine.build(self.engine,{})
        self.assertTrue(result['staged'])
        self.assertEqual(len(self.engine.commands),2)
        receipt=json.loads((self.work/'server/bin.staged/build-info.json').read_text())
        self.assertIsNone(receipt['bot_creation_bridge'])
        self.assertIn('Custom revision',receipt['bot_creation_bridge_unavailable'])
        self.assertIn('unavailable',result['message'])

    def test_tampered_already_patched_source_never_falls_back_to_plain_build(self):
        import modern_bot_bridge
        marker=self.source/'zone/trasc-bot-bridge.json'; marker.write_text('existing-patch')
        with patch.object(self.module.server_ferry,'prepare',return_value={'feature':'existing-ferry'}),patch.object(modern_bot_bridge,'prepare',side_effect=modern_bot_bridge.UnsupportedSource('Changed patch receipt')):
            with self.assertRaises(modern_bot_bridge.UnsupportedSource): self.module.Engine.build(self.engine,{})
        self.assertEqual(self.engine.commands,[])
        with patch.object(self.module.server_ferry,'prepare',return_value={'feature':'existing-ferry'}),patch.object(modern_bot_bridge,'prepare',side_effect=ValueError('Patched source changed')):
            with self.assertRaisesRegex(ValueError,'Patched source changed'): self.module.Engine.build(self.engine,{})
        self.assertEqual(self.engine.commands,[])


@unittest.skipUnless(os.environ.get('ERARULES_MARIADB')=='1','Set ERARULES_MARIADB=1 to run the isolated real database fixture')
class BotsMariaDBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): era_fixture.EraMariaDBTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls): era_fixture.EraMariaDBTests.tearDownClass.__func__(cls)

    def setUp(self):
        self.work=self.root/self._testMethodName
        for name in ('run','backups','logs','server/bin'): (self.work/name).mkdir(parents=True)
        self.engine=BotFixtureEngine(self)
        self.engine.mysql('DROP DATABASE IF EXISTS peq; CREATE DATABASE peq CHARACTER SET utf8mb4;',database=False)
        self.engine.mysql("""
        CREATE TABLE account(id INT PRIMARY KEY,name VARCHAR(30) NOT NULL) ENGINE=MyISAM;
        CREATE TABLE character_data(id INT UNSIGNED PRIMARY KEY,account_id INT NOT NULL,name VARCHAR(64) NOT NULL UNIQUE,level INT UNSIGNED NOT NULL,is_deleted TINYINT NOT NULL DEFAULT 0) ENGINE=InnoDB;
        CREATE TABLE character_inventory(id INT UNSIGNED NOT NULL,slotid INT NOT NULL,itemid INT UNSIGNED NOT NULL,charges INT NOT NULL,custom_data TEXT,PRIMARY KEY(id,slotid)) ENGINE=InnoDB;
        CREATE TABLE char_create_combinations(race INT UNSIGNED NOT NULL,`class` INT UNSIGNED NOT NULL,PRIMARY KEY(race,`class`)) ENGINE=InnoDB;
        CREATE TABLE name_filter(name VARCHAR(64) NOT NULL) ENGINE=InnoDB;
        CREATE TABLE rule_sets(ruleset_id INT PRIMARY KEY,name VARCHAR(64)) ENGINE=InnoDB;
        CREATE TABLE rule_values(ruleset_id INT,rule_name VARCHAR(64),rule_value TEXT,PRIMARY KEY(ruleset_id,rule_name)) ENGINE=InnoDB;
        CREATE TABLE variables(varname VARCHAR(64),value TEXT) ENGINE=InnoDB;
        INSERT INTO account VALUES(7,'Thor'),(8,'Other');
        INSERT INTO character_data VALUES(101,7,'Izadar',22,0),(102,8,'Otherchar',12,0),(103,7,'Deleted',22,1);
        INSERT INTO char_create_combinations VALUES(1,1),(1,2),(128,7);
        INSERT INTO name_filter VALUES('forbidden');
        INSERT INTO rule_sets VALUES(1,'default');
        INSERT INTO rule_values VALUES(1,'Character:GroupInvitesRequireTarget','true');
        """)
        self.engine.mysql((Path(__file__).parent/'fixtures/takp_bot_manager.sql').read_text())
        (self.work/'server/bin/build-info.json').write_text(json.dumps({'format':1,'profile':'takp','recipe':'isolated-fixture','revision':'25bf70a'}))
        self.qualifier=patch.object(bots,'_creation',return_value={'available':True,'reason':''})
        self.qualifier.start()
        self.ctx=bots.context(self.engine)
        self.args={'identity':self.ctx['identity'],'owner_id':101,'request_id':'creation-request-123','drafts':[{'name':'Healer','race':1,'class':2,'gender':1},{'name':'Warrior','race':1,'class':1,'gender':0}]}

    def tearDown(self): self.qualifier.stop()
    def values(self,sql): return [line.split('\t') for line in self.engine.mysql(sql).splitlines()[1:]]
    def generate(self):
        result=bots.preview(self.engine,self.args)
        self.args['preview_hash']=result['preview_hash']
        return bots.generate(self.engine,self.args)

    def test_real_migrations_roster_creation_defaults_and_idempotency(self):
        before=self.values('SELECT COUNT(*) FROM takp_bot_runtime;')
        result=self.generate()
        self.assertEqual(result['owner']['id'],101)
        self.assertEqual([b['name'] for b in result['bots']],['Healer','Warrior'])
        self.assertEqual(self.values('SELECT owner_character_id,name FROM takp_bot_data ORDER BY id;'),[['101','Healer'],['101','Warrior']])
        self.assertEqual(self.values('SELECT COUNT(*) FROM takp_bot_runtime;'),before)
        self.assertEqual(self.values("SELECT COUNT(*) FROM takp_bot_name_registry WHERE kind='bot';"),[['2']])
        again=bots.generate(self.engine,self.args)
        self.assertTrue(again['idempotent'])
        self.assertEqual(again['bots'],result['bots'])
        self.assertEqual(self.values('SELECT COUNT(*) FROM takp_bot_data;'),[['2']])
        status=bots.status(self.engine,{})
        self.assertTrue(status['available'])
        self.assertEqual(status['identity'],self.ctx['identity'])

    def test_character_search_deleted_owners_names_and_combinations(self):
        result=bots.characters(self.engine,{'identity':self.ctx['identity'],'query':'thor'})
        self.assertEqual([c['id'] for c in result['characters']],[101])
        with self.assertRaisesRegex(ValueError,'active character'): bots.owner(self.ctx,103)
        for name in ('Deleted','Izadar','Forbiddenhero'):
            args=dict(self.args,drafts=[dict(self.args['drafts'][0],name=name)])
            with self.subTest(name=name),self.assertRaises(ValueError): bots.preview(self.engine,args)
        with self.assertRaisesRegex(ValueError,'combination'):
            bots.preview(self.engine,dict(self.args,drafts=[dict(self.args['drafts'][0],race=128)]))
        self.assertEqual(self.values('SELECT COUNT(*) FROM takp_bot_data;'),[['0']])

    def test_late_collision_rolls_back_first_insert_and_name_trigger(self):
        review=bots.preview(self.engine,self.args)
        value=json.loads(bots._preview_path(self.engine,self.args['request_id']).read_text())
        bots.ensure_receipts(self.engine)
        sql=bots.takp_transaction(self.ctx,value)
        self.engine.mysql("INSERT INTO character_data VALUES(104,8,'Warrior',15,0);")
        with self.assertRaises(ValueError): self.engine.mysql(sql)
        self.assertEqual(self.values('SELECT COUNT(*) FROM takp_bot_data;'),[['0']])
        self.assertEqual(self.values("SELECT COUNT(*) FROM takp_bot_name_registry WHERE kind='bot';"),[['0']])
        self.assertEqual(self.values('SELECT COUNT(*) FROM '+bots.RECEIPTS+';'),[['0']])
        self.assertTrue(review['preview_hash'])

    def test_missing_database_incarnation_is_a_transaction_failure(self):
        bots.preview(self.engine,self.args)
        value=json.loads(bots._preview_path(self.engine,self.args['request_id']).read_text())
        bots.ensure_receipts(self.engine)
        sql=bots.takp_transaction(self.ctx,value)
        self.engine.mysql('DELETE FROM '+bots.INSTANCE+';')
        with self.assertRaises(ValueError): self.engine.mysql(sql)
        self.assertEqual(self.values('SELECT COUNT(*) FROM takp_bot_data;'),[['0']])
        self.assertEqual(self.values('SELECT COUNT(*) FROM '+bots.RECEIPTS+';'),[['0']])

    def test_lost_response_recovers_committed_receipt(self):
        review=bots.preview(self.engine,self.args); self.args['preview_hash']=review['preview_hash']
        real=self.engine.mysql
        def lost(sql,**kwargs):
            output=real(sql,**kwargs)
            if sql.startswith('SET SESSION sql_mode='): raise ValueError('Connection lost after COMMIT')
            return output
        with patch.object(self.engine,'mysql',side_effect=lost): result=bots.generate(self.engine,self.args)
        self.assertTrue(result['idempotent'])
        self.assertEqual(self.values('SELECT COUNT(*) FROM takp_bot_data;'),[['2']])

    def test_owner_rules_schema_and_restore_epoch_invalidate_preview(self):
        review=bots.preview(self.engine,self.args); self.args['preview_hash']=review['preview_hash']
        self.engine.mysql('UPDATE character_data SET account_id=8 WHERE id=101;')
        with self.assertRaisesRegex(ValueError,'character/draft changed'): bots.generate(self.engine,self.args)
        self.engine.mysql('UPDATE character_data SET account_id=7 WHERE id=101;')
        self.engine.mysql("UPDATE rule_values SET rule_value='false' WHERE rule_name='Character:GroupInvitesRequireTarget';")
        with self.assertRaisesRegex(ValueError,'changed since preview'): bots.generate(self.engine,self.args)
        self.engine.mysql("UPDATE rule_values SET rule_value='true' WHERE rule_name='Character:GroupInvitesRequireTarget';")
        self.engine.config['bot_database_epoch']='b'*32
        with self.assertRaisesRegex(ValueError,'database or server deployment changed'): bots.generate(self.engine,self.args)
        self.assertEqual(self.values('SELECT COUNT(*) FROM takp_bot_data;'),[['0']])

    def test_receipt_owner_mismatch_removed_bot_and_old_restore_never_recreate(self):
        result=self.generate()
        with self.assertRaisesRegex(ValueError,'another owner'):
            bots.generate(self.engine,dict(self.args,owner_id=102))
        self.engine.mysql('DELETE FROM takp_bot_data WHERE id='+str(result['bots'][0]['id'])+';')
        with self.assertRaisesRegex(ValueError,'changed or was removed'): bots.generate(self.engine,self.args)
        self.engine.mysql('DELETE FROM '+bots.RECEIPTS+'; DELETE FROM takp_bot_data;')
        with self.assertRaisesRegex(ValueError,'receipt is missing'): bots.generate(self.engine,self.args)
        self.assertEqual(self.values('SELECT COUNT(*) FROM takp_bot_data;'),[['0']])

    def test_storage_engine_and_name_trigger_changes_disable_creation(self):
        self.engine.mysql('ALTER TABLE takp_bot_runtime ENGINE=MyISAM;')
        with self.assertRaisesRegex(ValueError,'24 storage'): bots.context(self.engine)
        self.engine.mysql('ALTER TABLE takp_bot_runtime ENGINE=InnoDB; DROP TRIGGER takp_bot_name_insert;')
        with self.assertRaisesRegex(ValueError,'shared-name triggers'): bots.context(self.engine)

    def test_trigger_with_qualified_name_but_changed_body_is_rejected(self):
        self.engine.mysql('CREATE OR REPLACE TRIGGER takp_bot_name_insert AFTER INSERT ON takp_bot_data FOR EACH ROW SET @ignored_bot_name=NEW.name;')
        with self.assertRaisesRegex(ValueError,'shared-name trigger changed'): bots.context(self.engine)


class ModernStorageFixtureEngine(era_fixture.FixtureEngine):
    profile='traditional'
    def __init__(self,case):
        super().__init__(case); self.config['bot_database_epoch']='a'*32
    def check_cancel(self): pass
    def log(self,message): pass


@unittest.skipUnless(os.environ.get('ERARULES_MARIADB')=='1','Set ERARULES_MARIADB=1 to run the isolated real database fixture')
class ModernBotStorageMariaDBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): era_fixture.EraMariaDBTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls): era_fixture.EraMariaDBTests.tearDownClass.__func__(cls)
    def setUp(self):
        self.work=self.root/self._testMethodName
        for name in ('run','backups','logs','server/bin'): (self.work/name).mkdir(parents=True)
        self.engine=ModernStorageFixtureEngine(self)
        self.engine.mysql('DROP DATABASE IF EXISTS peq; CREATE DATABASE peq CHARACTER SET utf8mb4;',database=False)
        self.engine.mysql("""
        CREATE TABLE account(id INT PRIMARY KEY,name VARCHAR(30) NOT NULL) ENGINE=MyISAM;
        CREATE TABLE character_data(id INT UNSIGNED PRIMARY KEY,account_id INT NOT NULL,name VARCHAR(64) NOT NULL UNIQUE,level INT UNSIGNED NOT NULL,deleted_at DATETIME NULL) ENGINE=MyISAM;
        CREATE TABLE bot_data(bot_id INT UNSIGNED PRIMARY KEY,owner_id INT UNSIGNED NOT NULL,name VARCHAR(15) NOT NULL UNIQUE,`class` TINYINT UNSIGNED NOT NULL,race SMALLINT UNSIGNED NOT NULL,gender TINYINT UNSIGNED NOT NULL) ENGINE=MyISAM;
        CREATE TABLE bot_settings(bot_id INT PRIMARY KEY,value VARCHAR(32) NOT NULL) ENGINE=MyISAM;
        CREATE TABLE bot_buffs(bot_id INT PRIMARY KEY,value VARCHAR(32) NOT NULL) ENGINE=InnoDB;
        CREATE TABLE data_buckets(id INT PRIMARY KEY,character_id INT,key_name VARCHAR(64),value TEXT) ENGINE=MyISAM;
        CREATE TABLE bot_create_combinations(race INT UNSIGNED PRIMARY KEY,classes INT UNSIGNED NOT NULL) ENGINE=MyISAM;
        CREATE TABLE bot_spells_entries(id INT PRIMARY KEY,value VARCHAR(32) NOT NULL) ENGINE=MyISAM;
        CREATE TABLE items(id INT PRIMARY KEY,name VARCHAR(64) NOT NULL) ENGINE=MyISAM;
        CREATE TABLE bot_custom_content(id INT PRIMARY KEY,value VARCHAR(32) NOT NULL) ENGINE=MyISAM;
        INSERT INTO account VALUES(7,'Thor');
        INSERT INTO character_data VALUES(101,7,'Izadar',22,NULL);
        INSERT INTO bot_data VALUES(11,101,'Existing',1,1,0);
        INSERT INTO bot_settings VALUES(11,'Preserve settings');
        INSERT INTO bot_buffs VALUES(11,'Preserve buffs');
        INSERT INTO data_buckets VALUES(1,101,'bot_creation_limit','128');
        INSERT INTO bot_create_combinations VALUES(1,3);
        INSERT INTO bot_spells_entries VALUES(1,'Read-only content');
        INSERT INTO items VALUES(1,'Preserve item');
        INSERT INTO bot_custom_content VALUES(1,'Unrelated custom content');
        """)
        (self.work/'server/bin/build-info.json').write_text(json.dumps({'format':1,'recipe':'isolated-fixture','source':{'repo':'Traditional fixture'}}))
        self.ctx=bots.context(self.engine)
        self.args={'identity':self.ctx['identity']}
    def values(self,sql): return [line.split('\t') for line in self.engine.mysql(sql).splitlines()[1:]]
    def engines(self):
        return dict(self.values("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();"))
    def review(self):
        result=bots.storage_preview(self.engine,self.args)
        return result,dict(self.args,preview_hash=result['preview_hash'])

    def test_review_backup_conversion_preserves_rows_and_excludes_content(self):
        state=bots.status(self.engine,{})
        self.assertTrue(state['storage']['needed'])
        self.assertFalse(state['creation']['available'])
        review,args=self.review()
        expected=['character_data','bot_data','bot_settings','data_buckets']
        self.assertEqual([c['table'] for c in review['changes']],expected)
        self.assertTrue(review['backup_required'])
        result=bots.storage_enable(self.engine,args)
        self.assertTrue(result['complete'])
        self.assertEqual(result['converted'],expected)
        self.assertEqual(result['remaining'],[])
        self.assertNotEqual(result['identity'],self.ctx['identity'])
        with gzip.open(self.work/result['backup'],'rb') as backup:
            dump=backup.read()
        self.assertIn(b'CREATE TABLE `character_data`',dump)
        self.assertIn(b'Preserve settings',dump)
        for name in expected: self.assertEqual(self.engines()[name],'InnoDB')
        for name in ('account','bot_create_combinations','bot_spells_entries','items','bot_custom_content'):
            self.assertEqual(self.engines()[name],'MyISAM')
        self.assertEqual(self.values('SELECT id,account_id,name,level FROM character_data;'),[['101','7','Izadar','22']])
        self.assertEqual(self.values('SELECT * FROM bot_settings;'),[['11','Preserve settings']])
        self.assertFalse(bots.status(self.engine,{})['storage']['needed'])
        with self.assertRaisesRegex(ValueError,'database or server deployment changed'): bots.context(self.engine,self.args)

    def test_failed_or_missing_backup_never_reaches_alter(self):
        _,args=self.review(); real=self.engine.mysql; queries=[]
        def record(sql,**kwargs): queries.append(sql); return real(sql,**kwargs)
        with patch.object(self.engine,'mysql',side_effect=record),patch.object(self.engine,'backup_database',side_effect=ValueError('Dump failed')):
            with self.assertRaisesRegex(ValueError,'Dump failed'): bots.storage_enable(self.engine,args)
        self.assertFalse(any(sql.startswith('ALTER TABLE') for sql in queries))
        self.assertEqual(self.engines()['character_data'],'MyISAM')
        _,args=self.review(); queries.clear()
        with patch.object(self.engine,'mysql',side_effect=record),patch.object(self.engine,'backup_database',return_value={'file':'backups/missing.sql.gz'}):
            with self.assertRaises(ValueError): bots.storage_enable(self.engine,args)
        self.assertFalse(any(sql.startswith('ALTER TABLE') for sql in queries))

    def test_schema_change_or_running_server_rejects_before_backup(self):
        _,args=self.review()
        self.engine.mysql('ALTER TABLE bot_settings ADD COLUMN changed INT DEFAULT 0;')
        with patch.object(self.engine,'backup_database') as backup:
            with self.assertRaisesRegex(ValueError,'changed since review'): bots.storage_enable(self.engine,args)
        backup.assert_not_called()
        self.engine.running=True
        with patch.object(self.engine,'backup_database') as backup:
            with self.assertRaisesRegex(ValueError,'Stop the server'): bots.storage_preview(self.engine,self.args)
        backup.assert_not_called()
        self.assertEqual(self.engines()['character_data'],'MyISAM')

    def test_partial_failure_reports_real_conversions_and_can_review_remaining(self):
        _,args=self.review(); real=self.engine.mysql
        def fail_second(sql,**kwargs):
            if sql=='ALTER TABLE `bot_data` ENGINE=InnoDB;': raise ValueError('Second ALTER failed')
            return real(sql,**kwargs)
        with patch.object(self.engine,'mysql',side_effect=fail_second): result=bots.storage_enable(self.engine,args)
        self.assertFalse(result['complete'])
        self.assertEqual(result['converted'],['character_data'])
        self.assertEqual([r['name'] for r in result['remaining']],['bot_data','bot_settings','data_buckets'])
        self.assertIn('Second ALTER failed',result['error'])
        self.assertTrue((self.work/result['backup']).is_file())
        self.assertEqual(self.engines()['character_data'],'InnoDB')
        self.assertEqual(self.engines()['bot_data'],'MyISAM')
        self.args={'identity':result['identity']}
        review,newargs=self.review()
        self.assertEqual([c['table'] for c in review['changes']],['bot_data','bot_settings','data_buckets'])
        complete=bots.storage_enable(self.engine,newargs)
        self.assertTrue(complete['complete'])
        self.assertEqual(self.values('SELECT name FROM bot_data;'),[['Existing']])
        self.assertEqual(len(list((self.work/'backups').glob('*.gz'))),2)

    def test_unsupported_or_view_storage_is_not_offered_for_conversion(self):
        self.engine.mysql('CREATE VIEW bot_owner_options AS SELECT 1 AS id;')
        state=bots.status(self.engine,{})
        self.assertTrue(state['storage']['needed'])
        self.assertFalse(state['storage']['available'])
        self.assertIn('bot_owner_options',state['storage']['reason'])
        with patch.object(self.engine,'backup_database') as backup:
            with self.assertRaisesRegex(ValueError,'bot_owner_options'): bots.storage_preview(self.engine,self.args)
        backup.assert_not_called()


if __name__=='__main__': unittest.main()
