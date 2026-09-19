"""Real MariaDB content edits, stale previews, rollback/audit and client exports.

Run inside the ARM64 runtime, or against an isolated CI MariaDB service with
TRASC_TEST_MYSQL_PORT. No production databases are used.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'backend'),'/opt/trasc']
from engine import Engine, CLIENT_FILES
import spire

SEED='''
CREATE TABLE items(id int PRIMARY KEY, Name varchar(64), hp int NOT NULL DEFAULT 0, price bigint unsigned NOT NULL DEFAULT 0,
 clickeffect int DEFAULT -1, custom_field varchar(100), raw_data varbinary(20)) ENGINE=InnoDB;
CREATE TABLE npc_types(id int PRIMARY KEY,name varchar(64),level tinyint unsigned,hp int,loottable_id int,merchant_id int) ENGINE=InnoDB;
CREATE TABLE loottable(id int PRIMARY KEY,name varchar(64),mincash int unsigned DEFAULT 0,maxcash int unsigned DEFAULT 0) ENGINE=InnoDB;
CREATE TABLE lootdrop(id int PRIMARY KEY,name varchar(64)) ENGINE=InnoDB;
CREATE TABLE loottable_entries(loottable_id int,lootdrop_id int,probability float DEFAULT 100,multiplier int DEFAULT 1,mindrop int DEFAULT 0,droplimit int DEFAULT 0,PRIMARY KEY(loottable_id,lootdrop_id)) ENGINE=InnoDB;
CREATE TABLE lootdrop_entries(lootdrop_id int,item_id int,item_charges smallint unsigned DEFAULT 1,chance float DEFAULT 100,equip_item tinyint DEFAULT 0,PRIMARY KEY(lootdrop_id,item_id)) ENGINE=InnoDB;
CREATE TABLE merchantlist(merchantid int,slot int unsigned,item int,probability int DEFAULT 100,min_status int DEFAULT 0,max_status int DEFAULT 255,custom_flag int DEFAULT 9,PRIMARY KEY(merchantid,slot)) ENGINE=InnoDB;
CREATE TABLE spells_new(id int PRIMARY KEY,name varchar(64),mana int DEFAULT 0,custom_spell int DEFAULT 17) ENGINE=InnoDB;
CREATE TABLE db_str(id int,type int,value varchar(255),PRIMARY KEY(id,type)) ENGINE=InnoDB;
CREATE TABLE aa_ability(id int PRIMARY KEY,name varchar(64),first_rank_id int,enabled tinyint) ENGINE=InnoDB;
CREATE TABLE aa_ranks(id int PRIMARY KEY,title_sid int,desc_sid int,cost int,spell int,prev_id int DEFAULT 0,next_id int DEFAULT 0) ENGINE=InnoDB;
CREATE TABLE aa_rank_effects(rank_id int,slot int,effect_id int,base1 int,base2 int,PRIMARY KEY(rank_id,slot)) ENGINE=InnoDB;
CREATE TABLE character_data(id int PRIMARY KEY,name varchar(64),level int) ENGINE=InnoDB;
INSERT INTO character_data VALUES(1,'Player',50);
INSERT INTO items VALUES(100,'Sword',1,18446744073709551615,-1,'custom stays',X'00FF'),(101,'Potion',0,10,26,'other',NULL);
INSERT INTO npc_types VALUES(1,'Merchant',10,100,10,7);
INSERT INTO loottable VALUES(10,'Treasures',10,20);
INSERT INTO lootdrop VALUES(20,'Weapons');
INSERT INTO loottable_entries VALUES(10,20,100,1,0,0);
INSERT INTO lootdrop_entries VALUES(20,100,1,100,0);
INSERT INTO merchantlist VALUES(7,1,100,100,0,255,42);
INSERT INTO spells_new VALUES(26,'Minor Healing',5,17),(44999,'Last supported',5,17),(45000,'Excluded',5,17);
INSERT INTO db_str VALUES(30,1,'Ability'),(30,4,'Description'),(31,1,'Title only');
INSERT INTO aa_ranks VALUES(40,30,30,1,26,0,0);
INSERT INTO aa_ability VALUES(50,'Healing AA',40,1);
INSERT INTO aa_rank_effects VALUES(40,1,0,1,0);
'''


def run():
    with tempfile.TemporaryDirectory(prefix='spire-') as temp:
        engine=Engine(temp)
        if os.environ.get('TRASC_TEST_MYSQL_PORT'):
            engine.config['database']='spire_test'
            engine.mysql_options.write_text('[client]\nuser=root\npassword=test\nprotocol=tcp\nhost=127.0.0.1\nport='+os.environ['TRASC_TEST_MYSQL_PORT']+'\ndefault-character-set=utf8mb4\n')
            engine.ensure_db=lambda: None
            engine.mysql('CREATE DATABASE IF NOT EXISTS spire_test CHARACTER SET utf8mb4;',database=False)
        try:
            engine.ensure_db();engine.config['database_imported']=True
            engine.mysql(SEED)
            def expect_error(fn,text):
                try: fn()
                except ValueError as e: assert text in str(e),(text,str(e))
                else: raise AssertionError('Expected rejection: '+text)
            def preview(table,key,changed,action='update'):
                d=spire.detail(engine,{'table':table,'key':key}) if action!='insert' else {}
                return spire.preview(engine,dict(table=table,key=key,values=changed,action=action,revision=d.get('revision')))
            def edit(table,key,changed,action='update'):
                p=preview(table,key,changed,action);return spire.apply(engine,{'token':p['token']})
            assert all(e['available'] for e in spire.catalog(engine,{})['entities'])
            assert spire.search(engine,{'table':'items','query':'Sword'})['records'][0]['key']=={'id':'100'}
            assert spire.search(engine,{'table':'merchantlist','query':'Sword'})['records'][0]['values']['item_name']=='Sword'
            assert spire.search(engine,{'table':'merchantlist','query':'Merchant'})['records'][0]['key']=={'merchantid':'7','slot':'1'}
            assert spire.search(engine,{'table':'lootdrop_entries','query':'Weapons'})['records'][0]['values']['item_name']=='Sword'
            assert spire.search(engine,{'table':'loottable_entries','query':'Treasures'})['records'][0]['values']['drop_name']=='Weapons'
            assert not spire.search(engine,{'table':'items','query':"%' OR 1=1 --"})['records']
            assert any(l['table']=='merchantlist' for l in spire.detail(engine,{'table':'npc_types','key':{'id':1}})['links'])
            draft=engine.dispatch('spire_merchant_draft',{'merchantid':'7'})
            assert draft['values']=={'merchantid':'7','slot':'2'} and draft['warnings']
            assert spire.merchant_draft(engine,{'merchantid':8})['values']['slot']=='1'
            engine.mysql('INSERT INTO merchantlist(merchantid,slot,item) VALUES(7,3,101);')
            assert spire.merchant_draft(engine,{'merchantid':7})['values']['slot']=='2'
            engine.mysql('DELETE FROM merchantlist WHERE merchantid=7 AND slot=3;')
            expect_error(lambda:spire.merchant_draft(engine,{'merchantid':0}),'above zero')
            expect_error(lambda:spire.merchant_draft(engine,{'merchantid':"7 OR 1=1"}),'whole number')
            expect_error(lambda:preview('merchantlist',{}, {'merchantid':'7','slot':'2'},'insert'),'Choose an item')
            # A suggestion is not a reservation: an occupied slot still cannot overwrite stock.
            suggested=preview('merchantlist',{},dict(draft['values'],item='101'),'insert')
            engine.mysql('INSERT INTO merchantlist(merchantid,slot,item) VALUES(7,2,100);')
            expect_error(lambda:spire.apply(engine,{'token':suggested['token']}),'Record changed')
            engine.mysql('DELETE FROM merchantlist WHERE merchantid=7 AND slot=2;')
            item=spire.detail(engine,{'table':'items','key':{'id':101}})
            assert any(f['name']=='clickeffect' and f['editable'] for f in item['fields'])
            assert any(l['table']=='spells_new' and l['filters']=={'id':'26'} for l in item['links'])
            expect_error(lambda:preview('items',{'id':101},{'clickeffect':'999'}),'does not exist')
            # Full-row concurrency token includes custom/binary fields; untouched values survive.
            p=preview('items',{'id':100},{'Name':"Zöe's blade",'hp':'12'})
            assert 'Sword' in engine.mysql('SELECT Name FROM items WHERE id=100;')
            saved=spire.apply(engine,{'token':p['token']});assert (engine.work/saved['backup']).stat().st_size>0
            assert engine.mysql('SELECT hp,custom_field,HEX(raw_data),price FROM items WHERE id=100;').splitlines()[1]=='12\tcustom stays\t00FF\t18446744073709551615'
            expect_error(lambda:spire.apply(engine,{'token':p['token']}),'already saved')
            edit('npc_types',{'id':1},{'level':'12'})
            edit('loottable',{'id':10},{'mincash':'15'})
            edit('lootdrop',{'id':20},{'name':'Rare weapons'})
            edit('loottable_entries',{'loottable_id':10,'lootdrop_id':20},{'probability':'55.5'})
            edit('lootdrop_entries',{}, {'lootdrop_id':'20','item_id':'101','chance':'25'},'insert')
            edit('merchantlist',{}, {'merchantid':'7','slot':'2','item':'101'},'insert')
            edit('merchantlist',{'merchantid':7,'slot':2},{'probability':'50'})
            edit('merchantlist',{'merchantid':7,'slot':2},{},'delete')
            assert engine.mysql('SELECT custom_flag FROM merchantlist WHERE slot=1;').splitlines()[1]=='42'
            expect_error(lambda:preview('merchantlist',{}, {'merchantid':'7','slot':'3','item':'999'},'insert'),'does not exist')
            expect_error(lambda:preview('lootdrop_entries',{'lootdrop_id':20,'item_id':100},{'chance':'101'}),'allowed range')
            expect_error(lambda:preview('loottable',{'id':10},{'mincash':'100'}),'must not exceed')
            expect_error(lambda:preview('items',{'id':100},{'custom_field':'overwrite'}),'Unsupported')
            expect_error(lambda:preview('items',{'id':100},{'id':'200'}),'immutable')
            expect_error(lambda:preview('items',{'id':100},{},'delete'),'not supported')
            p=preview('items',{'id':100},{'hp':'13'})
            engine.mysql("UPDATE items SET custom_field='external edit' WHERE id=100;")
            expect_error(lambda:spire.apply(engine,{'token':p['token']}),'Record changed')
            p=preview('items',{'id':100},{'hp':'14'})
            with patch.object(engine,'server_running',return_value=True):
                expect_error(lambda:spire.apply(engine,{'token':p['token']}),'Stop the server')
            p=preview('items',{'id':100},{'hp':'15'})
            with patch.object(engine,'backup_database',side_effect=ValueError('backup failed')):
                expect_error(lambda:spire.apply(engine,{'token':p['token']}),'backup failed')
            assert engine.mysql('SELECT hp FROM items WHERE id=100;').splitlines()[1]=='12'
            # Change after preflight, during the backup: SQL guard must roll back the edit and audit.
            p=preview('items',{'id':100},{'hp':'16'});backup=engine.backup_database
            def racing_backup(a):
                r=backup(a);engine.mysql('UPDATE items SET hp=19 WHERE id=100;');return r
            with patch.object(engine,'backup_database',side_effect=racing_backup):
                expect_error(lambda:spire.apply(engine,{'token':p['token']}),'did not commit')
            assert engine.mysql('SELECT hp FROM items WHERE id=100;').splitlines()[1]=='19'
            assert not spire.rows(engine,'SELECT id FROM '+spire.ident(spire.AUDIT)+' WHERE id='+spire.literal(p['token'])+';')
            edit('db_str',{'id':30,'type':4},{'value':"Healing's description"})
            assert spire.detail(engine,{'table':'db_str','key':{'id':30,'type':1}})['values']['value']=='Ability'
            expect_error(lambda:preview('db_str',{'id':30,'type':4},{'value':'broken^export'}),'corrupt client export')
            expect_error(lambda:preview('aa_ranks',{'id':40},{'desc_sid':'31'}),'does not exist')
            edit('aa_ability',{'id':50},{'name':'Improved Healing'})
            edit('aa_ranks',{'id':40},{'cost':'3','spell':'45000'})
            edit('aa_rank_effects',{'rank_id':40,'slot':1},{'base1':'5'})
            edit('spells_new',{'id':45000},{'name':'Edited high spell'})
            edit('spells_new',{'id':26},{'mana':'8'})
            assert spire.export_status(engine)['pending_export']==6
            # Use the real export/install/filter path, with only the compiled exporter substituted.
            client=engine.work/'client/current';client.mkdir();(client/'trasc-client.json').write_text('{"imported":true}')
            def spell_bytes():
                return b''.join(b'^'.join([r['values']['id'].encode(),r['values']['name'].encode()]+[b'0']*235)+b'\r\n'
                    for r in spire.search(engine,{'table':'spells_new'})['records'])
            (client/'spells_us.txt').write_bytes(spell_bytes());(client/'Resources').mkdir();(client/'Resources/spells_us.txt').write_bytes(spell_bytes())
            engine.apply_spell_test({})
            original_run=engine.run
            def exporter(argv,**kwargs):
                if str(argv[0]).endswith('export_client_files'):
                    folder=engine.work/'server/export';folder.mkdir(exist_ok=True)
                    for name in CLIENT_FILES:(folder/name).write_bytes(b'fixture data\n')
                    (folder/'spells_us.txt').write_bytes(spell_bytes())
                    data=spire.detail(engine,{'table':'db_str','key':{'id':30,'type':4}})['values']['value']
                    (folder/'dbstr_us.txt').write_bytes(('30^4^'+data+'\n').encode())
                else:return original_run(argv,**kwargs)
            with patch.object(engine,'write_config'),patch.object(engine,'run',side_effect=exporter):
                exported=engine.export_client({})
            assert exported['filter_applied'] and exported['local_client_synced']
            for folder in (client,client/'Resources'):
                data=(folder/'spells_us.txt').read_bytes();assert b'44999^' in data and b'45000^' not in data
                assert b"Healing's description" in (folder/'dbstr_us.txt').read_bytes()
            assert 'Edited high spell' in engine.mysql('SELECT name FROM spells_new WHERE id=45000;')
            assert spire.export_status(engine)['pending_export']==0
            engine.restore_spell_test({})
            assert b'45000^Edited high spell' in (client/'spells_us.txt').read_bytes()
            assert spire.history(engine,{})['entries'][0]['exported']==exported['file']
            assert engine.mysql('SELECT level FROM character_data;').splitlines()[1]=='50'
            engine.mysql('ALTER TABLE lootdrop ENGINE=MyISAM;')
            expect_error(lambda:preview('lootdrop',{'id':20},{'name':'unsafe'}),'InnoDB')
            engine.mysql('ALTER TABLE merchantlist DROP PRIMARY KEY;')
            assert spire.search(engine,{'table':'merchantlist','query':'Potion'})['read_only']
            print('PASS: real content browse/link/edit/insert/delete, validation, composite keys, backup, concurrent edit rollback, durable audit, character isolation, AA/string edits and filtered/full client export',flush=True)
        finally:
            if os.environ.get('TRASC_TEST_MYSQL_PORT'):engine.mysql('DROP DATABASE IF EXISTS spire_test;',database=False)
            engine.shutdown()


if __name__=='__main__':run()
